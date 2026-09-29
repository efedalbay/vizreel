"""Amounts over time, as filled areas."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from vizreel.charts.base import ChartType, check_reading_time, split_duration
from vizreel.charts.line import END_LABEL_ROOM, MIN_PLOT_PX, Point, drawn
from vizreel.charts.registry import register
from vizreel.errors import RenderError
from vizreel.format.numbers import format_number, format_numbers, shared_decimals
from vizreel.render.layout import Box, px, stack_gap, stroke_width
from vizreel.render.scales import (
    LinearScale,
    point_positions,
    spread_labels,
    thin_labels,
    value_axis,
)
from vizreel.spec.data import Table
from vizreel.spec.models import AreaChart

if TYPE_CHECKING:
    from manim import Animation, Mobject, Scene, VMobject

OVERLAP_FILL = 0.25
"""Opacity of an area's fill when areas overlap, so the areas behind it show through."""
STACKED_FILL = 0.7
"""Opacity of an area's fill when areas are stacked and never overlap."""


def band(tops: list[Point], bottoms: list[Point]) -> list[Point]:
    """Return the outline of the area between two lines at the same x positions.

    The outline runs along `tops` from left to right, then back along `bottoms`.
    """
    return [*tops, *reversed(bottoms)]


def label_anchor(top: float, bottom: float, stack: bool) -> float:
    """The value an end label points at: the middle of a stacked band, the top of an area."""
    return (top + bottom) / 2 if stack else top


@dataclass
class _AreaFinal:
    """The drawn chart, which the emphasis changes: its areas, their lines and end dots."""

    fills: list["VMobject"]
    lines: list["VMobject"]
    dots: list["Mobject"]
    fill_opacity: float


