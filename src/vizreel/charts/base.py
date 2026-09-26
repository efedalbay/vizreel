"""The contract every chart type implements, and the timing helpers charts share."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from vizreel.errors import RenderError
from vizreel.spec.models import BaseChart

if TYPE_CHECKING:
    from manim import Scene


class ChartType(ABC):
    """A chart type: its spec model and how it builds itself on a Manim scene.

    Attributes:
        name: The `type:` value in the spec, e.g. "line".
        model: Pydantic model for this chart's fields.
    """

    name: ClassVar[str]
    model: ClassVar[type[BaseChart]]

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
