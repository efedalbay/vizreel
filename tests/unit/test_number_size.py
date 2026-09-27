import pytest

from vizreel.charts.base import SMALLEST_NUMBER_SCALE, count_samples, fitting_number_size
from vizreel.errors import RenderError
from vizreel.format.locales import LOCALES, Locale
from vizreel.format.numbers import decimals_for, format_number
from vizreel.spec.models import NumberFormat


def test_count_samples_are_the_ends_and_the_powers_of_ten_between() -> None:
    assert count_samples(0, 1846) == [0, 1, 2, 10, 20, 100, 200, 1000, 1846]


def test_count_samples_of_a_count_down() -> None:
    assert count_samples(1200, 340) == [340, 1000, 1200]


def test_count_samples_across_zero_have_both_signs() -> None:
    assert count_samples(-50, 30) == [-50, -20, -10, -2, -1, 0, 1, 2, 10, 20, 30]


def _dense(start: float, end: float) -> list[float]:
    """Many values along a count: evenly spaced, and spaced by ratio near zero."""
    low, high = sorted((start, end))
    even = [low + (high - low) * step / 4000 for step in range(4001)]
    by_ratio = [high * 0.995**step for step in range(6000) if low <= high * 0.995**step]
    return even + by_ratio


@pytest.mark.parametrize("locale", list(LOCALES.values()), ids=list(LOCALES))
@pytest.mark.parametrize(
    "fmt",
    [
        NumberFormat(),
        NumberFormat(compact=True),
        NumberFormat(compact="short"),
        NumberFormat(compact="long", suffix=" €"),
        NumberFormat(compact=True, decimals=2),
    ],
    ids=["plain", "compact", "short", "long", "decimals"],
)
@pytest.mark.parametrize(("start", "end"), [(0, 2250000000), (0, 1846.5), (0, 1500000)])
def test_no_text_of_a_count_is_longer_than_the_longest_sample(
    locale: Locale, fmt: NumberFormat, start: float, end: float
) -> None:
    fixed = fmt.model_copy(update={"decimals": decimals_for([start, end], fmt)})

    def longest(values: list[float]) -> int:
        return max(len(format_number(value, fixed, locale=locale)) for value in values)

    assert longest(_dense(start, end)) <= longest(count_samples(start, end))


def test_a_number_that_fits_keeps_its_size() -> None:
    assert fitting_number_size(180, 5.0, 6.0, "the number") == 180


def test_a_number_too_wide_shrinks_to_fit() -> None:
    size = fitting_number_size(180, 8.0, 6.0, "the number")

    assert size == pytest.approx(135, rel=1e-5)
    assert size * 8.0 / 180 <= 6.0


def test_a_number_shrinks_to_half_its_size_at_most() -> None:
    assert SMALLEST_NUMBER_SCALE == 0.5
    assert fitting_number_size(180, 12.0, 6.0, "the number") == pytest.approx(90, rel=1e-5)

    with pytest.raises(RenderError, match="the number is too wide to fit even at half"):
        fitting_number_size(180, 12.1, 6.0, "the number")
