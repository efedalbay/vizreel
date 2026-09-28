"""Parts shared by the chart types that draw bars per category: bar, waterfall and stacked.

Not a chart type itself; the registry skips modules whose name starts with an underscore.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, TypeVar

from vizreel.charts.base import arranged
from vizreel.errors import RenderError
from vizreel.render.layout import BAR_FILL, Box, Layout, px, stack_gap
from vizreel.render.scales import two_line_splits
from vizreel.themes.models import Theme

if TYPE_CHECKING:
    from manim import VMobject

    from vizreel.render.elements import TextBlock

MIN_ROW_THICKNESS_PX = 16
"""Least thickness, in pixels at 1080p, of the bar in a row."""
MAX_ROW_THICKNESS = 1.5
"""Most thickness of the bar in a row, as a multiple of the value font size."""
MAX_ROW_GAP = 0.8
"""Most space between rows, as a multiple of the height of a row."""
LEGEND_MARK = 0.3
"""Radius of a legend dot, as a share of the label size, so the dot matches the name."""

T = TypeVar("T")

BarLayout = Literal["auto", "columns", "rows"]


def by_bar_layout(
    bar_layout: BarLayout, layout: Layout, columns: Callable[[], T], rows: Callable[[], T]
) -> T:
    """Build a bar chart's geometry as columns or rows, as its `layout` field asks.

    `auto` uses what the frame calls for: columns at 16:9, rows at 9:16, and at 1:1 columns
    if they fit, else rows (see `arranged`).
    """
    if bar_layout == "columns":
        return columns()
    if bar_layout == "rows":
        return rows()
    return arranged(layout, columns, rows)


@dataclass(frozen=True)
class Row:
    """Where one row of a bar chart goes, in scene units.

    Attributes:
        label_top: Top of the row's label.
        bar_center: Vertical center of the row's bar.
        thickness: Height of the row's bar.
    """

    label_top: float
    bar_center: float
    thickness: float


def plan_rows(
    count: int,
    top: float,
    bottom: float,
    label_height: float,
    label_gap: float,
    thickness_range: tuple[float, float],
    fill: float = BAR_FILL,
) -> list[Row]:
    """Stack `count` rows, each a label above a bar, centered between `bottom` and `top`.

    Each row gets an equal share of the height. The bar takes `fill` of what the label
    leaves, within `thickness_range`; the gap between rows is at most `MAX_ROW_GAP` rows, so a
    few rows stay together instead of spreading over a tall frame.

    Raises:
        RenderError: The bars would be thinner than the least thickness.
    """
    thinnest, thickest = thickness_range
    share = (top - bottom) / count
    thickness = min((share - label_height - label_gap) * fill, thickest)
    if thickness < thinnest:
        raise RenderError("not enough room for the bars; shorten the title or the labels")
    row_height = label_height + label_gap + thickness
    gap = min(share - row_height, row_height * MAX_ROW_GAP)
    total = count * row_height + (count - 1) * gap
    first_top = (top + bottom + total) / 2
    rows = []
    for index in range(count):
        row_top = first_top - index * (row_height + gap)
        rows.append(Row(row_top, row_top - label_height - label_gap - thickness / 2, thickness))
    return rows


@dataclass(frozen=True)
class BarGeometry:
    """Where the parts of a bar chart go, for columns or rows.

    Attributes:
        labels: The category labels, in place.
        bar: Builds bar `index` grown by a share from 0 to 1, in a fill color.
        value: Builds the value label of bar `index` grown by a share, at the bar's end.
        axis: The line the bars grow from, or None.
    """

    labels: list["VMobject"]
    bar: Callable[[int, float, str], "VMobject"]
    value: Callable[[int, float], "VMobject"]
    axis: "VMobject | None"


def category_label(
    content: str,
    theme: Theme,
    width: float,
    align: Literal["center", "left"],
    too_long: str,
) -> "TextBlock":
    """Build a category label on one line, or split in two if one line is wider than `width`.

    Args:
        content: The label.
        theme: Its font, size and color come from here.
        width: Widest a line may be.
        align: How two lines line up.
        too_long: The error message when the label does not fit on two lines.

    Raises:
        RenderError: The label does not fit on two lines.
    """
    from vizreel.render import elements

    fonts, sizes, colors = theme.fonts, theme.sizes, theme.colors
    single = elements.text_block(content, fonts.body, sizes.label, colors.muted)
    if single.mobject.width <= width:
        return single
    for split in two_line_splits(content):
        lines = [elements.text(part, fonts.body, sizes.label, colors.muted) for part in split]
        if all(line.width <= width for line in lines):
            return elements.paragraph_block(
                list(split), fonts.body, sizes.label, colors.muted, align
            )
    raise RenderError(too_long)


def series_legend(
    names: list[str], series_colors: list[str], theme: Theme, content: Box
) -> "VMobject":
    """Build a legend, a dot and a name per series, at the top left of `content`.

    The items sit in one row, or one under another if the row is wider than the content.
    Item `i` is a group of its dot and its name.

    Raises:
        RenderError: The names do not fit even one under another.
    """
    from manim import DOWN, LEFT, RIGHT, UP, Dot, VGroup

    from vizreel.render import elements

    fonts, sizes, colors = theme.fonts, theme.sizes, theme.colors
    gap = stack_gap(sizes.label, sizes.label)
    items = VGroup(
        *(
            VGroup(
                Dot(radius=px(sizes.label) * LEGEND_MARK, color=color),
                elements.text(name, fonts.body, sizes.label, colors.muted),
            ).arrange(RIGHT, buff=gap / 2)
            for name, color in zip(names, series_colors, strict=True)
        )
    )
    items.arrange(RIGHT, buff=gap * 2)
    if items.width > content.width:
        items.arrange(DOWN, buff=gap / 2, aligned_edge=LEFT)
    if items.width > content.width:
        raise RenderError("the series names are too long for the legend; shorten them")
    return items.align_to((content.left, content.top, 0.0), UP + LEFT)


def series_emphasis(
    kept: int | None,
    parts: list[list["VMobject"]],
    legend: "VMobject",
    series_colors: list[str],
    theme: Theme,
    layout: Layout,
) -> list[Any]:
    """Return the animations that keep series `kept` in its color and dim the others.

    Args:
        kept: Index of the series to keep, or None to dim none.
        parts: The drawn parts of each series.
        legend: The legend from `series_legend`, whose dots and names follow their series.
        series_colors: The color of each series.
        theme: Colors and the dim opacity.
        layout: Whether a panel is drawn, which is what a dimmed part blends into.
    """
    from manim import ManimColor, interpolate_color

    colors = theme.colors
    backdrop = ManimColor(colors.surface if layout.panel else colors.background)

    def shown(color: str, dimmed: bool) -> ManimColor:
        full = ManimColor(color)
        return interpolate_color(backdrop, full, colors.dim_opacity) if dimmed else full

    animations: list[Any] = []
    for index, series_parts in enumerate(parts):
        dimmed = kept is not None and index != kept
        fill = shown(series_colors[index], dimmed)
        dot, name = legend[index]
        animations += [part.animate.set_fill(fill) for part in series_parts]
        animations += [
            dot.animate.set_fill(fill),
            name.animate.set_color(shown(colors.muted, dimmed)),
        ]
    return animations
