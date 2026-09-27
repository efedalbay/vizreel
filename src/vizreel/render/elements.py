"""Manim building blocks shared by chart types: text, headers, panels, easing.

Imports Manim at the top. Chart modules import this module inside `build`.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cache
from xml.sax.saxutils import escape

from manim import (
    DOWN,
    LEFT,
    ManimColor,
    MarkupText,
    Mobject,
    Paragraph,
    RoundedRectangle,
    Text,
    VGroup,
    VMobject,
    config,
    rate_functions,
)

from vizreel.errors import RenderError
from vizreel.render.layout import Box, Layout, font_size, px, stack_gap
from vizreel.themes.models import FontStyle, FontWeight, Theme

_PANGO_WEIGHTS = {"regular": "NORMAL", "semibold": "SEMIBOLD", "bold": "BOLD"}
PANEL_Z_INDEX = -1
LAYOUT_FONT_SIZE = 150
"""Text is laid out at least this large (Manim font size) and scaled to its real size.

Pango rounds glyph positions, which at small sizes makes letter spacing uneven
("Northw ind"). Much larger sizes overflow the surface Manim gives Pango and lose glyphs.
"""
TEXT_SURFACE_PX = 4096
"""Width and height of the surface Pango lays text out on.

Manim uses the video's pixel size, so text would wrap at a different point in a preview, a
vertical frame or 4k. A fixed surface lays text out the same way in every output, and at this
size even a line as wide as the frame at the smallest theme size fits on one line.
"""


@contextmanager
def _text_surface() -> Iterator[None]:
    saved = config.pixel_width, config.pixel_height
    config.pixel_width = config.pixel_height = TEXT_SURFACE_PX
    try:
        yield
    finally:
        config.pixel_width, config.pixel_height = saved


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
    with _text_surface():
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


def paragraph(lines: list[str], style: FontStyle, size_px: float, hex_color: str) -> VMobject:
    """Build centered lines of text, spaced by Pango so that baselines are even.

    Raises:
        RenderError: Pango could not lay out every character.
    """
    lines = [line.strip() for line in lines]
    size = font_size(size_px)
    oversample = max(1.0, LAYOUT_FONT_SIZE / size)
    with _text_surface():
        mobject = Paragraph(
            *lines,
            font=style.family,
            weight=_PANGO_WEIGHTS[style.weight],
            font_size=size * oversample,
            color=color(hex_color),
            alignment="center",
            disable_ligatures=True,
            warn_missing_font=False,
        )
    for line, line_mobject in zip(lines, mobject.submobjects, strict=True):
        _check_complete(line_mobject, line, len(line))
    return mobject.scale(1 / oversample)


def number_text(content: str, style: FontStyle, size_px: float, hex_color: str) -> VMobject:
    """Build a number with tabular figures, so every digit has the same width.

    Raises:
        RenderError: Pango could not lay out every character.
    """
    size = font_size(size_px)
    oversample = max(1.0, LAYOUT_FONT_SIZE / size)
    with _text_surface():
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


@dataclass(frozen=True)
class LineMetrics:
    """Vertical extent of a line of text in a font, measured from its baseline.

    Attributes:
        ascent: From the baseline to the top of capitals and ascenders.
        descent: From the baseline down to the bottom of descenders.
    """

    ascent: float
    descent: float


def line_metrics(style: FontStyle, size_px: float) -> LineMetrics:
    """Measure the ascent and descent of a font at a size."""
    return _line_metrics(style.family, style.weight, size_px)


@cache
def _line_metrics(family: str, weight: FontWeight, size_px: float) -> LineMetrics:
    style = FontStyle(family=family, weight=weight)
    capital, ascender, descender = text("Hdg", style, size_px, "#000000")
    baseline = float(capital.get_bottom()[1])
    top = max(float(capital.get_top()[1]), float(ascender.get_top()[1]))
    return LineMetrics(ascent=top - baseline, descent=baseline - float(descender.get_bottom()[1]))


def baseline(line: Mobject, content: str, style: FontStyle, size_px: float) -> float:
    """Return the y of the baseline of `line`, a line of text built from `content`.

    Text is positioned by its ink, which moves with the letters: a dotted capital I or an
    accent reaches higher, a descender lower. The baseline stays put.
    """
    below = _ink_below_baseline(content.strip(), style.family, style.weight, size_px)
    return float(line.get_bottom()[1]) + below


@cache
def _ink_below_baseline(content: str, family: str, weight: FontWeight, size_px: float) -> float:
    # "x" sits exactly on the baseline, so the ink of the rest is measured against it.
    style = FontStyle(family=family, weight=weight)
    reference, *rest = text("x" + content, style, size_px, "#000000")
    return float(reference.get_bottom()[1]) - float(VGroup(*rest).get_bottom()[1])


@dataclass(frozen=True)
class TextBlock:
    """Text placed by the extent of its font instead of the extent of its ink.

    The top is the first line's ascent above its baseline and the bottom the last line's
    descent below its baseline, so where a block sits does not depend on its letters.

    Attributes:
        mobject: A line of text from `text`, or lines of text from `paragraph`.
        lines: The content of each line.
        style: The font of the text.
        size_px: The font size of the text.
    """

    mobject: VMobject
    lines: tuple[str, ...]
    style: FontStyle
    size_px: float

    def _baseline(self, index: int) -> float:
        line = self.mobject if isinstance(self.mobject, Text) else self.mobject[index]
        return baseline(line, self.lines[index], self.style, self.size_px)

    def top(self) -> float:
        """The y of the top of the first line."""
        return self._baseline(0) + line_metrics(self.style, self.size_px).ascent

    def bottom(self) -> float:
        """The y of the bottom of the last line."""
        return self._baseline(-1) - line_metrics(self.style, self.size_px).descent

    @property
    def height(self) -> float:
        """The distance from the top to the bottom."""
        return self.top() - self.bottom()

    def move_top_to(self, y: float) -> None:
        """Move the block vertically so that its top is at `y`."""
        self.mobject.shift((0.0, y - self.top(), 0.0))

    def move_bottom_to(self, y: float) -> None:
        """Move the block vertically so that its bottom is at `y`."""
        self.mobject.shift((0.0, y - self.bottom(), 0.0))


def text_block(content: str, style: FontStyle, size_px: float, hex_color: str) -> TextBlock:
    """Build a line of text, as `text` does, to be placed by its font's extent."""
    return TextBlock(text(content, style, size_px, hex_color), (content,), style, size_px)


