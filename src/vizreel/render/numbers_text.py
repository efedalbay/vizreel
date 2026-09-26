"""Number text built from cached glyphs, so a counting number can change every frame cheaply.

Imports Manim at the top. Chart modules import this module inside `build`.
"""

from manim import ORIGIN, VMobject

from vizreel.render import elements
from vizreel.themes.models import FontStyle

DIGITS = "0123456789"


def digit_pattern(content: str) -> str:
    """Replace every digit with 0: "$1,234.5M" → "$0,000.0M"."""
    return "".join("0" if char in DIGITS else char for char in content)


class NumberGlyphs:
    """Builds number text in one style, laying out each digit pattern with Pango only once.

    With tabular figures every digit has the same advance, so "$1,234.5M" has its glyphs
    exactly where "$0,000.0M" has them. The pattern is laid out once; each digit glyph is
    then copied in from a cached set and placed where Pango would have put it.
    """

    def __init__(self, style: FontStyle, size_px: float, hex_color: str) -> None:
        self._style, self._size_px, self._color = style, size_px, hex_color
        self._patterns: dict[str, VMobject] = {}
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

    def __call__(self, content: str) -> VMobject:
        """Build the text of a number, centered at the origin like Manim's `Text`."""
        pattern = digit_pattern(content)
        if pattern not in self._patterns:
            self._patterns[pattern] = self._layout(pattern)
        result = self._patterns[pattern].copy()
        visible = [char for char in content if not char.isspace()]
        for index, char in enumerate(visible):
            if char in DIGITS and char != "0":
                result.submobjects[index] = self._digit_at(int(char), result.submobjects[index])
        return result.move_to(ORIGIN)

    def _digit_at(self, digit: int, zero_slot: VMobject) -> VMobject:
        glyph = self._digits[digit].copy()
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
        return elements.number_text(content, self._style, self._size_px, self._color)
