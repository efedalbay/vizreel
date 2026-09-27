"""Render charts at preview quality and check the files. Slow: run with `pytest -m render`."""

from pathlib import Path

import av
import numpy as np
import pytest
from typer.testing import CliRunner

from vizreel.cli import app
from vizreel.render.engine import ChartResult, RenderOptions, render_spec

pytestmark = pytest.mark.render

SHOWCASE = Path(__file__).parents[2] / "examples" / "showcase.yaml"
STAT_ID = "peak-valuation"
PREVIEW = (854, 480)
PREVIEW_FPS = 15
STAT_DURATION = 3


def render_stat(out_dir: Path, **options: object) -> ChartResult:
    [result] = render_spec(
        SHOWCASE,
        RenderOptions(out_dir=out_dir, only=(STAT_ID,), quality="preview", **options),  # type: ignore[arg-type]
        reraise=True,
    )
    return result


def frames_rgba(path: Path) -> list[np.ndarray]:
    with av.open(str(path)) as container:
        return [frame.to_ndarray(format="rgba") for frame in container.decode(video=0)]


def image_rgba(path: Path) -> np.ndarray:
    [image] = frames_rgba(path)
    return image


@pytest.fixture(scope="module")
def stat_mov(tmp_path_factory: pytest.TempPathFactory) -> ChartResult:
    return render_stat(tmp_path_factory.mktemp("mov"), still=True)


def test_stat_mov_has_expected_size_rate_and_duration(stat_mov: ChartResult) -> None:
    assert stat_mov.error is None
    assert stat_mov.video is not None
    assert stat_mov.video.name == f"{STAT_ID}.preview.mov"
    with av.open(str(stat_mov.video)) as container:
        stream = container.streams.video[0]
        assert (stream.width, stream.height) == PREVIEW
        assert stream.average_rate == PREVIEW_FPS
        assert stream.codec_context.pix_fmt == "argb"
    assert len(frames_rgba(stat_mov.video)) == STAT_DURATION * PREVIEW_FPS


def test_stat_mov_background_is_transparent(stat_mov: ChartResult) -> None:
    assert stat_mov.video is not None
    frames = frames_rgba(stat_mov.video)

    for frame in (frames[0], frames[-1]):
        assert frame[2, 2, 3] == 0
    center = frames[-1][PREVIEW[1] // 2, PREVIEW[0] // 2]
    assert center[3] == 255


def test_stat_final_hold_is_still(stat_mov: ChartResult) -> None:
    assert stat_mov.video is not None
    frames = frames_rgba(stat_mov.video)
    hold_frames = int(1.5 * PREVIEW_FPS)

    for frame in frames[-hold_frames:]:
        assert np.array_equal(frame, frames[-1])


def test_stat_still_is_last_frame_with_alpha(stat_mov: ChartResult) -> None:
    assert stat_mov.still is not None
    assert stat_mov.video is not None
    assert stat_mov.still.name == f"{STAT_ID}.preview.png"
    still = image_rgba(stat_mov.still)

    assert still.shape == (PREVIEW[1], PREVIEW[0], 4)
    assert still[2, 2, 3] == 0
    assert np.array_equal(still, frames_rgba(stat_mov.video)[-1])


def test_stat_content_stays_in_safe_area(stat_mov: ChartResult) -> None:
    assert stat_mov.still is not None
    alpha = image_rgba(stat_mov.still)[:, :, 3]
    rows, columns = np.nonzero(alpha)
    width, height = PREVIEW

    assert columns.min() >= width * 0.05 - 1
    assert columns.max() <= width * 0.95 + 1
    assert rows.min() >= height * 0.05 - 1
    assert rows.max() <= height * 0.95 + 1


def test_stat_mp4_is_opaque_with_theme_background(tmp_path: Path) -> None:
    result = render_stat(tmp_path, format="mp4")

    assert result.video is not None
    assert result.video.suffix == ".mp4"
    with av.open(str(result.video)) as container:
        assert container.streams.video[0].codec_context.pix_fmt == "yuv420p"
    corner = frames_rgba(result.video)[-1][2, 2]
    assert np.allclose(corner[:3], (0x0E, 0x11, 0x16), atol=4)


def test_stat_webm(tmp_path: Path) -> None:
    result = render_stat(tmp_path, format="webm")

    assert result.video is not None
    assert result.video.suffix == ".webm"
    assert len(frames_rgba(result.video)) == STAT_DURATION * PREVIEW_FPS


def render_one(spec_path: Path, out_dir: Path, chart_id: str) -> ChartResult:
    [result] = render_spec(
        spec_path,
        RenderOptions(out_dir=out_dir, only=(chart_id,), quality="preview", still=True),
        reraise=True,
    )
    return result


def hex_rgb(color: str) -> tuple[int, int, int]:
    return (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))


