from pathlib import Path

import pytest

from vizreel.render.layout import (
    FRAME_HEIGHT,
    FRAME_WIDTH,
    Box,
    Layout,
    build_layout,
    font_size,
    px,
    stroke_width,
)
from vizreel.themes.loader import load_theme

SIZES = load_theme("default", Path(".")).sizes


def layout(*, panel: bool = True, title: int = 1, subtitle: int = 0, source: int = 1) -> Layout:
    return build_layout(
        SIZES, panel=panel, title_lines=title, subtitle_lines=subtitle, source_lines=source
    )


def test_pixels_at_1080p_convert_to_scene_units() -> None:
    assert px(1080) == pytest.approx(FRAME_HEIGHT)
    assert px(135) == pytest.approx(1)


def test_font_size_uses_72_points_per_scene_unit() -> None:
    assert font_size(56) == pytest.approx(56 * 8 / 1080 * 72)
    assert font_size(135) == pytest.approx(72)


def test_stroke_width_is_hundredths_of_a_scene_unit() -> None:
    assert stroke_width(13.5) == pytest.approx(10)
    assert stroke_width(135) == pytest.approx(100)


def test_frame_is_16_by_9_around_origin() -> None:
    frame = layout().frame

    assert (frame.width, frame.height) == pytest.approx((FRAME_WIDTH, FRAME_HEIGHT))
    assert frame.center == pytest.approx((0, 0))
    assert frame.width / frame.height == pytest.approx(16 / 9)


def test_safe_area_keeps_five_percent_margin() -> None:
    result = layout()

    assert result.safe.width == pytest.approx(FRAME_WIDTH * 0.9)
    assert result.safe.height == pytest.approx(FRAME_HEIGHT * 0.9)
    assert result.safe.center == pytest.approx((0, 0))


def test_panel_padding_shrinks_inner_area() -> None:
    with_panel = layout(panel=True)
    without_panel = layout(panel=False)

    assert without_panel.inner == without_panel.safe
    assert with_panel.inner == with_panel.safe.inset(px(SIZES.panel_padding))
    assert with_panel.panel_padding == pytest.approx(px(SIZES.panel_padding))
    assert without_panel.panel_padding == 0


@pytest.mark.parametrize("panel", [True, False])
@pytest.mark.parametrize(
    ("title", "subtitle", "source"), [(0, 0, 0), (1, 0, 1), (1, 1, 1), (2, 2, 2)]
)
def test_bands_stack_inside_inner_area(panel: bool, title: int, subtitle: int, source: int) -> None:
    result = layout(panel=panel, title=title, subtitle=subtitle, source=source)

    for band in (result.title, result.content, result.source):
        assert result.inner.contains(band)
    assert result.title.bottom >= result.content.top
    assert result.content.bottom >= result.source.top
    assert result.content.height > 0


def test_bands_without_text_have_no_height() -> None:
    result = layout(title=0, subtitle=0, source=0)

    assert result.title.height == 0
    assert result.source.height == 0
    assert result.content == result.inner


def test_title_band_fits_title_and_subtitle() -> None:
    result = layout(title=1, subtitle=1)

    assert result.title.height == pytest.approx(px(1.3 * (SIZES.title + SIZES.subtitle)))


def test_panel_around_content_stays_in_safe_area() -> None:
    result = layout()
    small = Box(-1, -1, 1, 1)
    huge = Box(-100, -100, 100, 100)

    assert result.panel_around(small) == small.expand(result.panel_padding, result.safe)
    assert result.panel_around(small).width == pytest.approx(2 + 2 * result.panel_padding)
    assert result.panel_around(huge) == result.safe


def test_box_geometry() -> None:
    box = Box(-2, -1, 4, 3)

    assert (box.width, box.height, box.center) == (6, 4, (1, 1))
    assert box.inset(1) == Box(-1, 0, 3, 2)
    assert box.contains(Box(0, 0, 1, 1))
    assert not box.contains(Box(0, 0, 5, 1))
