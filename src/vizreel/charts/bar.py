"""Compare categories."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from vizreel.charts.base import (
    ChartType,
    check_reading_time,
    split_duration,
    staggered_progress,
)
from vizreel.charts.registry import register
from vizreel.errors import RenderError
from vizreel.format.numbers import format_number, shared_decimals
from vizreel.render.layout import BAR_FILL, LABEL_FILL, px, stack_gap, stroke_width
from vizreel.render.scales import LinearScale, band_centers, two_line_splits
from vizreel.spec.models import Bar, BarChart

if TYPE_CHECKING:
    from manim import Animation, Scene, VMobject

    from vizreel.render.elements import TextBlock

MIN_BAR_AREA_PX = 120
"""Least height, in pixels at 1080p, left for the tallest column."""
MIN_ROW_THICKNESS_PX = 16
"""Least thickness, in pixels at 1080p, of the bar in a row."""
MAX_ROW_THICKNESS = 1.5
"""Most thickness of the bar in a row, as a multiple of the value font size."""
MAX_ROW_GAP = 0.8
"""Most space between rows, as a multiple of the height of a row."""
MIN_ROW_LENGTH = 0.4
"""Least share of the content width left for the longest row after its value label."""


def sorted_bars(chart: BarChart) -> list[Bar]:
    """Return the bars in display order."""
    if chart.sort == "asc":
        return sorted(chart.bars, key=lambda bar: bar.value)
    if chart.sort == "desc":
        return sorted(chart.bars, key=lambda bar: bar.value, reverse=True)
    return list(chart.bars)


def uses_rows(chart: BarChart, vertical_frame: bool) -> bool:
    """Whether the bars are drawn as rows rather than columns."""
    return chart.layout == "rows" or (chart.layout == "auto" and vertical_frame)


@dataclass(frozen=True)
class Row:
    """Where one row of a bar chart goes, in scene units.

    Attributes:
        label_top: Top of the row's label.
        bar_center: Vertical center of the row's bar.
        thickness: Height of the row's bar.
    """

    label_top: float
    bar_center: float
    thickness: float


def plan_rows(
    count: int,
    top: float,
    bottom: float,
    label_height: float,
    label_gap: float,
    thickness_range: tuple[float, float],
) -> list[Row]:
    """Stack `count` rows, each a label above a bar, centered between `bottom` and `top`.

    Each row gets an equal share of the height. The bar takes `BAR_FILL` of what the label
    leaves, within `thickness_range`; the gap between rows is at most `MAX_ROW_GAP` rows, so a
    few rows stay together instead of spreading over a tall frame.

    Raises:
        RenderError: The bars would be thinner than the least thickness.
    """
    thinnest, thickest = thickness_range
    share = (top - bottom) / count
    thickness = min((share - label_height - label_gap) * BAR_FILL, thickest)
    if thickness < thinnest:
        raise RenderError("not enough room for the bars; shorten the title or the labels")
    row_height = label_height + label_gap + thickness
    gap = min(share - row_height, row_height * MAX_ROW_GAP)
    total = count * row_height + (count - 1) * gap
    first_top = (top + bottom + total) / 2
    rows = []
    for index in range(count):
        row_top = first_top - index * (row_height + gap)
        rows.append(Row(row_top, row_top - label_height - label_gap - thickness / 2, thickness))
    return rows


@dataclass(frozen=True)
class BarGeometry:
    """Where the parts of a bar chart go, for columns or rows.

    Attributes:
        labels: The category labels, in place.
        bar: Builds bar `index` grown by a share from 0 to 1, in a fill color.
        value: Builds the value label of bar `index` grown by a share, at the bar's end.
        axis: The line the bars grow from, or None.
    """

    labels: list["VMobject"]
    bar: Callable[[int, float, str], "VMobject"]
    value: Callable[[int, float], "VMobject"]
    axis: "VMobject | None"


@register
class BarChartType(ChartType):
    """One bar per category, with a value label on every bar and no value axis.

    Columns grow up from a baseline, with the labels below it. Rows grow to the right, each
    under its label, which leaves labels the whole width; vertical frames use rows. The title
    fades in, the labels appear, then the bars grow one after another while their values
    count. At the highlight beat the highlighted bar turns to the highlight color and the
    others to muted.
    """

    name = "bar"
    model = BarChart
    template = """\
- id: regions                      # unique; lowercase letters, digits and hyphens
  type: bar
  title: Northwind revenue by region
  bars:                            # two to eight bars; values zero or more
    - { label: North, value: 412000000 }
    - { label: South, value: 298000000 }
    - { label: East, value: 187500000 }
  number: { prefix: "$", compact: true }
  highlight: { label: East }       # optional: the bar that carries the message
  # sort: desc                     # optional: none, asc or desc
  # layout: rows                   # optional: auto, columns or rows; rows fit long labels
  # subtitle: Fiscal year 2022     # optional
  # source: "Source: example data" # optional
  # duration: 5                    # optional: seconds, at least 2
