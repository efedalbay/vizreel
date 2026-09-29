"""A Manim scene that hosts one chart."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from manim import DEFAULT_WAIT_TIME, Mobject, Scene, config
from manim.scene.scene_file_writer import to_av_frame_rate

from vizreel.charts.base import ChartType, Continuation, FrameClock
from vizreel.render.elements import PANEL_Z_INDEX
from vizreel.render.layout import Box, Layout

if TYPE_CHECKING:
    from PIL.Image import Image

FIT_BELOW_SHARE = 0.9
"""The layout closes in around content that needs less than this share of its height."""


def content_extent(mobjects: list[Mobject], content: Box) -> tuple[float, float] | None:
    """Return the bottom and top of what is drawn in the `content` box, or None if nothing is.

    Every shape counts on its own, so a group that also holds the title or the source line
    does not stretch the extent to them. The background panel does not count.
    """
    bottoms, tops = [], []
    for mobject in mobjects:
        for part in mobject.family_members_with_points():
            if part.z_index == PANEL_Z_INDEX:
                continue
            bottom, top = float(part.get_bottom()[1]), float(part.get_top()[1])
            left, right = float(part.get_left()[0]), float(part.get_right()[0])
            inside = bottom < content.top and top > content.bottom
            if inside and left < content.right and right > content.left:
                bottoms.append(bottom)
                tops.append(top)
    return (min(bottoms), max(tops)) if bottoms else None


class ChartScene(Scene):
    """Renders a single chart by letting its chart type build on this scene.

    Every `play` needs an explicit `run_time`. Run times and waits are rounded to whole
    frames through a `FrameClock`, so the clip is exactly as long as the chart's duration.

    With a `continuation`, the scene renders a later clip of a sequence instead: the chart,
    which emphasizes the previous item, is built without recording, then the emphasis moves
    on (see `ChartType.continue_to`).

    With an exit in the chart's theme (`motion.exit`), the chart's last wait, its final hold,
    ends early by the exit's length, and the exit plays in the time left. Waits are held back
    until the next animation, or the end of the clip, to know which wait is the last.

    Attributes:
        still: With an exit, the frame before it, where the chart is complete; else None.
    """

    def __init__(
        self,
        chart_type: ChartType,
        continuation: Continuation | None = None,
        relayout: Callable[[Layout], ChartType] | None = None,
        **kwargs: Any,
    ) -> None:
        """Host a chart.

        Args:
            chart_type: The chart to build.
            continuation: For the later clips of a sequence, what follows the build.
            relayout: Builds the chart again in another layout. With it, the layout closes in
                around content that needs less height than it has (see `fit_to_content`).
            **kwargs: Passed on to Manim's `Scene`.
        """
        self.chart_type = chart_type
        self.continuation = continuation
        self.relayout = relayout
        self.clock = FrameClock(to_av_frame_rate(config.frame_rate))
        self.still: Image | None = None
        self._waiting = False
        self._held_back: float | None = None
        super().__init__(**kwargs)

    def construct(self) -> None:
        """Build the chart, or the next clip of its sequence."""
        if self.relayout is not None:
            self.fit_to_content(self.relayout)
        if self.continuation is None:
            self.chart_type.build(self)
        else:
            self.chart_type.continue_to(self, self.continuation.item, self.continuation.duration)
        self._end()

    def _end(self) -> None:
        """Hold the last wait, or the part of it before the exit, then play the exit."""
        from vizreel.render import elements

        theme = self.chart_type.theme
        motion = theme.motion
        if motion.exit == "none" or self._held_back is None:
            self._release_wait()
            return
        hold, self._held_back = self._held_back, None
        self._hold(hold - motion.exit_time)
        camera = self.renderer.camera
        # A copy: the image shares its pixels with the camera, which the exit draws over.
        self.still = camera.get_image().copy() if hasattr(camera, "get_image") else None
        center = self.chart_type.layout.inner.center
        self.play(
            elements.leave(list(self.mobjects), theme, center),
            run_time=motion.exit_time,
            rate_func=elements.easing(theme),
        )

    def fit_to_content(self, relayout: Callable[[Layout], ChartType]) -> None:
        """Close the layout in around the chart's content if it leaves much of it empty.

        The chart is built once without recording to measure how tall its content is. Built
        again in the fitted layout, it draws the same content, shifted, so every clip of a
        sequence gets the same layout.
        """
        layout = self.chart_type.layout
        with self.unrecorded():
            self.chart_type.build(self)
        extent = content_extent(self.mobjects, layout.content)
        self.clear()
        if extent is None:
            return
        bottom, top = extent
        if top - bottom < layout.content.height * FIT_BELOW_SHARE:
            self.chart_type = relayout(layout.fitted_to_content(bottom, top))

    @contextmanager
    def unrecorded(self) -> Iterator[None]:
        """Play animations to their end without writing any frame.

        Manim finishes each animation in one step, so the scene ends up exactly as it would
        after playing them. The frame clock starts again afterwards, so the recorded part of
        the clip has exactly the frames of its own length.
        """
        renderer = self.renderer
        renderer._original_skipping_status = True
        try:
            yield
            self._release_wait()
        finally:
            renderer._original_skipping_status = False
            renderer.skip_animations = False
            self.clock = FrameClock(to_av_frame_rate(config.frame_rate))

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
        self._release_wait()
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

        The wait is held back until the next animation or the end of the clip (see the class
        docstring). It is always frozen, whatever `frozen_frame` says, which guarantees that
        nothing moves; `stop_condition` is not supported.
        """
        self._release_wait()
        self._held_back = duration

    def _release_wait(self) -> None:
        """Render the wait held back, if there is one."""
        if self._held_back is not None:
            duration, self._held_back = self._held_back, None
            self._hold(duration)

    def _hold(self, duration: float) -> None:
        """Render a frozen wait for a whole number of frames.

        A frozen wait renders int(duration × fps) frames, so half a frame more gives exactly
        the frames the clock hands out.
        """
        frames = self.clock.frames_for(duration)
        self._waiting = True
        try:
            super().wait((frames + 0.5) / self.clock.fps, frozen_frame=True)
        finally:
            self._waiting = False
