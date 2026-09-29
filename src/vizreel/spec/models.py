"""Pydantic models for the spec format. `docs/SPEC.md` is the reference for every field."""

from typing import Annotated, Any, ClassVar, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from vizreel.themes.models import Easing, Entrance, Exit
from vizreel.validation import Location, RuleViolation, raise_rule_violations, rule_error

CHART_ID_PATTERN = r"^[a-z0-9-]+$"
WINDOWS_RESERVED_NAMES = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)


def _duplicate_issues(
    values: list[str], list_name: str, key: str | None, what: str
) -> list[RuleViolation]:
    issues: list[RuleViolation] = []
    first_index: dict[str, int] = {}
    for index, value in enumerate(values):
        if value not in first_index:
            first_index[value] = index
            continue
        loc: Location = (list_name, index) if key is None else (list_name, index, key)
        first = f"{list_name}[{first_index[value]}]"
        issues.append((loc, f'"{value}" is already used by {first}; {what} must be unique'))
    return issues


def _quoted_list(items: list[str]) -> str:
    return ", ".join(f'"{item}"' for item in dict.fromkeys(items))


def _reject_reserved_name(value: str) -> str:
    if value in WINDOWS_RESERVED_NAMES:
        raise rule_error(f'"{value}" is a reserved file name on Windows. Choose another id')
    return value


FRAME_RATES: tuple[float, ...] = (23.976, 24, 25, 29.97, 30, 50, 59.94, 60)
"""The frame rates a clip can have: film, PAL and NTSC rates, and 30 and 60 for the web."""


def _check_frame_rate(value: float) -> float:
    if value not in FRAME_RATES:
        rates = ", ".join(f"{rate:g}" for rate in FRAME_RATES[:-1])
        raise rule_error(f"{value:g} is not a supported frame rate. Use {rates} or 60")
    return value


ChartId = Annotated[str, Field(pattern=CHART_ID_PATTERN), AfterValidator(_reject_reserved_name)]
FrameRate = Annotated[
    float, AfterValidator(_check_frame_rate), Field(json_schema_extra={"enum": list(FRAME_RATES)})
]
Text = Annotated[str, Field(min_length=1)]
Duration = Annotated[float, Field(ge=2)]


class SpecModel(BaseModel):
    """Base for every spec model: unknown fields and loosely typed values are errors."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        allow_inf_nan=False,
        use_attribute_docstrings=True,
    )


class Motion(SpecModel):
    """Motion settings that override the theme's `motion` for a chart or a whole spec."""

    easing: Easing | None = None
    """Curve of every movement and of counting numbers; all ease out. The theme's if left
    out."""
    entrance: Entrance | None = None
    """How the panel, titles, labels and legends appear: fade, rise or zoom. The theme's if
    left out."""
    exit: Exit | None = None
    """How the clip ends: none keeps the complete chart; fade, sink and zoom make it leave the
    screen. The theme's if left out."""


class Meta(SpecModel):
    """Settings shared by all charts in the spec."""

    title: Text | None = None
    """Human-readable name of the spec. Not rendered."""
    theme: Text = "default"
    """Built-in theme name, or a path to a theme YAML file (relative to the spec file)."""
    resolution: Literal["720p", "1080p", "1440p", "4k"] = "1080p"
    """Output resolution, named by the short side: 1080p is 1920×1080, or 1080×1920 at 9:16."""
    aspect: Literal["16:9", "9:16", "1:1"] = "16:9"
    """Frame shape: 16:9 is landscape, 9:16 is vertical, for Shorts, Reels and TikTok, and 1:1
    is square, for feeds."""
    fps: FrameRate = 60
    """Frames per second: 23.976, 24, 25, 29.97, 30, 50, 59.94 or 60. Match the editor's
    timeline, or it blends or drops frames."""
    format: Literal["mov", "webm", "mp4", "prores", "png"] = "mov"
    """mov, webm, prores and png have a transparent background; mp4 is opaque. prores is ProRes
    4444 in ID.prores.mov, png a folder of numbered PNG frames."""
    locale: Literal["en-US", "tr-TR", "es-ES", "pt-BR", "fr-FR"] = "en-US"
    """How numbers are written: separators, the percent sign and compact unit names."""
    motion: Motion = Field(default_factory=Motion)
    """Motion settings for every chart, over the theme's; a chart's own `motion` goes over
    these."""


class NumberFormat(SpecModel):
    """How displayed values are formatted."""

    prefix: str = ""
    """Text before the number, e.g. "$"."""
    suffix: str = ""
    """Text after the number, e.g. "%" or " users"."""
    decimals: Annotated[int, Field(ge=0, le=6)] | None = None
    """Fixed number of decimals. Leave out for automatic decimals."""
    compact: bool | Literal["long", "short"] = False
    """Abbreviate large numbers: 740000000 becomes 740M, or 740 milyon in tr-TR. `true` uses the
    locale's usual unit names; `long` and `short` choose them: 740 million, 740 Mn."""


class DataFile(SpecModel):
    """A CSV file with a chart's data, and the columns to read from it."""

    file: Text
    """Path to the file, relative to the spec file."""
    columns: list[Text] | None = Field(default=None, min_length=1)
    """The columns to read, by the names in the header row and in this order. All of them if
    left out."""


