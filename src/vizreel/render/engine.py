"""Render the charts of a spec to clips, one file per chart."""

import math
import os
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal

from vizreel.charts.base import Continuation
from vizreel.charts.registry import BUILT_IN, chart_registry
from vizreel.errors import OutputError, RenderError, VizreelError
from vizreel.format.locales import Locale, locale_for
from vizreel.render.layout import Aspect, Layout, build_layout, frame_size
from vizreel.spec.loader import load_spec
from vizreel.spec.models import BaseChart, Motion, SequencedChart, Spec
from vizreel.themes.loader import load_theme
from vizreel.themes.models import Theme

Quality = Literal["preview", "final"]
OutputFormat = Literal["mov", "webm", "mp4", "prores", "png"]

SHORT_SIDES: dict[str, int] = {"720p": 720, "1080p": 1080, "1440p": 1440, "4k": 2160}
"""Pixels on the short side of the frame for each `meta.resolution`."""
PREVIEW_SHORT_SIDE = 480
PREVIEW_FPS = 15
PREVIEW_SUFFIX = ".preview"
ASPECT_SUFFIXES: dict[str, str] = {"16:9": "", "9:16": ".vertical", "1:1": ".square"}
"""What a clip's file name says about its shape, so that shapes never replace each other."""
TRANSPARENT_FORMATS = frozenset({"mov", "webm", "prores", "png"})
MANIM_FORMATS: dict[str, str] = {"prores": "mov", "png": "mov"}
"""What Manim writes for the formats it does not write itself; `transcode` converts it."""


@dataclass(frozen=True)
class RenderOptions:
    """How to render a spec. `None` means: use the spec's `meta` value.

    Attributes:
        out_dir: Folder for the output files.
        only: Chart ids to render. Empty renders every chart.
        quality: "preview" renders small and at 15 fps; "final" uses the spec settings.
        format: Output format, overriding `meta.format`.
        still: Also save the last frame of each chart as PNG.
        aspect: Frame shape, overriding `meta.aspect`.
        fps: Frame rate of a final render, overriding `meta.fps`. Previews stay at 15 fps.
    """

    out_dir: Path = Path("out")
    only: tuple[str, ...] = ()
    quality: Quality = "final"
    format: OutputFormat | None = None
    still: bool = False
    aspect: Aspect | None = None
    fps: float | None = None


@dataclass(frozen=True)
class ChartResult:
    """Outcome of rendering one clip of a chart.

    Attributes:
        chart_id: The chart's id.
        video: The clip, or None if rendering failed.
        still: The PNG of the last frame, if requested and rendering succeeded.
        error: Why rendering failed, or None.
        seconds: Time spent rendering.
        step: For a chart told as a sequence, which clip this is, from 1; else None.
        steps: For a chart told as a sequence, how many clips it has; else None.
    """

    chart_id: str
    video: Path | None = None
    still: Path | None = None
    error: str | None = None
    seconds: float = 0.0
    step: int | None = None
    steps: int | None = None


@dataclass(frozen=True)
class ClipPlan:
    """One clip to render for a chart.

    Attributes:
        chart: The chart as built for the clip, emphasizing the element of its step.
        continuation: For the later clips of a sequence, what follows the build; else None.
        step: For a chart told as a sequence, which clip this is, from 1; else None.
    """

    chart: BaseChart
    continuation: Continuation | None = None
    step: int | None = None


def plan_clips(chart: BaseChart) -> list[ClipPlan]:
    """Return the clips of a chart: one, or one per item of its sequence.

    The first clip of a sequence is the chart emphasizing the first item. Each later clip
    builds the chart emphasizing the item before (the end of the previous clip) and moves
    the emphasis on to its own item.
    """
    if not isinstance(chart, SequencedChart) or not chart.sequence:
        return [ClipPlan(chart)]
    items = chart.sequence
    plans = [ClipPlan(chart.with_highlight(items[0]), step=1)]
    for index in range(1, len(items)):
        plans.append(
            ClipPlan(
                chart.with_highlight(items[index - 1]),
                Continuation(items[index], chart.step_duration),
                step=index + 1,
            )
        )
    return plans


@dataclass(frozen=True)
class FrameSettings:
    """Pixel size, frame rate, shape and background of the output."""

    width: int
    height: int
    fps: Fraction
    format: OutputFormat
    aspect: Aspect = "16:9"

    @property
    def transparent(self) -> bool:
        """Whether the output keeps a transparent background."""
        return self.format in TRANSPARENT_FORMATS


def frame_pixels(short_side: int, aspect: Aspect) -> tuple[int, int]:
    """Width and height in pixels of a frame.

    The long side is rounded up to an even number, which video encoders need.
    """
    long_side = math.ceil(short_side * 16 / 9 / 2) * 2
    if aspect == "1:1":
        return (short_side, short_side)
    return (long_side, short_side) if aspect == "16:9" else (short_side, long_side)


