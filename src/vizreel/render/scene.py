"""A Manim scene that hosts one chart."""

from collections.abc import Callable
from typing import Any

from manim import DEFAULT_WAIT_TIME, Scene, config

from vizreel.charts.base import ChartType, FrameClock


class ChartScene(Scene):
    """Renders a single chart by letting its chart type build on this scene.

    Every `play` needs an explicit `run_time`. Run times and waits are rounded to whole
    frames through a `FrameClock`, so the clip is exactly as long as the chart's duration.
    """

    def __init__(self, chart_type: ChartType, **kwargs: Any) -> None:
        self.chart_type = chart_type
        self.clock = FrameClock(int(config.frame_rate))
        self._waiting = False
        super().__init__(**kwargs)

    def construct(self) -> None:
        """Build the chart."""
        self.chart_type.build(self)

    def play(self, *args: Any, **kwargs: Any) -> None:
        """Play animations for a whole number of frames.

        Manim renders ceil(run_time × fps) frames, so half a frame less gives exactly the
        frames the clock hands out.

        Raises:
            TypeError: No `run_time` was given.
        """
        if self._waiting:
            super().play(*args, **kwargs)
            return
        if "run_time" not in kwargs:
            raise TypeError("ChartScene.play() needs an explicit run_time")
        frames = self.clock.frames_for(kwargs["run_time"])
        kwargs["run_time"] = (frames - 0.5) / self.clock.fps
        super().play(*args, **kwargs)

    def wait(
        self,
        duration: float = DEFAULT_WAIT_TIME,
        stop_condition: Callable[[], bool] | None = None,
        frozen_frame: bool | None = None,
    ) -> None:
        """Hold the current frame, unchanged, for a whole number of frames.

        The wait is always frozen, whatever `frozen_frame` says, which guarantees that
        nothing moves. A frozen wait renders int(duration × fps) frames, so half a frame
        more gives exactly the frames the clock hands out.
        """
        frames = self.clock.frames_for(duration)
        self._waiting = True
        try:
            super().wait(
                (frames + 0.5) / self.clock.fps, stop_condition=stop_condition, frozen_frame=True
            )
        finally:
            self._waiting = False
