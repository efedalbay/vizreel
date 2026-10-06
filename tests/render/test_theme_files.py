"""Themes that bring their own files: fonts, and textures behind the chart."""

from pathlib import Path

import av
import numpy as np
import pytest
import yaml

from vizreel.render.engine import RenderOptions, render_spec
from vizreel.themes.loader import BUILTIN_DIR

FIXTURES = Path(__file__).parents[1] / "fixtures"
PLEX_MONO = Path(__file__).parents[2] / "examples" / "themes" / "fonts" / "IBMPlexMono-Regular.ttf"
SPEC = """\
version: 1
meta: {{ theme: {theme} }}
charts:
  - id: offers
    type: bar
    title: Offers Northwind received
    bars:
      - {{ label: Contoso, value: 311000000 }}
      - {{ label: Fabrikam, value: 375000000 }}
    number: {{ prefix: "$", compact: true }}
    highlight: {{ label: Fabrikam }}
    source: "Source: example data"
"""

pytestmark = pytest.mark.render


def theme_data() -> dict[str, object]:
    data: dict[str, object] = yaml.safe_load(
        (BUILTIN_DIR / "default.yaml").read_text(encoding="utf-8")
    )
    return data


def still(path: Path) -> np.ndarray:
    with av.open(str(path)) as container:
        return next(container.decode(video=0)).to_ndarray(format="rgb24").astype(int)


def render_still(spec_dir: Path, theme: str, out: Path, aspect: str = "16:9") -> np.ndarray:
    (spec_dir / "spec.yaml").write_text(SPEC.format(theme=theme), encoding="utf-8")
    [result] = render_spec(
        spec_dir / "spec.yaml",
        RenderOptions(out_dir=out, quality="preview", still=True, aspect=aspect),  # type: ignore[arg-type]
        reraise=True,
    )
    assert result.error is None and result.still is not None
    return still(result.still)


