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
    assert stat_mov.video.name == f"{STAT_ID}.mov"
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
    assert stat_mov.still.name == f"{STAT_ID}.png"
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


def test_a_failing_chart_does_not_stop_the_others(tmp_path: Path) -> None:
    results = render_spec(SHOWCASE, RenderOptions(out_dir=tmp_path, quality="preview"))

    assert [result.chart_id for result in results] == [
        "peak-valuation",
        "valuation",
        "offers",
        "final-years",
    ]
    assert results[0].error is None
    assert (tmp_path / "peak-valuation.mov").is_file()
    assert all("not implemented yet" in (result.error or "") for result in results[1:])


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
    assert (tmp_path / f"{STAT_ID}.mov").is_file()
    assert (tmp_path / f"{STAT_ID}.png").is_file()
    assert result.stdout.strip().endswith("1 rendered, 0 failed")


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


def test_text_uses_the_bundled_font(tmp_path: Path) -> None:
    """Inter must stay in use after the Windows font speed-up in vizreel.render.fonts."""
    from manim import Text, tempconfig

    from vizreel.render.fonts import register_bundled_fonts

    register_bundled_fonts()
    with tempconfig({"media_dir": str(tmp_path), "verbosity": "ERROR"}):
        inter = Text("Northwind 1,234", font="Inter", warn_missing_font=False).width
        fallback = Text("Northwind 1,234", font="No Such Font", warn_missing_font=False).width

    assert inter != pytest.approx(fallback, rel=1e-3)
