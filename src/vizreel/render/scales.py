"""Axis ranges, value-to-position mapping and label placement. Pure functions, no Manim import."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

NICE_STEPS = (1, 2, 2.5, 5)
"""Tick steps are one of these times a power of ten."""
MAX_TICKS = 6
"""Most ticks on a value axis, including both ends."""


@dataclass(frozen=True)
class Axis:
    """A value axis.

    Attributes:
        low: Value at the start of the axis.
        high: Value at the end of the axis.
        ticks: Values to mark, from low to high.
    """

    low: float
    high: float
    ticks: tuple[float, ...]


def value_axis(
    values: Sequence[float], *, low: float | None = None, high: float | None = None
) -> Axis:
    """Choose the range and ticks of a value axis.

    Without `low` and `high`, the axis includes zero (it starts at 0 when every value is
    positive) and is extended to the nearest ticks. A given `low` or `high` is kept exactly.

    Args:
        values: The data. At least one value.
        low: Fixed start of the axis, e.g. from `y_min`.
        high: Fixed end of the axis, e.g. from `y_max`.
    """
    start = low if low is not None else min(0.0, min(values))
    end = high if high is not None else max(0.0, max(values))
    if end <= start:
        end = start + 1
    step = _tick_step(start, end, fixed_low=low is not None, fixed_high=high is not None)
    if low is None:
        start = _floor_to(start, step)
    if high is None:
        end = _ceil_to(end, step)
    return Axis(start, end, _multiples(step, start, end))


def _tick_step(start: float, end: float, *, fixed_low: bool, fixed_high: bool) -> Decimal:
    """Return the smallest nice step that gives at most `MAX_TICKS` ticks."""
    exponent = math.floor(math.log10(end - start)) - 2
    while True:
        for nice in NICE_STEPS:
            step = Decimal(str(nice)).scaleb(exponent)
            low = start if fixed_low else _floor_to(start, step)
            high = end if fixed_high else _ceil_to(end, step)
            if len(_multiples(step, low, high)) <= MAX_TICKS:
                return step
        exponent += 1


def _floor_to(value: float, step: Decimal) -> float:
    return float(math.floor(Decimal(str(value)) / step) * step)


def _ceil_to(value: float, step: Decimal) -> float:
    return float(math.ceil(Decimal(str(value)) / step) * step)


def _multiples(step: Decimal, low: float, high: float) -> tuple[float, ...]:
    first = math.ceil(Decimal(str(low)) / step)
    last = math.floor(Decimal(str(high)) / step)
    return tuple(float(index * step) for index in range(first, last + 1))


@dataclass(frozen=True)
class LinearScale:
    """Maps values in `domain` linearly to positions in `range`."""

    domain: tuple[float, float]
    range: tuple[float, float]

    def __call__(self, value: float) -> float:
        """Position of `value`."""
        (d0, d1), (r0, r1) = self.domain, self.range
        return r0 + (value - d0) / (d1 - d0) * (r1 - r0)


def point_positions(count: int, start: float, end: float) -> list[float]:
    """Evenly spaced positions from `start` to `end`, both included."""
    if count == 1:
        return [(start + end) / 2]
    return [start + (end - start) * index / (count - 1) for index in range(count)]


def band_centers(count: int, start: float, end: float) -> list[float]:
    """Centers of `count` equal bands that fill `start` to `end`."""
    width = (end - start) / count
    return [start + width * (index + 0.5) for index in range(count)]


def thin_labels(centers: Sequence[float], widths: Sequence[float], gap: float) -> list[int]:
    """Choose which labels to show so that none overlap.

    Keeps every k-th label for the smallest k that fits, always with the first and the last.

    Args:
        centers: Horizontal center of each label, increasing.
        widths: Width of each label.
        gap: Least space between two shown labels.

    Returns:
        Indices of the labels to show.
    """
    count = len(centers)
    for stride in range(1, count + 1):
        shown = list(range(0, count, stride))
        if shown[-1] != count - 1:
            shown.append(count - 1)
            if len(shown) > 2 and not _apart(shown[-2], shown[-1], centers, widths, gap):
                shown.pop(-2)
        if all(_apart(a, b, centers, widths, gap) for a, b in zip(shown, shown[1:], strict=False)):
            return shown
    return [0] if count == 1 else [0, count - 1]


def _apart(a: int, b: int, centers: Sequence[float], widths: Sequence[float], gap: float) -> bool:
    return centers[a] + widths[a] / 2 + gap <= centers[b] - widths[b] / 2


def spread_labels(
    desired: Sequence[float], heights: Sequence[float], gap: float, low: float, high: float
) -> list[float]:
    """Move labels vertically so that none overlap, staying close to where they belong.

    Overlapping labels are grouped and each group is centered on the mean of its members'
    desired positions, then kept inside `low`..`high`.

    Args:
        desired: Desired vertical center of each label.
        heights: Height of each label.
        gap: Least space between two labels.
        low: Lowest allowed bottom edge.
        high: Highest allowed top edge.

    Returns:
        Vertical center of each label, in the order given.

    Raises:
        ValueError: The labels do not fit between `low` and `high`.
    """
    total = sum(heights) + gap * (len(heights) - 1)
    if total > high - low + 1e-9:
        raise ValueError("labels do not fit")
    groups: list[list[int]] = []
    for index in sorted(range(len(desired)), key=lambda i: desired[i]):
        groups.append([index])
        while len(groups) > 1:
            below, above = groups[-2], groups[-1]
            below_top = _group_bottom(below, desired, heights, gap, low, high) + _group_height(
                below, heights, gap
            )
            if below_top + gap <= _group_bottom(above, desired, heights, gap, low, high):
                break
            groups[-2:] = [below + above]

    centers = [0.0] * len(desired)
    for group in groups:
        y = _group_bottom(group, desired, heights, gap, low, high)
        for index in group:
            centers[index] = y + heights[index] / 2
            y += heights[index] + gap
    return centers


def _group_height(group: list[int], heights: Sequence[float], gap: float) -> float:
    return sum(heights[i] for i in group) + gap * (len(group) - 1)


def _group_bottom(
    group: list[int],
    desired: Sequence[float],
    heights: Sequence[float],
    gap: float,
    low: float,
    high: float,
) -> float:
    height = _group_height(group, heights, gap)
    center = sum(desired[i] for i in group) / len(group)
    return min(max(center - height / 2, low), high - height)


def two_line_splits(text: str) -> list[tuple[str, str]]:
    """Every way to break `text` into two lines at a space, most balanced first."""
    words = text.split()
    splits = [(" ".join(words[:i]), " ".join(words[i:])) for i in range(1, len(words))]
    return sorted(splits, key=lambda split: abs(len(split[0]) - len(split[1])))
