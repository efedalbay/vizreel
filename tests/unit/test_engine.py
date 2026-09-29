from fractions import Fraction
from pathlib import Path

import pytest

from vizreel.errors import RenderError, SpecError
from vizreel.render.engine import (
    FrameSettings,
    RenderOptions,
    exact_frame_rate,
    frame_settings,
    output_paths,
    select_charts,
)
from vizreel.spec.loader import load_spec, parse_spec
from vizreel.spec.models import FRAME_RATES, Spec

CHARTS = "charts: [{ id: a, type: stat, value: 1 }]"
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

    assert output_paths("offers", options, FrameSettings(1920, 1080, 60, "mov")) == (
        Path("clips/offers.mov"),
        Path("clips/offers.png"),
    )


def test_preview_output_paths_have_a_suffix() -> None:
    options = RenderOptions(out_dir=Path("clips"), quality="preview", still=True)

    assert output_paths("offers", options, FrameSettings(854, 480, 15, "webm")) == (
        Path("clips/offers.preview.webm"),
        Path("clips/offers.preview.png"),
    )


def test_no_still_path_without_still() -> None:
    assert output_paths("offers", RenderOptions(), FrameSettings(1920, 1080, 60, "mp4")) == (
        Path("out/offers.mp4"),
        None,
    )


def test_select_all_charts_in_spec_order() -> None:
    spec = load_spec(SHOWCASE)

    assert [chart.id for chart in select_charts(spec, ())] == [
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


def test_select_only_keeps_spec_order() -> None:
    spec = load_spec(SHOWCASE)

    selected = select_charts(spec, ("final-years", "peak-valuation"))

    assert [chart.id for chart in selected] == ["peak-valuation", "final-years"]


def test_select_unknown_id_lists_ids() -> None:
    spec = load_spec(SHOWCASE)

    with pytest.raises(
        RenderError,
        match="no chart with id 'nope'. Ids in the spec: peak-valuation, valuation, offers, "
        "final-years, headcount, profit, revenue-mix, region-growth, users, fundraiser, market, "
        "top-markets",
    ):
        select_charts(spec, ("nope",))


@pytest.mark.parametrize(
    ("resolution", "size"),
    [("720p", (720, 1280)), ("1080p", (1080, 1920)), ("1440p", (1440, 2560)), ("4k", (2160, 3840))],
)
def test_vertical_frames_swap_the_sides(resolution: str, size: tuple[int, int]) -> None:
    spec = spec_with_meta(f'{{ resolution: {resolution}, aspect: "9:16" }}')

    settings = frame_settings(spec, RenderOptions())

    assert (settings.width, settings.height, settings.aspect) == (*size, "9:16")


def test_vertical_preview_is_480_wide() -> None:
    spec = spec_with_meta('{ aspect: "9:16" }')

    assert frame_settings(spec, RenderOptions(quality="preview")) == FrameSettings(
        480, 854, 15, "mov", "9:16"
    )


def test_aspect_option_overrides_meta() -> None:
    spec = spec_with_meta('{ aspect: "9:16" }')

    assert frame_settings(spec, RenderOptions()).aspect == "9:16"
    assert frame_settings(spec, RenderOptions(aspect="16:9")).aspect == "16:9"
    assert frame_settings(spec_with_meta("{}"), RenderOptions(aspect="9:16")).aspect == "9:16"


def test_vertical_output_paths_have_a_suffix() -> None:
    vertical = FrameSettings(1080, 1920, 60, "mov", "9:16")

    assert output_paths("offers", RenderOptions(still=True), vertical) == (
        Path("out/offers.vertical.mov"),
        Path("out/offers.vertical.png"),
    )
    assert output_paths("offers", RenderOptions(quality="preview"), vertical) == (
        Path("out/offers.vertical.preview.mov"),
        None,
    )


@pytest.mark.parametrize(
    ("fps", "exact"),
    [
        (23.976, Fraction(24000, 1001)),
        (24, Fraction(24)),
        (25, Fraction(25)),
        (29.97, Fraction(30000, 1001)),
        (30, Fraction(30)),
        (50, Fraction(50)),
        (59.94, Fraction(60000, 1001)),
        (60, Fraction(60)),
    ],
)
def test_frame_rates_are_exact_ratios(fps: float, exact: Fraction) -> None:
    assert exact_frame_rate(fps) == exact


def test_every_frame_rate_is_accepted_and_others_are_not() -> None:
    for fps in FRAME_RATES:
        assert parse_spec(f"version: 1\nmeta: {{ fps: {fps} }}\n{CHARTS}", "s").meta.fps == fps
    with pytest.raises(SpecError) as caught:
        parse_spec(f"version: 1\nmeta: {{ fps: 45 }}\n{CHARTS}", "s")
    assert "45 is not a supported frame rate" in str(caught.value.issues[0])


def test_fps_option_overrides_meta_but_not_previews() -> None:
    spec = parse_spec(f"version: 1\nmeta: {{ fps: 29.97 }}\n{CHARTS}", "s")

    assert frame_settings(spec, RenderOptions()).fps == Fraction(30000, 1001)
    assert frame_settings(spec, RenderOptions(fps=25)).fps == 25
    assert frame_settings(spec, RenderOptions(fps=25, quality="preview")).fps == 15


def test_square_frames_have_equal_sides_and_a_suffix(tmp_path: Path) -> None:
    spec = spec_with_meta("{ resolution: 1080p }")
    settings = frame_settings(spec, RenderOptions(aspect="1:1"))

    video, _ = output_paths("sales", RenderOptions(out_dir=tmp_path), settings)

    assert (settings.width, settings.height) == (1080, 1080)
    assert video == tmp_path / "sales.square.mov"


@pytest.mark.parametrize(
    ("output_format", "name"),
    [("mov", "sales.mov"), ("prores", "sales.prores.mov"), ("png", "sales"), ("mp4", "sales.mp4")],
)
def test_output_paths_of_each_format(tmp_path: Path, output_format: str, name: str) -> None:
    spec = spec_with_meta(f"{{ format: {output_format} }}")
    settings = frame_settings(spec, RenderOptions())

    video, _ = output_paths("sales", RenderOptions(out_dir=tmp_path), settings)

    assert video == tmp_path / name
    assert settings.transparent is (output_format != "mp4")
