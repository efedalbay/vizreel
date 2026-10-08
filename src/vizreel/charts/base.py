"""The contract every chart type implements, and the timing helpers charts share."""

import math
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

from vizreel.errors import RenderError
from vizreel.format.locales import Locale
from vizreel.render.layout import Layout
from vizreel.spec.data import Table, TableError
from vizreel.spec.models import BaseChart
from vizreel.themes.models import Theme

if TYPE_CHECKING:
    from manim import Scene

    from vizreel.render.scene import ChartScene

T = TypeVar("T")


def arranged(layout: Layout, landscape: Callable[[], T], vertical: Callable[[], T]) -> T:
    """Build a chart's geometry in the arrangement its frame calls for.

    A landscape frame uses `landscape` and a vertical one `vertical`. A square frame is as
    narrow as a vertical one but not as tall, so neither always fits: it tries `landscape`,
    such as columns side by side, and uses `vertical` when that raises `RenderError`.
    """
    if not layout.square:
        return vertical() if layout.vertical else landscape()
    try:
        return landscape()
    except RenderError:
        return vertical()


CHART_API_VERSION = 1
"""Version of the chart type contract. It goes up when a change to `ChartType` or
`vizreel.plugin` would break chart types written for the previous version."""


@dataclass(frozen=True)
class Continuation:
    """What a clip of a sequence does after the clip before it.

    Attributes:
        item: The sequence item to emphasize.
        duration: Length of the clip, in seconds.
    """

    item: Any
    duration: float


class ChartType(ABC):
    """A chart type: its spec model and how it builds itself on a Manim scene.

    Chart modules import Manim inside `build`, not at the top, so that validating a spec
    does not pay for importing Manim.

    Attributes:
        name: The `type:` value in the spec, e.g. "line".
        model: Pydantic model for this chart's fields.
        template: A commented example of this chart as a YAML list item, printed by
            `vizreel new`. It must be a valid chart.
        api_version: The version of this contract the chart type is written for. A chart type
            from another package sets it to the `CHART_API_VERSION` it was written for.
        fits_to_content: In a vertical frame, whether the title, the source line and the
            panel close in around the chart's content when it leaves much of the frame empty.
            A chart type that draws the title and source in their bands and its panel around
            `layout.inner` gets this for free; one that places them itself sets it to False.
        own_header: Whether the chart type sets the title and subtitle itself, at sizes of
            its own, rather than in the title band. Its layout then has no title band.
        chart: The chart to build, an instance of `model`.
        theme: All styling.
        layout: All geometry.
        locale: How numbers are written. Pass it to every `format.numbers` call.
        logo_corner: Where the lower right corner of the theme's logo goes, if the chart
            type places it itself before its first animation, such as inside a card it fits
            around its content; None puts it at the lower right of `layout.source`.
        warnings: What the user should know about the clip, such as an effect left out
            because the duration is too short for it. Shown after the clip renders.
    """

    name: ClassVar[str]
    model: ClassVar[type[BaseChart]]
    template: ClassVar[str]
    api_version: ClassVar[int] = CHART_API_VERSION
    fits_to_content: ClassVar[bool] = True
    own_header: ClassVar[bool] = False

    def __init__(self, chart: BaseChart, theme: Theme, layout: Layout, locale: Locale) -> None:
        self.chart = chart
        self.theme = theme
        self.layout = layout
        self.locale = locale
        self.logo_corner: tuple[float, float] | None = None
        self.warnings: list[str] = []

    @classmethod
    def from_table(cls, table: Table, chart: dict[str, Any]) -> dict[str, Any]:
        """Return the chart's data fields, as a spec would write them, from a data file.

        A chart with `data:` gets these fields before it is validated, so the model checks
        them as it checks fields written in the spec. Read cells with the table's methods,
        which raise `TableError` naming the line and column of a cell that is wrong. A field
        the spec also writes is an error, so leave out a field the spec may give instead.

        Args:
            table: The data file's cells.
            chart: The chart's fields as the spec writes them, not yet validated.

        Raises:
            TableError: The table does not hold what the chart needs. By default every
                table: a chart type reads data files only if it implements this.
        """
        raise TableError(f"cannot be used: {cls.name} charts do not read data from a file")

    @abstractmethod
    def build(self, scene: "Scene") -> None:
        """Add mobjects and play animations on the given scene."""

    def emphasis(self, item: Any) -> list[Any]:
        """Return the animations that move the emphasis to the element a sequence item names.

        They set the final look of every element that can be emphasized, whatever it looked
        like before, so emphasizing an element always ends on the same frame; the chart's own
        highlight beat plays them too. Chart types whose model is a `SequencedChart` implement
        this; it is valid once `build` has run.
        """
        raise NotImplementedError(f"{self.name} charts cannot be told as a sequence")

    def continue_to(self, scene: "ChartScene", item: Any, duration: float) -> None:
        """Play the clip of a sequence that follows this chart's clip.

        The chart is built again without recording a frame, which leaves the scene exactly
        on the last frame of its own clip; then the emphasis moves to `item` and holds.

        Args:
            scene: The scene to play on.
            item: The sequence item to emphasize next.
            duration: Length of the clip, in seconds.

        Raises:
            RenderError: `duration` leaves less than the theme's hold after the emphasis.
        """
        from vizreel.render import elements

        motion = self.theme.motion
        hold = duration - motion.highlight
        if hold < motion.hold - 1e-9:
            raise RenderError(
                f"step_duration {duration:g}s is too short for this theme; use at least "
                f"{motion.highlight + motion.hold:g}s"
            )
        with scene.unrecorded():
            self.build(scene)
        scene.play(
            *self.emphasis(item),
            run_time=motion.highlight,
            rate_func=elements.easing(self.theme),
            cue="highlight",
        )
        scene.wait(hold)


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


