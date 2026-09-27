"""Render the charts of a spec to clips, one file per chart."""

import math
import os
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from vizreel.charts.base import Continuation
from vizreel.charts.registry import builtin_registry
from vizreel.errors import OutputError, RenderError, VizreelError
from vizreel.render.layout import Aspect, Layout, build_layout, frame_size
from vizreel.spec.loader import load_spec
from vizreel.spec.models import BaseChart, SequencedChart, Spec
from vizreel.themes.loader import load_theme
from vizreel.themes.models import Theme

Quality = Literal["preview", "final"]
OutputFormat = Literal["mov", "webm", "mp4"]

SHORT_SIDES: dict[str, int] = {"720p": 720, "1080p": 1080, "1440p": 1440, "4k": 2160}
"""Pixels on the short side of the frame for each `meta.resolution`."""
PREVIEW_SHORT_SIDE = 480
PREVIEW_FPS = 15
PREVIEW_SUFFIX = ".preview"
VERTICAL_SUFFIX = ".vertical"
TRANSPARENT_FORMATS = frozenset({"mov", "webm"})


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
    """

    out_dir: Path = Path("out")
    only: tuple[str, ...] = ()
    quality: Quality = "final"
    format: OutputFormat | None = None
    still: bool = False
    aspect: Aspect | None = None


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
    fps: int
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
    return (long_side, short_side) if aspect == "16:9" else (short_side, long_side)


def frame_settings(spec: Spec, options: RenderOptions) -> FrameSettings:
    """Combine the spec's `meta` with the command-line options."""
    output_format = options.format or spec.meta.format
    aspect = options.aspect or spec.meta.aspect
    if options.quality == "preview":
        short_side, fps = PREVIEW_SHORT_SIDE, PREVIEW_FPS
    else:
        short_side, fps = SHORT_SIDES[spec.meta.resolution], spec.meta.fps
    return FrameSettings(*frame_pixels(short_side, aspect), fps, output_format, aspect)


def output_paths(
    chart_id: str, options: RenderOptions, settings: FrameSettings, step: int | None = None
) -> tuple[Path, Path | None]:
    """Return the clip path and, if a still is requested, the PNG path for a chart.

    The clips of a sequence are numbered from 1. Vertical files get a `.vertical` suffix and
    preview files a `.preview` suffix, so that renders of one chart in another shape or
    quality never replace each other.
    """
    stem = (
        chart_id
        + (f".{step}" if step is not None else "")
        + (VERTICAL_SUFFIX if settings.aspect == "9:16" else "")
        + (PREVIEW_SUFFIX if options.quality == "preview" else "")
    )
    output_format = settings.format
    video = options.out_dir / f"{stem}.{output_format}"
    still = options.out_dir / f"{stem}.png" if options.still else None
    return video, still


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
            result = _render_safely(plan, steps, theme, settings, options, reraise)
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
        render_chart(plan.chart, theme, settings, video, still, plan.continuation)
    except VizreelError as exc:
        return result(error=str(exc))
    except Exception as exc:
        if reraise:
            raise
        return result(error=f"unexpected error: {type(exc).__name__}: {exc}")
    return result(video=video, still=still)


def render_chart(
    chart: BaseChart,
    theme: Theme,
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

    from vizreel.render import elements
    from vizreel.render.scene import ChartScene

    chart_type = builtin_registry().get(chart.type)

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
            "frame_rate": settings.fps,
            "transparent": settings.transparent,
            "format": settings.format,
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
            scene = ChartScene(chart_type(chart, theme, layout), continuation)
            scene.render()
            _move(Path(scene.renderer.file_writer.movie_file_path), video_path)
            if still_path is not None:
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
