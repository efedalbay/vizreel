"""One measure before and after."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from vizreel.charts.base import (
    ChartType,
    check_reading_time,
    count_samples,
    fitting_number_size,
    split_duration,
)
from vizreel.charts.registry import register
from vizreel.errors import RenderError
from vizreel.format.numbers import (
    change_amount,
    change_decimals,
    decimals_for,
    format_change,
    format_number,
)
from vizreel.render.layout import px, stack_gap, stroke_width
from vizreel.spec.data import Table
from vizreel.spec.models import CompareChart

if TYPE_CHECKING:
    from collections.abc import Callable

    from manim import Animation, Scene, VMobject

    from vizreel.render.numbers_text import NumberGlyphs

NUMBER_SCALE = 2 / 3
"""Size of the two values, as a share of the theme's big number size. A stat has one hero
number; here two numbers share the frame, and at full size two of them rarely fit."""
MIN_ARROW_PX = 240
"""Least length, in pixels at 1080p, of the arrow between values side by side."""
MIN_STACKED_ARROW_PX = 120
"""Least length, in pixels at 1080p, of the arrow between values one above the other."""
SIDE_GAP = 0.3
"""Space between the values and the arrow side by side, as a multiple of the number size."""
ARROW_TIP = 5
"""Length of the arrow's tip, as a multiple of the theme's line width."""


@dataclass(frozen=True)
class ValueBlock:
    """The vertical extent of a value with its label, from the number's baseline.

    Attributes:
        ascent: From the baseline up to the top of the number.
        depth: From the baseline down to the bottom of the label.
    """

    ascent: float
    depth: float

    @property
    def height(self) -> float:
        """The whole height."""
        return self.ascent + self.depth


@dataclass(frozen=True)
class ComparePlacement:
    """Where the parts of a compare chart go, in scene units.

    Attributes:
        before: Horizontal center and baseline of the earlier number.
        after: Horizontal center and baseline of the later number.
        arrow: Start and end of the arrow.
        change: Center of the change text.
    """

    before: tuple[float, float]
    after: tuple[float, float]
    arrow: tuple[tuple[float, float], tuple[float, float]]
    change: tuple[float, float]


def place_side_by_side(
    center: tuple[float, float],
    width: float,
    column_width: float,
    block: ValueBlock,
    change_size: tuple[float, float],
    gap: float,
    min_arrow: float,
) -> ComparePlacement:
    """Place the two values in columns left and right of an arrow, the change above it.

    The numbers share a baseline, the arrow runs at half their height, and the whole group
    is centered on `center`.

    Args:
        center: Center of the space for the chart.
        width: Width of that space.
        column_width: Width of each value's column.
        block: The extent of the taller value with its label.
        change_size: Width and height of the change text; (0, 0) without one.
        gap: Space between the columns and the arrow, and between the arrow and the change.
        min_arrow: Least length of the arrow.

    Raises:
        RenderError: The two values and the arrow are wider than `width`.
    """
    arrow = max(change_size[0] + 2 * gap, min_arrow)
    if 2 * column_width + 2 * gap + arrow > width + 1e-9:
        raise RenderError("the values are too wide to compare side by side; use compact numbers")
    x, y = center
    baseline = y + block.height / 2 - block.ascent
    arrow_y = baseline + block.ascent / 2
    offset = arrow / 2 + gap + column_width / 2
    return ComparePlacement(
        before=(x - offset, baseline),
        after=(x + offset, baseline),
        arrow=((x - arrow / 2, arrow_y), (x + arrow / 2, arrow_y)),
        change=(x, arrow_y + gap + change_size[1] / 2),
    )


def place_stacked(
    center: tuple[float, float],
    height: float,
    blocks: tuple[ValueBlock, ValueBlock],
    change_size: tuple[float, float],
    gap: float,
    min_arrow: float,
) -> ComparePlacement:
    """Place the earlier value above the later one, with a downward arrow between them.

    The change goes to the right of the arrow, and the whole group is centered on `center`.

    Raises:
        RenderError: The two values and the arrow are taller than `height`.
    """
    before, after = blocks
    arrow = max(change_size[1] + 2 * gap, min_arrow)
    total = before.height + gap + arrow + gap + after.height
    if total > height + 1e-9:
        raise RenderError("not enough room for the values; shorten the title or the labels")
    x, y = center
    before_baseline = y + total / 2 - before.ascent
    arrow_top = before_baseline - before.depth - gap
    arrow_bottom = arrow_top - arrow
    return ComparePlacement(
        before=(x, before_baseline),
        after=(x, arrow_bottom - gap - after.ascent),
        arrow=((x, arrow_top), (x, arrow_bottom)),
        change=(x + gap + change_size[0] / 2, (arrow_top + arrow_bottom) / 2),
    )


@register
class CompareChartType(ChartType):
    """One measure at two moments: the earlier value, an arrow, the later value.

    The earlier value counts up, the arrow draws, and the later value counts from the earlier
    one to its own value, so the viewer sees the change happen. At the highlight beat the
    earlier value dims and the change counts in. Values sit side by side at 16:9, and one
    above the other at 9:16 or when they are too wide to sit side by side.
    """

    name = "compare"
    model = CompareChart
    template = """\