def test_a_theme_brings_its_font_file_from_its_own_folder(tmp_path: Path) -> None:
    brand = tmp_path / "brand"
    (brand / "fonts").mkdir(parents=True)
    (brand / "fonts" / "mono.ttf").write_bytes(PLEX_MONO.read_bytes())
    data = theme_data()
    data["fonts"] = {
        "heading": {"file": "fonts/mono.ttf"},
        "body": {"file": "fonts/mono.ttf"},
        "numbers": {"file": "fonts/mono.ttf"},
    }
    (brand / "mono.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()

    with_file = render_still(project, "../brand/mono.yaml", tmp_path / "a")
    with_inter = render_still(project, "default", tmp_path / "b")

    # Same layout and colors, other letter shapes: the text differs, the panel does not.
    different = np.any(np.abs(with_file - with_inter) > 64, axis=2)
    assert different.sum() > 2000


def test_a_number_font_without_tabular_figures_is_warned_about(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from manim import Rectangle

    from vizreel.render import elements, fonts
    from vizreel.themes.loader import load_theme

    def proportional(content: str, *args: object, **kwargs: object) -> Rectangle:
        return Rectangle(width=0.5 if "1" in content else 1.0, height=1)

    theme = load_theme("default", tmp_path)
    assert fonts.tabular_figures_warning(theme) is None
    fonts._has_tabular_figures.cache_clear()
    monkeypatch.setattr(elements, "number_text", proportional)
    assert fonts.tabular_figures_warning(theme) == (
        'the number font "Inter" (theme fonts.numbers) has no tabular figures, so counting '
        "numbers will shift sideways; choose a font whose digits share one width"
    )
    fonts._has_tabular_figures.cache_clear()


LINES, MARGIN, PAPER, TEXT = "#9CB8A6", "#B8322A", "#E8E0CC", "#1F2A24"


def textured_theme(folder: Path, texture: dict[str, object]) -> str:
    data = theme_data()
    colors = data["colors"]
    assert isinstance(colors, dict)
    colors.update(background=PAPER, surface=PAPER, text=TEXT)
    data["texture"] = texture
    data["motion"] = {**data["motion"], "exit": "fade"}  # type: ignore[dict-item]
    (folder / "paper.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    return "paper.yaml"


def rgba(path: Path) -> np.ndarray:
    from PIL import Image

    with Image.open(path) as picture:
        return np.asarray(picture.convert("RGBA")).astype(int)


def near(pixels: np.ndarray, hex_color: str, tolerance: int = 12) -> np.ndarray:
    target = [int(hex_color[index : index + 2], 16) for index in (1, 3, 5)]
    return np.all(np.abs(pixels[..., :3] - target) <= tolerance, axis=-1)


@pytest.mark.parametrize("aspect", ["16:9", "9:16", "1:1"])
def test_ruled_lines_fill_the_panel_and_leave_with_it(tmp_path: Path, aspect: str) -> None:
    texture = {"ruled": {"spacing": 40, "color": LINES, "width": 4, "margin": MARGIN}}
    theme = textured_theme(tmp_path, texture)
    (tmp_path / "spec.yaml").write_text(SPEC.format(theme=theme), encoding="utf-8")

    [result] = render_spec(
        tmp_path / "spec.yaml",
        RenderOptions(out_dir=tmp_path, quality="preview", still=True, aspect=aspect),  # type: ignore[arg-type]
        reraise=True,
    )

    assert result.still is not None and result.video is not None
    frame = rgba(result.still)
    opaque = frame[..., 3] == 255
    lines = near(frame, LINES) & opaque
    # Rows of lines across the panel, a red margin down its side, text on top.
    rows = np.nonzero(lines.sum(axis=1) > frame.shape[1] * 0.3)[0]
    assert len(np.unique(rows // 4)) >= 4
    assert (near(frame, MARGIN) & opaque).sum() > 40
    assert (near(frame, TEXT, 30) & opaque).sum() > 200
    # Nothing outside the panel: the frame's corners stay transparent.
    assert frame[0, 0, 3] == 0 and frame[-1, -1, 3] == 0
    with av.open(str(result.video)) as container:
        last = list(container.decode(video=0))[-1].to_ndarray(format="rgba")
    assert last[..., 3].max() == 0


def test_a_picture_fills_the_panel_inside_its_round_corners(tmp_path: Path) -> None:
    from PIL import Image

    Image.new("RGB", (32, 32), "#CBAD7A").save(tmp_path / "manila.png")
    theme = textured_theme(tmp_path, {"image": {"file": "manila.png", "fit": "tile"}})

    frame = rgba_still(tmp_path, theme)

    panel = np.nonzero(frame[..., 3] == 255)
    top, left = panel[0].min(), panel[1].min()
    assert near(frame[top + 20 : top + 30, left + 20 : left + 30], "#CBAD7A", 6).all()
    # The panel's corner is cut round: its very corner pixel is not covered.
    assert frame[top, left, 3] < 255


def test_an_opaque_clip_has_the_texture_over_its_whole_frame(tmp_path: Path) -> None:
    theme = textured_theme(tmp_path, {"ruled": {"spacing": 40, "color": LINES, "width": 4}})
    (tmp_path / "spec.yaml").write_text(SPEC.format(theme=theme), encoding="utf-8")

    [result] = render_spec(
        tmp_path / "spec.yaml",
        RenderOptions(out_dir=tmp_path, quality="preview", still=True, format="mp4"),
        reraise=True,
    )

    assert result.still is not None
    frame = rgba(result.still)
    # The lines reach the very edges of the frame, outside any panel.
    edge = near(frame[:, :3], LINES)
    assert edge.all(axis=1).sum() >= 4
    assert near(frame[:, :3], PAPER).all(axis=1).sum() > frame.shape[0] / 2


def rgba_still(folder: Path, theme: str) -> np.ndarray:
    (folder / "spec.yaml").write_text(SPEC.format(theme=theme), encoding="utf-8")
    [result] = render_spec(
        folder / "spec.yaml",
        RenderOptions(out_dir=folder, quality="preview", still=True),
        reraise=True,
    )
    assert result.still is not None
    return rgba(result.still)
