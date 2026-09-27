"""The number conventions of each supported locale, following the Unicode CLDR."""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

NO_BREAK_SPACE = "\N{NO-BREAK SPACE}"
NARROW_NO_BREAK_SPACE = "\N{NARROW NO-BREAK SPACE}"

UnitStyle = Literal["long", "short"]
"""Whether compact numbers name their unit in full (740 million) or abbreviate it (740M)."""


def _never(number: Decimal) -> bool:
    return False


def _exactly_one(number: Decimal) -> bool:
    return abs(number) == 1


def _integer_part_zero_or_one(number: Decimal) -> bool:
    return int(abs(number)) in (0, 1)


@dataclass(frozen=True)
class UnitNames:
    """The names of the compact units thousand, million, billion and trillion in one style.

    Attributes:
        names: Each unit as (singular, plural).
        separator: Text between the number and the unit name.
        is_singular: Whether a number, as shown, takes the singular name.
    """

    names: tuple[tuple[str, str], tuple[str, str], tuple[str, str], tuple[str, str]]
    separator: str = NO_BREAK_SPACE
    is_singular: Callable[[Decimal], bool] = _never

    def name(self, unit_index: int, number: Decimal) -> str:
        """Return the unit after `number`, separator included; unit 0 has none."""
        if unit_index == 0:
            return ""
        singular, plural = self.names[unit_index - 1]
        return self.separator + (singular if self.is_singular(number) else plural)


def _invariable(thousand: str, million: str, billion: str, trillion: str) -> UnitNames:
    """Unit names without a plural, joined to the number by a no-break space."""
    return UnitNames(
        ((thousand, thousand), (million, million), (billion, billion), (trillion, trillion))
    )


@dataclass(frozen=True)
class Locale:
    """How numbers are written in one language and region.

    Attributes:
        name: The `meta.locale` value, e.g. "tr-TR".
        group: Separator between groups of three digits.
        decimal: Separator before the decimals.
        percent: Where the digits go in a percent, e.g. "%{}" for %47.
        long_units: Compact unit names in full, e.g. "milyon".
        short_units: Abbreviated compact unit names, e.g. "Mn".
        usual_units: The style `compact: true` uses: what readers of the locale expect.
        min_grouping_digits: Digits needed before the first group separator; with 2, 1846 has
            no separator but 18,460 does.
    """

    name: str
    group: str
    decimal: str
    percent: str
    long_units: UnitNames
    short_units: UnitNames
    usual_units: UnitStyle = "long"
    min_grouping_digits: int = 1

    def units(self, style: UnitStyle) -> UnitNames:
        """Return the compact unit names in this style."""
        return self.long_units if style == "long" else self.short_units


EN_US = Locale(
    name="en-US",
    group=",",
    decimal=".",
    percent="{}%",
    long_units=_invariable("thousand", "million", "billion", "trillion"),
    short_units=UnitNames((("K", "K"), ("M", "M"), ("B", "B"), ("T", "T")), separator=""),
    usual_units="short",
)
TR_TR = Locale(
    name="tr-TR",
    group=".",
    decimal=",",
    percent="%{}",
    long_units=_invariable("bin", "milyon", "milyar", "trilyon"),
    short_units=_invariable("B", "Mn", "Mr", "Tn"),
)
ES_ES = Locale(
    name="es-ES",
    group=".",
    decimal=",",
    percent="{}" + NO_BREAK_SPACE + "%",
    long_units=UnitNames(
        (
            ("mil", "mil"),
            ("millón", "millones"),
            ("mil millones", "mil millones"),
            ("billón", "billones"),
        ),
        is_singular=_exactly_one,
    ),
    short_units=_invariable("mil", "M", "mil M", "B"),
    min_grouping_digits=2,
)
PT_BR = Locale(
    name="pt-BR",
    group=".",
    decimal=",",
    percent="{}%",
    long_units=UnitNames(
        (("mil", "mil"), ("milhão", "milhões"), ("bilhão", "bilhões"), ("trilhão", "trilhões")),
        is_singular=_integer_part_zero_or_one,
    ),
    short_units=_invariable("mil", "mi", "bi", "tri"),
)
FR_FR = Locale(
    name="fr-FR",
    group=NARROW_NO_BREAK_SPACE,
    decimal=",",
    percent="{}" + NARROW_NO_BREAK_SPACE + "%",
    long_units=UnitNames(
        (
            ("mille", "mille"),
            ("million", "millions"),
            ("milliard", "milliards"),
            ("billion", "billions"),
        ),
        is_singular=_integer_part_zero_or_one,
    ),
    short_units=_invariable("k", "M", "Md", "Bn"),
)

LOCALES: dict[str, Locale] = {locale.name: locale for locale in (EN_US, TR_TR, ES_ES, PT_BR, FR_FR)}
"""Every supported locale by its `meta.locale` name."""


def locale_for(name: str) -> Locale:
    """Return the locale with this `meta.locale` name.

    Raises:
        KeyError: Not a supported locale. Spec validation rejects these.
    """
    return LOCALES[name]
