"""Sequence of events."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from vizreel.charts.base import ChartType, check_reading_time, split_duration
from vizreel.charts.registry import register
from vizreel.errors import RenderError
from vizreel.render.layout import LABEL_FILL, px, stack_gap, stroke_width
from vizreel.render.scales import band_centers, clamp_center, wrap_text
from vizreel.spec.models import TimelineChart

if TYPE_CHECKING:
    from manim import Animation, Scene, VMobject

ONE_SIDE_LINES = 2
"""Most lines of a label when every label sits below the axis."""
ALTERNATING_LINES = 3
"""Most lines of a label when labels alternate above and below the axis."""
EMPHASIS_SCALE = 1.6
"""The emphasized event's dot grows by this factor at the highlight beat."""
STEM_GAPS = 1.5
"""Length of the stem between the axis and a label, in label gaps."""
EDGE_SLOTS = 1.5
"""Slots the first and last label may span when labels alternate sides."""


@dataclass(frozen=True)
class LabelPlan:
    """Where event labels go and how they wrap.

    Attributes:
        alternate: Labels alternate below and above the axis instead of all sitting below.
        lines: The wrapped lines of each label.
        widths: Widest each label may be.
    """

    alternate: bool
    lines: list[list[str]]
    widths: list[float]


def label_widths(count: int, width: float, alternate: bool) -> list[float]:
    """Widest each event label may be.

    Below-only labels get one slot each. Alternating labels get two slots, because the
    neighbor on the same side is two slots away; the first and last get `EDGE_SLOTS`
    because they are moved inside the frame, toward their same-side neighbor.
    """
    slot = width / count
    if not alternate:
        return [slot * LABEL_FILL] * count
    widths = []
    for index in range(count):
        at_edge = index in (0, count - 1)
        has_same_side_neighbor = index - 2 >= 0 or index + 2 < count
        slots = EDGE_SLOTS if at_edge and has_same_side_neighbor else 2
        widths.append(min(slots * slot, width) * LABEL_FILL)
    return widths


def plan_labels(
    dates: Sequence[str],
    labels: Sequence[str],
    width: float,
    fits: Callable[[str, float], bool],
) -> LabelPlan:
    """Decide whether labels alternate sides, and wrap them.

    Every label sits below the axis if each fits its own slot in at most `ONE_SIDE_LINES`
    lines. Otherwise labels alternate sides with the widths of `label_widths` and at most
    `ALTERNATING_LINES` lines. Dates always stay on one line.

    Args:
        dates: The date of each event.
        labels: The label of each event.
        width: Width of the whole timeline.
        fits: Whether a line of text fits a width.

    Raises:
        RenderError: A date or label does not fit even when labels alternate.
    """
    count = len(labels)
    for alternate, max_lines in ((False, ONE_SIDE_LINES), (True, ALTERNATING_LINES)):
        widths = label_widths(count, width, alternate)
        wrapped = [
            _wrap(label, label_width, max_lines, fits)
            for label, label_width in zip(labels, widths, strict=True)
        ]
        dates_fit = all(fits(date, w) for date, w in zip(dates, widths, strict=True))
        if dates_fit and all(lines is not None for lines in wrapped):
            return LabelPlan(alternate, [lines or [] for lines in wrapped], widths)
    for date, label, lines, label_width in zip(dates, labels, wrapped, widths, strict=True):
        if not fits(date, label_width):
            raise RenderError(f'event date "{date}" is too long for {count} events; shorten it')
        if lines is None:
            raise RenderError(f'event label "{label}" is too long for {count} events; shorten it')
    raise AssertionError("unreachable")


def _wrap(
    text: str, width: float, max_lines: int, fits: Callable[[str, float], bool]
) -> list[str] | None:
    return wrap_text(text, lambda line: fits(line, width), max_lines)


def side_of(index: int, alternate: bool) -> int:
    """-1 if event `index` is labeled below the axis, 1 if above."""
    return 1 if alternate and index % 2 else -1


def inverse(curve: Callable[[float], float], value: float) -> float:
    """The time at which an increasing curve from 0 to 1 reaches `value`."""
    low, high = 0.0, 1.0
    for _ in range(50):
        middle = (low + high) / 2
        if curve(middle) < value:
            low = middle
        else:
            high = middle
    return high