def frame_settings(spec: Spec, options: RenderOptions) -> FrameSettings:
    """Combine the spec's `meta` with the command-line options."""
    output_format = options.format or spec.meta.format
    aspect = options.aspect or spec.meta.aspect
    fps: float
    if options.quality == "preview":
        short_side, fps = PREVIEW_SHORT_SIDE, PREVIEW_FPS
    else:
        short_side, fps = SHORT_SIDES[spec.meta.resolution], options.fps or spec.meta.fps
    return FrameSettings(
        *frame_pixels(short_side, aspect), exact_frame_rate(fps), output_format, aspect
    )


def exact_frame_rate(fps: float) -> Fraction:
    """Return a frame rate as the exact ratio video files store: 29.97 is 30000/1001.

    The NTSC rates 23.976, 29.97 and 59.94 are 24, 30 and 60 slowed by 1000/1001; the
    others are whole numbers.
    """
    if fps == round(fps):
        return Fraction(round(fps))
    return Fraction(round(fps * 1001 / 1000) * 1000, 1001)


def output_paths(
    chart_id: str, options: RenderOptions, settings: FrameSettings, step: int | None = None
) -> tuple[Path, Path | None]:
    """Return the clip path and, if a still is requested, the PNG path for a chart.

    A PNG sequence goes in a folder named like the clip, and a ProRes clip is `ID.prores.mov`,
    so it never replaces a QuickTime Animation clip of the same chart.

    The clips of a sequence are numbered from 1. Vertical files get a `.vertical` suffix and
    preview files a `.preview` suffix, so that renders of one chart in another shape or
    quality never replace each other.
    """
    stem = (
        chart_id
        + (f".{step}" if step is not None else "")
        + ASPECT_SUFFIXES[settings.aspect]
        + (PREVIEW_SUFFIX if options.quality == "preview" else "")
    )
    if settings.format == "png":
        video = options.out_dir / stem
    elif settings.format == "prores":
        video = options.out_dir / f"{stem}.prores.mov"
    else:
        video = options.out_dir / f"{stem}.{settings.format}"
    still = options.out_dir / f"{stem}.png" if options.still else None
    return video, still


def clip_theme(theme: Theme, spec_motion: Motion, chart_motion: Motion, *, last: bool) -> Theme:
    """Return the theme a clip renders with: the theme's motion under the spec's and chart's.

    Each field of the chart's `motion` goes over the spec's, which goes over the theme's. Only
    the last clip of a chart leaves the screen, so the clips of a sequence cut together. A
    clip that leaves holds for its exit on top of the theme's hold, which the chart types
    count in their timing; the scene then plays the exit at the end of that hold.
    """
    motion = theme.motion.model_copy(
        update={
            **spec_motion.model_dump(exclude_none=True),
            **chart_motion.model_dump(exclude_none=True),
        }
    )
    if not last:
        motion = motion.model_copy(update={"exit": "none"})
    elif motion.exit != "none":
        motion = motion.model_copy(update={"hold": motion.hold + motion.exit_time})
    return theme.model_copy(update={"motion": motion})


def select_charts(spec: Spec, only: tuple[str, ...]) -> list[BaseChart]:
    """Return the charts to render, in spec order.

    Raises:
        RenderError: An id in `only` does not exist in the spec.
    """
    ids = [chart.id for chart in spec.charts]
    unknown = [chart_id for chart_id in only if chart_id not in ids]
    if unknown:
        raise RenderError(
            f"no chart with id {', '.join(repr(u) for u in unknown)}. Ids in the spec: "
            f"{', '.join(ids)}"
        )
    return [chart for chart in spec.charts if not only or chart.id in only]


def render_spec(
    spec_path: Path,
    options: RenderOptions,
    *,
    on_start: Callable[[BaseChart], None] | None = None,
    on_done: Callable[[ChartResult], None] | None = None,
    reraise: bool = False,
) -> list[ChartResult]:
    """Render every selected chart of a spec file. A failing chart does not stop the others.

    Args:
        spec_path: The spec file.
        options: Output folder, chart selection, quality, format and still.
        on_start: Called before each chart renders.
        on_done: Called after each chart, with its result.
        reraise: Let unexpected exceptions propagate instead of recording them.

    Raises:
        SpecError: The spec is not valid.
        ThemeError: The theme cannot be loaded.
        RenderError: `options.only` names a chart that does not exist, or a theme font
            is not available.
        OutputError: The output folder cannot be created.
    """
    spec = load_spec(spec_path)
    theme = load_theme(spec.meta.theme, spec_path.parent)
    charts = select_charts(spec, options.only)
    settings = frame_settings(spec, options)
    locale = locale_for(spec.meta.locale)
    try:
        options.out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OutputError(f"cannot create {options.out_dir}: {exc.strerror}") from None

    from vizreel.render.fonts import check_theme_fonts

    check_theme_fonts(theme)
    results = []
    for chart in charts:
        if on_start:
            on_start(chart)
        plans = plan_clips(chart)
        steps = len(plans) if plans[0].step is not None else None
        for plan in plans:
            last = plan.step is None or plan.step == steps
            motion_theme = clip_theme(theme, spec.meta.motion, plan.chart.motion, last=last)
            result = _render_safely(plan, steps, motion_theme, locale, settings, options, reraise)
            results.append(result)
            if on_done:
                on_done(result)
            if result.error:
                # The later clips of a sequence would fail the same way.
                break
    return results


