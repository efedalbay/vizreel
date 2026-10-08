"""Number text built from cached glyphs, so a counting number can change every frame cheaply.

Imports Manim at the top. Chart modules import this module inside `build`.
"""

from manim import ORIGIN, VGroup, VMobject

from vizreel.render import elements
from vizreel.themes.models import FontStyle

DIGITS = "0123456789"


def shape_copy(mobject: VMobject) -> VMobject:
    """Copy the shapes and style of a mobject and its parts, and nothing else.

    Manim's `copy` deep-copies every attribute, which for text takes far longer than drawing
    it; a number that counts is built again on every frame.
    """
    if mobject.submobjects:
        return VGroup(*(shape_copy(part) for part in mobject.submobjects))
    copy = VMobject()
    copy.set_points(mobject.points.copy())
    copy.match_style(mobject)
    return copy


def digit_pattern(content: str) -> str:
    """Replace every digit with 0: "$1,234.5M" → "$0,000.0M"."""
    return "".join("0" if char in DIGITS else char for char in content)


class NumberGlyphs:
    """Builds number text in one style, laying out each digit pattern with Pango only once.

    With tabular figures every digit has the same advance, so "$1,234.5M" has its glyphs
    exactly where "$0,000.0M" has them. The pattern is laid out once; each digit glyph is
    then copied in from a cached set and placed where Pango would have put it.

    Every number of a pattern has the same bounding box, whatever its digits: an invisible
    strut, its last part, spans what any digit could cover in each digit's place. A number
    placed by its box, as charts place labels, so stays put while it counts, even in a font
    whose digits are not all as tall, such as one with old-style figures.
    """

    def __init__(
        self, style: FontStyle, size_px: float, hex_color: str, affix_scale: float = 1.0
    ) -> None:
        """Prepare the digits of one style.

        Args:
            style: The font.
            size_px: The size of the digits.
            hex_color: The color.
            affix_scale: Size of what precedes and follows the digits, relative to them; see
                `elements.number_text`. Big numbers use the theme's `affix_scale`.
        """
        self._style, self._size_px, self._color = style, size_px, hex_color
        self._affix_scale = affix_scale
        self._patterns: dict[str, VMobject] = {}
        self._baselines: dict[str, float] = {}
        digits = self._layout(DIGITS)
        zeros = self._layout("0" * len(DIGITS))
        advance = (zeros[-1].get_left()[0] - zeros[0].get_left()[0]) / (len(DIGITS) - 1)
        zero = digits[0]
        self._digits: list[VMobject] = list(digits.submobjects)
        self._offsets = [
            (
                glyph.get_left()[0] - zero.get_left()[0] - index * advance,
                glyph.get_bottom()[1] - zero.get_bottom()[1],
            )
            for index, glyph in enumerate(self._digits)
        ]
        # How far any digit reaches past a 0 in its place, on each side.
        self._reach = (
            min(0.0, *(dx for dx, _ in self._offsets)),
            max(
                0.0,
                *(
                    dx + glyph.width - zero.width
                    for (dx, _), glyph in zip(self._offsets, self._digits, strict=True)
                ),
            ),
            min(0.0, *(dy for _, dy in self._offsets)),
            max(
                0.0,
                *(
                    dy + glyph.height - zero.height
                    for (_, dy), glyph in zip(self._offsets, self._digits, strict=True)
                ),
            ),
        )

    def __call__(self, content: str) -> VMobject:
        """Build the text of a number, centered at the origin like Manim's `Text`."""
        pattern = digit_pattern(content)
        if pattern not in self._patterns:
            self._patterns[pattern] = self._with_strut(self._layout(pattern), pattern)
        result = shape_copy(self._patterns[pattern])
        visible = [char for char in content if not char.isspace()]
        for index, char in enumerate(visible):
            if char in DIGITS and char != "0":
                result.submobjects[index] = self._digit_at(int(char), result.submobjects[index])
        return result.move_to(ORIGIN)

    def _with_strut(self, layout: VMobject, pattern: str) -> VMobject:
        """Add to a laid-out pattern the strut that keeps its box the same for every value."""
        visible = [char for char in pattern if not char.isspace()]
        slots = [layout.submobjects[index] for index, char in enumerate(visible) if char == "0"]
        if not slots:
            return layout
        left_reach, right_reach, down_reach, up_reach = self._reach
        left = min(float(layout.get_left()[0]), float(slots[0].get_left()[0]) + left_reach)
        right = max(float(layout.get_right()[0]), float(slots[-1].get_right()[0]) + right_reach)
        bottom = min(
            float(layout.get_bottom()[1]),
            min(float(slot.get_bottom()[1]) for slot in slots) + down_reach,
        )
        top = max(
            float(layout.get_top()[1]), max(float(slot.get_top()[1]) for slot in slots) + up_reach
        )
        # A line of no width and no area: nothing to see, whatever color or opacity it gets.
        strut = VMobject(stroke_width=0, fill_opacity=0)
        strut.set_points_as_corners([(left, bottom, 0.0), (right, top, 0.0)])
        layout.add(strut)
        # Built numbers are centered by their box; their 0s stand this far from its center.
        self._baselines[pattern] = float(slots[0].get_bottom()[1]) - (bottom + top) / 2
        return layout

    def at(self, content: str, x: float, baseline: float) -> VMobject:
        """Build the text of a number centered at `x`, its digits standing on `baseline`.

        Placing by the digits rather than the ink keeps two numbers level when one has a comma
        or a dollar sign that reaches below the digits.
        """
        result = self(content)
        # Where a 0 of the pattern stands, which no digit moves.
        bottom = self._baselines.get(digit_pattern(content), 0.0)
        return result.shift((x - result.get_center()[0], baseline - bottom, 0.0))

    def _digit_at(self, digit: int, zero_slot: VMobject) -> VMobject:
        glyph = shape_copy(self._digits[digit])
        dx, dy = self._offsets[digit]
        glyph.shift(
            (
                zero_slot.get_left()[0] + dx - glyph.get_left()[0],
                zero_slot.get_bottom()[1] + dy - glyph.get_bottom()[1],
                0.0,
            )
        )
        return glyph

    def _layout(self, content: str) -> VMobject:
        return elements.number_text(
            content, self._style, self._size_px, self._color, self._affix_scale
        )
