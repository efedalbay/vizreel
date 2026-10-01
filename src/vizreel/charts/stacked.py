"""Bars made of parts."""

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
    sequential_progress,
    split_duration,
    staggered_progress,
)
from vizreel.charts.registry import register
from vizreel.errors import RenderError
from vizreel.format.numbers import format_number, shared_decimals
from vizreel.render.layout import BAR_FILL, LABEL_FILL, Box, px, stack_gap, stroke_width
from vizreel.render.scales import LinearScale, band_centers
from vizreel.spec.data import Table
from vizreel.spec.models import StackedChart

if TYPE_CHECKING:
    from manim import Animation, Scene, VMobject

MIN_BAR_AREA_PX = 120
"""Least height, in pixels at 1080p, left for the tallest column."""
MIN_ROW_LENGTH = 0.4
"""Least share of the width left for the longest row after its total."""
SEPARATOR_PX = 2
"""Width, in pixels at 1080p, of the line in the background color between two parts."""


def stack_bounds(chart: StackedChart) -> list[list[tuple[float, float]]]:
    """Return where each part of each bar starts and ends, as values.

    Item `[s][c]` is the part of series `s` in category `c`: it starts where the parts below it
    end, so the parts of a bar stack from zero to the bar's total.
    """
    below = [0.0] * len(chart.categories)
    bounds = []
    for series in chart.series:
        bounds.append([(low, low + value) for low, value in zip(below, series.values, strict=True)])
        below = [low + value for low, value in zip(below, series.values, strict=True)]
    return bounds


@dataclass(frozen=True)
class StackedGeometry:
    """Where the parts of a stacked bar chart go, for columns or rows.

    Attributes:
        labels: The category labels, in place.
        part: Builds the part of series `s` in category `c`, from its start to a value, in a
            fill color.
        total: Builds the total label of category `c` for a total, at the end of that total.
        axis: The line the bars grow from, or None.
    """

    labels: list["VMobject"]
    part: Callable[[int, int, float, str], "VMobject"]
    total: Callable[[int, float], "VMobject"]
    axis: "VMobject | None"


