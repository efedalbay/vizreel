"""Lines that race through many periods."""

from typing import TYPE_CHECKING, Any

from vizreel.charts._race import check_race_time, fill_gaps, race_position
from vizreel.charts.base import ChartType, check_reading_time
from vizreel.charts.line import END_LABEL_ROOM, MIN_PLOT_PX, drawn, runs
from vizreel.charts.registry import register
from vizreel.errors import RenderError
from vizreel.format.numbers import decimals_for, format_number, format_numbers
from vizreel.render.layout import Box, px, stack_gap, stroke_width
from vizreel.render.scales import (
    LinearScale,
    point_positions,
    spread_labels,
    thin_labels,
    value_axis,
)
from vizreel.spec.data import Table
from vizreel.spec.models import LineRaceChart

if TYPE_CHECKING:
    from manim import Animation, Scene, VMobject

HEADROOM = 1.1
"""The top of the vertical axis, as a multiple of the largest value drawn so far."""


def race_gaps(values: list[float | None]) -> list[float | None]:
    """Fill the gaps inside a series.

    Before its first value and after its last, the series is not drawn.
    """
    known = [index for index, value in enumerate(values) if value is not None]
    filled = fill_gaps(values, None)
    return [value if index <= known[-1] else None for index, value in enumerate(filled)]


def axis_top(drawn_max: float) -> float:
    """The top of the vertical axis when the largest value drawn so far is `drawn_max`."""
    return (drawn_max or 1.0) * HEADROOM


