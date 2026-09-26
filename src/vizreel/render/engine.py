"""Render the charts of a spec to clips, one file per chart."""

import os
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from vizreel.charts.registry import builtin_registry
from vizreel.errors import OutputError, RenderError, VizreelError
from vizreel.render.layout import build_layout
from vizreel.spec.loader import load_spec
from vizreel.spec.models import BaseChart, Spec
from vizreel.themes.loader import load_theme
from vizreel.themes.models import Theme

Quality = Literal["preview", "final"]
OutputFormat = Literal["mov", "webm", "mp4"]

RESOLUTIONS: dict[str, tuple[int, int]] = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "1440p": (2560, 1440),
    "4k": (3840, 2160),
}
PREVIEW_SIZE = (854, 480)
PREVIEW_FPS = 15
PREVIEW_SUFFIX = ".preview"
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
    """

    out_dir: Path = Path("out")
    only: tuple[str, ...] = ()
    quality: Quality = "final"
    format: OutputFormat | None = None
    still: bool = False


@dataclass(frozen=True)
class ChartResult:
    """Outcome of rendering one chart.

    Attributes:
        chart_id: The chart's id.
        video: The clip, or None if rendering failed.
        still: The PNG of the last frame, if requested and rendering succeeded.
        error: Why rendering failed, or None.
        seconds: Time spent rendering.
    """

    chart_id: str
    video: Path | None = None
    still: Path | None = None
    error: str | None = None
    seconds: float = 0.0


@dataclass(frozen=True)
class FrameSettings:
    """Pixel size, frame rate and background of the output."""

    width: int
    height: int
    fps: int
    format: OutputFormat

    @property
    def transparent(self) -> bool:
        """Whether the output keeps a transparent background."""
        return self.format in TRANSPARENT_FORMATS


def frame_settings(spec: Spec, options: RenderOptions) -> FrameSettings:
    """Combine the spec's `meta` with the command-line options."""
    output_format = options.format or spec.meta.format
    if options.quality == "preview":
        return FrameSettings(*PREVIEW_SIZE, PREVIEW_FPS, output_format)
    width, height = RESOLUTIONS[spec.meta.resolution]
    return FrameSettings(width, height, spec.meta.fps, output_format)


def output_paths(
    chart_id: str, options: RenderOptions, output_format: OutputFormat
) -> tuple[Path, Path | None]:
    """Return the clip path and, if a still is requested, the PNG path for a chart.

    Preview files get a `.preview` suffix, so a preview never replaces a final clip.
    """
    stem = chart_id + (PREVIEW_SUFFIX if options.quality == "preview" else "")
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
        result = _render_safely(chart, theme, settings, options, reraise)
        results.append(result)
        if on_done:
            on_done(result)
    return results


def _render_safely(
    chart: BaseChart,
    theme: Theme,
    settings: FrameSettings,
    options: RenderOptions,
    reraise: bool,
) -> ChartResult:
    started = time.perf_counter()
    video, still = output_paths(chart.id, options, settings.format)
    try:
        render_chart(chart, theme, settings, video, still)
    except VizreelError as exc:
        return ChartResult(chart.id, error=str(exc), seconds=time.perf_counter() - started)
    except Exception as exc:
        if reraise:
            raise
        error = f"unexpected error: {type(exc).__name__}: {exc}"
        return ChartResult(chart.id, error=error, seconds=time.perf_counter() - started)
    return ChartResult(chart.id, video, still, seconds=time.perf_counter() - started)


def render_chart(
    chart: BaseChart,
    theme: Theme,
    settings: FrameSettings,
    video_path: Path,
    still_path: Path | None,
) -> None:
    """Render one chart to `video_path` and, if given, its last frame to `still_path`.

    Manim's cache and partial movie files go to a temporary folder that is removed afterwards.
    """
    from manim import Camera, tempconfig

    from vizreel.render.scene import ChartScene

    chart_type = builtin_registry().get(chart.type)
    layout = build_layout(
        theme.sizes,
        panel=theme.background_panel and settings.transparent,
        title_lines=1 if chart.title else 0,
        subtitle_lines=1 if chart.subtitle else 0,
        source_lines=1 if chart.source else 0,
    )
    with tempfile.TemporaryDirectory(prefix="vizreel-", ignore_cleanup_errors=True) as media_dir:
        manim_config = {
            "verbosity": "ERROR",
            "progress_bar": "none",
            "media_dir": media_dir,
            "output_file": chart.id,
            "pixel_width": settings.width,
            "pixel_height": settings.height,
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
            scene = ChartScene(chart_type(chart, theme, layout))
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
