"""Bundled fonts, registered with Pango so output looks the same on every machine."""

import sys
import tempfile
from functools import cache
from pathlib import Path

from vizreel.errors import RenderError
from vizreel.themes.models import FontStyle, FontWeight, Theme

FONTS_DIR = Path(__file__).parents[1] / "assets" / "fonts"


def bundled_font_files() -> list[Path]:
    """Return the bundled font files, sorted by name."""
    return sorted(FONTS_DIR.glob("*.ttf"))


_registered: set[Path] = set()
"""Font files already registered with Pango in this process."""


@cache
def register_bundled_fonts() -> frozenset[str]:
    """Make the bundled fonts available to Manim's `Text`. Safe to call more than once.

    Returns:
        Every font family Pango can use, bundled and installed.

    Raises:
        RenderError: Pango could not register a font file.
    """
    return _register(bundled_font_files())


def check_theme_fonts(theme: Theme) -> None:
    """Register the font files the theme brings, and check that every family is available.

    Raises:
        RenderError: A family is neither bundled, nor installed, nor in a file the theme
            brings.
    """
    available = register_bundled_fonts()
    styles = [(role, getattr(theme.fonts, role)) for role in ("heading", "body", "numbers")]
    files = [Path(style.file) for _, style in styles if style.file]
    if files:
        available |= _register(files)
    for role, style in styles:
        if style.family in available:
            continue
        if style.file:
            raise RenderError(
                f"the font file {Path(style.file).name} (theme fonts.{role}) holds the family "
                f'"{style.family}", which the text renderer could not load'
            )
        raise RenderError(
            f'font "{style.family}" (theme fonts.{role}) is not installed. The bundled font is '
            "Inter; a theme can also bring a font file with file:"
        )


def tabular_figures_warning(theme: Theme) -> str | None:
    """Say so if the theme's number font has no tabular figures, or None if it has them.

    With tabular figures every digit is as wide as the others, so a counting number does not
    shift sideways. Call it after `check_theme_fonts`; it builds text, so it imports Manim.
    """
    style = theme.fonts.numbers
    if _has_tabular_figures(style.family, style.weight):
        return None
    return (
        f'the number font "{style.family}" (theme fonts.numbers) has no tabular figures, so '
        "counting numbers will shift sideways; choose a font whose digits share one width"
    )


@cache
def _has_tabular_figures(family: str, weight: FontWeight) -> bool:
    from vizreel.render.elements import number_text

    style = FontStyle(family=family, weight=weight)
    # Between two zeros the ink spans the digits' advances, not their own ink, which is
    # narrower than the advance for a digit such as 1 even with tabular figures.
    widths = [number_text(f"0{digit * 8}0", style, 100, "#000000").width for digit in "0123456789"]
    return max(widths) - min(widths) <= max(widths) * TABULAR_TOLERANCE


TABULAR_TOLERANCE = 0.01
"""Digits whose widths differ by at most this share count as tabular."""


def _register(paths: list[Path]) -> frozenset[str]:
    """Register font files with Pango, each once.

    Returns:
        The font families Pango lists, which include those of the new files. On Windows they
        are listed before ManimPango's list of registered files is emptied, after which a
        listing leaves them out although text can still use them.

    Raises:
        RenderError: Pango could not register a file.
    """
    import manimpango

    new = [path for path in paths if path not in _registered]
    for path in new:
        if not manimpango.register_font(str(path)):
            raise RenderError(f"could not register the font file {path.name}")
    _registered.update(new)
    families = frozenset(manimpango.list_fonts())
    if new and sys.platform == "win32":
        _stop_re_adding_fonts_on_windows()
    return families


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
