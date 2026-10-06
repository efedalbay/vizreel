"""Title card: a headline that opens a video or a part of one."""

from itertools import pairwise
from typing import TYPE_CHECKING

from vizreel.charts.base import ChartType, check_reading_time, split_duration
from vizreel.charts.registry import register
from vizreel.errors import RenderError
from vizreel.render.layout import px
from vizreel.render.scales import balanced_lines
from vizreel.spec.models import TitleCardChart
from vizreel.themes.models import FontStyle

if TYPE_CHECKING:
    from manim import Animation, Scene

    from vizreel.render.elements import TextBlock

HEADLINE_LINES = 3
"""Most lines the headline wraps onto."""
LINE_GAP = 0.9
"""Gap between the card's lines, as a multiple of the smaller font size: twice the gap of
stacked text, so each line reads on its own."""
LINE_LAG = 0.3
"""Each line starts appearing after this share of the one before it has."""


def line_starts(count: int, reveal: float, lag: float = LINE_LAG) -> list[float]:
    """When each of `count` lines starts appearing, if they all appear within `reveal` seconds.

    Each line takes the same time, and starts once `lag` of the line before it has passed.
    """
    each = reveal / (1 + lag * (count - 1))
    return [index * lag * each for index in range(count)]


@register
class TitleCardChartType(ChartType):
    """A headline, centered, with a short line above it and a line under it.

    The lines appear one after another, as the theme's entrance says, and then hold.
    """

    name = "title-card"
    model = TitleCardChart
    # The card places its own lines in the middle of the frame, whatever its shape.
    fits_to_content = False
    own_header = True
    template = """\
- id: part-two                     # unique; lowercase letters, digits and hyphens
  type: title-card
  title: How Northwind grew        # the headline; wraps onto up to three lines
  kicker: Part 2                   # optional: short line above the headline
  # subtitle: 2019 to 2024         # optional: line under the headline
  # source: "Source: example data" # optional: short, shown at the bottom
  # duration: 3                    # optional: seconds, at least 2
"""

    def build(self, scene: "Scene") -> None:
        """Add the card to the scene and animate it."""
        from manim import AnimationGroup, LaggedStart, VGroup

        from vizreel.render import elements

        chart = self.chart
        assert isinstance(chart, TitleCardChart)
        theme, layout = self.theme, self.layout
        fonts, sizes, colors, motion = theme.fonts, theme.sizes, theme.colors, theme.motion
        ease = elements.easing(theme)
        width = layout.content.width

        def block(
            content: str, style: FontStyle, size: float, color: str, what: str, most: int
        ) -> "TextBlock":
            lines = elements.wrapped_lines(content, style, size, width, what, most)
            if len(lines) == 1:
                return elements.text_block(content, style, size, color)
            lines = balanced_lines(
                content, lambda line: elements.text(line, style, size, color).width, len(lines)
            )
            return elements.paragraph_block(lines, style, size, color, "center")

        lines: list[TextBlock] = []
        if chart.kicker:
            lines.append(
                block(chart.kicker, fonts.body, sizes.label, colors.accent, "the kicker", 2)
            )
        lines.append(
            block(
                chart.title,
                fonts.heading,
                sizes.headline,
                colors.text,
                "the title",
                HEADLINE_LINES,
            )
        )
        if chart.subtitle:
            lines.append(
                block(chart.subtitle, fonts.body, sizes.subtitle, colors.muted, "the subtitle", 2)
            )
        gaps = [
            px(min(above.size_px, below.size_px)) * LINE_GAP for above, below in pairwise(lines)
        ]
        height = sum(line.top() - line.bottom() for line in lines) + sum(gaps)
        center_x, center_y = layout.content.center
        top = center_y + height / 2
        for line, gap in zip(lines, [*gaps, 0.0], strict=True):
            line.move_top_to(top)
            line.mobject.set_x(center_x)
            top = line.bottom() - gap
        if height > layout.content.height + 1e-9:
            raise RenderError(
                "the title card's lines are too tall to fit at the theme's sizes; shorten them"
            )
        source = elements.source_line(chart.source, theme, layout)

        phases = split_duration(chart.duration, intro=0.0, highlight=0, hold=motion.hold)
        starts = line_starts(len(lines), phases.main)
        texts = [text for text in (chart.kicker, chart.title, chart.subtitle) if text]
        check_reading_time(
            [*zip(texts, starts, strict=True), *([(chart.source, 0.0)] if chart.source else [])],
            chart.duration,
        )

        fade = min(motion.title_fade, phases.main)
        reveal: list[Animation] = [
            LaggedStart(
                *(elements.appear(line.mobject, theme, rate_func=ease) for line in lines),
                lag_ratio=LINE_LAG,
                run_time=phases.main,
            )
        ]
        if layout.panel:
            card = elements.panel(layout.panel_around(layout.inner), theme)
            reveal.append(elements.appear(card, theme, run_time=fade, rate_func=ease))
        if source is not None:
            reveal.append(elements.appear(source, theme, run_time=fade, rate_func=ease))
        scene.play(AnimationGroup(*reveal), run_time=phases.main, cue="reveal")
        scene.add(VGroup(*(line.mobject for line in lines)))
        scene.wait(phases.hold)
