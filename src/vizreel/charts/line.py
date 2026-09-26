"""Values over time."""

from collections.abc import Callable
from typing import TYPE_CHECKING

from vizreel.charts.base import ChartType, check_reading_time, split_duration
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
from vizreel.spec.models import LineChart, NumberFormat

if TYPE_CHECKING:
    from manim import Animation, Scene, VMobject

Point = tuple[float, float]
"""A data point as (horizontal position, value)."""

MIN_PLOT_PX = 160
"""Least width and height, in pixels at 1080p, of the plot area."""
FIRST_LABEL_RAMP = 0.05
"""The first-value label fades in while the tip moves this share of the plot width."""
END_LABEL_ROOM = 1.1
"""Room kept for end labels, as a multiple of the widest final end label."""


def runs(xs: list[float], values: list[float | None]) -> list[list[Point]]:
    """Split a series into runs of consecutive points, breaking at null values."""
    result: list[list[Point]] = []
    current: list[Point] = []
    for x, value in zip(xs, values, strict=True):
        if value is None:
            if current:
                result.append(current)
            current = []
        else:
            current.append((x, value))
    if current:
        result.append(current)
    return result


def drawn(series_runs: list[list[Point]], x_cut: float) -> list[list[Point]]:
    """The runs of a series left of `x_cut`; a run cut in the middle ends exactly at `x_cut`.

    The result is a prefix of `series_runs`: item i is the drawn part of run i.
    """
    result: list[list[Point]] = []
    for run in series_runs:
        if run[0][0] > x_cut + 1e-9:
            break
        visible = [point for point in run if point[0] <= x_cut + 1e-9]
        if len(visible) < len(run):
            (x0, v0), (x1, v1) = visible[-1], run[len(visible)]
            share = (x_cut - x0) / (x1 - x0)
            if share > 0:
                visible.append((x_cut, v0 + (v1 - v0) * share))
        result.append(visible)
    return result


def tip(series_runs: list[list[Point]], x_cut: float) -> Point | None:
    """Where the pen of a series is: the last drawn point, or None before the first point."""
    parts = drawn(series_runs, x_cut)
    return parts[-1][-1] if parts else None


