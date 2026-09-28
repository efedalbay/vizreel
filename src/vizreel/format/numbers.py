"""Formatting of every number a chart displays, in the spec's locale. Pure functions."""

import math
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from vizreel.format.locales import Locale, UnitStyle
from vizreel.spec.models import NumberFormat

ChangeKind = Literal["percent", "absolute"]
"""How a change between two values is expressed."""

MINUS_SIGN = "−"
"""Typographic minus. Same width as the digits, unlike the hyphen."""

PERCENT_WHOLE_FROM = 10
"""Percent changes at least this large are whole numbers (−72%); smaller ones keep one
decimal (+4.5%), where the decimal still matters."""

AUTO_MAX_DECIMALS = 2
"""Most decimals shown when `decimals` is not set and the number is not abbreviated."""

COMPACT_SIGNIFICANT_DIGITS = 3
"""Significant digits of an abbreviated number when `decimals` is not set: 740M, 2.25B, 12.3K."""

MIN_UNIT_COUNT_STEPS = 10
"""A count keeps the unit of its final value only if it then shows at least this many values.
A count to 2B would show only 0B, 1B and 2B, so it goes through thousands and millions."""

COMPACT_POWERS: tuple[int, ...] = (1, 10**3, 10**6, 10**9, 10**12)
"""Size of each compact unit: none, thousand, million, billion, trillion."""

_DEFAULT_FORMAT = NumberFormat()


def format_number(
    value: float,
    fmt: NumberFormat | None = None,
    *,
    locale: Locale,
    unit_of: float | None = None,
) -> str:
    """Format one value for display, e.g. 740000000 → "$740M", or "740 milyon" in tr-TR.

    Args:
        value: The number to format.
        fmt: Prefix, suffix, decimals and compact notation. Defaults to plain formatting.
        locale: Separators and compact unit names.
        unit_of: For a number counting toward this value: show it in this value's compact
            unit and decimals, so a count to 1.85B reads 0.37B, not 370M, and keeps its unit
            and width. The count's last frame reads exactly as the value on its own. A value
            too small in its unit to count smoothly (see `MIN_UNIT_COUNT_STEPS`) is counted in
            the natural units.
    """
    if unit_of is None:
        return format_numbers([value], fmt, locale=locale)[0]
    fmt = fmt or _DEFAULT_FORMAT
    places = fmt.decimals if fmt.decimals is not None else shared_decimals([unit_of], fmt)[0]
    return _format(value, fmt, places, locale, unit_of)


def format_numbers(
    values: Sequence[float], fmt: NumberFormat | None = None, *, locale: Locale
) -> list[str]:
    """Format values that appear together in one chart with consistent decimals.

    See `shared_decimals`: a chart shows 0.05, 0.20 and 2.25 rather than 0.05, 0.2 and 2.25.

    Args:
        values: The numbers to format.
        fmt: Prefix, suffix, decimals and compact notation. Defaults to plain formatting.
        locale: Separators and compact unit names.
    """
    fmt = fmt or _DEFAULT_FORMAT
    decimals = shared_decimals(values, fmt)
    return [
        _format(value, fmt, places, locale) for value, places in zip(values, decimals, strict=True)
    ]


def shared_decimals(values: Sequence[float], fmt: NumberFormat | None = None) -> list[int]:
    """Return the decimals of each value when the values are shown together.

    With `fmt.decimals` set, every value uses it. Otherwise values share the decimals of the
    most precise one; with compact notation, only values with the same unit share them, so
    $1.25B stands next to $412.0M rather than $412.00M.
    """
    fmt = fmt or _DEFAULT_FORMAT
    if fmt.decimals is not None:
        return [fmt.decimals] * len(values)
    auto = [_auto_decimals(value, _is_compact(fmt)) for value in values]
    most_by_unit: dict[int, int] = {}
    for unit_index, places in auto:
        most_by_unit[unit_index] = max(most_by_unit.get(unit_index, 0), places)
    return [most_by_unit[unit_index] for unit_index, _ in auto]


