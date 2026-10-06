"""Themes that bring their own files: fonts, and textures behind the chart."""

from pathlib import Path

import av
import numpy as np
import pytest
import yaml

from vizreel.render.engine import RenderOptions, render_spec
from vizreel.themes.loader import BUILTIN_DIR

FIXTURES = Path(__file__).parents[1] / "fixtures"
PLEX_MONO = FIXTURES / "fonts" / "IBMPlexMono-Regular.ttf"
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
    monkeypatch.setattr(elements, "number_text", proportional)
    assert fonts.tabular_figures_warning(theme) == (
        'the number font "Inter" (theme fonts.numbers) has no tabular figures, so counting '
        "numbers will shift sideways; choose a font whose digits share one width"
    )
