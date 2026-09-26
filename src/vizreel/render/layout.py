"""Geometry of a chart frame in Manim scene units. Pure functions, no Manim import.

Manim's frame is 8 units high at every resolution, so geometry computed here is
resolution-independent. Theme sizes are pixels at 1080p and are converted here.
"""

from dataclasses import dataclass

from vizreel.themes.models import ThemeSizes

FRAME_HEIGHT = 8.0
"""Height of Manim's frame in scene units."""
FRAME_WIDTH = FRAME_HEIGHT * 16 / 9
"""Width of Manim's frame in scene units (16:9)."""
REFERENCE_HEIGHT_PX = 1080
"""Frame height in pixels that theme sizes refer to."""
POINTS_PER_UNIT = 72
"""Manim's `Text` measures `font_size` in points, 72 per scene unit."""
SAFE_MARGIN = 0.05
"""Share of the frame kept empty on every side (docs/DESIGN.md §2)."""
LINE_HEIGHT = 1.3
"""Height of a line of text as a multiple of its font size."""
BAND_GAP = 0.5
"""Gap between the title, content and source bands, as a multiple of the title size."""
STACK_GAP = 0.45
"""Gap between lines of stacked text, as a multiple of the smaller font size."""


def px(pixels: float) -> float:
    """Convert pixels at 1080p to scene units."""
    return pixels * FRAME_HEIGHT / REFERENCE_HEIGHT_PX


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

    def panel_around(self, content: Box) -> Box:
        """Background panel surrounding `content`, kept inside the safe area."""
        return content.expand(self.panel_padding, self.safe)


def build_layout(
    sizes: ThemeSizes,
    *,
    panel: bool,
    title_lines: int,
    subtitle_lines: int,
    source_lines: int,
) -> Layout:
    """Divide the frame into bands for one chart.

    Args:
        sizes: Theme sizes, in pixels at 1080p.
        panel: Whether a background panel is drawn around the content.
        title_lines: Lines of title text (0 without a title).
        subtitle_lines: Lines of subtitle text (0 without a subtitle).
        source_lines: Lines of source text (0 without a source).
    """
    frame = Box(-FRAME_WIDTH / 2, -FRAME_HEIGHT / 2, FRAME_WIDTH / 2, FRAME_HEIGHT / 2)
    safe = Box(
        frame.left + FRAME_WIDTH * SAFE_MARGIN,
        frame.bottom + FRAME_HEIGHT * SAFE_MARGIN,
        frame.right - FRAME_WIDTH * SAFE_MARGIN,
        frame.top - FRAME_HEIGHT * SAFE_MARGIN,
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
