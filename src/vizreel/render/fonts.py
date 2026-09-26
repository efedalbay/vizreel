"""Bundled fonts, registered with Pango so output looks the same on every machine."""

import sys
import tempfile
from functools import cache
from pathlib import Path

from vizreel.errors import RenderError
from vizreel.themes.models import Theme

FONTS_DIR = Path(__file__).parents[1] / "assets" / "fonts"


def bundled_font_files() -> list[Path]:
    """Return the bundled font files, sorted by name."""
    return sorted(FONTS_DIR.glob("*.ttf"))


@cache
def register_bundled_fonts() -> frozenset[str]:
    """Make the bundled fonts available to Manim's `Text`. Safe to call more than once.

    Returns:
        Every font family Pango can use, bundled and installed.

    Raises:
        RenderError: Pango could not register a font file.
    """
    import manimpango

    for path in bundled_font_files():
        if not manimpango.register_font(str(path)):
            raise RenderError(f"could not register the bundled font {path.name}")
    families = frozenset(manimpango.list_fonts())
    if sys.platform == "win32":
        _stop_re_adding_fonts_on_windows()
    return families


def check_theme_fonts(theme: Theme) -> None:
    """Check that every font family of the theme is available.

    Raises:
        RenderError: A family is neither bundled nor installed.
    """
    available = register_bundled_fonts()
    fonts = theme.fonts
    for role, style in (
        ("heading", fonts.heading),
        ("body", fonts.body),
        ("numbers", fonts.numbers),
    ):
        if style.family not in available:
            raise RenderError(
                f'font "{style.family}" (theme fonts.{role}) is not installed. '
                "The bundled font is Inter"
            )


def _stop_re_adding_fonts_on_windows() -> None:
    """Make text rendering on Windows about 20 times faster.

    On Windows, ManimPango adds every registered font to Pango's font map again for each
    text it renders, and each addition costs about a second. Pango keeps one font map per
    thread, so once one text has added the fonts they stay available, and ManimPango's list
    can be emptied. If ManimPango changes its internals, this does nothing and text is slow.
    """
    import manimpango

    module = sys.modules.get("manimpango.register_font")
    registered = getattr(module, "registered_fonts", None)
    if not isinstance(registered, set):
        return
    with tempfile.TemporaryDirectory(prefix="vizreel-fonts-") as folder:
        svg = str(Path(folder) / "warm-up.svg")
        manimpango.MarkupUtils.text2svg(
            "0", None, "NORMAL", "NORMAL", 10, 0, False, svg, 0, 0, 100, 100
        )
    registered.clear()
