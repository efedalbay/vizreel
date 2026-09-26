"""Values over time."""

from typing import TYPE_CHECKING

from vizreel.charts.base import ChartType
from vizreel.charts.registry import register
from vizreel.spec.models import LineChart

if TYPE_CHECKING:
    from manim import Scene


@register
class LineChartType(ChartType):
    """One to three series drawn from left to right."""

    name = "line"
    model = LineChart

    def build(self, scene: "Scene") -> None:
        """Not implemented yet."""
        raise NotImplementedError("the line chart type is not implemented yet")
