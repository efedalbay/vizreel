"""Big number card."""

from itertools import pairwise
from typing import TYPE_CHECKING

from vizreel.charts.base import (
    MIN_MAIN,
    ChartType,
    Phases,
    check_reading_time,
    count_samples,
    fitting_number_size,
    seconds_up,
    split_duration,
)
from vizreel.charts.registry import register
from vizreel.errors import RenderError
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
    # The card is already fitted: it surrounds the title, number, label and source it stacks.
    fits_to_content = False
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
            Rectangle,
            UpdateFromAlphaFunc,
            ValueTracker,
            VGroup,
        )

        from vizreel.render import elements
        from vizreel.render.layout import px
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

        counted = [
            format_number(value, number_format, locale=self.locale, unit_of=chart.value)
            for value in count_samples(chart.start, chart.value)
        ]
        # The size fits the widest text of the count, and stays the same while it counts.
        at_theme_size = NumberGlyphs(
            fonts.numbers, sizes.big_number, colors.text, sizes.affix_scale
        )
        number_size = fitting_number_size(
            sizes.big_number,
            max(at_theme_size(text).width for text in counted),
            self.layout.inner.width,
            "the number",
        )
        glyphs = NumberGlyphs(
            fonts.numbers, number_size, number_color[chart.trend], sizes.affix_scale
        )

        def number(value: float) -> "VMobject":
            return glyphs(
                format_number(value, number_format, locale=self.locale, unit_of=chart.value)
            )

        header = line(chart.title, fonts.heading, sizes.title, colors.text) + line(
            chart.subtitle, fonts.body, sizes.subtitle, colors.muted
        )
        source = line(chart.source, fonts.body, sizes.caption, colors.muted)
        footer = line(chart.label, fonts.body, sizes.label, colors.muted) + source
        final_number = number(chart.value)
        widest_number = max((glyphs(text) for text in counted), key=lambda mobject: mobject.width)
        lines = [*header, (final_number, number_size), *footer]
        logo = self.theme.logo
        if logo is not None:
            # Room for the theme's logo at the bottom of the card, which fits its content.
            lines.append(
                (Rectangle(width=1e-3, height=px(logo.height)).set_opacity(0), sizes.caption)
            )

        elements.check_fits(widest_number, self.layout.inner, "the number")
        intro = motion.title_fade if header else 0.0
        phases = split_duration(
            chart.duration, intro=intro, highlight=0, hold=motion.hold, reveal_max=motion.reveal_max
        )
        ring = self._ring_phases(intro)
        if ring is not None:
            phases = ring
        # The header and the source line are set apart; the number and its label stay close.
        band_breaks = {len(header) - 1 if header else -1, len(lines) - 2 if source else -1}
        gaps = [
            self.layout.band_gap if index in band_breaks else stack_gap(size, below)
            for index, ((_, size), (_, below)) in enumerate(pairwise(lines))
        ]
        if ring is not None:
            # The ring goes around the number alone: the lines above and below it move out of
            # its way.
            above, below = self._ring_overhang(final_number)
            at = len(header)
            if at > 0:
                gaps[at - 1] = max(gaps[at - 1], above)
            if at < len(gaps):
                gaps[at] = max(gaps[at], below)
        column = elements.stack(
            [(mobject, gap) for (mobject, _), gap in zip(lines, [*gaps, 0.0], strict=True)],
            self.layout.content.center,
        )
        number_center = final_number.get_center()

        header_group = VGroup(*(mobject for mobject, _ in header))
        footer_group = VGroup(*(mobject for mobject, _ in footer))
        check_reading_time(
            [(text, 0.0) for text in (chart.title, chart.subtitle) if text]
            + [(text, phases.main_start) for text in (chart.label, chart.source) if text],
            chart.duration,
        )

        # The ring goes around the number on the card, so the card holds it too.
        pen = (
            elements.highlight_ring(elements.bounds(final_number), self.theme)
            if ring is not None
            else None
        )
        widest_in_place = widest_number.copy().move_to(number_center)
        on_card = VGroup(column, widest_in_place, *([pen] if pen is not None else []))
        if logo is not None:
            box = elements.bounds(on_card)
            self.logo_corner = (box.right, box.bottom)
        opening: list[Animation] = []
        if self.layout.panel:
            card_box = self.layout.panel_around(elements.bounds(on_card))
            card = elements.panel(card_box, self.theme)
            opening.append(
                elements.appear(card, self.theme, run_time=motion.title_fade, rate_func=ease)
            )
        if header:
            opening.append(
                elements.appear(
                    header_group, self.theme, run_time=motion.title_fade, rate_func=ease
                )
            )
            scene.play(AnimationGroup(*opening), run_time=phases.intro, cue="title")
            opening = []

        tracker = ValueTracker(chart.start)
        counting = elements.redrawn_shapes(
            lambda: number(tracker.get_value()).move_to(number_center)
        )
        scene.add(counting)
        start, end = chart.start, chart.value

        def count_to(mobject: ValueTracker, alpha: float) -> None:
            mobject.set_value(start + (end - start) * alpha)

        # Manim calls the update function with (mobject, alpha) but types it with one argument.
        count = UpdateFromAlphaFunc(tracker, count_to, run_time=phases.main, rate_func=ease)  # type: ignore[arg-type]
        reveal: list[Animation] = [*opening, count]
        if footer:
            fade = min(motion.title_fade, phases.main)
            reveal.append(elements.appear(footer_group, self.theme, run_time=fade, rate_func=ease))
        scene.play(AnimationGroup(*reveal), run_time=phases.main, cue="reveal")

        counting.clear_updaters()
        scene.remove(counting)
        scene.add(final_number)
        if pen is not None:
            scene.play(
                elements.draw_ring(pen, rate_func=ease), run_time=phases.highlight, cue="highlight"
            )
        scene.wait(phases.hold)

    def _ring_overhang(self, number: "VMobject") -> tuple[float, float]:
        """How far the highlight ring reaches above and below the number, with room to spare.

        The gaps above and below the number are at least this, so the ring crosses no text.
        """
        from vizreel.render import elements
        from vizreel.render.layout import px

        sizes = self.theme.sizes
        pen = elements.highlight_ring(elements.bounds(number), self.theme)
        spare = px(sizes.line * elements.RING_STROKE) / 2 + stack_gap(sizes.caption, sizes.caption)
        above = float(pen.get_top()[1]) - float(number.get_top()[1]) + spare
        below = float(number.get_bottom()[1]) - float(pen.get_bottom()[1]) + spare
        return above, below

    def _ring_phases(self, intro: float) -> "Phases | None":
        """The phases with a beat for the theme's highlight ring after the count.

        None if the theme draws no ring, or if the duration leaves no time for one, which adds
        a warning: the clip keeps its duration.
        """
        motion = self.theme.motion
        if self.theme.highlight_mark != "ring":
            return None
        try:
            return split_duration(
                self.chart.duration,
                intro=intro,
                highlight=motion.highlight,
                hold=motion.hold,
                reveal_max=motion.reveal_max,
            )
        except RenderError:
            needed = intro + motion.highlight + motion.hold + MIN_MAIN
            self.warnings.append(
                f"duration {self.chart.duration:g}s leaves no time to draw the highlight ring "
                f"after the count, so the clip has none; it needs at least {seconds_up(needed)}s"
            )
            return None
