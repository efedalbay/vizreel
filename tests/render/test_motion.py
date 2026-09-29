"""Entrances and exits: every chart type honors them, keeps its length and ends as before."""

from pathlib import Path

import av
import numpy as np
import pytest

from vizreel.render.engine import ChartResult, RenderOptions, render_spec

ROOT = Path(__file__).parents[2]
SHOWCASE = ROOT / "examples" / "showcase.yaml"
SEQUENCES = Path(__file__).parent / "fixtures" / "sequences.yaml"
CHART_IDS = [
    "peak-valuation",
    "valuation",
    "offers",
    "final-years",
    "headcount",
    "profit",
    "revenue-mix",
    "region-growth",
    "users",
    "fundraiser",
    "market",
    "top-markets",
]

pytestmark = pytest.mark.render


def frames_rgba(path: Path) -> list[np.ndarray]:
    with av.open(str(path)) as container:
        return [frame.to_ndarray(format="rgba") for frame in container.decode(video=0)]


def image_rgba(path: Path) -> np.ndarray:
    with av.open(str(path)) as container:
        return next(container.decode(video=0)).to_ndarray(format="rgba")


def with_motion(spec: Path, motion: str, folder: Path) -> Path:
    """A copy of `spec` whose `meta` sets `motion`."""
    text = spec.read_text(encoding="utf-8")
    if "\nmeta:\n" in text:
        text = text.replace("\nmeta:\n", f"\nmeta:\n  motion: {motion}\n", 1)
    else:
        text = text.replace("version: 1\n", f"version: 1\nmeta:\n  motion: {motion}\n", 1)
    copy = folder / spec.name
    copy.write_text(text, encoding="utf-8")
    return copy


def render_all(spec: Path, folder: Path) -> dict[str, ChartResult]:
    options = RenderOptions(out_dir=folder, quality="preview", still=True)
    return {result.chart_id: result for result in render_spec(spec, options, reraise=True)}


@pytest.fixture(scope="module")
def plain(tmp_path_factory: pytest.TempPathFactory) -> dict[str, ChartResult]:
    return render_all(SHOWCASE, tmp_path_factory.mktemp("plain"))


@pytest.fixture(scope="module")
def moving(tmp_path_factory: pytest.TempPathFactory) -> dict[str, ChartResult]:
    folder = tmp_path_factory.mktemp("moving")
    return render_all(with_motion(SHOWCASE, "{ entrance: rise, exit: fade }", folder), folder)


@pytest.mark.parametrize("chart_id", CHART_IDS)
def test_every_chart_type_enters_and_leaves_within_its_length(
    plain: dict[str, ChartResult], moving: dict[str, ChartResult], chart_id: str
) -> None:
    before, after = plain[chart_id], moving[chart_id]
    assert before.video and before.still and after.video and after.still
    plain_frames, moving_frames = frames_rgba(before.video), frames_rgba(after.video)

    assert len(moving_frames) == len(plain_frames)
    # The entrance moves things into place, so the complete chart is the same; the still is
    # that chart, from before the exit, and the clip ends with nothing left on screen.
    assert np.array_equal(image_rgba(after.still), image_rgba(before.still))
    assert np.array_equal(image_rgba(after.still), plain_frames[-1])
    assert moving_frames[-1][:, :, 3].max() == 0


@pytest.mark.parametrize(
    "motion", ["{ entrance: zoom, exit: zoom }", "{ exit: sink }", "{ easing: ease_out_expo }"]
)
def test_other_entrances_exits_and_easings_keep_the_length(
    plain: dict[str, ChartResult], tmp_path: Path, motion: str
) -> None:
    spec = with_motion(SHOWCASE, motion, tmp_path)
    [result] = render_spec(
        spec,
        RenderOptions(out_dir=tmp_path, only=("offers",), quality="preview", still=True),
        reraise=True,
    )
    before = plain["offers"]
    assert result.video and result.still and before.video and before.still
    frames = frames_rgba(result.video)

    assert len(frames) == len(frames_rgba(before.video))
    assert np.array_equal(image_rgba(result.still), image_rgba(before.still))
    leaves = "exit" in motion
    assert (frames[-1][:, :, 3].max() == 0) == leaves


@pytest.mark.parametrize("chart_id", ["bar", "area"])
def test_a_sequence_leaves_only_at_the_end_and_still_cuts_seamlessly(
    tmp_path: Path, chart_id: str
) -> None:
    spec = with_motion(SEQUENCES, "{ entrance: rise, exit: sink }", tmp_path)
    results = render_spec(
        spec, RenderOptions(out_dir=tmp_path, only=(chart_id,), quality="preview"), reraise=True
    )
    first, second = (frames_rgba(result.video) for result in results if result.video)

    assert np.array_equal(first[-1], second[0])
    assert first[-1][:, :, 3].max() > 0
    assert second[-1][:, :, 3].max() == 0
    assert len(second) == 3 * 15


def test_a_chart_too_short_for_its_exit_says_how_long_it_must_be(tmp_path: Path) -> None:
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        "version: 1\ncharts:\n  - { id: s, type: stat, value: 1, duration: 2, "
        "motion: { exit: fade } }\n",
        encoding="utf-8",
    )

    [result] = render_spec(spec, RenderOptions(out_dir=tmp_path, quality="preview"))

    assert result.error == "duration 2s is too short for this chart; use at least 2.5s"