def decimals_for(values: Sequence[float], fmt: NumberFormat | None = None) -> int:
    """Return one number of decimals for all these values, whatever their units.

    A counting animation formats every frame with the decimals of its start and end
    values, so the text does not change length while it counts.
    """
    fmt = fmt or _DEFAULT_FORMAT
    if fmt.decimals is not None:
        return fmt.decimals
    return max((_auto_decimals(value, _is_compact(fmt))[1] for value in values), default=0)


def change_amount(before: float, after: float, kind: ChangeKind) -> float:
    """Return the change from `before` to `after`: in percent of `before`, or the difference.

    Raises:
        ValueError: A percent change from a value that is not positive. Spec validation
            rejects these.
    """
    if kind == "absolute":
        return after - before
    if before <= 0:
        raise ValueError(f"cannot express a change from {before} in percent")
    return (after - before) / before * 100


def change_decimals(amount: float, kind: ChangeKind, fmt: NumberFormat | None = None) -> int:
    """Return the decimals a change is shown with.

    A percent change has none from `PERCENT_WHOLE_FROM` percent up, and none when there is no
    change at all; otherwise one. An absolute change follows the number format, like any
    other value.
    """
    if kind == "absolute":
        return decimals_for([amount], fmt)
    size = abs(_round(_to_decimal(amount), 1))
    return 0 if size >= PERCENT_WHOLE_FROM or amount == 0 else 1


def format_change(
    amount: float,
    kind: ChangeKind,
    fmt: NumberFormat | None = None,
    decimals: int | None = None,
    *,
    locale: Locale,
    unit_of: float | None = None,
) -> str:
    """Format a change with its sign, e.g. "−72%", "+4.5%" or "+$1.2M". No change has no sign.

    Args:
        amount: The change, from `change_amount`.
        kind: Percent or absolute.
        fmt: The chart's number format, for absolute changes. Percent changes ignore it.
        decimals: Decimals to show; by default those of `change_decimals`. A change that counts
            up keeps the decimals of its final value in every frame.
        locale: Separators, the percent sign's place and compact unit names.
        unit_of: For an absolute change counting toward this one: show it in this change's
            compact unit, as `format_number` does.
    """
    fmt = fmt or _DEFAULT_FORMAT
    places = change_decimals(amount, kind, fmt) if decimals is None else decimals
    if kind == "percent":
        rounded = _round(_to_decimal(amount), places)
        text = locale.percent.format(_digits(abs(rounded), places, locale))
    else:
        unit = _unit_index(unit_of, fmt, places)
        rounded, _ = _round_scaled(_to_decimal(amount), _is_compact(fmt), places, unit)
        text = _format(abs(amount), fmt, places, locale, unit_of)
    sign = "+" if rounded > 0 else MINUS_SIGN if rounded < 0 else ""
    return sign + text


def whole_percents(values: Sequence[float]) -> list[int]:
    """Return each value's share of the total in whole percents that add up to exactly 100.

    Rounding each share on its own can give 99 or 101 (33 + 33 + 33); a viewer adds them up
    and wonders what is missing. The largest remainder method floors every share, then gives
    the missing points to the shares that lost the most, earlier values first on a tie.

    Raises:
        ValueError: The values do not add up to more than zero.
    """
    total = sum(values)
    if total <= 0:
        raise ValueError("percents need a total above zero")
    exact = [value / total * 100 for value in values]
    percents = [math.floor(share) for share in exact]
    missing = 100 - sum(percents)
    by_remainder = sorted(range(len(values)), key=lambda index: percents[index] - exact[index])
    for index in by_remainder[:missing]:
        percents[index] += 1
    return percents


def format_percent(percent: float, *, locale: Locale) -> str:
    """Format a whole percent, e.g. 47 → "47%", or "%47" in tr-TR."""
    return locale.percent.format(_digits(_round(_to_decimal(percent), 0), 0, locale))


