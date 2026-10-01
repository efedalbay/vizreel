"""Title cards: their lines appear one after another, in every frame shape."""

from pathlib import Path

import av
import numpy as np
import pytest

from vizreel.render.engine import RenderOptions, render_spec
from vizreel.themes.loader import load_theme

PREVIEW_FPS = 15
SPEC = """\
version: 1
charts:
  - id: part-two
    type: title-card
    kicker: Part 2
    title: How Northwind grew to five countries
    subtitle: Revenue, staff and customers, 2019 to 2024
    duration: 4
"""

pytestmark = pytest.mark.render


def ink(frame: np.ndarray, background: str) -> np.ndarray:
    """How far each pixel of an opaque frame is from the background color."""
    target = [int(background[index : index + 2], 16) for index in (1, 3, 5)]
    return np.abs(frame[:, :, :3].astype(int) - target).sum(axis=2)


def text_bands(frame: np.ndarray, background: str) -> list[slice]:
    """The runs of rows of a frame that have text on them, top to bottom."""
    inked = (ink(frame, background) > 60).any(axis=1)
    bands, start = [], None
    for row, has_ink in enumerate([*inked, False]):
        if has_ink and start is None:
            start = row
        elif not has_ink and start is not None:
            bands.append(slice(start, row))
            start = None
    return bands


def shown_by(frames: list[np.ndarray], rows: list[slice], background: str) -> int:
    """The first frame on which the text in these rows is nearly as strong as on the last."""
    strength = [sum(int(ink(frame[band], background).sum()) for band in rows) for frame in frames]
    return next(index for index, value in enumerate(strength) if value >= 0.9 * strength[-1])


@pytest.mark.parametrize("aspect", ["16:9", "9:16", "1:1"])
def test_the_kicker_headline_and_subtitle_appear_in_turn_then_hold(
    tmp_path: Path, aspect: str
) -> None:
    (tmp_path / "spec.yaml").write_text(SPEC, encoding="utf-8")
    colors = load_theme("default", tmp_path).colors

    [result] = render_spec(
        tmp_path / "spec.yaml",
        RenderOptions(out_dir=tmp_path, quality="preview", format="mp4", aspect=aspect),  # type: ignore[arg-type]
        reraise=True,
    )

    assert result.video is not None
    with av.open(str(result.video)) as container:
        frames = [frame.to_ndarray(format="rgb24") for frame in container.decode(video=0)]
    assert len(frames) == 4 * PREVIEW_FPS
    # The kicker, the lines of the headline, and the subtitle.
    bands = text_bands(frames[-1], colors.background)
    assert len(bands) >= 3
    kicker = shown_by(frames, bands[:1], colors.background)
    headline = shown_by(frames, bands[1:-1], colors.background)
    subtitle = shown_by(frames, bands[-1:], colors.background)
    assert kicker < headline < subtitle
    hold = int(1.5 * PREVIEW_FPS)
    # An mp4 frame differs from an identical one by a little compression noise.
    last = frames[-1].astype(int)
    assert all(np.abs(frame.astype(int) - last).max() <= 8 for frame in frames[-hold:])


def test_a_headline_too_long_for_three_lines_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "spec.yaml").write_text(
        SPEC.replace(
            "How Northwind grew to five countries",
            "How Northwind grew from one small garage workshop to offices in five countries",
        ),
        encoding="utf-8",
    )

    [result] = render_spec(
        tmp_path / "spec.yaml", RenderOptions(out_dir=tmp_path, quality="preview", aspect="9:16")
    )

    assert result.error == (
        "the title is too long to fit on 3 lines at the theme's size; shorten it"
    )
