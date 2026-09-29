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