class BaseChart(SpecModel):
    """Fields shared by every chart type."""

    id: ChartId
    """Unique in the spec, [a-z0-9-]+. Used as the output file name."""
    type: str
    """Chart type."""
    data: Text | DataFile | None = None
    """A CSV file that gives the chart's data in place of fields such as `bars`: its path,
    relative to the spec file, or the path and the columns to read. See "Data from files" in
    docs/SPEC.md."""
    title: Text | None = None
    """Shown at the top of the chart."""
    subtitle: Text | None = None
    """Smaller line under the title."""
    source: Text | None = None
    """Short source label shown at the bottom, e.g. "Source: example data"."""
    duration: Duration
    """Total clip length in seconds, including the final hold. Minimum 2."""
    motion: Motion = Field(default_factory=Motion)
    """Motion settings for this chart, over those of `meta` and the theme."""


class SequencedChart(BaseChart):
    """A chart that can also be told as a sequence of clips, the emphasis moving each time.

    Subclasses name the elements a sequence can emphasize (`sequence_names`), say whether the
    chart already emphasizes one (`has_highlight`), and make a copy that emphasizes a given
    element (`with_highlight`).
    """

    sequence: list[Text] | None = Field(default=None, min_length=2, max_length=8)
    """Two to eight elements to emphasize, one clip each. Each clip after the first starts
    from the last frame of the one before and moves the emphasis to the next element."""
    step_duration: Duration = 3
    """Length in seconds of each clip after the first. Minimum 2."""

    sequence_noun: ClassVar[str] = "element"
    """What a sequence item names, in error messages, e.g. "bar label"."""

    def sequence_names(self) -> list[str]:
        """The names a sequence item can take."""
        raise NotImplementedError

    def has_highlight(self) -> bool:
        """Whether the chart itself names what to emphasize."""
        raise NotImplementedError

    def with_highlight(self, item: Any) -> Self:
        """Return a copy that emphasizes the element a sequence item names."""
        raise NotImplementedError

    def _sequence_issues(self) -> list[RuleViolation]:
        if self.sequence is None:
            return []
        issues: list[RuleViolation] = []
        if self.has_highlight():
            issues.append(
                (
                    ("sequence",),
                    "cannot be used together with a highlight; the sequence says what to "
                    "emphasize in each clip",
                )
            )
        names = self.sequence_names()
        for index, item in enumerate(self.sequence):
            name = _sequence_name(item)
            if name not in names:
                issues.append(
                    (
                        ("sequence", index),
                        f'"{name}" does not match any {self.sequence_noun}. '
                        f"Choose from: {_quoted_list(names)}",
                    )
                )
        return issues


def _sequence_name(item: Any) -> str:
    """The element a sequence item names: the item itself, or its `x` for a line chart."""
    return item if isinstance(item, str) else str(item.x)


class StatChart(BaseChart):
    """A single number that counts up (or down) to its value."""

    type: Literal["stat"]
    duration: Duration = 3
    """Total clip length in seconds, including the final hold. Minimum 2."""
    value: float
    """Final value."""
    start: float = 0
    """Value the count starts from."""
    label: Text | None = None
    """Line under the number."""
    number: NumberFormat = Field(default_factory=NumberFormat)
    """Formatting of the value."""
    trend: Literal["up", "down", "none"] = "none"
    """Colors the number with the theme's positive or negative color."""


class ProgressChart(BaseChart):
    """How far a value has come toward a goal, as a bar or a ring that fills."""

    type: Literal["progress"]
    duration: Duration = 4
    """Total clip length in seconds, including the final hold. Minimum 2."""
    value: float = Field(ge=0)
    """How far it has come. Zero or more."""
    goal: float = Field(gt=0)
    """Where it is going. A value past the goal fills the bar and shows more than 100%."""
    style: Literal["bar", "ring"] = "bar"
    """A bar that fills from the left, or a ring that fills clockwise from the top with the
    percent in the middle."""
    label: Text | None = None
    """Line under the chart, e.g. "raised for the new library"."""
    number: NumberFormat = Field(default_factory=NumberFormat)
    """Formatting of the value and the goal."""


class LineSeries(SpecModel):
    """One line on a line chart."""

    name: Text | None = None
    """Shown next to the line. Required if the chart has more than one series."""
    values: list[float | None]
    """One value per x label. null leaves a gap."""


class LineHighlight(SpecModel):
    """A point to mark on a line chart."""

    x: Text
    """The x label to mark with a vertical line and dot."""
    label: Text | None = None
    """Callout text at the highlighted point."""