@register
class LineRaceChartType(ChartType):
    """Lines that draw through many periods, the vertical axis growing to keep them in frame.

    Grid lines and period labels appear first. Then one pen draws every line from left to
    right at one pace, slowing to a stop on the last period, each line with its name and
    value riding its tip. The vertical axis grows with the largest value drawn so far. The
    lines are in the theme's series colors; a followed series is in the highlight color while
    the others are muted.
    """

    name = "line-race"
    model = LineRaceChart
    template = """\
- id: users-race                   # unique; lowercase letters, digits and hyphens
  type: line-race
  title: Northwind users by platform
  periods: ["2019", "2020", "2021", "2022", "2023"]   # in order; quote years
  series:                          # one to six; one value per period, null for a gap
    - { name: Web, values: [1.2, 1.9, 2.4, 2.8, 3.0] }
    - { name: Mobile, values: [0.4, 1.1, 2.2, 3.6, 4.9] }
  number: { suffix: "M" }
  # highlight: { series: Mobile }  # optional: the series drawn in the highlight color
  # source: "Source: example data" # optional
  # duration: 15                   # optional: seconds, at least 2
"""

    @classmethod
    def from_table(cls, table: Table, chart: dict[str, Any]) -> dict[str, Any]:
        """Read the periods from the first column and a series from each other column.

        A series is named by its column's header; an empty cell leaves a gap.
        """
        if table.width < 2:
            table.require_width(2, "the periods and a series")
        rows = range(len(table.rows))
        return {
            "periods": [table.text(row, 0) for row in rows],
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
            LEFT,
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
        assert isinstance(chart, LineRaceChart)
        theme, layout = self.theme, self.layout
        fonts, sizes, colors, motion = theme.fonts, theme.sizes, theme.colors, theme.motion
        ease = elements.easing(theme)
        content = layout.content
        gap = stack_gap(sizes.label, sizes.label)
        count = len(chart.periods)
        dot_radius = px(sizes.dot) / 2
        values = [race_gaps(series.values) for series in chart.series]
        followed = chart.highlight.series if chart.highlight else None
        if followed is None and len(chart.series) > len(colors.series):
            raise RenderError(
                f"{len(chart.series)} lines need as many colors and the theme has "
                f"{len(colors.series)}; follow one with highlight, which mutes the others"
            )
        line_colors = [
            (colors.highlight if series.name == followed else colors.muted)
            if followed
            else colors.series[index]
            for index, series in enumerate(chart.series)
        ]

        header = elements.header(chart.title, chart.subtitle, theme, layout)
        source = elements.source_line(chart.source, theme, layout)

        every_value = [value for series in values for value in series if value is not None]
        value_format = chart.number.model_copy(
            update={"decimals": decimals_for(every_value, chart.number)}
        )
        glyphs = NumberGlyphs(fonts.numbers, sizes.value, colors.text)
        names = [
            elements.text(series.name, fonts.body, sizes.label, colors.text)
            for series in chart.series
        ]

        # In a narrow frame the name goes above the value, leaving the lines more width.
        narrow = layout.vertical or layout.square

        def end_label(index: int, value: float) -> "VMobject":
            number = glyphs(format_number(value, value_format, locale=self.locale))
            name = names[index]
            if narrow:
                return VGroup(name, number).arrange(DOWN, aligned_edge=LEFT, buff=gap / 2)
            label = VGroup(name, number).arrange(RIGHT, buff=gap)
            # Figures sit on the baseline, so the name goes on the baseline of the number.
            name_baseline = elements.baseline(
                name, chart.series[index].name, fonts.body, sizes.label
            )
            name.shift((0.0, number.get_bottom()[1] - name_baseline, 0.0))
            return label

        largest = max(every_value)
        full_axis = value_axis([0.0, axis_top(largest)], low=0.0)
        tick_cache: dict[float, VMobject] = {}

        def tick_label(tick: float) -> "VMobject":
            if tick not in tick_cache:
                [text] = format_numbers([tick], chart.number, locale=self.locale)
                tick_cache[tick] = elements.number_text(text, fonts.body, sizes.label, colors.muted)
            return tick_cache[tick]

        widest_tick = max(tick_label(tick).width for tick in full_axis.ticks)
        x_blocks = [
            elements.text_block(text, fonts.body, sizes.label, colors.muted)
            for text in chart.periods
        ]
        x_labels = [block.mobject for block in x_blocks]
        widest_end = max(end_label(index, largest).width for index in range(len(chart.series)))
        tallest_tick = max(tick_label(tick).height for tick in full_axis.ticks)
        x_label_gap = gap + tallest_tick / 2
        plot = Box(
            content.left + widest_tick + gap,
            content.bottom + max(block.height for block in x_blocks) + x_label_gap,
            content.right - dot_radius - gap - widest_end * END_LABEL_ROOM,
            content.top - glyphs("0").height / 2,
        )
        if min(plot.width, plot.height) < px(MIN_PLOT_PX):
            raise RenderError(
                "not enough room for the line race; shorten the series names or the title"
            )
        xs = point_positions(
            count, plot.left + x_labels[0].width / 2, plot.right - x_labels[-1].width / 2
        )
        shown_x = thin_labels(xs, [label.width for label in x_labels], gap * 2)
        for index in shown_x:
            x_blocks[index].move_top_to(plot.bottom - x_label_gap)
            x_labels[index].set_x(xs[index])
        series_runs = [runs(xs, series) for series in values]

        def x_at(position: float) -> float:
            return xs[0] + (xs[-1] - xs[0]) * position / (count - 1)

        def drawn_max(x_cut: float) -> float:
            return max(
                (
                    value
                    for series in series_runs
                    for run in drawn(series, x_cut)
                    for _, value in run
                ),
                default=0.0,
            )

        def race_frame(position: float) -> "VMobject":
            x_cut = x_at(position)
            top = axis_top(drawn_max(x_cut))
            y_of = LinearScale((0.0, top), (plot.bottom, plot.top))
            group = VGroup()
            for tick in value_axis([0.0, top], low=0.0).ticks:
                if tick > top + 1e-9:
                    continue
                y = y_of(tick)
                group.add(
                    Line(
                        (plot.left, y, 0.0),
                        (plot.right, y, 0.0),
                        color=colors.grid,
                        stroke_width=stroke_width(sizes.grid_line),
                    ),
                    tick_label(tick).move_to(
                        (plot.left - gap - tick_label(tick).width / 2, y, 0.0)
                    ),
                )
            tips = []
            for index, series in enumerate(series_runs):
                parts = drawn(series, x_cut)
                for part in parts:
                    points = [(x, y_of(value), 0.0) for x, value in part]
                    if len(points) > 1:
                        path = VMobject(
                            stroke_color=line_colors[index], stroke_width=stroke_width(sizes.line)
                        )
                        path.set_points_as_corners(points)
                        group.add(path)
                if parts and x_cut <= series[-1][-1][0] + 1e-9:
                    tips.append((index, parts[-1][-1]))
                elif parts:
                    tips.append((index, series[-1][-1]))
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
                raise RenderError("the labels of the lines do not fit; use fewer series") from None
            for (index, (x, value)), label, center in zip(tips, labels, centers, strict=True):
                group.add(Dot((x, y_of(value), 0.0), radius=dot_radius, color=line_colors[index]))
                group.add(label.move_to((x + dot_radius + gap + label.width / 2, center, 0.0)))
            return group

        intro = (motion.title_fade if len(header) else 0.0) + motion.structure
        race_seconds = chart.duration - intro - motion.hold
        check_race_time(race_seconds, count, chart.duration)
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

        # The grid of the first frame draws, and the axis labels appear.
        first = race_frame(0.0)
        grid = VGroup(*(part for part in first if isinstance(part, Line)))
        ticks = [part for part in first if part in tick_cache.values()]
        axis_labels = VGroup(*ticks, *(x_labels[index] for index in shown_x))
        scene.play(
            AnimationGroup(
                *opening,
                Create(grid, run_time=motion.structure, rate_func=ease),
                elements.appear(axis_labels, theme, run_time=motion.structure, rate_func=ease),
            ),
            run_time=motion.structure,
        )
        scene.remove(grid, *ticks)

        seconds = ValueTracker(0.0)
        racing = elements.redrawn(
            lambda: race_frame(race_position(seconds.get_value(), race_seconds, count))
        )
        scene.add(racing)
        scene.play(seconds.animate.set_value(race_seconds), run_time=race_seconds, rate_func=linear)
        racing.clear_updaters()
        scene.wait(motion.hold)
