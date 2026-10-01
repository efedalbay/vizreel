"""Manim building blocks for chart types in other packages. See `docs/PLUGINS.md`.

Importing this module imports Manim, which takes several seconds; import it inside `build`.
"""

from vizreel.render.elements import (
    TextBlock,
    appear,
    bounds,
    check_fits,
    color,
    easing,
    fade_away,
    header,
    line_metrics,
    panel,
    redrawn_shapes,
    source_line,
    stack,
    text,
    text_block,
    wrapped_block,
)
from vizreel.render.numbers_text import NumberGlyphs

__all__ = [
    "NumberGlyphs",
    "TextBlock",
    "appear",
    "bounds",
    "check_fits",
    "color",
    "easing",
    "fade_away",
    "header",
    "line_metrics",
    "panel",
    "redrawn_shapes",
    "source_line",
    "stack",
    "text",
    "text_block",
    "wrapped_block",
]
