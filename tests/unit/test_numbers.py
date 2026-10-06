import pytest

from vizreel.format.locales import EN_US as EN
from vizreel.format.numbers import (
    MINUS_SIGN,
    change_amount,
    change_decimals,
    decimals_for,
    format_change,
    format_number,
    format_numbers,
    format_percent,
    shared_decimals,
    split_number_text,
    whole_percents,
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
    assert format_number(value, locale=EN) == expected


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
    assert format_number(value, NumberFormat(decimals=decimals), locale=EN) == expected


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
    assert format_number(value, NumberFormat(decimals=decimals), locale=EN) == expected


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
    assert format_number(value, fmt, locale=EN) == expected


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
    assert format_number(value, COMPACT, locale=EN) == expected


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
    assert format_number(value, COMPACT, locale=EN) == expected


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
    assert format_number(value, fmt, locale=EN) == expected


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
    assert (
        format_number(value, NumberFormat(compact=True, decimals=decimals), locale=EN) == expected
    )


def test_compact_negative_number_puts_sign_before_prefix() -> None:
    assert format_number(-2500000, DOLLARS_COMPACT, locale=EN) == f"{M}$2.5M"


def test_spec_example_peak_valuation() -> None:
    assert format_number(740000000, DOLLARS_COMPACT, locale=EN) == "$740M"


def test_minus_sign_is_typographic_minus() -> None:
    assert MINUS_SIGN == "−"
    assert "-" not in format_number(-5, locale=EN)


def test_group_shares_the_most_precise_decimals() -> None:
    fmt = NumberFormat(prefix="$", suffix="B")

    assert format_numbers([0.05, 0.2, 2.25, 2.25], fmt, locale=EN) == [
        "$0.05B",
        "$0.20B",
        "$2.25B",
        "$2.25B",
    ]


def test_group_of_whole_numbers_has_no_decimals() -> None:
    values = [740000000, 70000000, 40000000]

    assert format_numbers(values, DOLLARS_COMPACT, locale=EN) == ["$740M", "$70M", "$40M"]


def test_compact_group_shares_decimals_per_unit() -> None:
    values = [1250000000, 412000000, 187500000, 54300000, 7800000, 950000]

    assert format_numbers(values, DOLLARS_COMPACT, locale=EN) == [
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
    assert format_numbers([1, 2.5], NumberFormat(decimals=0), locale=EN) == ["1", "3"]


def test_group_mixed_precision() -> None:
    assert format_numbers([1, 2.5], locale=EN) == ["1.0", "2.5"]


def test_empty_group() -> None:
    assert format_numbers([], locale=EN) == []


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
        format_number(value, locale=EN)


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        (1200, 340, f"{M}72%"),
        (100, 104.5, "+4.5%"),
        (100, 95.5, f"{M}4.5%"),
        (100, 109.96, "+10%"),
        (100, 350, "+250%"),
        (10, 1500, "+14,900%"),
        (100, 100, "0%"),
        (100, 100.01, "0.0%"),
    ],
)
def test_percent_changes(before: float, after: float, expected: str) -> None:
    assert format_change(change_amount(before, after, "percent"), "percent", locale=EN) == expected


@pytest.mark.parametrize(
    ("before", "after", "fmt", "expected"),
    [
        (1200, 340, NumberFormat(), f"{M}860"),
        (1_250_000_000, 1_400_000_000, NumberFormat(prefix="$", compact=True), "+$150M"),
        (2.5, 1.25, NumberFormat(suffix=" kg"), f"{M}1.25 kg"),
        (7, 7, NumberFormat(prefix="$"), "$0"),
    ],
)
def test_absolute_changes(before: float, after: float, fmt: NumberFormat, expected: str) -> None:
    assert (
        format_change(change_amount(before, after, "absolute"), "absolute", fmt, locale=EN)
        == expected
    )


def test_a_counting_change_keeps_the_decimals_of_its_final_value() -> None:
    final = change_amount(100, 104.5, "percent")
    places = change_decimals(final, "percent")

    assert format_change(final * 0.1, "percent", decimals=places, locale=EN) == "+0.5%"
    assert format_change(0.0, "percent", decimals=places, locale=EN) == "0.0%"


@pytest.mark.parametrize("before", [0, -5])
def test_percent_change_from_a_value_that_is_not_positive_is_an_error(before: float) -> None:
    with pytest.raises(ValueError, match="in percent"):
        change_amount(before, 10, "percent")


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([47, 28, 25], [47, 28, 25]),
        ([1, 1, 1], [34, 33, 33]),
        ([2, 1], [67, 33]),
        ([0.1, 99.9], [0, 100]),
        ([5, 5, 5, 5, 5, 5], [17, 17, 17, 17, 16, 16]),
    ],
)
def test_whole_percents_add_up_to_100(values: list[float], expected: list[int]) -> None:
    percents = whole_percents(values)

    assert percents == expected
    assert sum(percents) == 100


def test_whole_percents_need_a_positive_total() -> None:
    with pytest.raises(ValueError, match="above zero"):
        whole_percents([0, 0])


@pytest.mark.parametrize(("percent", "expected"), [(47, "47%"), (0, "0%"), (46.6, "47%")])
def test_format_percent(percent: float, expected: str) -> None:
    assert format_percent(percent, locale=EN) == expected


