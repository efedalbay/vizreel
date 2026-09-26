"""Sequence of events."""

from typing import TYPE_CHECKING

from vizreel.charts.base import ChartType
from vizreel.charts.registry import register
from vizreel.spec.models import TimelineChart

if TYPE_CHECKING:
    from manim import Scene


@register
class TimelineChartType(ChartType):
    """Events placed in order along a horizontal line."""

    name = "timeline"
    model = TimelineChart

    def build(self, scene: "Scene") -> None:
        """Not implemented yet."""
        raise NotImplementedError("the timeline chart type is not implemented yet")
