from typing import get_args

import pytest

from vizreel.errors import SpecError
from vizreel.format.locales import (
    EN_US,
    ES_ES,
    FR_FR,
    LOCALES,
    PT_BR,
    TR_TR,
    Locale,
    locale_for,
)
from vizreel.format.numbers import (
    MINUS_SIGN,
    change_amount,
    format_change,
    format_number,
    format_numbers,
    format_percent,
)
from vizreel.spec.loader import parse_spec
from vizreel.spec.models import Meta, NumberFormat

M = MINUS_SIGN
NB = " "
NN = " "
PLAIN = NumberFormat()
COMPACT = NumberFormat(compact=True)


def test_every_locale_the_spec_accepts_is_defined() -> None:
    assert set(get_args(Meta.model_fields["locale"].annotation)) == set(LOCALES)
    assert all(locale_for(name).name == name for name in LOCALES)


def test_an_unknown_locale_is_a_spec_error() -> None:
    with pytest.raises(SpecError) as caught:
        parse_spec(
            "version: 1\nmeta: { locale: de-DE }\n"
            "charts:\n  - { id: users, type: stat, value: 1846, label: Users }\n",
            "spec.yaml",
        )

    [issue] = [str(issue) for issue in caught.value.issues]
    assert "meta.locale" in issue
    assert "tr-TR" in issue


def test_tr_tr_is_accepted_by_the_spec() -> None:
    spec = parse_spec(
        "version: 1\nmeta: { locale: tr-TR }\n"
        "charts:\n  - { id: users, type: stat, value: 1846, label: Users }\n",
        "spec.yaml",
    )

    assert spec.meta.locale == "tr-TR"


@pytest.mark.parametrize(
    ("locale", "value", "fmt", "expected"),
    [
        # Separators and automatic decimals.
        (EN_US, 1846.5, PLAIN, "1,846.5"),
        (TR_TR, 1846.5, PLAIN, "1.846,5"),
        (ES_ES, 1846.5, PLAIN, "1846,5"),
        (PT_BR, 1846.5, PLAIN, "1.846,5"),
        (FR_FR, 1846.5, PLAIN, f"1{NN}846,5"),
        (TR_TR, 1234567.891, PLAIN, "1.234.567,89"),
        (ES_ES, 1234567.891, PLAIN, "1.234.567,89"),
        (FR_FR, 1234567.891, PLAIN, f"1{NN}234{NN}567,89"),
        (TR_TR, 0.05, PLAIN, "0,05"),
        # Spanish groups only numbers of five digits or more.
        (ES_ES, 1846, PLAIN, "1846"),
        (ES_ES, 18460, PLAIN, "18.460"),
        (ES_ES, -1846, PLAIN, f"{M}1846"),
        # Fixed decimals.
        (TR_TR, 2.2, NumberFormat(decimals=2), "2,20"),
        (PT_BR, 1234.5, NumberFormat(decimals=0), "1.235"),
        (FR_FR, 7, NumberFormat(decimals=3), "7,000"),
        # Prefix, suffix and the minus sign, which stays in front.
        (TR_TR, 42000, NumberFormat(suffix=" TL"), "42.000 TL"),
        (TR_TR, 12.5, NumberFormat(prefix="%"), "%12,5"),
        (TR_TR, -3, NumberFormat(prefix="%"), f"{M}%3"),
        (ES_ES, -12.5, NumberFormat(suffix=" €"), f"{M}12,5 €"),
        (PT_BR, 1846, NumberFormat(prefix="R$ "), "R$ 1.846"),
        (FR_FR, -1846, NumberFormat(suffix=" €"), f"{M}1{NN}846 €"),
    ],
)
def test_plain_numbers_in_each_locale(
    locale: Locale, value: float, fmt: NumberFormat, expected: str
) -> None:
    assert format_number(value, fmt, locale=locale) == expected


