"""Manim building blocks shared by chart types: text, panels, easing.

Imports Manim at the top. Chart modules import this module inside `build`.
"""

from collections.abc import Callable
from xml.sax.saxutils import escape

from manim import (
    DOWN,
    ManimColor,
    MarkupText,
    Mobject,
    RoundedRectangle,
    Text,
    VGroup,
    VMobject,
    rate_functions,
)

from vizreel.errors import RenderError
from vizreel.render.layout import Box, font_size, px
from vizreel.themes.models import FontStyle, Theme

_PANGO_WEIGHTS = {"regular": "NORMAL", "semibold": "SEMIBOLD", "bold": "BOLD"}
PANEL_Z_INDEX = -1
_OVERSAMPLE = 10
"""Text is laid out this many times larger and scaled down. Pango rounds glyph positions,
which at small sizes produces uneven letter spacing ("Northw ind")."""


def color(hex_color: str) -> ManimColor:
    """Turn a theme color into a Manim color."""
    return ManimColor(hex_color)


def text(content: str, style: FontStyle, size_px: float, hex_color: str) -> VMobject:
    """Build a line of text in a theme font."""
    mobject = Text(
        content,
        font=style.family,
        weight=_PANGO_WEIGHTS[style.weight],
        font_size=font_size(size_px) * _OVERSAMPLE,
        color=color(hex_color),
        warn_missing_font=False,
    )
    return mobject.scale(1 / _OVERSAMPLE)


def number_text(content: str, style: FontStyle, size_px: float, hex_color: str) -> VMobject:
    """Build a number with tabular figures, so every digit has the same width."""
    mobject = MarkupText(
        f'<span font_features="tnum">{escape(content)}</span>',
        font=style.family,
        weight=_PANGO_WEIGHTS[style.weight],
        font_size=font_size(size_px) * _OVERSAMPLE,
        color=color(hex_color),
        warn_missing_font=False,
    )
    return mobject.scale(1 / _OVERSAMPLE)


def easing(theme: Theme) -> Callable[[float], float]:
    """Return the theme's easing curve as a Manim rate function."""
    curve: Callable[[float], float] = getattr(rate_functions, theme.motion.easing)
    return curve


def panel(box: Box, theme: Theme) -> RoundedRectangle:
    """Build the background panel covering `box`. It is drawn behind everything else."""
    radius = min(px(theme.sizes.panel_radius), box.width / 2, box.height / 2)
    rectangle = RoundedRectangle(
        width=box.width,
        height=box.height,
        corner_radius=radius,
        stroke_width=0,
        fill_color=color(theme.colors.surface),
        fill_opacity=1,
    )
    rectangle.move_to((*box.center, 0.0))
    rectangle.set_z_index(PANEL_Z_INDEX)
    return rectangle


def bounds(mobject: Mobject) -> Box:
    """Return the bounding box of a mobject."""
    return Box(
        float(mobject.get_left()[0]),
        float(mobject.get_bottom()[1]),
        float(mobject.get_right()[0]),
        float(mobject.get_top()[1]),
    )


def stack(items: list[tuple[VMobject, float]], center: tuple[float, float]) -> VGroup:
    """Stack mobjects top to bottom, horizontally centered, and center the stack at `center`.

    Args:
        items: Each mobject with the gap to leave below it.
        center: Center of the whole stack.
    """
    group = VGroup(*(mobject for mobject, _ in items))
    for (previous, gap), (current, _) in zip(items, items[1:], strict=False):
        current.next_to(previous, DOWN, buff=gap)
    group.move_to((*center, 0.0))
    return group


def check_fits(mobject: Mobject, box: Box, what: str) -> None:
    """Check that a mobject is not wider than `box`.

    Raises:
        RenderError: The mobject is too wide. Text is never shrunk below the theme size.
    """
    if mobject.width > box.width + 1e-9:
        raise RenderError(f"{what} is too wide to fit at the theme's size; shorten it")
