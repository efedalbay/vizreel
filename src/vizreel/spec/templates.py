"""Commented spec templates that `vizreel new` prints."""

import textwrap

from vizreel.charts.registry import BUILT_IN, chart_registry
from vizreel.errors import UsageError

_HEADER = """\
# A {name} chart. Every field is described in docs/SPEC.md.
# Check it:   vizreel validate FILE
# Render it:  vizreel render FILE --quality preview --still
version: 1
charts:
"""
_PLUGIN_HEADER = _HEADER.replace(
    "Every field is described in docs/SPEC.md.",
    "It comes from {source}; see that package for its fields.",
)


def spec_template(type_name: str) -> str:
    """Return a complete, valid spec with one commented chart of `type_name`.

    Raises:
        UsageError: No chart type has that name.
    """
    registry = chart_registry()
    if type_name not in registry.names():
        raise UsageError(
            f'unknown chart type "{type_name}". Valid types: {", ".join(registry.names())}'
            + registry.unknown_type_hint(type_name)
        )
    template = registry.get(type_name).template
    source = registry.source(type_name)
    header = _HEADER if source == BUILT_IN else _PLUGIN_HEADER
    return header.format(name=type_name, source=source) + textwrap.indent(template, "  ")
