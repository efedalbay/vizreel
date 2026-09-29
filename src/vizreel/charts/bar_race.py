"""Bars that race through many periods."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from vizreel.charts._race import (
    caption_at,
    check_caption_times,
    check_race_time,
    fill_gaps,
    race_position,
    slot_positions,
    value_at,
)
from vizreel.charts.base import ChartType, arranged, check_reading_time, count_samples
from vizreel.charts.registry import register
from vizreel.errors import RenderError
from vizreel.format.numbers import decimals_for, format_number
from vizreel.render.layout import BAR_FILL, Box, px, stack_gap
from vizreel.spec.data import Table
from vizreel.spec.models import BarRaceChart

if TYPE_CHECKING:
    from manim import Animation, Mobject, Scene, VMobject

PERIOD_SCALE = 0.5
"""Size of the period shown above the bars, as a share of the theme's big number size."""
MAX_LABEL_SHARE = 0.4
"""Most of the content width the series names may take, left of the bars."""
MIN_BAR_SHARE = 0.3
"""Least of the content width left for the longest bar."""
MIN_BAR_PX = 12
"""Least thickness of a bar, in pixels at 1080p."""
LEAVE_DROP = 0.6
"""How far below the last place a bar sinks as it leaves the screen, in places."""
RISING_LOOK_BACK = 0.01
"""How far back along the race a bar's place is compared, in periods, to tell if it rises."""


@dataclass(frozen=True)
class RaceRows:
    """Where the rows of a bar race go, in scene units.

    Attributes:
        label_right: Right edge of the series names, when they are left of the bars.
        bar_left: Where the bars start.
        longest: Length of the bar with the largest value, before its image and value.
        first: Vertical center of the first place's bar.
        pitch: Distance between two places.
        thickness: Thickness of a bar.
        names_above: Whether each name is above its bar instead of left of it.
    """

    label_right: float
    bar_left: float
    longest: float
    first: float
    pitch: float
    thickness: float
    names_above: bool = False

    def center(self, place: float) -> float:
        """The vertical center of a place, which may be between two places."""
        return self.first - place * self.pitch


def plan_race_rows(
    area: Box,
    show: int,
    label_width: float,
    value_width: float,
    gap: float,
    thinnest: float,
    image_aspect: float = 0.0,
) -> RaceRows:
    """Plan `show` rows in `area`: the names in a column, then the bars, images and values.

    Args:
        area: The room for the rows.
        show: How many rows.
        label_width: Width of the widest name.
        value_width: Width of the widest value.
        gap: Space between a name, a bar, an image and a value.
        thinnest: Least thickness of a bar.
        image_aspect: Width of the widest image when it is as tall as a bar, as a share of
            its height; 0 without images.

    Raises:
        RenderError: The names are too wide, the bars too short or too thin.
    """
    if label_width > area.width * MAX_LABEL_SHARE:
        raise RenderError("the series names are too long for the frame; shorten them")
    pitch = area.height / show
    thickness = pitch * BAR_FILL
    bar_left = area.left + label_width + gap
    longest = area.right - _after_bar(value_width, gap, thickness, image_aspect) - bar_left
    _check_bars(area, show, longest, thickness, thinnest)
    first = area.top - pitch / 2
    return RaceRows(area.left + label_width, bar_left, longest, first, pitch, thickness)


def plan_race_rows_above(
    area: Box,
    show: int,
    label_height: float,
    value_width: float,
    gap: float,
    thinnest: float,
    image_aspect: float = 0.0,
) -> RaceRows:
    """Plan `show` rows in `area`, each name above its bar, for a narrow frame.

    The bars have the whole width, as in the rows of a bar chart.

    Raises:
        RenderError: The bars are too short or too thin.
    """
    pitch = area.height / show
    thickness = (pitch - label_height - gap / 2) * BAR_FILL
    longest = area.width - _after_bar(value_width, gap, thickness, image_aspect)
    _check_bars(area, show, longest, thickness, thinnest)
    row = label_height + gap / 2 + thickness
    first = area.top - (pitch - row) / 2 - label_height - gap / 2 - thickness / 2
    return RaceRows(area.left, area.left, longest, first, pitch, thickness, names_above=True)


