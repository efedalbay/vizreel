"""Races from a CSV file of 24 periods, in every frame shape."""

from pathlib import Path

import av
import numpy as np
import pytest

from vizreel.render.engine import RenderOptions, render_spec

DATA = Path(__file__).parents[2] / "examples" / "data.yaml"
PREVIEW_FPS = 15

pytestmark = pytest.mark.render


def frames_rgba(path: Path) -> list[np.ndarray]:
    with av.open(str(path)) as container:
        return [frame.to_ndarray(format="rgba") for frame in container.decode(video=0)]


@pytest.mark.parametrize("aspect", ["16:9", "9:16", "1:1"])
@pytest.mark.parametrize("chart_id", ["market-race", "catching-up", "growth-race"])
def test_a_race_of_24_periods_renders_in_every_shape(
    tmp_path: Path, chart_id: str, aspect: str
) -> None:
    [result] = render_spec(
        DATA,
        RenderOptions(out_dir=tmp_path, only=(chart_id,), quality="preview", aspect=aspect),  # type: ignore[arg-type]
        reraise=True,
    )
    assert result.video is not None
    frames = frames_rgba(result.video)

    assert len(frames) == 15 * PREVIEW_FPS
    # The race moves on every frame until its hold, which is still.
    hold = int(1.5 * PREVIEW_FPS)
    for frame in frames[-hold:]:
        assert np.array_equal(frame, frames[-1])
    race = frames[int(1.1 * PREVIEW_FPS) : -hold - PREVIEW_FPS]
    assert all(
        not np.array_equal(earlier, later) for earlier, later in zip(race, race[1:], strict=False)
    )


def test_a_line_race_with_more_lines_than_colors_asks_to_follow_one(tmp_path: Path) -> None:
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        "version: 1\ncharts:\n  - id: r\n    type: line-race\n    periods: [a, b]\n    series:\n"
        + "".join(f"      - {{ name: S{index}, values: [1, {index}] }}\n" for index in range(4)),
        encoding="utf-8",
    )

    [result] = render_spec(spec, RenderOptions(out_dir=tmp_path, quality="preview"))

    assert result.error == (
        "4 lines need as many colors and the theme has 3; follow one with highlight, which "
        "mutes the others"
    )


def test_a_race_draws_series_in_their_brand_colors(tmp_path: Path) -> None:
    from vizreel.themes.loader import load_theme

    spec = Path(__file__).parents[2] / "examples" / "brand.yaml"
    theme = load_theme("themes/example-brand.yaml", spec.parent)
    [result] = render_spec(
        spec,
        RenderOptions(out_dir=tmp_path, only=("brand-race",), quality="preview", still=True),
        reraise=True,
    )
    assert result.still is not None
    with av.open(str(result.still)) as container:
        rgb = next(container.decode(video=0)).to_ndarray(format="rgb24").astype(int)

    for color in theme.colors.brand.values():
        target = [int(color[index : index + 2], 16) for index in (1, 3, 5)]
        assert np.all(np.abs(rgb - target) <= 4, axis=2).sum() > 500


def test_a_race_shows_images_and_they_leave_with_it(tmp_path: Path) -> None:
    from PIL import Image

    Image.new("RGBA", (40, 20), (255, 0, 255, 255)).save(tmp_path / "logo.png")
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        "version: 1\ncharts:\n  - id: r\n    type: bar-race\n    periods: [a, b, c]\n"
        "    series:\n      - { name: A, values: [1, 2, 3] }\n"
        "      - { name: B, values: [3, 2, 1] }\n"
        "    images: { A: logo.png }\n    duration: 5\n    motion: { exit: fade }\n",
        encoding="utf-8",
    )

    [result] = render_spec(
        spec, RenderOptions(out_dir=tmp_path, quality="preview", still=True), reraise=True
    )

    assert result.video is not None and result.still is not None
    with av.open(str(result.still)) as container:
        still = next(container.decode(video=0)).to_ndarray(format="rgb24").astype(int)
    magenta = np.all(np.abs(still - [255, 0, 255]) <= 4, axis=2)
    assert magenta.sum() > 50
    rows, columns = np.nonzero(magenta)
    assert columns.max() - columns.min() > rows.max() - rows.min()
    assert frames_rgba(result.video)[-1][:, :, 3].max() == 0