class LineChart(SequencedChart):
    """One to three series drawn from left to right."""

    sequence_noun: ClassVar[str] = "x label"

    type: Literal["line"]
    duration: Duration = 6
    """Total clip length in seconds, including the final hold. Minimum 2."""
    x: list[str] = Field(min_length=2)
    """Labels on the horizontal axis, in order. Must be unique."""
    series: list[LineSeries] = Field(min_length=1, max_length=3)
    """One to three series."""
    number: NumberFormat = Field(default_factory=NumberFormat)
    """Formatting of axis and value labels."""
    y_min: float | None = None
    """Bottom of the vertical axis. Automatic if left out."""
    y_max: float | None = None
    """Top of the vertical axis. Automatic if left out."""
    highlight: LineHighlight | None = None
    """A point to mark."""
    # A line chart also accepts a point with a callout, where other charts take only names.
    sequence: list[Text | LineHighlight] | None = Field(  # type: ignore[assignment]
        default=None, min_length=2, max_length=8
    )
    """Two to eight points to mark, one clip each: an x label, or a point with a callout."""

    def sequence_names(self) -> list[str]:
        """The x labels that have a value in some series."""
        return [
            label
            for index, label in enumerate(self.x)
            if any(
                index < len(series.values) and series.values[index] is not None
                for series in self.series
            )
        ]

    def has_highlight(self) -> bool:
        """Whether a point is marked."""
        return self.highlight is not None

    def with_highlight(self, item: Any) -> Self:
        """Return a copy that marks the point a sequence item names."""
        highlight = LineHighlight(x=item) if isinstance(item, str) else item
        return self.model_copy(update={"highlight": highlight})

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        issues = [
            *_duplicate_issues(self.x, "x", None, "x labels"),
            *self._series_issues(),
            *self._range_issues(),
            *self._highlight_issues(),
            *self._sequence_issues(),
        ]
        raise_rule_violations(type(self).__name__, issues)
        return self

    def _series_issues(self) -> list[RuleViolation]:
        issues: list[RuleViolation] = []
        expected = len(self.x)
        for index, series in enumerate(self.series):
            values_loc: Location = ("series", index, "values")
            if len(series.values) != expected:
                issues.append(
                    (
                        values_loc,
                        f"expected {expected} values (same as x), got {len(series.values)}",
                    )
                )
            if all(value is None for value in series.values):
                issues.append((values_loc, "needs at least one number, not only null"))
            if len(self.series) > 1 and series.name is None:
                issues.append(
                    (("series", index, "name"), "required when the chart has more than one series")
                )
        return issues

    def _range_issues(self) -> list[RuleViolation]:
        y_min, y_max = self.y_min, self.y_max
        if y_min is not None and y_max is not None and y_min >= y_max:
            return [(("y_max",), f"must be greater than y_min ({y_min:g}), got {y_max:g}")]
        issues: list[RuleViolation] = []
        for series_index, series in enumerate(self.series):
            for value_index, value in enumerate(series.values):
                loc: Location = ("series", series_index, "values", value_index)
                if value is None:
                    continue
                if y_min is not None and value < y_min:
                    issues.append((loc, f"{value:g} is below y_min ({y_min:g})"))
                if y_max is not None and value > y_max:
                    issues.append((loc, f"{value:g} is above y_max ({y_max:g})"))
        return issues

    def _highlight_issues(self) -> list[RuleViolation]:
        if self.highlight is None:
            return []
        target = self.highlight.x
        loc: Location = ("highlight", "x")
        if target not in self.x:
            return [(loc, f'"{target}" is not one of the x labels: {_quoted_list(self.x)}')]
        index = self.x.index(target)
        has_value = any(
            index < len(series.values) and series.values[index] is not None
            for series in self.series
        )
        if not has_value:
            return [(loc, f'"{target}" has no value in any series; nothing to highlight')]
        return []


class RaceSeries(SpecModel):
    """One contestant of a race: a name and a value for every period."""

    name: Text
    """Shown next to its bar or line. Unique."""
    values: list[Annotated[float, Field(ge=0)] | None]
    """One value per period, zero or more. null leaves a gap that the periods around it fill
    in."""


class RaceHighlight(SpecModel):
    """The series to follow."""

    series: Text
    """Name of the series drawn in the highlight color."""


class RaceCaption(SpecModel):
    """A caption over a race, from a period on."""

    period: Text
    """The period it appears at, one of the race's periods."""
    text: Text
    """What it says, e.g. "The crisis". It stays until the next caption, or the end."""


MAX_CAPTIONS = 10


def _caption_issues(captions: list[RaceCaption], periods: list[str]) -> list[RuleViolation]:
    """What is wrong with the captions of a race: unknown periods, or periods out of order."""
    issues: list[RuleViolation] = []
    previous = -1
    for index, caption in enumerate(captions):
        loc: Location = ("captions", index, "period")
        if caption.period not in periods:
            issues.append(
                (loc, f'"{caption.period}" is not one of the periods: {_quoted_list(periods)}')
            )
            continue
        at = periods.index(caption.period)
        if at <= previous:
            issues.append(
                (
                    loc,
                    f'"{caption.period}" comes before the caption above it; list captions in order',
                )
            )
        previous = max(previous, at)
    return issues


def _race_issues(periods: list[str], series: list[RaceSeries]) -> list[RuleViolation]:
    """What is wrong with the periods and series of a race."""
    issues = _duplicate_issues(periods, "periods", None, "periods")
    issues += _duplicate_issues([item.name for item in series], "series", "name", "series names")
    for index, item in enumerate(series):
        loc: Location = ("series", index, "values")
        if len(item.values) != len(periods):
            issues.append(
                (loc, f"expected {len(periods)} values (same as periods), got {len(item.values)}")
            )
        if all(value is None for value in item.values):
            issues.append((loc, "needs at least one number, not only null"))
    return issues


def _highlight_issues(
    highlight: RaceHighlight | None, series: list[RaceSeries]
) -> list[RuleViolation]:
    names = [item.name for item in series]
    if highlight is None or highlight.series in names:
        return []
    return [
        (
            ("highlight", "series"),
            f'"{highlight.series}" does not match any series. Series: {_quoted_list(names)}',
        )
    ]