@pytest.fixture(scope="module")
def bar_mov(tmp_path_factory: pytest.TempPathFactory) -> ChartResult:
    return render_one(SHOWCASE, tmp_path_factory.mktemp("bar"), "offers")


def test_bar_clip_has_expected_duration_and_still_hold(bar_mov: ChartResult) -> None:
    assert bar_mov.error is None
    assert bar_mov.video is not None
    frames = frames_rgba(bar_mov.video)

    assert len(frames) == 5 * PREVIEW_FPS
    for frame in frames[-int(1.5 * PREVIEW_FPS) :]:
        assert np.array_equal(frame, frames[-1])


def test_bar_highlight_colors_in_last_frame(bar_mov: ChartResult) -> None:
    from vizreel.themes.loader import load_theme

    colors = load_theme("default", Path(".")).colors
    assert bar_mov.still is not None
    rgb = image_rgba(bar_mov.still)[:, :, :3].astype(int)

    def matching(color: str) -> np.ndarray:
        return np.all(np.abs(rgb - hex_rgb(color)) <= 6, axis=2)

    highlighted_columns = np.nonzero(matching(colors.highlight))[1]
    # The highlighted bar is the last of three, so it lies in the right third.
    assert highlighted_columns.size > 50
    assert highlighted_columns.min() > PREVIEW[0] * 2 / 3
    assert not matching(colors.accent).any()


def test_vertical_bar_chart_draws_rows(tmp_path: Path) -> None:
    from vizreel.themes.loader import load_theme

    colors = load_theme("default", Path(".")).colors
    [result] = render_spec(
        SHOWCASE,
        RenderOptions(
            out_dir=tmp_path, only=("offers",), quality="preview", still=True, aspect="9:16"
        ),
        reraise=True,
    )
    assert result.still is not None
    rgb = image_rgba(result.still)[:, :, :3].astype(int)
    rows, columns = np.nonzero(np.all(np.abs(rgb - hex_rgb(colors.highlight)) <= 6, axis=2))

    assert rgb.shape[:2] == (PREVIEW[0], PREVIEW[1])
    # The highlighted bar is the last row; a row starts at the left of the chart.
    assert rows.size > 50
    assert rows.min() > PREVIEW[0] / 2
    assert columns.min() < PREVIEW[1] * 0.2


def test_bar_chart_with_eight_long_labels_wraps_them(tmp_path: Path) -> None:
    labels = [f"Northwind region {name}" for name in "ABCDEFGH"]
    bars = ", ".join(f'{{ label: "{label}", value: {i + 1} }}' for i, label in enumerate(labels))
    spec = tmp_path / "bars.yaml"
    spec.write_text(f"version: 1\ncharts:\n  - {{ id: regions, type: bar, bars: [{bars}] }}\n")

    result = render_one(spec, tmp_path, "regions")

    assert result.error is None


def test_bar_label_too_long_even_on_two_lines_is_an_error(tmp_path: Path) -> None:
    long = "Northwind Incorporated International Holdings"
    bars = ", ".join(f'{{ label: "{long} {i}", value: {i + 1} }}' for i in range(8))
    spec = tmp_path / "bars.yaml"
    spec.write_text(f"version: 1\ncharts:\n  - {{ id: regions, type: bar, bars: [{bars}] }}\n")

    [result] = render_spec(spec, RenderOptions(out_dir=tmp_path, quality="preview"))

    assert result.error is not None
    assert "is too long for 8 bars; shorten it" in result.error


@pytest.fixture(scope="module")
def line_mov(tmp_path_factory: pytest.TempPathFactory) -> ChartResult:
    return render_one(SHOWCASE, tmp_path_factory.mktemp("line"), "valuation")


def test_line_clip_has_expected_duration_and_still_hold(line_mov: ChartResult) -> None:
    assert line_mov.error is None
    assert line_mov.video is not None
    frames = frames_rgba(line_mov.video)

    assert len(frames) == 6 * PREVIEW_FPS
    for frame in frames[-int(1.5 * PREVIEW_FPS) :]:
        assert np.array_equal(frame, frames[-1])