"""

    def build(self, scene: "Scene") -> None:
        """Add the chart to the scene and animate it."""
        from manim import (
            AnimationGroup,
            Create,
            FadeIn,
            ValueTracker,
            VGroup,
            always_redraw,
            linear,
        )

        from vizreel.render import elements
        from vizreel.render.numbers_text import NumberGlyphs

        chart = self.chart
        assert isinstance(chart, BarChart)
        theme, layout = self.theme, self.layout
        fonts, sizes, colors, motion = theme.fonts, theme.sizes, theme.colors, theme.motion
        ease = elements.easing(theme)
        bars = sorted_bars(chart)
        count = len(bars)

        header = elements.header(chart.title, chart.subtitle, theme, layout)
        source = elements.source_line(chart.source, theme, layout)
        value_formats = [
            chart.number.model_copy(update={"decimals": places})
            for places in shared_decimals([bar.value for bar in bars], chart.number)
        ]
        glyphs = NumberGlyphs(fonts.numbers, sizes.value, colors.text)

        def value_text(index: int, grown: float) -> "VMobject":
            return glyphs(format_number(bars[index].value * grown, value_formats[index]))

        final_values = [value_text(index, 1.0) for index in range(count)]
        if uses_rows(chart, layout.vertical):
            geometry = self._rows(bars, value_text, final_values)
        else:
            geometry = self._columns(bars, value_text, final_values)

        intro = (motion.title_fade if len(header) else 0.0) + motion.structure
        phases = split_duration(
            chart.duration,
            intro=intro,
            highlight=motion.highlight if chart.highlight else 0.0,
            hold=motion.hold,
        )
        labels_appear = motion.title_fade if len(header) else 0.0
        check_reading_time(
            [(text, 0.0) for text in (chart.title, chart.subtitle, chart.source) if text]
            + [(bar.label, labels_appear) for bar in bars],
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
        structure = [
            *opening,
            *(
                [Create(geometry.axis, run_time=motion.structure, rate_func=ease)]
                if geometry.axis
                else []
            ),
            FadeIn(VGroup(*geometry.labels), run_time=motion.structure, rate_func=ease),
        ]
        scene.play(AnimationGroup(*structure), run_time=motion.structure)

        progress = ValueTracker(0.0)

        def grown(index: int) -> float:
            local = staggered_progress(
                progress.get_value(), index, count, stagger=motion.stagger, total=phases.main
            )
            return ease(local)

        def growing_bar(index: int) -> "VMobject":
            return always_redraw(lambda: geometry.bar(index, grown(index), colors.accent))

        def counting_value(index: int) -> "VMobject":
            return always_redraw(lambda: geometry.value(index, grown(index)))

        growing = [growing_bar(index) for index in range(count)]
        counting = [counting_value(index) for index in range(count)]
        scene.add(*growing, *counting)
        scene.play(progress.animate.set_value(1.0), run_time=phases.main, rate_func=linear)

        final_bars = [geometry.bar(index, 1.0, colors.accent) for index in range(count)]
        for index, value_mobject in enumerate(final_values):
            value_mobject.move_to(geometry.value(index, 1.0).get_center())
        scene.remove(*growing, *counting)
        scene.add(*final_bars, *final_values)

        if chart.highlight:
            highlighted = chart.highlight.label
            recolor = [
                bar_mobject.animate.set_fill(colors.highlight, opacity=1)
                if bar.label == highlighted
                else bar_mobject.animate.set_fill(colors.muted, opacity=colors.dim_opacity)
                for bar_mobject, bar in zip(final_bars, bars, strict=True)
            ]
            scene.play(*recolor, run_time=phases.highlight, rate_func=ease)
        scene.wait(phases.hold)

    def _columns(
        self,
        bars: list[Bar],
        value_text: Callable[[int, float], "VMobject"],
        final_values: list["VMobject"],
    ) -> BarGeometry:
        """Columns growing up from a baseline, with the labels under the baseline."""
        from manim import Line, Rectangle, VGroup

        from vizreel.render import elements

        fonts, sizes, colors = self.theme.fonts, self.theme.sizes, self.theme.colors
        content = self.layout.content
        count = len(bars)
        slot = content.width / count
        centers = band_centers(count, content.left, content.right)
        label_gap = stack_gap(sizes.label, sizes.label)

        def category_label(content_text: str) -> "TextBlock":
            max_width = slot * LABEL_FILL
            single = elements.text_block(content_text, fonts.body, sizes.label, colors.muted)
            if single.mobject.width <= max_width:
                return single
            for split in two_line_splits(content_text):
                lines = [
                    elements.text(part, fonts.body, sizes.label, colors.muted) for part in split
                ]
                if all(line.width <= max_width for line in lines):
                    return elements.paragraph_block(
                        list(split), fonts.body, sizes.label, colors.muted
                    )
            raise RenderError(
                f'bar label "{content_text}" is too long for {count} bars; shorten it '
                "or use layout: rows"
            )

        label_blocks = [category_label(bar.label) for bar in bars]
        labels_height = max(block.height for block in label_blocks)
        baseline = content.bottom + labels_height + label_gap
        for block, center in zip(label_blocks, centers, strict=True):
            block.move_top_to(baseline - label_gap)
            block.mobject.set_x(center)

        for final_label, bar in zip(final_values, bars, strict=True):
            if final_label.width > slot * LABEL_FILL:
                raise RenderError(
                    f'the value of "{bar.label}" is too wide for {count} bars; '
                    "use compact numbers or fewer bars"
                )
        value_gap = stack_gap(sizes.value, sizes.value)
        top = content.top - max(label.height for label in final_values) - value_gap
        if top - baseline < px(MIN_BAR_AREA_PX):
            raise RenderError("not enough room for the bars; shorten the title or the labels")
        scale = LinearScale((0, max(bar.value for bar in bars) or 1), (baseline, top))
        bar_width = slot * BAR_FILL

        def bar_rectangle(index: int, grown: float, fill: str) -> "VMobject":
            height = (scale(bars[index].value) - baseline) * grown
            if height <= 0:
                return VGroup()
            rectangle = Rectangle(
                width=bar_width, height=height, stroke_width=0, fill_color=fill, fill_opacity=1
            )
            return rectangle.move_to((centers[index], baseline + height / 2, 0.0))

        def value_at(index: int, grown: float) -> "VMobject":
            if grown <= 0:
                return VGroup()
            label = value_text(index, grown)
            bar_top = baseline + (scale(bars[index].value) - baseline) * grown
            return label.move_to((centers[index], bar_top + value_gap + label.height / 2, 0.0))

        base_line = Line(
            (content.left, baseline, 0.0),
            (content.right, baseline, 0.0),
            color=colors.grid,
            stroke_width=stroke_width(sizes.grid_line),
        )
        return BarGeometry(
            [block.mobject for block in label_blocks], bar_rectangle, value_at, base_line
        )

    def _rows(
        self,
        bars: list[Bar],
        value_text: Callable[[int, float], "VMobject"],
        final_values: list["VMobject"],
    ) -> BarGeometry:
        """Rows growing to the right, each bar under its label, values at the bar ends."""
        from manim import LEFT, Rectangle, VGroup

        from vizreel.render import elements

        fonts, sizes, colors = self.theme.fonts, self.theme.sizes, self.theme.colors
        content = self.layout.content
        count = len(bars)
        label_gap = stack_gap(sizes.label, sizes.label) / 2
        value_gap = stack_gap(sizes.value, sizes.value)

        def row_label(content_text: str) -> "TextBlock":
            single = elements.text_block(content_text, fonts.body, sizes.label, colors.muted)
            if single.mobject.width <= content.width:
                return single
            for split in two_line_splits(content_text):
                lines = [
                    elements.text(part, fonts.body, sizes.label, colors.muted) for part in split
                ]
                if all(line.width <= content.width for line in lines):
                    return elements.paragraph_block(
                        list(split), fonts.body, sizes.label, colors.muted, align="left"
                    )
            raise RenderError(f'bar label "{content_text}" is too long; shorten it')

        label_blocks = [row_label(bar.label) for bar in bars]
        rows = plan_rows(
            count,
            content.top,
            content.bottom,
            max(block.height for block in label_blocks),
            label_gap,
            (px(MIN_ROW_THICKNESS_PX), px(sizes.value) * MAX_ROW_THICKNESS),
        )
        for block, row in zip(label_blocks, rows, strict=True):
            block.move_top_to(row.label_top)
            block.mobject.align_to((content.left, 0.0, 0.0), LEFT)

        longest = content.width - value_gap - max(label.width for label in final_values)
        if longest < content.width * MIN_ROW_LENGTH:
            raise RenderError("the values are too wide for the bars; use compact numbers")
        scale = LinearScale(
            (0, max(bar.value for bar in bars) or 1), (content.left, content.left + longest)
        )

        def length(index: int, grown: float) -> float:
            return (scale(bars[index].value) - content.left) * grown

        def bar_rectangle(index: int, grown: float, fill: str) -> "VMobject":
            width = length(index, grown)
            if width <= 0:
                return VGroup()
            rectangle = Rectangle(
                width=width,
                height=rows[index].thickness,
                stroke_width=0,
                fill_color=fill,
                fill_opacity=1,
            )
            return rectangle.move_to((content.left + width / 2, rows[index].bar_center, 0.0))

        def value_at(index: int, grown: float) -> "VMobject":
            if grown <= 0:
                return VGroup()
            label = value_text(index, grown)
            start = content.left + length(index, grown) + value_gap
            return label.move_to((start + label.width / 2, rows[index].bar_center, 0.0))

        return BarGeometry([block.mobject for block in label_blocks], bar_rectangle, value_at, None)
