"""Sequence of events."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from vizreel.charts.base import ChartType, arranged, check_reading_time, split_duration
from vizreel.charts.registry import register
from vizreel.errors import RenderError
from vizreel.render.layout import LABEL_FILL, px, stack_gap, stroke_width
from vizreel.render.scales import band_centers, clamp_center, wrap_text
from vizreel.spec.data import Table
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
VERTICAL_LINES = 3
"""Most lines of a label on a vertical timeline, where labels have the whole width."""
VERTICAL_STEM_GAPS = 2.5
"""Length of the stem between the axis and a label on a vertical timeline, in label gaps."""
MAX_VERTICAL_PITCH = 1.8
"""Most distance between events on a vertical timeline, as a multiple of the least."""


def plan_vertical_events(
    top: float, bottom: float, heights: Sequence[float], gap: float
) -> list[float]:
    """Return the top of each event's label on a vertical timeline, first event first.

    Events are evenly spaced and centered between `bottom` and `top`. The spacing leaves at
    least `gap` under the tallest label, and is at most `MAX_VERTICAL_PITCH` times that, so a
    few events stay together instead of spreading over a tall frame.

    Raises:
        RenderError: The labels do not fit.
    """
    count = len(heights)
    least = max(heights) + gap
    fill = (top - bottom - heights[-1]) / (count - 1)
    pitch = min(fill, least * MAX_VERTICAL_PITCH)
    if pitch < least - 1e-9:
        raise RenderError("not enough room for the timeline; shorten the labels or the title")
    total = (count - 1) * pitch + heights[-1]
    first = (top + bottom + total) / 2
    return [first - index * pitch for index in range(count)]


@dataclass(frozen=True)
class TimelineGeometry:
    """Where the parts of a timeline go, horizontal or vertical.

    The axis is drawn by a pen that moves along it; positions along the axis are shares of
    its length, from 0 at the start to 1 at the end.

    Attributes:
        blocks: Each event's date and label, in place.
        shares: Where each event is along the axis.
        appear_share: How far the pen moves while an event appears.
        axis: Builds the axis drawn up to a share of its length.
        stem: Builds event `index`'s stem grown by a share from 0 to 1.
        dot: Builds event `index`'s dot grown by a share from 0 to 1.
    """

    blocks: list["VMobject"]
    shares: list[float]
    appear_share: float
    axis: Callable[[float], "VMobject"]
    stem: Callable[[int, float], "VMobject"]
    dot: Callable[[int, float], "VMobject"]


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
    template = """\
- id: history                      # unique; lowercase letters, digits and hyphens
  type: timeline
  title: How Northwind grew
  events:                          # two to seven events, in order
    - { date: "2016", label: "Founded" }   # dates are shown as written
    - { date: "2018", label: "Opens offices in three countries", emphasis: true }
    - { date: "2020", label: "Reaches one million users" }
  # subtitle: 2016 to 2020         # optional
  # source: "Source: example data" # optional
  # duration: 7                    # optional: seconds, at least 2