def paragraph_block(
    lines: list[str], style: FontStyle, size_px: float, hex_color: str
) -> TextBlock:
    """Build lines of text, as `paragraph` does, to be placed by their font's extent."""
    return TextBlock(paragraph(lines, style, size_px, hex_color), tuple(lines), style, size_px)


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
    blocks: list[tuple[TextBlock, str]] = []
    if title:
        heading = text_block(title, theme.fonts.heading, theme.sizes.title, theme.colors.text)
        blocks.append((heading, "the title"))
    if subtitle:
        sub = text_block(subtitle, theme.fonts.body, theme.sizes.subtitle, theme.colors.muted)
        blocks.append((sub, "the subtitle"))
    group = VGroup()
    top = layout.title.top
    for index, (block, what) in enumerate(blocks):
        check_fits(block.mobject, layout.title, what)
        if index:
            previous = blocks[index - 1][0]
            top = previous.bottom() - stack_gap(previous.size_px, block.size_px)
        block.move_top_to(top)
        block.mobject.align_to((layout.title.left, 0.0, 0.0), LEFT)
        group.add(block.mobject)
    return group


def source_line(source: str | None, theme: Theme, layout: Layout) -> VMobject | None:
    """Build the source line, left-aligned at the bottom of the source band.

    Raises:
        RenderError: The source is too wide for the frame.
    """
    if not source:
        return None
    block = text_block(source, theme.fonts.body, theme.sizes.caption, theme.colors.muted)
    check_fits(block.mobject, layout.source, "the source")
    block.move_bottom_to(layout.source.bottom)
    return block.mobject.align_to((layout.source.left, 0.0, 0.0), LEFT)
