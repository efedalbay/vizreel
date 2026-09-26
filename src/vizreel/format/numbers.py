"""Formatting of every number a chart displays. Pure functions; en-US only in version 1."""

import math
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from vizreel.spec.models import NumberFormat

MINUS_SIGN = "−"
"""Typographic minus. Same width as the digits, unlike the hyphen."""

AUTO_MAX_DECIMALS = 2
"""Most decimals shown when `decimals` is not set and the number is not abbreviated."""

COMPACT_SIGNIFICANT_DIGITS = 3
"""Significant digits of an abbreviated number when `decimals` is not set: 740M, 2.25B, 12.3K."""

COMPACT_UNITS: tuple[tuple[str, int], ...] = (
    ("", 1),
    ("K", 10**3),
    ("M", 10**6),
    ("B", 10**9),
    ("T", 10**12),
)

_DEFAULT_FORMAT = NumberFormat()


def format_number(value: float, fmt: NumberFormat | None = None) -> str:
    """Format one value for display, e.g. 740000000 → "$740M".

    Args:
        value: The number to format.
        fmt: Prefix, suffix, decimals and compact notation. Defaults to plain formatting.
    """
    return format_numbers([value], fmt)[0]


def format_numbers(values: Sequence[float], fmt: NumberFormat | None = None) -> list[str]:
    """Format values that appear together in one chart with the same number of decimals.

    When `fmt.decimals` is not set, every value gets as many decimals as the most
    precise one needs, so a chart shows 0.05, 0.20 and 2.25 rather than 0.05, 0.2 and 2.25.

    Args:
        values: The numbers to format.
        fmt: Prefix, suffix, decimals and compact notation. Defaults to plain formatting.
    """
    fmt = fmt or _DEFAULT_FORMAT
    decimals = decimals_for(values, fmt)
    return [_format(value, fmt, decimals) for value in values]


def decimals_for(values: Sequence[float], fmt: NumberFormat | None = None) -> int:
    """Return the number of decimals `format_numbers` uses for these values.

    A counting animation formats every frame with the decimals of its start and end
    values, so the text does not change length while it counts.
    """
    fmt = fmt or _DEFAULT_FORMAT
    if fmt.decimals is not None:
        return fmt.decimals
    return max((_auto_decimals(value, fmt.compact) for value in values), default=0)


def _format(value: float, fmt: NumberFormat, decimals: int) -> str:
    rounded, unit_index = _round_scaled(_to_decimal(value), fmt.compact, decimals)
    sign = MINUS_SIGN if rounded < 0 else ""
    digits = f"{abs(rounded):,.{decimals}f}"
    return f"{sign}{fmt.prefix}{digits}{COMPACT_UNITS[unit_index][0]}{fmt.suffix}"


def _auto_decimals(value: float, compact: bool) -> int:
    number = _to_decimal(value)
    scaled, unit_index = _scale(number, compact)
    if unit_index == 0:
        max_decimals = AUTO_MAX_DECIMALS
    else:
        integer_digits = len(str(int(abs(scaled))))
        max_decimals = max(0, COMPACT_SIGNIFICANT_DIGITS - integer_digits)
    rounded, _ = _round_scaled(number, compact, max_decimals)
    return _decimals_needed(rounded)


def _round_scaled(number: Decimal, compact: bool, decimals: int) -> tuple[Decimal, int]:
    """Scale to the compact unit and round, moving up a unit if rounding reaches 1000."""
    scaled, unit_index = _scale(number, compact)
    rounded = _round(scaled, decimals)
    if compact and unit_index > 0 and abs(rounded) >= 1000 and unit_index + 1 < len(COMPACT_UNITS):
        unit_index += 1
        rounded = _round(number / COMPACT_UNITS[unit_index][1], decimals)
    return rounded, unit_index


def _scale(number: Decimal, compact: bool) -> tuple[Decimal, int]:
    unit_index = 0
    if compact:
        while (
            unit_index + 1 < len(COMPACT_UNITS) and abs(number) >= COMPACT_UNITS[unit_index + 1][1]
        ):
            unit_index += 1
    return number / COMPACT_UNITS[unit_index][1], unit_index


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
