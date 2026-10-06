"""Manim building blocks shared by chart types: text, headers, panels, easing, motion.

Imports Manim at the top. Chart modules import this module inside `build`.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cache
from typing import Any, Literal
from xml.sax.saxutils import escape

import numpy as np
from manim import (
    DOWN,
    LEFT,
    ORIGIN,
    UP,
    Animation,
    FadeIn,
    Group,
    ImageMobject,
    ManimColor,
    MarkupText,
    Mobject,
    RoundedRectangle,
    Text,
    UpdateFromAlphaFunc,
    VGroup,
    VMobject,
    config,
    rate_functions,
)

from vizreel.errors import RenderError
from vizreel.format.numbers import split_number_text
from vizreel.render.layout import LINE_STEP, Box, Layout, font_size, px, stack_gap, stroke_width
from vizreel.render.scales import ring_path, wrap_text
from vizreel.themes.models import FontStyle, FontWeight, Theme

_PANGO_WEIGHTS = {"regular": "NORMAL", "semibold": "SEMIBOLD", "bold": "BOLD"}
PANEL_Z_INDEX = -1
LAYOUT_FONT_SIZE = 150
"""Text is laid out at least this large (Manim font size) and scaled to its real size.

Pango rounds glyph positions, which at small sizes makes letter spacing uneven
("Northw ind"). Much larger sizes overflow the surface Manim gives Pango and lose glyphs.
"""
MAX_TEXT_LINES = 2
"""Most lines a title, subtitle or stat line wraps onto."""
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


def paragraph(
    lines: list[str],
    style: FontStyle,
    size_px: float,
    hex_color: str,
    align: Literal["center", "left"] = "center",
) -> VMobject:
    """Build lines of text with their baselines `LINE_STEP` font sizes apart.

    Pango's own spacing for Inter leaves almost nothing between a descender and the ascender
    of the line below, which reads as cramped at title sizes.

    Raises:
        RenderError: Pango could not lay out every character.
    """
    lines = [line.strip() for line in lines]
    step = px(size_px) * LINE_STEP
    mobjects = []
    for index, line in enumerate(lines):
        mobject = text(line, style, size_px, hex_color)
        mobject.shift((0.0, -index * step - baseline(mobject, line, style, size_px), 0.0))
        mobject.shift((-(mobject.get_left()[0] if align == "left" else mobject.get_x()), 0.0, 0.0))
        mobjects.append(mobject)
    return VGroup(*mobjects).move_to(ORIGIN)


def number_text(
    content: str, style: FontStyle, size_px: float, hex_color: str, affix_scale: float = 1.0
) -> VMobject:
    """Build a number with tabular figures, so every digit has the same width.

    Args:
        content: Formatted number text.
        style: The font.
        size_px: The size of the digits.
        hex_color: The color.
        affix_scale: Size of what precedes and follows the digits (a currency, a unit name,
            a percent sign), relative to the digits, on the same baseline. The minus sign
            and the parentheses of a negative number keep the size of the digits.

    Raises:
        RenderError: Pango could not lay out every character.
    """
    size = font_size(size_px)
    oversample = max(1.0, LAYOUT_FONT_SIZE / size)
    sign, prefix, digits, suffix, closing = split_number_text(content)
    markup = escape(content)
    if affix_scale != 1.0:
        small = f'<span size="{affix_scale:.0%}">'
        affixes = [(small + escape(part) + "</span>") if part else "" for part in (prefix, suffix)]
        markup = escape(sign) + affixes[0] + escape(digits) + affixes[1] + escape(closing)
    with _text_surface():
        mobject = MarkupText(
            f'<span font_features="tnum">{markup}</span>',
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
    lines: list[str],
    style: FontStyle,
    size_px: float,
    hex_color: str,
    align: Literal["center", "left"] = "center",
) -> TextBlock:
    """Build lines of text, as `paragraph` does, to be placed by their font's extent."""
    mobject = paragraph(lines, style, size_px, hex_color, align)
    return TextBlock(mobject, tuple(lines), style, size_px)