def test_line_highlight_marks_the_highlighted_x(line_mov: ChartResult) -> None:
    from vizreel.themes.loader import load_theme

    colors = load_theme("default", Path(".")).colors
    assert line_mov.still is not None
    rgb = image_rgba(line_mov.still)[:, :, :3].astype(int)
    highlight = np.all(np.abs(rgb - hex_rgb(colors.highlight)) <= 12, axis=2)
    columns = np.nonzero(highlight)[1]

    # The guide line stands on "2018", the middle of five x labels.
    assert columns.size > 20
    assert PREVIEW[0] * 0.4 < np.median(columns) < PREVIEW[0] * 0.6


def test_line_chart_with_three_named_series_and_gaps(tmp_path: Path) -> None:
    spec = tmp_path / "lines.yaml"
    spec.write_text(
        "version: 1\ncharts:\n"
        "  - id: users\n"
        "    type: line\n"
        "    title: Northwind users by platform\n"
        '    x: ["2016", "2017", "2018", "2019", "2020", "2021"]\n'
        "    number: { compact: true }\n"
        "    series:\n"
        "      - { name: Web, values: [120000, 180000, 260000, 250000, 310000, 330000] }\n"
        "      - { name: Mobile, values: [null, 90000, 210000, 270000, 300000, 340000] }\n"
        "      - { name: Kiosk, values: [40000, 45000, null, 60000, 62000, 335000] }\n"
        '    highlight: { x: "2019", label: "Mobile passes web" }\n'
    )

    result = render_one(spec, tmp_path, "users")

    assert result.error is None


@pytest.mark.parametrize(
    ("quality", "duration", "frames"),
    [("preview", 3.7, 56), ("final", 2.7, 81)],
)
def test_clip_has_exactly_the_frames_of_its_duration(
    tmp_path: Path, quality: str, duration: float, frames: int
) -> None:
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        "version: 1\nmeta: { resolution: 720p, fps: 30 }\n"
        f"charts: [{{ id: a, type: stat, value: 42, title: Northwind, duration: {duration} }}]\n"
    )

    [result] = render_spec(
        spec,
        RenderOptions(out_dir=tmp_path, quality=quality),
        reraise=True,  # type: ignore[arg-type]
    )

    assert result.video is not None
    assert len(frames_rgba(result.video)) == frames


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("name", "seconds"), [("timeline-2", 7), ("timeline-4", 7), ("timeline-7", 9)]
)
def test_timeline_renders_with_exact_length_and_still_hold(
    tmp_path: Path, name: str, seconds: int
) -> None:
    result = render_one(FIXTURES / f"{name}.yaml", tmp_path, name)

    assert result.error is None
    assert result.video is not None
    frames = frames_rgba(result.video)
    assert len(frames) == seconds * PREVIEW_FPS
    for frame in frames[-int(1.5 * PREVIEW_FPS) :]:
        assert np.array_equal(frame, frames[-1])


def test_timeline_emphasis_marks_the_emphasized_event(tmp_path: Path) -> None:
    from vizreel.themes.loader import load_theme

    colors = load_theme("default", Path(".")).colors
    result = render_one(FIXTURES / "timeline-4.yaml", tmp_path, "timeline-4")
    assert result.still is not None
    rgb = image_rgba(result.still)[:, :, :3].astype(int)
    columns = np.nonzero(np.all(np.abs(rgb - hex_rgb(colors.highlight)) <= 12, axis=2))[1]

    # The third of four events sits in the third quarter of the frame.
    assert columns.size > 20
    assert PREVIEW[0] * 0.5 < np.median(columns) < PREVIEW[0] * 0.75


def test_vertical_timeline_runs_down_the_left(tmp_path: Path) -> None:
    from vizreel.themes.loader import load_theme

    colors = load_theme("default", Path(".")).colors
    [result] = render_spec(
        FIXTURES / "timeline-7.yaml",
        RenderOptions(out_dir=tmp_path, quality="preview", still=True, aspect="9:16"),
        reraise=True,
    )
    assert result.error is None
    assert result.video is not None and result.still is not None
    frames = frames_rgba(result.video)
    rgb = image_rgba(result.still)[:, :, :3].astype(int)
    rows, columns = np.nonzero(np.all(np.abs(rgb - hex_rgb(colors.highlight)) <= 12, axis=2))

    assert len(frames) == 9 * PREVIEW_FPS
    assert rgb.shape[:2] == (PREVIEW[0], PREVIEW[1])
    # The emphasized event is the fourth of seven: its dot and date sit near the middle
    # height, at the left.
    assert PREVIEW[0] * 0.3 < np.median(rows) < PREVIEW[0] * 0.6
    assert columns.min() < PREVIEW[1] * 0.2