def _after_bar(value_width: float, gap: float, thickness: float, image_aspect: float) -> float:
    """The room a bar leaves after it, for its image and its value."""
    image = thickness * image_aspect + gap if image_aspect else 0.0
    return gap + image + value_width


def _check_bars(area: Box, show: int, longest: float, thickness: float, thinnest: float) -> None:
    if longest < area.width * MIN_BAR_SHARE:
        raise RenderError("the values are too wide for the bars; use compact numbers")
    if thickness < thinnest:
        raise RenderError(f"{show} bars do not fit the frame; show fewer or shorten the title")


@register
class BarRaceChartType(ChartType):
    """Bars that grow and change places as their values change over many periods.

    The largest `show` bars are on screen, from the largest down, each with its name on the
    left and its value counting at its end, and the period above them. The race runs through
    the periods at one pace and slows to a stop on the last; bars slide to their new places
    as their values pass each other, and bars that enter or leave the largest slide in or out
    at the bottom. The bars are in the accent color, the followed series in the highlight
    color.
    """

    name = "bar-race"
    model = BarRaceChart
    template = """\
- id: market-race                  # unique; lowercase letters, digits and hyphens
  type: bar-race
  title: Northwind's rise in the market
  periods: ["2019", "2020", "2021", "2022"]   # in order; quote years
  series:                          # two to thirty; one value per period, null for a gap
    - { name: Northwind, values: [12, 30, 55, 90] }
    - { name: Contoso, values: [60, 64, 70, 72] }
    - { name: Fabrikam, values: [40, 35, 38, 31] }
  number: { suffix: "M" }
  highlight: { series: Northwind } # optional: the series drawn in the highlight color
  # show: 8                        # optional: how many bars are on screen, 3 to 12
  # source: "Source: example data" # optional
  # duration: 15                   # optional: seconds, at least 2
"""

    @classmethod
    def from_table(cls, table: Table, chart: dict[str, Any]) -> dict[str, Any]:
        """Read the periods from the first column and a series from each other column.

        A series is named by its column's header; an empty cell leaves a gap.
        """
        if table.width < 3:
            table.require_width(3, "the periods and at least two series")
        rows = range(len(table.rows))
        return {
            "periods": [table.text(row, 0) for row in rows],
            "series": [
                {
                    "name": table.header[column],
                    "values": [table.optional_number(row, column) for row in rows],
                }
                for column in range(1, table.width)
            ],
        }

    def _bar_colors(self) -> list[str]:
        """The color of each series' bar: the highlight, its brand color, or the accent.

        Raises:
            RenderError: A brand color is not in the theme.
        """
        assert isinstance(self.chart, BarRaceChart)
        colors = self.theme.colors
        followed = self.chart.highlight.series if self.chart.highlight else None
        result = []
        for series in self.chart.series:
            brand = self.chart.colors.get(series.name)
            if brand is not None and brand not in colors.brand:
                known = ", ".join(f'"{name}"' for name in colors.brand) or "none"
                raise RenderError(
                    f'the color "{brand}" of "{series.name}" is not a brand color of the theme '
                    f"({known}); add it to colors.brand in the theme"
                )
            if series.name == followed:
                result.append(colors.highlight)
            elif brand is not None:
                result.append(colors.brand[brand])
            else:
                result.append(colors.accent)
        return result

    def _images(self, height: float) -> dict[int, "Mobject"]:
        """Load each series' image, `height` tall, by the index of its series.

        Raises:
            RenderError: An image cannot be read.
        """
        from manim import ImageMobject, SVGMobject

        assert isinstance(self.chart, BarRaceChart)
        images: dict[int, Mobject] = {}
        for index, series in enumerate(self.chart.series):
            path = self.chart.images.get(series.name)
            if path is None:
                continue
            try:
                image = SVGMobject(path) if path.lower().endswith(".svg") else ImageMobject(path)
            except Exception as exc:
                raise RenderError(f"cannot read the image {path}: {exc}") from None
            images[index] = image.scale_to_fit_height(height)
        return images

    def build(self, scene: "Scene") -> None:
        """Add the chart to the scene and animate it."""
        from manim import (
            DOWN,
            LEFT,
            RIGHT,
            UP,
            AnimationGroup,
            Group,
            Rectangle,
            UpdateFromAlphaFunc,
            ValueTracker,
            VGroup,
            linear,
        )

        from vizreel.render import elements
        from vizreel.render.numbers_text import NumberGlyphs

        chart = self.chart
        assert isinstance(chart, BarRaceChart)
        theme, layout = self.theme, self.layout
        fonts, sizes, colors, motion = theme.fonts, theme.sizes, theme.colors, theme.motion
        ease = elements.easing(theme)
        content = layout.content
        gap = stack_gap(sizes.label, sizes.label)
        count = len(chart.periods)
        values = [fill_gaps(series.values, 0.0) for series in chart.series]
        filled = [[value or 0.0 for value in series] for series in values]
        bar_colors = self._bar_colors()

        header = elements.header(chart.title, chart.subtitle, theme, layout)
        source = elements.source_line(chart.source, theme, layout)

        every_value = [value for series in filled for value in series]
        value_format = chart.number.model_copy(
            update={"decimals": decimals_for(every_value, chart.number)}
        )
        glyphs = NumberGlyphs(fonts.numbers, sizes.value, colors.text)

        def value_text(value: float) -> "VMobject":
            return glyphs(format_number(value, value_format, locale=self.locale))

        names = [
            elements.text(series.name, fonts.body, sizes.label, colors.muted)
            for series in chart.series
        ]
        period_size = sizes.big_number * PERIOD_SCALE
        period_texts = [
            elements.number_text(period, fonts.numbers, period_size, colors.muted)
            for period in chart.periods
        ]
        period_height = max(text.height for text in period_texts)
        # The total goes under the period, right-aligned, its label in words the spec gives.
        totals = [sum(values_now) for values_now in zip(*filled, strict=True)]
        total_label = (
            elements.text(chart.total, fonts.body, sizes.label, colors.muted)
            if chart.total
            else None
        )

        def total_text(value: float) -> "Mobject":
            assert total_label is not None
            number = value_text(value)
            label = total_label.set_opacity(1.0)
            group = Group(label, number).arrange(RIGHT, buff=gap)
            label.align_to(number, DOWN)
            return group

        total_width = (
            max(total_text(value).width for value in {*totals, *count_samples(0, max(totals))})
            if total_label is not None
            else 0.0
        )
        total_height = total_text(max(totals)).height if total_label is not None else 0.0
        period_width = max(max(text.width for text in period_texts), total_width)
        # Captions go left of the period, above the bars.
        captions = [
            elements.wrapped_block(
                caption.text,
                fonts.body,
                sizes.label,
                colors.text,
                content.width - period_width - gap * 2,
                "the caption",
                "left",
            ).mobject
            for caption in chart.captions
        ]
        number_band = period_height + (total_height + gap / 2 if total_label is not None else 0.0)
        band_height = max([number_band, *(caption.height for caption in captions)])
        caption_starts = [float(chart.periods.index(caption.period)) for caption in chart.captions]
        widest_value = max(
            value_text(value).width for value in {*every_value, *count_samples(0, max(every_value))}
        )
        area = Box(content.left, content.bottom, content.right, content.top - band_height - gap * 2)
        # Images are as tall as a bar; loaded one unit tall, their width is their aspect.
        images = self._images(1.0)
        image_aspect = max((image.width for image in images.values()), default=0.0)
        tallest_name = max(name.height for name in names)
        rows = arranged(
            layout,
            lambda: plan_race_rows(
                area,
                chart.show,
                max(name.width for name in names),
                widest_value,
                gap,
                max(px(MIN_BAR_PX), tallest_name * BAR_FILL),
                image_aspect,
            ),
            lambda: plan_race_rows_above(
                area, chart.show, tallest_name, widest_value, gap, px(MIN_BAR_PX), image_aspect
            ),
        )
        for image in images.values():
            image.scale_to_fit_height(rows.thickness)

        def place_name(name: "VMobject", y: float) -> "VMobject":
            if rows.names_above:
                name.align_to((rows.bar_left, 0.0, 0.0), LEFT)
                return name.align_to((0.0, y + rows.thickness / 2 + gap / 2, 0.0), DOWN)
            return name.align_to((rows.label_right, 0.0, 0.0), RIGHT).set_y(y)

        places_at = slot_positions(filled, ease)

        # Every frame places the same name and period mobjects again rather than copies of
        # them: Manim's copies of text take longer than drawing the frame.
        def period_at(position: float) -> "VMobject":
            text = period_texts[min(max(round(position), 0), count - 1)]
            return text.align_to((content.right, content.top, 0.0), UP + RIGHT)

        def total_at(value: float) -> "Mobject":
            total = total_text(value)
            top = content.top - period_height - gap / 2
            return total.align_to((content.right, top, 0.0), UP + RIGHT)

        def race_frame(position: float, grown: float, with_names: bool) -> "Mobject":
            now = [value_at(series, position) for series in filled]
            places = places_at(position)
            before = places_at(max(position - RISING_LOOK_BACK, 0.0))
            largest = max(now) or 1.0
            drawn = sorted(
                (index for index, place in enumerate(places) if place < chart.show),
                key=lambda index: (places[index] < before[index] - 1e-9, -places[index]),
            )
            group = Group()
            for index in drawn:
                place = places[index]
                opacity = min(chart.show - place, 1.0)
                y = rows.center(min(place, chart.show - 1 + LEAVE_DROP))
                length = rows.longest * now[index] / largest * grown
                color = bar_colors[index]
                row = Group()
                if length > 0:
                    bar = Rectangle(
                        width=length,
                        height=rows.thickness,
                        stroke_width=0,
                        fill_color=elements.color(color),
                        fill_opacity=opacity,
                    )
                    row.add(bar.move_to((rows.bar_left + length / 2, y, 0.0)))
                if with_names:
                    name = names[index].set_opacity(opacity)
                    row.add(place_name(name, y))
                start = rows.bar_left + length + gap
                image = images.get(index)
                if image is not None and grown > 0:
                    image.set_opacity(opacity)
                    row.add(image.align_to((start, 0.0, 0.0), LEFT).set_y(y))
                    start += image.width + gap
                if grown > 0:
                    number = value_text(now[index] * grown).set_opacity(opacity)
                    row.add(number.align_to((start, 0.0, 0.0), LEFT).set_y(y))
                group.add(row)
            if with_names:
                group.add(period_at(position))
                if total_label is not None:
                    group.add(total_at(sum(now)))
                shown = caption_at(caption_starts, position)
                if shown is not None and shown[1] > 0:
                    caption = captions[shown[0]].set_opacity(shown[1])
                    caption.align_to((content.left, 0.0, 0.0), LEFT)
                    group.add(caption.set_y(content.top - band_height / 2))
            return group

        intro = (motion.title_fade if len(header) else 0.0) + motion.structure
        race_seconds = chart.duration - intro - motion.hold
        check_race_time(race_seconds, count, chart.duration)
        check_caption_times(
            [
                (caption.text, start)
                for caption, start in zip(chart.captions, caption_starts, strict=True)
            ],
            intro,
            race_seconds,
            count,
            chart.duration,
        )
        check_reading_time(
            [(text, 0.0) for text in (chart.title, chart.subtitle, chart.source) if text],
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

        # The names and the first period appear while the bars grow to their first values.
        first_places = places_at(0.0)
        labels = Group(
            *(
                place_name(names[index].copy(), rows.center(place))
                for index, place in enumerate(first_places)
                if place < chart.show
            ),
            period_at(0.0).copy(),
            *([total_at(totals[0]).copy()] if total_label is not None else []),
        )
        growth = ValueTracker(0.0)

        def advance(tracker: ValueTracker, alpha: float) -> None:
            tracker.set_value(alpha)

        growing = elements.redrawn(lambda: race_frame(0.0, ease(growth.get_value()), False))
        scene.add(growing)
        scene.play(
            AnimationGroup(
                *opening,
                elements.appear(labels, theme, run_time=motion.structure, rate_func=ease),
                UpdateFromAlphaFunc(growth, advance, run_time=motion.structure, rate_func=linear),  # type: ignore[arg-type]
            ),
            run_time=motion.structure,
        )
        scene.remove(growing, labels)

        seconds = ValueTracker(0.0)
        racing = elements.redrawn(
            lambda: race_frame(race_position(seconds.get_value(), race_seconds, count), 1.0, True)
        )
        scene.add(racing)
        scene.play(seconds.animate.set_value(race_seconds), run_time=race_seconds, rate_func=linear)
        racing.clear_updaters()
        scene.wait(motion.hold)