def _check_complete(mobject: VMobject, content: str, expected: int) -> None:
    """Check that Pango laid out every character, not only the ones that fit its surface."""
    if len(mobject.submobjects) != expected:
        raise RenderError(f'"{content}" could not be laid out completely; shorten it')


def easing(theme: Theme) -> Callable[[float], float]:
    """Return the theme's easing curve as a Manim rate function."""
    curve: Callable[[float], float] = getattr(rate_functions, theme.motion.easing)
    return curve


def fade_away(mobject: Mobject) -> UpdateFromAlphaFunc:
    """Fade a mobject out by lowering its opacity, leaving its shape alone.

    Manim's FadeOut first splits the mobject's curves to match its target, which moves a
    few edge pixels by a shade; a clip of a sequence must start on exactly the frame the
    clip before it ended on. The faded mobject stays on the scene, invisible.
    """

    def fade(target: Mobject, alpha: float) -> None:
        target.set_opacity(1 - alpha)

    # Manim calls the update function with (mobject, alpha) but types it with one argument.
    return UpdateFromAlphaFunc(mobject, fade)  # type: ignore[arg-type]


def redrawn(build: Callable[[], Mobject]) -> Group:
    """Return a group whose parts are built again, by `build`, on every frame.

    Unlike Manim's `always_redraw`, which copies the new parts into the old ones, it takes
    the new parts as they are, which is much faster for a frame of many parts. It starts
    empty: Manim draws, on every frame of an animation, the parts a moving group has when the
    animation starts, and the first update comes before the first frame.
    """
    group = Group()
    group.add_updater(lambda mobject: setattr(mobject, "submobjects", build().submobjects))
    return group


def redrawn_shapes(build: Callable[[], VMobject]) -> VGroup:
    """Return a group holding a shape that `build` builds again on every frame.

    A faster `always_redraw` for shapes and text: Manim's copies the new points into the old
    shape, aligning them point by point, which takes most of a frame's time. It is a
    `VGroup`, so it can be grouped with other shapes, and starts empty like `redrawn`.
    """
    group = VGroup()
    group.add_updater(lambda mobject: setattr(mobject, "submobjects", [build()]))
    return group


MOTION_DISTANCE = 1.0
"""How far an entrance rises and an exit sinks, as a multiple of the label size."""
ZOOM_SCALE = 0.9
"""The size an entrance grows from and an exit shrinks to, as a share of the full size."""


def appear(mobject: Mobject, theme: Theme, **kwargs: Any) -> Animation:
    """Make a panel, title, label or legend appear, as the theme's `entrance` says.

    It fades in, and with `rise` also rises a little into place, with `zoom` grows a little
    into place. Data does not appear this way: bars grow, lines draw and numbers count.

    Args:
        mobject: What appears.
        theme: The entrance, and the label size that sets how far it rises.
        **kwargs: Passed on to the animation, e.g. `run_time` and `rate_func`.
    """
    entrance = theme.motion.entrance
    if entrance == "rise":
        return FadeIn(mobject, shift=UP * px(theme.sizes.label) * MOTION_DISTANCE, **kwargs)
    if entrance == "zoom":
        return FadeIn(mobject, scale=ZOOM_SCALE, **kwargs)
    return FadeIn(mobject, **kwargs)