def test_a_long_title_wraps_onto_two_lines(tmp_path: Path) -> None:
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        "version: 1\ncharts:\n"
        "  - id: long-title\n    type: bar\n"
        "    title: Northwind revenue in each of its sales regions\n"
        "    bars: [{ label: North, value: 3 }, { label: South, value: 2 }]\n",
        encoding="utf-8",
    )

    [result] = render_spec(
        spec, RenderOptions(out_dir=tmp_path, quality="preview", aspect="9:16"), reraise=True
    )

    assert result.error is None


def test_a_title_too_long_for_two_lines_is_an_error(tmp_path: Path) -> None:
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        "version: 1\ncharts:\n"
        "  - id: long-title\n    type: stat\n    value: 1\n"
        f"    title: {'Northwind revenue in every region ' * 4}\n",
        encoding="utf-8",
    )

    [result] = render_spec(spec, RenderOptions(out_dir=tmp_path, quality="preview"))

    assert result.error is not None
    assert "too long to fit on 2 lines" in result.error


@pytest.mark.parametrize("aspect", ["16:9", "9:16"])
def test_compare_shows_the_change_in_its_direction_color(tmp_path: Path, aspect: str) -> None:
    from vizreel.themes.loader import load_theme

    colors = load_theme("default", Path(".")).colors
    [result] = render_spec(
        SHOWCASE,
        RenderOptions(
            out_dir=tmp_path, only=("headcount",), quality="preview", still=True, aspect=aspect
        ),
        reraise=True,
    )
    assert result.error is None
    assert result.video is not None and result.still is not None
    frames = frames_rgba(result.video)
    rgb = image_rgba(result.still)[:, :, :3].astype(int)
    height, width = rgb.shape[:2]
    rows, columns = np.nonzero(np.all(np.abs(rgb - hex_rgb(colors.negative)) <= 12, axis=2))

    assert len(frames) == 5 * PREVIEW_FPS
    for frame in frames[-int(1.5 * PREVIEW_FPS) :]:
        assert np.array_equal(frame, frames[-1])
    # 1,200 to 340 is a fall: the change is drawn in the negative color, between the values.
    assert rows.size > 30
    assert height * 0.25 < np.median(rows) < height * 0.75
    assert width * 0.3 < np.median(columns) < width * 0.8
    assert not np.all(np.abs(rgb - hex_rgb(colors.positive)) <= 12, axis=2).any()


@pytest.mark.parametrize("aspect", ["16:9", "9:16"])
def test_waterfall_highlights_the_total_and_keeps_its_length(tmp_path: Path, aspect: str) -> None:
    from vizreel.themes.loader import load_theme

    colors = load_theme("default", Path(".")).colors
    [result] = render_spec(
        SHOWCASE,
        RenderOptions(
            out_dir=tmp_path, only=("profit",), quality="preview", still=True, aspect=aspect
        ),
        reraise=True,
    )
    assert result.error is None
    assert result.video is not None and result.still is not None
    frames = frames_rgba(result.video)
    rgb = image_rgba(result.still)[:, :, :3].astype(int)
    height, width = rgb.shape[:2]
    rows, columns = np.nonzero(np.all(np.abs(rgb - hex_rgb(colors.highlight)) <= 6, axis=2))

    assert len(frames) == 6 * PREVIEW_FPS
    for frame in frames[-int(1.5 * PREVIEW_FPS) :]:
        assert np.array_equal(frame, frames[-1])
    # The total is the last bar: the rightmost column, or the lowest row.
    assert rows.size > 50
    if aspect == "16:9":
        assert columns.min() > width * 0.7
    else:
        assert rows.min() > height * 0.5


