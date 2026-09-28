"""A `progress` chart type for vizreel: how far a value has come toward a goal.

An example of a chart type in its own package. It uses only `vizreel.plugin` and
`vizreel.plugin.render`, the API vizreel keeps stable for chart types from other packages.
"""

from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field

from vizreel.plugin import (
    CHART_API_VERSION,
    BaseChart,
    ChartType,
    Duration,
    NumberFormat,
    Text,
    check_reading_time,
    count_samples,
    decimals_for,
    fitting_number_size,
    format_number,
    format_percent,
    px,
    split_duration,
    stack_gap,
)

if TYPE_CHECKING:
    from manim import Animation, Scene, VMobject

__version__ = "0.1.0"

BAR_WIDTH_SHARE = 0.75
"""Share of the content width the bar spans in a landscape frame; a vertical one uses it all."""


class ProgressChart(BaseChart):
    """How far a value has come toward a goal."""

    type: Literal["progress"]
    duration: Duration = 4
    """Total clip length in seconds, including the final hold. Minimum 2."""
    value: Annotated[float, Field(ge=0)]
    """How far it has come."""
    goal: Annotated[float, Field(gt=0)]
    """Where it is going. A value past the goal fills the bar and shows more than 100%."""
    label: Text | None = None
    """Line under the bar, e.g. "raised for the new library"."""
    number: NumberFormat = Field(default_factory=NumberFormat)
    """Formatting of the value and the goal."""


class ProgressChartType(ChartType):
    """A bar that fills toward a goal while its percent counts up."""

    name = "progress"
    model = ProgressChart
    api_version = CHART_API_VERSION
    template = """\
- id: fundraiser                   # unique; lowercase letters, digits and hyphens
  type: progress
  value: 68000                     # how far it has come
  goal: 100000                     # where it is going
  label: raised for the new library  # optional: line under the bar
  number: { prefix: "$", compact: true }  # optional: format of the value and goal
  # title: Northwind's fundraiser  # optional
  # source: "Source: example data" # optional
  # duration: 4                    # optional: seconds, at least 2
"""

    def build(self, scene: "Scene") -> None:
        """Add the chart to the scene and animate it."""
        from manim import (
            LEFT,
            AnimationGroup,
            FadeIn,
            Rectangle,
            UpdateFromAlphaFunc,
            ValueTracker,
            VGroup,
            always_redraw,
        )

        from vizreel.plugin import render

        chart = self.chart
        assert isinstance(chart, ProgressChart)
        theme, layout = self.theme, self.layout
        fonts, sizes, colors, motion = theme.fonts, theme.sizes, theme.colors, theme.motion
        ease = render.easing(theme)
        content = layout.content
        percent = chart.value / chart.goal * 100
        filled = min(chart.value / chart.goal, 1.0)

        header = render.header(chart.title, chart.subtitle, theme, layout)
        source = render.source_line(chart.source, theme, layout)

        # The percent is sized for the widest text of its count, like the big number of a stat.
        percents = [
            format_percent(value, locale=self.locale) for value in count_samples(0, percent)
        ]
        at_theme_size = render.NumberGlyphs(fonts.numbers, sizes.big_number, colors.text)
        percent_size = fitting_number_size(
            sizes.big_number,
            max(at_theme_size(text).width for text in percents),
            content.width,
            "the percent",
        )
        percent_glyphs = render.NumberGlyphs(fonts.numbers, percent_size, colors.text)

        amount_format = chart.number.model_copy(
            update={"decimals": decimals_for([0, chart.value, chart.goal], chart.number)}
        )
        amount_glyphs = render.NumberGlyphs(fonts.numbers, sizes.value, colors.muted)

        def percent_text(progress: float) -> "VMobject":
            return percent_glyphs(format_percent(percent * progress, locale=self.locale))

        def amount_text(progress: float) -> "VMobject":
            value = format_number(
                chart.value * progress, amount_format, locale=self.locale, unit_of=chart.value
            )
            goal = format_number(chart.goal, amount_format, locale=self.locale)
            return amount_glyphs(f"{value} / {goal}")

        bar_width = content.width if layout.vertical else content.width * BAR_WIDTH_SHARE
        bar_height = px(sizes.value)
        track = Rectangle(
            width=bar_width,
            height=bar_height,
            stroke_width=0,
            fill_color=render.color(colors.grid),
            fill_opacity=1,
        )
        final_percent, final_amount = percent_text(1.0), amount_text(1.0)
        render.check_fits(final_amount, content, "the value and goal")
        items: list[tuple[VMobject, float]] = [
            (final_percent, bar_height),
            (track, bar_height),
            (final_amount, stack_gap(sizes.value, sizes.label)),
        ]
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
            items.append((label, 0.0))
        render.stack(items, content.center)
        percent_center, amount_center = final_percent.get_center(), final_amount.get_center()
        track_left = track.get_left()

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
            opening.append(FadeIn(card, run_time=motion.title_fade, rate_func=ease))
        titles = VGroup(header, *([source] if source else []))
        if len(titles):
            opening.append(FadeIn(titles, run_time=motion.title_fade, rate_func=ease))
        if len(header):
            scene.play(AnimationGroup(*opening), run_time=phases.intro)
            opening = []

        tracker = ValueTracker(0.0)

        def fill_to(progress: float) -> "VMobject":
            width = bar_width * filled * progress
            fill = Rectangle(
                width=max(width, 1e-4),
                height=bar_height,
                stroke_width=0,
                fill_color=render.color(colors.highlight),
                fill_opacity=1 if width > 0 else 0,
            )
            # Above the track, which the reveal animation brings to the front.
            return fill.move_to(track_left, aligned_edge=LEFT).set_z_index(1)

        fill = always_redraw(lambda: fill_to(tracker.get_value()))
        counting_percent = always_redraw(
            lambda: percent_text(tracker.get_value()).move_to(percent_center)
        )
        counting_amount = always_redraw(
            lambda: amount_text(tracker.get_value()).move_to(amount_center)
        )
        scene.add(track.set_opacity(0), fill, counting_percent, counting_amount)

        def advance(mobject: ValueTracker, alpha: float) -> None:
            mobject.set_value(alpha)

        fade = min(motion.title_fade, phases.main)
        # Manim calls the update function with (mobject, alpha) but types it with one argument.
        count = UpdateFromAlphaFunc(tracker, advance, run_time=phases.main, rate_func=ease)  # type: ignore[arg-type]
        reveal: list[Animation] = [*opening, count, track.animate(run_time=fade).set_opacity(1)]
        if label is not None:
            reveal.append(FadeIn(label, run_time=fade, rate_func=ease))
        scene.play(AnimationGroup(*reveal), run_time=phases.main)

        for mobject in (fill, counting_percent, counting_amount):
            mobject.clear_updaters()
        scene.wait(phases.hold)