def leave(mobjects: list[Mobject], theme: Theme, center: tuple[float, float]) -> Animation:
    """Make everything on the scene leave, as the theme's `exit` says.

    Every part fades out from its own opacity, so a dimmed part stays dimmer than the rest
    until the end. With `sink` everything also sinks a little, with `zoom` it shrinks a
    little toward `center`.

    Args:
        mobjects: The mobjects on the scene.
        theme: The exit, and the label size that sets how far it sinks.
        center: The point everything shrinks toward.
    """
    exit_style = theme.motion.exit
    members = list(
        dict.fromkeys(
            member for mobject in mobjects for member in mobject.family_members_with_points()
        )
    )
    parts = [part for part in members if isinstance(part, VMobject)]
    opacities = [(part.fill_rgbas[:, 3].copy(), part.stroke_rgbas[:, 3].copy()) for part in parts]
    images = [part for part in members if isinstance(part, ImageMobject)]
    image_alphas = [image.pixel_array[:, :, 3].copy() for image in images]
    distance = px(theme.sizes.label) * MOTION_DISTANCE
    reached = {"alpha": 0.0}

    def step(_: Mobject, alpha: float) -> None:
        before, reached["alpha"] = reached["alpha"], alpha
        for part, (fill, stroke) in zip(parts, opacities, strict=True):
            part.fill_rgbas[:, 3] = fill * (1 - alpha)
            part.stroke_rgbas[:, 3] = stroke * (1 - alpha)
        for image, image_alpha in zip(images, image_alphas, strict=True):
            image.pixel_array[:, :, 3] = image_alpha * (1 - alpha)
        for mobject in mobjects:
            if exit_style == "sink":
                mobject.shift(DOWN * distance * (alpha - before))
            elif exit_style == "zoom":
                factor = (1 - (1 - ZOOM_SCALE) * alpha) / (1 - (1 - ZOOM_SCALE) * before)
                mobject.scale(factor, about_point=(*center, 0.0))

    # The animation is on everything, so that Manim redraws it all instead of keeping the
    # parts it thinks are still as a fixed background. Manim calls the update function with
    # (mobject, alpha) but types it with one argument.
    return UpdateFromAlphaFunc(Group(*mobjects), step)  # type: ignore[arg-type]


def panel(box: Box, theme: Theme) -> Mobject:
    """Build the background panel covering `box`. It is drawn behind everything else.

    With a theme texture it is a group: the panel's color, then its ruled lines or picture.
    """
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
    if theme.texture is None:
        return rectangle
    from vizreel.render.texture import panel_texture

    margin_x = box.left + px(theme.sizes.panel_padding) / 2
    return Group(rectangle, *panel_texture(box, theme, margin_x, radius))


RING_PADDING = 0.1
"""Least space between a highlight ring and the corners of what it rings, as a share of the
ringed text's height."""
RING_STROKE = 0.6
"""Width of a highlight ring's pen, as a share of the theme's data line width."""
RING_Z_INDEX = 2
"""A highlight ring is drawn over the chart, as a pen mark on the page would be."""


def highlight_ring(box: Box, theme: Theme) -> VMobject:
    """Build the ring the theme's `highlight_mark: ring` draws around a highlighted value.

    It leans a little and its ends pass each other, as a pen ring does; it never crosses
    `box`. Draw it with `draw_ring` at the highlight beat. Its pen is the theme's `mark` color,
    or its `highlight` color.
    """
    points = ring_path(box.center, box.width, box.height, box.height * RING_PADDING)
    ring = VMobject()
    ring.set_points_smoothly([np.array((x, y, 0.0)) for x, y in points])
    ring.set_stroke(
        color(theme.colors.mark or theme.colors.highlight),
        width=stroke_width(theme.sizes.line * RING_STROKE),
    )
    ring.set_fill(opacity=0)
    return ring.set_z_index(RING_Z_INDEX)