@pytest.mark.parametrize("aspect", ["16:9", "9:16"])
def test_stacked_keeps_the_highlighted_series_color(tmp_path: Path, aspect: str) -> None:
    from vizreel.themes.loader import load_theme

    colors = load_theme("default", Path(".")).colors
    [result] = render_spec(
        SHOWCASE,
        RenderOptions(
            out_dir=tmp_path, only=("revenue-mix",), quality="preview", still=True, aspect=aspect
        ),
        reraise=True,
    )
    assert result.error is None
    assert result.video is not None and result.still is not None
    frames = frames_rgba(result.video)
    rgb = image_rgba(result.still)[:, :, :3].astype(int)

    def pixels(color: str) -> int:
        return int(np.all(np.abs(rgb - hex_rgb(color)) <= 6, axis=2).sum())

    assert len(frames) == 6 * PREVIEW_FPS
    for frame in frames[-int(1.5 * PREVIEW_FPS) :]:
        assert np.array_equal(frame, frames[-1])
    # Cloud, the first series, is highlighted and keeps its color; Devices is dimmed.
    assert pixels(colors.series[0]) > 500
    assert pixels(colors.series[1]) < 20


def test_timeline_label_too_long_is_an_error(tmp_path: Path) -> None:
    long = "Northwind signs a partnership with every airline in the region at once"
    events = ", ".join(f'{{ date: "{2010 + i}", label: "{long}" }}' for i in range(7))
    spec = tmp_path / "timeline.yaml"
    spec.write_text(f"version: 1\ncharts:\n  - {{ id: t, type: timeline, events: [{events}] }}\n")

    [result] = render_spec(spec, RenderOptions(out_dir=tmp_path, quality="preview"))

    assert result.error is not None
    assert "is too long for 7 events; shorten it" in result.error


def test_light_theme_is_used_for_rendering(tmp_path: Path) -> None:
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        "version: 1\nmeta: { theme: light, format: mp4 }\n"
        "charts: [{ id: a, type: stat, value: 42, label: Northwind }]\n"
    )

    result = render_one(spec, tmp_path, "a")

    assert result.video is not None
    corner = frames_rgba(result.video)[-1][2, 2]
    assert np.allclose(corner[:3], hex_rgb("#F6F8FA"), atol=4)


@pytest.mark.parametrize("name", ["stat", "line", "bar", "timeline"])
def test_every_template_renders(tmp_path: Path, name: str) -> None:
    from vizreel.spec.templates import spec_template

    spec = tmp_path / f"{name}.yaml"
    spec.write_text(spec_template(name), encoding="utf-8")

    [result] = render_spec(spec, RenderOptions(out_dir=tmp_path, quality="preview"))

    assert result.error is None
    assert result.video is not None


def test_a_failing_chart_does_not_stop_the_others(tmp_path: Path) -> None:
    too_wide = "Northwind " * 20
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        "version: 1\ncharts:\n"
        "  - { id: first, type: stat, value: 1 }\n"
        f'  - {{ id: broken, type: stat, value: 2, title: "{too_wide.strip()}" }}\n'
        "  - { id: last, type: stat, value: 3 }\n"
    )

    results = render_spec(spec, RenderOptions(out_dir=tmp_path, quality="preview"))

    assert [result.chart_id for result in results] == ["first", "broken", "last"]
    assert results[0].error is None
    assert results[2].error is None
    assert results[1].error
    assert (tmp_path / "first.preview.mov").is_file()
    assert (tmp_path / "last.preview.mov").is_file()


