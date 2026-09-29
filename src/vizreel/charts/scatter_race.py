"""Points that race through many periods on two value axes."""

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from vizreel.charts._race import (
    caption_at,
    check_caption_times,
    check_race_time,
    fill_gaps,
    race_colors,
    race_position,
    value_at,
)
from vizreel.charts.base import ChartType, check_reading_time
from vizreel.charts.line import MIN_PLOT_PX
from vizreel.charts.registry import register
from vizreel.errors import RenderError
from vizreel.format.numbers import format_numbers
from vizreel.render.layout import Box, px, stack_gap, stroke_width
from vizreel.render.scales import LinearScale, thin_labels, value_axis
from vizreel.spec.data import Table, TableError
from vizreel.spec.models import ScatterRaceChart

if TYPE_CHECKING:
    from manim import Animation, Mobject, Scene, VMobject

HEADROOM = 1.1
"""The far end of each axis, as a multiple of the largest value seen so far."""
PERIOD_SCALE = 0.5
"""Size of the period shown above the plot, as a share of the theme's big number size."""
LARGEST_POINT = 1.2
"""Radius of the point with the largest size, as a multiple of the value text size."""
POINT_OPACITY = 0.85
"""Opacity of the points' fill, so that one behind another shows through a little."""
TRAIL_OPACITY = 0.5
"""Opacity of the path of the followed series."""
LABEL_FADE = 0.3
"""How long a name takes to fade in once it has a clear place, in periods."""
LABEL_LOOKS = 4
"""How many earlier moments are looked at to fade a name in."""


@dataclass(frozen=True)
class Point:
    """A point on the plot, in scene units: its center and its radius."""

    x: float
    y: float
    radius: float

    def box(self) -> Box:
        """The square around the point."""
        return Box(
            self.x - self.radius, self.y - self.radius, self.x + self.radius, self.y + self.radius
        )


def _overlap(first: Box, second: Box) -> bool:
    return (
        first.left < second.right
        and second.left < first.right
        and first.bottom < second.top
        and second.bottom < first.top
    )


def _inside(inner: Box, outer: Box) -> bool:
    return (
        inner.left >= outer.left
        and inner.right <= outer.right
        and inner.bottom >= outer.bottom
        and inner.top <= outer.top
    )


def place_labels(
    points: list[Point | None],
    sizes: list[tuple[float, float] | None],
    order: list[int],
    bounds: Box,
    gap: float,
) -> list[Box | None]:
    """Place the name of each point clear of every point and of the names placed before it.

    Each name tries the right of its point, then the left, above and below. A name with no
    clear place is left out, so no two names, and no name and a point, ever overlap.

    Args:
        points: Every point on the plot, or None for a series not shown.
        sizes: The width and height of each name, or None for a point without one.
        order: The points in the order their names are placed; earlier ones win.
        bounds: The box every name stays inside.
        gap: Space between a point and its name.

    Returns:
        The box of each name, or None where it is left out.
    """
    obstacles = [point.box() for point in points if point is not None]
    placed: list[Box] = []
    result: list[Box | None] = [None] * len(points)
    for index in order:
        point, size = points[index], sizes[index]
        if point is None or size is None:
            continue
        width, height = size
        reach = point.radius + gap
        candidates = [
            Box(
                point.x + reach, point.y - height / 2, point.x + reach + width, point.y + height / 2
            ),
            Box(
                point.x - reach - width, point.y - height / 2, point.x - reach, point.y + height / 2
            ),
            Box(
                point.x - width / 2, point.y + reach, point.x + width / 2, point.y + reach + height
            ),
            Box(
                point.x - width / 2, point.y - reach - height, point.x + width / 2, point.y - reach
            ),
        ]
        for box in candidates:
            clear = _inside(box, bounds) and not any(
                _overlap(box, other) for other in [*obstacles, *placed]
            )
            if clear:
                result[index] = box
                placed.append(box)
                break
    return result


def point_radius(
    size: float | None, largest: float, smallest_radius: float, largest_radius: float
) -> float:
    """The radius of a point: its area grows with its size, from the smallest radius up."""
    if size is None or largest <= 0:
        return smallest_radius
    return max(largest_radius * math.sqrt(max(size, 0.0) / largest), smallest_radius)


