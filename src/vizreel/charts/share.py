"""How a whole divides into parts."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from vizreel.charts.base import ChartType, check_reading_time, split_duration
from vizreel.charts.registry import register
from vizreel.errors import RenderError
from vizreel.format.numbers import format_percent, whole_percents
from vizreel.render.layout import Box, px, stack_gap, stroke_width
from vizreel.spec.models import ShareChart

if TYPE_CHECKING:
    from manim import Animation, Mobject, Scene, VMobject

NUMBER_SCALE = 2 / 3
"""Size of the percent in the middle, as a share of the theme's big number size."""
INNER_RADIUS = 0.62
"""Inner radius of the ring, as a share of its outer radius."""
MIN_RADIUS_PX = 160
"""Least outer radius of the ring, in pixels at 1080p."""
CENTER_FILL = 0.8
"""Share of the ring's inner width that the text in the middle may use."""
OTHER_SHADES = (0.8, 0.4)
"""How strongly the parts other than the highlighted one show the muted color, first to last,
blended into the background. The highlighted part shows it fully until it turns to the
highlight color, so no two neighboring parts share a shade."""
SEPARATOR_PX = 4
"""Width, in pixels at 1080p, of the line in the background color between two parts."""
LEGEND_MARK = 0.3
"""Radius of a legend dot, as a share of the label size."""
LEGEND_PITCH = 1.7
"""Distance between legend rows, as a multiple of the label size."""


def part_spans(values: list[float]) -> list[tuple[float, float]]:
    """Return where each part starts and ends around the ring, as shares of the whole."""
    total = sum(values)
    spans = []
    start = 0.0
    for value in values:
        end = start + value / total
        spans.append((start, end))
        start = end
    return spans


@dataclass(frozen=True)
class SharePlacement:
    """Where the ring and the legend go, in scene units.

    Attributes:
        center: Center of the ring.
        radius: Outer radius of the ring.
        legend: Top left corner of the legend.
    """

    center: tuple[float, float]
    radius: float
    legend: tuple[float, float]


def place_share(
    content: Box,
    vertical: bool,
    legend_size: tuple[float, float],
    gap: float,
    min_radius: float,
) -> SharePlacement:
    """Place the ring and the legend: side by side at 16:9, the legend under the ring at 9:16.

    The ring is as large as the space allows, and the pair is centered in `content`.

    Raises:
        RenderError: The ring would be smaller than `min_radius`.
    """
    legend_width, legend_height = legend_size
    x, y = content.center
    if vertical:
        radius = min(content.width / 2, (content.height - gap - legend_height) / 2)
        top = y + (2 * radius + gap + legend_height) / 2
        center = (x, top - radius)
        legend = (x - legend_width / 2, top - 2 * radius - gap)
    else:
        radius = min(content.height / 2, (content.width - gap - legend_width) / 2)
        left = x - (2 * radius + gap + legend_width) / 2
        center = (left + radius, y)
        legend = (left + 2 * radius + gap, y + legend_height / 2)
    if radius < min_radius - 1e-9:
        raise RenderError("not enough room for the ring; shorten the labels or the title")
    return SharePlacement(center, radius, legend)


def part_shades(count: int, highlighted: int) -> list[float]:
    """Return how strongly each part shows the muted color, from 0 to 1.

    The highlighted part shows it fully; the others step through `OTHER_SHADES`, in order.
    """
    strongest, weakest = OTHER_SHADES
    others = [index for index in range(count) if index != highlighted]
    shades = [1.0] * count
    for step, index in enumerate(others):
        shades[index] = strongest - (strongest - weakest) * step / max(len(others) - 1, 1)
    return shades


