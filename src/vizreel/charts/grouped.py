"""Bars side by side, in groups."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from vizreel.charts._bars import (
    MAX_ROW_THICKNESS,
    MIN_ROW_THICKNESS_PX,
    by_bar_layout,
    category_label,
    plan_rows,
    series_emphasis,
    series_legend,
)
from vizreel.charts.base import (
    ChartType,
    check_reading_time,
    split_duration,
    staggered_progress,
)
from vizreel.charts.registry import register
from vizreel.errors import RenderError
from vizreel.format.numbers import format_number, shared_decimals
from vizreel.render.layout import LABEL_FILL, Box, px, stack_gap, stroke_width
from vizreel.render.scales import LinearScale, band_centers
from vizreel.spec.data import Table
from vizreel.spec.models import GroupedChart

if TYPE_CHECKING:
    from manim import Animation, Scene, VMobject

MIN_BAR_AREA_PX = 120
"""Least height, in pixels at 1080p, left for the tallest column."""
MIN_ROW_LENGTH = 0.4
"""Least share of the width left for the longest row after its value."""
GROUP_FILL = 0.8
"""Share of its slot a group spans; the rest is the space between groups."""
LABEL_PITCH = 1.25
"""Least thickness of a bar in rows, as a multiple of the height of its value label, so the
values of a group stand apart."""
SEPARATOR_PX = 2
"""Width, in pixels at 1080p, of the line in the background color between two bars of a
group."""

ValueText = Callable[[int, int, float], "VMobject"]
"""Builds the value label of series `s` in category `c` at an amount."""


@dataclass(frozen=True)
class GroupedGeometry:
    """Where the bars of a grouped bar chart go, for columns or rows.

    Attributes:
        labels: The category labels, in place.
        bar: Builds the bar of series `s` in category `c` grown by a share from 0 to 1, in a
            fill color.
        value: Builds the value label of series `s` in category `c` grown by a share, at the
            bar's end.
        axis: The line the bars grow from, or None.
    """

    labels: list["VMobject"]
    bar: Callable[[int, int, float, str], "VMobject"]
    value: Callable[[int, int, float], "VMobject"]
    axis: "VMobject | None"


def group_offsets(count: int, width: float) -> list[float]:
    """Return the centers of `count` bars side by side, relative to the center of their group.

    The bars are `width` wide together; the centers are in order.
    """
    bar = width / count
    return [(index + 0.5) * bar - width / 2 for index in range(count)]


@register
class GroupedChartType(ChartType):
    """Bars side by side in groups of two or three, one group per category.

    A legend under the title names the series by color, and every bar has its value. The
    groups grow one after another while their values count. At the highlight beat the
    highlighted series keeps its color and the others dim. Columns at 16:9 and 1:1, rows at
    9:16 or when the values do not fit side by side.
    """

    name = "grouped"
    model = GroupedChart
    template = """\
- id: revenue-by-region            # unique; lowercase letters, digits and hyphens
  type: grouped
  title: Northwind revenue by region
  categories: [North, South, East] # two to six groups
  series:                          # two or three bars in each group, in order
    - { name: "2022", values: [310, 240, 150] }
    - { name: "2023", values: [412, 298, 188] }
  number: { prefix: "$", suffix: "M" }
  # highlight: { series: "2023" }  # optional: the series that keeps its color at the end
  # layout: rows                   # optional: auto, columns or rows
  # subtitle: In millions of dollars   # optional
  # source: "Source: example data" # optional
  # duration: 6                    # optional: seconds, at least 2