def _named_series_issues(
    by_series: dict[str, Any], series: list[RaceSeries], field: str
) -> list[RuleViolation]:
    """What is wrong with a field that gives something to series by name."""
    names = [item.name for item in series]
    return [
        (
            (field, name),
            f'"{name}" does not match any series. Series: {_quoted_list(names)}',
        )
        for name in by_series
        if name not in names
    ]


class BarRaceChart(BaseChart):
    """Bars that grow and change places as their values change over many periods."""

    type: Literal["bar-race"]
    duration: Duration = 15
    """Total clip length in seconds, including the final hold. Minimum 2."""
    periods: list[Text] = Field(min_length=2, max_length=200)
    """The periods, in order, e.g. years. Shown as written. Unique."""
    series: list[RaceSeries] = Field(min_length=2, max_length=30)
    """Two to thirty contestants."""
    show: int = Field(default=8, ge=3, le=12)
    """How many of the largest bars are on screen at once."""
    number: NumberFormat = Field(default_factory=NumberFormat)
    """Formatting of the values."""
    highlight: RaceHighlight | None = None
    """The series to follow, drawn in the highlight color."""
    captions: list[RaceCaption] = Field(default_factory=list, max_length=MAX_CAPTIONS)
    """Up to ten captions that appear over the race at the periods they name, in order."""
    colors: dict[Text, Text] = Field(default_factory=dict)
    """Brand colors for some series, by series name: the name of a color in the theme's
    `colors.brand`, e.g. {Northwind: northwind-blue}. The other bars keep the accent color."""
    images: dict[Text, Text] = Field(default_factory=dict)
    """Images for some series, by series name: a PNG, JPEG or SVG file relative to the spec
    file, e.g. {Northwind: logos/northwind.svg}, shown at the end of the series' bar."""

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        issues = _race_issues(self.periods, self.series)
        issues += _highlight_issues(self.highlight, self.series)
        issues += _named_series_issues(self.colors, self.series, "colors")
        issues += _named_series_issues(self.images, self.series, "images")
        issues += _caption_issues(self.captions, self.periods)
        raise_rule_violations(type(self).__name__, issues)
        return self


class LineRaceChart(BaseChart):
    """Lines that draw through many periods, the axis growing to keep them in the frame."""

    type: Literal["line-race"]
    duration: Duration = 15
    """Total clip length in seconds, including the final hold. Minimum 2."""
    periods: list[Text] = Field(min_length=2, max_length=200)
    """The periods, in order, e.g. years, along the horizontal axis. Unique."""
    series: list[RaceSeries] = Field(min_length=1, max_length=6)
    """One to six lines. Without a highlight, at most as many as the theme has series colors
    (three in the built-in themes)."""
    number: NumberFormat = Field(default_factory=NumberFormat)
    """Formatting of axis and value labels."""
    highlight: RaceHighlight | None = None
    """The series to follow, drawn in the highlight color while the others are muted."""
    captions: list[RaceCaption] = Field(default_factory=list, max_length=MAX_CAPTIONS)
    """Up to ten captions that appear over the race at the periods they name, in order."""

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        issues = _race_issues(self.periods, self.series)
        issues += _highlight_issues(self.highlight, self.series)
        issues += _caption_issues(self.captions, self.periods)
        raise_rule_violations(type(self).__name__, issues)
        return self


class AreaSeries(SpecModel):
    """One filled area on an area chart."""

    name: Text | None = None
    """Shown next to the area's end. Required if the chart has more than one series."""
    values: list[Annotated[float, Field(ge=0)]]
    """One value per x label, zero or more."""


class AreaHighlight(SpecModel):
    """The series to emphasize."""

    series: Text
    """Name of the series that keeps its color while the others dim."""


class AreaChart(SequencedChart):
    """One to three series drawn from left to right as filled areas, overlapping or stacked."""

    sequence_noun: ClassVar[str] = "series name"

    type: Literal["area"]
    duration: Duration = 6
    """Total clip length in seconds, including the final hold. Minimum 2."""
    x: list[str] = Field(min_length=2)
    """Labels on the horizontal axis, in order. Must be unique."""
    series: list[AreaSeries] = Field(min_length=1, max_length=3)
    """One to three series."""
    stack: bool = False
    """Stack the areas on each other, so the top shows their total, instead of overlapping
    them from zero."""
    number: NumberFormat = Field(default_factory=NumberFormat)
    """Formatting of axis and value labels."""
    highlight: AreaHighlight | None = None
    """The series to emphasize."""

    def sequence_names(self) -> list[str]:
        """The series names."""
        return [series.name for series in self.series if series.name is not None]

    def has_highlight(self) -> bool:
        """Whether a series is emphasized."""
        return self.highlight is not None

    def with_highlight(self, item: Any) -> Self:
        """Return a copy that emphasizes the series with this name."""
        return self.model_copy(update={"highlight": AreaHighlight(series=item)})

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        issues = _duplicate_issues(self.x, "x", None, "x labels")
        names = [series.name or "" for series in self.series]
        issues += _duplicate_issues(
            [name for name in names if name], "series", "name", "series names"
        )
        for index, series in enumerate(self.series):
            if len(series.values) != len(self.x):
                issues.append(
                    (
                        ("series", index, "values"),
                        f"expected {len(self.x)} values (same as x), got {len(series.values)}",
                    )
                )
            if len(self.series) > 1 and series.name is None:
                issues.append(
                    (("series", index, "name"), "required when the chart has more than one series")
                )
        if self.highlight is not None and self.highlight.series not in names:
            issues.append(
                (
                    ("highlight", "series"),
                    f'"{self.highlight.series}" does not match any series. '
                    f"Series: {_quoted_list([name for name in names if name])}",
                )
            )
        issues += self._sequence_issues()
        raise_rule_violations(type(self).__name__, issues)
        return self

    def tops(self) -> list[list[float]]:
        """The top of each area at each x label: its values, or its running total if stacked."""
        if not self.stack:
            return [list(series.values) for series in self.series]
        tops, below = [], [0.0] * len(self.x)
        for series in self.series:
            below = [low + value for low, value in zip(below, series.values, strict=True)]
            tops.append(below)
        return tops

    def bottoms(self) -> list[list[float]]:
        """The bottom of each area at each x label: zero, or the top of the area below it."""
        zero = [0.0] * len(self.x)
        return [zero, *self.tops()[:-1]] if self.stack else [zero for _ in self.series]


