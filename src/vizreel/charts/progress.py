"""How far a value has come toward a goal."""

from typing import TYPE_CHECKING

from vizreel.charts.base import (
    ChartType,
    check_reading_time,
    count_samples,
    fitting_number_size,
    split_duration,
)
from vizreel.charts.registry import register
from vizreel.errors import RenderError
from vizreel.format.numbers import decimals_for, format_number, format_percent
from vizreel.render.layout import px, stack_gap
from vizreel.spec.models import ProgressChart

if TYPE_CHECKING:
    from manim import Animation, Scene, VMobject

BAR_WIDTH_SHARE = 0.75
"""Share of the content width the bar spans in a landscape frame; narrower frames use it all."""
RING_NUMBER_SCALE = 2 / 3
"""Size of the percent in the middle of the ring, as a share of the theme's big number size."""
INNER_RADIUS = 0.8
"""Inner radius of the ring, as a share of its outer radius."""
CENTER_FILL = 0.8
"""Share of the ring's inner width that the percent may use."""
MIN_RADIUS_PX = 120
"""Least outer radius of the ring, in pixels at 1080p."""


def filled_share(value: float, goal: float) -> float:
    """How much of the bar or ring fills: the value's share of the goal, at most all of it."""
    return min(value / goal, 1.0)


