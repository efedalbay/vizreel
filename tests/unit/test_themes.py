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
    assert builtin_theme_names() == ["default", "light"]


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
        'theme "dark" not found. Built-in themes: default, light. '
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


PLEX_MONO = Path(__file__).parents[2] / "examples" / "themes" / "fonts" / "IBMPlexMono-Regular.ttf"


def test_each_font_role_may_use_its_own_family(tmp_path: Path) -> None:
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

    fonts = load_theme(str(path), tmp_path).fonts
    assert [fonts.heading.family, fonts.body.family, fonts.numbers.family] == ["A", "B", "C"]


def test_a_font_file_next_to_the_theme_gives_its_family(tmp_path: Path) -> None:
    (tmp_path / "fonts").mkdir()
    (tmp_path / "fonts" / "mono.ttf").write_bytes(PLEX_MONO.read_bytes())
    path = write_theme(
        tmp_path / "mono.yaml",
        {"fonts": {"numbers": {"file": "fonts/mono.ttf"}, "body": {"file": "fonts/mono.ttf"}}},
    )

    numbers = load_theme(str(path), Path("elsewhere")).fonts.numbers
    assert numbers.family == "IBM Plex Mono"
    assert numbers.file == str((tmp_path / "fonts" / "mono.ttf").resolve())


def test_font_files_that_cannot_be_used_name_the_file(tmp_path: Path) -> None:
    (tmp_path / "broken.ttf").write_text("not a font")
    (tmp_path / "mono.otf").write_bytes(PLEX_MONO.read_bytes())
    path = write_theme(
        tmp_path / "fonts.yaml",
        {
            "fonts": {
                "heading": {"file": "missing.ttf"},
                "body": {"file": "broken.ttf"},
                "numbers": {"file": "mono.otf", "family": "Plex"},
            }
        },
    )

    assert theme_errors(path) == [
        f"fonts.heading.file: missing.ttf was not found in {tmp_path}",
        "fonts.body.file: broken.ttf cannot be read as a font",
        'fonts.numbers.family: is "Plex" but mono.otf holds the family "IBM Plex Mono"; '
        "leave out family or write it as the file names it",
    ]


def test_a_font_file_must_be_ttf_or_otf(tmp_path: Path) -> None:
    path = write_theme(tmp_path / "fonts.yaml", {"fonts": {"heading": {"file": "font.woff2"}}})

    assert theme_errors(path) == ["fonts.heading.file: font.woff2 is not a TTF or OTF font file"]


def test_unknown_theme_field(tmp_path: Path) -> None:
    path = write_theme(tmp_path / "typo.yaml", {"motion": {"hodl": 2}})

    assert theme_errors(path) == [
        "motion.hodl: unknown field. Check the spelling against docs/THEMES.md"
    ]


def test_empty_theme_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")

    assert theme_errors(path) == [
        "the file is empty; a theme needs `colors`, `fonts`, `sizes`, `motion` and "
        "`background_panel`"
    ]


def test_themes_doc_lists_every_builtin_theme() -> None:
    doc = (Path(__file__).parents[2] / "docs" / "THEMES.md").read_text(encoding="utf-8")

    for name in builtin_theme_names():
        description = load_theme(name, Path(".")).description
        assert f"| `{name}` | {description} |" in doc


def logo_theme(folder: Path, logo: dict[str, object]) -> Path:
    data = default_theme_data()
    data["logo"] = logo
    path = folder / "brand.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_a_theme_logo_is_found_next_to_the_theme(tmp_path: Path) -> None:
    (tmp_path / "logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')

    theme = load_theme(str(logo_theme(tmp_path, {"file": "logo.svg"})), Path("."))

    assert theme.logo is not None
    assert theme.logo.file == str((tmp_path / "logo.svg").resolve())
    assert theme.logo.height == 48


@pytest.mark.parametrize(
    ("logo", "message"),
    [
        ({"file": "gone.png"}, "logo.file: gone.png was not found in"),
        ({"file": "logo.gif"}, "logo.file: logo.gif is not a PNG, JPEG or SVG file"),
        ({"file": "logo.png", "height": 8}, "logo.height: must be at least 16, got 8"),
    ],
)
def test_a_wrong_theme_logo_is_an_error(
    tmp_path: Path, logo: dict[str, object], message: str
) -> None:
    (tmp_path / "logo.png").write_bytes(b"")

    [error] = theme_errors(logo_theme(tmp_path, logo))

    assert error.startswith(message)


def test_the_example_brand_theme_has_a_logo() -> None:
    theme = load_theme(str(Path("examples") / "themes" / "example-brand.yaml"), Path("."))

    assert theme.logo is not None
    assert Path(theme.logo.file).name == "northwind-logo.svg"
