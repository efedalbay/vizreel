"""Geometry of a chart frame in Manim scene units. Pure functions, no Manim import.

The short side of the frame is 8 units at every resolution and in both aspects, so geometry
computed here is resolution-independent, and a size is as large on a vertical frame as on a
landscape one. Theme sizes are pixels at 1080p (on the short side) and are converted here.
"""

from dataclasses import dataclass, replace
from typing import Literal

from vizreel.themes.models import ThemeSizes

Aspect = Literal["16:9", "9:16", "1:1"]
"""Frame shape: landscape, vertical or square."""

SHORT_SIDE = 8.0
"""Short side of Manim's frame in scene units."""
LONG_SIDE = SHORT_SIDE * 16 / 9
"""Long side of Manim's frame in scene units."""
REFERENCE_SHORT_SIDE_PX = 1080
"""Short side of the frame in pixels that theme sizes refer to."""
POINTS_PER_UNIT = 72
"""Manim's `Text` measures `font_size` in points, 72 per scene unit."""
STROKE_UNITS_PER_SCENE_UNIT = 100
"""Manim's `stroke_width` is measured in hundredths of a scene unit."""


@dataclass(frozen=True)
class Margins:
    """Shares of the frame kept empty: left and right of its width, bottom and top of its height."""

    left: float
    bottom: float
    right: float
    top: float


SAFE_MARGINS: dict[Aspect, Margins] = {
    "16:9": Margins(0.05, 0.05, 0.05, 0.05),
    "9:16": Margins(0.06, 0.20, 0.06, 0.10),
    "1:1": Margins(0.05, 0.05, 0.05, 0.05),
}
"""The safe area of each aspect (docs/DESIGN.md §2). Vertical platforms cover the top with
menus and the bottom with the caption, the channel name and buttons."""
LINE_HEIGHT = 1.3
"""Height of a line of text as a multiple of its font size."""
LINE_STEP = 1.2
"""Distance between the baselines of wrapped lines, as a multiple of their font size. Less than
`LINE_HEIGHT`, so wrapped text stays inside the room the layout gives it."""
BAND_GAP = 0.5
"""Gap between the title, content and source bands, as a multiple of the title size."""
STACK_GAP = 0.45
"""Gap between lines of stacked text, as a multiple of the smaller font size."""
BAR_FILL = 0.62
"""Share of each bar's slot covered by the bar; the rest is space between bars."""
LABEL_FILL = 0.96
"""Share of a slot that a category label may use, leaving space between labels."""


def px(pixels: float) -> float:
    """Convert pixels at 1080p to scene units."""
    return pixels * SHORT_SIDE / REFERENCE_SHORT_SIDE_PX


def frame_size(aspect: Aspect) -> tuple[float, float]:
    """Width and height of Manim's frame in scene units."""
    if aspect == "1:1":
        return (SHORT_SIDE, SHORT_SIDE)
    return (LONG_SIDE, SHORT_SIDE) if aspect == "16:9" else (SHORT_SIDE, LONG_SIDE)


def stroke_width(pixels: float) -> float:
    """Convert a stroke width in pixels at 1080p to Manim's `stroke_width`.

    Manim draws strokes `stroke_width` hundredths of a scene unit wide.
    """
    return px(pixels) * STROKE_UNITS_PER_SCENE_UNIT


def stack_gap(above_px: float, below_px: float) -> float:
    """Vertical gap, in scene units, between two stacked lines of text with these font sizes."""
    return px(min(above_px, below_px)) * STACK_GAP


def font_size(pixels: float) -> float:
    """Convert a font size in pixels at 1080p to Manim's `font_size`."""
    return px(pixels) * POINTS_PER_UNIT


@dataclass(frozen=True)
class Box:
    """An axis-aligned rectangle in scene units. The origin is the frame center."""

    left: float
    bottom: float
    right: float
    top: float

    @property
    def width(self) -> float:
        """Horizontal size."""
        return self.right - self.left

    @property
    def height(self) -> float:
        """Vertical size."""
        return self.top - self.bottom

    @property
    def center(self) -> tuple[float, float]:
        """Center point (x, y)."""
        return ((self.left + self.right) / 2, (self.bottom + self.top) / 2)

    def inset(self, amount: float) -> "Box":
        """Shrink by `amount` on every side."""
        return Box(self.left + amount, self.bottom + amount, self.right - amount, self.top - amount)

    def expand(self, amount: float, limit: "Box") -> "Box":
        """Grow by `amount` on every side without leaving `limit`."""
        return Box(
            max(self.left - amount, limit.left),
            max(self.bottom - amount, limit.bottom),
            min(self.right + amount, limit.right),
            min(self.top + amount, limit.top),
        )

    def contains(self, other: "Box") -> bool:
        """Whether `other` lies completely inside this box."""
        return (
            self.left <= other.left
            and self.bottom <= other.bottom
            and other.right <= self.right
            and other.top <= self.top
        )


