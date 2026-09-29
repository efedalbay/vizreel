"""Timing and ordering shared by the race chart types. Pure functions.

Not a chart type itself; the registry skips modules whose name starts with an underscore.
Positions along the race are in periods: 0 is the first period, 1.5 halfway between the
second and the third.
"""

import bisect
import math
from collections.abc import Callable, Sequence

from vizreel.errors import RenderError

MIN_PERIOD_SECONDS = 0.2
"""Least time a period of a race may take, so the viewer can follow it."""
SWAP_PERIODS = 0.4
"""How long two bars take to change places, in periods."""
SAMPLES_PER_PERIOD = 20
"""How often, per period, the order of the bars is looked at to find where it changes."""


def fill_gaps(values: Sequence[float | None], before: float | None) -> list[float | None]:
    """Fill the gaps of a series from the values around them.

    A gap between two values runs in a straight line from one to the other. A gap after the
    last value keeps it. A gap before the first value is `before`, or stays a gap if `before`
    is None.
    """
    known = [index for index, value in enumerate(values) if value is not None]
    filled: list[float | None] = []
    for index, value in enumerate(values):
        if value is not None:
            filled.append(value)
            continue
        later = bisect.bisect(known, index)
        if later == 0:
            filled.append(before)
        elif later == len(known):
            filled.append(values[known[-1]])
        else:
            low, high = known[later - 1], known[later]
            low_value, high_value = values[low], values[high]
            assert low_value is not None and high_value is not None
            filled.append(low_value + (high_value - low_value) * (index - low) / (high - low))
    return filled


def value_at(values: Sequence[float], position: float) -> float:
    """The value of a series without gaps at a position along the race.

    Between two periods it runs in a straight line. A race has at least two periods.
    """
    last = len(values) - 1
    position = min(max(position, 0.0), last)
    low = min(int(position), last - 1)
    return values[low] + (values[low + 1] - values[low]) * (position - low)


def order_at(series: Sequence[Sequence[float]], position: float) -> list[int]:
    """The series from the largest value to the smallest at a position.

    Series with equal values keep their order.
    """
    now = [value_at(values, position) for values in series]
    return sorted(range(len(series)), key=lambda index: (-now[index], index))


def race_position(seconds: float, total: float, periods: int) -> float:
    """Where a race is after `seconds` of the `total` it takes to go through its periods.

    It runs at one pace, one period after another, and slows to a stop over the last
    period, which it covers in the time of two, so that it ends softly without a jump.
    """
    last = periods - 1
    pace = (last + 1) / total
    steady = (last - 1) / pace
    if seconds <= steady:
        return seconds * pace
    share = min((seconds - steady) * pace / 2, 1.0)
    return last - (1 - share) ** 2


def check_race_time(seconds: float, periods: int, duration: float) -> None:
    """Check that a race has time enough for each of its periods.

    Raises:
        RenderError: A period would take less than `MIN_PERIOD_SECONDS`.
    """
    needed = periods * MIN_PERIOD_SECONDS
    if seconds < needed - 1e-9:
        raise RenderError(
            f"duration {duration:g}s is too short for {periods} periods; use at least "
            f"{duration - seconds + needed:.1f}s"
        )


def slot_positions(
    series: Sequence[Sequence[float]], ease: Callable[[float], float]
) -> Callable[[float], list[float]]:
    """Return where each series stands in the order at a position along the race.

    Place 0 is the largest value. Where two series change places, each slides to its new
    place over `SWAP_PERIODS`, eased, so the places change smoothly and briefly.

    Args:
        series: Every series' values, one per period, without gaps.
        ease: The curve of each change of place.
    """
    last = len(series[0]) - 1
    steps = max(last * SAMPLES_PER_PERIOD, 1)
    places = [[0] * len(series) for _ in range(steps + 1)]
    for step in range(steps + 1):
        for place, index in enumerate(order_at(series, last * step / steps)):
            places[step][index] = place
    changes: list[list[tuple[float, int]]] = [[] for _ in series]
    for step in range(1, steps + 1):
        for index in range(len(series)):
            moved = places[step][index] - places[step - 1][index]
            if moved:
                changes[index].append((last * step / steps, moved))

    def at(position: float) -> list[float]:
        result = []
        for index in range(len(series)):
            place = float(places[0][index])
            for start, moved in changes[index]:
                if start > position:
                    break
                place += moved * ease(min((position - start) / SWAP_PERIODS, 1.0))
            result.append(place)
        return result

    return at


CAPTION_FADE = 0.3
"""How long a caption takes to fade in, and out before the next one, in periods."""


def race_time(position: float, total: float, periods: int) -> float:
    """The seconds a race takes to reach a position: the inverse of `race_position`."""
    last = periods - 1
    pace = (last + 1) / total
    steady = (last - 1) / pace
    if position <= last - 1:
        return position / pace
    remaining = min(max(last - position, 0.0), 1.0)
    return steady + (1 - math.sqrt(remaining)) * 2 / pace


def caption_at(starts: Sequence[float], position: float) -> tuple[int, float] | None:
    """Which caption shows at a position along the race, and how opaque it is.

    Caption `i` shows from `starts[i]` until the next one starts, fading in over
    `CAPTION_FADE` periods and out over the `CAPTION_FADE` before the next; the last stays to
    the end. None before the first caption.
    """
    index = bisect.bisect_right(starts, position + 1e-9) - 1
    if index < 0:
        return None
    opacity = min((position - starts[index]) / CAPTION_FADE, 1.0)
    if index + 1 < len(starts):
        opacity = min(opacity, (starts[index + 1] - position) / CAPTION_FADE)
    return index, max(opacity, 0.0)


def check_caption_times(
    captions: Sequence[tuple[str, float]],
    intro: float,
    race_seconds: float,
    periods: int,
    duration: float,
) -> None:
    """Check that every caption stays on screen long enough to be read.

    Args:
        captions: Each caption's text and the position it appears at, in order.
        intro: When the race starts, in seconds from the start of the clip.
        race_seconds: How long the race takes.
        periods: How many periods it runs through.
        duration: Length of the clip; the last caption stays to its end.

    Raises:
        RenderError: A caption would go before it can be read.
    """
    from vizreel.charts.base import reading_time

    for index, (text, start) in enumerate(captions):
        shown = intro + race_time(start, race_seconds, periods)
        if index + 1 < len(captions):
            gone = intro + race_time(captions[index + 1][1], race_seconds, periods)
        else:
            gone = duration
        if gone - shown < reading_time(text) - 1e-9:
            raise RenderError(
                f'the caption "{text}" is on screen for {gone - shown:.1f}s and needs '
                f"{reading_time(text):.1f}s to be read; shorten it, move the next caption later "
                "or make the clip longer"
            )
