"""Axis ranges, value-to-position mapping and label placement. Pure functions, no Manim import."""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from itertools import combinations, pairwise

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


def wrap_text(text: str, fits: Callable[[str], bool], max_lines: int) -> list[str] | None:
    """Break `text` into lines at spaces, putting as many words on each line as fit.

    Args:
        text: The text to wrap.
        fits: Whether a line of text fits the available width.
        max_lines: Most lines allowed.

    Returns:
        The lines, or None if a word does not fit on its own or more lines are needed.
    """
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}" if current else word
        if fits(candidate):
            current = candidate
            continue
        if not current or not fits(word):
            return None
        lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines if len(lines) <= max_lines else None


def balanced_lines(text: str, width_of: Callable[[str], float], count: int) -> list[str]:
    """Break `text` at spaces into `count` lines whose widest line is as narrow as it can be.

    Wrapping puts as many words on each line as fit, which can leave one word alone on the
    last line; this spreads the words over the lines evenly instead.

    Args:
        text: The text to break, with at least `count` words.
        width_of: The width of a line of text.
        count: The number of lines.
    """
    words = text.split()
    widths: dict[tuple[int, int], float] = {}

    def width(start: int, end: int) -> float:
        if (start, end) not in widths:
            widths[start, end] = width_of(" ".join(words[start:end]))
        return widths[start, end]

    best: tuple[float, tuple[int, ...]] | None = None
    for breaks in combinations(range(1, len(words)), count - 1):
        bounds = (0, *breaks, len(words))
        widest = max(width(start, end) for start, end in pairwise(bounds))
        if best is None or widest < best[0] - 1e-9:
            best = (widest, bounds)
    assert best is not None, "the text has fewer words than lines"
    return [" ".join(words[start:end]) for start, end in pairwise(best[1])]


def clamp_center(center: float, width: float, low: float, high: float) -> float:
    """Move a span of `width` centered at `center` as little as needed to lie in low..high."""
    return min(max(center, low + width / 2), high - width / 2)


def two_line_splits(text: str) -> list[tuple[str, str]]:
    """Every way to break `text` into two lines at a space, most balanced first."""
    words = text.split()
    splits = [(" ".join(words[:i]), " ".join(words[i:])) for i in range(1, len(words))]
    return sorted(splits, key=lambda split: abs(len(split[0]) - len(split[1])))


RING_TILT = math.radians(-5)
"""How far a highlight ring leans from level: a pen's ellipse is rarely straight."""
RING_OVERSHOOT = math.radians(30)
"""How far past its start a highlight ring goes, as a pen does when it closes a loop."""
RING_WIDTH = 1.3
"""A highlight ring is at most this many times as wide as the box it rings; it grows taller
instead, to keep the box's corners inside it."""
RING_GAP = 0.15
"""How far outside its start a highlight ring ends, as a share of the box's height, so its two
ends pass each other instead of meeting."""


def ring_path(
    center: tuple[float, float], width: float, height: float, padding: float, samples: int = 96
) -> list[tuple[float, float]]:
    """The points of a ring drawn around a box, as if with a pen.

    An ellipse that leans a little (`RING_TILT`), starts at its upper left, goes clockwise
    once around and a little more (`RING_OVERSHOOT`), and widens as it goes, so it ends
    `RING_GAP` outside where it began. It passes `padding` beyond each corner of the box,
    whatever its lean, so it never crosses the box. It is as wide as an ellipse through the
    corners would be, √2 times the box, but at most `RING_WIDTH` times the box's width plus
    the padding; a wide box gets a taller ring rather than a much wider one.

    Args:
        center: The box's center.
        width: The box's width.
        height: The box's height.
        padding: The least distance between the box's corners and the ring.
        samples: The number of segments of the path.
    """
    half_width, half_height = width / 2 + padding, height / 2 + padding
    cos_tilt, sin_tilt = math.cos(RING_TILT), math.sin(RING_TILT)
    # The box's corners as the leaning ellipse sees them.
    corners = [
        (x * cos_tilt + y * sin_tilt, y * cos_tilt - x * sin_tilt)
        for x in (-half_width, half_width)
        for y in (-half_height, half_height)
    ]
    reach = max(abs(x) for x, _ in corners)
    radius_x = max(min(half_width * math.sqrt(2), half_width * RING_WIDTH), reach * 1.02)
    radius_y = max(abs(y) / math.sqrt(1 - (x / radius_x) ** 2) for x, y in corners)
    gap = height * RING_GAP
    start = math.radians(135)
    points = []
    for index in range(samples + 1):
        share = index / samples
        angle = start - (2 * math.pi + RING_OVERSHOOT) * share
        x = (radius_x + gap * share) * math.cos(angle)
        y = (radius_y + gap * share) * math.sin(angle)
        points.append(
            (center[0] + x * cos_tilt - y * sin_tilt, center[1] + x * sin_tilt + y * cos_tilt)
        )
    return points
