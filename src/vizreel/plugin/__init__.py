"""The API for chart types in other packages. See `docs/PLUGINS.md`.

Everything a chart type from another package may use is imported from here or from
`vizreel.plugin.render`. The rest of vizreel is internal and can change in any release; what is
here changes only with `CHART_API_VERSION`.

This module does not import Manim, so importing a chart type stays fast for `vizreel validate`.
Import `vizreel.plugin.render` inside `build`, as the built-in chart types do.
"""

from vizreel.charts.base import (
    CHART_API_VERSION,
    SMALLEST_NUMBER_SCALE,
    ChartType,
    Phases,
    check_reading_time,
    count_samples,
    fitting_number_size,
    sequential_progress,
    split_duration,
    staggered_progress,
)
from vizreel.errors import RenderError
from vizreel.format.locales import Locale
from vizreel.format.numbers import (
    MINUS_SIGN,
    change_amount,
    change_decimals,
    decimals_for,
    format_change,
    format_number,
    format_numbers,
    format_percent,
    shared_decimals,
    whole_percents,
)
from vizreel.render.engine import ChartResult, RenderOptions, render_spec
from vizreel.render.layout import Box, Layout, px, stack_gap, stroke_width
from vizreel.spec.models import BaseChart, Duration, NumberFormat, SequencedChart, SpecModel, Text
from vizreel.themes.models import FontStyle, Theme

__all__ = [
    "CHART_API_VERSION",
    "MINUS_SIGN",
    "SMALLEST_NUMBER_SCALE",
    "BaseChart",
    "Box",
    "ChartResult",
    "ChartType",
    "Duration",
    "FontStyle",
    "Layout",
    "Locale",
    "NumberFormat",
    "Phases",
    "RenderError",
    "RenderOptions",
    "SequencedChart",
    "SpecModel",
    "Text",
    "Theme",
    "change_amount",
    "change_decimals",
    "check_reading_time",
    "count_samples",
    "decimals_for",
    "fitting_number_size",
    "format_change",
    "format_number",
    "format_numbers",
    "format_percent",
    "px",
    "render_spec",
    "sequential_progress",
    "shared_decimals",
    "split_duration",
    "stack_gap",
    "staggered_progress",
    "stroke_width",
    "whole_percents",
]
