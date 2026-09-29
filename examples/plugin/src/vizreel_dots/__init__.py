"""A `dots` chart type for vizreel: how many of a group, as a grid of dots that fill in.

An example of a chart type in its own package. It uses only `vizreel.plugin` and
`vizreel.plugin.render`, the API vizreel keeps stable for chart types from other packages.
"""

import math
from typing import TYPE_CHECKING, Annotated, Literal, Self

from pydantic import Field, model_validator

from vizreel.plugin import (
    CHART_API_VERSION,
    BaseChart,
    ChartType,
    Duration,
    NumberFormat,
    RenderError,
    Text,
    check_reading_time,
    count_samples,
    fitting_number_size,
    format_number,
    px,
    split_duration,
)

if TYPE_CHECKING:
    from manim import Animation, Scene, VMobject

__version__ = "0.1.0"

COLUMNS = 10
"""Most dots in a row of the grid."""
MAX_PITCH = 2.0
"""Most space between two dots' centers, as a multiple of the label size."""
DOT_FILL = 0.7
"""Share of the space between two dots' centers that a dot spans."""
MIN_DOT_PX = 12
"""Least diameter of a dot, in pixels at 1080p."""


class DotsChart(BaseChart):
    """How many of a group, as a grid of dots of which that many fill in."""

    type: Literal["dots"]
    duration: Duration = 4
    """Total clip length in seconds, including the final hold. Minimum 2."""
    value: Annotated[int, Field(ge=0)]
    """How many of the group: the dots that fill in."""
    total: Annotated[int, Field(ge=2, le=100)]
    """How many there are in all: the dots in the grid, 2 to 100."""
    label: Text | None = None
    """Line under the grid, e.g. "of 25 customers renew their plan"."""
    number: NumberFormat = Field(default_factory=NumberFormat)
    """Formatting of the value."""

    @model_validator(mode="after")
    def _check_value_within_total(self) -> Self:
        if self.value > self.total:
            raise ValueError(f"value {self.value} is more than total {self.total}")
        return self


def grid_shape(total: int) -> tuple[int, int]:
    """Return the columns and rows of a grid of `total` dots.

    The grid is as square as it can be, with at most `COLUMNS` dots in a row.
    """
    columns = min(math.ceil(math.sqrt(total)), COLUMNS)
    return columns, math.ceil(total / columns)


class DotsChartType(ChartType):
    """A number that counts up while as many dots of a grid fill in, one after another."""

    name = "dots"
    model = DotsChart
    api_version = CHART_API_VERSION
    template = """\
- id: renewals                     # unique; lowercase letters, digits and hyphens
  type: dots
  value: 18                        # how many of the group
  total: 25                        # how many in all: 2 to 100 dots
  label: of 25 customers renew their plan  # optional: line under the grid
  # title: Northwind renewals      # optional
  # source: "Source: example data" # optional
  # duration: 4                    # optional: seconds, at least 2
"""

    def build(self, scene: "Scene") -> None:
        """Add the chart to the scene and animate it."""
        from manim import AnimationGroup, Dot, ValueTracker, VGroup, always_redraw

        from vizreel.plugin import render

        chart = self.chart
        assert isinstance(chart, DotsChart)
        theme, layout = self.theme, self.layout
        fonts, sizes, colors, motion = theme.fonts, theme.sizes, theme.colors, theme.motion
        ease = render.easing(theme)
        content = layout.content
        gap = px(sizes.label)

        header = render.header(chart.title, chart.subtitle, theme, layout)
        source = render.source_line(chart.source, theme, layout)

        # The number is sized for the widest text of its count, like the big number of a stat.
        at_theme_size = render.NumberGlyphs(
            fonts.numbers, sizes.big_number, colors.text, sizes.affix_scale
        )
        widest = max(
            at_theme_size(
                format_number(value, chart.number, locale=self.locale, unit_of=chart.value)
            ).width
            for value in count_samples(0, chart.value)
        )
        number_size = fitting_number_size(sizes.big_number, widest, content.width, "the value")
        glyphs = render.NumberGlyphs(fonts.numbers, number_size, colors.text, sizes.affix_scale)

        def number_text(value: float) -> "VMobject":
            return glyphs(
                format_number(value, chart.number, locale=self.locale, unit_of=chart.value)
            )

        final_number = number_text(chart.value)
        label = None
        if chart.label:
            label = render.wrapped_block(
                chart.label,
                fonts.body,
                sizes.label,
                colors.muted,
                content.width,
                "the label",
                "center",
            ).mobject

        columns, rows = grid_shape(chart.total)
        grid_height = content.height - final_number.height - gap
        if label is not None:
            grid_height -= label.height + gap
        pitch = min(content.width / columns, grid_height / rows, px(sizes.label) * MAX_PITCH)
        if pitch * DOT_FILL < px(MIN_DOT_PX):
            raise RenderError("not enough room for the dots; shorten the title or the label")
        radius = pitch * DOT_FILL / 2

        def dot_at(index: int, color: str) -> "VMobject":
            row, column = divmod(index, columns)
            return Dot(
                (column * pitch, -row * pitch, 0.0), radius=radius, color=render.color(color)
            )

        grid = VGroup(*(dot_at(index, colors.grid) for index in range(chart.total)))
        items: list[tuple[VMobject, float]] = [(final_number, gap), (grid, gap)]
        if label is not None:
            items.append((label, 0.0))
        render.stack(items, content.center)
        number_center = final_number.get_center()
        grid_corner = grid[0].get_center()

        intro = motion.title_fade if len(header) else 0.0
        phases = split_duration(chart.duration, intro=intro, highlight=0, hold=motion.hold)
        check_reading_time(
            [(text, 0.0) for text in (chart.title, chart.subtitle, chart.source) if text]
            + ([(chart.label, phases.main_start)] if chart.label else []),
            chart.duration,
        )

        opening: list[Animation] = []
        if layout.panel:
            card = render.panel(layout.panel_around(layout.inner), theme)
            opening.append(render.appear(card, theme, run_time=motion.title_fade, rate_func=ease))
        titles = VGroup(header, *([source] if source else []))
        if len(titles):
            opening.append(render.appear(titles, theme, run_time=motion.title_fade, rate_func=ease))
        if len(header):
            scene.play(AnimationGroup(*opening), run_time=phases.intro)
            opening = []

        tracker = ValueTracker(0.0)

        def filled(progress: float) -> "VMobject":
            count = round(chart.value * ease(progress))
            dots = VGroup(*(dot_at(index, colors.highlight) for index in range(count)))
            # Above the grid, which its fade-in brings to the front.
            return dots.shift(grid_corner).set_z_index(1)

        def counting(progress: float) -> "VMobject":
            return number_text(chart.value * ease(progress)).move_to(number_center)

        filling = always_redraw(lambda: filled(tracker.get_value()))
        number = always_redraw(lambda: counting(tracker.get_value()))
        scene.add(filling, number)
        fade = min(motion.title_fade, phases.main)
        reveal: list[Animation] = [
            *opening,
            tracker.animate(run_time=phases.main, rate_func=lambda t: t).set_value(1.0),
            render.appear(grid, theme, run_time=fade, rate_func=ease),
        ]
        if label is not None:
            reveal.append(render.appear(label, theme, run_time=fade, rate_func=ease))
        scene.play(AnimationGroup(*reveal), run_time=phases.main)

        for mobject in (filling, number):
            mobject.clear_updaters()
        scene.wait(phases.hold)