@pytest.mark.parametrize(
    ("value", "final", "fmt", "expected"),
    [
        (370_000_000, 1_850_000_000, NumberFormat(compact=True, decimals=2), "0.37B"),
        (0, 1_850_000_000, NumberFormat(compact=True, decimals=2), "0.00B"),
        (370_000_000, 1_850_000_000, COMPACT, "0.37B"),
        (1_850_000_000, 740_000_000, COMPACT, "1,850M"),
        (-12_000, 740_000, DOLLARS_COMPACT, f"{M}$12K"),
        (500_000, 2_000_000_000, COMPACT, "500K"),
        (5, 1000, NumberFormat(), "5"),
        (740, 740, COMPACT, "740"),
    ],
    ids=[
        "billions",
        "zero",
        "auto-decimals",
        "count-down",
        "negative",
        "too-few-steps",
        "not-compact",
        "below-a-thousand",
    ],
)
def test_a_count_is_shown_in_the_unit_of_its_final_value(
    value: float, final: float, fmt: NumberFormat, expected: str
) -> None:
    assert format_number(value, fmt, locale=EN, unit_of=final) == expected


@pytest.mark.parametrize("final", [1_850_000_000, 740_000_000, 12_345, 2_000_000_000, 999_950])
def test_the_last_frame_of_a_count_reads_as_the_value_alone(final: float) -> None:
    assert format_number(final, COMPACT, locale=EN, unit_of=final) == format_number(
        final, COMPACT, locale=EN
    )


def test_an_absolute_change_counts_in_the_unit_of_its_final_value() -> None:
    fmt = NumberFormat(prefix="$", compact=True)

    assert format_change(37_000_000, "absolute", fmt, 0, locale=EN, unit_of=150_000_000) == "+$37M"
    assert (
        format_change(-370_000_000, "absolute", fmt, 2, locale=EN, unit_of=-1_850_000_000)
        == f"{M}$0.37B"
    )


@pytest.mark.parametrize(
    ("text", "parts"),
    [
        (f"{M}$1.85B", (M, "$", "1.85", "B", "")),
        ("1,85 milyar TL", ("", "", "1,85", " milyar TL", "")),
        ("%47", ("", "%", "47", "", "")),
        (f"{M}%3", (M, "%", "3", "", "")),
        ("+14,900%", ("", "+", "14,900", "%", "")),
        ("1 846,5", ("", "", "1 846,5", "", "")),
        ("7", ("", "", "7", "", "")),
        ("n/a", ("", "n/a", "", "", "")),
        ("($1.85B)", ("(", "$", "1.85", "B", ")")),
        ("(%12)", ("(", "%", "12", "", ")")),
    ],
)
def test_split_number_text(text: str, parts: tuple[str, str, str, str, str]) -> None:
    assert split_number_text(text) == parts
    assert "".join(parts) == text


PARENS = NumberFormat(negative="parentheses")


@pytest.mark.parametrize(
    ("value", "fmt", "locale", "text"),
    [
        (-360, PARENS, "en-US", "(360)"),
        (360, PARENS, "en-US", "360"),
        (-0.004, PARENS, "en-US", "0"),
        (
            -1_200_000,
            NumberFormat(prefix="$", compact=True, negative="parentheses"),
            "en-US",
            "($1.2M)",
        ),
        (-375_000_000, NumberFormat(prefix="$", negative="parentheses"), "en-US", "($375,000,000)"),
        (-12.5, NumberFormat(suffix="%", negative="parentheses"), "en-US", "(12.5%)"),
        (-12.5, NumberFormat(prefix="%", negative="parentheses"), "tr-TR", "(%12,5)"),
        (
            -1_850_000_000,
            NumberFormat(suffix=" TL", compact=True, negative="parentheses"),
            "tr-TR",
            "(1,85 milyar TL)",
        ),
        (-1846.5, PARENS, "es-ES", "(1846,5)"),
        (-18460, PARENS, "es-ES", "(18.460)"),
        (
            -740_000_000,
            NumberFormat(compact=True, negative="parentheses"),
            "pt-BR",
            "(740 milhões)",
        ),
        (-1846.5, NumberFormat(suffix=" €", negative="parentheses"), "fr-FR", "(1 846,5 €)"),
        (-1_200_000, NumberFormat(prefix="$", compact=True), "en-US", f"{M}$1.2M"),
    ],
)
def test_a_negative_number_can_be_written_in_parentheses(
    value: float, fmt: NumberFormat, locale: str, text: str
) -> None:
    from vizreel.format.locales import LOCALES

    assert format_number(value, fmt, locale=LOCALES[locale]) == text


def test_values_shown_together_put_only_the_negative_ones_in_parentheses() -> None:
    fmt = NumberFormat(prefix="$", compact=True, negative="parentheses")

    assert format_numbers([1_250_000, -360_000, 0], fmt, locale=EN) == ["$1.25M", "($360K)", "$0"]


def test_a_fall_is_in_parentheses_and_a_rise_keeps_its_plus_sign() -> None:
    fmt = NumberFormat(prefix="$", compact=True, negative="parentheses")

    assert format_change(-72, "percent", fmt, locale=EN) == "(72%)"
    assert format_change(4.5, "percent", fmt, locale=EN) == "+4.5%"
    assert format_change(0, "percent", fmt, locale=EN) == "0%"
    assert format_change(-5_000_000, "absolute", fmt, locale=EN) == "($5M)"
    assert format_change(500_000, "absolute", fmt, locale=EN) == "+$500K"
    assert (
        format_change(-370_000_000, "absolute", fmt, 2, locale=EN, unit_of=-1_850_000_000)
        == "($0.37B)"
    )


def test_a_count_toward_a_negative_value_keeps_its_unit_in_parentheses() -> None:
    fmt = NumberFormat(prefix="$", compact=True, negative="parentheses")

    assert format_number(-370_000_000, fmt, locale=EN, unit_of=-1_850_000_000) == "($0.37B)"