@register
class StackedChartType(ChartType):
    """Bars made of two or three parts, one bar per category, with each bar's total.

    A legend under the title names the parts by color. The parts grow one series at a time:
    the bottom part in every bar, then the next part on top of it, while each total counts
    up. At the highlight beat the highlighted series keeps its color and the others dim.
    Columns at 16:9 and rows at 9:16, as for bar charts.
    """

    name = "stacked"
    model = StackedChart
    template = """\
- id: revenue-mix                  # unique; lowercase letters, digits and hyphens
  type: stacked
  title: Northwind revenue by product
  categories: ["2021", "2022", "2023"]   # two to eight bars; quote years
  series:                          # two or three parts of each bar, from the bottom up
    - { name: Cloud, values: [1.2, 2.4, 3.9] }
    - { name: Devices, values: [3.1, 2.9, 3.2] }
  number: { prefix: "$", suffix: "B" }
  # highlight: { series: Cloud }   # optional: the series that keeps its color at the end
  # layout: rows                   # optional: auto, columns or rows
  # subtitle: In billions of dollars   # optional
  # source: "Source: example data" # optional
  # duration: 6                    # optional: seconds, at least 2
"""

    @classmethod
    def from_table(cls, table: Table, chart: dict[str, Any]) -> dict[str, Any]:
        """Read the categories from the first column and a series from each other column.

        A series is named by its column's header, and gives one part of every bar.
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
        assert isinstance(chart, StackedChart)
        theme, layout = self.theme, self.layout
        fonts, sizes, colors, motion = theme.fonts, theme.sizes, theme.colors, theme.motion
        ease = elements.easing(theme)
        content = layout.content
        series_count, category_count = len(chart.series), len(chart.categories)
        series_colors = colors.series[:series_count]
        bounds = stack_bounds(chart)
        totals = chart.totals()

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

        total_formats = [
            chart.number.model_copy(update={"decimals": places})
            for places in shared_decimals(totals, chart.number)
        ]
        glyphs = NumberGlyphs(fonts.numbers, sizes.value, colors.text)

        def total_text(category: int, amount: float) -> "VMobject":
            total = totals[category]
            return glyphs(
                format_number(amount, total_formats[category], locale=self.locale, unit_of=total)
            )

        final_totals = [total_text(index, total) for index, total in enumerate(totals)]
        geometry = by_bar_layout(
            chart.layout,
            layout,
            lambda: self._columns(area, bounds, totals, total_text, final_totals),
            lambda: self._rows(area, bounds, totals, total_text, final_totals),
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
            scene.play(AnimationGroup(*opening), run_time=motion.title_fade)
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
        scene.play(AnimationGroup(*structure), run_time=motion.structure)

        progress = ValueTracker(0.0)
        series_seconds = phases.main / series_count

        def grown(series: int, category: int) -> float:
            local = sequential_progress(progress.get_value(), series, series_count)
            return ease(
                staggered_progress(
                    local, category, category_count, stagger=motion.stagger, total=series_seconds
                )
            )

        def reached(series: int, category: int) -> float:
            low, high = bounds[series][category]
            return low + (high - low) * grown(series, category)

        def growing_part(series: int, category: int) -> "VMobject":
            color = series_colors[series]
            return elements.redrawn_shapes(
                lambda: geometry.part(series, category, reached(series, category), color)
            )

        def counting_total(category: int) -> "VMobject":
            def build() -> "VMobject":
                amount = sum(
                    reached(series, category) - bounds[series][category][0]
                    for series in range(series_count)
                )
                return geometry.total(category, amount) if amount > 0 else VGroup()

            return elements.redrawn_shapes(build)

        growing = [
            growing_part(series, category)
            for series in range(series_count)
            for category in range(category_count)
        ]
        counting = [counting_total(category) for category in range(category_count)]
        scene.add(*growing, *counting)
        scene.play(progress.animate.set_value(1.0), run_time=phases.main, rate_func=linear)

        final_parts = [
            [
                geometry.part(series, category, bounds[series][category][1], series_colors[series])
                for category in range(category_count)
            ]
            for series in range(series_count)
        ]
        for category, total_mobject in enumerate(final_totals):
            total_mobject.move_to(geometry.total(category, totals[category]).get_center())
        scene.remove(*growing, *counting)
        scene.add(*(part for parts in final_parts for part in parts), *final_totals)
        self._final = (final_parts, legend, series_colors)

        if chart.highlight:
            scene.play(
                *self.emphasis(chart.highlight.series),
                run_time=phases.highlight,
                rate_func=ease,
            )
        scene.wait(phases.hold)

    def emphasis(self, item: Any) -> list[Any]:
        """Keep the series named `item` in its color and dim the others, in the legend too."""
        assert isinstance(self.chart, StackedChart)
        final_parts, legend, series_colors = self._final
        names = [series.name for series in self.chart.series]
        return series_emphasis(
            names.index(item), final_parts, legend, series_colors, self.theme, self.layout
        )

    def _separator(self) -> tuple[str, float]:
        """The color and width of the line drawn between two parts of a bar."""
        colors = self.theme.colors
        backdrop = colors.surface if self.layout.panel else colors.background
        return backdrop, stroke_width(SEPARATOR_PX)

    def _columns(
        self,
        area: Box,
        bounds: list[list[tuple[float, float]]],
        totals: list[float],
        total_text: Callable[[int, float], "VMobject"],
        final_totals: list["VMobject"],
    ) -> StackedGeometry:
        """Columns on a baseline, the labels under it and each total above its column."""
        from manim import Line, Rectangle, VGroup

        assert isinstance(self.chart, StackedChart)
        sizes, colors = self.theme.sizes, self.theme.colors
        categories = self.chart.categories
        count = len(categories)
        slot = area.width / count
        centers = band_centers(count, area.left, area.right)
        label_gap = stack_gap(sizes.label, sizes.label)

        label_blocks = [
            category_label(
                text,
                self.theme,
                slot * LABEL_FILL,
                "center",
                f'category "{text}" is too long for {count} bars; shorten it or use layout: rows',
            )
            for text in categories
        ]
        labels_height = max(block.height for block in label_blocks)
        baseline = area.bottom + labels_height + label_gap
        for block, center in zip(label_blocks, centers, strict=True):
            block.move_top_to(baseline - label_gap)
            block.mobject.set_x(center)

        for total_mobject, text in zip(final_totals, categories, strict=True):
            if total_mobject.width > slot * LABEL_FILL:
                raise RenderError(
                    f'the total of "{text}" is too wide for {count} bars; '
                    "use compact numbers or fewer categories"
                )
        value_gap = stack_gap(sizes.value, sizes.value)
        top = area.top - max(label.height for label in final_totals) - value_gap
        if top - baseline < px(MIN_BAR_AREA_PX):
            raise RenderError("not enough room for the bars; shorten the title or the labels")
        scale = LinearScale((0, max(totals) or 1), (baseline, top))
        bar_width = slot * BAR_FILL
        separator_color, separator_width = self._separator()

        def part(series: int, category: int, reached: float, fill: str) -> "VMobject":
            start, end = scale(bounds[series][category][0]), scale(reached)
            if end - start <= 0:
                return VGroup()
            rectangle = Rectangle(
                width=bar_width,
                height=end - start,
                fill_color=fill,
                fill_opacity=1,
                stroke_color=separator_color,
                stroke_width=separator_width,
            )
            return rectangle.move_to((centers[category], (start + end) / 2, 0.0))

        def total(category: int, amount: float) -> "VMobject":
            label = total_text(category, amount)
            end = scale(amount)
            return label.move_to((centers[category], end + value_gap + label.height / 2, 0.0))

        base_line = Line(
            (area.left, baseline, 0.0),
            (area.right, baseline, 0.0),
            color=colors.grid,
            stroke_width=stroke_width(sizes.grid_line),
        )
        return StackedGeometry([block.mobject for block in label_blocks], part, total, base_line)

    def _rows(
        self,
        area: Box,
        bounds: list[list[tuple[float, float]]],
        totals: list[float],
        total_text: Callable[[int, float], "VMobject"],
        final_totals: list["VMobject"],
    ) -> StackedGeometry:
        """Rows growing to the right, each under its label, each total after its bar."""
        from manim import LEFT, Rectangle, VGroup

        assert isinstance(self.chart, StackedChart)
        sizes = self.theme.sizes
        categories = self.chart.categories
        label_gap = stack_gap(sizes.label, sizes.label) / 2
        value_gap = stack_gap(sizes.value, sizes.value)

        label_blocks = [
            category_label(
                text, self.theme, area.width, "left", f'category "{text}" is too long; shorten it'
            )
            for text in categories
        ]
        rows = plan_rows(
            len(categories),
            area.top,
            area.bottom,
            max(block.height for block in label_blocks),
            label_gap,
            (px(MIN_ROW_THICKNESS_PX), px(sizes.value) * MAX_ROW_THICKNESS),
        )
        for block, row in zip(label_blocks, rows, strict=True):
            block.move_top_to(row.label_top)
            block.mobject.align_to((area.left, 0.0, 0.0), LEFT)

        longest = area.width - value_gap - max(label.width for label in final_totals)
        if longest < area.width * MIN_ROW_LENGTH:
            raise RenderError("the totals are too wide for the bars; use compact numbers")
        scale = LinearScale((0, max(totals) or 1), (area.left, area.left + longest))
        separator_color, separator_width = self._separator()

        def part(series: int, category: int, reached: float, fill: str) -> "VMobject":
            start, end = scale(bounds[series][category][0]), scale(reached)
            if end - start <= 0:
                return VGroup()
            rectangle = Rectangle(
                width=end - start,
                height=rows[category].thickness,
                fill_color=fill,
                fill_opacity=1,
                stroke_color=separator_color,
                stroke_width=separator_width,
            )
            return rectangle.move_to(((start + end) / 2, rows[category].bar_center, 0.0))

        def total(category: int, amount: float) -> "VMobject":
            label = total_text(category, amount)
            start = scale(amount) + value_gap
            return label.move_to((start + label.width / 2, rows[category].bar_center, 0.0))

        return StackedGeometry([block.mobject for block in label_blocks], part, total, None)
