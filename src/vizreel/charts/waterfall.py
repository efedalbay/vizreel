"""How a starting value becomes a total."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from vizreel.charts._bars import (
    MAX_ROW_THICKNESS,
    MIN_ROW_THICKNESS_PX,
    BarGeometry,
    category_label,
    plan_rows,
    uses_rows,
)
from vizreel.charts.base import (
    ChartType,
    check_reading_time,
    sequential_progress,
    split_duration,
)
from vizreel.charts.registry import register
from vizreel.errors import RenderError
from vizreel.format.numbers import format_change, format_number, shared_decimals
from vizreel.render.layout import BAR_FILL, LABEL_FILL, px, stack_gap, stroke_width
from vizreel.render.scales import LinearScale, band_centers
from vizreel.spec.models import WaterfallChart

if TYPE_CHECKING:
    from manim import Animation, Scene, VMobject

MIN_BAR_AREA_PX = 120
"""Least height, in pixels at 1080p, left for the tallest column."""
MIN_ROW_LENGTH = 0.4
"""Least share of the content width left for the longest row after its value label."""

BarKind = Literal["total", "up", "down"]
Connector = Callable[[int], "VMobject"]
"""Builds the line from the end of bar index to the start of the next one."""


@dataclass(frozen=True)
class WaterfallBar:
    """One bar of a waterfall, as the values it spans.

    Attributes:
        label: The bar's label.
        low: The value the bar grows from: zero for a total, the running total before a step.
        high: The value it grows to: the total, or the running total after the step.
        kind: A total, an increase or a decrease.
    """

    label: str
    low: float
    high: float
    kind: BarKind

    @property
    def amount(self) -> float:
        """The value the bar shows: a total, or a signed change."""
        return self.high - self.low

    @property
    def top(self) -> float:
        """The higher of the two ends."""
        return max(self.low, self.high)


def waterfall_bars(chart: WaterfallChart) -> list[WaterfallBar]:
    """Return the start, each step and the total as bars, in order."""
    bars = [WaterfallBar(chart.start.label, 0.0, chart.start.value, "total")]
    total = chart.start.value
    for step in chart.steps:
        kind: BarKind = "up" if step.value >= 0 else "down"
        bars.append(WaterfallBar(step.label, total, total + step.value, kind))
        total += step.value
    bars.append(WaterfallBar(chart.end.label, 0.0, total, "total"))
    return bars


@register
class WaterfallChartType(ChartType):
    """A starting value, the changes that add to it or take from it, and the total.

    The start grows from zero; each step then grows from where the previous one ended, up in
    the positive color or down in the negative color, with a thin line joining them; the
    total grows last. At the highlight beat the highlighted bar, the total unless another is
    named, turns to the highlight color and the others to muted. Columns at 16:9 and rows at
    9:16, as for bar charts.
    """

    name = "waterfall"
    model = WaterfallChart
    template = """\
- id: profit                       # unique; lowercase letters, digits and hyphens
  type: waterfall
  title: How Northwind's revenue became profit
  start: { label: Revenue, value: 12000000 }
  steps:                           # one to six changes; negative takes away
    - { label: Salaries, value: -5000000 }
    - { label: Marketing, value: -2000000 }
    - { label: Other income, value: 500000 }
  end: { label: Profit }           # optional: the total's label, "Total" by default
  number: { prefix: "$", compact: true }
  # highlight: { label: Marketing } # optional: the bar to emphasize; the total by default
  # layout: rows                   # optional: auto, columns or rows
  # subtitle: Fiscal year 2022     # optional
  # source: "Source: example data" # optional
  # duration: 6                    # optional: seconds, at least 2
