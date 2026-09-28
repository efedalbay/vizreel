"""The example plugin in `examples/plugin`, installed as its pyproject.toml declares."""

from pathlib import Path

import pytest

from vizreel.charts.registry import chart_registry
from vizreel.errors import SpecError
from vizreel.spec.loader import load_spec, parse_spec, spec_json_schema
from vizreel.spec.templates import spec_template

EXAMPLE_PLUGIN = Path(__file__).parents[2] / "examples" / "plugin"

pytestmark = pytest.mark.usefixtures("example_plugin")


def test_the_progress_type_comes_from_the_example_plugin() -> None:
    registry = chart_registry()

    assert "progress" in registry.names()
    assert registry.source("progress") == "vizreel-progress 0.1.0"
    assert registry.problems == []


def test_the_example_spec_and_the_template_are_valid() -> None:
    spec = load_spec(EXAMPLE_PLUGIN / "progress.yaml")

    assert [chart.type for chart in spec.charts] == ["progress"]
    parse_spec(spec_template("progress"), "template")
    uncommented = spec_template("progress").replace("  # title:", "  title:")
    parse_spec(uncommented.replace("  # source:", "  source:"), "template")


def test_progress_fields_are_checked() -> None:
    with pytest.raises(SpecError) as caught:
        parse_spec(
            "version: 1\ncharts:\n  - { id: a, type: progress, value: -1, goal: 0 }\n", "spec.yaml"
        )

    assert [issue.location for issue in caught.value.issues] == [
        "charts[0].value",
        "charts[0].goal",
    ]


def test_progress_is_in_the_json_schema() -> None:
    assert "ProgressChart" in spec_json_schema()["$defs"]
