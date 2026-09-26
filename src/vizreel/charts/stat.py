"""Big number card."""

from typing import TYPE_CHECKING

from vizreel.charts.base import ChartType
from vizreel.charts.registry import register
from vizreel.spec.models import StatChart

if TYPE_CHECKING:
    from manim import Scene


@register
class StatChartType(ChartType):
    """A single number that counts up (or down) to its value."""

    name = "stat"
    model = StatChart

    def build(self, scene: "Scene") -> None:
        """Not implemented yet."""
        raise NotImplementedError("the stat chart type is not implemented yet")
