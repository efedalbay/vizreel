"""A Manim scene that hosts one chart."""

from typing import Any

from manim import Scene

from vizreel.charts.base import ChartType


class ChartScene(Scene):
    """Renders a single chart by letting its chart type build on this scene."""

    def __init__(self, chart_type: ChartType, **kwargs: Any) -> None:
        self.chart_type = chart_type
        super().__init__(**kwargs)

    def construct(self) -> None:
        """Build the chart."""
        self.chart_type.build(self)
