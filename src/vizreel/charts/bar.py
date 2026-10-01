"""Compare categories."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from vizreel.charts._bars import (
    MAX_ROW_THICKNESS,
    MIN_ROW_THICKNESS_PX,
    BarGeometry,
    by_bar_layout,
    category_label,
    plan_rows,
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
from vizreel.render.layout import BAR_FILL, LABEL_FILL, px, stack_gap, stroke_width
from vizreel.render.scales import LinearScale, band_centers
from vizreel.spec.data import Table
from vizreel.spec.models import Bar, BarChart

if TYPE_CHECKING:
    from manim import Animation, Scene, VMobject


MIN_BAR_AREA_PX = 120
"""Least height, in pixels at 1080p, left for the tallest column."""
MIN_ROW_LENGTH = 0.4
"""Least share of the content width left for the longest row after its value label."""


def sorted_bars(chart: BarChart) -> list[Bar]:
    """Return the bars in display order."""
    if chart.sort == "asc":
        return sorted(chart.bars, key=lambda bar: bar.value)
    if chart.sort == "desc":
        return sorted(chart.bars, key=lambda bar: bar.value, reverse=True)
    return list(chart.bars)


@register
class BarChartType(ChartType):
    """One bar per category, with a value label on every bar and no value axis.

    Columns grow up from a baseline, with the labels below it. Rows grow to the right, each
    under its label, which leaves labels the whole width; vertical frames use rows. The title
    fades in, the labels appear, then the bars grow one after another while their values
    count. At the highlight beat the highlighted bar turns to the highlight color and the
    others to muted.
    """

    name = "bar"
    model = BarChart
    template = """\
- id: regions                      # unique; lowercase letters, digits and hyphens
  type: bar
  title: Northwind revenue by region
  bars:                            # two to eight bars; values zero or more
    - { label: North, value: 412000000 }
    - { label: South, value: 298000000 }
    - { label: East, value: 187500000 }
  number: { prefix: "$", compact: true }
  highlight: { label: East }       # optional: the bar that carries the message
  # sort: desc                     # optional: none, asc or desc
  # layout: rows                   # optional: auto, columns or rows; rows fit long labels
  # subtitle: Fiscal year 2022     # optional
  # source: "Source: example data" # optional
  # duration: 5                    # optional: seconds, at least 2