def draw_ring(ring: VMobject, **kwargs: Any) -> Animation:
    """Draw a highlight ring as a pen does, from its start to its end.

    Unlike Manim's Create, it shows nothing at all before it starts: Create draws a dot where
    the pen will start, so a clip of a sequence would not start on exactly the frame the clip
    before it ended on.

    Args:
        ring: A ring from `highlight_ring`.
        **kwargs: Passed on to the animation, e.g. `run_time` and `rate_func`.
    """
    whole = ring.copy()
    opacity = ring.get_stroke_opacity()

    def draw(target: VMobject, alpha: float) -> None:
        target.pointwise_become_partial(whole, 0, alpha)
        target.set_stroke(opacity=opacity if alpha > 0 else 0)

    # Manim calls the update function with (mobject, alpha) but types it with one argument.
    return UpdateFromAlphaFunc(ring, draw, introducer=True, **kwargs)  # type: ignore[arg-type]


def erase_ring(ring: VMobject, **kwargs: Any) -> Animation:
    """Fade a highlight ring out by its pen alone.

    `fade_away` sets the whole opacity, which would fill the ring's inside; a ring has no
    fill. The ring stays on the scene, invisible.
    """
    opacity = ring.get_stroke_opacity()

    def erase(target: VMobject, alpha: float) -> None:
        target.set_stroke(opacity=opacity * (1 - alpha))

    # Manim calls the update function with (mobject, alpha) but types it with one argument.
    return UpdateFromAlphaFunc(ring, erase, **kwargs)  # type: ignore[arg-type]


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


def wrapped_lines(
    content: str,
    style: FontStyle,
    size_px: float,
    width: float,
    what: str,
    max_lines: int = MAX_TEXT_LINES,
) -> list[str]:
    """Split text into at most `max_lines` lines that each fit `width`.

    Raises:
        RenderError: The text does not fit in that many lines.
    """
    lines = wrap_text(
        content, lambda line: text(line, style, size_px, "#000000").width <= width, max_lines
    )
    if lines is None:
        raise RenderError(
            f"{what} is too long to fit on {max_lines} lines at the theme's size; shorten it"
        )
    return lines


def wrapped_block(
    content: str,
    style: FontStyle,
    size_px: float,
    hex_color: str,
    width: float,
    what: str,
    align: Literal["center", "left"],
    max_lines: int = MAX_TEXT_LINES,
) -> TextBlock:
    """Build text on as many lines as it needs to fit `width`, at most `max_lines`.

    Raises:
        RenderError: The text does not fit in that many lines.
    """
    lines = wrapped_lines(content, style, size_px, width, what, max_lines)
    if len(lines) == 1:
        return text_block(content, style, size_px, hex_color)
    return paragraph_block(lines, style, size_px, hex_color, align)


def header_lines(
    title: str | None, subtitle: str | None, theme: Theme, width: float
) -> tuple[list[str], list[str]]:
    """Return the lines of the title and of the subtitle when wrapped to `width`.

    Raises:
        RenderError: The title or subtitle does not fit in `MAX_TEXT_LINES` lines.
    """
    fonts, sizes = theme.fonts, theme.sizes
    return (
        wrapped_lines(title, fonts.heading, sizes.title, width, "the title") if title else [],
        wrapped_lines(subtitle, fonts.body, sizes.subtitle, width, "the subtitle")
        if subtitle
        else [],
    )


def header(title: str | None, subtitle: str | None, theme: Theme, layout: Layout) -> VGroup:
    """Build the title and subtitle, left-aligned at the top of the title band.

    Each wraps onto a second line if it does not fit the width of the band.

    Raises:
        RenderError: The title or subtitle does not fit on two lines.
    """
    fonts, sizes, colors = theme.fonts, theme.sizes, theme.colors
    width = layout.title.width
    blocks: list[TextBlock] = []
    if title:
        blocks.append(
            wrapped_block(
                title, fonts.heading, sizes.title, colors.text, width, "the title", "left"
            )
        )
    if subtitle:
        blocks.append(
            wrapped_block(
                subtitle, fonts.body, sizes.subtitle, colors.muted, width, "the subtitle", "left"
            )
        )
    group = VGroup()
    top = layout.title.top
    for index, block in enumerate(blocks):
        if index:
            previous = blocks[index - 1]
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
