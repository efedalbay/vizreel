"""Manim building blocks shared by chart types: text, headers, panels, easing.

Imports Manim at the top. Chart modules import this module inside `build`.
"""

from collections.abc import Callable
from xml.sax.saxutils import escape

from manim import (
    DOWN,
    LEFT,
    UP,
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
from vizreel.render.layout import Box, Layout, font_size, px, stack_gap
from vizreel.themes.models import FontStyle, Theme

_PANGO_WEIGHTS = {"regular": "NORMAL", "semibold": "SEMIBOLD", "bold": "BOLD"}
PANEL_Z_INDEX = -1
LAYOUT_FONT_SIZE = 150
"""Text is laid out at least this large (Manim font size) and scaled to its real size.

Pango rounds glyph positions, which at small sizes makes letter spacing uneven
("Northw ind"). Much larger sizes overflow the surface Manim gives Pango and lose glyphs.
"""


def color(hex_color: str) -> ManimColor:
    """Turn a theme color into a Manim color."""
    return ManimColor(hex_color)


def text(content: str, style: FontStyle, size_px: float, hex_color: str) -> VMobject:
    """Build a line of text in a theme font.

    Raises:
        RenderError: Pango could not lay out every character.
    """
    content = content.strip()
    size = font_size(size_px)
    oversample = max(1.0, LAYOUT_FONT_SIZE / size)
    mobject = Text(
        content,
        font=style.family,
        weight=_PANGO_WEIGHTS[style.weight],
        font_size=size * oversample,
        color=color(hex_color),
        disable_ligatures=True,
        warn_missing_font=False,
    )
    # With ligatures disabled, Text has one submobject per character, spaces included.
    _check_complete(mobject, content, len(content))
    return mobject.scale(1 / oversample)


def number_text(content: str, style: FontStyle, size_px: float, hex_color: str) -> VMobject:
    """Build a number with tabular figures, so every digit has the same width.

    Raises:
        RenderError: Pango could not lay out every character.
    """
    size = font_size(size_px)
    oversample = max(1.0, LAYOUT_FONT_SIZE / size)
    mobject = MarkupText(
        f'<span font_features="tnum">{escape(content)}</span>',
        font=style.family,
        weight=_PANGO_WEIGHTS[style.weight],
        font_size=size * oversample,
        color=color(hex_color),
        disable_ligatures=True,
        warn_missing_font=False,
    )
    # MarkupText has one submobject per visible character.
    _check_complete(mobject, content, sum(1 for char in content if not char.isspace()))
    return mobject.scale(1 / oversample)


def _check_complete(mobject: VMobject, content: str, expected: int) -> None:
    """Check that Pango laid out every character, not only the ones that fit its surface."""
    if len(mobject.submobjects) != expected:
        raise RenderError(f'"{content}" could not be laid out completely; shorten it')


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


def header(title: str | None, subtitle: str | None, theme: Theme, layout: Layout) -> VGroup:
    """Build the title and subtitle, left-aligned at the top of the title band.

    Raises:
        RenderError: The title or subtitle is too wide for the frame.
    """
    lines: list[tuple[VMobject, float]] = []
    if title:
        lines.append(
            (
                text(title, theme.fonts.heading, theme.sizes.title, theme.colors.text),
                theme.sizes.title,
            )
        )
    if subtitle:
        lines.append(
            (
                text(subtitle, theme.fonts.body, theme.sizes.subtitle, theme.colors.muted),
                theme.sizes.subtitle,
            )
        )
    group = VGroup()
    for index, (mobject, size) in enumerate(lines):
        check_fits(mobject, layout.title, "the title" if index == 0 and title else "the subtitle")
        if index == 0:
            mobject.align_to((layout.title.left, layout.title.top, 0.0), UP + LEFT)
        else:
            previous, previous_size = lines[index - 1]
            mobject.next_to(previous, DOWN, buff=stack_gap(previous_size, size), aligned_edge=LEFT)
        group.add(mobject)
    return group


def source_line(source: str | None, theme: Theme, layout: Layout) -> VMobject | None:
    """Build the source line, left-aligned at the bottom of the source band.

    Raises:
        RenderError: The source is too wide for the frame.
    """
    if not source:
        return None
    mobject = text(source, theme.fonts.body, theme.sizes.caption, theme.colors.muted)
    check_fits(mobject, layout.source, "the source")
    return mobject.align_to((layout.source.left, layout.source.bottom, 0.0), DOWN + LEFT)
