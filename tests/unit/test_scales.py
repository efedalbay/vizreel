from collections.abc import Callable

import pytest

from vizreel.render.scales import (
    MAX_TICKS,
    Axis,
    LinearScale,
    band_centers,
    clamp_center,
    point_positions,
    spread_labels,
    thin_labels,
    two_line_splits,
    value_axis,
    wrap_text,
)


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([0.05, 0.2, 2.25, 2.25], Axis(0, 2.5, (0, 0.5, 1, 1.5, 2, 2.5))),
        ([740e6, 70e6, 40e6], Axis(0, 800e6, (0, 200e6, 400e6, 600e6, 800e6))),
        ([3, 7, 9], Axis(0, 10, (0, 2, 4, 6, 8, 10))),
        ([1, 2], Axis(0, 2, (0, 0.5, 1, 1.5, 2))),
        ([0.3], Axis(0, 0.3, (0, 0.1, 0.2, 0.3))),
        ([12], Axis(0, 12.5, (0, 2.5, 5, 7.5, 10, 12.5))),
    ],
)
def test_positive_data_starts_at_zero_and_ends_on_a_tick(
    values: list[float], expected: Axis
) -> None:
    assert value_axis(values) == expected


def test_negative_data_ends_at_zero() -> None:
    assert value_axis([-3, -8]) == Axis(-8, 0, (-8, -6, -4, -2, 0))
    assert value_axis([-3, -9]) == Axis(-10, 0, (-10, -8, -6, -4, -2, 0))


def test_mixed_data_includes_both_signs() -> None:
    axis = value_axis([-4, 9])

    assert axis.low <= -4
    assert axis.high >= 9
    assert 0 in axis.ticks


def test_all_zero_data_gets_a_unit_range() -> None:
    assert value_axis([0, 0]) == Axis(0, 1, (0, 0.2, 0.4, 0.6, 0.8, 1))


def test_fixed_bounds_are_kept_exactly() -> None:
    axis = value_axis([12, 18], low=10, high=19)

    assert (axis.low, axis.high) == (10, 19)
    assert all(10 <= tick <= 19 for tick in axis.ticks)
    assert axis.ticks == (10, 12, 14, 16, 18)


def test_one_fixed_bound() -> None:
    axis = value_axis([12, 18], low=10)

    assert axis.low == 10
    assert axis.high == 18
    assert axis.ticks[-1] == 18


@pytest.mark.parametrize(
    "values", [[0.1, 0.7], [0.3, 0.9], [1e-6, 3e-6], [123456789], [0.07, 0.21, 0.33]]
)
def test_ticks_are_clean_and_limited(values: list[float]) -> None:
    axis = value_axis(values)

    assert 2 <= len(axis.ticks) <= MAX_TICKS
    for tick in axis.ticks:
        assert repr(tick) == repr(float(f"{tick:.12g}"))
    assert axis.ticks[0] == axis.low
    assert axis.ticks[-1] == axis.high


def test_linear_scale_maps_domain_to_range() -> None:
    scale = LinearScale(domain=(0, 2.5), range=(-2, 3))

    assert scale(0) == -2
    assert scale(2.5) == 3
    assert scale(1.25) == 0.5


def test_point_positions_include_both_ends() -> None:
    assert point_positions(5, -4, 4) == [-4, -2, 0, 2, 4]
    assert point_positions(1, -4, 4) == [0]


def test_band_centers_fill_the_range() -> None:
    assert band_centers(4, 0, 8) == [1, 3, 5, 7]


def test_thin_labels_keeps_all_when_they_fit() -> None:
    assert thin_labels([0, 2, 4, 6], [1, 1, 1, 1], gap=0.5) == [0, 1, 2, 3]


def test_thin_labels_keeps_every_other_label() -> None:
    centers = [float(i) for i in range(9)]

    assert thin_labels(centers, [1.2] * 9, gap=0.2) == [0, 2, 4, 6, 8]


def test_thin_labels_always_keeps_the_last_label() -> None:
    centers = [float(i) for i in range(8)]

    shown = thin_labels(centers, [1.2] * 8, gap=0.2)

    assert shown[0] == 0
    assert shown[-1] == 7
    assert all(b - a >= 2 for a, b in zip(shown, shown[1:], strict=False))


def test_spread_labels_leaves_separate_labels_alone() -> None:
    assert spread_labels([0, 2, 4], [0.5, 0.5, 0.5], gap=0.1, low=-5, high=5) == [0, 2, 4]


def test_spread_labels_centers_overlapping_labels_on_their_mean() -> None:
    centers = spread_labels([1.0, 1.1], [0.4, 0.4], gap=0.2, low=-5, high=5)

    assert centers == pytest.approx([0.75, 1.35])


def test_spread_labels_keeps_input_order() -> None:
    centers = spread_labels([1.1, 1.0], [0.4, 0.4], gap=0.2, low=-5, high=5)

    assert centers == pytest.approx([1.35, 0.75])


def test_spread_labels_stays_inside_bounds() -> None:
    centers = spread_labels([4.9, 4.95, 5.0], [0.4, 0.4, 0.4], gap=0.1, low=0, high=5)

    assert centers[2] + 0.2 <= 5 + 1e-9
    assert all(b - a >= 0.5 - 1e-9 for a, b in zip(centers, centers[1:], strict=False))


def test_spread_labels_merges_groups_that_touch_after_moving() -> None:
    centers = spread_labels([0, 0.1, 0.9], [0.4, 0.4, 0.4], gap=0.1, low=-5, high=5)

    ordered = sorted(centers)
    assert all(b - a >= 0.5 - 1e-9 for a, b in zip(ordered, ordered[1:], strict=False))


def test_spread_labels_that_cannot_fit() -> None:
    with pytest.raises(ValueError, match="labels do not fit"):
        spread_labels([0, 0, 0], [1, 1, 1], gap=0.5, low=0, high=2)


def at_most(characters: int) -> Callable[[str], bool]:
    return lambda line: len(line) <= characters


def test_wrap_text_fills_each_line() -> None:
    assert wrap_text("Files for bankruptcy in June", at_most(12), 3) == [
        "Files for",
        "bankruptcy",
        "in June",
    ]


def test_wrap_text_keeps_short_text_on_one_line() -> None:
    assert wrap_text("Raises $865M", at_most(20), 2) == ["Raises $865M"]


def test_wrap_text_collapses_repeated_spaces() -> None:
    assert wrap_text("  Raises   $865M ", at_most(20), 1) == ["Raises $865M"]


def test_wrap_text_fails_when_a_word_is_too_long() -> None:
    assert wrap_text("Northwind incorporated", at_most(8), 3) is None


def test_wrap_text_fails_when_too_many_lines_are_needed() -> None:
    assert wrap_text("one two three four", at_most(5), 3) is None
    assert wrap_text("one two three four", at_most(5), 4) == ["one", "two", "three", "four"]


def test_wrap_text_of_empty_text() -> None:
    assert wrap_text("", at_most(5), 1) == []


@pytest.mark.parametrize(
    ("center", "expected"),
    [(5, 5), (0.5, 1.5), (9.8, 8.5), (-3, 1.5)],
)
def test_clamp_center_keeps_the_span_inside(center: float, expected: float) -> None:
    assert clamp_center(center, width=3, low=0, high=10) == expected


def test_two_line_splits_most_balanced_first() -> None:
    assert two_line_splits("Buyer A (2015)") == [("Buyer A", "(2015)"), ("Buyer", "A (2015)")]
    assert two_line_splits("North") == []