def _render_safely(
    plan: ClipPlan,
    steps: int | None,
    theme: Theme,
    locale: Locale,
    settings: FrameSettings,
    options: RenderOptions,
    reraise: bool,
) -> ChartResult:
    chart_id = plan.chart.id
    started = time.perf_counter()
    video, still = output_paths(chart_id, options, settings, plan.step)

    def result(**fields: Any) -> ChartResult:
        seconds = time.perf_counter() - started
        return ChartResult(chart_id, seconds=seconds, step=plan.step, steps=steps, **fields)

    try:
        render_chart(plan.chart, theme, locale, settings, video, still, plan.continuation)
    except VizreelError as exc:
        return result(error=str(exc))
    except Exception as exc:
        if reraise:
            raise
        source = chart_registry().source(plan.chart.type)
        # A bug in another package's chart type is reported to that package, not to vizreel.
        where = "" if source == BUILT_IN else f" in chart type {plan.chart.type} from {source}"
        return result(error=f"unexpected error{where}: {type(exc).__name__}: {exc}")
    return result(video=video, still=still)


def render_chart(
    chart: BaseChart,
    theme: Theme,
    locale: Locale,
    settings: FrameSettings,
    video_path: Path,
    still_path: Path | None,
    continuation: Continuation | None = None,
) -> None:
    """Render one chart to `video_path` and, if given, its last frame to `still_path`.

    With a `continuation`, render the later clip of a sequence that follows this chart's
    clip instead. Manim's cache and partial movie files go to a temporary folder that is
    removed afterwards.
    """
    from manim import Camera, tempconfig

    from vizreel.render import elements, transcode
    from vizreel.render.scene import ChartScene

    chart_type = chart_registry().get(chart.type)

    def layout_with(title_lines: int, subtitle_lines: int) -> Layout:
        return build_layout(
            theme.sizes,
            aspect=settings.aspect,
            panel=theme.background_panel and settings.transparent,
            title_lines=title_lines,
            subtitle_lines=subtitle_lines,
            source_lines=1 if chart.source else 0,
        )

    scene_width, scene_height = frame_size(settings.aspect)
    with tempfile.TemporaryDirectory(prefix="vizreel-", ignore_cleanup_errors=True) as media_dir:
        manim_config = {
            "verbosity": "ERROR",
            "progress_bar": "none",
            "media_dir": media_dir,
            "output_file": chart.id,
            "pixel_width": settings.width,
            "pixel_height": settings.height,
            "frame_width": scene_width,
            "frame_height": scene_height,
            "frame_rate": float(settings.fps),
            "transparent": settings.transparent,
            "format": MANIM_FORMATS.get(settings.format, settings.format),
            "background_color": theme.colors.background,
            "disable_caching": True,
            "write_to_movie": True,
            "save_last_frame": False,
            "preview": False,
        }
        with tempconfig(manim_config):
            # The title band is as tall as the title and subtitle once wrapped to its width,
            # which does not depend on its height.
            width = layout_with(1, 1).title.width
            title, subtitle = elements.header_lines(chart.title, chart.subtitle, theme, width)
            layout = layout_with(len(title), len(subtitle))
            fit = settings.aspect == "9:16" and chart_type.fits_to_content
            scene = ChartScene(
                chart_type(chart, theme, layout, locale),
                continuation,
                relayout=(lambda fitted: chart_type(chart, theme, fitted, locale)) if fit else None,
            )
            scene.render()
            movie = Path(scene.renderer.file_writer.movie_file_path)
            if settings.format == "prores":
                transcode.to_prores(movie, video_path)
            elif settings.format == "png":
                transcode.to_png_sequence(movie, video_path)
            else:
                _move(movie, video_path)
            if still_path is not None:
                # A clip that leaves the screen ends empty; its still is the chart before.
                if scene.still is not None:
                    scene.still.save(still_path)
                else:
                    camera = scene.renderer.camera
                    assert isinstance(camera, Camera)
                    camera.get_image().save(still_path)


def _move(source: Path, target: Path) -> None:
    try:
        os.replace(source, target)
    except OSError:
        try:
            shutil.move(str(source), str(target))
        except OSError as exc:
            raise OutputError(f"cannot write {target}: {exc.strerror}") from None
