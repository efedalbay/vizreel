"""Values over time."""

import itertools
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

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
from vizreel.spec.data import Table
from vizreel.spec.models import LineChart, LineHighlight, NumberFormat

if TYPE_CHECKING:
    from manim import Animation, Mobject, Scene, VMobject

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


def place_first_labels(
    anchors: list[Point],
    sizes: list[tuple[float, float]],
    polylines: list[list[Point]],
    gap: float,
    bounds: Box,
) -> list[Box]:
    """Place each first-value label above or below the first point of its series.

    Every choice of sides is tried, fewest labels below first, and among those the ones that
    put the lower points' labels below. The first choice where no label comes near another
    label or a line, and every label stays inside `bounds`, wins. If there is none, the
    labels are stacked above the lines, the label of the lowest point at the bottom.

    Args:
        anchors: The first point of each labeled series, in scene coordinates.
        sizes: The width and height of each label.
        polylines: Every line of the chart, as points in scene coordinates.
        gap: Space between a label and its point; a quarter of it is kept clear around
            each label.
        bounds: Where labels may go.

    Returns:
        The box of each label, in the order given. A label starts at its point's x.
    """

    def box(index: int, side: int) -> Box:
        (x, y), (width, height) = anchors[index], sizes[index]
        near = y + side * gap
        far = near + side * height
        return Box(x, min(near, far), x + width, max(near, far))

    def clear(boxes: list[Box]) -> bool:
        padded = [label.inset(-gap / 4) for label in boxes]
        return (
            all(_inside(label, bounds) for label in boxes)
            and not any(_overlap(a, b) for i, a in enumerate(padded) for b in padded[i + 1 :])
            and not any(
                _segment_hits_box(start, end, label)
                for label in padded
                for line in polylines
                for start, end in zip(line, line[1:], strict=False)
            )
        )

    def preference(sides: tuple[int, ...]) -> tuple[int, float]:
        below = [anchors[index][1] for index, side in enumerate(sides) if side < 0]
        return len(below), sum(below)

    for sides in sorted(itertools.product((1, -1), repeat=len(anchors)), key=preference):
        boxes = [box(index, side) for index, side in enumerate(sides)]
        if clear(boxes):
            return boxes
    return _stacked_above_lines(anchors, sizes, polylines, gap)


def _stacked_above_lines(
    anchors: list[Point], sizes: list[tuple[float, float]], polylines: list[list[Point]], gap: float
) -> list[Box]:
    stacked: dict[int, Box] = {}
    floor = -math.inf
    for index in sorted(range(len(anchors)), key=lambda i: anchors[i][1]):
        (x, y), (width, height) = anchors[index], sizes[index]
        # A quarter gap beside the label too, as `place_first_labels` keeps clear: a steep
        # line just past the label's corner would otherwise touch it.
        highest = _highest(polylines, x - gap / 4, x + width + gap / 4)
        bottom = max(y + gap, highest + gap / 2, floor + gap / 2)
        stacked[index] = Box(x, bottom, x + width, bottom + height)
        floor = bottom + height
    return [stacked[index] for index in range(len(anchors))]


def _highest(polylines: list[list[Point]], left: float, right: float) -> float:
    """The highest y that any line reaches between `left` and `right`."""
    highest = -math.inf
    for line in polylines:
        for (x0, y0), (x1, y1) in zip(line, line[1:], strict=False):
            start, end = max(x0, left), min(x1, right)
            if start > end:
                continue
            for x in (start, end):
                share = (x - x0) / (x1 - x0) if x1 != x0 else 0.0
                highest = max(highest, y0 + (y1 - y0) * share)
    return highest


def _inside(inner: Box, outer: Box) -> bool:
    return (
        inner.left >= outer.left
        and inner.right <= outer.right
        and inner.bottom >= outer.bottom
        and inner.top <= outer.top
    )


def _overlap(a: Box, b: Box) -> bool:
    return a.left < b.right and b.left < a.right and a.bottom < b.top and b.bottom < a.top


def _segment_hits_box(start: Point, end: Point, box: Box) -> bool:
    """Whether the segment from `start` to `end` passes through `box` (Liang-Barsky)."""
    (x0, y0), (x1, y1) = start, end
    dx, dy = x1 - x0, y1 - y0
    low, high = 0.0, 1.0
    for direction, distance in (
        (-dx, x0 - box.left),
        (dx, box.right - x0),
        (-dy, y0 - box.bottom),
        (dy, box.top - y0),
    ):
        if direction == 0:
            if distance < 0:
                return False
            continue
        share = distance / direction
        if direction < 0:
            low = max(low, share)
        else:
            high = min(high, share)
        if low > high:
            return False
    return True