@pytest.mark.parametrize(
    ("locale", "value", "expected"),
    [
        (EN_US, 740000000, "740M"),
        (TR_TR, 12300, f"12,3{NB}bin"),
        (TR_TR, 740000000, f"740{NB}milyon"),
        (TR_TR, 2250000000, f"2,25{NB}milyar"),
        (TR_TR, 3.2e12, f"3,2{NB}trilyon"),
        (TR_TR, 1.5e15, f"1.500{NB}trilyon"),
        (TR_TR, 999950, f"1{NB}milyon"),
        (ES_ES, 12300, f"12,3{NB}mil"),
        (ES_ES, 1000000, f"1{NB}millón"),
        (ES_ES, 1200000, f"1,2{NB}millones"),
        (ES_ES, 2250000000, f"2,25{NB}mil millones"),
        (ES_ES, 1e12, f"1{NB}billón"),
        (ES_ES, 3.2e12, f"3,2{NB}billones"),
        (PT_BR, 12300, f"12,3{NB}mil"),
        (PT_BR, 1000000, f"1{NB}milhão"),
        (PT_BR, 1500000, f"1,5{NB}milhão"),
        (PT_BR, 2000000, f"2{NB}milhões"),
        (PT_BR, 1200000000, f"1,2{NB}bilhão"),
        (PT_BR, 2250000000, f"2,25{NB}bilhões"),
        (PT_BR, 3.2e12, f"3,2{NB}trilhões"),
        (FR_FR, 12300, f"12,3{NB}mille"),
        (FR_FR, 1000000, f"1{NB}million"),
        (FR_FR, 1500000, f"1,5{NB}million"),
        (FR_FR, 740000000, f"740{NB}millions"),
        (FR_FR, 2250000000, f"2,25{NB}milliards"),
        (FR_FR, 1e12, f"1{NB}billion"),
        (FR_FR, 3.2e12, f"3,2{NB}billions"),
    ],
)
def test_compact_numbers_use_the_locale_unit_names(
    locale: Locale, value: float, expected: str
) -> None:
    assert format_number(value, COMPACT, locale=locale) == expected


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        (TR_TR, f"1,0{NB}milyon"),
        (ES_ES, f"1,0{NB}millón"),
        (PT_BR, f"1,0{NB}milhão"),
        (FR_FR, f"1,0{NB}million"),
    ],
)
def test_the_unit_follows_the_number_shown(locale: Locale, expected: str) -> None:
    assert format_number(1000000, NumberFormat(compact=True, decimals=1), locale=locale) == expected


@pytest.mark.parametrize(
    ("locale", "fmt", "expected"),
    [
        (TR_TR, NumberFormat(suffix=" TL", compact=True), f"740{NB}milyon TL"),
        (TR_TR, NumberFormat(prefix="$", compact=True), f"$740{NB}milyon"),
        (ES_ES, NumberFormat(suffix=" €", compact=True), f"740{NB}millones €"),
        (PT_BR, NumberFormat(prefix="R$ ", compact=True), f"R$ 740{NB}milhões"),
        (FR_FR, NumberFormat(suffix=" €", compact=True), f"740{NB}millions €"),
    ],
)
def test_compact_numbers_with_prefix_and_suffix(
    locale: Locale, fmt: NumberFormat, expected: str
) -> None:
    assert format_number(740000000, fmt, locale=locale) == expected


def test_negative_compact_number_puts_sign_before_prefix() -> None:
    fmt = NumberFormat(prefix="$", compact=True)

    assert format_number(-2500000, fmt, locale=TR_TR) == f"{M}$2,5{NB}milyon"


def test_group_shares_decimals_in_every_locale() -> None:
    values = [1250000000, 412000000, 54300000, 950000]

    assert format_numbers(values, COMPACT, locale=TR_TR) == [
        f"1,25{NB}milyar",
        f"412,0{NB}milyon",
        f"54,3{NB}milyon",
        f"950{NB}bin",
    ]


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        (EN_US, "47%"),
        (TR_TR, "%47"),
        (ES_ES, f"47{NB}%"),
        (PT_BR, "47%"),
        (FR_FR, f"47{NN}%"),
    ],
)
def test_percents(locale: Locale, expected: str) -> None:
    assert format_percent(47, locale=locale) == expected


@pytest.mark.parametrize(
    ("locale", "before", "after", "expected"),
    [
        (TR_TR, 1200, 340, f"{M}%72"),
        (TR_TR, 100, 104.5, "+%4,5"),
        (TR_TR, 10, 1500, "+%14.900"),
        (ES_ES, 1200, 340, f"{M}72{NB}%"),
        (ES_ES, 10, 200, f"+1900{NB}%"),
        (ES_ES, 10, 1500, f"+14.900{NB}%"),
        (PT_BR, 100, 104.5, "+4,5%"),
        (FR_FR, 100, 95.5, f"{M}4,5{NN}%"),
        (FR_FR, 100, 100, f"0{NN}%"),
    ],
)
def test_percent_changes(locale: Locale, before: float, after: float, expected: str) -> None:
    amount = change_amount(before, after, "percent")

    assert format_change(amount, "percent", locale=locale) == expected


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        (TR_TR, f"+$150{NB}milyon"),
        (ES_ES, f"+$150{NB}millones"),
        (PT_BR, f"+$150{NB}milhões"),
        (FR_FR, f"+$150{NB}millions"),
    ],
)
def test_absolute_changes(locale: Locale, expected: str) -> None:
    amount = change_amount(1_250_000_000, 1_400_000_000, "absolute")
    fmt = NumberFormat(prefix="$", compact=True)

    assert format_change(amount, "absolute", fmt, locale=locale) == expected
