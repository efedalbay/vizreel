"""What a TTF or OTF font file says about itself: its family, weight and width. Pure Python.

Text renderers choose a face by family, weight and width, so a theme that brings a font
file must ask for that file's own weight and width, or another file of the family, or no
font at all, is drawn instead.
"""

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

FontWeight = Literal["regular", "medium", "semibold", "bold", "extrabold", "black"]
"""The weights a theme can draw, from regular (400) to black (900)."""

FontStretch = Literal[
    "ultracondensed",
    "extracondensed",
    "condensed",
    "semicondensed",
    "normal",
    "semiexpanded",
    "expanded",
    "extraexpanded",
    "ultraexpanded",
]
"""The widths of a font, from narrowest to widest, as text renderers name them."""

WEIGHT_CLASSES: dict[FontWeight, int] = {
    "regular": 400,
    "medium": 500,
    "semibold": 600,
    "bold": 700,
    "extrabold": 800,
    "black": 900,
}
"""The weight class of each weight, as fonts number them."""

LIGHTEST_CLASS = 350
"""Fonts lighter than this, such as Light (300) or Thin (100), are not drawn."""

STRETCHES: tuple[FontStretch, ...] = (
    "ultracondensed",
    "extracondensed",
    "condensed",
    "semicondensed",
    "normal",
    "semiexpanded",
    "expanded",
    "extraexpanded",
    "ultraexpanded",
)
"""The widths, in the order of a font's width class, 1 to 9."""

WEIGHT_WORDS: dict[str, FontWeight] = {
    "regular": "regular",
    "normal": "regular",
    "book": "regular",
    "medium": "medium",
    "semibold": "semibold",
    "demibold": "semibold",
    "bold": "bold",
    "extrabold": "extrabold",
    "ultrabold": "extrabold",
    "black": "black",
    "heavy": "black",
}
"""Words a font's style name uses for a weight."""

WIDTH_WORDS = (
    "Ultra Condensed",
    "UltraCondensed",
    "Extra Condensed",
    "ExtraCondensed",
    "Semi Condensed",
    "SemiCondensed",
    "Condensed",
    "Narrow",
    "Compressed",
    "Semi Expanded",
    "SemiExpanded",
    "Extra Expanded",
    "ExtraExpanded",
    "Ultra Expanded",
    "UltraExpanded",
    "Expanded",
    "Extended",
)
"""Words a family name may end with that a text renderer may take as a width instead."""


@dataclass(frozen=True)
class FontFile:
    """What a font file says about itself.

    Attributes:
        family: Its family as the file names it, typographic family first: "IBM Plex Mono"
            for IBM Plex Mono Medium.
        names: Every name a text renderer may list the family under, most likely first:
            the typographic family, the legacy family, and both without a width word, as
            some renderers list "Archivo Condensed" as "Archivo", condensed.
        style: Its style name, e.g. "Bold" or "ExtraBold".
        weight_class: Its weight, from 1 to 1000; 400 is regular, 700 bold.
        width_class: Its width, from 1 to 9; 5 is normal, 3 condensed.
    """

    family: str
    names: tuple[str, ...]
    style: str
    weight_class: int
    width_class: int

    @property
    def weight(self) -> FontWeight:
        """The theme weight nearest the file's weight class."""
        return min(WEIGHT_CLASSES, key=lambda name: abs(WEIGHT_CLASSES[name] - self.weight_class))

    @property
    def stretch(self) -> FontStretch:
        """The width the file is drawn at."""
        return STRETCHES[min(max(self.width_class, 1), 9) - 1]

    def named_weights(self) -> set[FontWeight]:
        """The weights the file may be called: its nearest weight, and the one its style names.

        JetBrains Mono Bold has weight class 558, nearest semibold; it may be called bold too.
        """
        words = self.style.lower().replace(" ", "").replace("-", "")
        # "ExtraBold" holds "bold" too; the longest word in the style is its own.
        found = [word for word in WEIGHT_WORDS if word in words]
        if not found:
            return {self.weight}
        return {self.weight, WEIGHT_WORDS[max(found, key=len)]}


def read_font_file(path: Path) -> FontFile:
    """Read the family, style, weight and width of a TTF or OTF file.

    Raises:
        OSError: The file cannot be read.
        ValueError: The file is not a font, or names no family.
    """
    data = path.read_bytes()
    tables = _tables(data)
    if "name" not in tables or "OS/2" not in tables:
        raise ValueError(f"{path.name} has no name or OS/2 table")
    names = _names(data, tables["name"])
    legacy = names.get(1, "")
    typographic = names.get(16, "") or legacy
    if not typographic:
        raise ValueError(f"{path.name} names no font family")
    style = names.get(17, "") or names.get(2, "")
    offset, length = tables["OS/2"]
    if length < 8:
        raise ValueError(f"{path.name} has a broken OS/2 table")
    weight_class, width_class = struct.unpack(">HH", data[offset + 4 : offset + 8])
    candidates = [typographic, legacy, _without_width(typographic), _without_width(legacy)]
    return FontFile(
        family=typographic,
        names=tuple(dict.fromkeys(name for name in candidates if name)),
        style=style,
        weight_class=weight_class,
        width_class=width_class,
    )


def _tables(data: bytes) -> dict[str, tuple[int, int]]:
    """The offset and length of each table of an sfnt font."""
    if len(data) < 12 or data[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
        raise ValueError("not a TTF or OTF font")
    (count,) = struct.unpack(">H", data[4:6])
    tables = {}
    for index in range(count):
        start = 12 + 16 * index
        if start + 16 > len(data):
            raise ValueError("a broken font: its table list is cut short")
        tag, _, offset, length = struct.unpack(">4sIII", data[start : start + 16])
        if offset + length > len(data):
            raise ValueError("a broken font: a table runs past its end")
        tables[tag.decode("latin-1")] = (offset, length)
    return tables


def _names(data: bytes, table: tuple[int, int]) -> dict[int, str]:
    """The English names of a font's name table, by name ID, Windows names first."""
    offset, length = table
    _, count, strings = struct.unpack(">HHH", data[offset : offset + 6])
    found: dict[int, str] = {}
    mac: dict[int, str] = {}
    for index in range(count):
        record = offset + 6 + 12 * index
        if record + 12 > offset + length:
            break
        platform, _, language, name_id, size, start = struct.unpack(
            ">HHHHHH", data[record : record + 12]
        )
        raw = data[offset + strings + start : offset + strings + start + size]
        if platform == 3 and language == 0x409:
            found[name_id] = raw.decode("utf-16-be", errors="replace")
        elif platform == 1 and language == 0:
            mac[name_id] = raw.decode("mac-roman", errors="replace")
    return {**mac, **found}


def _without_width(family: str) -> str:
    """The family without a width word at its end: "Archivo Condensed" → "Archivo"."""
    for word in WIDTH_WORDS:
        if family.endswith(" " + word):
            return family[: -len(word) - 1]
    return family
