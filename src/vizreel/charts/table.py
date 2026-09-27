"""A few rows and columns."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from vizreel.charts.base import (
    ChartType,
    check_reading_time,
    split_duration,
    staggered_progress,
)
from vizreel.charts.registry import register
from vizreel.errors import RenderError
from vizreel.format.numbers import format_number, shared_decimals
from vizreel.render.layout import px, stroke_width
from vizreel.spec.models import NumberFormat, TableChart

if TYPE_CHECKING:
    from manim import Animation, Mobject, Scene, VMobject

MIN_COLUMN_GAP = 1.0
"""Least space between two columns, as a multiple of the cell text size."""
MAX_COLUMN_GAP = 3.0
"""Most space between two columns, as a multiple of the cell text size; a narrow table is
centered instead of spreading over the whole width."""
ROW_PITCH = 2.0
"""Distance between the baselines of two rows, as a multiple of the cell text size."""
BAND_STRENGTH = 0.18
"""How much of the highlight color the band behind the highlighted row mixes into the
background: enough to see, while its text keeps its contrast."""


@dataclass(frozen=True)
class TablePlacement:
    """Where the columns and rows of a table go, in scene units.

    Attributes:
        lefts: Left edge of each column.
        widths: Width of each column.
        header_baseline: Baseline of the column names.
        rule_y: Height of the line under the column names.
        baselines: Baseline of each row.
    """

    lefts: list[float]
    widths: list[float]
    header_baseline: float
    rule_y: float
    baselines: list[float]


def place_table(
    center: tuple[float, float],
    size: tuple[float, float],
    widths: list[float],
    rows: int,
    cell_px: float,
) -> TablePlacement:
    """Place the columns and rows of a table, centered in a space of `size`.

    Columns keep their widths; the space between them grows up to `MAX_COLUMN_GAP` times the
    cell text size. Rows are `ROW_PITCH` text sizes apart, the column names one pitch above
    the first row with the line halfway between.

    Raises:
        RenderError: The columns do not fit side by side, or the rows do not fit.
    """
    width, height = size
    label = px(cell_px)
    free = width - sum(widths)
    gap = min(free / (len(widths) - 1), label * MAX_COLUMN_GAP)
    if gap < label * MIN_COLUMN_GAP - 1e-9:
        raise RenderError(
            "the table is too wide for the frame; use compact numbers or fewer columns"
        )
    pitch = label * ROW_PITCH
    total_height = pitch * rows + label
    if total_height > height + 1e-9:
        raise RenderError("not enough room for the rows; use fewer rows or shorten the title")
    total_width = sum(widths) + gap * (len(widths) - 1)
    x, y = center
    lefts = []
    left = x - total_width / 2
    for column_width in widths:
        lefts.append(left)
        left += column_width + gap
    header_baseline = y + total_height / 2 - label
    return TablePlacement(
        lefts=lefts,
        widths=widths,
        header_baseline=header_baseline,
        rule_y=header_baseline - pitch / 2 + label / 4,
        baselines=[header_baseline - pitch * (index + 1) for index in range(rows)],
    )


@dataclass
class _TableFinal:
    """The drawn table, which the emphasis changes: its cells and the band."""

    texts: dict[tuple[int, int], "VMobject"]
    numbers: dict[tuple[int, int], "VMobject"]
    band: "VMobject"
    band_x: float
    band_ys: list[float]
    band_shown: bool = False
    """Whether the band is on screen, behind an emphasized row."""


@register
class TableChartType(ChartType):
    """A few rows and columns: row names, then numbers or text.

    The column names and a thin line appear first; then the rows appear one after another
    from the top, their numbers counting up. Text is set flush left and numbers flush right,
    with tabular figures so digits line up. At the highlight beat a soft band in the
    highlight color appears behind the highlighted row and the other rows dim.
    """

    name = "table"
    model = TableChart
    template = """\
- id: top-markets                  # unique; lowercase letters, digits and hyphens
  type: table
  title: Northwind's largest markets
  columns:                         # two to four; the first holds the row names
    - { name: Market }
    - { name: Revenue, number: { prefix: "$", compact: true } }
    - { name: Growth, number: { suffix: "%" } }
  rows:                            # two to eight, one cell per column
    - [Germany, 412000000, 12]
    - [France, 298000000, -3]
    - [Japan, 187500000, 21]
  # highlight: { row: Japan }      # optional: the row to emphasize
  # subtitle: Fiscal year 2023     # optional
  # source: "Source: example data" # optional
  # duration: 6                    # optional: seconds, at least 2
