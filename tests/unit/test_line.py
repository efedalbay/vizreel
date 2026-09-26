import pytest

from vizreel.charts.line import drawn, runs, tip

XS = [0.0, 1.0, 2.0, 3.0, 4.0]


def test_runs_break_at_null_values() -> None:
    assert runs(XS, [1, 2, None, 4, 5]) == [[(0, 1), (1, 2)], [(3, 4), (4, 5)]]


def test_runs_skip_leading_and_trailing_nulls() -> None:
    assert runs(XS, [None, 2, 3, None, None]) == [[(1, 2), (2, 3)]]


def test_runs_keep_isolated_points() -> None:
    assert runs(XS, [1, None, 3, None, 5]) == [[(0, 1)], [(2, 3)], [(4, 5)]]


def test_drawn_interpolates_where_the_pen_is() -> None:
    series = runs(XS, [0, 10, 20, 30, 40])

    assert drawn(series, 1.5) == [[(0, 0), (1, 10), (1.5, 15)]]


def test_drawn_on_a_point_does_not_duplicate_it() -> None:
    series = runs(XS, [0, 10, 20, 30, 40])

    assert drawn(series, 2.0) == [[(0, 0), (1, 10), (2, 20)]]


def test_drawn_before_the_first_point_is_empty() -> None:
    assert drawn(runs(XS, [None, None, 5, 6, 7]), 1.5) == []


def test_drawn_across_a_gap_keeps_earlier_runs_whole() -> None:
    series = runs(XS, [1, 2, None, 4, 6])

    assert drawn(series, 3.5) == [[(0, 1), (1, 2)], [(3, 4), (3.5, 5)]]


def test_drawn_inside_a_gap_stops_at_the_last_point() -> None:
    series = runs(XS, [1, 2, None, 4, 6])

    assert drawn(series, 2.5) == [[(0, 1), (1, 2)]]


def test_tip_is_the_last_drawn_point() -> None:
    series = runs(XS, [1, 2, None, 4, 6])

    assert tip(series, 0.5) == pytest.approx((0.5, 1.5))
    assert tip(series, 2.5) == (1, 2)
    assert tip(series, 4.0) == (4, 6)


def test_tip_before_the_first_point_is_none() -> None:
    assert tip(runs(XS, [None, 1, 2, 3, 4]), 0.5) is None