"""

    @classmethod
    def from_table(cls, table: Table, chart: dict[str, Any]) -> dict[str, Any]:
        """Read one event per row: its date, then its label."""
        table.require_width(2, "a date and a label")
        return {
            "events": [
                {"date": table.text(row, 0), "label": table.text(row, 1)}
                for row in range(len(table.rows))
            ]
        }

    def build(self, scene: "Scene") -> None:
        """Add the timeline to the scene and animate it."""
        from manim import (
            AnimationGroup,
            FadeIn,
            UpdateFromAlphaFunc,
            ValueTracker,
            VGroup,
            always_redraw,
            linear,
        )

        from vizreel.render import elements

        chart = self.chart
        assert isinstance(chart, TimelineChart)
        theme, layout = self.theme, self.layout
        motion = theme.motion
        ease = elements.easing(theme)
        events = chart.events
        count = len(events)

        header = elements.header(chart.title, chart.subtitle, theme, layout)
        source = elements.source_line(chart.source, theme, layout)
        geometry = arranged(layout, self._horizontal, self._vertical)
        blocks = geometry.blocks

        intro = motion.title_fade if len(header) else 0.0
        emphasized = next((index for index, event in enumerate(events) if event.emphasis), None)
        phases = split_duration(
            chart.duration,
            intro=intro,
            highlight=motion.highlight if emphasized is not None else 0.0,
            hold=motion.hold,
        )

        def appears_at(index: int) -> float:
            return phases.main_start + inverse(ease, geometry.shares[index]) * phases.main

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
            return min(ease(progress.get_value()), 1.0)

        def grown(index: int) -> float:
            local = (pen() - geometry.shares[index]) / geometry.appear_share
            return ease(min(max(local, 0.0), 1.0))

        def marks_at(index: int) -> "VMobject":
            amount = grown(index)
            if amount <= 0:
                return VGroup()
            return VGroup(geometry.stem(index, amount), geometry.dot(index, amount))

        def appearing_marks(index: int) -> "VMobject":
            return always_redraw(lambda: marks_at(index))

        def fade_with_pen(index: int) -> None:
            # Setting the opacity in place is much cheaper than copying the text every frame.
            blocks[index].add_updater(lambda block: block.set_opacity(grown(index)))

        drawing_axis = always_redraw(lambda: geometry.axis(pen()))
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

        stems = [geometry.stem(index, 1.0) for index in range(count)]
        dots = [geometry.dot(index, 1.0) for index in range(count)]
        for event_block in blocks:
            event_block.clear_updaters()
            event_block.set_opacity(1.0)
        scene.remove(drawing_axis, *appearing)
        scene.add(geometry.axis(1.0), *stems, *dots)
        self._final = (blocks, dots, stems, dots[0].width)

        if emphasized is not None:
            scene.play(
                *self.emphasis(events[emphasized].date),
                run_time=phases.highlight,
                rate_func=ease,
            )
        scene.wait(phases.hold)

    def emphasis(self, item: Any) -> list[Any]:
        """Emphasize the event dated `item` and dim the other events' marks.

        The emphasized event's dot grows and turns to the highlight color, as does its date;
        the other events' dots and stems dim and their text returns to its own colors.
        """
        from manim import ManimColor, interpolate_color

        assert isinstance(self.chart, TimelineChart)
        colors = self.theme.colors
        blocks, dots, stems, dot_width = self._final
        backdrop = ManimColor(colors.surface if self.layout.panel else colors.background)

        def dimmed(color: str) -> ManimColor:
            return interpolate_color(backdrop, ManimColor(color), colors.dim_opacity)

        animations: list[Any] = []
        for index, event in enumerate(self.chart.events):
            date, description = blocks[index]
            if event.date == item:
                animations += [
                    dots[index]
                    .animate.set(width=dot_width * EMPHASIS_SCALE)
                    .set_fill(colors.highlight),
                    stems[index].animate.set_stroke(colors.grid),
                    date.animate.set_color(colors.highlight),
                    description.animate.set_color(colors.text),
                ]
            else:
                animations += [
                    dots[index].animate.set(width=dot_width).set_fill(dimmed(colors.accent)),
                    stems[index].animate.set_stroke(dimmed(colors.grid)),
                    date.animate.set_color(colors.text),
                    description.animate.set_color(colors.muted),
                ]
        return animations

    def _event_block(
        self, index: int, lines: list[str], align: Literal["center", "left"]
    ) -> tuple["VMobject", float, float]:
        """Build an event's date and label, and return it with its top and bottom.

        Lines sit on their baselines, and the top and bottom come from the font, not the ink,
        so a dotted capital I or a descender does not move a label off its row.
        """
        from manim import DOWN, LEFT, ORIGIN, VGroup

        from vizreel.render import elements

        fonts, sizes, colors = self.theme.fonts, self.theme.sizes, self.theme.colors
        assert isinstance(self.chart, TimelineChart)
        event = self.chart.events[index]
        gap = stack_gap(sizes.label, sizes.label)
        date_metrics = elements.line_metrics(fonts.heading, sizes.label)
        label_metrics = elements.line_metrics(fonts.body, sizes.label)
        date = elements.text(event.date, fonts.heading, sizes.label, colors.text)
        description = elements.paragraph(lines, fonts.body, sizes.label, colors.muted, align)
        description.next_to(date, DOWN, aligned_edge=LEFT if align == "left" else ORIGIN)
        date_baseline = elements.baseline(date, event.date, fonts.heading, sizes.label)
        first_baseline = date_baseline - gap / 2 - label_metrics.ascent
        description.shift(
            (
                0.0,
                first_baseline
                - elements.baseline(description[0], lines[0], fonts.body, sizes.label),
                0.0,
            )
        )
        last_baseline = elements.baseline(description[-1], lines[-1], fonts.body, sizes.label)
        top = date_baseline + date_metrics.ascent
        bottom = last_baseline - label_metrics.descent
        return VGroup(date, description), top, bottom

    def _fits(self) -> Callable[[str, float], bool]:
        """Return a check whether a line of label text fits a width, remembering widths."""
        from vizreel.render import elements

        fonts, sizes, colors = self.theme.fonts, self.theme.sizes, self.theme.colors
        widths: dict[str, float] = {}

        def fits(line: str, width: float) -> bool:
            if line not in widths:
                widths[line] = elements.text(line, fonts.body, sizes.label, colors.muted).width
            return widths[line] <= width

        return fits

    def _horizontal(self) -> TimelineGeometry:
        """Events along a horizontal axis, labels below it or alternating above and below."""
        from manim import Dot, Line, VGroup

        chart = self.chart
        assert isinstance(chart, TimelineChart)
        sizes, colors = self.theme.sizes, self.theme.colors
        content = self.layout.content
        events = chart.events
        count = len(events)
        slot = content.width / count
        xs = band_centers(count, content.left, content.right)
        gap = stack_gap(sizes.label, sizes.label)
        dot_radius = px(sizes.dot) / 2
        stem_length = gap * STEM_GAPS

        plan = plan_labels(
            [event.date for event in events],
            [event.label for event in events],
            content.width,
            self._fits(),
        )
        built = [self._event_block(index, plan.lines[index], "center") for index in range(count)]
        heights = [top - bottom for _, top, bottom in built]
        sides = [side_of(index, plan.alternate) for index in range(count)]
        above = max((h for h, s in zip(heights, sides, strict=True) if s > 0), default=0.0)
        below = max((h for h, s in zip(heights, sides, strict=True) if s < 0), default=0.0)
        above_height = stem_length + above if above else dot_radius
        below_height = stem_length + below if below else dot_radius
        axis_y = content.center[1] + (below_height - above_height) / 2
        if above_height + below_height > content.height:
            raise RenderError("not enough room for the timeline; shorten the labels or the title")

        for index, ((event_block, top, bottom), side) in enumerate(zip(built, sides, strict=True)):
            x = clamp_center(xs[index], event_block.width, content.left, content.right)
            stem_end = axis_y + side * stem_length
            dy = stem_end - bottom if side > 0 else stem_end - top
            event_block.shift((x - event_block.get_center()[0], dy, 0.0))

        def axis(share: float) -> "VMobject":
            if share <= 0:
                return VGroup()
            return Line(
                (content.left, axis_y, 0.0),
                (content.left + share * content.width, axis_y, 0.0),
                color=colors.grid,
                stroke_width=stroke_width(sizes.line),
            )

        def stem(index: int, grown: float) -> "VMobject":
            return Line(
                (xs[index], axis_y + sides[index] * dot_radius, 0.0),
                (xs[index], axis_y + sides[index] * stem_length * grown, 0.0),
                color=colors.grid,
                stroke_width=stroke_width(sizes.grid_line),
            )

        def dot(index: int, grown: float) -> "VMobject":
            return Dot((xs[index], axis_y, 0.0), radius=dot_radius * grown, color=colors.accent)

        return TimelineGeometry(
            blocks=[event_block for event_block, _, _ in built],
            shares=[(x - content.left) / content.width for x in xs],
            appear_share=slot / 2 / content.width,
            axis=axis,
            stem=stem,
            dot=dot,
        )

    def _vertical(self) -> TimelineGeometry:
        """Events down a vertical axis at the left, each label to the right of its dot."""
        from manim import LEFT, Dot, Line, VGroup

        from vizreel.render import elements

        chart = self.chart
        assert isinstance(chart, TimelineChart)
        fonts, sizes, colors = self.theme.fonts, self.theme.sizes, self.theme.colors
        content = self.layout.content
        events = chart.events
        count = len(events)
        gap = stack_gap(sizes.label, sizes.label)
        dot_radius = px(sizes.dot) / 2
        axis_x = content.left + dot_radius * EMPHASIS_SCALE
        label_x = axis_x + gap * VERTICAL_STEM_GAPS
        label_width = content.right - label_x
        fits = self._fits()

        all_lines = []
        for event in events:
            lines = _wrap(event.label, label_width, VERTICAL_LINES, fits)
            if not fits(event.date, label_width):
                raise RenderError(f'event date "{event.date}" is too long; shorten it')
            if lines is None:
                raise RenderError(f'event label "{event.label}" is too long; shorten it')
            all_lines.append(lines)
        built = [self._event_block(index, all_lines[index], "left") for index in range(count)]
        heights = [top - bottom for _, top, bottom in built]
        tops = plan_vertical_events(content.top, content.bottom, heights, gap * 2)
        # The dot sits level with the middle of the date's capitals.
        dot_drop = elements.line_metrics(fonts.heading, sizes.label).ascent / 2
        ys = [top - dot_drop for top in tops]
        for (event_block, top, _), wanted_top in zip(built, tops, strict=True):
            event_block.shift((0.0, wanted_top - top, 0.0))
            event_block.align_to((label_x, 0.0, 0.0), LEFT)

        axis_top = tops[0]
        axis_length = tops[0] - (tops[-1] - heights[-1])

        def axis(share: float) -> "VMobject":
            if share <= 0:
                return VGroup()
            return Line(
                (axis_x, axis_top, 0.0),
                (axis_x, axis_top - share * axis_length, 0.0),
                color=colors.grid,
                stroke_width=stroke_width(sizes.line),
            )

        def stem(index: int, grown: float) -> "VMobject":
            start = axis_x + dot_radius
            end = label_x - gap / 4
            return Line(
                (start, ys[index], 0.0),
                (start + (end - start) * grown, ys[index], 0.0),
                color=colors.grid,
                stroke_width=stroke_width(sizes.grid_line),
            )

        def dot(index: int, grown: float) -> "VMobject":
            return Dot((axis_x, ys[index], 0.0), radius=dot_radius * grown, color=colors.accent)

        pitch = tops[0] - tops[1]
        return TimelineGeometry(
            blocks=[event_block for event_block, _, _ in built],
            shares=[(axis_top - y) / axis_length for y in ys],
            appear_share=pitch / 2 / axis_length,
            axis=axis,
            stem=stem,
            dot=dot,
        )
