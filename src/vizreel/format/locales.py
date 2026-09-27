"""The number conventions of each supported locale, following the Unicode CLDR."""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

NO_BREAK_SPACE = " "
NARROW_NO_BREAK_SPACE = " "


def _never(number: Decimal) -> bool:
    return False


def _exactly_one(number: Decimal) -> bool:
    return abs(number) == 1


def _integer_part_zero_or_one(number: Decimal) -> bool:
    return int(abs(number)) in (0, 1)


@dataclass(frozen=True)
class Locale:
    """How numbers are written in one language and region.

    Attributes:
        name: The `meta.locale` value, e.g. "tr-TR".
        group: Separator between groups of three digits.
        decimal: Separator before the decimals.
        percent: Where the digits go in a percent, e.g. "%{}" for %47.
        units: Names of the compact units thousand, million, billion and trillion, each as
            (singular, plural).
        unit_separator: Text between an abbreviated number and its unit.
        is_singular: Whether an abbreviated number takes the singular unit name.
        min_grouping_digits: Digits needed before the first group separator; with 2, 1846 has
            no separator but 18,460 does.
    """

    name: str
    group: str
    decimal: str
    percent: str
    units: tuple[tuple[str, str], tuple[str, str], tuple[str, str], tuple[str, str]]
    unit_separator: str = NO_BREAK_SPACE
    is_singular: Callable[[Decimal], bool] = _never
    min_grouping_digits: int = 1


EN_US = Locale(
    name="en-US",
    group=",",
    decimal=".",
    percent="{}%",
    units=(("K", "K"), ("M", "M"), ("B", "B"), ("T", "T")),
    unit_separator="",
)
TR_TR = Locale(
    name="tr-TR",
    group=".",
    decimal=",",
    percent="%{}",
    units=(("bin", "bin"), ("milyon", "milyon"), ("milyar", "milyar"), ("trilyon", "trilyon")),
)
ES_ES = Locale(
    name="es-ES",
    group=".",
    decimal=",",
    percent="{}" + NO_BREAK_SPACE + "%",
    units=(
        ("mil", "mil"),
        ("millón", "millones"),
        ("mil millones", "mil millones"),
        ("billón", "billones"),
    ),
    is_singular=_exactly_one,
    min_grouping_digits=2,
)
PT_BR = Locale(
    name="pt-BR",
    group=".",
    decimal=",",
    percent="{}%",
    units=(("mil", "mil"), ("milhão", "milhões"), ("bilhão", "bilhões"), ("trilhão", "trilhões")),
    is_singular=_integer_part_zero_or_one,
)
FR_FR = Locale(
    name="fr-FR",
    group=NARROW_NO_BREAK_SPACE,
    decimal=",",
    percent="{}" + NARROW_NO_BREAK_SPACE + "%",
    units=(
        ("mille", "mille"),
        ("million", "millions"),
        ("milliard", "milliards"),
        ("billion", "billions"),
    ),
    is_singular=_integer_part_zero_or_one,
)

LOCALES: dict[str, Locale] = {locale.name: locale for locale in (EN_US, TR_TR, ES_ES, PT_BR, FR_FR)}
"""Every supported locale by its `meta.locale` name."""


def locale_for(name: str) -> Locale:
    """Return the locale with this `meta.locale` name.

    Raises:
        KeyError: Not a supported locale. Spec validation rejects these.
    """
    return LOCALES[name]