@dataclass(frozen=True)
class Layout:
    """Areas of a chart frame.

    Attributes:
        frame: The whole frame.
        safe: The frame without the safe margin. Nothing is drawn outside it.
        inner: Where content may go: the safe area, minus the panel padding if a
            background panel is drawn.
        title: Band at the top of `inner` for the title and subtitle. Zero height without them.
        source: Band at the bottom of `inner` for the source line. Zero height without it.
        content: The rest of `inner`, for the chart itself.
        panel: Whether a background panel is drawn behind the content.
        panel_padding: Space between the background panel and the content it surrounds.
        band_gap: Gap between the title, content and source bands.
    """

    frame: Box
    safe: Box
    inner: Box
    title: Box
    source: Box
    content: Box
    panel: bool
    panel_padding: float
    band_gap: float

    @property
    def vertical(self) -> bool:
        """Whether the frame is taller than it is wide."""
        return self.frame.height > self.frame.width

    @property
    def square(self) -> bool:
        """Whether the frame is as tall as it is wide."""
        return abs(self.frame.height - self.frame.width) < 1e-9

    def panel_around(self, content: Box) -> Box:
        """Background panel surrounding `content`, kept inside the safe area."""
        return content.expand(self.panel_padding, self.safe)

    def fitted_to_content(self, bottom: float, top: float) -> "Layout":
        """Return this layout closed in around chart content that spans `bottom` to `top`.

        The title band goes just above the content and the source band just below it, and
        `inner`, which the panel surrounds, shrinks to them. The card is centered where
        `inner` was, and `content` moves with the content without changing size, so a chart
        built in it draws exactly what it drew before, only shifted.
        """
        title_height, source_height = self.title.height, self.source.height
        title_gap = self.band_gap if title_height else 0.0
        source_gap = self.band_gap if source_height else 0.0
        card = title_height + title_gap + (top - bottom) + source_gap + source_height
        if card >= self.inner.height - 1e-9:
            return self
        center = self.inner.center[1]
        left, right = self.inner.left, self.inner.right
        inner = Box(left, center - card / 2, right, center + card / 2)
        shift = inner.top - title_height - title_gap - top
        content = self.content
        return replace(
            self,
            inner=inner,
            title=Box(left, inner.top - title_height, right, inner.top),
            source=Box(left, inner.bottom, right, inner.bottom + source_height),
            content=Box(content.left, content.bottom + shift, content.right, content.top + shift),
        )


def build_layout(
    sizes: ThemeSizes,
    *,
    aspect: Aspect = "16:9",
    panel: bool,
    title_lines: int,
    subtitle_lines: int,
    source_lines: int,
) -> Layout:
    """Divide the frame into bands for one chart.

    Args:
        sizes: Theme sizes, in pixels at 1080p.
        aspect: The frame shape.
        panel: Whether a background panel is drawn around the content.
        title_lines: Lines of title text (0 without a title).
        subtitle_lines: Lines of subtitle text (0 without a subtitle).
        source_lines: Lines of source text (0 without a source).
    """
    width, height = frame_size(aspect)
    margins = SAFE_MARGINS[aspect]
    frame = Box(-width / 2, -height / 2, width / 2, height / 2)
    safe = Box(
        frame.left + width * margins.left,
        frame.bottom + height * margins.bottom,
        frame.right - width * margins.right,
        frame.top - height * margins.top,
    )
    padding = px(sizes.panel_padding) if panel else 0.0
    inner = safe.inset(padding)
    gap = px(sizes.title) * BAND_GAP

    title_height = px(LINE_HEIGHT * (sizes.title * title_lines + sizes.subtitle * subtitle_lines))
    source_height = px(LINE_HEIGHT * sizes.caption * source_lines)
    title_band = Box(inner.left, inner.top - title_height, inner.right, inner.top)
    source_band = Box(inner.left, inner.bottom, inner.right, inner.bottom + source_height)
    content_top = title_band.bottom - (gap if title_height else 0)
    content_bottom = source_band.top + (gap if source_height else 0)
    content = Box(inner.left, content_bottom, inner.right, content_top)

    return Layout(
        frame=frame,
        safe=safe,
        inner=inner,
        title=title_band,
        source=source_band,
        content=content,
        panel=panel,
        band_gap=gap,
        panel_padding=padding,
    )
