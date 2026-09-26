from pathlib import Path

import pytest
import yaml

from vizreel.errors import ThemeError
from vizreel.themes.loader import BUILTIN_DIR, builtin_theme_names, load_theme, resolve_theme_path
from vizreel.themes.models import Theme


def default_theme_data() -> dict[str, object]:
    data: dict[str, object] = yaml.safe_load(
        (BUILTIN_DIR / "default.yaml").read_text(encoding="utf-8")
    )
    return data


def write_theme(path: Path, changes: dict[str, dict[str, object]]) -> Path:
    data = default_theme_data()
    for section, values in changes.items():
        target = data[section]
        assert isinstance(target, dict)
        target.update(values)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def theme_errors(path: Path) -> list[str]:
    with pytest.raises(ThemeError) as caught:
        load_theme(str(path), path.parent)
    return [str(issue) for issue in caught.value.issues]


def test_builtin_themes() -> None:
    assert builtin_theme_names() == ["default"]


def test_default_theme_loads() -> None:
    theme = load_theme("default", Path("."))

    assert isinstance(theme, Theme)
    assert theme.fonts.numbers.family == "Inter"
    assert theme.motion.easing == "ease_out_cubic"
    assert theme.background_panel is True


def test_resolve_builtin_name() -> None:
    assert resolve_theme_path("default", Path("anywhere")) == BUILTIN_DIR / "default.yaml"


def test_resolve_path_relative_to_spec(tmp_path: Path) -> None:
    (tmp_path / "themes").mkdir()
    theme_path = write_theme(tmp_path / "themes" / "brand.yaml", {})

    assert resolve_theme_path("themes/brand.yaml", tmp_path) == theme_path
    assert load_theme("themes/brand.yaml", tmp_path).colors.surface == "#161B22"


def test_resolve_absolute_path(tmp_path: Path) -> None:
    theme_path = write_theme(tmp_path / "brand.yaml", {})

    assert resolve_theme_path(str(theme_path), Path("elsewhere")) == theme_path


def test_missing_theme_lists_builtin_themes(tmp_path: Path) -> None:
    with pytest.raises(ThemeError) as caught:
        load_theme("dark", tmp_path)

    assert caught.value.source == str(tmp_path / "dark")
    assert [str(issue) for issue in caught.value.issues] == [
        'theme "dark" not found. Built-in themes: default. '
        f"A custom theme is a path to a YAML file; a relative path is looked up in {tmp_path}"
    ]


def test_invalid_theme_reports_every_error(tmp_path: Path) -> None:
    path = write_theme(
        tmp_path / "bad.yaml",
        {
            "colors": {"highlight": "#FFF", "series": ["#58A6FF", "#F2B53A"]},
            "sizes": {"title": 40, "caption": 12},
            "motion": {"easing": "ease_out_bounce", "hold": 1},
        },
    )

    assert theme_errors(path) == [
        'colors.highlight: expected a color as #RRGGBB, e.g. "#F2B53A", got "#FFF"',
        "colors.series: expected at least 3 items, got 2",
        "sizes.title: must be at least 56, got 40",
        "sizes.caption: must be at least 24, got 12",
        'motion.easing: expected one of "ease_out_sine", "ease_out_cubic", "ease_out_quart" '
        'or "ease_out_expo", got "ease_out_bounce"',
        "motion.hold: must be at least 1.5, got 1",
    ]


def test_stroke_widths_and_dim_opacity_must_be_positive(tmp_path: Path) -> None:
    path = write_theme(
        tmp_path / "strokes.yaml",
        {"colors": {"dim_opacity": 1.5}, "sizes": {"line": 0, "dot": -2}},
    )

    assert theme_errors(path) == [
        "colors.dim_opacity: must be at most 1, got 1.5",
        "sizes.line: must be greater than 0, got 0",
        "sizes.dot: must be greater than 0, got -2",
    ]


def test_theme_with_three_font_families_is_rejected(tmp_path: Path) -> None:
    path = write_theme(
        tmp_path / "fonts.yaml",
        {
            "fonts": {
                "heading": {"family": "A"},
                "body": {"family": "B"},
                "numbers": {"family": "C"},
            }
        },
    )

    assert theme_errors(path) == [
        "fonts.numbers.family: a theme uses at most 2 font families, got 3: A, B, C"
    ]


def test_unknown_theme_field(tmp_path: Path) -> None:
    path = write_theme(tmp_path / "typo.yaml", {"motion": {"hodl": 2}})

    assert theme_errors(path) == [
        "motion.hodl: unknown field. Check the spelling against the built-in default theme"
    ]


def test_empty_theme_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")

    assert theme_errors(path) == [
        "the file is empty; a theme needs `colors`, `fonts`, `sizes`, `motion` and "
        "`background_panel`"
    ]