@register
class ShareChartType(ChartType):
    """A ring divided into parts, with the emphasized part's percent in the middle.

    The ring draws clockwise from the top like a pen, and the legend beside it lists each
    part with its percent, which counts up as its part draws. The parts are shades of the
    muted color; at the highlight beat the emphasized part, the largest unless another is
    named, turns to the highlight color and its percent counts up in the middle. Percents are
    whole numbers that add up to 100.
    """

    name = "share"
    model = ShareChart
    template = """\
- id: market                       # unique; lowercase letters, digits and hyphens
  type: share
  title: Northwind's share of the market
  parts:                           # two to six parts, clockwise from the top
    - { label: Northwind, value: 47 }
    - { label: Contoso, value: 28 }
    - { label: Others, value: 25 }
  # highlight: { label: Contoso }  # optional: the part to emphasize; the largest by default
  # subtitle: Share of sales in 2023   # optional
  # source: "Source: example data" # optional
  # duration: 6                    # optional: seconds, at least 2
"""

    def build(self, scene: "Scene") -> None:
        """Add the chart to the scene and animate it."""
        from manim import (
            LEFT,
            PI,
            TAU,
            AnimationGroup,
            AnnularSector,
            Dot,
            FadeIn,
            ManimColor,
            UpdateFromAlphaFunc,
            ValueTracker,
            VGroup,
            always_redraw,
            interpolate_color,
            linear,
        )

        from vizreel.render import elements
        from vizreel.render.numbers_text import NumberGlyphs

        chart = self.chart
        assert isinstance(chart, ShareChart)
        theme, layout = self.theme, self.layout
        fonts, sizes, colors, motion = theme.fonts, theme.sizes, theme.colors, theme.motion
        ease = elements.easing(theme)
        content = layout.content
        parts = chart.parts
        count = len(parts)
        highlighted = chart.highlighted()
        percents = whole_percents([part.value for part in parts])
        spans = part_spans([part.value for part in parts])
        gap = stack_gap(sizes.label, sizes.label)
        backdrop = ManimColor(colors.surface if layout.panel else colors.background)
        shade_colors = [
            interpolate_color(backdrop, ManimColor(colors.muted), shade)
            for shade in part_shades(count, highlighted)
        ]

        header = elements.header(chart.title, chart.subtitle, theme, layout)
        source = elements.source_line(chart.source, theme, layout)

        percent_glyphs = NumberGlyphs(fonts.numbers, sizes.value, colors.text)
        names = [elements.text(part.label, fonts.body, sizes.label, colors.muted) for part in parts]
        widest_percent = max(percent_glyphs(format_percent(p)).width for p in [*percents, 100])
        dot_radius = px(sizes.label) * LEGEND_MARK
        name_x = 2 * dot_radius + gap / 2
        percent_right = name_x + max(name.width for name in names) + gap * 2 + widest_percent
        pitch = px(sizes.label) * LEGEND_PITCH
        legend_size = (percent_right, pitch * (count - 1) + px(sizes.label))

        number_size = sizes.big_number * NUMBER_SCALE
        center_glyphs = NumberGlyphs(fonts.numbers, number_size, colors.text)
        widest_center = center_glyphs(format_percent(100)).width
        min_radius = max(px(MIN_RADIUS_PX), widest_center / (2 * INNER_RADIUS * CENTER_FILL))
        placement = place_share(content, layout.vertical, legend_size, gap * 3, min_radius)
        (cx, cy), radius = placement.center, placement.radius
        inner = radius * INNER_RADIUS

        legend_left, legend_top = placement.legend
        rows_y = [legend_top - px(sizes.label) / 2 - index * pitch for index in range(count)]
        dots = [
            Dot((legend_left + dot_radius, y, 0.0), radius=dot_radius, color=shade_colors[index])
            for index, y in enumerate(rows_y)
        ]
        for name, y in zip(names, rows_y, strict=True):
            name.move_to((0.0, y, 0.0)).align_to((legend_left + name_x, 0.0, 0.0), LEFT)
        # Percents stand on the baseline of their row's name.
        baselines = [
            elements.baseline(name, part.label, fonts.body, sizes.label)
            for name, part in zip(names, parts, strict=True)
        ]
        percent_right_x = legend_left + percent_right

        def percent_text(index: int, percent: float) -> "VMobject":
            text = percent_glyphs.at(format_percent(percent), 0.0, baselines[index])
            return text.shift((percent_right_x - text.get_right()[0], 0.0, 0.0))

        # The highlighted part's name goes under its percent when both fit inside the ring;
        # otherwise only the percent does, and the legend still names the part.
        center_block: elements.TextBlock | None
        try:
            center_block = elements.wrapped_block(
                parts[highlighted].label,
                fonts.body,
                sizes.label,
                colors.muted,
                2 * inner * CENTER_FILL,
                "the highlighted label",
                "center",
            )
        except RenderError:
            center_block = None
        number_height = center_glyphs(format_percent(percents[highlighted])).height
        name_gap = gap * 1.5
        name_height = center_block.height + name_gap if center_block is not None else 0.0
        if number_height + name_height > 2 * inner * CENTER_FILL:
            center_block, name_height = None, 0.0
        number_baseline = cy + (number_height + name_height) / 2 - number_height
        center_name = center_block.mobject if center_block is not None else None
        if center_block is not None:
            center_block.move_top_to(number_baseline - name_gap)
            center_block.mobject.set_x(cx)

        separator = stroke_width(SEPARATOR_PX)

        def sector(index: int, reached: float, color: Any) -> "VMobject":
            start = spans[index][0]
            if reached - start <= 1e-4:
                return VGroup()
            return AnnularSector(
                inner_radius=inner,
                outer_radius=radius,
                start_angle=PI / 2 - TAU * start,
                angle=-TAU * (reached - start),
                arc_center=(cx, cy, 0.0),
                fill_color=color,
                fill_opacity=1,
                stroke_color=backdrop,
                stroke_width=separator,
            )

        intro = motion.title_fade if len(header) else 0.0
        phases = split_duration(
            chart.duration, intro=intro, highlight=motion.highlight, hold=motion.hold
        )
        check_reading_time(
            [(text, 0.0) for text in (chart.title, chart.subtitle, chart.source) if text]
            + [
                (f"{part.label} {percents[index]}%", phases.main_start + span[0] * phases.main)
                for index, (part, span) in enumerate(zip(parts, spans, strict=True))
            ],
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

        progress = ValueTracker(0.0)

        def pen() -> float:
            return min(ease(progress.get_value()), 1.0)

        def local(index: int) -> float:
            start, end = spans[index]
            return min(max((pen() - start) / (end - start), 0.0), 1.0)

        def drawing_sector(index: int) -> "VMobject":
            return always_redraw(
                lambda: sector(index, min(pen(), spans[index][1]), shade_colors[index])
            )

        def counting_percent(index: int) -> "VMobject":
            return always_redraw(
                lambda: (
                    percent_text(index, percents[index] * local(index))
                    if local(index) > 0
                    else VGroup()
                )
            )

        def fade_with_pen(index: int) -> None:
            # Setting the opacity in place is much cheaper than copying the text every frame.
            def update(mobject: "Mobject") -> None:
                mobject.set_opacity(min(local(index) * 4, 1.0))

            for mobject in (dots[index], names[index]):
                mobject.set_opacity(0.0)
                mobject.add_updater(update)

        drawing = [drawing_sector(index) for index in range(count)]
        counting = [counting_percent(index) for index in range(count)]
        for index in range(count):
            fade_with_pen(index)
        scene.add(*drawing, *counting, *dots, *names)

        def move_pen(tracker: ValueTracker, alpha: float) -> None:
            tracker.set_value(alpha)

        # Manim calls the update function with (mobject, alpha) but types it with one argument.
        sweep = UpdateFromAlphaFunc(progress, move_pen, run_time=phases.main, rate_func=linear)  # type: ignore[arg-type]
        scene.play(AnimationGroup(*opening, sweep), run_time=phases.main)

        final_sectors = [
            sector(index, spans[index][1], shade_colors[index]) for index in range(count)
        ]
        final_percents = [percent_text(index, percents[index]) for index in range(count)]
        for mobject in (*dots, *names):
            mobject.clear_updaters()
            mobject.set_opacity(1.0)
        scene.remove(*drawing, *counting)
        scene.add(*final_sectors, *final_percents)

        center_tracker = ValueTracker(0.0)
        counting_center = always_redraw(
            lambda: center_glyphs.at(
                format_percent(center_tracker.get_value()), cx, number_baseline
            )
        )
        scene.add(counting_center)

        def count_center(tracker: ValueTracker, alpha: float) -> None:
            tracker.set_value(percents[highlighted] * alpha)

        beat: list[Any] = [
            final_sectors[highlighted].animate.set_fill(colors.highlight),
            dots[highlighted].animate.set_fill(colors.highlight),
            names[highlighted].animate.set_color(colors.text),
            UpdateFromAlphaFunc(center_tracker, count_center),  # type: ignore[arg-type]
        ]
        if center_name is not None:
            beat.append(FadeIn(center_name))
        scene.play(*beat, run_time=phases.highlight, rate_func=ease)
        counting_center.clear_updaters()
        scene.wait(phases.hold)