class Bar(SpecModel):
    """One bar on a bar chart."""

    label: Text
    """Category label. Must be unique."""
    value: float = Field(ge=0)
    """Bar height. Zero or more."""


class BarHighlight(SpecModel):
    """The bar to emphasize."""

    label: Text
    """Label of the bar to draw in the highlight color. Other bars are muted."""


class BarChart(SequencedChart):
    """One bar per category, as columns or as rows."""

    sequence_noun: ClassVar[str] = "bar label"

    type: Literal["bar"]
    duration: Duration = 5
    """Total clip length in seconds, including the final hold. Minimum 2."""
    bars: list[Bar] = Field(min_length=2, max_length=8)
    """Two to eight bars."""
    number: NumberFormat = Field(default_factory=NumberFormat)
    """Formatting of value labels."""
    sort: Literal["none", "asc", "desc"] = "none"
    """Order of bars."""
    layout: Literal["auto", "columns", "rows"] = "auto"
    """Columns grow up from a baseline; rows grow to the right, each under its label. auto uses
    columns in a 16:9 frame and rows in a 9:16 frame."""
    highlight: BarHighlight | None = None
    """The bar to emphasize."""

    def sequence_names(self) -> list[str]:
        """The bar labels."""
        return [bar.label for bar in self.bars]

    def has_highlight(self) -> bool:
        """Whether a bar is emphasized."""
        return self.highlight is not None

    def with_highlight(self, item: Any) -> Self:
        """Return a copy that emphasizes the bar with this label."""
        return self.model_copy(update={"highlight": BarHighlight(label=item)})

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        labels = [bar.label for bar in self.bars]
        issues = _duplicate_issues(labels, "bars", "label", "bar labels")
        if self.highlight is not None and self.highlight.label not in labels:
            issues.append(
                (
                    ("highlight", "label"),
                    f'"{self.highlight.label}" does not match any bar. '
                    f"Bar labels: {_quoted_list(labels)}",
                )
            )
        issues += self._sequence_issues()
        raise_rule_violations(type(self).__name__, issues)
        return self


class TimelineEvent(SpecModel):
    """One event on a timeline."""

    date: Text
    """Displayed as written, e.g. "Mar 2016"."""
    label: Text
    """Short description, at most about 40 characters for readability."""
    emphasis: bool = False
    """Draw this event in the highlight color, larger. At most one event per timeline."""


class TimelineChart(SequencedChart):
    """Events placed in order along a line."""

    sequence_noun: ClassVar[str] = "event date"

    type: Literal["timeline"]
    duration: Duration = 7
    """Total clip length in seconds, including the final hold. Minimum 2."""
    events: list[TimelineEvent] = Field(min_length=2, max_length=7)
    """Two to seven events, in chronological order."""

    def sequence_names(self) -> list[str]:
        """The event dates that name exactly one event."""
        dates = [event.date for event in self.events]
        return [date for date in dates if dates.count(date) == 1]

    def has_highlight(self) -> bool:
        """Whether an event has emphasis."""
        return any(event.emphasis for event in self.events)

    def with_highlight(self, item: Any) -> Self:
        """Return a copy that emphasizes the event with this date."""
        events = [
            event.model_copy(update={"emphasis": event.date == item}) for event in self.events
        ]
        return self.model_copy(update={"events": events})

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        emphasized = [index for index, event in enumerate(self.events) if event.emphasis]
        issues: list[RuleViolation] = [
            (
                ("events", index, "emphasis"),
                f"only one event can have emphasis; events[{emphasized[0]}] already has it",
            )
            for index in emphasized[1:]
        ]
        issues += self._sequence_issues()
        raise_rule_violations(type(self).__name__, issues)
        return self


class CompareValue(SpecModel):
    """One side of a compare chart."""

    label: Text
    """When or what the value is, e.g. "2019" or "Before the redesign"."""
    value: float
    """The value."""