"""

    def build(self, scene: "Scene") -> None:
        """Add the table to the scene and animate it."""
        from manim import (
            LEFT,
            AnimationGroup,
            Create,
            FadeIn,
            Line,
            ManimColor,
            Rectangle,
            ValueTracker,
            VGroup,
            always_redraw,
            interpolate_color,
            linear,
        )

        from vizreel.render import elements
        from vizreel.render.numbers_text import NumberGlyphs

        chart = self.chart
        assert isinstance(chart, TableChart)
        theme, layout = self.theme, self.layout
        fonts, sizes, colors, motion = theme.fonts, theme.sizes, theme.colors, theme.motion
        ease = elements.easing(theme)
        content = layout.content
        columns, rows = chart.columns, chart.rows
        column_count, row_count = len(columns), len(rows)
        numeric = [chart.numeric(column) for column in range(column_count)]

        header = elements.header(chart.title, chart.subtitle, theme, layout)
        source = elements.source_line(chart.source, theme, layout)

        formats: list[list[NumberFormat]] = []
        for column in range(column_count):
            if numeric[column]:
                values = [float(row[column]) for row in rows]
                places = shared_decimals(values, columns[column].number)
                formats.append(
                    [columns[column].number.model_copy(update={"decimals": p}) for p in places]
                )
            else:
                formats.append([])

        def number_text(row: int, column: int, value: float) -> str:
            return format_number(value, formats[column][row], locale=self.locale)

        names = [
            elements.text_block(column.name, fonts.body, sizes.label, colors.muted)
            for column in columns
        ]

        def cells_at(
            size_px: float,
        ) -> tuple[NumberGlyphs, dict[tuple[int, int], elements.TextBlock], list[float]]:
            """Build the cells at a text size and measure the width of each column."""
            glyphs = NumberGlyphs(fonts.numbers, size_px, colors.text)
            texts = {
                (row, column): elements.text_block(
                    str(rows[row][column]),
                    fonts.body,
                    size_px,
                    colors.text if column == 0 else colors.muted,
                )
                for row in range(row_count)
                for column in range(column_count)
                if not numeric[column]
            }
            widths = []
            for column in range(column_count):
                cells = [names[column].mobject.width]
                for row in range(row_count):
                    if numeric[column]:
                        text = number_text(row, column, float(rows[row][column]))
                        cells.append(glyphs(text).width)
                    else:
                        cells.append(texts[row, column].mobject.width)
                widths.append(max(cells))
            return glyphs, texts, widths

        # The cells take the largest theme text size at which the table fits, so a short
        # table reads well on a phone and a long one still fits.
        candidates = sorted({sizes.title, sizes.subtitle, sizes.value, sizes.label}, reverse=True)
        for size_px in candidates:
            glyphs, texts, widths = cells_at(size_px)
            try:
                placement = place_table(
                    content.center, (content.width, content.height), widths, row_count, size_px
                )
                break
            except RenderError:
                if size_px == candidates[-1]:
                    raise

        def edge(column: int) -> tuple[float, bool]:
            """The x a column's cells line up on, and whether they are flush right."""
            if numeric[column]:
                return placement.lefts[column] + placement.widths[column], True
            return placement.lefts[column], False

        def place_text(block: "elements.TextBlock", column: int, baseline: float) -> None:
            x, right = edge(column)
            content_text = block.lines[0]
            block.mobject.shift(
                (
                    0.0,
                    baseline
                    - elements.baseline(block.mobject, content_text, block.style, block.size_px),
                    0.0,
                )
            )
            if right:
                block.mobject.shift((x - block.mobject.get_right()[0], 0.0, 0.0))
            else:
                block.mobject.align_to((x, 0.0, 0.0), LEFT)

        for column, name in enumerate(names):
            place_text(name, column, placement.header_baseline)
        for (row, column), block in texts.items():
            place_text(block, column, placement.baselines[row])

        def number_at(row: int, column: int, value: float) -> "VMobject":
            x, _ = edge(column)
            text = glyphs.at(number_text(row, column, value), 0.0, placement.baselines[row])
            return text.shift((x - text.get_right()[0], 0.0, 0.0))

        table_left = placement.lefts[0]
        table_right = placement.lefts[-1] + placement.widths[-1]
        rule = Line(
            (table_left, placement.rule_y, 0.0),
            (table_right, placement.rule_y, 0.0),
            color=colors.grid,
            stroke_width=stroke_width(sizes.grid_line),
        )

        intro = (motion.title_fade if len(header) else 0.0) + motion.structure
        phases = split_duration(
            chart.duration,
            intro=intro,
            highlight=motion.highlight if chart.highlight else 0.0,
            hold=motion.hold,
        )
        check_reading_time(
            [(text, 0.0) for text in (chart.title, chart.subtitle, chart.source) if text]
            + [(column.name, intro) for column in columns]
            + [
                (
                    " ".join(str(cell) for cell in row),
                    phases.main_start + phases.main * index / row_count,
                )
                for index, row in enumerate(rows)
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
        scene.play(
            AnimationGroup(
                *opening,
                Create(rule, run_time=motion.structure, rate_func=ease),
                FadeIn(
                    VGroup(*(name.mobject for name in names)),
                    run_time=motion.structure,
                    rate_func=ease,
                ),
            ),
            run_time=motion.structure,
        )

        progress = ValueTracker(0.0)

        def grown(row: int) -> float:
            local = staggered_progress(
                progress.get_value(), row, row_count, stagger=motion.stagger * 3, total=phases.main
            )
            return ease(local)

        def fade_with_row(mobject: "Mobject", row: int) -> None:
            # Setting the opacity in place is much cheaper than copying the text every frame.
            def update(target: "Mobject") -> None:
                target.set_opacity(grown(row))

            mobject.set_opacity(0.0)
            mobject.add_updater(update)

        def counting(row: int, column: int) -> "VMobject":
            """A number that counts up while it fades in with its row."""
            value = float(rows[row][column])

            def build() -> "VMobject":
                amount = grown(row)
                if amount <= 0:
                    return VGroup()
                return number_at(row, column, value * amount).set_opacity(amount)

            return always_redraw(build)

        for (row, _), block in texts.items():
            fade_with_row(block.mobject, row)
        counters = [
            counting(row, column)
            for row in range(row_count)
            for column in range(column_count)
            if numeric[column]
        ]
        scene.add(*(block.mobject for block in texts.values()), *counters)
        scene.play(progress.animate.set_value(1.0), run_time=phases.main, rate_func=linear)

        numbers = {
            (row, column): number_at(row, column, float(rows[row][column]))
            for row in range(row_count)
            for column in range(column_count)
            if numeric[column]
        }
        for block in texts.values():
            block.mobject.clear_updaters()
            block.mobject.set_opacity(1.0)
        scene.remove(*counters)
        scene.add(*numbers.values())

        label = px(size_px)
        band = Rectangle(
            width=table_right - table_left + label,
            height=label * ROW_PITCH * 0.8,
            stroke_width=0,
            fill_color=interpolate_color(
                ManimColor(colors.surface if layout.panel else colors.background),
                ManimColor(colors.highlight),
                BAND_STRENGTH,
            ),
            fill_opacity=1,
        )
        band.set_z_index(elements.PANEL_Z_INDEX + 0.5)
        self._final = _TableFinal(
            texts={key: block.mobject for key, block in texts.items()},
            numbers=numbers,
            band=band,
            band_x=(table_left + table_right) / 2,
            band_ys=[baseline + label / 3 for baseline in placement.baselines],
        )

        if chart.highlight:
            scene.play(
                *self.emphasis(chart.highlight.row), run_time=phases.highlight, rate_func=ease
            )
        scene.wait(phases.hold)

    def emphasis(self, item: Any) -> list[Any]:
        """Put a soft band behind the row named `item` and dim the other rows.

        The band fades in the first time and moves to the new row after that; the emphasized
        row's text returns to its own colors.
        """
        from manim import FadeIn, ManimColor, interpolate_color

        assert isinstance(self.chart, TableChart)
        colors = self.theme.colors
        final = self._final
        highlighted = self.chart.row_names.index(item)
        backdrop = ManimColor(colors.surface if self.layout.panel else colors.background)

        def look(row: int, color: str) -> Any:
            if row == highlighted:
                return ManimColor(color)
            return interpolate_color(backdrop, ManimColor(color), colors.dim_opacity)

        target = (final.band_x, final.band_ys[highlighted], 0.0)
        animations: list[Any] = []
        if final.band_shown:
            animations.append(final.band.animate.move_to(target))
        else:
            final.band.move_to(target)
            animations.append(FadeIn(final.band))
            final.band_shown = True
        for (row, column), text in final.texts.items():
            original = colors.text if column == 0 else colors.muted
            animations.append(text.animate.set_color(look(row, original)))
        for (row, _), number in final.numbers.items():
            animations.append(number.animate.set_color(look(row, colors.text)))
        return animations
