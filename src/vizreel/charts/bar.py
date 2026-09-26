"""Compare categories."""

from typing import TYPE_CHECKING

from vizreel.charts.base import ChartType
from vizreel.charts.registry import register
from vizreel.spec.models import BarChart

if TYPE_CHECKING:
    from manim import Scene


@register
class BarChartType(ChartType):
    """Vertical bars, one per category."""

    name = "bar"
    model = BarChart

    def build(self, scene: "Scene") -> None:
        """Not implemented yet."""
        raise NotImplementedError("the bar chart type is not implemented yet")