"""

    @classmethod
    def from_table(cls, table: Table, chart: dict[str, Any]) -> dict[str, Any]:
        """Read the categories from the first column and a series from each other column.

        A series is named by its column's header, and gives one bar of every group.
        """
        if table.width < 2:
            table.require_width(2, "the categories and a series")
        rows = range(len(table.rows))
        return {
            "categories": [table.text(row, 0) for row in rows],
            "series": [
                {
                    "name": table.header[column],
                    "values": [table.number(row, column) for row in rows],
                }
                for column in range(1, table.width)
            ],
        }

    def build(self, scene: "Scene") -> None:
        """Add the chart to the scene and animate it."""
        from manim import (
            AnimationGroup,
            Create,
            ValueTracker,
            VGroup,
            linear,
        )

        from vizreel.render import elements
        from vizreel.render.numbers_text import NumberGlyphs

        chart = self.chart
        assert isinstance(chart, GroupedChart)
        theme, layout = self.theme, self.layout
        fonts, sizes, colors, motion = theme.fonts, theme.sizes, theme.colors, theme.motion
        ease = elements.easing(theme)
        content = layout.content
        series_count, category_count = len(chart.series), len(chart.categories)
        series_colors = colors.series[:series_count]
        values = [series.values for series in chart.series]

        header = elements.header(chart.title, chart.subtitle, theme, layout)
        source = elements.source_line(chart.source, theme, layout)
        legend = series_legend(
            [series.name for series in chart.series], series_colors, theme, content
        )
        area = Box(
            content.left,
            content.bottom,
            content.right,
            content.top - legend.height - stack_gap(sizes.label, sizes.label) * 2,
        )

        every_value = [value for row in values for value in row]
        places = iter(shared_decimals(every_value, chart.number))
        value_formats = [
            [chart.number.model_copy(update={"decimals": next(places)}) for _ in row]
            for row in values
        ]
        glyphs = NumberGlyphs(fonts.numbers, sizes.value, colors.text)

        def value_text(series: int, category: int, amount: float) -> "VMobject":
            return glyphs(
                format_number(
                    amount,
                    value_formats[series][category],
                    locale=self.locale,
                    unit_of=values[series][category],
                )
            )

        final_values = [
            [value_text(series, category, value) for category, value in enumerate(row)]
            for series, row in enumerate(values)
        ]

        def columns() -> GroupedGeometry:
            return self._columns(area, value_text, final_values)

        def rows() -> GroupedGeometry:
            return self._rows(area, value_text, final_values)

        def columns_or_rows() -> GroupedGeometry:
            try:
                return columns()
            except RenderError:
                return rows()

        geometry = by_bar_layout(
            chart.layout, layout, columns_or_rows if chart.layout == "auto" else columns, rows
        )

        intro = (motion.title_fade if len(header) else 0.0) + motion.structure
        phases = split_duration(
            chart.duration,
            intro=intro,
            highlight=motion.highlight if chart.highlight else 0.0,
            hold=motion.hold,
        )
        labels_appear = motion.title_fade if len(header) else 0.0
        check_reading_time(
            [(text, 0.0) for text in (chart.title, chart.subtitle, chart.source) if text]
            + [(text, labels_appear) for text in chart.categories]
            + [(series.name, labels_appear) for series in chart.series],
            chart.duration,
        )

        opening: list[Animation] = []
        if layout.panel:
            card = elements.panel(layout.panel_around(layout.inner), theme)
            opening.append(elements.appear(card, theme, run_time=motion.title_fade, rate_func=ease))
        titles = VGroup(header, *([source] if source else []))
        if len(titles):
            opening.append(
                elements.appear(titles, theme, run_time=motion.title_fade, rate_func=ease)
            )
        if len(header):
            scene.play(AnimationGroup(*opening), run_time=motion.title_fade, cue="title")
            opening = []
        structure = [
            *opening,
            *(
                [Create(geometry.axis, run_time=motion.structure, rate_func=ease)]
                if geometry.axis
                else []
            ),
            elements.appear(
                VGroup(legend, *geometry.labels), theme, run_time=motion.structure, rate_func=ease
            ),
        ]
        scene.play(AnimationGroup(*structure), run_time=motion.structure, cue="structure")

        progress = ValueTracker(0.0)

        def grown(category: int) -> float:
            local = staggered_progress(
                progress.get_value(),
                category,
                category_count,
                stagger=motion.stagger,
                total=phases.main,
            )
            return ease(local)

        def growing_bar(series: int, category: int) -> "VMobject":
            color = series_colors[series]
            return elements.redrawn_shapes(
                lambda: geometry.bar(series, category, grown(category), color)
            )

        def counting_value(series: int, category: int) -> "VMobject":
            return elements.redrawn_shapes(
                lambda: geometry.value(series, category, grown(category))
            )

        pairs = [
            (series, category)
            for category in range(category_count)
            for series in range(series_count)
        ]
        growing = [growing_bar(series, category) for series, category in pairs]
        counting = [counting_value(series, category) for series, category in pairs]
        scene.add(*growing, *counting)
        scene.play(
            progress.animate.set_value(1.0), run_time=phases.main, rate_func=linear, cue="reveal"
        )

        final_bars = [
            [
                geometry.bar(series, category, 1.0, series_colors[series])
                for category in range(category_count)
            ]
            for series in range(series_count)
        ]
        for series, category in pairs:
            final_values[series][category].move_to(
                geometry.value(series, category, 1.0).get_center()
            )
        scene.remove(*growing, *counting)
        scene.add(
            *(bar for bars in final_bars for bar in bars),
            *(label for labels in final_values for label in labels),
        )
        self._final = (final_bars, legend, series_colors)

        if chart.highlight:
            scene.play(
                *self.emphasis(chart.highlight.series),
                run_time=phases.highlight,
                rate_func=ease,
                cue="highlight",
            )
        scene.wait(phases.hold)

    def emphasis(self, item: Any) -> list[Any]:
        """Keep the series named `item` in its color and dim the others, in the legend too."""
        assert isinstance(self.chart, GroupedChart)
        final_bars, legend, series_colors = self._final
        names = [series.name for series in self.chart.series]
        return series_emphasis(
            names.index(item), final_bars, legend, series_colors, self.theme, self.layout
        )

    def _separator(self) -> tuple[str, float]:
        """The color and width of the line drawn between two bars of a group."""
        colors = self.theme.colors
        backdrop = colors.surface if self.layout.panel else colors.background
        return backdrop, stroke_width(SEPARATOR_PX)

    def _columns(
        self, area: Box, value_text: ValueText, final_values: list[list["VMobject"]]
    ) -> GroupedGeometry:
        """Groups of columns on a baseline, the labels under it, each value above its bar."""
        from manim import Line, Rectangle, VGroup

        assert isinstance(self.chart, GroupedChart)
        sizes, colors = self.theme.sizes, self.theme.colors
        categories = self.chart.categories
        values = [series.values for series in self.chart.series]
        count, series_count = len(categories), len(values)
        slot = area.width / count
        centers = band_centers(count, area.left, area.right)
        group_width = slot * GROUP_FILL
        bar_width = group_width / series_count
        offsets = group_offsets(series_count, group_width)
        label_gap = stack_gap(sizes.label, sizes.label)

        if any(label.width > bar_width * LABEL_FILL for row in final_values for label in row):
            raise RenderError(
                "the values are too wide to sit side by side; use compact numbers, fewer "
                "categories or layout: rows"
            )
        label_blocks = [
            category_label(
                text,
                self.theme,
                slot * LABEL_FILL,
                "center",
                f'category "{text}" is too long for {count} groups; shorten it or use layout: rows',
            )
            for text in categories
        ]
        labels_height = max(block.height for block in label_blocks)
        baseline = area.bottom + labels_height + label_gap
        for block, center in zip(label_blocks, centers, strict=True):
            block.move_top_to(baseline - label_gap)
            block.mobject.set_x(center)

        value_gap = stack_gap(sizes.value, sizes.value)
        tallest_label = max(label.height for row in final_values for label in row)
        top = area.top - tallest_label - value_gap
        if top - baseline < px(MIN_BAR_AREA_PX):
            raise RenderError("not enough room for the bars; shorten the title or the labels")
        scale = LinearScale((0, max(max(row) for row in values) or 1), (baseline, top))
        separator_color, separator_width = self._separator()

        def bar_top(series: int, category: int, grown: float) -> float:
            return baseline + (scale(values[series][category]) - baseline) * grown

        def bar(series: int, category: int, grown: float, fill: str) -> "VMobject":
            height = bar_top(series, category, grown) - baseline
            if height <= 0:
                return VGroup()
            rectangle = Rectangle(
                width=bar_width,
                height=height,
                fill_color=fill,
                fill_opacity=1,
                stroke_color=separator_color,
                stroke_width=separator_width,
            )
            x = centers[category] + offsets[series]
            return rectangle.move_to((x, baseline + height / 2, 0.0))

        def value(series: int, category: int, grown: float) -> "VMobject":
            if grown <= 0:
                return VGroup()
            label = value_text(series, category, values[series][category] * grown)
            x = centers[category] + offsets[series]
            y = bar_top(series, category, grown) + value_gap + label.height / 2
            return label.move_to((x, y, 0.0))

        base_line = Line(
            (area.left, baseline, 0.0),
            (area.right, baseline, 0.0),
            color=colors.grid,
            stroke_width=stroke_width(sizes.grid_line),
        )
        return GroupedGeometry([block.mobject for block in label_blocks], bar, value, base_line)

    def _rows(
        self, area: Box, value_text: ValueText, final_values: list[list["VMobject"]]
    ) -> GroupedGeometry:
        """Groups of rows growing to the right, each under its label, values after the bars."""
        from manim import LEFT, Rectangle, VGroup

        assert isinstance(self.chart, GroupedChart)
        sizes = self.theme.sizes
        categories = self.chart.categories
        values = [series.values for series in self.chart.series]
        series_count = len(values)
        label_gap = stack_gap(sizes.label, sizes.label) / 2
        value_gap = stack_gap(sizes.value, sizes.value)

        label_blocks = [
            category_label(
                text, self.theme, area.width, "left", f'category "{text}" is too long; shorten it'
            )
            for text in categories
        ]
        tallest_label = max(label.height for row in final_values for label in row)
        thinnest = max(px(MIN_ROW_THICKNESS_PX), tallest_label * LABEL_PITCH)
        thickest = max(px(sizes.value) * MAX_ROW_THICKNESS, thinnest)
        rows = plan_rows(
            len(categories),
            area.top,
            area.bottom,
            max(block.height for block in label_blocks),
            label_gap,
            (thinnest * series_count, thickest * series_count),
            GROUP_FILL,
        )
        for block, row in zip(label_blocks, rows, strict=True):
            block.move_top_to(row.label_top)
            block.mobject.align_to((area.left, 0.0, 0.0), LEFT)

        widest_label = max(label.width for row in final_values for label in row)
        longest = area.width - value_gap - widest_label
        if longest < area.width * MIN_ROW_LENGTH:
            raise RenderError("the values are too wide for the bars; use compact numbers")
        scale = LinearScale(
            (0, max(max(row) for row in values) or 1), (area.left, area.left + longest)
        )
        separator_color, separator_width = self._separator()

        def center(series: int, category: int) -> float:
            row = rows[category]
            return row.bar_center - group_offsets(series_count, row.thickness)[series]

        def length(series: int, category: int, grown: float) -> float:
            return (scale(values[series][category]) - area.left) * grown

        def bar(series: int, category: int, grown: float, fill: str) -> "VMobject":
            width = length(series, category, grown)
            if width <= 0:
                return VGroup()
            rectangle = Rectangle(
                width=width,
                height=rows[category].thickness / series_count,
                fill_color=fill,
                fill_opacity=1,
                stroke_color=separator_color,
                stroke_width=separator_width,
            )
            return rectangle.move_to((area.left + width / 2, center(series, category), 0.0))

        def value(series: int, category: int, grown: float) -> "VMobject":
            if grown <= 0:
                return VGroup()
            label = value_text(series, category, values[series][category] * grown)
            start = area.left + length(series, category, grown) + value_gap
            return label.move_to((start + label.width / 2, center(series, category), 0.0))

        return GroupedGeometry([block.mobject for block in label_blocks], bar, value, None)
