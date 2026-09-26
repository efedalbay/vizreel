import pytest

from vizreel.charts.line import drawn, place_first_labels, runs, tip
from vizreel.render.layout import Box

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


BOUNDS = Box(0.0, 0.0, 10.0, 10.0)
LABEL = (1.0, 1.0)
GAP = 0.2


def test_a_lone_first_label_goes_above_its_point() -> None:
    [box] = place_first_labels([(1.0, 3.0)], [LABEL], [[(1.0, 3.0), (9.0, 4.0)]], GAP, BOUNDS)

    assert box == Box(1.0, 3.2, 2.0, 4.2)


def test_close_first_labels_go_above_and_below() -> None:
    upper = [(1.0, 5.0), (9.0, 5.5)]
    lower = [(1.0, 4.0), (9.0, 4.5)]

    high, low = place_first_labels(
        [upper[0], lower[0]], [LABEL, LABEL], [upper, lower], GAP, BOUNDS
    )

    assert high.bottom == pytest.approx(5.2)
    assert low.top == pytest.approx(3.8)


def test_a_label_goes_below_when_its_line_rises_steeply() -> None:
    steep = [(1.0, 5.0), (2.0, 9.0)]

    [box] = place_first_labels([steep[0]], [LABEL], [steep], GAP, BOUNDS)

    assert box.top == pytest.approx(4.8)


def test_labels_stack_above_the_lines_when_nothing_else_fits() -> None:
    # The lower line starts at the bottom edge, so its label cannot go below it, and the
    # upper line is too close above it.
    upper = [(1.0, 1.0), (9.0, 6.0)]
    lower = [(1.0, 0.2), (9.0, 3.0)]

    high, low = place_first_labels(
        [upper[0], lower[0]], [LABEL, LABEL], [upper, lower], GAP, BOUNDS
    )

    assert low.bottom > 1.0 + (6.0 - 1.0) / 8
    assert high.bottom >= low.top + GAP / 2 - 1e-9
