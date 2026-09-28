"""How a whole divides into parts."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from vizreel.charts.base import (
    SMALLEST_NUMBER_SCALE,
    ChartType,
    check_reading_time,
    fitting_number_size,
    split_duration,
)
from vizreel.charts.registry import register
from vizreel.errors import RenderError
from vizreel.format.numbers import format_percent, whole_percents
from vizreel.render.layout import Box, Layout, px, stack_gap, stroke_width
from vizreel.spec.data import Table
from vizreel.spec.models import ShareChart

if TYPE_CHECKING:
    from manim import Animation, Mobject, Scene, VMobject

    from vizreel.render.numbers_text import NumberGlyphs

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


def largest_ring(
    content: Box, layout: Layout, legend_size: tuple[float, float], gap: float, min_radius: float
) -> SharePlacement:
    """Place the ring and legend as the frame calls for; a square frame takes the larger ring.

    A square frame is as narrow as a vertical one but not as tall, so the legend may fit
    beside the ring or under it; whichever leaves the larger ring wins.

    Raises:
        RenderError: The ring would be smaller than `min_radius` either way.
    """
    arrangements = (False, True) if layout.square else (layout.vertical,)
    placements, error = [], None
    for vertical in arrangements:
        try:
            placements.append(place_share(content, vertical, legend_size, gap, min_radius))
        except RenderError as exc:
            error = exc
    if not placements:
        assert error is not None
        raise error
    return max(placements, key=lambda placement: placement.radius)


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


@dataclass
class _ShareFinal:
    """The drawn chart, which the emphasis changes: its parts, legend and middle."""

    sectors: Sequence["VMobject"]
    dots: Sequence["VMobject"]
    names: Sequence["VMobject"]
    percents: list[int]
    center: tuple[float, float]
    inner: float
    gap: float
    glyphs: "NumberGlyphs"
    shown: "VMobject | None" = None
    """The percent and name in the middle, once a part has been emphasized."""


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

    @classmethod
    def from_table(cls, table: Table, chart: dict[str, Any]) -> dict[str, Any]:
        """Read one part per row: its label, then its value."""
        table.require_width(2, "a label and a value")
        return {
            "parts": [
                {"label": table.text(row, 0), "value": table.number(row, 1)}
                for row in range(len(table.rows))
            ]
        }

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
        widest_percent = max(
            percent_glyphs(format_percent(p, locale=self.locale)).width for p in [*percents, 100]
        )
        dot_radius = px(sizes.label) * LEGEND_MARK
        name_x = 2 * dot_radius + gap / 2
        percent_right = name_x + max(name.width for name in names) + gap * 2 + widest_percent
        pitch = px(sizes.label) * LEGEND_PITCH
        legend_size = (percent_right, pitch * (count - 1) + px(sizes.label))

        number_size = sizes.big_number * NUMBER_SCALE
        at_scale = NumberGlyphs(fonts.numbers, number_size, colors.text, sizes.affix_scale)
        widest_center = at_scale(format_percent(100, locale=self.locale)).width
        # The ring needs room for the percent at the least size a big number may shrink to;
        # the percent then takes the largest size the ring leaves it.
        least_center = widest_center * SMALLEST_NUMBER_SCALE
        min_radius = max(px(MIN_RADIUS_PX), least_center / (2 * INNER_RADIUS * CENTER_FILL))
        placement = largest_ring(content, layout, legend_size, gap * 3, min_radius)
        (cx, cy), radius = placement.center, placement.radius
        inner = radius * INNER_RADIUS
        number_size = fitting_number_size(
            number_size, widest_center, 2 * inner * CENTER_FILL, "the percent"
        )
        center_glyphs = NumberGlyphs(fonts.numbers, number_size, colors.text, sizes.affix_scale)

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
            text = percent_glyphs.at(
                format_percent(percent, locale=self.locale), 0.0, baselines[index]
            )
            return text.shift((percent_right_x - text.get_right()[0], 0.0, 0.0))

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
        self._final = _ShareFinal(
            sectors=final_sectors,
            dots=dots,
            names=names,
            percents=percents,
            center=(cx, cy),
            inner=inner,
            gap=gap,
            glyphs=center_glyphs,
        )

        scene.play(
            *self.emphasis(parts[highlighted].label), run_time=phases.highlight, rate_func=ease
        )
        scene.wait(phases.hold)

    def emphasis(self, item: Any) -> list[Any]:
        """Emphasize the part labeled `item` and count its percent up in the middle.

        The part turns to the highlight color and the others take their shades; a percent
        already in the middle, from an earlier emphasis, fades out.
        """
        from manim import (
            FadeIn,
            ManimColor,
            UpdateFromAlphaFunc,
            VGroup,
            interpolate_color,
        )

        assert isinstance(self.chart, ShareChart)
        from vizreel.render import elements

        colors = self.theme.colors
        final = self._final
        labels = [part.label for part in self.chart.parts]
        index = labels.index(item)
        backdrop = ManimColor(colors.surface if self.layout.panel else colors.background)
        shades = part_shades(len(labels), index)
        animations: list[Any] = []
        for part, (sector, dot, name) in enumerate(
            zip(final.sectors, final.dots, final.names, strict=True)
        ):
            fill = (
                ManimColor(colors.highlight)
                if part == index
                else interpolate_color(backdrop, ManimColor(colors.muted), shades[part])
            )
            animations += [
                sector.animate.set_fill(fill),
                dot.animate.set_fill(fill),
                name.animate.set_color(colors.text if part == index else colors.muted),
            ]
        if final.shown is not None:
            animations.append(elements.fade_away(final.shown))
        baseline, center_name = self._center_text(index)
        cx, _ = final.center
        percent = final.percents[index]
        number = VGroup()

        def count(mobject: "Mobject", alpha: float) -> None:
            # The percent fades in as it counts, so that the first frame of the emphasis is
            # still the frame before it, where a sequence cuts. Each frame holds a fresh text
            # rather than reshaping the last one, so the final text does not depend on how
            # many frames led to it.
            text = final.glyphs.at(
                format_percent(percent * alpha, locale=self.locale), cx, baseline
            )
            mobject.submobjects = [text.set_opacity(alpha)]

        animations.append(UpdateFromAlphaFunc(number, count))  # type: ignore[arg-type]
        if center_name is not None:
            animations.append(FadeIn(center_name))
        final.shown = VGroup(number, *([center_name] if center_name is not None else []))
        return animations

    def _center_text(self, index: int) -> tuple[float, "VMobject | None"]:
        """Return the baseline of part `index`'s percent in the middle, and its name under it.

        The name goes under the percent when both fit inside the ring; otherwise only the
        percent does, and the legend still names the part.
        """
        from vizreel.render import elements

        assert isinstance(self.chart, ShareChart)
        fonts, sizes, colors = self.theme.fonts, self.theme.sizes, self.theme.colors
        final = self._final
        cx, cy = final.center
        room = 2 * final.inner * CENTER_FILL
        block: elements.TextBlock | None
        try:
            block = elements.wrapped_block(
                self.chart.parts[index].label,
                fonts.body,
                sizes.label,
                colors.muted,
                room,
                "the highlighted label",
                "center",
            )
        except RenderError:
            block = None
        number_height = final.glyphs(
            format_percent(final.percents[index], locale=self.locale)
        ).height
        name_gap = final.gap * 1.5
        name_height = block.height + name_gap if block is not None else 0.0
        if number_height + name_height > room:
            block, name_height = None, 0.0
        baseline = cy + (number_height + name_height) / 2 - number_height
        if block is None:
            return baseline, None
        block.move_top_to(baseline - name_gap)
        block.mobject.set_x(cx)
        return baseline, block.mobject