def _format(
    value: float, fmt: NumberFormat, decimals: int, locale: Locale, unit_of: float | None = None
) -> str:
    forced = _unit_index(unit_of, fmt, decimals)
    rounded, unit_index = _round_scaled(_to_decimal(value), _is_compact(fmt), decimals, forced)
    sign = MINUS_SIGN if rounded < 0 else ""
    digits = _digits(abs(rounded), decimals, locale)
    unit = locale.units(_unit_style(fmt, locale)).name(unit_index, rounded)
    return f"{sign}{fmt.prefix}{digits}{unit}{fmt.suffix}"


def _digits(number: Decimal, decimals: int, locale: Locale) -> str:
    """Write a rounded number that is not negative with the locale's separators."""
    integer, _, fraction = f"{number:,.{decimals}f}".partition(".")
    if len(integer.replace(",", "")) < 3 + locale.min_grouping_digits:
        integer = integer.replace(",", "")
    digits = integer.replace(",", locale.group)
    return f"{digits}{locale.decimal}{fraction}" if fraction else digits


def _is_compact(fmt: NumberFormat) -> bool:
    return fmt.compact is not False


def _unit_style(fmt: NumberFormat, locale: Locale) -> UnitStyle:
    """Return the unit names `fmt.compact` asks for; `true` means the locale's usual ones."""
    if isinstance(fmt.compact, bool):
        return locale.usual_units
    return fmt.compact


def _auto_decimals(value: float, compact: bool) -> tuple[int, int]:
    """Return the compact unit a value is shown in and the decimals it needs."""
    number = _to_decimal(value)
    scaled, unit_index = _scale(number, compact)
    if unit_index == 0:
        max_decimals = AUTO_MAX_DECIMALS
    else:
        integer_digits = len(str(int(abs(scaled))))
        max_decimals = max(0, COMPACT_SIGNIFICANT_DIGITS - integer_digits)
    rounded, rounded_unit = _round_scaled(number, compact, max_decimals)
    return rounded_unit, _decimals_needed(rounded)


def _unit_index(unit_of: float | None, fmt: NumberFormat, decimals: int) -> int | None:
    """Return the compact unit `unit_of` is shown in, or None without `unit_of`."""
    if unit_of is None or not _is_compact(fmt):
        return None
    rounded, unit = _round_scaled(_to_decimal(unit_of), True, decimals)
    steps = abs(rounded).scaleb(decimals)
    return unit if unit > 0 and steps >= MIN_UNIT_COUNT_STEPS else None


def _round_scaled(
    number: Decimal, compact: bool, decimals: int, unit: int | None = None
) -> tuple[Decimal, int]:
    """Scale to the compact unit and round, moving up a unit if rounding reaches 1000.

    With `unit`, scale to that unit instead, whatever the number's size.
    """
    if unit is not None:
        return _round(number / COMPACT_POWERS[unit], decimals), unit
    scaled, unit_index = _scale(number, compact)
    rounded = _round(scaled, decimals)
    if compact and unit_index > 0 and abs(rounded) >= 1000 and unit_index + 1 < len(COMPACT_POWERS):
        unit_index += 1
        rounded = _round(number / COMPACT_POWERS[unit_index], decimals)
    return rounded, unit_index


def _scale(number: Decimal, compact: bool) -> tuple[Decimal, int]:
    unit_index = 0
    if compact:
        while (
            unit_index + 1 < len(COMPACT_POWERS) and abs(number) >= COMPACT_POWERS[unit_index + 1]
        ):
            unit_index += 1
    return number / COMPACT_POWERS[unit_index], unit_index


def _round(number: Decimal, decimals: int) -> Decimal:
    """Round half away from zero: 2.675 → 2.68 and 2.5 → 3, as a viewer expects."""
    return number.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


def _decimals_needed(number: Decimal) -> int:
    return max(0, -int(number.normalize().as_tuple().exponent))


def _to_decimal(value: float) -> Decimal:
    """Convert via the shortest repr, so 2.675 becomes Decimal("2.675"), not 2.67499999...

    Raises:
        ValueError: The value is infinite or NaN. Spec validation rejects these.
    """
    if not math.isfinite(value):
        raise ValueError(f"cannot format {value}")
    return Decimal(str(value))
