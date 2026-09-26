"""Commented spec templates that `vizreel new` prints."""

import textwrap

from vizreel.charts.registry import builtin_registry
from vizreel.errors import UsageError

_HEADER = """\
# A {name} chart. Every field is described in docs/SPEC.md.
# Check it:   vizreel validate FILE
# Render it:  vizreel render FILE --quality preview --still
version: 1
charts:
"""


def spec_template(type_name: str) -> str:
    """Return a complete, valid spec with one commented chart of `type_name`.

    Raises:
        UsageError: No chart type has that name.
    """
    registry = builtin_registry()
    if type_name not in registry.names():
        raise UsageError(
            f'unknown chart type "{type_name}". Valid types: {", ".join(registry.names())}'
        )
    template = registry.get(type_name).template
    return _HEADER.format(name=type_name) + textwrap.indent(template, "  ")