"""

    def build(self, scene: "Scene") -> None:
        """Add the chart to the scene and animate it."""
        from manim import (
            AnimationGroup,
            Create,
            FadeIn,
            ManimColor,
            ValueTracker,
            VGroup,
            always_redraw,
            interpolate_color,
            linear,
        )

        from vizreel.render import elements
        from vizreel.render.numbers_text import NumberGlyphs

        chart = self.chart
        assert isinstance(chart, WaterfallChart)
        theme, layout = self.theme, self.layout
        fonts, sizes, colors, motion = theme.fonts, theme.sizes, theme.colors, theme.motion
        ease = elements.easing(theme)
        bars = waterfall_bars(chart)
        count = len(bars)

        header = elements.header(chart.title, chart.subtitle, theme, layout)
        source = elements.source_line(chart.source, theme, layout)
        value_formats = [
            chart.number.model_copy(update={"decimals": places})
            for places in shared_decimals([abs(bar.amount) for bar in bars], chart.number)
        ]
        glyphs = NumberGlyphs(fonts.numbers, sizes.value, colors.text)

        def value_text(index: int, grown: float) -> "VMobject":
            bar, value_format = bars[index], value_formats[index]
            if bar.kind == "total":
                return glyphs(format_number(bar.amount * grown, value_format))
            places = value_format.decimals
            return glyphs(format_change(bar.amount * grown, "absolute", value_format, places))

        final_values = [value_text(index, 1.0) for index in range(count)]
        if uses_rows(chart.layout, layout.vertical):
            geometry, connector = self._rows(bars, value_text, final_values)
        else:
            geometry, connector = self._columns(bars, value_text, final_values)

        intro = (motion.title_fade if len(header) else 0.0) + motion.structure
        phases = split_duration(
            chart.duration, intro=intro, highlight=motion.highlight, hold=motion.hold
        )
        labels_appear = motion.title_fade if len(header) else 0.0
        check_reading_time(
            [(text, 0.0) for text in (chart.title, chart.subtitle, chart.source) if text]
            + [(label, labels_appear) for label in chart.labels],
            chart.duration,
        )

        opening: list[Animation] = []
        if layout.panel:
            card = elements.panel(layout.panel_around(layout.inner), theme)
            opening.append(FadeIn(card, run_time=motion.title_fade, rate_func=ease))
        titles = VGroup(header, *([source] if source else []))
        if len(titles):
            opening.append(FadeIn(titles, run_time=motion.title_fade, rate_func=ease))
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
            FadeIn(VGroup(*geometry.labels), run_time=motion.structure, rate_func=ease),
        ]
        scene.play(AnimationGroup(*structure), run_time=motion.structure)

        fills = {"total": colors.accent, "up": colors.positive, "down": colors.negative}
        progress = ValueTracker(0.0)

        def grown(index: int) -> float:
            return ease(sequential_progress(progress.get_value(), index, count))

        def growing_bar(index: int) -> "VMobject":
            fill = fills[bars[index].kind]
            return always_redraw(lambda: geometry.bar(index, grown(index), fill))

        def counting_value(index: int) -> "VMobject":
            return always_redraw(lambda: geometry.value(index, grown(index)))

        def connectors_now() -> "VMobject":
            return VGroup(
                *(
                    connector(index)
                    for index in range(count - 1)
                    if connector is not None
                    and sequential_progress(progress.get_value(), index + 1, count) > 0
                )
            )

        growing = [growing_bar(index) for index in range(count)]
        counting = [counting_value(index) for index in range(count)]
        joining = always_redraw(connectors_now)
        scene.add(joining, *growing, *counting)
        scene.play(progress.animate.set_value(1.0), run_time=phases.main, rate_func=linear)

        final_bars = [geometry.bar(index, 1.0, fills[bar.kind]) for index, bar in enumerate(bars)]
        for index, value_mobject in enumerate(final_values):
            value_mobject.move_to(geometry.value(index, 1.0).get_center())
        final_connectors = VGroup(
            *(connector(index) for index in range(count - 1) if connector is not None)
        )
        scene.remove(joining, *growing, *counting)
        scene.add(final_connectors, *final_bars, *final_values)

        # The other bars keep their colors and only dim, so the final frame still tells an
        # increase from a decrease.
        backdrop = ManimColor(colors.surface if layout.panel else colors.background)
        highlighted = chart.highlight.label if chart.highlight else chart.end.label
        recolor = [
            bar_mobject.animate.set_fill(
                colors.highlight
                if bar.label == highlighted
                else interpolate_color(backdrop, ManimColor(fills[bar.kind]), colors.dim_opacity)
            )
            for bar_mobject, bar in zip(final_bars, bars, strict=True)
        ]
        scene.play(*recolor, run_time=phases.highlight, rate_func=ease)
        scene.wait(phases.hold)

    def _columns(
        self,
        bars: list[WaterfallBar],
        value_text: Callable[[int, float], "VMobject"],
        final_values: list["VMobject"],
    ) -> tuple[BarGeometry, Connector | None]:
        """Columns on a baseline, the labels under it and each value above its column."""
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
                f'label "{bar.label}" is too long for {count} bars; shorten it or use layout: rows',
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
                    "use compact numbers or fewer steps"
                )
        value_gap = stack_gap(sizes.value, sizes.value)
        top = content.top - max(label.height for label in final_values) - value_gap
        if top - baseline < px(MIN_BAR_AREA_PX):
            raise RenderError("not enough room for the bars; shorten the title or the labels")
        scale = LinearScale((0, max(bar.top for bar in bars) or 1), (baseline, top))
        bar_width = slot * BAR_FILL

        def ends(index: int, grown: float) -> tuple[float, float]:
            bar = bars[index]
            current = bar.low + (bar.high - bar.low) * grown
            return scale(bar.low), scale(current)

        def bar_rectangle(index: int, grown: float, fill: str) -> "VMobject":
            start, end = ends(index, grown)
            height = abs(end - start)
            if height <= 0:
                return VGroup()
            rectangle = Rectangle(
                width=bar_width, height=height, stroke_width=0, fill_color=fill, fill_opacity=1
            )
            return rectangle.move_to((centers[index], (start + end) / 2, 0.0))

        def value_at(index: int, grown: float) -> "VMobject":
            if grown <= 0:
                return VGroup()
            label = value_text(index, grown)
            bar_top = max(ends(index, grown))
            return label.move_to((centers[index], bar_top + value_gap + label.height / 2, 0.0))

        def connector(index: int) -> "VMobject":
            level = scale(bars[index].high)
            return Line(
                (centers[index] + bar_width / 2, level, 0.0),
                (centers[index + 1] - bar_width / 2, level, 0.0),
                color=colors.grid,
                stroke_width=stroke_width(sizes.grid_line),
            )

        base_line = Line(
            (content.left, baseline, 0.0),
            (content.right, baseline, 0.0),
            color=colors.grid,
            stroke_width=stroke_width(sizes.grid_line),
        )
        geometry = BarGeometry(
            [block.mobject for block in label_blocks], bar_rectangle, value_at, base_line
        )
        return geometry, connector

    def _rows(
        self,
        bars: list[WaterfallBar],
        value_text: Callable[[int, float], "VMobject"],
        final_values: list["VMobject"],
    ) -> tuple[BarGeometry, Connector | None]:
        """Rows growing to the right, each under its label, each value after its bar."""
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
                f'label "{bar.label}" is too long; shorten it',
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
            (0, max(bar.top for bar in bars) or 1), (content.left, content.left + longest)
        )

        def ends(index: int, grown: float) -> tuple[float, float]:
            bar = bars[index]
            current = bar.low + (bar.high - bar.low) * grown
            return scale(bar.low), scale(current)

        def bar_rectangle(index: int, grown: float, fill: str) -> "VMobject":
            start, end = ends(index, grown)
            width = abs(end - start)
            if width <= 0:
                return VGroup()
            rectangle = Rectangle(
                width=width,
                height=rows[index].thickness,
                stroke_width=0,
                fill_color=fill,
                fill_opacity=1,
            )
            return rectangle.move_to(((start + end) / 2, rows[index].bar_center, 0.0))

        def value_at(index: int, grown: float) -> "VMobject":
            if grown <= 0:
                return VGroup()
            label = value_text(index, grown)
            start = max(ends(index, grown)) + value_gap
            return label.move_to((start + label.width / 2, rows[index].bar_center, 0.0))

        # Rows have no connectors: a line down from one row to the next would cross the label
        # between them.
        geometry = BarGeometry(
            [block.mobject for block in label_blocks], bar_rectangle, value_at, None
        )
        return geometry, None
