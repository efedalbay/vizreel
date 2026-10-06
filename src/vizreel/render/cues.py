"""Cues: when each moment of a clip happens, for placing sound effects. Pure functions."""

from dataclasses import dataclass
from fractions import Fraction

CUE_NAMES = ("title", "structure", "reveal", "highlight", "mark", "move", "hold", "exit", "end")
"""The moments a cue file names:

- title: the panel, title and source appear.
- structure: axes, grid lines and labels draw, and a race's first values grow.
- reveal: the data grows, draws or counts; it ends when the numbers stop counting.
- highlight: the highlight beat, or the emphasis moving in a clip of a sequence.
- mark: the theme's highlight ring is drawn, as with a pen.
- move: an animation a chart type does not name.
- hold: the final hold, in which nothing moves.
- exit: the clip leaves the screen.
- end: the clip's last frame.
"""


@dataclass(frozen=True)
class Cue:
    """One moment of a clip.

    Attributes:
        name: One of `CUE_NAMES`, or a name a chart type from another package gives.
        start_frame: The first frame of the moment, counting from 0.
        end_frame: The frame after its last one: a moment of one frame ends one frame later.
    """

    name: str
    start_frame: int
    end_frame: int


def cue_document(
    cues: list[Cue], fps: float | Fraction, frames: int, clip: str
) -> dict[str, object]:
    """Return a clip's cues as a JSON document, with an `end` cue on its last frame.

    Times are in seconds from the start of the clip, rounded to the millisecond; frames count
    from 0. A cue starts on its first frame and ends where its last frame ends.

    Args:
        cues: The moments recorded while the clip rendered, in order.
        fps: The clip's frame rate.
        frames: The number of frames in the clip.
        clip: The clip's file name.
    """

    def seconds(frame: int) -> float:
        return round(float(frame / Fraction(fps)), 3)

    last = Cue("end", frames - 1, frames)
    return {
        "clip": clip,
        "fps": float(fps),
        "frames": frames,
        "duration": seconds(frames),
        "cues": [
            {
                "name": cue.name,
                "start": seconds(cue.start_frame),
                "end": seconds(cue.end_frame),
                "start_frame": cue.start_frame,
                "end_frame": cue.end_frame,
            }
            for cue in [*cues, last]
        ],
    }
