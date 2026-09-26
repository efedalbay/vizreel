import pytest

from vizreel.format.numbers import (
    MINUS_SIGN,
    decimals_for,
    format_number,
    format_numbers,
    shared_decimals,
)
from vizreel.spec.models import NumberFormat

M = MINUS_SIGN
COMPACT = NumberFormat(compact=True)
DOLLARS_COMPACT = NumberFormat(prefix="$", compact=True)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0"),
        (7, "7"),
        (1200000, "1,200,000"),
        (1200000.0, "1,200,000"),
        (4.2, "4.2"),
        (0.05, "0.05"),
        (1.234, "1.23"),
        (1234567.891, "1,234,567.89"),
        (-1200, f"{M}1,200"),
        (-0.001, "0"),
        (1e20, "100,000,000,000,000,000,000"),
    ],
)
def test_plain_numbers(value: float, expected: str) -> None:
    assert format_number(value) == expected


@pytest.mark.parametrize(
    ("value", "decimals", "expected"),
    [
        (2.675, 2, "2.68"),
        (2.5, 0, "3"),
        (3.5, 0, "4"),
        (0.125, 2, "0.13"),
        (-1.005, 2, f"{M}1.01"),
        (-2.5, 0, f"{M}3"),
    ],
)
def test_rounding_is_half_away_from_zero(value: float, decimals: int, expected: str) -> None:
    assert format_number(value, NumberFormat(decimals=decimals)) == expected


@pytest.mark.parametrize(
    ("value", "decimals", "expected"),
    [
        (2.2, 2, "2.20"),
        (1234.5, 0, "1,235"),
        (7, 3, "7.000"),
        (-0.001, 2, "0.00"),
        (4.25, 1, "4.3"),
    ],
)
def test_fixed_decimals_keep_trailing_zeros(value: float, decimals: int, expected: str) -> None:
    assert format_number(value, NumberFormat(decimals=decimals)) == expected


@pytest.mark.parametrize(
    ("value", "fmt", "expected"),
    [
        (12, NumberFormat(suffix="%"), "12%"),
        (42000, NumberFormat(suffix=" users"), "42,000 users"),
        (2.25, NumberFormat(prefix="$", suffix="B", decimals=2), "$2.25B"),
        (-12.5, NumberFormat(prefix="$"), f"{M}$12.5"),
        (-3, NumberFormat(suffix="%"), f"{M}3%"),
    ],
)
def test_prefix_and_suffix(value: float, fmt: NumberFormat, expected: str) -> None:
    assert format_number(value, fmt) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (740000000, "740M"),
        (2250000000, "2.25B"),
        (1200000, "1.2M"),
        (70000000, "70M"),
        (12345678, "12.3M"),
        (1000, "1K"),
        (1500, "1.5K"),
        (865000000, "865M"),
        (1750000000, "1.75B"),
        (3.2e12, "3.2T"),
        (1.5e15, "1,500T"),
    ],
)
def test_compact_uses_three_significant_digits(value: float, expected: str) -> None:
    assert format_number(value, COMPACT) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (999, "999"),
        (999.5, "999.5"),
        (0.5, "0.5"),
        (12.345, "12.35"),
    ],
)
def test_compact_leaves_numbers_below_1000_unabbreviated(value: float, expected: str) -> None:
    assert format_number(value, COMPACT) == expected


@pytest.mark.parametrize(
    ("value", "fmt", "expected"),
    [
        (999950, COMPACT, "1M"),
        (999499, COMPACT, "999K"),
        (999500000, COMPACT, "1B"),
        (999950, NumberFormat(compact=True, decimals=1), "1.0M"),
        (-999950, COMPACT, f"{M}1M"),
    ],
)
def test_compact_moves_up_a_unit_when_rounding_reaches_1000(
    value: float, fmt: NumberFormat, expected: str
) -> None:
    assert format_number(value, fmt) == expected


@pytest.mark.parametrize(
    ("value", "decimals", "expected"),
    [
        (1234, 1, "1.2K"),
        (740000000, 1, "740.0M"),
        (2250000000, 0, "2B"),
        (1234567, 3, "1.235M"),
    ],
)
def test_compact_with_fixed_decimals(value: float, decimals: int, expected: str) -> None:
    assert format_number(value, NumberFormat(compact=True, decimals=decimals)) == expected


def test_compact_negative_number_puts_sign_before_prefix() -> None:
    assert format_number(-2500000, DOLLARS_COMPACT) == f"{M}$2.5M"


def test_spec_example_peak_valuation() -> None:
    assert format_number(740000000, DOLLARS_COMPACT) == "$740M"


def test_minus_sign_is_typographic_minus() -> None:
    assert MINUS_SIGN == "−"
    assert "-" not in format_number(-5)


def test_group_shares_the_most_precise_decimals() -> None:
    fmt = NumberFormat(prefix="$", suffix="B")

    assert format_numbers([0.05, 0.2, 2.25, 2.25], fmt) == ["$0.05B", "$0.20B", "$2.25B", "$2.25B"]


def test_group_of_whole_numbers_has_no_decimals() -> None:
    values = [740000000, 70000000, 40000000]

    assert format_numbers(values, DOLLARS_COMPACT) == ["$740M", "$70M", "$40M"]


def test_compact_group_shares_decimals_per_unit() -> None:
    values = [1250000000, 412000000, 187500000, 54300000, 7800000, 950000]

    assert format_numbers(values, DOLLARS_COMPACT) == [
        "$1.25B",
        "$412.0M",
        "$187.5M",
        "$54.3M",
        "$7.8M",
        "$950K",
    ]


def test_shared_decimals() -> None:
    assert shared_decimals([1250000000, 412000000, 7800000], COMPACT) == [2, 1, 1]
    assert shared_decimals([0.05, 2.25, 3]) == [2, 2, 2]
    assert shared_decimals([1, 2.5], NumberFormat(decimals=3)) == [3, 3]
    assert shared_decimals([]) == []


def test_group_with_fixed_decimals_ignores_precision_of_values() -> None:
    assert format_numbers([1, 2.5], NumberFormat(decimals=0)) == ["1", "3"]


def test_group_mixed_precision() -> None:
    assert format_numbers([1, 2.5]) == ["1.0", "2.5"]


def test_empty_group() -> None:
    assert format_numbers([]) == []


@pytest.mark.parametrize(
    ("values", "fmt", "expected"),
    [
        ([0, 1200000], None, 0),
        ([0, 4.25], None, 2),
        ([0, 740000000], COMPACT, 0),
        ([0, 2250000000], COMPACT, 2),
        ([0, 1200000], COMPACT, 1),
        ([0, 4.25], NumberFormat(decimals=4), 4),
        ([], None, 0),
    ],
)
def test_decimals_for(values: list[float], fmt: NumberFormat | None, expected: int) -> None:
    assert decimals_for(values, fmt) == expected


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_non_finite_values_are_rejected(value: float) -> None:
    with pytest.raises(ValueError, match="cannot format"):
        format_number(value)