def running_extents(series: list[list[float | None]]) -> list[tuple[float, float]]:
    """The smallest and largest value seen up to each period, across every series.

    The low end is at most zero, so an axis of positive values starts at zero.
    """
    low, high = 0.0, 0.0
    result = []
    for period in range(len(series[0])):
        now = [value for values in series if (value := values[period]) is not None]
        low = min([low, *now])
        high = max([high, *now])
        result.append((low, high))
    return result


def visible_span(values: list[float | None]) -> tuple[int, int] | None:
    """The first and last period with a value, or None if there is none."""
    known = [index for index, value in enumerate(values) if value is not None]
    return (known[0], known[-1]) if known else None


@register
class ScatterRaceChartType(ChartType):
    """Points that move over many periods on two value axes, sized by a third value.

    The axes and their titles appear first, then the race runs through the periods at one
    pace and slows to a stop on the last one, each point moving from one period's place to
    the next. The axes grow with the largest values seen so far. Names sit beside their points
    wherever they are clear of every point and other name. Points are in the accent color, or
    a brand color, and the followed series in the highlight color, with its path behind it if
    `trail` is set.
    """

    name = "scatter-race"
    model = ScatterRaceChart
    template = """\
- id: growth-race                  # unique; lowercase letters, digits and hyphens
  type: scatter-race
  title: Revenue and staff of the market
  periods: ["2021", "2022", "2023"]   # in order; quote years
  x_title: Revenue                 # what the horizontal axis measures
  y_title: Employees               # what the vertical axis measures
  series:                          # two to thirty; one value per period, null for a gap
    - { name: Northwind, x: [12, 30, 55], y: [80, 150, 260], size: [3, 5, 9] }
    - { name: Contoso, x: [60, 64, 70], y: [400, 380, 390], size: [8, 8, 9] }
    - { name: Fabrikam, x: [40, 35, 38], y: [220, 240, 230] }
  x_number: { prefix: "$", suffix: "M" }
  highlight: { series: Northwind } # optional: the series drawn in the highlight color
  # trail: true                    # optional: draw the path of the followed series
  # source: "Source: example data" # optional
  # duration: 15                   # optional: seconds, at least 2
"""

    @classmethod
    def from_table(cls, table: Table, chart: dict[str, Any]) -> dict[str, Any]:
        """Read a row per period and series: the period, the name, x, y and an optional size.

        Periods and series are in the order they first appear; a period missing for a series
        leaves a gap.
        """
        if table.width not in (4, 5):
            table.require_width(4, "the period, the name, x and y, and an optional size")
        periods: list[str] = []
        names: list[str] = []
        cells: dict[tuple[str, str], int] = {}
        for row in range(len(table.rows)):
            period, name = table.text(row, 0), table.text(row, 1)
            if (period, name) in cells:
                first = table.lines[cells[period, name]]
                raise TableError(
                    f'has "{name}" in "{period}" again; it is already on row {first}',
                    row=table.lines[row],
                )
            cells[period, name] = row
            periods += [] if period in periods else [period]
            names += [] if name in names else [name]

        def column(name: str, index: int) -> list[float | None]:
            return [
                table.optional_number(cells[period, name], index)
                if (period, name) in cells
                else None
                for period in periods
            ]

        return {
            "periods": periods,
            "series": [
                {
                    "name": name,
                    "x": column(name, 2),
                    "y": column(name, 3),
                    **({"size": column(name, 4)} if table.width == 5 else {}),
                }
                for name in names
            ],
        }

    def build(self, scene: "Scene") -> None:
        """Add the chart to the scene and animate it."""
        from manim import (
            DOWN,
            LEFT,
            RIGHT,
            UP,
            AnimationGroup,
            Create,
            Dot,
            Group,
            Line,
            UpdateFromAlphaFunc,
            ValueTracker,
            VGroup,
            VMobject,
            linear,
        )

        from vizreel.render import elements

        chart = self.chart
        assert isinstance(chart, ScatterRaceChart)
        theme, layout = self.theme, self.layout
        fonts, sizes, colors, motion = theme.fonts, theme.sizes, theme.colors, theme.motion
        ease = elements.easing(theme)
        content = layout.content
        gap = stack_gap(sizes.label, sizes.label)
        count = len(chart.periods)
        names = [series.name for series in chart.series]
        followed = chart.highlight.series if chart.highlight else None
        point_colors = race_colors(
            names, followed, chart.colors, colors.brand, colors.accent, colors.highlight
        )
        backdrop = colors.surface if layout.panel else colors.background

        # Each series is shown from its first period with both values to its last.
        spans = [
            visible_span(
                [x if y is not None else None for x, y in zip(item.x, item.y, strict=True)]
            )
            for item in chart.series
        ]
        xs = [fill_gaps(item.x, None) for item in chart.series]
        ys = [fill_gaps(item.y, None) for item in chart.series]
        size_values = [
            fill_gaps(item.size, None) if item.size is not None else None for item in chart.series
        ]
        largest_size = max(
            (value for values in size_values if values for value in values if value is not None),
            default=0.0,
        )
        x_extents = running_extents(xs)
        y_extents = running_extents(ys)

        header = elements.header(chart.title, chart.subtitle, theme, layout)
        source = elements.source_line(chart.source, theme, layout)

        period_texts = [
            elements.number_text(
                period, fonts.numbers, sizes.big_number * PERIOD_SCALE, colors.muted
            )
            for period in chart.periods
        ]
        period_width = max(text.width for text in period_texts)
        captions = [
            elements.wrapped_block(
                caption.text,
                fonts.body,
                sizes.label,
                colors.text,
                content.width - period_width - gap * 2,
                "the caption",
                "left",
            ).mobject
            for caption in chart.captions
        ]
        band = max([max(text.height for text in period_texts), *(c.height for c in captions)])
        caption_starts = [float(chart.periods.index(caption.period)) for caption in chart.captions]

        tick_cache: dict[tuple[str, float], VMobject] = {}

        def tick_label(axis: str, tick: float) -> "VMobject":
            if (axis, tick) not in tick_cache:
                number = chart.x_number if axis == "x" else chart.y_number
                [text] = format_numbers([tick], number, locale=self.locale)
                tick_cache[axis, tick] = elements.number_text(
                    text, fonts.body, sizes.label, colors.muted
                )
            return tick_cache[axis, tick]

        full_x = value_axis([x_extents[-1][0], x_extents[-1][1] * HEADROOM])
        full_y = value_axis([y_extents[-1][0], y_extents[-1][1] * HEADROOM])
        widest_y_tick = max(tick_label("y", tick).width for tick in full_y.ticks)
        tallest_x_tick = max(tick_label("x", tick).height for tick in full_x.ticks)
        x_title = elements.text(chart.x_title, fonts.body, sizes.label, colors.muted)
        y_title = elements.text(chart.y_title, fonts.body, sizes.label, colors.muted)
        largest_radius = px(sizes.value) * LARGEST_POINT
        smallest_radius = px(sizes.dot) / 2
        plot = Box(
            content.left + widest_y_tick + gap,
            content.bottom + x_title.height + tallest_x_tick + gap * 2,
            content.right - largest_radius,
            content.top - band - gap * 2 - y_title.height - gap,
        )
        if min(plot.width, plot.height) < px(MIN_PLOT_PX):
            raise RenderError(
                "not enough room for the scatter race; shorten the axis titles or the title"
            )
        x_title.align_to((plot.right, content.bottom, 0.0), DOWN + RIGHT)
        y_title.align_to((content.left, plot.top + gap + y_title.height, 0.0), UP + LEFT)
        label_names = set(chart.labeled())
        name_texts = [
            elements.text(name, fonts.body, sizes.label, colors.text)
            if name in label_names
            else None
            for name in names
        ]
        label_bounds = Box(plot.left, plot.bottom, content.right, plot.top)

        def extents(
            position: float, axis: list[tuple[float, float]], values: list[list[float | None]]
        ) -> tuple[float, float]:
            low, high = axis[min(int(position), count - 1)]
            for index, series in enumerate(values):
                span = spans[index]
                if span is not None and span[0] <= position <= span[1]:
                    value = value_at(series[span[0] : span[1] + 1], position - span[0])  # type: ignore[arg-type]
                    low, high = min(low, value), max(high, value)
            return low, high

        def scales(
            position: float,
        ) -> tuple[LinearScale, LinearScale, tuple[float, float], tuple[float, float]]:
            x_low, x_high = extents(position, x_extents, xs)
            y_low, y_high = extents(position, y_extents, ys)
            x_range = (x_low, (x_high or 1.0) * HEADROOM)
            y_range = (y_low, (y_high or 1.0) * HEADROOM)
            x_of = LinearScale(x_range, (plot.left, plot.right))
            y_of = LinearScale(y_range, (plot.bottom, plot.top))
            return x_of, y_of, x_range, y_range

        def points_at(position: float, grown: float) -> list[Point | None]:
            x_of, y_of, _, _ = scales(position)
            result: list[Point | None] = []
            for index in range(len(names)):
                span = spans[index]
                if span is None or not span[0] <= position <= span[1]:
                    result.append(None)
                    continue
                local = position - span[0]
                x = value_at(xs[index][span[0] : span[1] + 1], local)  # type: ignore[arg-type]
                y = value_at(ys[index][span[0] : span[1] + 1], local)  # type: ignore[arg-type]
                sizes_now = size_values[index]
                size = (
                    value_at(sizes_now[span[0] : span[1] + 1], local)  # type: ignore[arg-type]
                    if sizes_now is not None and None not in sizes_now[span[0] : span[1] + 1]
                    else None
                )
                radius = point_radius(size, largest_size, smallest_radius, largest_radius) * grown
                result.append(Point(x_of(x), y_of(y), radius))
            return result

        def label_order(points: list[Point | None]) -> list[int]:
            return sorted(
                range(len(names)),
                key=lambda index: (
                    names[index] != followed,
                    -(points[index].radius if points[index] is not None else 0.0),  # type: ignore[union-attr]
                ),
            )

        def labels_at(position: float) -> list[tuple[int, Box, float]]:
            name_sizes = [
                (text.width, text.height) if text is not None else None for text in name_texts
            ]
            now = points_at(position, 1.0)
            boxes = place_labels(now, name_sizes, label_order(now), label_bounds, gap / 2)
            placed = []
            for index, box in enumerate(boxes):
                if box is None:
                    continue
                looks = (
                    [
                        place_labels(
                            before := points_at(
                                max(position - LABEL_FADE * step / LABEL_LOOKS, 0.0), 1.0
                            ),
                            name_sizes,
                            label_order(before),
                            label_bounds,
                            gap / 2,
                        )[index]
                        is not None
                        for step in range(1, LABEL_LOOKS + 1)
                    ]
                    if position > 0
                    else [True] * LABEL_LOOKS
                )
                opacity = (1 + sum(looks)) / (LABEL_LOOKS + 1)
                placed.append((index, box, opacity))
            return placed

        def grid_at(position: float) -> "Mobject":
            x_of, y_of, x_range, y_range = scales(position)
            group = VGroup()
            for tick in value_axis(list(y_range)).ticks:
                if not y_range[0] - 1e-9 <= tick <= y_range[1] + 1e-9:
                    continue
                y = y_of(tick)
                group.add(
                    Line(
                        (plot.left, y, 0.0),
                        (plot.right, y, 0.0),
                        color=colors.grid,
                        stroke_width=stroke_width(sizes.grid_line),
                    ),
                    tick_label("y", tick).move_to(
                        (plot.left - gap - tick_label("y", tick).width / 2, y, 0.0)
                    ),
                )
            x_ticks = [
                tick
                for tick in value_axis(list(x_range)).ticks
                if x_range[0] - 1e-9 <= tick <= x_range[1] + 1e-9
            ]
            # Labels that would touch are thinned, as on a line chart; every grid line stays.
            shown = set(
                thin_labels(
                    [x_of(tick) for tick in x_ticks],
                    [tick_label("x", tick).width for tick in x_ticks],
                    gap * 2,
                )
            )
            for index, tick in enumerate(x_ticks):
                x = x_of(tick)
                group.add(
                    Line(
                        (x, plot.bottom, 0.0),
                        (x, plot.top, 0.0),
                        color=colors.grid,
                        stroke_width=stroke_width(sizes.grid_line),
                    )
                )
                if index in shown:
                    label = tick_label("x", tick)
                    group.add(label.move_to((x, plot.bottom - gap - label.height / 2, 0.0)))
            return group

        def race_frame(position: float, grown: float, with_labels: bool) -> "Mobject":
            group = Group(grid_at(position))
            now = points_at(position, grown)
            if chart.trail and followed is not None:
                group.add(trail_at(position))
            drawn = sorted(
                (
                    index
                    for index, point in enumerate(now)
                    if point is not None and point.radius > 0
                ),
                key=lambda index: (names[index] == followed, -now[index].radius),  # type: ignore[union-attr]
            )
            for index in drawn:
                point = now[index]
                assert point is not None
                group.add(
                    Dot(
                        (point.x, point.y, 0.0),
                        radius=point.radius,
                        fill_color=elements.color(point_colors[index]),
                        fill_opacity=POINT_OPACITY,
                        stroke_color=elements.color(backdrop),
                        stroke_width=stroke_width(sizes.grid_line),
                    )
                )
            if with_labels:
                for index, box, opacity in labels_at(position):
                    text = name_texts[index]
                    assert text is not None
                    group.add(text.set_opacity(opacity).move_to((*box.center, 0.0)))
                text = period_texts[min(max(round(position), 0), count - 1)]
                group.add(text.align_to((content.right, content.top, 0.0), UP + RIGHT))
                shown = caption_at(caption_starts, position)
                if shown is not None and shown[1] > 0:
                    caption = captions[shown[0]].set_opacity(shown[1])
                    caption.align_to((content.left, 0.0, 0.0), LEFT)
                    group.add(caption.set_y(content.top - band / 2))
            return group

        def trail_at(position: float) -> "VMobject":
            index = names.index(followed)  # type: ignore[arg-type]
            span = spans[index]
            path = VMobject(
                stroke_color=elements.color(colors.highlight),
                stroke_width=stroke_width(sizes.line),
                stroke_opacity=TRAIL_OPACITY,
            )
            if span is None or position < span[0]:
                return path
            steps = [float(step) for step in range(span[0], min(int(position), span[1]) + 1)]
            steps.append(min(position, float(span[1])))
            corners = []
            x_of, y_of, _, _ = scales(position)
            for step in steps:
                local = step - span[0]
                x = value_at(xs[index][span[0] : span[1] + 1], local)  # type: ignore[arg-type]
                y = value_at(ys[index][span[0] : span[1] + 1], local)  # type: ignore[arg-type]
                corners.append((x_of(x), y_of(y), 0.0))
            if len(corners) > 1:
                path.set_points_as_corners(corners)
            return path

        intro = (motion.title_fade if len(header) else 0.0) + motion.structure
        race_seconds = chart.duration - intro - motion.hold
        check_race_time(race_seconds, count, chart.duration)
        check_caption_times(
            [
                (caption.text, start)
                for caption, start in zip(chart.captions, caption_starts, strict=True)
            ],
            intro,
            race_seconds,
            count,
            chart.duration,
        )
        check_reading_time(
            [(text, 0.0) for text in (chart.title, chart.subtitle, chart.source) if text],
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

        # The axes and their titles appear while the points grow to their first places.
        grid = grid_at(0.0)
        axes = Group(x_title, y_title, *(part for part in grid if not isinstance(part, Line)))
        lines = VGroup(*(part for part in grid if isinstance(part, Line)))
        growth = ValueTracker(0.0)

        def advance(tracker: ValueTracker, alpha: float) -> None:
            tracker.set_value(alpha)

        growing = elements.redrawn(
            lambda: Group(*race_frame(0.0, ease(growth.get_value()), False)[1:])
        )
        scene.add(growing)
        scene.play(
            AnimationGroup(
                *opening,
                Create(lines, run_time=motion.structure, rate_func=ease),
                elements.appear(axes, theme, run_time=motion.structure, rate_func=ease),
                UpdateFromAlphaFunc(growth, advance, run_time=motion.structure, rate_func=linear),  # type: ignore[arg-type]
            ),
            run_time=motion.structure,
        )
        # The race draws the grid and ticks from here on; the titles stay as they are.
        scene.remove(growing, lines, axes)
        scene.add(x_title, y_title)

        seconds = ValueTracker(0.0)
        racing = elements.redrawn(
            lambda: race_frame(race_position(seconds.get_value(), race_seconds, count), 1.0, True)
        )
        scene.add(racing)
        scene.play(seconds.animate.set_value(race_seconds), run_time=race_seconds, rate_func=linear)
        racing.clear_updaters()
        scene.wait(motion.hold)