class CompareChart(BaseChart):
    """One measure at two moments, and the change between them."""

    type: Literal["compare"]
    duration: Duration = 5
    """Total clip length in seconds, including the final hold. Minimum 2."""
    before: CompareValue
    """The earlier value."""
    after: CompareValue
    """The later value."""
    change: Literal["percent", "absolute", "none"] = "percent"
    """How the change is shown: in percent of the earlier value, as the difference, or not."""
    trend: Literal["auto", "none"] = "auto"
    """auto colors the change with the theme's positive color if it goes up and its negative
    color if it goes down; none keeps it in the text color, e.g. when a rise is bad news."""
    number: NumberFormat = Field(default_factory=NumberFormat)
    """Formatting of both values, and of the change when it is absolute."""

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        issues: list[RuleViolation] = []
        if self.change == "percent" and self.before.value <= 0:
            issues.append(
                (
                    ("before", "value"),
                    f"a percent change needs a value above zero, got {self.before.value:g}; "
                    "use change: absolute",
                )
            )
        raise_rule_violations(type(self).__name__, issues)
        return self


class WaterfallStart(SpecModel):
    """The value a waterfall starts from."""

    label: Text
    """What the value is, e.g. "Revenue"."""
    value: float = Field(ge=0)
    """The starting value. Zero or more."""


class WaterfallStep(SpecModel):
    """One change on a waterfall."""

    label: Text
    """What changes the value, e.g. "Salaries"."""
    value: float
    """The change: positive adds to the running total, negative takes from it."""


class WaterfallEnd(SpecModel):
    """The total a waterfall ends with. Its value is the start plus every step."""

    label: Text = "Total"
    """What the total is, e.g. "Profit"."""


class WaterfallHighlight(SpecModel):
    """The bar to emphasize."""

    label: Text
    """Label of the start, a step or the end."""


class WaterfallChart(SequencedChart):
    """How a starting value becomes a total through increases and decreases."""

    sequence_noun: ClassVar[str] = "bar label"

    type: Literal["waterfall"]
    duration: Duration = 6
    """Total clip length in seconds, including the final hold. Minimum 2."""
    start: WaterfallStart
    """The starting value."""
    steps: list[WaterfallStep] = Field(min_length=1, max_length=6)
    """One to six changes, in order."""
    end: WaterfallEnd = Field(default_factory=WaterfallEnd)
    """The total."""
    number: NumberFormat = Field(default_factory=NumberFormat)
    """Formatting of the values; changes are shown with their sign."""
    layout: Literal["auto", "columns", "rows"] = "auto"
    """Columns or rows, as for bar charts. auto uses columns at 16:9 and rows at 9:16."""
    highlight: WaterfallHighlight | None = None
    """The bar to emphasize. The total, if not given."""

    @property
    def labels(self) -> list[str]:
        """The label of every bar, in order: the start, each step, the end."""
        return [self.start.label, *(step.label for step in self.steps), self.end.label]

    def sequence_names(self) -> list[str]:
        """The labels of the start, the steps and the end."""
        return self.labels

    def has_highlight(self) -> bool:
        """Whether a bar is named to emphasize."""
        return self.highlight is not None

    def with_highlight(self, item: Any) -> Self:
        """Return a copy that emphasizes the bar with this label."""
        return self.model_copy(update={"highlight": WaterfallHighlight(label=item)})

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        issues: list[RuleViolation] = []
        locations: list[Location] = [
            ("start", "label"),
            *(("steps", index, "label") for index in range(len(self.steps))),
            ("end", "label"),
        ]
        first_seen: dict[str, Location] = {}
        for label, location in zip(self.labels, locations, strict=True):
            if label in first_seen:
                first = _location_text(first_seen[label])
                issues.append(
                    (location, f'"{label}" is already used by {first}; labels must be unique')
                )
            else:
                first_seen[label] = location
        total = self.start.value
        for index, step in enumerate(self.steps):
            total += step.value
            if total < 0:
                issues.append(
                    (
                        ("steps", index, "value"),
                        f"the running total falls to {total:g} here; a waterfall stays at zero "
                        "or above in version 1",
                    )
                )
                break
        if self.highlight is not None and self.highlight.label not in self.labels:
            issues.append(
                (
                    ("highlight", "label"),
                    f'"{self.highlight.label}" does not match any bar. '
                    f"Labels: {_quoted_list(self.labels)}",
                )
            )
        issues += self._sequence_issues()
        raise_rule_violations(type(self).__name__, issues)
        return self


class StackedSeries(SpecModel):
    """One part of every bar of a stacked bar chart."""

    name: Text
    """Shown in the legend."""
    values: list[Annotated[float, Field(ge=0)]]
    """One value per category, zero or more."""


class StackedHighlight(SpecModel):
    """The series to emphasize."""

    series: Text
    """Name of the series that keeps its color while the others dim."""