def split_duration(
    duration: float,
    *,
    intro: float,
    highlight: float,
    hold: float,
    reveal_max: float | None = None,
) -> Phases:
    """Divide a clip into phases.

    The data reveal gets the time left after intro, highlight and the minimum hold, up to
    half of the clip and up to `reveal_max`. Any time beyond that lengthens the hold, so a
    long clip, such as one as long as its narration, counts no slower than a short one.

    Args:
        duration: Total clip length in seconds.
        intro: Length of the intro.
        highlight: Length of the highlight beat, 0 for none.
        hold: Minimum final hold.
        reveal_max: Longest data reveal, usually the theme's `motion.reveal_max`; None for
            no limit but half the clip.

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
    if reveal_max is not None:
        main = min(main, max(reveal_max, MIN_MAIN))
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


def sequential_progress(progress: float, index: int, count: int) -> float:
    """Progress of one of `count` items that run one after another, each in an equal share.

    Args:
        progress: How far the group is, from 0 to 1.
        index: Position of the item in the group, from 0.
        count: Number of items.

    Returns:
        How far the item is, from 0 to 1.
    """
    return min(max(progress * count - index, 0.0), 1.0)


class FrameClock:
    """Turns the wanted length of each animation into whole frames.

    Rounding every animation on its own adds up: two animations of 7.5 frames would make
    16 frames instead of 15. The clock tracks the total wanted time and gives each
    animation the frames that keep the total on it, so a clip has exactly
    `round(duration × fps)` frames and no animation is off by more than half a frame.
    """

    def __init__(self, fps: float | Fraction) -> None:
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


def seconds_up(seconds: float) -> str:
    """Write a number of seconds a user must give, rounded up to a tenth: 3.04 is "3.1".

    Rounding to the nearest tenth could suggest a duration that is still too short.
    """
    return f"{math.ceil(seconds * 10 - 1e-9) / 10:.1f}"


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
                f"set duration to at least {seconds_up(needed)}s"
            )


SMALLEST_NUMBER_SCALE = 0.5
"""A big number too wide for the frame shrinks to at most this share of its size
(docs/DESIGN.md §2)."""


def count_samples(start: float, end: float) -> list[float]:
    """Return values whose text is as wide as the widest text a count from `start` to `end` shows.

    With tabular figures, the width of a number in one format depends only on its sign, its
    number of digits, its compact unit and whether the unit name is plural. Each of these
    changes at zero, at a power of ten or at twice one, so the widest text is at one of those
    or at an end of the count.
    """
    low, high = sorted((start, end))
    samples = {start, end}
    if low < 0 < high:
        samples.add(0.0)
    for exponent in range(25):
        for magnitude in (10.0**exponent, 2 * 10.0**exponent):
            samples.update(value for value in (magnitude, -magnitude) if low <= value <= high)
    return sorted(samples)


def fitting_number_size(size: float, width: float, room: float, what: str) -> float:
    """Return the size at which a number `width` wide at `size` fits in `room`.

    A number that fits keeps its size; a wider one shrinks, down to `SMALLEST_NUMBER_SCALE`
    of it. Sizes are in px and widths in scene units.

    Raises:
        RenderError: The number does not fit even at the smallest size.
    """
    if width <= room:
        return size
    scale = room / width
    if scale < SMALLEST_NUMBER_SCALE:
        raise RenderError(
            f"{what} is too wide to fit even at half the theme's size; "
            "use compact: short, fewer decimals or a shorter prefix or suffix"
        )
    # Just under the exact scale, so that rounding in the text layout cannot push it over.
    return size * scale * (1 - 1e-6)
