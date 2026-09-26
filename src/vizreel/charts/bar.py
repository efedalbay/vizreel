"""Compare categories."""

from typing import TYPE_CHECKING

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
from vizreel.render.scales import LinearScale, band_centers, two_line_splits
from vizreel.spec.models import Bar, BarChart

if TYPE_CHECKING:
    from manim import Animation, Scene, VMobject

MIN_BAR_AREA_PX = 120
"""Least height, in pixels at 1080p, left for the tallest bar."""


def sorted_bars(chart: BarChart) -> list[Bar]:
    """Return the bars in display order."""
    if chart.sort == "asc":
        return sorted(chart.bars, key=lambda bar: bar.value)
    if chart.sort == "desc":
        return sorted(chart.bars, key=lambda bar: bar.value, reverse=True)
    return list(chart.bars)


@register
class BarChartType(ChartType):
    """Vertical bars, one per category, with a value label on every bar and no value axis.

    The title fades in, the baseline draws, then the bars grow from the baseline one after
    another while their labels count. At the highlight beat the highlighted bar turns to the
    highlight color and the others to muted.
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
  # subtitle: Fiscal year 2022     # optional
  # source: "Source: example data" # optional
  # duration: 5                    # optional: seconds, at least 2
"""

    def build(self, scene: "Scene") -> None:
        """Add the chart to the scene and animate it."""
        from manim import (
            AnimationGroup,
            Create,
            FadeIn,
            Line,
            Rectangle,
            ValueTracker,
            VGroup,
            always_redraw,
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
        content = layout.content
        slot = content.width / count
        centers = band_centers(count, content.left, content.right)
        label_gap = stack_gap(sizes.label, sizes.label)

        def category_label(content_text: str) -> "VMobject":
            max_width = slot * LABEL_FILL
            single = elements.text(content_text, fonts.body, sizes.label, colors.muted)
            if single.width <= max_width:
                return VGroup(single)
            for split in two_line_splits(content_text):
                lines = [
                    elements.text(part, fonts.body, sizes.label, colors.muted) for part in split
                ]
                if all(line.width <= max_width for line in lines):
                    return elements.paragraph(list(split), fonts.body, sizes.label, colors.muted)
            raise RenderError(
                f'bar label "{content_text}" is too long for {count} bars; shorten it'
            )

        header = elements.header(chart.title, chart.subtitle, theme, layout)
        source = elements.source_line(chart.source, theme, layout)
        labels = [category_label(bar.label) for bar in bars]
        labels_height = max(label.height for label in labels)
        baseline = content.bottom + labels_height + label_gap
        for label, center in zip(labels, centers, strict=True):
            label.move_to((center, baseline - label_gap - label.height / 2, 0.0))

        value_formats = [
            chart.number.model_copy(update={"decimals": places})
            for places in shared_decimals([bar.value for bar in bars], chart.number)
        ]
        glyphs = NumberGlyphs(fonts.numbers, sizes.value, colors.text)
        final_values = [
            glyphs(format_number(bar.value, value_format))
            for bar, value_format in zip(bars, value_formats, strict=True)
        ]
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
            label = glyphs(format_number(bars[index].value * grown, value_formats[index]))
            bar_top = baseline + (scale(bars[index].value) - baseline) * grown
            return label.move_to((centers[index], bar_top + value_gap + label.height / 2, 0.0))

        base_line = Line(
            (content.left, baseline, 0.0),
            (content.right, baseline, 0.0),
            color=colors.grid,
            stroke_width=stroke_width(sizes.grid_line),
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
            opening.append(FadeIn(card, run_time=motion.title_fade, rate_func=ease))
        titles = VGroup(header, *([source] if source else []))
        if len(titles):
            opening.append(FadeIn(titles, run_time=motion.title_fade, rate_func=ease))
        if len(header):
            scene.play(AnimationGroup(*opening), run_time=motion.title_fade)
            opening = []
        structure = [
            *opening,
            Create(base_line, run_time=motion.structure, rate_func=ease),
            FadeIn(VGroup(*labels), run_time=motion.structure, rate_func=ease),
        ]
        scene.play(AnimationGroup(*structure), run_time=motion.structure)

        progress = ValueTracker(0.0)

        def grown(index: int) -> float:
            local = staggered_progress(
                progress.get_value(), index, count, stagger=motion.stagger, total=phases.main
            )
            return ease(local)

        def growing_bar(index: int) -> "VMobject":
            return always_redraw(lambda: bar_rectangle(index, grown(index), colors.accent))

        def counting_value(index: int) -> "VMobject":
            return always_redraw(lambda: value_at(index, grown(index)))

        growing = [growing_bar(index) for index in range(count)]
        counting = [counting_value(index) for index in range(count)]
        scene.add(*growing, *counting)
        scene.play(progress.animate.set_value(1.0), run_time=phases.main, rate_func=linear)

        final_bars = [bar_rectangle(index, 1.0, colors.accent) for index in range(count)]
        for index, value_mobject in enumerate(final_values):
            value_mobject.move_to(value_at(index, 1.0).get_center())
        scene.remove(*growing, *counting)
        scene.add(*final_bars, *final_values)

        if chart.highlight:
            highlighted = chart.highlight.label
            recolor = [
                bar_mobject.animate.set_fill(colors.highlight, opacity=1)
                if bar.label == highlighted
                else bar_mobject.animate.set_fill(colors.muted, opacity=colors.dim_opacity)
                for bar_mobject, bar in zip(final_bars, bars, strict=True)
            ]
            scene.play(*recolor, run_time=phases.highlight, rate_func=ease)
        scene.wait(phases.hold)
