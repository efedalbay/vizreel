from pathlib import Path

import pytest

from vizreel.errors import RenderError
from vizreel.render.engine import (
    FrameSettings,
    RenderOptions,
    frame_settings,
    output_paths,
    select_charts,
)
from vizreel.spec.loader import load_spec, parse_spec
from vizreel.spec.models import Spec

SHOWCASE = Path(__file__).parents[2] / "examples" / "showcase.yaml"


def spec_with_meta(meta: str) -> Spec:
    return parse_spec(
        f"version: 1\nmeta: {meta}\ncharts: [{{ id: a, type: stat, value: 1 }}]", "spec.yaml"
    )


@pytest.mark.parametrize(
    ("resolution", "size"),
    [("720p", (1280, 720)), ("1080p", (1920, 1080)), ("1440p", (2560, 1440)), ("4k", (3840, 2160))],
)
def test_final_quality_uses_spec_resolution(resolution: str, size: tuple[int, int]) -> None:
    spec = spec_with_meta(f"{{ resolution: {resolution}, fps: 30 }}")

    settings = frame_settings(spec, RenderOptions(quality="final"))

    assert (settings.width, settings.height, settings.fps) == (*size, 30)


def test_preview_quality_is_small_and_15_fps() -> None:
    spec = spec_with_meta("{ resolution: 4k, fps: 60 }")

    assert frame_settings(spec, RenderOptions(quality="preview")) == FrameSettings(
        854, 480, 15, "mov"
    )


def test_format_option_overrides_meta() -> None:
    spec = spec_with_meta("{ format: webm }")

    assert frame_settings(spec, RenderOptions()).format == "webm"
    assert frame_settings(spec, RenderOptions(format="mp4")).format == "mp4"


@pytest.mark.parametrize(
    ("output_format", "transparent"), [("mov", True), ("webm", True), ("mp4", False)]
)
def test_transparency_depends_on_format(output_format: str, transparent: bool) -> None:
    assert FrameSettings(1, 1, 30, output_format).transparent is transparent  # type: ignore[arg-type]


def test_final_output_paths_use_the_chart_id() -> None:
    options = RenderOptions(out_dir=Path("clips"), still=True)

    assert output_paths("offers", options, "mov") == (
        Path("clips/offers.mov"),
        Path("clips/offers.png"),
    )


def test_preview_output_paths_have_a_suffix() -> None:
    options = RenderOptions(out_dir=Path("clips"), quality="preview", still=True)

    assert output_paths("offers", options, "webm") == (
        Path("clips/offers.preview.webm"),
        Path("clips/offers.preview.png"),
    )


def test_no_still_path_without_still() -> None:
    assert output_paths("offers", RenderOptions(), "mp4") == (Path("out/offers.mp4"), None)


def test_select_all_charts_in_spec_order() -> None:
    spec = load_spec(SHOWCASE)

    assert [chart.id for chart in select_charts(spec, ())] == [
        "peak-valuation",
        "valuation",
        "offers",
        "final-years",
    ]


def test_select_only_keeps_spec_order() -> None:
    spec = load_spec(SHOWCASE)

    selected = select_charts(spec, ("final-years", "peak-valuation"))

    assert [chart.id for chart in selected] == ["peak-valuation", "final-years"]


def test_select_unknown_id_lists_ids() -> None:
    spec = load_spec(SHOWCASE)

    with pytest.raises(
        RenderError,
        match="no chart with id 'nope'. Ids in the spec: peak-valuation, valuation, offers, "
        "final-years",
    ):
        select_charts(spec, ("nope",))