@register
class AreaChartType(ChartType):
    """One to three series as filled areas drawn from left to right.

    Grid lines and axis labels appear first. Then the areas fill from left to right behind a
    line along their top, with a label at the tip that counts along: the series name and its
    value. Overlapping areas are translucent; stacked areas sit on each other, so the top
    shows the total. At the highlight beat the highlighted series keeps its color and the
    others dim.
    """

    name = "area"
    model = AreaChart
    template = """\
- id: users                        # unique; lowercase letters, digits and hyphens
  type: area
  title: Northwind users by platform
  x: ["2020", "2021", "2022", "2023"]   # labels in order; quote years
  series:                          # one to three series; values zero or more
    - { name: Web, values: [1.2, 1.9, 2.4, 2.8] }
    - { name: Mobile, values: [0.4, 1.1, 2.2, 3.6] }
  stack: true                      # optional: stack the areas; the top is their total
  number: { suffix: "M" }
  # highlight: { series: Mobile }  # optional: the series that keeps its color at the end
  # subtitle: Monthly active users # optional
  # source: "Source: example data" # optional
  # duration: 6                    # optional: seconds, at least 2
"""

    @classmethod
    def from_table(cls, table: Table, chart: dict[str, Any]) -> dict[str, Any]:
        """Read the x labels from the first column and a series from each other column.

        A series is named by its column's header. Every cell needs a value.
        """
        if table.width < 2:
            table.require_width(2, "the x labels and a series")
        rows = range(len(table.rows))
        return {
            "x": [table.text(row, 0) for row in rows],
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
            RIGHT,
            AnimationGroup,
            Create,
            Dot,
            FadeIn,
            Line,
            ValueTracker,
            VGroup,
            VMobject,
            always_redraw,
            linear,
        )

        from vizreel.render import elements
        from vizreel.render.numbers_text import NumberGlyphs

        chart = self.chart
        assert isinstance(chart, AreaChart)
        theme, layout = self.theme, self.layout
        fonts, sizes, colors, motion = theme.fonts, theme.sizes, theme.colors, theme.motion
        ease = elements.easing(theme)
        content = layout.content
        gap = stack_gap(sizes.label, sizes.label)
        count = len(chart.series)
        series_colors = colors.series[:count]
        dot_radius = px(sizes.dot) / 2
        fill_opacity = STACKED_FILL if chart.stack else OVERLAP_FILL
        tops, bottoms = chart.tops(), chart.bottoms()

        header = elements.header(chart.title, chart.subtitle, theme, layout)
        source = elements.source_line(chart.source, theme, layout)

        lasts = [series.values[-1] for series in chart.series]
        formats = [
            chart.number.model_copy(update={"decimals": places})
            for places in shared_decimals(lasts, chart.number)
        ]
        glyphs = NumberGlyphs(fonts.numbers, sizes.value, colors.text)
        names = [
            elements.text(series.name, fonts.body, sizes.label, colors.text)
            if count > 1 and series.name
            else None
            for series in chart.series
        ]

        def end_label(index: int, value: float) -> "VMobject":
            number = glyphs(
                format_number(value, formats[index], locale=self.locale, unit_of=lasts[index])
            )
            name = names[index]
            if name is None:
                return number
            label = VGroup(name.copy(), number).arrange(RIGHT, buff=gap)
            # Figures sit on the baseline, so the name goes on the baseline of the number.
            name_baseline = elements.baseline(
                label[0], chart.series[index].name or "", fonts.body, sizes.label
            )
            label[0].shift((0.0, number.get_bottom()[1] - name_baseline, 0.0))
            return label

        axis = value_axis([0.0, *(value for top in tops for value in top)], low=0.0)
        tick_labels = [
            elements.number_text(text, fonts.body, sizes.label, colors.muted)
            for text in format_numbers(list(axis.ticks), chart.number, locale=self.locale)
        ]
        x_blocks = [
            elements.text_block(text, fonts.body, sizes.label, colors.muted) for text in chart.x
        ]
        x_labels = [block.mobject for block in x_blocks]
        end_widths = [end_label(index, lasts[index]).width for index in range(count)]
        x_label_gap = gap + max(label.height for label in tick_labels) / 2
        plot = Box(
            content.left + max(label.width for label in tick_labels) + gap,
            content.bottom + max(block.height for block in x_blocks) + x_label_gap,
            content.right - dot_radius - gap - max(end_widths) * END_LABEL_ROOM,
            content.top - glyphs("0").height / 2,
        )
        if min(plot.width, plot.height) < px(MIN_PLOT_PX):
            raise RenderError(
                "not enough room for the area chart; shorten the labels, series names or title"
            )
        xs = point_positions(
            len(chart.x), plot.left + x_labels[0].width / 2, plot.right - x_labels[-1].width / 2
        )
        y_of = LinearScale((axis.low, axis.high), (plot.bottom, plot.top))
        top_points = [list(zip(xs, top, strict=True)) for top in tops]
        bottom_points = [list(zip(xs, bottom, strict=True)) for bottom in bottoms]

        grid = VGroup(
            *(
                Line(
                    (plot.left, y_of(tick), 0.0),
                    (plot.right, y_of(tick), 0.0),
                    color=colors.grid,
                    stroke_width=stroke_width(sizes.grid_line),
                )
                for tick in axis.ticks
            )
        )
        for label, tick in zip(tick_labels, axis.ticks, strict=True):
            label.move_to((plot.left - gap - label.width / 2, y_of(tick), 0.0))
        shown_x = thin_labels(xs, [label.width for label in x_labels], gap * 2)
        for index in shown_x:
            x_blocks[index].move_top_to(plot.bottom - x_label_gap)
            x_labels[index].set_x(xs[index])
        axis_labels = VGroup(*tick_labels, *(x_labels[index] for index in shown_x))

        def scene_points(points: list[Point]) -> list[tuple[float, float, float]]:
            return [(x, y_of(value), 0.0) for x, value in points]

        def area_fill(index: int, x_cut: float) -> "VMobject":
            [top] = drawn([top_points[index]], x_cut)
            [bottom] = drawn([bottom_points[index]], x_cut)
            if len(top) < 2:
                return VMobject()
            shape = VMobject(
                fill_color=series_colors[index], fill_opacity=fill_opacity, stroke_width=0
            )
            outline = scene_points(band(top, bottom))
            shape.set_points_as_corners([*outline, outline[0]])
            return shape

        def area_line(index: int, x_cut: float) -> "VMobject":
            [top] = drawn([top_points[index]], x_cut)
            if len(top) < 2:
                return VMobject()
            path = VMobject(
                stroke_color=series_colors[index], stroke_width=stroke_width(sizes.line)
            )
            path.set_points_as_corners(scene_points(top))
            return path

        def tips_with_labels(x_cut: float) -> "VMobject":
            ends = []
            for index in range(count):
                [top] = drawn([top_points[index]], x_cut)
                [bottom] = drawn([bottom_points[index]], x_cut)
                ends.append((top[-1][0], top[-1][1], bottom[-1][1]))
            labels = [end_label(index, high - low) for index, (_, high, low) in enumerate(ends)]
            try:
                centers = spread_labels(
                    [y_of(label_anchor(high, low, chart.stack)) for _, high, low in ends],
                    [label.height for label in labels],
                    gap / 2,
                    plot.bottom,
                    content.top,
                )
            except ValueError:
                raise RenderError(
                    "the end labels of the areas do not fit; shorten the series names"
                ) from None
            dots, placed = VGroup(), VGroup()
            for index, ((x, high, _), label, center) in enumerate(
                zip(ends, labels, centers, strict=True)
            ):
                dots.add(Dot((x, y_of(high), 0.0), radius=dot_radius, color=series_colors[index]))
                placed.add(label.move_to((x + dot_radius + gap + label.width / 2, center, 0.0)))
            return VGroup(dots, placed)

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
            + [(label, labels_appear) for label in chart.x]
            + [(series.name, labels_appear) for series in chart.series if series.name],
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
        scene.play(
            AnimationGroup(
                *opening,
                Create(grid, run_time=motion.structure, rate_func=ease),
                FadeIn(axis_labels, run_time=motion.structure, rate_func=ease),
            ),
            run_time=motion.structure,
        )

        progress = ValueTracker(0.0)
        sweep_start, sweep_end = xs[0], xs[-1]

        def x_cut() -> float:
            eased = ease(progress.get_value())
            return sweep_end if eased >= 1 else sweep_start + eased * (sweep_end - sweep_start)

        def redrawn(build: Callable[[], "VMobject"]) -> "VMobject":
            return always_redraw(build)

        def drawing(index: int) -> list["VMobject"]:
            return [
                redrawn(lambda: area_fill(index, x_cut())),
                redrawn(lambda: area_line(index, x_cut())),
            ]

        growing = [mobject for index in range(count) for mobject in drawing(index)]
        racing = redrawn(lambda: tips_with_labels(x_cut()))
        scene.add(*growing, racing)
        scene.play(progress.animate.set_value(1.0), run_time=phases.main, rate_func=linear)

        fills = [area_fill(index, sweep_end) for index in range(count)]
        lines = [area_line(index, sweep_end) for index in range(count)]
        final_tips = tips_with_labels(sweep_end)
        scene.remove(*growing, racing)
        scene.add(*(mobject for pair in zip(fills, lines, strict=True) for mobject in pair))
        scene.add(final_tips)
        self._final = _AreaFinal(fills, lines, final_tips[0].submobjects, fill_opacity)

        if chart.highlight:
            scene.play(
                *self.emphasis(chart.highlight.series), run_time=phases.highlight, rate_func=ease
            )
        scene.wait(phases.hold)

    def emphasis(self, item: Any) -> list[Any]:
        """Keep the series named `item` in its color and dim the others.

        A dimmed area's fill and line fade; its end dot blends toward the background, so that
        it stays opaque and the line end does not show through.
        """
        from manim import ManimColor, interpolate_color

        assert isinstance(self.chart, AreaChart)
        colors = self.theme.colors
        final = self._final
        backdrop = ManimColor(colors.surface if self.layout.panel else colors.background)
        animations: list[Any] = []
        for index, series in enumerate(self.chart.series):
            kept = series.name == item
            dim = 1.0 if kept else colors.dim_opacity
            color = ManimColor(colors.series[index])
            dot_color = color if kept else interpolate_color(backdrop, color, colors.dim_opacity)
            animations += [
                final.fills[index].animate.set_fill(opacity=final.fill_opacity * dim),
                final.lines[index].animate.set_stroke(opacity=dim),
                final.dots[index].animate.set_fill(dot_color),
            ]
        return animations
