"""Big number card."""

from itertools import pairwise
from typing import TYPE_CHECKING

from vizreel.charts.base import ChartType, check_reading_time, split_duration
from vizreel.charts.registry import register
from vizreel.format.numbers import decimals_for, format_number
from vizreel.render.layout import stack_gap
from vizreel.spec.models import StatChart
from vizreel.themes.models import FontStyle

if TYPE_CHECKING:
    from manim import Animation, Scene, VMobject


@register
class StatChartType(ChartType):
    """A single number that counts up (or down) to its value.

    Title, subtitle, number, label and source are stacked in one centered column.
    The header fades in first; then the number counts while the label and source fade in.
    """

    name = "stat"
    model = StatChart
    template = """\
- id: customers                    # unique; lowercase letters, digits and hyphens
  type: stat
  value: 48200                     # the number to count to
  label: Northwind customers       # optional: line under the number
  number: { compact: true }        # optional: prefix, suffix, decimals, compact
  # start: 0                       # optional: value the count starts from
  # trend: up                      # optional: up, down or none; colors the number
  # title: Customers in 2022       # optional
  # subtitle: All regions          # optional
  # source: "Source: example data" # optional: short, shown at the bottom
  # duration: 3                    # optional: seconds, at least 2
"""

    def build(self, scene: "Scene") -> None:
        """Add the card to the scene and animate it."""
        from manim import (
            AnimationGroup,
            FadeIn,
            UpdateFromAlphaFunc,
            ValueTracker,
            VGroup,
            always_redraw,
        )

        from vizreel.render import elements
        from vizreel.render.numbers_text import NumberGlyphs

        chart = self.chart
        assert isinstance(chart, StatChart)
        fonts, sizes, colors, motion = (
            self.theme.fonts,
            self.theme.sizes,
            self.theme.colors,
            self.theme.motion,
        )
        ease = elements.easing(self.theme)

        def line(
            content: str | None, style: FontStyle, size: float, color: str
        ) -> list[tuple["VMobject", float]]:
            if not content:
                return []
            block = elements.wrapped_block(
                content, style, size, color, self.layout.inner.width, "the stat card text", "center"
            )
            return [(block.mobject, size)]

        number_color = {"up": colors.positive, "down": colors.negative, "none": colors.text}
        number_format = chart.number.model_copy(
            update={"decimals": decimals_for([chart.start, chart.value], chart.number)}
        )

        glyphs = NumberGlyphs(fonts.numbers, sizes.big_number, number_color[chart.trend])

        def number(value: float) -> "VMobject":
            return glyphs(format_number(value, number_format))

        header = line(chart.title, fonts.heading, sizes.title, colors.text) + line(
            chart.subtitle, fonts.body, sizes.subtitle, colors.muted
        )
        source = line(chart.source, fonts.body, sizes.caption, colors.muted)
        footer = line(chart.label, fonts.body, sizes.label, colors.muted) + source
        final_number = number(chart.value)
        widest_number = max(final_number, number(chart.start), key=lambda mobject: mobject.width)
        lines = [*header, (final_number, sizes.big_number), *footer]

        elements.check_fits(widest_number, self.layout.inner, "the number")
        # The header and the source line are set apart; the number and its label stay close.
        band_breaks = {len(header) - 1 if header else -1, len(lines) - 2 if source else -1}
        gaps = [
            self.layout.band_gap if index in band_breaks else stack_gap(size, below)
            for index, ((_, size), (_, below)) in enumerate(pairwise(lines))
        ]
        column = elements.stack(
            [(mobject, gap) for (mobject, _), gap in zip(lines, [*gaps, 0.0], strict=True)],
            self.layout.content.center,
        )
        number_center = final_number.get_center()

        header_group = VGroup(*(mobject for mobject, _ in header))
        footer_group = VGroup(*(mobject for mobject, _ in footer))
        phases = split_duration(
            chart.duration,
            intro=motion.title_fade if header else 0.0,
            highlight=0,
            hold=motion.hold,
        )
        check_reading_time(
            [(text, 0.0) for text in (chart.title, chart.subtitle) if text]
            + [(text, phases.main_start) for text in (chart.label, chart.source) if text],
            chart.duration,
        )

        opening: list[Animation] = []
        if self.layout.panel:
            widest_in_place = widest_number.copy().move_to(number_center)
            card_box = self.layout.panel_around(elements.bounds(VGroup(column, widest_in_place)))
            card = elements.panel(card_box, self.theme)
            opening.append(FadeIn(card, run_time=motion.title_fade, rate_func=ease))
        if header:
            opening.append(FadeIn(header_group, run_time=motion.title_fade, rate_func=ease))
            scene.play(AnimationGroup(*opening), run_time=phases.intro)
            opening = []

        tracker = ValueTracker(chart.start)
        counting = always_redraw(lambda: number(tracker.get_value()).move_to(number_center))
        scene.add(counting)
        start, end = chart.start, chart.value

        def count_to(mobject: ValueTracker, alpha: float) -> None:
            mobject.set_value(start + (end - start) * alpha)

        # Manim calls the update function with (mobject, alpha) but types it with one argument.
        count = UpdateFromAlphaFunc(tracker, count_to, run_time=phases.main, rate_func=ease)  # type: ignore[arg-type]
        reveal: list[Animation] = [*opening, count]
        if footer:
            fade = min(motion.title_fade, phases.main)
            reveal.append(FadeIn(footer_group, run_time=fade, rate_func=ease))
        scene.play(AnimationGroup(*reveal), run_time=phases.main)

        counting.clear_updaters()
        scene.remove(counting)
        scene.add(final_number)
        scene.wait(phases.hold)
