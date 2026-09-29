"""The theme's logo: every chart type shows it inside the safe area, and it leaves with the clip."""

from pathlib import Path

import av
import numpy as np
import pytest
import yaml
from PIL import Image

from vizreel.render.engine import RenderOptions, render_spec
from vizreel.render.layout import SAFE_MARGINS
from vizreel.themes.loader import BUILTIN_DIR

SHOWCASE = Path(__file__).parents[2] / "examples" / "showcase.yaml"
MAGENTA = (255, 0, 255)

pytestmark = pytest.mark.render


def rgba(path: Path, last: bool = False) -> np.ndarray:
    with av.open(str(path)) as container:
        frames = [frame.to_ndarray(format="rgba") for frame in container.decode(video=0)]
    return frames[-1] if last else frames[0]


@pytest.mark.parametrize("aspect", ["16:9", "9:16"])
def test_every_chart_type_shows_the_theme_logo_in_the_safe_area(
    tmp_path: Path, aspect: str
) -> None:
    Image.new("RGBA", (60, 60), (*MAGENTA, 255)).save(tmp_path / "logo.png")
    theme = yaml.safe_load((BUILTIN_DIR / "default.yaml").read_text(encoding="utf-8"))
    theme["logo"] = {"file": "logo.png", "height": 48}
    (tmp_path / "brand.yaml").write_text(yaml.safe_dump(theme), encoding="utf-8")
    spec = yaml.safe_load(SHOWCASE.read_text(encoding="utf-8"))
    spec["meta"]["theme"] = str(tmp_path / "brand.yaml")
    spec["meta"]["motion"] = {"exit": "fade"}
    (tmp_path / "spec.yaml").write_text(yaml.safe_dump(spec), encoding="utf-8")

    results = render_spec(
        tmp_path / "spec.yaml",
        RenderOptions(out_dir=tmp_path / "out", quality="preview", still=True, aspect=aspect),  # type: ignore[arg-type]
        reraise=True,
    )

    margins = SAFE_MARGINS[aspect]
    assert len(results) == len(spec["charts"])
    for result in results:
        assert result.error is None and result.still is not None and result.video is not None
        still = rgba(result.still)
        height, width = still.shape[:2]
        rows, columns = np.nonzero(
            np.all(np.abs(still[:, :, :3].astype(int) - MAGENTA) <= 4, axis=2)
        )
        assert rows.size > 100, result.chart_id
        assert columns.min() >= width * margins.left - 1, result.chart_id
        assert columns.max() <= width * (1 - margins.right) + 1, result.chart_id
        assert rows.min() >= height * margins.top - 1, result.chart_id
        assert rows.max() <= height * (1 - margins.bottom) + 1, result.chart_id
        assert rgba(result.video, last=True)[:, :, 3].max() == 0, result.chart_id
