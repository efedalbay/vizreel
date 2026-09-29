from pathlib import Path

import pytest

from vizreel.charts._race import (
    SWAP_PERIODS,
    check_race_time,
    fill_gaps,
    order_at,
    race_position,
    slot_positions,
    value_at,
)
from vizreel.charts.bar_race import plan_race_rows
from vizreel.charts.line_race import axis_top, race_gaps
from vizreel.errors import RenderError, SpecError
from vizreel.render.layout import BAR_FILL, Box
from vizreel.spec.loader import load_spec, parse_spec
from vizreel.spec.models import BarRaceChart, LineRaceChart

ROOT = Path(__file__).parents[2]


def linear(share: float) -> float:
    return share


def test_gaps_fill_in_a_straight_line_and_keep_the_last_value() -> None:
    assert fill_gaps([None, 1, None, 3, None], 0.0) == [0.0, 1, 2.0, 3, 3]
    assert fill_gaps([None, 2], None) == [None, 2]


def test_a_line_is_not_drawn_before_its_first_value_or_after_its_last() -> None:
    assert race_gaps([None, 1, None, 3, None]) == [None, 1, 2.0, 3, None]


def test_values_run_in_a_straight_line_between_periods() -> None:
    assert value_at([0, 10, 20], 1.5) == 15
    assert value_at([0, 10, 20], 0) == 0
    assert value_at([0, 10, 20], 2) == 20
    assert value_at([0, 10, 20], 5) == 20


def test_the_order_is_from_the_largest_value_and_ties_keep_their_order() -> None:
    assert order_at([[1, 5], [3, 2]], 0) == [1, 0]
    assert order_at([[1, 5], [3, 2]], 1) == [0, 1]
    assert order_at([[2, 2], [2, 2]], 0.5) == [0, 1]


def test_a_race_runs_at_one_pace_then_slows_to_a_stop_on_its_last_period() -> None:
    total, periods = 10.0, 5
    positions = [race_position(total * step / 100, total, periods) for step in range(101)]

    assert positions[0] == 0
    assert positions[-1] == periods - 1
    assert all(later >= earlier for earlier, later in zip(positions, positions[1:], strict=False))
    # Three periods at one pace take 3/5 of the time; the last takes the other 2/5.
    assert race_position(6.0, total, periods) == pytest.approx(3.0)
    steps = [later - earlier for earlier, later in zip(positions, positions[1:], strict=False)]
    assert steps[0] == pytest.approx(steps[50])
    assert steps[-1] < steps[0] / 10


def test_a_race_needs_time_for_its_periods() -> None:
    check_race_time(4.8, 24, 15)

    with pytest.raises(RenderError, match="duration 5s is too short for 24 periods; use at least"):
        check_race_time(2.0, 24, 5)


def test_two_series_change_places_briefly_and_smoothly() -> None:
    places = slot_positions([[1, 5], [3, 2]], linear)

    assert places(0) == [1, 0]
    assert places(1) == [0, 1]
    # They cross at 0.4 and slide past each other over SWAP_PERIODS.
    assert places(0.4 + SWAP_PERIODS / 2) == pytest.approx([0.5, 0.5])


def test_bars_of_a_real_race_overlap_only_while_they_change_places() -> None:
    chart = load_spec(ROOT / "examples" / "data.yaml").charts
    race = next(chart for chart in chart if isinstance(chart, BarRaceChart))
    series = [[value or 0.0 for value in fill_gaps(item.values, 0.0)] for item in race.series]
    places = slot_positions(series, linear)
    last = len(race.periods) - 1

    for step in range(last * 50 + 1):
        now = places(last * step / (last * 50))
        for first in range(len(now)):
            for second in range(first + 1, len(now)):
                if abs(now[first] - now[second]) < BAR_FILL:
                    # Bars whose lanes overlap are both on their way to a new place.
                    assert now[first] % 1 and now[second] % 1


def test_race_rows_fill_the_area_and_check_what_fits() -> None:
    area = Box(0.0, 0.0, 10.0, 8.0)
    rows = plan_race_rows(area, 8, 2.0, 1.0, 0.2, 0.1)

    assert rows.pitch == 1.0
    assert rows.center(0) == 7.5
    assert rows.center(7) == 0.5
    assert rows.thickness == pytest.approx(BAR_FILL)
    assert rows.longest == pytest.approx(10.0 - 1.0 - 0.2 - 2.2)
    with pytest.raises(RenderError, match="names are too long"):
        plan_race_rows(area, 8, 5.0, 1.0, 0.2, 0.1)
    with pytest.raises(RenderError, match="12 bars do not fit"):
        plan_race_rows(area, 12, 2.0, 1.0, 0.2, 0.5)


def test_the_axis_of_a_line_race_keeps_room_above_the_lines() -> None:
    assert axis_top(100) == pytest.approx(110)
    assert axis_top(0) == pytest.approx(1.1)


