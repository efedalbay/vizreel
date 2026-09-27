"""Pydantic models for the spec format. `docs/SPEC.md` is the reference for every field."""

from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

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


ChartId = Annotated[str, Field(pattern=CHART_ID_PATTERN), AfterValidator(_reject_reserved_name)]
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


class Meta(SpecModel):
    """Settings shared by all charts in the spec."""

    title: Text | None = None
    """Human-readable name of the spec. Not rendered."""
    theme: Text = "default"
    """Built-in theme name, or a path to a theme YAML file (relative to the spec file)."""
    resolution: Literal["720p", "1080p", "1440p", "4k"] = "1080p"
    """Output resolution, named by the short side: 1080p is 1920×1080, or 1080×1920 at 9:16."""
    aspect: Literal["16:9", "9:16"] = "16:9"
    """Frame shape: 16:9 is landscape, 9:16 is vertical, for Shorts, Reels and TikTok."""
    fps: Literal[30, 60] = 60
    """Frames per second."""
    format: Literal["mov", "webm", "mp4"] = "mov"
    """mov and webm have a transparent background. mp4 is opaque."""
    locale: Literal["en-US"] = "en-US"
    """Number formatting. Only en-US in version 1."""


class NumberFormat(SpecModel):
    """How displayed values are formatted."""

    prefix: str = ""
    """Text before the number, e.g. "$"."""
    suffix: str = ""
    """Text after the number, e.g. "%" or " users"."""
    decimals: Annotated[int, Field(ge=0, le=6)] | None = None
    """Fixed number of decimals. Leave out for automatic decimals."""
    compact: bool = False
    """Abbreviate large numbers: 740000000 becomes 740M."""


class BaseChart(SpecModel):
    """Fields shared by every chart type."""

    id: ChartId
    """Unique in the spec, [a-z0-9-]+. Used as the output file name."""
    type: str
    """Chart type."""
    title: Text | None = None
    """Shown at the top of the chart."""
    subtitle: Text | None = None
    """Smaller line under the title."""
    source: Text | None = None
    """Short source label shown at the bottom, e.g. "Source: example data"."""
    duration: Duration
    """Total clip length in seconds, including the final hold. Minimum 2."""


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


class LineChart(BaseChart):
    """One to three series drawn from left to right."""

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

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        issues = [
            *_duplicate_issues(self.x, "x", None, "x labels"),
            *self._series_issues(),
            *self._range_issues(),
            *self._highlight_issues(),
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


class BarChart(BaseChart):
    """One bar per category, as columns or as rows."""

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


class TimelineChart(BaseChart):
    """Events placed in order along a horizontal line."""

    type: Literal["timeline"]
    duration: Duration = 7
    """Total clip length in seconds, including the final hold. Minimum 2."""
    events: list[TimelineEvent] = Field(min_length=2, max_length=7)
    """Two to seven events, in chronological order."""

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
        raise_rule_violations(type(self).__name__, issues)
        return self


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
