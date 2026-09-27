import pytest

from vizreel.charts.timeline import (
    ALTERNATING_LINES,
    MAX_VERTICAL_PITCH,
    ONE_SIDE_LINES,
    inverse,
    label_widths,
    plan_labels,
    plan_vertical_events,
    side_of,
)
from vizreel.errors import RenderError
from vizreel.render.layout import LABEL_FILL


def fits_characters(line: str, width: float) -> bool:
    """A fake measure: every character is one unit wide."""
    return len(line) <= width


def test_labels_below_get_one_slot_each() -> None:
    assert label_widths(4, 40, alternate=False) == [10 * LABEL_FILL] * 4


def test_alternating_labels_get_two_slots_and_less_at_the_edges() -> None:
    assert label_widths(5, 50, alternate=True) == pytest.approx(
        [15 * LABEL_FILL, 20 * LABEL_FILL, 20 * LABEL_FILL, 20 * LABEL_FILL, 15 * LABEL_FILL]
    )


def test_two_alternating_labels_have_no_same_side_neighbor() -> None:
    assert label_widths(2, 20, alternate=True) == pytest.approx([20 * LABEL_FILL] * 2)


def test_short_labels_all_sit_below() -> None:
    plan = plan_labels(["2016", "2017"], ["Founded", "Raises money"], 40, fits_characters)

    assert plan.alternate is False
    assert plan.lines == [["Founded"], ["Raises money"]]


def test_long_labels_alternate_and_wrap() -> None:
    labels = ["Founded in a rented garage", "Raises a seed round", "Opens offices abroad"]

    plan = plan_labels(["2016", "2017", "2018"], labels, 36, fits_characters)

    assert plan.alternate is True
    assert all(len(lines) <= ALTERNATING_LINES for lines in plan.lines)
    for lines, width in zip(plan.lines, plan.widths, strict=True):
        assert all(len(line) <= width for line in lines)


def test_labels_below_use_at_most_two_lines() -> None:
    plan = plan_labels(["1", "2"], ["aa bb cc", "dd"], 20, fits_characters)

    assert plan.alternate is False
    assert all(len(lines) <= ONE_SIDE_LINES for lines in plan.lines)


def test_label_too_long_even_when_alternating() -> None:
    labels = ["Founded by two friends in a rented garage near the harbor", "b", "c"]

    with pytest.raises(RenderError, match='event label "Founded by .*" is too long for 3 events'):
        plan_labels(["1", "2", "3"], labels, 24, fits_characters)


def test_date_too_long_is_an_error() -> None:
    with pytest.raises(RenderError, match='event date "The spring of 2016" is too long'):
        plan_labels(["The spring of 2016", "2017"], ["a", "b"], 10, fits_characters)


@pytest.mark.parametrize(("index", "side"), [(0, -1), (1, 1), (2, -1), (3, 1)])
def test_alternating_sides_start_below(index: int, side: int) -> None:
    assert side_of(index, alternate=True) == side
    assert side_of(index, alternate=False) == -1


@pytest.mark.parametrize("value", [0.0, 0.1, 0.5, 0.9, 1.0])
def test_inverse_of_a_curve(value: float) -> None:
    def ease_out_cubic(t: float) -> float:
        return 1 - (1 - t) ** 3

    assert inverse(lambda t: t, value) == pytest.approx(value, abs=1e-9)
    assert ease_out_cubic(inverse(ease_out_cubic, value)) == pytest.approx(value, abs=1e-9)


def test_vertical_events_fill_the_height_evenly() -> None:
    tops = plan_vertical_events(top=4.0, bottom=-4.0, heights=[1.0, 1.0, 1.0, 1.0], gap=0.5)

    assert tops == pytest.approx([4.0, 4.0 - 7 / 3, 4.0 - 14 / 3, -3.0])


def test_few_vertical_events_stay_together_in_the_middle() -> None:
    tops = plan_vertical_events(top=6.0, bottom=-6.0, heights=[1.0, 2.0], gap=0.5)
    pitch = (2.0 + 0.5) * MAX_VERTICAL_PITCH

    assert tops[0] - tops[1] == pytest.approx(pitch)
    assert (tops[0] + tops[1] - 2.0) / 2 == pytest.approx(0.0)


def test_vertical_events_that_do_not_fit_are_an_error() -> None:
    with pytest.raises(RenderError, match="not enough room"):
        plan_vertical_events(top=1.0, bottom=-1.0, heights=[1.0, 1.0, 1.0], gap=0.2)