def marked_points(chart: LineChart) -> list[LineHighlight]:
    """Every point the chart marks: each point of its sequence, or its one highlight."""
    if chart.sequence:
        return [LineHighlight(x=item) if isinstance(item, str) else item for item in chart.sequence]
    return [chart.highlight] if chart.highlight else []


@dataclass
class _LineFinal:
    """The drawn chart, which the emphasis changes: its lines, their end dots and the marks."""

    lines: list["VMobject"]
    tips: list["Mobject"]
    colors: list[str]
    marks: Callable[[LineHighlight], tuple["VMobject", "VMobject", "VMobject | None"]]
    shown: "VMobject | None" = None
    """The guide line, dots and callout of the point marked last."""


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
    template = """\
- id: revenue                      # unique; lowercase letters, digits and hyphens
  type: line
  title: Northwind revenue by product
  x: ["2019", "2020", "2021", "2022"]   # labels in order; quote years
  series:                          # one to three series
    - { name: Cloud, values: [1.2, 2.4, 3.9, 5.1] }
    - { name: Devices, values: [3.1, 2.9, 3.2, 3.0] }   # null leaves a gap
  number: { prefix: "$", suffix: "B" }
  highlight: { x: "2021", label: "Cloud passes devices" }   # optional
  # subtitle: In billions of dollars   # optional
  # source: "Source: example data"     # optional
  # y_min: 0                       # optional: fixed axis range
  # y_max: 6
  # duration: 6                    # optional: seconds, at least 2
"""

    @classmethod
    def from_table(cls, table: Table, chart: dict[str, Any]) -> dict[str, Any]:
        """Read the x labels from the first column and a series from each other column.

        A series is named by its column's header; an empty cell leaves a gap.
        """
        if table.width < 2:
            table.require_width(2, "the x labels and a series")
        rows = range(len(table.rows))
        return {
            "x": [table.text(row, 0) for row in rows],
            "series": [
                {
                    "name": table.header[column],
                    "values": [table.optional_number(row, column) for row in rows],
                }
                for column in range(1, table.width)
            ],
        }

    def build(self, scene: "Scene") -> None:
        """Add the chart to the scene and animate it."""
        from manim import (
            DOWN,
            RIGHT,
            AnimationGroup,
            Create,
            Dot,
            Line,
            ValueTracker,
            VGroup,
            VMobject,
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

        # Values that get a label: first, last and highlighted. They share decimals. A chart
        # told as a sequence counts every point it will mark, so that all its clips share one
        # layout and one number format and cut together seamlessly.
        present = [[v for v in series.values if v is not None] for series in chart.series]
        firsts = [values[0] for values in present]
        lasts = [values[-1] for values in present]
        marked = marked_points(chart)
        highlighted = [
            value
            for point in marked
            for series in chart.series
            if (value := series.values[chart.x.index(point.x)]) is not None
        ]
        labeled = firsts + lasts + highlighted
        formats: dict[float, NumberFormat] = {
            value: chart.number.model_copy(update={"decimals": places})
            for value, places in zip(labeled, shared_decimals(labeled, chart.number), strict=True)
        }
        glyphs = NumberGlyphs(fonts.numbers, sizes.value, colors.text)

        def value_text(value: float, final: float) -> "VMobject":
            return glyphs(format_number(value, formats[final], locale=self.locale, unit_of=final))

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
            number = value_text(value, lasts[index])
            parts.append(number)
            label = VGroup(*parts).arrange(RIGHT, buff=gap / 2)
            if name is not None:
                # Figures sit on the baseline, so the name goes on the baseline of the number.
                name_baseline = elements.baseline(
                    parts[1], chart.series[index].name or "", fonts.body, sizes.label
                )
                parts[1].shift((0.0, number.get_bottom()[1] - name_baseline, 0.0))
            return label

        # Plot area: the content band minus axis labels, end labels and callout room.
        values = [value for series_values in present for value in series_values]
        axis = value_axis(values, low=chart.y_min, high=chart.y_max)
        tick_labels = [
            elements.number_text(text, fonts.body, sizes.label, colors.muted)
            for text in format_numbers(list(axis.ticks), chart.number, locale=self.locale)
        ]
        x_blocks = [
            elements.text_block(text, fonts.body, sizes.label, colors.muted) for text in chart.x
        ]
        x_labels = [block.mobject for block in x_blocks]
        end_widths = [end_label(index, lasts[index]).width for index in range(count)]
        callout_labels = [
            elements.text(point.label, fonts.body, sizes.label, colors.text)
            for point in marked
            if point.label
        ]
        callout_height = glyphs("0").height + (
            max(label.height for label in callout_labels) + gap if callout_labels else 0
        )
        # The lowest tick label is centered on the plot's bottom edge and reaches half its
        # height below it, so the x labels start below that.
        x_label_gap = gap + max(label.height for label in tick_labels) / 2
        plot = Box(
            content.left + max(label.width for label in tick_labels) + gap,
            content.bottom + max(block.height for block in x_blocks) + x_label_gap,
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
            x_blocks[index].move_top_to(plot.bottom - x_label_gap)
            x_labels[index].set_x(xs[index])
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
        labeled_first = {
            index: label for index, label in enumerate(first_labels) if label is not None
        }
        first_boxes = place_first_labels(
            [
                (series_runs[index][0][0][0], y_of(series_runs[index][0][0][1]))
                for index in labeled_first
            ],
            [(label.width, label.height) for label in labeled_first.values()],
            [
                [(x, y_of(value)) for x, value in run]
                for series_run in series_runs
                for run in series_run
            ],
            gap,
            Box(plot.left, plot.bottom, plot.right, content.top),
        )
        for label, first_box in zip(labeled_first.values(), first_boxes, strict=True):
            label.move_to((*first_box.center, 0.0))

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
            opening.append(elements.appear(card, theme, run_time=motion.title_fade, rate_func=ease))
        titles = VGroup(header, *([source] if source else []))
        if len(titles):
            opening.append(
                elements.appear(titles, theme, run_time=motion.title_fade, rate_func=ease)
            )
        if len(header):
            scene.play(AnimationGroup(*opening), run_time=motion.title_fade)
            opening = []
        scene.play(
            AnimationGroup(
                *opening,
                Create(grid, run_time=motion.structure, rate_func=ease),
                elements.appear(axis_labels, theme, run_time=motion.structure, rate_func=ease),
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
            return elements.redrawn_shapes(build)

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

        def marks(item: LineHighlight) -> tuple["VMobject", "VMobject", "VMobject | None"]:
            """The guide line, the dots and the callout that mark the point `item`."""
            index = chart.x.index(item.x)
            x = xs[index]
            points = [
                value
                for value in (series.values[index] for series in chart.series)
                if value is not None
            ]
            dots = VGroup(
                *(
                    Dot((x, y_of(value), 0.0), radius=dot_radius, color=colors.highlight)
                    for value in points
                )
            )
            callout_parts: list[VMobject] = []
            if item.label:
                callout_parts.append(
                    elements.text(item.label, fonts.body, sizes.label, colors.text)
                )
            if count == 1:
                callout_parts.append(value_text(points[0], points[0]))
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
            return guide, dots, callout if callout_parts else None

        self._final = _LineFinal(
            lines=final_lines,
            tips=final_tips[0].submobjects,
            colors=series_colors,
            marks=marks,
        )
        if chart.highlight:
            scene.play(*self.emphasis(chart.highlight), run_time=phases.highlight, rate_func=ease)
        scene.wait(phases.hold)

    def emphasis(self, item: Any) -> list[Any]:
        """Mark the point a sequence item names and dim the lines.

        A guide line draws up from the point, dots appear on it and the callout fades in; the
        marks of an earlier emphasis fade out. Dots at the line ends dim by blending toward
        the background, so that they stay opaque and the line end does not show through.
        """
        from manim import Create, FadeIn, ManimColor, VGroup, interpolate_color

        from vizreel.render import elements

        colors = self.theme.colors
        final = self._final
        target = LineHighlight(x=item) if isinstance(item, str) else item
        backdrop = ManimColor(colors.surface if self.layout.panel else colors.background)
        animations: list[Any] = [
            *(line.animate.set_stroke(opacity=colors.dim_opacity) for line in final.lines),
            *(
                dot.animate.set_fill(
                    interpolate_color(backdrop, ManimColor(color), colors.dim_opacity)
                )
                for dot, color in zip(final.tips, final.colors, strict=True)
            ),
        ]
        if final.shown is not None:
            animations.append(elements.fade_away(final.shown))
        guide, dots, callout = final.marks(target)
        animations += [Create(guide), FadeIn(dots), *([FadeIn(callout)] if callout else [])]
        final.shown = VGroup(guide, dots, *([callout] if callout else []))
        return animations
