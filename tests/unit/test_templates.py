import re

import pytest

from vizreel.charts.registry import builtin_registry
from vizreel.errors import UsageError
from vizreel.spec.loader import parse_spec
from vizreel.spec.templates import spec_template

TYPES = builtin_registry().names()
COMMENTED_FIELD = re.compile(r"^(\s*)# (\w+:)", re.MULTILINE)


@pytest.mark.parametrize("name", TYPES)
def test_template_is_a_valid_spec_with_one_chart(name: str) -> None:
    spec = parse_spec(spec_template(name), f"{name}.yaml")

    assert [chart.type for chart in spec.charts] == [name]


@pytest.mark.parametrize("name", TYPES)
def test_template_stays_valid_with_every_optional_field_uncommented(name: str) -> None:
    uncommented = COMMENTED_FIELD.sub(r"\1\2", spec_template(name))

    assert uncommented != spec_template(name)
    parse_spec(uncommented, f"{name}.yaml")


@pytest.mark.parametrize("name", TYPES)
def test_template_starts_with_usage_comments(name: str) -> None:
    first_line = spec_template(name).splitlines()[0]

    assert first_line == f"# A {name} chart. Every field is described in docs/SPEC.md."


def test_unknown_type_lists_valid_types() -> None:
    with pytest.raises(UsageError, match='unknown chart type "pie". Valid types: bar, line'):
        spec_template("pie")
