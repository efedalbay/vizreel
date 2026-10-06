"""Cue files: their moments land on the frames of the clip they describe."""

import json
from pathlib import Path

import av
import numpy as np
import pytest

from vizreel.render.engine import RenderOptions, render_spec

ROOT = Path(__file__).parents[2]

pytestmark = pytest.mark.render


@pytest.fixture(scope="module")
def showcase_clips(tmp_path_factory: pytest.TempPathFactory) -> list[tuple[str, Path, Path]]:
    out = tmp_path_factory.mktemp("cues")
    results = render_spec(
        ROOT / "examples" / "showcase.yaml",
        RenderOptions(out_dir=out, quality="preview", cues=True),
        reraise=True,
    )
    clips = []
    for result in results:
        assert result.video is not None and result.cues is not None, result.chart_id
        clips.append((result.chart_id, result.video, result.cues))
    return clips


def frames(path: Path) -> list[np.ndarray]:
    with av.open(str(path)) as container:
        return [frame.to_ndarray(format="rgba") for frame in container.decode(video=0)]


def test_every_showcase_clip_has_a_cue_file_whose_moments_land_on_its_frames(
    showcase_clips: list[tuple[str, Path, Path]],
) -> None:
    for chart_id, video, cues_file in showcase_clips:
        document = json.loads(cues_file.read_text(encoding="utf-8"))
        clip = frames(video)
        cues = document["cues"]
        by_name = {cue["name"]: cue for cue in cues}

        assert document["frames"] == len(clip), chart_id
        assert by_name["end"]["start_frame"] == len(clip) - 1, chart_id
        # The moments follow one another without a gap, from the first frame to the last.
        moments = [cue for cue in cues if cue["name"] not in ("mark", "end")]
        assert moments[0]["start_frame"] == 0, chart_id
        for before, after in zip(moments, moments[1:], strict=False):
            assert before["end_frame"] == after["start_frame"], chart_id
        assert moments[-1]["end_frame"] == len(clip), chart_id
        # Nothing moves from the start of the hold to the end, and the data moves in its reveal.
        hold = by_name["hold"]
        assert all(np.array_equal(frame, clip[-1]) for frame in clip[hold["start_frame"] :])
        reveal = by_name["reveal"]
        assert not np.array_equal(clip[reveal["start_frame"]], clip[reveal["end_frame"] - 1])
        if "highlight" in by_name:
            highlight = by_name["highlight"]
            # The frame before the beat is not yet the final one; the beat brings it there.
            assert not np.array_equal(clip[highlight["start_frame"] - 1], clip[-1]), chart_id
            assert highlight["end_frame"] == hold["start_frame"], chart_id
        # Seconds are frames over the frame rate.
        for cue in cues:
            assert cue["start"] == pytest.approx(cue["start_frame"] / document["fps"], abs=1e-3)


def test_the_mark_cue_is_when_the_ring_is_drawn(tmp_path: Path) -> None:
    import yaml

    from vizreel.themes.loader import BUILTIN_DIR

    theme = yaml.safe_load((BUILTIN_DIR / "default.yaml").read_text(encoding="utf-8"))
    theme.update(highlight_mark="ring")
    theme["colors"]["mark"] = "#E5483B"
    (tmp_path / "ring.yaml").write_text(yaml.safe_dump(theme), encoding="utf-8")
    (tmp_path / "spec.yaml").write_text(
        "version: 1\nmeta: { theme: ring.yaml, cues: true }\ncharts:\n"
        "  - { id: n, type: stat, value: 375000000, number: { prefix: '$', compact: true } }\n",
        encoding="utf-8",
    )

    [result] = render_spec(
        tmp_path / "spec.yaml", RenderOptions(out_dir=tmp_path, quality="preview")
    )

    assert result.cues is not None and result.video is not None
    document = json.loads(result.cues.read_text(encoding="utf-8"))
    [mark] = [cue for cue in document["cues"] if cue["name"] == "mark"]
    clip = frames(result.video)

    def pen(frame: np.ndarray) -> int:
        return int(np.all(np.abs(frame[..., :3].astype(int) - [229, 72, 59]) <= 24, axis=2).sum())

    assert pen(clip[mark["start_frame"] - 1]) == 0
    assert 0 < pen(clip[mark["start_frame"] + 2]) < pen(clip[mark["end_frame"]])
