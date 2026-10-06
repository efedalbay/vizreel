"""The theme's highlight ring: drawn around the highlighted value of a bar or stat chart."""

from pathlib import Path

import av
import numpy as np
import pytest
import yaml

from vizreel.render.engine import RenderOptions, render_spec
from vizreel.themes.loader import BUILTIN_DIR

PREVIEW_FPS = 15
MARK = "#E5483B"
SPEC = """\
version: 1
meta: { theme: ring.yaml }
charts:
  - id: offers
    type: bar
    title: Offers Northwind received
    bars:
      - { label: Contoso, value: 311000000 }
      - { label: Fabrikam, value: 375000000 }
      - { label: Tailspin, value: 120000000 }
    number: { prefix: "$", compact: true }
    highlight: { label: Fabrikam }
  - id: told
    type: bar
    bars:
      - { label: Contoso, value: 311000000 }
      - { label: Fabrikam, value: 375000000 }
    number: { prefix: "$", compact: true }
    sequence: [Contoso, Fabrikam]
  - id: check
    type: stat
    value: 375000000
    label: Fabrikam's offer
    number: { prefix: "$", compact: true }
  - id: rushed
    type: stat
    title: Fabrikam's offer
    value: 375000000
    number: { prefix: "$", compact: true }
    duration: 2.5
"""

pytestmark = pytest.mark.render


@pytest.fixture
def spec(tmp_path: Path) -> Path:
    theme = yaml.safe_load((BUILTIN_DIR / "default.yaml").read_text(encoding="utf-8"))
    theme["highlight_mark"] = "ring"
    theme["colors"]["mark"] = MARK
    (tmp_path / "ring.yaml").write_text(yaml.safe_dump(theme), encoding="utf-8")
    (tmp_path / "spec.yaml").write_text(SPEC, encoding="utf-8")
    return tmp_path / "spec.yaml"


def frames(path: Path) -> list[np.ndarray]:
    with av.open(str(path)) as container:
        return [
            frame.to_ndarray(format="rgba")[..., :3].astype(int)
            for frame in container.decode(video=0)
        ]


def pen(frame: np.ndarray) -> np.ndarray:
    target = [int(MARK[index : index + 2], 16) for index in (1, 3, 5)]
    return np.all(np.abs(frame - target) <= 24, axis=2)


def render(spec: Path, only: str, aspect: str = "16:9") -> list:  # type: ignore[type-arg]
    return render_spec(
        spec,
        RenderOptions(
            out_dir=spec.parent / aspect.replace(":", "x"),
            only=(only,),
            quality="preview",
            aspect=aspect,  # type: ignore[arg-type]
        ),
        reraise=True,
    )


@pytest.mark.parametrize("aspect", ["16:9", "9:16", "1:1"])
def test_a_ring_is_drawn_around_the_highlighted_bar_at_the_highlight_beat(
    spec: Path, aspect: str
) -> None:
    [result] = render(spec, "offers", aspect)

    assert result.video is not None and result.warnings == ()
    clip = frames(result.video)
    counts = [int(pen(frame).sum()) for frame in clip]
    first = next(index for index, count in enumerate(counts) if count > 10)
    # The ring appears only with the highlight beat, after the bars have grown, and is drawn
    # as a pen stroke: more of it on each frame until it is whole.
    assert first > len(clip) / 3
    assert counts[first] < counts[-1]
    assert counts[-1] > 150


def test_the_ring_moves_with_the_emphasis_and_the_clips_still_cut_together(spec: Path) -> None:
    results = render(spec, "told")

    first, second = (frames(result.video) for result in results if result.video)
    assert np.array_equal(first[-1], second[0])
    before, after = pen(second[0]), pen(second[-1])
    assert before.sum() > 150 and after.sum() > 150
    # The ring has moved from Contoso's value, on the left, to Fabrikam's, on the right.
    assert np.nonzero(after)[1].mean() > np.nonzero(before)[1].mean()


def test_a_stat_draws_its_ring_after_the_count(spec: Path) -> None:
    [result] = render(spec, "check")

    assert result.video is not None and result.warnings == ()
    clip = frames(result.video)
    assert len(clip) == 3 * PREVIEW_FPS
    # The count takes until 0.9s; the ring is drawn after it.
    assert pen(clip[int(0.5 * PREVIEW_FPS)]).sum() == 0
    assert pen(clip[-1]).sum() > 150


def test_a_stat_too_short_for_its_ring_keeps_its_duration_and_says_so(spec: Path) -> None:
    [result] = render(spec, "rushed")

    assert result.video is not None
    clip = frames(result.video)
    # 37.5 frames round to 38: a clip has round(duration × fps) frames.
    assert len(clip) == 38
    assert pen(clip[-1]).sum() == 0
    assert result.warnings == (
        "duration 2.5s leaves no time to draw the highlight ring after the count, so the clip "
        "has none; it needs at least 3.1s",
    )
