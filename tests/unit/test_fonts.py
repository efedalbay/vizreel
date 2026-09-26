import manimpango

from vizreel.render.fonts import FONTS_DIR, bundled_font_files, register_bundled_fonts
from vizreel.themes.loader import load_theme


def test_bundled_fonts_ship_with_their_license() -> None:
    names = [path.name for path in bundled_font_files()]

    assert names == ["Inter-Bold.ttf", "Inter-Regular.ttf", "Inter-SemiBold.ttf"]
    assert "SIL OPEN FONT LICENSE" in (FONTS_DIR / "Inter-OFL.txt").read_text(encoding="utf-8")


def test_registered_fonts_are_available_to_pango() -> None:
    register_bundled_fonts()
    register_bundled_fonts()

    assert "Inter" in manimpango.list_fonts()


def test_default_theme_uses_only_bundled_families() -> None:
    fonts = load_theme("default", FONTS_DIR).fonts

    families = {style.family for style in (fonts.heading, fonts.body, fonts.numbers)}
    assert families == {"Inter"}
