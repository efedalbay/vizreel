"""Theme model: every color, font, size and timing a chart uses.

Sizes are font sizes in pixels at 1080p, the unit of `docs/DESIGN.md`. They scale with the
output resolution. Minimums enforce the legibility rules of `docs/DESIGN.md` §2.
"""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vizreel.validation import raise_rule_violations

Color = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
"""A color as #RRGGBB."""

Easing = Literal["ease_out_sine", "ease_out_cubic", "ease_out_quart", "ease_out_expo"]
"""Ease-out curves only: movement starts fast and stops softly, without overshoot."""

Entrance = Literal["fade", "rise", "zoom"]
"""How the panel, titles, labels and legends appear: fading in, also rising a little, or also
growing a little."""

Exit = Literal["none", "fade", "sink", "zoom"]
"""How a clip ends: on the complete chart, or with everything fading out, also sinking a
little, or also shrinking a little."""

FontWeight = Literal["regular", "semibold", "bold"]

MAX_FONT_FAMILIES = 2


class ThemeModel(BaseModel):
    """Base for every theme model: unknown fields and loosely typed values are errors."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        allow_inf_nan=False,
        use_attribute_docstrings=True,
    )


class ThemeColors(ThemeModel):
    """Named color roles. Charts use roles, never color values."""

    background: Color
    """Frame background of opaque (mp4) output."""
    surface: Color
    """Background panel behind charts in transparent output."""
    text: Color
    """Titles, values and labels."""
    muted: Color
    """Secondary text and de-emphasized data."""
    grid: Color
    """Axes and grid lines."""
    accent: Color
    """Neutral emphasis, e.g. a single series or a stat number without trend."""
    positive: Color
    """Upward trend."""
    negative: Color
    """Downward trend."""
    highlight: Color
    """The one element that carries the message."""
    series: list[Color] = Field(min_length=3)
    """Series colors, used in this order. At least three, one per line chart series."""
    dim_opacity: float = Field(gt=0, le=1)
    """Opacity of everything except the highlighted element during the highlight beat."""


class FontStyle(ThemeModel):
    """A font family and weight."""

    family: Annotated[str, Field(min_length=1)]
    """Font family name, e.g. "Inter"."""
    weight: FontWeight = "regular"
    """Font weight."""


class ThemeFonts(ThemeModel):
    """Fonts by role. At most two families."""

    heading: FontStyle
    """Titles."""
    body: FontStyle
    """Labels, subtitles and the source line."""
    numbers: FontStyle
    """Values. Rendered with tabular figures so counting does not jitter."""

    @model_validator(mode="after")
    def _check_family_count(self) -> Self:
        families = list(
            dict.fromkeys(style.family for style in (self.heading, self.body, self.numbers))
        )
        if len(families) > MAX_FONT_FAMILIES:
            raise_rule_violations(
                type(self).__name__,
                [
                    (
                        ("numbers", "family"),
                        f"a theme uses at most {MAX_FONT_FAMILIES} font families, got "
                        f"{len(families)}: {', '.join(families)}",
                    )
                ],
            )
        return self


class ThemeSizes(ThemeModel):
    """Font sizes, panel geometry and stroke widths, in pixels at 1080p."""

    title: float = Field(ge=56)
    """Chart title. At least 56."""
    subtitle: float = Field(ge=32)
    """Line under the title. At least 32."""
    big_number: float = Field(ge=160)
    """The number of a stat chart. At least 160."""
    affix_scale: float = Field(default=0.6, ge=0.5, le=1)
    """Size of what surrounds the digits of a big number (a unit name, a currency, a percent
    sign), relative to the digits: 0.6, the default, sets "milyar" in "1,85 milyar" at 60% of the
    digits. 1 sets them at the size of the digits."""
    label: float = Field(ge=32)
    """Axis labels, category labels and the stat label. At least 32."""
    value: float = Field(ge=32)
    """Value labels on charts. At least 32."""
    caption: float = Field(ge=24)
    """Source line. At least 24."""
    panel_radius: float = Field(ge=0)
    """Corner radius of the background panel."""
    panel_padding: float = Field(ge=0)
    """Space between the panel edge and its content."""
    line: float = Field(gt=0)
    """Stroke width of data lines."""
    grid_line: float = Field(gt=0)
    """Stroke width of grid lines and axes."""
    dot: float = Field(gt=0)
    """Diameter of data point markers."""


class ThemeMotion(ThemeModel):
    """Timing of animations, in seconds."""

    easing: Easing
    """Curve of every movement and of counting numbers."""
    title_fade: float = Field(gt=0)
    """Fade-in of the title."""
    structure: float = Field(gt=0)
    """Drawing of axes and baselines."""
    stagger: float = Field(ge=0)
    """Delay between bars or events appearing one after another."""
    highlight: float = Field(gt=0)
    """The highlight beat."""
    hold: float = Field(ge=1.5)
    """Final hold where nothing moves. At least 1.5."""
    entrance: Entrance = "fade"
    """How the panel, titles, labels and legends appear. Data always grows, draws or counts."""
    exit: Exit = "none"
    """How a clip ends. With an exit, the hold still lasts `hold` before it."""
    exit_time: float = Field(default=0.5, gt=0)
    """Length of the exit, within the clip's duration."""


class Theme(ThemeModel):
    """A complete visual theme."""

    description: Annotated[str, Field(min_length=1)] | None = None
    """One line describing the theme, shown by `vizreel themes list`."""
    colors: ThemeColors
    """Color roles."""
    fonts: ThemeFonts
    """Fonts by role."""
    sizes: ThemeSizes
    """Font sizes and panel geometry, in pixels at 1080p."""
    motion: ThemeMotion
    """Animation timing."""
    background_panel: bool
    """Draw a panel in the surface color behind charts in transparent output."""