def test_render_command(tmp_path: Path) -> None:
    runner = CliRunner(env={"FORCE_COLOR": None, "TTY_COMPATIBLE": None})

    result = runner.invoke(
        app,
        [
            "render",
            str(SHOWCASE),
            "--only",
            STAT_ID,
            "--quality",
            "preview",
            "--still",
            "--out",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / f"{STAT_ID}.preview.mov").is_file()
    assert (tmp_path / f"{STAT_ID}.preview.png").is_file()
    assert result.stdout.strip().endswith("1 rendered, 0 failed")


def test_vertical_stat_has_the_vertical_size_and_duration(tmp_path: Path) -> None:
    [result] = render_spec(
        SHOWCASE,
        RenderOptions(out_dir=tmp_path, only=(STAT_ID,), quality="preview", aspect="9:16"),
        reraise=True,
    )

    assert result.video is not None
    assert result.video.name == f"{STAT_ID}.vertical.preview.mov"
    with av.open(str(result.video)) as container:
        stream = container.streams.video[0]
        assert (stream.width, stream.height) == (PREVIEW[1], PREVIEW[0])
    assert len(frames_rgba(result.video)) == STAT_DURATION * PREVIEW_FPS


def test_text_lays_out_the_same_at_every_output_size(tmp_path: Path) -> None:
    """Pango wraps text at the width of its surface; the surface must not be the video's."""
    from manim import tempconfig

    from vizreel.render import elements
    from vizreel.render.fonts import register_bundled_fonts
    from vizreel.themes.loader import load_theme

    register_bundled_fonts()
    theme = load_theme("default", Path("."))
    title = "Offers Northwind received from three buyers"
    heights = []
    for width, height in [(1920, 1080), (480, 854)]:
        config = {"media_dir": str(tmp_path), "pixel_width": width, "pixel_height": height}
        with tempconfig(config):
            heights.append(
                elements.text(title, theme.fonts.heading, theme.sizes.title, "#FFFFFF").height
            )

    assert heights[1] == pytest.approx(heights[0])


def test_watch_renders_again_only_the_changed_chart(tmp_path: Path) -> None:
    import threading
    import time

    from vizreel.watch import FileWatcher, watch_spec

    spec = tmp_path / "spec.yaml"
    charts = (
        "  - {{ id: first, type: stat, value: {first} }}\n"
        "  - {{ id: second, type: stat, value: 2 }}\n"
    )
    spec.write_text("version: 1\ncharts:\n" + charts.format(first=1), encoding="utf-8")
    renders: list[list[str]] = []
    waits = threading.Semaphore(0)
    done = threading.Event()
    watcher = FileWatcher([spec], settle=0.1)
    thread = threading.Thread(
        target=watch_spec,
        args=(spec, RenderOptions(out_dir=tmp_path / "out", quality="preview")),
        kwargs={
            "on_render": renders.append,
            "on_result": lambda result: None,
            "on_error": lambda error: pytest.fail(str(error)),
            "on_wait": waits.release,
            "stop": done.is_set,
            "poll_seconds": 0.05,
            "watcher": watcher,
        },
    )
    thread.start()
    try:
        assert waits.acquire(timeout=120)
        first_clip = tmp_path / "out" / "first.preview.mov"
        rendered_at = first_clip.stat().st_mtime_ns
        time.sleep(0.05)
        spec.write_text("version: 1\ncharts:\n" + charts.format(first=5), encoding="utf-8")
        assert waits.acquire(timeout=120)
    finally:
        done.set()
        thread.join(timeout=120)

    assert renders == [["first", "second"], ["first"]]
    assert first_clip.stat().st_mtime_ns > rendered_at


@pytest.mark.parametrize("size_px", [180, 36])
def test_composed_numbers_match_pango_layout(tmp_path: Path, size_px: float) -> None:
    from manim import tempconfig

    from vizreel.render import elements
    from vizreel.render.fonts import register_bundled_fonts
    from vizreel.render.layout import px
    from vizreel.render.numbers_text import NumberGlyphs
    from vizreel.themes.loader import load_theme

    register_bundled_fonts()
    fonts, colors = load_theme("default", Path(".")).fonts, load_theme("default", Path(".")).colors
    samples = ["$740M", "$123M", "1,234,567", "$2.25B", "−$9.81K", "47%", "1,111 users", "7"]
    with tempconfig({"media_dir": str(tmp_path), "verbosity": "ERROR"}):
        glyphs = NumberGlyphs(fonts.numbers, size_px, colors.text)
        for sample in samples:
            composed = glyphs(sample)
            direct = elements.number_text(sample, fonts.numbers, size_px, colors.text)
            assert len(composed.submobjects) == len(direct.submobjects)
            for ours, pango in zip(composed.submobjects, direct.submobjects, strict=True):
                assert ours.get_left()[0] == pytest.approx(pango.get_left()[0], abs=px(0.5))
                assert ours.get_bottom()[1] == pytest.approx(pango.get_bottom()[1], abs=px(0.5))
                assert ours.width == pytest.approx(pango.width, abs=px(0.5))


def test_digit_pattern() -> None:
    from vizreel.render.numbers_text import digit_pattern

    assert digit_pattern("$1,234.5M users") == "$0,000.0M users"
    assert digit_pattern("−9%") == "−0%"


def test_long_text_is_laid_out_completely(tmp_path: Path) -> None:
    from manim import tempconfig

    from vizreel.render import elements
    from vizreel.render.fonts import register_bundled_fonts
    from vizreel.themes.loader import load_theme

    register_bundled_fonts()
    theme = load_theme("default", Path("."))
    title = "Offers Northwind received from three buyers in 2015 and 2016"
    with tempconfig({"media_dir": str(tmp_path), "verbosity": "ERROR", "pixel_width": 854}):
        mobject = elements.text(title, theme.fonts.heading, theme.sizes.title, theme.colors.text)
        number = elements.number_text(
            "$1,234,567.89B users", theme.fonts.numbers, theme.sizes.big_number, theme.colors.text
        )

    assert len(mobject.submobjects) == len(title)
    assert len(number.submobjects) == len("$1,234,567.89Busers")


def test_text_that_pango_cannot_lay_out_completely_is_an_error(tmp_path: Path) -> None:
    from manim import tempconfig

    from vizreel.errors import RenderError
    from vizreel.render import elements
    from vizreel.render.fonts import register_bundled_fonts
    from vizreel.themes.loader import load_theme

    register_bundled_fonts()
    theme = load_theme("default", Path("."))
    with (
        tempconfig({"media_dir": str(tmp_path), "verbosity": "ERROR"}),
        pytest.raises(RenderError, match="could not be laid out completely"),
    ):
        elements.number_text("1" * 60, theme.fonts.numbers, 180, theme.colors.text)


def test_baseline_ignores_dots_accents_and_descenders(tmp_path: Path) -> None:
    from manim import tempconfig

    from vizreel.render import elements
    from vizreel.render.fonts import register_bundled_fonts
    from vizreel.render.layout import px
    from vizreel.themes.loader import load_theme

    register_bundled_fonts()
    theme = load_theme("default", Path("."))
    style, size, white = theme.fonts.body, theme.sizes.label, theme.colors.text
    with tempconfig({"media_dir": str(tmp_path), "verbosity": "ERROR"}):
        # One text puts every word on the same baseline; each word is then measured alone.
        words = ["Ilk", "İlk", "grafiği", "Âma", "ama"]
        row = elements.text(" ".join(words), style, size, white)
        metrics = elements.line_metrics(style, size)
        start = 0
        baselines = []
        for word in words:
            glyphs = row[start : start + len(word)]
            baselines.append(elements.baseline(glyphs, word, style, size))
            start += len(word) + 1
        paragraph = elements.paragraph(["İlk grafik", "Northwind"], style, size, white)
        first, second = (
            elements.baseline(paragraph[i], line, style, size)
            for i, line in enumerate(["İlk grafik", "Northwind"])
        )

    assert max(baselines) - min(baselines) < px(0.5)
    assert metrics.ascent > metrics.descent > 0
    assert first - second > metrics.ascent + metrics.descent


def test_text_blocks_are_placed_by_the_font_not_the_ink(tmp_path: Path) -> None:
    from manim import tempconfig

    from vizreel.render import elements
    from vizreel.render.fonts import register_bundled_fonts
    from vizreel.render.layout import px
    from vizreel.themes.loader import load_theme

    register_bundled_fonts()
    theme = load_theme("default", Path("."))
    style, size, white = theme.fonts.body, theme.sizes.label, theme.colors.text
    with tempconfig({"media_dir": str(tmp_path), "verbosity": "ERROR"}):
        blocks = [elements.text_block(word, style, size, white) for word in ["spec", "Ölç", "am"]]
        for block in blocks:
            block.move_top_to(1.0)
        baselines = [
            elements.baseline(block.mobject, block.lines[0], style, size) for block in blocks
        ]
        two_lines = elements.paragraph_block(["Buyer A", "(2015)"], style, size, white)
        two_lines.move_bottom_to(-1.0)

    assert max(baselines) - min(baselines) < px(0.5)
    assert max(b.height for b in blocks) - min(b.height for b in blocks) < px(0.5)
    assert all(block.top() == pytest.approx(1.0) for block in blocks)
    assert two_lines.bottom() == pytest.approx(-1.0)
    assert two_lines.height > 2 * blocks[0].height - px(size)


def test_text_uses_the_bundled_font(tmp_path: Path) -> None:
    """Inter must stay in use after the Windows font speed-up in vizreel.render.fonts."""
    from manim import Text, tempconfig

    from vizreel.render.fonts import register_bundled_fonts

    register_bundled_fonts()
    with tempconfig({"media_dir": str(tmp_path), "verbosity": "ERROR"}):
        inter = Text("Northwind 1,234", font="Inter", warn_missing_font=False).width
        fallback = Text("Northwind 1,234", font="No Such Font", warn_missing_font=False).width

    assert inter != pytest.approx(fallback, rel=1e-3)
