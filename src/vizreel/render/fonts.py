"""Bundled fonts, registered with Pango so output looks the same on every machine."""

from functools import cache
from pathlib import Path

from vizreel.errors import RenderError

FONTS_DIR = Path(__file__).parents[1] / "assets" / "fonts"


def bundled_font_files() -> list[Path]:
    """Return the bundled font files, sorted by name."""
    return sorted(FONTS_DIR.glob("*.ttf"))


@cache
def register_bundled_fonts() -> None:
    """Make the bundled fonts available to Manim's `Text`. Safe to call more than once.

    Raises:
        RenderError: Pango could not register a font file.
    """
    import manimpango

    for path in bundled_font_files():
        if not manimpango.register_font(str(path)):
            raise RenderError(f"could not register the bundled font {path.name}")
