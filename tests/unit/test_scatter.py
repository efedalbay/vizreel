import random
from pathlib import Path

import pytest

from vizreel.charts.scatter_race import (
    Point,
    place_labels,
    point_radius,
    running_extents,
    visible_span,
)
from vizreel.errors import SpecError
from vizreel.render.layout import Box
from vizreel.spec.loader import parse_spec
from vizreel.spec.models import ScatterRaceChart

TWO = "{ name: A, x: [1, 2, 3], y: [3, 2, 1] }, { name: B, x: [2, 2, null], y: [1, 1, 1] }"
BASE = "type: scatter-race, periods: [a, b, c], x_title: Revenue, y_title: Staff"


def scatter(extra: str = "", series: str = TWO) -> ScatterRaceChart:
    spec = parse_spec(
        f"version: 1\ncharts:\n  - {{ id: s, {BASE}, series: [{series}]{extra} }}", "s.yaml"
    )
    chart = spec.charts[0]
    assert isinstance(chart, ScatterRaceChart)
    return chart


def scatter_errors(extra: str = "", series: str = TWO) -> list[str]:
    with pytest.raises(SpecError) as caught:
        scatter(extra, series)
    return [str(issue) for issue in caught.value.issues]


def test_a_scatter_race_takes_periods_series_and_axis_titles() -> None:
    chart = scatter(", highlight: { series: A }, trail: true")

    assert chart.duration == 15
    assert (chart.x_title, chart.y_title) == ("Revenue", "Staff")
    assert chart.series[1].x == [2, 2, None]
    assert chart.series[0].size is None
    assert chart.trail


def test_every_list_has_one_value_per_period_and_a_series_needs_a_point() -> None:
    errors = scatter_errors(
        series="{ name: A, x: [1, 2], y: [3, 2, 1], size: [1, 2, 3, 4] }, "
        "{ name: B, x: [1, null, null], y: [null, 1, null] }"
    )

    assert errors == [
        "charts[0].series[0].x: expected 3 values (same as periods), got 2",
        "charts[0].series[0].size: expected 3 values (same as periods), got 4",
        "charts[0].series[1]: needs a period with both an x and a y value",
    ]


def test_names_given_to_series_must_match_one() -> None:
    errors = scatter_errors(", highlight: { series: Z }, labels: [A, Y], colors: { X: blue }")

    assert [error.split(":")[0] for error in errors] == [
        "charts[0].highlight.series",
        "charts[0].colors.X",
        "charts[0].labels[1]",
    ]


def test_up_to_eight_series_are_all_named_and_beyond_only_those_chosen() -> None:
    few = scatter()
    many_series = ", ".join(
        f"{{ name: S{index}, x: [1, 2, 3], y: [1, 2, 3] }}" for index in range(9)
    )
    many = scatter(", highlight: { series: S0 }, labels: [S4]", many_series)

    assert few.labeled() == ["A", "B"]
    assert many.labeled() == ["S0", "S4"]


def test_a_scatter_race_reads_a_row_per_period_and_series(tmp_path: Path) -> None:
    (tmp_path / "data.csv").write_text(
        "Year,Company,Revenue,Staff,Customers\n"
        "2001,A,1,10,100\n2001,B,2,20,200\n2002,A,3,30,300\n2003,B,4,40,\n2003,A,5,50,500\n"
    )

    spec = parse_spec(
        "version: 1\ncharts:\n  - { id: s, type: scatter-race, data: data.csv, "
        "x_title: Revenue, y_title: Staff }\n",
        "s.yaml",
        tmp_path,
    )

    chart = spec.charts[0]
    assert isinstance(chart, ScatterRaceChart)
    assert chart.periods == ["2001", "2002", "2003"]
    assert [(item.name, item.x, item.y, item.size) for item in chart.series] == [
        ("A", [1, 3, 5], [10, 30, 50], [100, 300, 500]),
        ("B", [2, None, 4], [20, None, 40], [200, None, None]),
    ]


def test_a_series_twice_in_a_period_is_an_error_naming_both_rows(tmp_path: Path) -> None:
    (tmp_path / "data.csv").write_text("Year,Company,X,Y\n2001,A,1,2\n2001,A,3,4\n")

    with pytest.raises(SpecError) as caught:
        parse_spec(
            "version: 1\ncharts:\n  - { id: s, type: scatter-race, data: data.csv, "
            "x_title: X, y_title: Y }\n",
            "s.yaml",
            tmp_path,
        )

    assert [str(issue) for issue in caught.value.issues] == [
        'charts[0].data: data.csv, row 3 has "A" in "2001" again; it is already on row 2'
    ]


def test_the_area_of_a_point_grows_with_its_size() -> None:
    assert point_radius(100, 100, 0.1, 2.0) == pytest.approx(2.0)
    assert point_radius(25, 100, 0.1, 2.0) == pytest.approx(1.0)
    assert point_radius(0, 100, 0.1, 2.0) == pytest.approx(0.1)
    assert point_radius(None, 100, 0.1, 2.0) == pytest.approx(0.1)


def test_the_axes_hold_every_value_seen_so_far_and_zero() -> None:
    extents = running_extents([[5, None, 2], [3, 9, None], [None, None, -1]])

    assert extents == [(0, 5), (0, 9), (-1, 9)]


def test_a_series_shows_from_its_first_value_to_its_last() -> None:
    assert visible_span([None, 1, None, 3, None]) == (1, 3)
    assert visible_span([None, None]) is None


def test_names_never_overlap_each_other_or_a_point() -> None:
    random.seed(4)
    bounds = Box(0.0, 0.0, 10.0, 6.0)
    for _ in range(200):
        count = random.randint(2, 30)
        points = [
            Point(random.uniform(0, 10), random.uniform(0, 6), random.uniform(0.05, 0.4))
            for _ in range(count)
        ]
        sizes = [(random.uniform(0.5, 1.5), 0.3) for _ in range(count)]
        boxes = place_labels(points, sizes, list(range(count)), bounds, 0.05)  # type: ignore[arg-type]

        placed = [box for box in boxes if box is not None]
        for box in placed:
            assert bounds.left <= box.left and box.right <= bounds.right
            assert bounds.bottom <= box.bottom and box.top <= bounds.top
            for point in points:
                circle = point.box()
                assert not (
                    box.left < circle.right
                    and circle.left < box.right
                    and box.bottom < circle.top
                    and circle.bottom < box.top
                )
        for index, first in enumerate(placed):
            for second in placed[index + 1 :]:
                assert not (
                    first.left < second.right
                    and second.left < first.right
                    and first.bottom < second.top
                    and second.bottom < first.top
                )


def test_a_name_goes_right_of_its_point_when_it_can() -> None:
    [box] = place_labels([Point(1.0, 1.0, 0.2)], [(1.0, 0.3)], [0], Box(0, 0, 5, 5), 0.1)

    assert box is not None
    assert box.left == pytest.approx(1.3)
    assert box.center[1] == pytest.approx(1.0)
