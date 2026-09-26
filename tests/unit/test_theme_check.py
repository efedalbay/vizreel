from pathlib import Path

import pytest

from vizreel.themes.check import (
    MARK_CONTRAST,
    MIN_DIFFERENCE,
    TEXT_CONTRAST,
    VISIONS,
    check_theme,
    ciede2000,
    color_difference,
    contrast_ratio,
    lab,
    linear_rgb,
    simulate,
)
from vizreel.themes.loader import load_theme


def test_contrast_matches_wcag_examples() -> None:
    assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21)
    assert contrast_ratio("#FFFFFF", "#FFFFFF") == pytest.approx(1)
    assert contrast_ratio("#777777", "#FFFFFF") == pytest.approx(4.48, abs=0.01)
    assert contrast_ratio("#767676", "#FFFFFF") == pytest.approx(4.54, abs=0.01)


def test_contrast_is_symmetric() -> None:
    assert contrast_ratio("#58A6FF", "#161B22") == contrast_ratio("#161B22", "#58A6FF")


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
        ((50.0, 0.0, 0.0), (50.0, -1.0, 2.0), 2.3669),
        ((50.0, 2.5, 0.0), (73.0, 25.0, -18.0), 27.1492),
        ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
        ((22.7233, 20.0904, -46.694), (23.0331, 14.973, -42.5619), 2.0373),
        ((90.9257, -0.5406, -0.9208), (88.6381, -0.8985, -0.7239), 1.5381),
    ],
)
def test_ciede2000_matches_sharma_reference_data(
    first: tuple[float, float, float], second: tuple[float, float, float], expected: float
) -> None:
    assert ciede2000(first, second) == pytest.approx(expected, abs=1e-4)
    assert ciede2000(second, first) == pytest.approx(expected, abs=1e-4)


def test_lab_of_white_and_black() -> None:
    assert lab(linear_rgb("#FFFFFF")) == pytest.approx((100, 0, 0), abs=0.01)
    assert lab(linear_rgb("#000000")) == pytest.approx((0, 0, 0), abs=0.01)


def test_simulation_keeps_grays_gray() -> None:
    gray = linear_rgb("#808080")
    for matrix in VISIONS.values():
        assert simulate(gray, matrix) == pytest.approx(gray, abs=0.01)


def test_red_and_green_collapse_for_deuteranopia() -> None:
    normal = color_difference("#D62728", "#2CA02C")
    deuteranopia = color_difference("#D62728", "#2CA02C", VISIONS["deuteranopia"])

    assert normal > 50
    assert deuteranopia < normal / 2


def test_default_theme_passes_every_check() -> None:
    failures = [
        result for result in check_theme(load_theme("default", Path("."))) if not result.passed
    ]

    assert failures == []


def test_check_reports_low_contrast_and_similar_series(tmp_path: Path) -> None:
    theme = load_theme("default", Path("."))
    colors = theme.colors.model_copy(
        update={"muted": "#30363D", "series": ["#58A6FF", "#5AA8FF", "#D2A8FF"]}
    )
    results = check_theme(theme.model_copy(update={"colors": colors}))
    failed = {result.description for result in results if not result.passed}

    assert "colors.muted on colors.surface" in failed
    assert "colors.series[0] and colors.series[1] with normal vision" in failed
    for result in results:
        assert result.passed == (result.value >= result.minimum)
        assert result.minimum in (TEXT_CONTRAST, MARK_CONTRAST, MIN_DIFFERENCE)
