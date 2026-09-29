from pathlib import Path
from typing import Literal

import pytest

from vizreel.charts.base import ChartType
from vizreel.charts.registry import ChartRegistry, builtin_registry
from vizreel.spec.models import BaseChart, StatChart

SHOWCASE = Path(__file__).parents[2] / "examples" / "showcase.yaml"


class DemoChart(BaseChart):
    type: Literal["demo"]
    duration: float = 3


class DemoChartType(ChartType):
    name = "demo"
    model = DemoChart
    template = "- { id: demo, type: demo }\n"

    def build(self, scene: object) -> None:
        raise NotImplementedError


def test_builtin_registry_has_every_chart_type() -> None:
    assert builtin_registry().names() == [
        "area",
        "bar",
        "compare",
        "grouped",
        "line",
        "share",
        "stacked",
        "stat",
        "table",
        "timeline",
        "waterfall",
    ]


def test_get_returns_the_chart_type_for_a_name() -> None:
    chart_type = builtin_registry().get("stat")

    assert chart_type.name == "stat"
    assert chart_type.model is StatChart


def test_get_unknown_name_lists_registered_types() -> None:
    with pytest.raises(
        KeyError, match="unknown chart type 'pie'; registered: area, bar, compare, grouped, line"
    ):
        builtin_registry().get("pie")


def test_register_adds_a_chart_type() -> None:
    registry = ChartRegistry()

    registry.register(DemoChartType)

    assert registry.names() == ["demo"]
    assert registry.models() == [DemoChart]


def test_register_twice_is_an_error() -> None:
    registry = ChartRegistry()
    registry.register(DemoChartType)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(DemoChartType)


def test_register_rejects_model_with_mismatched_type() -> None:
    class Mismatched(DemoChartType):
        name = "other"

    with pytest.raises(TypeError, match=r"DemoChart\.type must be Literal\['other'\]"):
        ChartRegistry().register(Mismatched)


def test_register_rejects_chart_type_without_template() -> None:
    class Untemplated(DemoChartType):
        template = ""

    with pytest.raises(TypeError, match="needs a template for `vizreel new`"):
        ChartRegistry().register(Untemplated)