class StackedChart(SequencedChart):
    """Bars made of two or three parts, stacked, one bar per category."""

    sequence_noun: ClassVar[str] = "series name"

    type: Literal["stacked"]
    duration: Duration = 6
    """Total clip length in seconds, including the final hold. Minimum 2."""
    categories: list[Text] = Field(min_length=2, max_length=8)
    """Two to eight categories, one bar each, in order."""
    series: list[StackedSeries] = Field(min_length=2, max_length=3)
    """Two or three parts of each bar, from the bottom (or left) up."""
    number: NumberFormat = Field(default_factory=NumberFormat)
    """Formatting of the totals."""
    layout: Literal["auto", "columns", "rows"] = "auto"
    """Columns or rows, as for bar charts. auto uses columns at 16:9 and rows at 9:16."""
    highlight: StackedHighlight | None = None
    """The series to emphasize."""

    def sequence_names(self) -> list[str]:
        """The series names."""
        return [series.name for series in self.series]

    def has_highlight(self) -> bool:
        """Whether a series is emphasized."""
        return self.highlight is not None

    def with_highlight(self, item: Any) -> Self:
        """Return a copy that emphasizes the series with this name."""
        return self.model_copy(update={"highlight": StackedHighlight(series=item)})

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        issues = _duplicate_issues(self.categories, "categories", None, "categories")
        names = [series.name for series in self.series]
        issues += _duplicate_issues(names, "series", "name", "series names")
        for index, series in enumerate(self.series):
            if len(series.values) != len(self.categories):
                issues.append(
                    (
                        ("series", index, "values"),
                        f"has {len(series.values)} values but there are "
                        f"{len(self.categories)} categories; give one value per category",
                    )
                )
        if self.highlight is not None and self.highlight.series not in names:
            issues.append(
                (
                    ("highlight", "series"),
                    f'"{self.highlight.series}" does not match any series. '
                    f"Series: {_quoted_list(names)}",
                )
            )
        issues += self._sequence_issues()
        raise_rule_violations(type(self).__name__, issues)
        return self

    def totals(self) -> list[float]:
        """The total of each category: the height of its bar."""
        return [
            sum(values) for values in zip(*(series.values for series in self.series), strict=True)
        ]


class GroupedSeries(SpecModel):
    """One bar in every group of a grouped bar chart."""

    name: Text
    """Shown in the legend."""
    values: list[Annotated[float, Field(ge=0)]]
    """One value per category, zero or more."""


class GroupedHighlight(SpecModel):
    """The series to emphasize."""

    series: Text
    """Name of the series that keeps its color while the others dim."""


class GroupedChart(SequencedChart):
    """Bars side by side in groups of two or three, one group per category."""

    sequence_noun: ClassVar[str] = "series name"

    type: Literal["grouped"]
    duration: Duration = 6
    """Total clip length in seconds, including the final hold. Minimum 2."""
    categories: list[Text] = Field(min_length=2, max_length=6)
    """Two to six categories, one group each, in order."""
    series: list[GroupedSeries] = Field(min_length=2, max_length=3)
    """Two or three series, one bar in each group, in order within the group."""
    number: NumberFormat = Field(default_factory=NumberFormat)
    """Formatting of the value labels."""
    layout: Literal["auto", "columns", "rows"] = "auto"
    """Columns or rows, as for bar charts. auto uses rows at 9:16, and columns elsewhere
    unless their values do not fit side by side."""
    highlight: GroupedHighlight | None = None
    """The series to emphasize."""

    def sequence_names(self) -> list[str]:
        """The series names."""
        return [series.name for series in self.series]

    def has_highlight(self) -> bool:
        """Whether a series is emphasized."""
        return self.highlight is not None

    def with_highlight(self, item: Any) -> Self:
        """Return a copy that emphasizes the series with this name."""
        return self.model_copy(update={"highlight": GroupedHighlight(series=item)})

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        issues = _duplicate_issues(self.categories, "categories", None, "categories")
        names = [series.name for series in self.series]
        issues += _duplicate_issues(names, "series", "name", "series names")
        for index, series in enumerate(self.series):
            if len(series.values) != len(self.categories):
                issues.append(
                    (
                        ("series", index, "values"),
                        f"has {len(series.values)} values but there are "
                        f"{len(self.categories)} categories; give one value per category",
                    )
                )
        if self.highlight is not None and self.highlight.series not in names:
            issues.append(
                (
                    ("highlight", "series"),
                    f'"{self.highlight.series}" does not match any series. '
                    f"Series: {_quoted_list(names)}",
                )
            )
        issues += self._sequence_issues()
        raise_rule_violations(type(self).__name__, issues)
        return self


class SharePart(SpecModel):
    """One part of the whole on a share chart."""

    label: Text
    """What the part is, e.g. "Northwind"."""
    value: float = Field(gt=0)
    """The part's size, in any unit; it is shown as a percent of the total. Above zero."""


class ShareHighlight(SpecModel):
    """The part to emphasize."""

    label: Text
    """Label of the part drawn in the highlight color, with its percent in the middle."""


class ShareChart(SequencedChart):
    """How a whole divides into parts, as a ring with the emphasized part's percent inside."""

    sequence_noun: ClassVar[str] = "part label"

    type: Literal["share"]
    duration: Duration = 6
    """Total clip length in seconds, including the final hold. Minimum 2."""
    parts: list[SharePart] = Field(min_length=2, max_length=6)
    """Two to six parts, in order around the ring, clockwise from the top."""
    highlight: ShareHighlight | None = None
    """The part to emphasize. The largest part, if not given."""

    def sequence_names(self) -> list[str]:
        """The part labels."""
        return [part.label for part in self.parts]

    def has_highlight(self) -> bool:
        """Whether a part is named to emphasize."""
        return self.highlight is not None

    def with_highlight(self, item: Any) -> Self:
        """Return a copy that emphasizes the part with this label."""
        return self.model_copy(update={"highlight": ShareHighlight(label=item)})

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        labels = [part.label for part in self.parts]
        issues = _duplicate_issues(labels, "parts", "label", "part labels")
        if self.highlight is not None and self.highlight.label not in labels:
            issues.append(
                (
                    ("highlight", "label"),
                    f'"{self.highlight.label}" does not match any part. '
                    f"Parts: {_quoted_list(labels)}",
                )
            )
        issues += self._sequence_issues()
        raise_rule_violations(type(self).__name__, issues)
        return self

    def highlighted(self) -> int:
        """Index of the emphasized part: the one named by `highlight`, else the largest."""
        if self.highlight is not None:
            return [part.label for part in self.parts].index(self.highlight.label)
        values = [part.value for part in self.parts]
        return values.index(max(values))