- id: headcount                    # unique; lowercase letters, digits and hyphens
  type: compare
  title: Northwind's employees
  before: { label: "2019", value: 1200 }
  after: { label: "2022", value: 340 }
  # change: percent                # optional: percent, absolute or none
  # trend: none                    # optional: auto colors the change up or down; none does not
  # number: { compact: true }      # optional: prefix, suffix, decimals, compact
  # subtitle: All offices          # optional
  # source: "Source: example data" # optional
  # duration: 5                    # optional: seconds, at least 2
"""

    @classmethod
    def from_table(cls, table: Table, chart: dict[str, Any]) -> dict[str, Any]:
        """Read two rows of a label and a value: the earlier value, then the later one."""
        table.require_width(2, "a label and a value")
        table.require_rows(2, "the earlier value and the later one")
        before, after = (
            {"label": table.text(row, 0), "value": table.number(row, 1)} for row in (0, 1)
        )
        return {"before": before, "after": after}

    def build(self, scene: "Scene") -> None:
        """Add the chart to the scene and animate it."""
        from manim import (
            AnimationGroup,
            Arrow,
            Create,
            ManimColor,
            UpdateFromAlphaFunc,
            ValueTracker,
            VGroup,
            always_redraw,
            interpolate_color,
        )

        from vizreel.render import elements
        from vizreel.render.numbers_text import NumberGlyphs

        chart = self.chart
        assert isinstance(chart, CompareChart)
        theme, layout = self.theme, self.layout
        fonts, sizes, colors, motion = theme.fonts, theme.sizes, theme.colors, theme.motion
        ease = elements.easing(theme)
        content = layout.content
        before_value, after_value = chart.before.value, chart.after.value

        header = elements.header(chart.title, chart.subtitle, theme, layout)
        source = elements.source_line(chart.source, theme, layout)

        places = decimals_for([0, before_value, after_value], chart.number)
        number_format = chart.number.model_copy(update={"decimals": places})
        number_size = sizes.big_number * NUMBER_SCALE
        before_text = format_number(before_value, number_format, locale=self.locale)
        after_text = format_number(after_value, number_format, locale=self.locale)
        # The earlier value counts up from zero, the later one from the earlier value.
        counts = ((0.0, before_value), (before_value, after_value))
        counted = [
            format_number(value, number_format, locale=self.locale, unit_of=end)
            for start, end in counts
            for value in count_samples(start, end)
        ]
        at_scale = NumberGlyphs(fonts.numbers, number_size, colors.text, sizes.affix_scale)
        widest = max(at_scale(text).width for text in counted)

        change_kind = chart.change
        amount = 0.0
        change_places = 0
        change_glyphs: NumberGlyphs | None = None
        change_size = (0.0, 0.0)
        if change_kind != "none":
            amount = change_amount(before_value, after_value, change_kind)
            change_places = change_decimals(amount, change_kind, chart.number)
            change_color = colors.text
            if chart.trend == "auto" and amount != 0:
                change_color = colors.positive if amount > 0 else colors.negative
            change_glyphs = NumberGlyphs(fonts.numbers, sizes.title, change_color)
            sample = change_glyphs(
                format_change(amount, change_kind, chart.number, change_places, locale=self.locale)
            )
            change_size = (sample.width, sample.height)

        side_gap = px(number_size) * SIDE_GAP
        arrow_room = max(change_size[0] + 2 * side_gap, px(MIN_ARROW_PX))
        side_column = (content.width - 2 * side_gap - arrow_room) / 2
        # Values too wide to sit side by side go one above the other, as in a vertical frame.
        stacked = layout.vertical or widest > side_column + 1e-9
        column = content.width if stacked else side_column
        number_size = fitting_number_size(number_size, widest, column, "the values")
        before_glyphs = NumberGlyphs(fonts.numbers, number_size, colors.muted, sizes.affix_scale)
        after_glyphs = NumberGlyphs(fonts.numbers, number_size, colors.text, sizes.affix_scale)
        widest = max(after_glyphs(text).width for text in counted)

        def label_block(text: str) -> "elements.TextBlock":
            return elements.wrapped_block(
                text, fonts.body, sizes.label, colors.muted, column, "a label", "center"
            )

        before_label, after_label = label_block(chart.before.label), label_block(chart.after.label)
        metrics = elements.line_metrics(fonts.numbers, number_size)
        label_gap = stack_gap(number_size, sizes.label) / 2
        blocks = [
            ValueBlock(metrics.ascent, metrics.descent + label_gap + label.height)
            for label in (before_label, after_label)
        ]
        if stacked:
            placement = place_stacked(
                content.center,
                content.height,
                (blocks[0], blocks[1]),
                change_size,
                px(sizes.label),
                px(MIN_STACKED_ARROW_PX),
            )
        else:
            placement = place_side_by_side(
                content.center,
                content.width,
                max(widest, before_label.mobject.width, after_label.mobject.width),
                max(blocks, key=lambda block: block.height),
                change_size,
                side_gap,
                px(MIN_ARROW_PX),
            )
        for label, (x, baseline) in (
            (before_label, placement.before),
            (after_label, placement.after),
        ):
            label.move_top_to(baseline - metrics.descent - label_gap)
            label.mobject.set_x(x)
        final_before = before_glyphs.at(before_text, *placement.before)
        final_after = after_glyphs.at(after_text, *placement.after)

        (start_x, start_y), (end_x, end_y) = placement.arrow
        arrow = Arrow(
            (start_x, start_y, 0.0),
            (end_x, end_y, 0.0),
            buff=0,
            color=colors.muted,
            stroke_width=stroke_width(sizes.line),
            tip_length=px(sizes.line) * ARROW_TIP,
            max_tip_length_to_length_ratio=1,
            max_stroke_width_to_length_ratio=1000,
        )

        intro = motion.title_fade if len(header) else 0.0
        phases = split_duration(
            chart.duration, intro=intro, highlight=motion.highlight, hold=motion.hold
        )
        half = phases.main / 2
        check_reading_time(
            [(text, 0.0) for text in (chart.title, chart.subtitle, chart.source) if text]
            + [
                (chart.before.label, phases.main_start),
                (chart.after.label, phases.main_start + half),
            ],
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
            scene.play(AnimationGroup(*opening), run_time=motion.title_fade)
            opening = []

        def counting(
            tracker: ValueTracker,
            text: "Callable[[float], str]",
            glyphs: "NumberGlyphs",
            position: tuple[float, float],
        ) -> "VMobject":
            return always_redraw(lambda: glyphs.at(text(tracker.get_value()), *position))

        def count(tracker: ValueTracker, start: float, end: float, run_time: float) -> "Animation":
            def step(mobject: ValueTracker, alpha: float) -> None:
                mobject.set_value(start + (end - start) * alpha)

            # Manim calls the update function with (mobject, alpha) but types it with one
            # argument.
            return UpdateFromAlphaFunc(tracker, step, run_time=run_time, rate_func=ease)  # type: ignore[arg-type]

        def number_text(final: float) -> "Callable[[float], str]":
            return lambda value: format_number(
                value, number_format, locale=self.locale, unit_of=final
            )

        before_tracker = ValueTracker(0.0)
        counting_before = counting(
            before_tracker, number_text(before_value), before_glyphs, placement.before
        )
        scene.add(counting_before)
        scene.play(
            AnimationGroup(
                *opening,
                count(before_tracker, 0.0, before_value, half),
                elements.appear(
                    before_label.mobject,
                    theme,
                    run_time=min(motion.title_fade, half),
                    rate_func=ease,
                ),
            ),
            run_time=half,
        )
        counting_before.clear_updaters()
        scene.remove(counting_before)
        scene.add(final_before)

        after_tracker = ValueTracker(before_value)
        counting_after = counting(
            after_tracker, number_text(after_value), after_glyphs, placement.after
        )
        scene.add(counting_after)
        scene.play(
            AnimationGroup(
                Create(arrow, run_time=min(motion.structure, half), rate_func=ease),
                count(after_tracker, before_value, after_value, half),
                elements.appear(
                    after_label.mobject,
                    theme,
                    run_time=min(motion.title_fade, half),
                    rate_func=ease,
                ),
            ),
            run_time=half,
        )
        counting_after.clear_updaters()
        scene.remove(counting_after)
        scene.add(final_after)

        backdrop = ManimColor(colors.surface if layout.panel else colors.background)
        dimmed = interpolate_color(backdrop, ManimColor(colors.muted), colors.dim_opacity)
        dimming = [
            final_before.animate.set_color(dimmed),
            before_label.mobject.animate.set_color(dimmed),
        ]
        change_count: list[Animation] = []
        counting_change = None
        if change_glyphs is not None and change_kind != "none":
            kind = change_kind

            def change_text(value: float) -> str:
                return format_change(
                    value, kind, chart.number, change_places, locale=self.locale, unit_of=amount
                )

            change_tracker = ValueTracker(0.0)
            change_x, change_y = placement.change
            # The change has no descenders, so its digits stand at the bottom of its ink.
            change_position = (change_x, change_y - change_size[1] / 2)
            counting_change = counting(change_tracker, change_text, change_glyphs, change_position)
            scene.add(counting_change)
            change_count.append(count(change_tracker, 0.0, amount, phases.highlight))
        scene.play(*dimming, *change_count, run_time=phases.highlight, rate_func=ease)
        if counting_change is not None:
            counting_change.clear_updaters()
        scene.wait(phases.hold)