@register
class ProgressChartType(ChartType):
    """A bar or a ring that fills toward a goal while its percent counts up.

    The bar fills from the left under a big percent; the ring fills clockwise from the top,
    with the percent in its middle. Under either, the value and the goal count up, then the
    label. The fill is in the highlight color, on a track in the grid color.
    """

    name = "progress"
    model = ProgressChart
    template = """\
- id: fundraiser                   # unique; lowercase letters, digits and hyphens
  type: progress
  value: 68000                     # how far it has come
  goal: 100000                     # where it is going
  label: raised for the new library  # optional: line under the chart
  number: { prefix: "$", compact: true }  # optional: format of the value and goal
  # style: ring                    # optional: bar or ring
  # title: Northwind's fundraiser  # optional
  # source: "Source: example data" # optional
  # duration: 4                    # optional: seconds, at least 2
"""

    def build(self, scene: "Scene") -> None:
        """Add the chart to the scene and animate it."""
        from manim import (
            LEFT,
            PI,
            TAU,
            AnimationGroup,
            AnnularSector,
            Rectangle,
            UpdateFromAlphaFunc,
            ValueTracker,
            VGroup,
            VMobject,
        )

        from vizreel.render import elements
        from vizreel.render.numbers_text import NumberGlyphs

        chart = self.chart
        assert isinstance(chart, ProgressChart)
        theme, layout = self.theme, self.layout
        fonts, sizes, colors, motion = theme.fonts, theme.sizes, theme.colors, theme.motion
        ease = elements.easing(theme)
        content = layout.content
        percent = chart.value / chart.goal * 100
        filled = filled_share(chart.value, chart.goal)
        ring = chart.style == "ring"

        header = elements.header(chart.title, chart.subtitle, theme, layout)
        source = elements.source_line(chart.source, theme, layout)

        amount_format = chart.number.model_copy(
            update={"decimals": decimals_for([0, chart.value, chart.goal], chart.number)}
        )
        amount_glyphs = NumberGlyphs(fonts.numbers, sizes.value, colors.muted)

        def amount_text(progress: float) -> "VMobject":
            value = format_number(
                chart.value * progress, amount_format, locale=self.locale, unit_of=chart.value
            )
            goal = format_number(chart.goal, amount_format, locale=self.locale)
            return amount_glyphs(f"{value} / {goal}")

        final_amount = amount_text(1.0)
        elements.check_fits(final_amount, content, "the value and goal")
        label = None
        if chart.label:
            label = elements.wrapped_block(
                chart.label,
                fonts.body,
                sizes.label,
                colors.muted,
                content.width,
                "the label",
                "center",
            ).mobject
        below_gap = stack_gap(sizes.value, sizes.label)
        below = final_amount.height + (label.height + below_gap if label is not None else 0)

        # The percent is sized for the widest text of its count, like the big number of a stat.
        percents = [
            format_percent(value, locale=self.locale) for value in count_samples(0, percent)
        ]
        start_size = sizes.big_number * (RING_NUMBER_SCALE if ring else 1)
        at_start_size = NumberGlyphs(fonts.numbers, start_size, colors.text, sizes.affix_scale)
        widest = max(at_start_size(text).width for text in percents)

        if ring:
            gap = stack_gap(sizes.value, sizes.value) * 2
            radius = min(content.width / 2, (content.height - gap - below) / 2)
            if radius < px(MIN_RADIUS_PX):
                raise RenderError("not enough room for the ring; shorten the title or the label")
            inner = radius * INNER_RADIUS
            room = 2 * inner * CENTER_FILL
        else:
            gap = px(sizes.value)
            bar_width = (
                content.width * BAR_WIDTH_SHARE
                if not (layout.vertical or layout.square)
                else content.width
            )
            room = content.width
        percent_size = fitting_number_size(start_size, widest, room, "the percent")
        percent_glyphs = NumberGlyphs(fonts.numbers, percent_size, colors.text, sizes.affix_scale)

        def percent_text(progress: float) -> "VMobject":
            return percent_glyphs(format_percent(percent * progress, locale=self.locale))

        final_percent = percent_text(1.0)
        items: list[tuple[VMobject, float]]
        if ring:
            track: VMobject = AnnularSector(
                inner_radius=inner,
                outer_radius=radius,
                angle=TAU,
                fill_color=elements.color(colors.grid),
                fill_opacity=1,
                stroke_width=0,
            )
            items = [(track, gap), (final_amount, below_gap)]
        else:
            bar_height = px(sizes.value)
            track = Rectangle(
                width=bar_width,
                height=bar_height,
                stroke_width=0,
                fill_color=elements.color(colors.grid),
                fill_opacity=1,
            )
            items = [(final_percent, gap), (track, gap), (final_amount, below_gap)]
        if label is not None:
            items.append((label, 0.0))
        elements.stack(items, content.center)
        if ring:
            final_percent.move_to(track.get_center())
        percent_center, amount_center = final_percent.get_center(), final_amount.get_center()
        track_center, track_left = track.get_center(), track.get_left()

        def fill_to(progress: float) -> "VMobject":
            share = filled * progress
            if share <= 0:
                # Manim keeps the z index of the first mobject an updater builds, so even the
                # empty fill goes above the track.
                return VMobject().set_z_index(1)
            fill: VMobject
            if ring:
                arc = AnnularSector(
                    inner_radius=inner,
                    outer_radius=radius,
                    start_angle=PI / 2,
                    angle=-TAU * share,
                    fill_color=elements.color(colors.highlight),
                    fill_opacity=1,
                    stroke_width=0,
                )
                # The arc is placed by its ring's center, not by its own bounding box.
                arc.shift(track_center - arc.arc_center)
                fill = arc
            else:
                fill = Rectangle(
                    width=bar_width * share,
                    height=bar_height,
                    stroke_width=0,
                    fill_color=elements.color(colors.highlight),
                    fill_opacity=1,
                ).move_to(track_left, aligned_edge=LEFT)
            return fill.set_z_index(1)

        intro = motion.title_fade if len(header) else 0.0
        phases = split_duration(chart.duration, intro=intro, highlight=0, hold=motion.hold)
        check_reading_time(
            [(text, 0.0) for text in (chart.title, chart.subtitle, chart.source) if text]
            + ([(chart.label, phases.main_start)] if chart.label else []),
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
            scene.play(AnimationGroup(*opening), run_time=phases.intro)
            opening = []

        tracker = ValueTracker(0.0)
        fill = elements.redrawn_shapes(lambda: fill_to(tracker.get_value()))
        counting_percent = elements.redrawn_shapes(
            lambda: percent_text(tracker.get_value()).move_to(percent_center)
        )
        counting_amount = elements.redrawn_shapes(
            lambda: amount_text(tracker.get_value()).move_to(amount_center)
        )
        scene.add(fill, counting_percent, counting_amount)

        def advance(mobject: ValueTracker, alpha: float) -> None:
            mobject.set_value(alpha)

        fade = min(motion.title_fade, phases.main)
        # Manim calls the update function with (mobject, alpha) but types it with one argument.
        count = UpdateFromAlphaFunc(tracker, advance, run_time=phases.main, rate_func=ease)  # type: ignore[arg-type]
        reveal: list[Animation] = [
            *opening,
            count,
            elements.appear(track, theme, run_time=fade, rate_func=ease),
        ]
        if label is not None:
            reveal.append(elements.appear(label, theme, run_time=fade, rate_func=ease))
        scene.play(AnimationGroup(*reveal), run_time=phases.main)

        for mobject in (fill, counting_percent, counting_amount):
            mobject.clear_updaters()
        scene.wait(phases.hold)