class TableColumn(SpecModel):
    """One column of a table."""

    name: Text
    """Shown above the column."""
    number: NumberFormat = Field(default_factory=NumberFormat)
    """Formatting of the column's numbers. Ignored for a column of text."""


class TableHighlight(SpecModel):
    """The row to emphasize."""

    row: Text
    """Name of the row, as in its first cell."""


class TableChart(SequencedChart):
    """A few rows and columns, the rows appearing one after another."""

    sequence_noun: ClassVar[str] = "row name"

    type: Literal["table"]
    duration: Duration = 6
    """Total clip length in seconds, including the final hold. Minimum 2."""
    columns: list[TableColumn] = Field(min_length=2, max_length=4)
    """Two to four columns. The first holds the row names."""
    rows: list[list[Text | float]] = Field(min_length=2, max_length=8)
    """Two to eight rows, each with one cell per column: the row's name, then numbers or text."""
    highlight: TableHighlight | None = None
    """The row to emphasize."""

    @property
    def row_names(self) -> list[str]:
        """The first cell of every row."""
        return [str(row[0]) if row else "" for row in self.rows]

    def numeric(self, column: int) -> bool:
        """Whether a column holds numbers rather than text. The first column never does."""
        return column > 0 and isinstance(self.rows[0][column], float | int)

    def sequence_names(self) -> list[str]:
        """The row names."""
        return self.row_names

    def has_highlight(self) -> bool:
        """Whether a row is emphasized."""
        return self.highlight is not None

    def with_highlight(self, item: Any) -> Self:
        """Return a copy that emphasizes the row with this name."""
        return self.model_copy(update={"highlight": TableHighlight(row=item)})

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        issues: list[RuleViolation] = []
        width = len(self.columns)
        for index, row in enumerate(self.rows):
            if len(row) != width:
                issues.append(
                    (
                        ("rows", index),
                        f"has {len(row)} cells but there are {width} columns; "
                        "give one cell per column",
                    )
                )
        if issues:
            raise_rule_violations(type(self).__name__, issues)
        for index, row in enumerate(self.rows):
            if not isinstance(row[0], str):
                issues.append(
                    (("rows", index, 0), "the first cell names the row; write it as text")
                )
        for column in range(1, width):
            numbers = self.numeric(column)
            kind = "numbers" if numbers else "text"
            for index, row in enumerate(self.rows):
                if isinstance(row[column], str) == numbers:
                    issues.append(
                        (
                            ("rows", index, column),
                            f'column "{self.columns[column].name}" holds {kind}, as in its first '
                            f"row, so this cell must be {kind} too",
                        )
                    )
        first_seen: dict[str, int] = {}
        for index, name in enumerate(self.row_names):
            if name in first_seen:
                issues.append(
                    (
                        ("rows", index, 0),
                        f'"{name}" is already used by rows[{first_seen[name]}]; row names must be '
                        "unique",
                    )
                )
            else:
                first_seen.setdefault(name, index)
        if self.highlight is not None and self.highlight.row not in self.row_names:
            issues.append(
                (
                    ("highlight", "row"),
                    f'"{self.highlight.row}" does not match any row. '
                    f"Rows: {_quoted_list(self.row_names)}",
                )
            )
        issues += self._sequence_issues()
        raise_rule_violations(type(self).__name__, issues)
        return self


def _location_text(location: Location) -> str:
    """Write a location the way error messages show it: steps[2].label."""
    text = ""
    for part in location:
        text += f"[{part}]" if isinstance(part, int) else f".{part}" if text else part
    return text


class Spec(SpecModel):
    """A vizreel spec: one or more charts, each rendered to its own clip.

    Validate specs through `vizreel.spec.loader`, which replaces `charts` with a
    discriminated union of every registered chart type.
    """

    version: Literal[1]
    """Spec format version. Currently 1."""
    meta: Meta = Field(default_factory=Meta)
    """Settings shared by all charts."""
    charts: list[BaseChart] = Field(min_length=1)
    """One or more charts. Each renders to its own file."""

    @field_validator("version", mode="before")
    @classmethod
    def _reject_boolean_version(cls, value: object) -> object:
        # YAML `true` loads as True, which equals 1 and would pass Literal[1].
        if isinstance(value, bool):
            raise rule_error(f"expected 1, got {str(value).lower()}")
        return value

    @model_validator(mode="after")
    def _check_unique_ids(self) -> Self:
        ids = [chart.id for chart in self.charts]
        raise_rule_violations(type(self).__name__, _duplicate_issues(ids, "charts", "id", "ids"))
        return self