@register
class LineChartType(ChartType):
    """One to three series drawn from left to right.

    Grid lines and axis labels appear first. Then each line draws from left to right with a
    label at its tip that counts along; the first value is labeled once the tip has moved
    on. At the highlight beat the lines dim and the highlighted point gets a guide line,
    a dot and a callout.
    """

    name = "line"
    model = LineChart

    def build(self, scene: "Scene") -> None:
        """Add the chart to the scene and animate it."""
        from manim import (
            DOWN,
            RIGHT,
            AnimationGroup,
            Create,
            Dot,
            FadeIn,
            Line,
            ManimColor,
            ValueTracker,
            VGroup,
            VMobject,
            always_redraw,
            interpolate_color,
            linear,
        )

        from vizreel.render import elements
        from vizreel.render.numbers_text import NumberGlyphs

        chart = self.chart
        assert isinstance(chart, LineChart)
        theme, layout = self.theme, self.layout
        fonts, sizes, colors, motion = theme.fonts, theme.sizes, theme.colors, theme.motion
        ease = elements.easing(theme)
        content = layout.content
        gap = stack_gap(sizes.label, sizes.label)
        count = len(chart.series)
        series_colors = colors.series[:count]
        dot_radius = px(sizes.dot) / 2

        header = elements.header(chart.title, chart.subtitle, theme, layout)
        source = elements.source_line(chart.source, theme, layout)

        # Values that get a label: first, last and highlighted. They share decimals.
        present = [[v for v in series.values if v is not None] for series in chart.series]
        firsts = [values[0] for values in present]
        lasts = [values[-1] for values in present]
        highlight_index = chart.x.index(chart.highlight.x) if chart.highlight else None
        highlighted = (
            [series.values[highlight_index] for series in chart.series]
            if highlight_index is not None
            else []
        )
        labeled = firsts + lasts + [value for value in highlighted if value is not None]
        formats: dict[float, NumberFormat] = {
            value: chart.number.model_copy(update={"decimals": places})
            for value, places in zip(labeled, shared_decimals(labeled, chart.number), strict=True)
        }
        glyphs = NumberGlyphs(fonts.numbers, sizes.value, colors.text)

        def value_text(value: float, final: float) -> "VMobject":
            return glyphs(format_number(value, formats[final]))

        names = [
            elements.text(series.name, fonts.body, sizes.label, colors.text)
            if count > 1 and series.name
            else None
            for series in chart.series
        ]

        def end_label(index: int, value: float) -> "VMobject":
            name = names[index]
            parts: list[VMobject] = []
            if name is not None:
                parts += [Dot(radius=dot_radius, color=series_colors[index]), name.copy()]
            parts.append(value_text(value, lasts[index]))
            return VGroup(*parts).arrange(RIGHT, buff=gap / 2)

        # Plot area: the content band minus axis labels, end labels and callout room.
        values = [value for series_values in present for value in series_values]
        axis = value_axis(values, low=chart.y_min, high=chart.y_max)
        tick_labels = [
            elements.number_text(text, fonts.body, sizes.label, colors.muted)
            for text in format_numbers(list(axis.ticks), chart.number)
        ]
        x_labels = [elements.text(text, fonts.body, sizes.label, colors.muted) for text in chart.x]
        end_widths = [end_label(index, lasts[index]).width for index in range(count)]
        callout_label = (
            elements.text(chart.highlight.label, fonts.body, sizes.label, colors.text)
            if chart.highlight and chart.highlight.label
            else None
        )
        callout_height = glyphs("0").height + (callout_label.height + gap if callout_label else 0)
        # The lowest tick label is centered on the plot's bottom edge and reaches half its
        # height below it, so the x labels start below that.
        x_label_gap = gap + max(label.height for label in tick_labels) / 2
        plot = Box(
            content.left + max(label.width for label in tick_labels) + gap,
            content.bottom + max(label.height for label in x_labels) + x_label_gap,
            content.right - dot_radius - gap - max(end_widths) * END_LABEL_ROOM,
            content.top - callout_height - gap,
        )
        if min(plot.width, plot.height) < px(MIN_PLOT_PX):
            raise RenderError(
                "not enough room for the line chart; shorten the labels, series names or title"
            )
        xs = point_positions(
            len(chart.x), plot.left + x_labels[0].width / 2, plot.right - x_labels[-1].width / 2
        )
        y_of = LinearScale((axis.low, axis.high), (plot.bottom, plot.top))
        series_runs = [runs(xs, series.values) for series in chart.series]

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
            label = x_labels[index]
            label.move_to((xs[index], plot.bottom - x_label_gap - label.height / 2, 0.0))
        axis_labels = VGroup(*tick_labels, *(x_labels[index] for index in shown_x))

        def series_line(index: int, x_cut: float) -> "VMobject":
            group = VGroup()
            for part, run in zip(
                drawn(series_runs[index], x_cut), series_runs[index], strict=False
            ):
                points = [(x, y_of(value), 0.0) for x, value in part]
                if len(run) == 1:
                    group.add(Dot(points[0], radius=px(sizes.line), color=series_colors[index]))
                elif len(points) > 1:
                    path = VMobject(
                        stroke_color=series_colors[index], stroke_width=stroke_width(sizes.line)
                    )
                    path.set_points_as_corners(points)
                    group.add(path)
            return group

        def tips_with_labels(x_cut: float) -> "VMobject":
            tips = [
                (index, point)
                for index, point in enumerate(tip(series_run, x_cut) for series_run in series_runs)
                if point is not None
            ]
            labels = [end_label(index, value) for index, (_, value) in tips]
            try:
                centers = spread_labels(
                    [y_of(value) for _, (_, value) in tips],
                    [label.height for label in labels],
                    gap / 2,
                    plot.bottom,
                    content.top,
                )
            except ValueError:
                raise RenderError(
                    "the end labels of the lines do not fit; shorten the series names"
                ) from None
            dots, placed = VGroup(), VGroup()
            for (index, (x, value)), label, center in zip(tips, labels, centers, strict=True):
                dots.add(Dot((x, y_of(value), 0.0), radius=dot_radius, color=series_colors[index]))
                placed.add(label.move_to((x + dot_radius + gap + label.width / 2, center, 0.0)))
            return VGroup(dots, placed)

        # A series with a single point is labeled by its end label only.
        first_labels = [
            value_text(firsts[index], firsts[index]) if len(present[index]) > 1 else None
            for index in range(count)
        ]
        for index, first_label in enumerate(first_labels):
            if first_label is not None:
                x, value = series_runs[index][0][0]
                first_label.move_to(
                    (x + first_label.width / 2, y_of(value) + gap + first_label.height / 2, 0.0)
                )

        def first_labels_at(x_cut: float) -> "VMobject":
            group = VGroup()
            for index, first_label in enumerate(first_labels):
                if first_label is None:
                    continue
                start = series_runs[index][0][0][0]
                clear_of_tip = start + dot_radius + gap + end_widths[index] + gap
                opacity = (x_cut - clear_of_tip) / (plot.width * FIRST_LABEL_RAMP)
                if opacity > 0:
                    group.add(first_label.copy().set_opacity(min(opacity, 1.0)))
            return group

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
            + (
                [(chart.highlight.label, phases.highlight_start)]
                if chart.highlight and chart.highlight.label
                else []
            ),
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

        # The pen sweeps from the first to the last data point, not across empty edges.
        sweep_start = min(series_run[0][0][0] for series_run in series_runs)
        sweep_end = max(series_run[-1][-1][0] for series_run in series_runs)

        def x_cut() -> float:
            eased = ease(progress.get_value())
            return sweep_end if eased >= 1 else sweep_start + eased * (sweep_end - sweep_start)

        def redrawn(build: Callable[[], "VMobject"]) -> "VMobject":
            return always_redraw(build)

        def drawing_line(index: int) -> "VMobject":
            return redrawn(lambda: series_line(index, x_cut()))

        drawing = [drawing_line(index) for index in range(count)]
        trailing = redrawn(lambda: first_labels_at(x_cut()))
        racing = redrawn(lambda: tips_with_labels(x_cut()))
        scene.add(*drawing, trailing, racing)
        scene.play(progress.animate.set_value(1.0), run_time=phases.main, rate_func=linear)

        final_lines = [series_line(index, sweep_end) for index in range(count)]
        scene.remove(*drawing, trailing, racing)
        final_tips = tips_with_labels(sweep_end)
        scene.add(*final_lines, first_labels_at(sweep_end), final_tips)

        def highlight_beat() -> None:
            assert highlight_index is not None
            backdrop = ManimColor(colors.surface if layout.panel else colors.background)
            x = xs[highlight_index]
            points = [
                (index, value) for index, value in enumerate(highlighted) if value is not None
            ]
            dots = VGroup(
                *(
                    Dot((x, y_of(value), 0.0), radius=dot_radius, color=colors.highlight)
                    for _, value in points
                )
            )
            callout_parts: list[VMobject] = []
            if callout_label is not None:
                callout_parts.append(callout_label)
            if count == 1:
                callout_parts.append(value_text(points[0][1], points[0][1]))
            callout = VGroup(*callout_parts).arrange(DOWN, buff=gap / 2)
            # The callout sits in the room kept above the plot, where it covers no data.
            callout_x = min(
                max(x, content.left + callout.width / 2), content.right - callout.width / 2
            )
            callout.move_to((callout_x, content.top - callout.height / 2, 0.0))
            guide_top = callout.get_bottom()[1] - gap / 2 if callout_parts else plot.top
            guide = Line(
                (x, plot.bottom, 0.0),
                (x, guide_top, 0.0),
                color=colors.highlight,
                stroke_width=stroke_width(sizes.grid_line),
            )
            dim = [
                *(line.animate.set_stroke(opacity=colors.dim_opacity) for line in final_lines),
                # Dots dim by blending toward the background so that they stay opaque
                # and the line end does not show through them.
                *(
                    dot.animate.set_fill(
                        interpolate_color(backdrop, dot.get_fill_color(), colors.dim_opacity)
                    )
                    for dot in final_tips[0]
                ),
            ]
            scene.play(
                *dim,
                Create(guide),
                FadeIn(dots),
                *([FadeIn(callout)] if callout_parts else []),
                run_time=phases.highlight,
                rate_func=ease,
            )

        if chart.highlight:
            highlight_beat()
        scene.wait(phases.hold)