def race_spec(chart: str) -> BarRaceChart | LineRaceChart:
    spec = parse_spec(f"version: 1\ncharts:\n  - {{ id: r, {chart} }}", "spec.yaml")
    race = spec.charts[0]
    assert isinstance(race, BarRaceChart | LineRaceChart)
    return race


def race_errors(chart: str) -> list[str]:
    with pytest.raises(SpecError) as caught:
        race_spec(chart)
    return [str(issue) for issue in caught.value.issues]


TWO = "{ name: A, values: [1, 2, 3] }, { name: B, values: [3, 2, null] }"


@pytest.mark.parametrize("kind", ["bar-race", "line-race"])
def test_a_race_takes_periods_and_series(kind: str) -> None:
    race = race_spec(f'type: {kind}, periods: ["2001", "2002", "2003"], series: [{TWO}]')

    assert race.duration == 15
    assert race.series[1].values == [3, 2, None]


@pytest.mark.parametrize("kind", ["bar-race", "line-race"])
def test_the_periods_and_series_of_a_race_are_checked(kind: str) -> None:
    errors = race_errors(
        f"type: {kind}, periods: [a, b, a], series: [{{ name: A, values: [1, 2] }}, "
        "{ name: A, values: [null, null, null] }], highlight: { series: C }"
    )

    assert errors == [
        'charts[0].periods[2]: "a" is already used by periods[0]; periods must be unique',
        'charts[0].series[1].name: "A" is already used by series[0]; series names must be unique',
        "charts[0].series[0].values: expected 3 values (same as periods), got 2",
        "charts[0].series[1].values: needs at least one number, not only null",
        'charts[0].highlight.series: "C" does not match any series. Series: "A"',
    ]


def test_a_bar_race_shows_three_to_twelve_bars_of_two_to_thirty_series() -> None:
    assert race_spec(f"type: bar-race, periods: [a, b, c], series: [{TWO}]").show == 8  # type: ignore[union-attr]
    [message] = race_errors(f"type: bar-race, periods: [a, b, c], series: [{TWO}], show: 13")
    assert message.startswith("charts[0].show:")
    [message] = race_errors(
        "type: bar-race, periods: [a, b], series: [{ name: A, values: [1, 2] }]"
    )
    assert message.startswith("charts[0].series:")


def test_a_line_race_takes_one_to_six_series() -> None:
    seven = ", ".join(f"{{ name: S{index}, values: [1, 2] }}" for index in range(7))

    [message] = race_errors(f"type: line-race, periods: [a, b], series: [{seven}]")

    assert message.startswith("charts[0].series:")


def test_a_race_reads_its_data_from_a_file(tmp_path: Path) -> None:
    (tmp_path / "data.csv").write_text("Year,A,B\n2001,1,3\n2002,,2\n2003,3,\n")

    spec = parse_spec(
        "version: 1\ncharts:\n  - { id: r, type: bar-race, data: data.csv }\n"
        "  - { id: l, type: line-race, data: data.csv }\n",
        "spec.yaml",
        tmp_path,
    )

    for race in spec.charts:
        assert isinstance(race, BarRaceChart | LineRaceChart)
        assert race.periods == ["2001", "2002", "2003"]
        assert [(item.name, item.values) for item in race.series] == [
            ("A", [1, None, 3]),
            ("B", [3, 2, None]),
        ]


def test_a_bar_race_gives_brand_colors_to_series_by_name() -> None:
    race = race_spec(f"type: bar-race, periods: [a, b, c], series: [{TWO}], colors: {{ A: blue }}")

    assert race.colors == {"A": "blue"}  # type: ignore[union-attr]
    assert race_errors(
        f"type: bar-race, periods: [a, b, c], series: [{TWO}], colors: {{ Z: blue }}"
    ) == ['charts[0].colors.Z: "Z" does not match any series. Series: "A", "B"']


def test_a_brand_color_must_be_in_the_theme() -> None:
    from vizreel.charts.bar_race import BarRaceChartType
    from vizreel.format.locales import EN_US
    from vizreel.render.layout import build_layout
    from vizreel.themes.loader import load_theme

    theme = load_theme("default", Path("."))
    brand = theme.model_copy(
        update={"colors": theme.colors.model_copy(update={"brand": {"blue": "#1F6FEB"}})}
    )
    race = race_spec(
        f"type: bar-race, periods: [a, b, c], series: [{TWO}], colors: {{ A: blue }}, "
        "highlight: { series: B }"
    )
    layout = build_layout(
        theme.sizes, aspect="16:9", panel=True, title_lines=0, subtitle_lines=0, source_lines=0
    )

    assert BarRaceChartType(race, brand, layout, EN_US)._bar_colors() == [
        "#1F6FEB",
        brand.colors.highlight,
    ]
    with pytest.raises(RenderError, match='the color "blue" of "A" is not a brand color'):
        BarRaceChartType(race, theme, layout, EN_US)._bar_colors()