@register
class TimelineChartType(ChartType):
    """Events placed in order along a horizontal line.

    The axis draws from left to right like a pen; each event's dot, stem and label appear
    as the pen reaches it. At the highlight beat the emphasized event grows and turns to
    the highlight color while the other events' marks dim.
    """

    name = "timeline"
    model = TimelineChart

    def build(self, scene: "Scene") -> None:
        """Add the timeline to the scene and animate it."""
        from manim import (
            DOWN,
            AnimationGroup,
            Dot,
            FadeIn,
            Line,
            ManimColor,
            UpdateFromAlphaFunc,
            ValueTracker,
            VGroup,
            always_redraw,
            interpolate_color,
            linear,
        )

        from vizreel.render import elements

        chart = self.chart
        assert isinstance(chart, TimelineChart)
        theme, layout = self.theme, self.layout
        fonts, sizes, colors, motion = theme.fonts, theme.sizes, theme.colors, theme.motion
        ease = elements.easing(theme)
        content = layout.content
        events = chart.events
        count = len(events)
        slot = content.width / count
        xs = band_centers(count, content.left, content.right)
        gap = stack_gap(sizes.label, sizes.label)
        dot_radius = px(sizes.dot) / 2
        stem_length = gap * STEM_GAPS

        header = elements.header(chart.title, chart.subtitle, theme, layout)
        source = elements.source_line(chart.source, theme, layout)

        widths: dict[str, float] = {}

        def fits(line: str, width: float) -> bool:
            if line not in widths:
                widths[line] = elements.text(line, fonts.body, sizes.label, colors.muted).width
            return widths[line] <= width

        plan = plan_labels(
            [event.date for event in events], [event.label for event in events], content.width, fits
        )

        def block(index: int) -> "VMobject":
            date = elements.text(events[index].date, fonts.heading, sizes.label, colors.text)
            description = elements.paragraph(
                plan.lines[index], fonts.body, sizes.label, colors.muted
            )
            return VGroup(date, description).arrange(DOWN, buff=gap / 2)

        blocks = [block(index) for index in range(count)]
        sides = [side_of(index, plan.alternate) for index in range(count)]
        above = max((b.height for b, s in zip(blocks, sides, strict=True) if s > 0), default=0.0)
        below = max((b.height for b, s in zip(blocks, sides, strict=True) if s < 0), default=0.0)
        above_height = stem_length + above if above else dot_radius
        below_height = stem_length + below if below else dot_radius
        axis_y = content.center[1] + (below_height - above_height) / 2
        if above_height + below_height > content.height:
            raise RenderError("not enough room for the timeline; shorten the labels or the title")

        for index, (event_block, side) in enumerate(zip(blocks, sides, strict=True)):
            x = clamp_center(xs[index], event_block.width, content.left, content.right)
            y = axis_y + side * (stem_length + event_block.height / 2)
            event_block.move_to((x, y, 0.0))

        axis_width = stroke_width(sizes.line)

        def stem(index: int, grown: float) -> "VMobject":
            start = axis_y + sides[index] * dot_radius
            end = axis_y + sides[index] * stem_length * grown
            return Line(
                (xs[index], start, 0.0),
                (xs[index], end, 0.0),
                color=colors.grid,
                stroke_width=stroke_width(sizes.grid_line),
            )

        def dot(index: int, grown: float) -> "VMobject":
            return Dot((xs[index], axis_y, 0.0), radius=dot_radius * grown, color=colors.accent)

        intro = motion.title_fade if len(header) else 0.0
        emphasized = next((index for index, event in enumerate(events) if event.emphasis), None)
        phases = split_duration(
            chart.duration,
            intro=intro,
            highlight=motion.highlight if emphasized is not None else 0.0,
            hold=motion.hold,
        )
        appear_distance = slot / 2

        def appears_at(index: int) -> float:
            share = (xs[index] - content.left) / content.width
            return phases.main_start + inverse(ease, share) * phases.main

        check_reading_time(
            [(text, 0.0) for text in (chart.title, chart.subtitle, chart.source) if text]
            + [(f"{e.date} {e.label}", appears_at(i)) for i, e in enumerate(events)],
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
            eased = ease(progress.get_value())
            return content.right if eased >= 1 else content.left + eased * content.width

        def grown(index: int) -> float:
            local = (pen() - xs[index]) / appear_distance
            return ease(min(max(local, 0.0), 1.0))

        def axis_at(end: float) -> "VMobject":
            if end <= content.left:
                return VGroup()
            return Line(
                (content.left, axis_y, 0.0),
                (end, axis_y, 0.0),
                color=colors.grid,
                stroke_width=axis_width,
            )

        def marks_at(index: int) -> "VMobject":
            amount = grown(index)
            if amount <= 0:
                return VGroup()
            return VGroup(stem(index, amount), dot(index, amount))

        def appearing_marks(index: int) -> "VMobject":
            return always_redraw(lambda: marks_at(index))

        def fade_with_pen(index: int) -> None:
            # Setting the opacity in place is much cheaper than copying the text every frame.
            blocks[index].add_updater(lambda block: block.set_opacity(grown(index)))

        drawing_axis = always_redraw(lambda: axis_at(pen()))
        appearing = [appearing_marks(index) for index in range(count)]
        for index in range(count):
            fade_with_pen(index)
        scene.add(drawing_axis, *appearing, *blocks)

        def move_pen(tracker: ValueTracker, alpha: float) -> None:
            tracker.set_value(alpha)

        # Manim calls the update function with (mobject, alpha) but types it with one argument.
        sweep = UpdateFromAlphaFunc(progress, move_pen, run_time=phases.main, rate_func=linear)  # type: ignore[arg-type]
        reveal: list[Animation] = [*opening, sweep]
        scene.play(AnimationGroup(*reveal), run_time=phases.main)

        stems = [stem(index, 1.0) for index in range(count)]
        dots = [dot(index, 1.0) for index in range(count)]
        for event_block in blocks:
            event_block.clear_updaters()
            event_block.set_opacity(1.0)
        scene.remove(drawing_axis, *appearing)
        scene.add(axis_at(content.right), *stems, *dots)

        if emphasized is not None:
            backdrop = ManimColor(colors.surface if layout.panel else colors.background)

            def dimmed(color: str) -> ManimColor:
                return interpolate_color(backdrop, ManimColor(color), colors.dim_opacity)

            date, description = blocks[emphasized]
            others = [index for index in range(count) if index != emphasized]
            beat = [
                dots[emphasized].animate.scale(EMPHASIS_SCALE).set_fill(colors.highlight),
                date.animate.set_color(colors.highlight),
                description.animate.set_color(colors.text),
                *(dots[index].animate.set_fill(dimmed(colors.accent)) for index in others),
                *(stems[index].animate.set_stroke(dimmed(colors.grid)) for index in others),
            ]
            scene.play(*beat, run_time=phases.highlight, rate_func=ease)
        scene.wait(phases.hold)
