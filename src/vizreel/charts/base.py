"""The contract every chart type implements, and the timing helpers charts share."""

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from vizreel.errors import RenderError
from vizreel.render.layout import Layout
from vizreel.spec.models import BaseChart
from vizreel.themes.models import Theme

if TYPE_CHECKING:
    from manim import Scene


class ChartType(ABC):
    """A chart type: its spec model and how it builds itself on a Manim scene.

    Chart modules import Manim inside `build`, not at the top, so that validating a spec
    does not pay for importing Manim.

    Attributes:
        name: The `type:` value in the spec, e.g. "line".
        model: Pydantic model for this chart's fields.
        template: A commented example of this chart as a YAML list item, printed by
            `vizreel new`. It must be a valid chart.
        chart: The chart to build, an instance of `model`.
        theme: All styling.
        layout: All geometry.
    """

    name: ClassVar[str]
    model: ClassVar[type[BaseChart]]
    template: ClassVar[str]

    def __init__(self, chart: BaseChart, theme: Theme, layout: Layout) -> None:
        self.chart = chart
        self.theme = theme
        self.layout = layout

    @abstractmethod
    def build(self, scene: "Scene") -> None:
        """Add mobjects and play animations on the given scene."""


MAIN_SHARE_MAX = 0.5
"""The data reveal takes at most this share of the clip (docs/DESIGN.md §3)."""
MIN_MAIN = 0.5
"""Shortest data reveal, in seconds, that still reads as motion."""
WORDS_PER_SECOND = 3
"""Reading speed: text stays on screen at least 1 second per 3 words (docs/DESIGN.md §3)."""


@dataclass(frozen=True)
class Phases:
    """Start and length of each phase of a clip, in seconds.

    Attributes:
        intro: Title and structure appear.
        main: The data is revealed.
        highlight: The highlight beat. Zero if the chart has none.
        hold: Nothing moves. At least the theme's hold.
    """

    intro: float
    main: float
    highlight: float
    hold: float

    @property
    def main_start(self) -> float:
        """When the data reveal starts."""
        return self.intro

    @property
    def highlight_start(self) -> float:
        """When the highlight beat starts."""
        return self.intro + self.main

    @property
    def hold_start(self) -> float:
        """When the final hold starts."""
        return self.intro + self.main + self.highlight

    @property
    def total(self) -> float:
        """Length of the whole clip."""
        return self.intro + self.main + self.highlight + self.hold


def split_duration(duration: float, *, intro: float, highlight: float, hold: float) -> Phases:
    """Divide a clip into phases.

    The data reveal gets the time left after intro, highlight and the minimum hold, up to
    half of the clip. Any time beyond that lengthens the hold.

    Args:
        duration: Total clip length in seconds.
        intro: Length of the intro.
        highlight: Length of the highlight beat, 0 for none.
        hold: Minimum final hold.

    Raises:
        RenderError: The duration leaves less than `MIN_MAIN` seconds for the data reveal.
    """
    available = duration - intro - highlight - hold
    if available < MIN_MAIN:
        needed = intro + highlight + hold + MIN_MAIN
        raise RenderError(
            f"duration {duration:g}s is too short for this chart; use at least {needed:g}s"
        )
    main = min(available, duration * MAIN_SHARE_MAX)
    return Phases(intro=intro, main=main, highlight=highlight, hold=hold + (available - main))


def staggered_progress(
    progress: float, index: int, count: int, *, stagger: float, total: float
) -> float:
    """Progress of one item in a group that starts one item after another.

    Items start `stagger` seconds apart and all finish within `total` seconds. If the delays
    would take more than half of `total`, they are shortened to fit.

    Args:
        progress: How far the group is, from 0 to 1.
        index: Position of the item in the group, from 0.
        count: Number of items.
        stagger: Wanted delay between two items, in seconds.
        total: Length of the whole group animation, in seconds.

    Returns:
        How far the item is, from 0 to 1.
    """
    delay = min(stagger, total / 2 / (count - 1)) if count > 1 else 0.0
    duration = total - delay * (count - 1)
    return min(max((progress * total - index * delay) / duration, 0.0), 1.0)


class FrameClock:
    """Turns the wanted length of each animation into whole frames.

    Rounding every animation on its own adds up: two animations of 7.5 frames would make
    16 frames instead of 15. The clock tracks the total wanted time and gives each
    animation the frames that keep the total on it, so a clip has exactly
    `round(duration × fps)` frames and no animation is off by more than half a frame.
    """

    def __init__(self, fps: int) -> None:
        self.fps = fps
        self._wanted = 0.0
        self._frames = 0

    def frames_for(self, duration: float) -> int:
        """Frames for the next animation of `duration` seconds. At least one."""
        self._wanted += duration
        target = max(math.floor(self._wanted * self.fps + 0.5), self._frames + 1)
        frames = target - self._frames
        self._frames = target
        return frames

    @property
    def frames(self) -> int:
        """Frames handed out so far."""
        return self._frames


def reading_time(text: str) -> float:
    """Seconds a text must stay on screen to be read."""
    return len(text.split()) / WORDS_PER_SECOND


def check_reading_time(texts: list[tuple[str, float]], duration: float) -> None:
    """Check that every text stays on screen long enough to be read before the clip ends.

    Args:
        texts: Each text with the time, in seconds, at which it appears.
        duration: Total clip length in seconds.

    Raises:
        RenderError: A text appears too late. The message names the duration needed.
    """
    for text, appears_at in texts:
        needed = appears_at + reading_time(text)
        if needed > duration:
            raise RenderError(
                f'"{text}" needs {reading_time(text):.1f}s on screen to be read; '
                f"set duration to at least {needed:.1f}s"
            )
