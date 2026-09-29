"""The example plugin in `examples/plugin`, installed as its pyproject.toml declares."""

from pathlib import Path

import pytest

from vizreel.charts.registry import chart_registry
from vizreel.errors import SpecError
from vizreel.spec.loader import load_spec, parse_spec, spec_json_schema
from vizreel.spec.templates import spec_template

EXAMPLE_PLUGIN = Path(__file__).parents[2] / "examples" / "plugin"

pytestmark = pytest.mark.usefixtures("example_plugin")


def test_the_dots_type_comes_from_the_example_plugin() -> None:
    registry = chart_registry()

    assert "dots" in registry.names()
    assert registry.source("dots") == "vizreel-dots 0.1.0"
    assert registry.problems == []


def test_the_example_spec_and_the_template_are_valid() -> None:
    spec = load_spec(EXAMPLE_PLUGIN / "dots.yaml")

    assert [chart.type for chart in spec.charts] == ["dots"]
    parse_spec(spec_template("dots"), "template")
    uncommented = spec_template("dots").replace("  # title:", "  title:")
    parse_spec(uncommented.replace("  # source:", "  source:"), "template")


def test_dots_fields_are_checked() -> None:
    with pytest.raises(SpecError) as caught:
        parse_spec(
            "version: 1\ncharts:\n  - { id: a, type: dots, value: -1, total: 101 }\n", "spec.yaml"
        )

    assert [issue.location for issue in caught.value.issues] == [
        "charts[0].value",
        "charts[0].total",
    ]


def test_the_value_cannot_be_more_than_the_total() -> None:
    with pytest.raises(SpecError) as caught:
        parse_spec("version: 1\ncharts:\n  - { id: a, type: dots, value: 30, total: 25 }\n", "s")

    [issue] = caught.value.issues
    assert issue.location == "charts[0]"
    assert "value 30 is more than total 25" in issue.message


def test_the_grid_is_as_square_as_it_can_be() -> None:
    from vizreel_dots import grid_shape

    assert grid_shape(25) == (5, 5)
    assert grid_shape(18) == (5, 4)
    assert grid_shape(100) == (10, 10)
    assert grid_shape(2) == (2, 1)


def test_dots_is_in_the_json_schema() -> None:
    assert "DotsChart" in spec_json_schema()["$defs"]