"""

    @classmethod
    def from_table(cls, table: Table, chart: dict[str, Any]) -> dict[str, Any]:
        """Read one bar per row: its label, then its value."""
        table.require_width(2, "a label and a value")
        return {
            "bars": [
                {"label": table.text(row, 0), "value": table.number(row, 1)}
                for row in range(len(table.rows))
            ]
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
        assert isinstance(chart, BarChart)
        theme, layout = self.theme, self.layout
        fonts, sizes, colors, motion = theme.fonts, theme.sizes, theme.colors, theme.motion
        ease = elements.easing(theme)
        bars = sorted_bars(chart)
        count = len(bars)

        header = elements.header(chart.title, chart.subtitle, theme, layout)
        source = elements.source_line(chart.source, theme, layout)
        value_formats = [
            chart.number.model_copy(update={"decimals": places})
            for places in shared_decimals([bar.value for bar in bars], chart.number)
        ]
        glyphs = NumberGlyphs(fonts.numbers, sizes.value, colors.text)

        def value_text(index: int, grown: float) -> "VMobject":
            return glyphs(
                format_number(
                    bars[index].value * grown,
                    value_formats[index],
                    locale=self.locale,
                    unit_of=bars[index].value,
                )
            )

        final_values = [value_text(index, 1.0) for index in range(count)]
        geometry = by_bar_layout(
            chart.layout,
            layout,
            lambda: self._columns(bars, value_text, final_values),
            lambda: self._rows(bars, value_text, final_values),
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
            + [(bar.label, labels_appear) for bar in bars],
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
                VGroup(*geometry.labels), theme, run_time=motion.structure, rate_func=ease
            ),
        ]
        scene.play(AnimationGroup(*structure), run_time=motion.structure)

        progress = ValueTracker(0.0)

        def grown(index: int) -> float:
            local = staggered_progress(
                progress.get_value(), index, count, stagger=motion.stagger, total=phases.main
            )
            return ease(local)

        def growing_bar(index: int) -> "VMobject":
            return elements.redrawn_shapes(lambda: geometry.bar(index, grown(index), colors.accent))

        def counting_value(index: int) -> "VMobject":
            return elements.redrawn_shapes(lambda: geometry.value(index, grown(index)))

        growing = [growing_bar(index) for index in range(count)]
        counting = [counting_value(index) for index in range(count)]
        scene.add(*growing, *counting)
        scene.play(progress.animate.set_value(1.0), run_time=phases.main, rate_func=linear)

        final_bars = [geometry.bar(index, 1.0, colors.accent) for index in range(count)]
        for index, value_mobject in enumerate(final_values):
            value_mobject.move_to(geometry.value(index, 1.0).get_center())
        scene.remove(*growing, *counting)
        scene.add(*final_bars, *final_values)
        self._final = list(zip(final_bars, bars, strict=True))

        if chart.highlight:
            scene.play(
                *self.emphasis(chart.highlight.label), run_time=phases.highlight, rate_func=ease
            )
        scene.wait(phases.hold)

    def emphasis(self, item: Any) -> list[Any]:
        """Turn the bar with the label `item` to the highlight color and the others to muted."""
        colors = self.theme.colors
        return [
            bar_mobject.animate.set_fill(colors.highlight, opacity=1)
            if bar.label == item
            else bar_mobject.animate.set_fill(colors.muted, opacity=colors.dim_opacity)
            for bar_mobject, bar in self._final
        ]

    def _columns(
        self,
        bars: list[Bar],
        value_text: Callable[[int, float], "VMobject"],
        final_values: list["VMobject"],
    ) -> BarGeometry:
        """Columns growing up from a baseline, with the labels under the baseline."""
        from manim import Line, Rectangle, VGroup

        sizes, colors = self.theme.sizes, self.theme.colors
        content = self.layout.content
        count = len(bars)
        slot = content.width / count
        centers = band_centers(count, content.left, content.right)
        label_gap = stack_gap(sizes.label, sizes.label)

        label_blocks = [
            category_label(
                bar.label,
                self.theme,
                slot * LABEL_FILL,
                "center",
                f'bar label "{bar.label}" is too long for {count} bars; shorten it '
                "or use layout: rows",
            )
            for bar in bars
        ]
        labels_height = max(block.height for block in label_blocks)
        baseline = content.bottom + labels_height + label_gap
        for block, center in zip(label_blocks, centers, strict=True):
            block.move_top_to(baseline - label_gap)
            block.mobject.set_x(center)

        for final_label, bar in zip(final_values, bars, strict=True):
            if final_label.width > slot * LABEL_FILL:
                raise RenderError(
                    f'the value of "{bar.label}" is too wide for {count} bars; '
                    "use compact numbers or fewer bars"
                )
        value_gap = stack_gap(sizes.value, sizes.value)
        top = content.top - max(label.height for label in final_values) - value_gap
        if top - baseline < px(MIN_BAR_AREA_PX):
            raise RenderError("not enough room for the bars; shorten the title or the labels")
        scale = LinearScale((0, max(bar.value for bar in bars) or 1), (baseline, top))
        bar_width = slot * BAR_FILL

        def bar_rectangle(index: int, grown: float, fill: str) -> "VMobject":
            height = (scale(bars[index].value) - baseline) * grown
            if height <= 0:
                return VGroup()
            rectangle = Rectangle(
                width=bar_width, height=height, stroke_width=0, fill_color=fill, fill_opacity=1
            )
            return rectangle.move_to((centers[index], baseline + height / 2, 0.0))

        def value_at(index: int, grown: float) -> "VMobject":
            if grown <= 0:
                return VGroup()
            label = value_text(index, grown)
            bar_top = baseline + (scale(bars[index].value) - baseline) * grown
            return label.move_to((centers[index], bar_top + value_gap + label.height / 2, 0.0))

        base_line = Line(
            (content.left, baseline, 0.0),
            (content.right, baseline, 0.0),
            color=colors.grid,
            stroke_width=stroke_width(sizes.grid_line),
        )
        return BarGeometry(
            [block.mobject for block in label_blocks], bar_rectangle, value_at, base_line
        )

    def _rows(
        self,
        bars: list[Bar],
        value_text: Callable[[int, float], "VMobject"],
        final_values: list["VMobject"],
    ) -> BarGeometry:
        """Rows growing to the right, each bar under its label, values at the bar ends."""
        from manim import LEFT, Rectangle, VGroup

        sizes = self.theme.sizes
        content = self.layout.content
        count = len(bars)
        label_gap = stack_gap(sizes.label, sizes.label) / 2
        value_gap = stack_gap(sizes.value, sizes.value)

        label_blocks = [
            category_label(
                bar.label,
                self.theme,
                content.width,
                "left",
                f'bar label "{bar.label}" is too long; shorten it',
            )
            for bar in bars
        ]
        rows = plan_rows(
            count,
            content.top,
            content.bottom,
            max(block.height for block in label_blocks),
            label_gap,
            (px(MIN_ROW_THICKNESS_PX), px(sizes.value) * MAX_ROW_THICKNESS),
        )
        for block, row in zip(label_blocks, rows, strict=True):
            block.move_top_to(row.label_top)
            block.mobject.align_to((content.left, 0.0, 0.0), LEFT)

        longest = content.width - value_gap - max(label.width for label in final_values)
        if longest < content.width * MIN_ROW_LENGTH:
            raise RenderError("the values are too wide for the bars; use compact numbers")
        scale = LinearScale(
            (0, max(bar.value for bar in bars) or 1), (content.left, content.left + longest)
        )

        def length(index: int, grown: float) -> float:
            return (scale(bars[index].value) - content.left) * grown

        def bar_rectangle(index: int, grown: float, fill: str) -> "VMobject":
            width = length(index, grown)
            if width <= 0:
                return VGroup()
            rectangle = Rectangle(
                width=width,
                height=rows[index].thickness,
                stroke_width=0,
                fill_color=fill,
                fill_opacity=1,
            )
            return rectangle.move_to((content.left + width / 2, rows[index].bar_center, 0.0))

        def value_at(index: int, grown: float) -> "VMobject":
            if grown <= 0:
                return VGroup()
            label = value_text(index, grown)
            start = content.left + length(index, grown) + value_gap
            return label.move_to((start + label.width / 2, rows[index].bar_center, 0.0))

        return BarGeometry([block.mobject for block in label_blocks], bar_rectangle, value_at, None)