def test_race_images_are_found_next_to_the_spec(tmp_path: Path) -> None:
    (tmp_path / "logos").mkdir()
    (tmp_path / "logos" / "a.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    chart = f"type: bar-race, periods: [a, b, c], series: [{TWO}]"

    spec = parse_spec(
        f"version: 1\ncharts:\n  - {{ id: r, {chart}, images: {{ A: logos/a.svg }} }}",
        "spec.yaml",
        tmp_path,
    )
    with pytest.raises(SpecError) as caught:
        parse_spec(
            f"version: 1\ncharts:\n  - {{ id: r, {chart}, "
            "images: { A: logos/b.svg, B: logos/a.gif, C: logos/a.svg } }",
            "spec.yaml",
            tmp_path,
        )

    race = spec.charts[0]
    assert isinstance(race, BarRaceChart)
    assert race.images == {"A": str((tmp_path / "logos" / "a.svg").resolve())}
    assert [str(issue) for issue in caught.value.issues] == [
        f"charts[0].images.A: logos/b.svg was not found in {tmp_path / 'logos'}",
        "charts[0].images.B: logos/a.gif is not a PNG, JPEG or SVG file",
        'charts[0].images.C: "C" does not match any series. Series: "A", "B"',
    ]


def test_watching_includes_the_images_of_a_spec(tmp_path: Path) -> None:
    from vizreel.spec.loader import spec_input_files

    (tmp_path / "a.png").write_bytes(b"")
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        "version: 1\ncharts:\n  - { id: r, type: bar-race, images: { A: a.png, B: gone.png } }\n"
    )

    assert spec_input_files(spec) == [tmp_path / "a.png"]


def test_race_rows_in_a_narrow_frame_put_each_name_above_its_bar() -> None:
    from vizreel.charts.bar_race import plan_race_rows_above

    area = Box(0.0, 0.0, 4.0, 8.0)
    rows = plan_race_rows_above(area, 8, 0.3, 1.0, 0.2, 0.1, image_aspect=1.0)

    assert rows.names_above
    assert rows.bar_left == 0.0
    assert rows.thickness == pytest.approx((1.0 - 0.3 - 0.1) * BAR_FILL)
    assert rows.longest == pytest.approx(4.0 - 0.2 - (rows.thickness + 0.2) - 1.0)
    # The name, the gap and the bar of the first row are centered in its slot.
    top = rows.center(0) + rows.thickness / 2 + 0.1 + 0.3
    bottom = rows.center(0) - rows.thickness / 2
    assert 8.0 - top == pytest.approx(bottom - 7.0)


def test_a_race_reaches_each_position_at_the_time_race_position_says() -> None:
    from vizreel.charts._race import race_time

    for position in (0, 1, 2.5, 3, 3.5, 3.99, 4):
        assert race_position(race_time(position, 10, 5), 10, 5) == pytest.approx(position)


def test_a_caption_shows_until_the_next_one_fading_in_and_out() -> None:
    from vizreel.charts._race import CAPTION_FADE, caption_at

    assert caption_at([1.0, 3.0], 0.5) is None
    assert caption_at([1.0, 3.0], 1.0) == (0, 0.0)
    assert caption_at([1.0, 3.0], 1.0 + CAPTION_FADE) == (0, pytest.approx(1.0))
    assert caption_at([1.0, 3.0], 2.0) == (0, 1.0)
    assert caption_at([1.0, 3.0], 3.0 - CAPTION_FADE / 2) == (0, pytest.approx(0.5))
    assert caption_at([1.0, 3.0], 10.0) == (1, 1.0)


def test_a_caption_must_stay_long_enough_to_be_read() -> None:
    from vizreel.charts._race import check_caption_times

    check_caption_times([("One two three", 0.0), ("Four", 4.0)], 1.0, 10.0, 5, 13.0)
    with pytest.raises(RenderError, match='the caption "Words enough for three seconds of'):
        check_caption_times(
            [("Words enough for three seconds of reading here", 0.0), ("Next", 1.0)],
            1.0,
            10.0,
            5,
            13.0,
        )


@pytest.mark.parametrize("kind", ["bar-race", "line-race"])
def test_captions_name_periods_in_order(kind: str) -> None:
    chart = f"type: {kind}, periods: [a, b, c], series: [{TWO}]"

    race = race_spec(
        f"{chart}, captions: [{{ period: a, text: Start }}, {{ period: c, text: End }}]"
    )
    assert [caption.period for caption in race.captions] == ["a", "c"]
    assert race_errors(
        f"{chart}, captions: [{{ period: c, text: One }}, {{ period: b, text: Two }}, "
        "{ period: z, text: Three }]"
    ) == [
        'charts[0].captions[1].period: "b" comes before the caption above it; list captions '
        "in order",
        'charts[0].captions[2].period: "z" is not one of the periods: "a", "b", "c"',
    ]
