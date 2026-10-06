from pathlib import Path

import pytest

from vizreel.errors import RenderError
from vizreel.render.fonts import (
    FONTS_DIR,
    bundled_font_files,
    check_theme_fonts,
    register_bundled_fonts,
)
from vizreel.themes.loader import builtin_theme_names, load_theme


def test_bundled_fonts_ship_with_their_license() -> None:
    names = [path.name for path in bundled_font_files()]

    assert names == ["Inter-Bold.ttf", "Inter-Regular.ttf", "Inter-SemiBold.ttf"]
    assert "SIL OPEN FONT LICENSE" in (FONTS_DIR / "Inter-OFL.txt").read_text(encoding="utf-8")


def test_registering_makes_inter_available() -> None:
    first = register_bundled_fonts()
    second = register_bundled_fonts()

    assert "Inter" in first
    assert first == second


@pytest.mark.parametrize("name", builtin_theme_names())
def test_builtin_theme_fonts_are_available(name: str) -> None:
    check_theme_fonts(load_theme(name, Path(".")))


def test_missing_theme_font_is_an_error() -> None:
    theme = load_theme("default", Path("."))
    heading = theme.fonts.heading.model_copy(update={"family": "No Such Font"})
    fonts = theme.fonts.model_copy(update={"heading": heading})

    with pytest.raises(
        RenderError,
        match=r'font "No Such Font" \(theme fonts.heading\) is not installed. '
        "The bundled font is Inter; a theme can also bring a font file with file:",
    ):
        check_theme_fonts(theme.model_copy(update={"fonts": fonts}))


def test_a_theme_font_file_is_registered_for_rendering() -> None:
    plex = Path(__file__).parents[2] / "examples" / "themes" / "fonts" / "IBMPlexMono-Regular.ttf"
    theme = load_theme("default", Path("."))
    numbers = theme.fonts.numbers.model_copy(
        update={"family": "IBM Plex Mono", "file": str(plex.resolve())}
    )
    fonts = theme.fonts.model_copy(update={"numbers": numbers})

    check_theme_fonts(theme.model_copy(update={"fonts": fonts}))
    # The bundled fonts stay available after another file is registered.
    check_theme_fonts(theme)
