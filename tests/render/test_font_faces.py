"""Font files are drawn with their own face, whatever other files of their family are loaded."""

from pathlib import Path

import pytest
import yaml

from vizreel.themes.loader import BUILTIN_DIR, load_theme

FONTS = Path(__file__).parents[1] / "fixtures" / "fonts"
SAMPLE = "HAMBURG"

pytestmark = pytest.mark.render


def theme_with(folder: Path, name: str, files: dict[str, str]) -> Path:
    data = yaml.safe_load((BUILTIN_DIR / "default.yaml").read_text(encoding="utf-8"))
    data["fonts"] = {role: {"file": str(FONTS / file)} for role, file in files.items()}
    path = folder / f"{name}.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def ink(mobject: object) -> float:
    """The area the letters cover, from their outlines: a bolder face covers more."""
    import numpy as np

    total = 0.0
    for part in mobject.family_members_with_points():  # type: ignore[attr-defined]
        signed = 0.0
        for path in part.get_subpaths():
            anchors = np.asarray(path)[::4, :2]
            x, y = anchors[:, 0], anchors[:, 1]
            signed += 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
        total += abs(signed)
    return total


def test_each_weight_and_width_of_a_family_draws_its_own_file(tmp_path: Path) -> None:
    from vizreel.render import elements
    from vizreel.render.fonts import check_theme_fonts

    # Every file of both families is loaded before any text is drawn.
    first = check_theme_fonts(
        load_theme(
            str(
                theme_with(
                    tmp_path,
                    "a",
                    {
                        "heading": "ArchivoCondensed-Bold.ttf",
                        "body": "JetBrainsMono-Regular.ttf",
                        "numbers": "JetBrainsMono-Bold.ttf",
                    },
                )
            ),
            tmp_path,
        )
    )
    second = check_theme_fonts(
        load_theme(
            str(
                theme_with(
                    tmp_path,
                    "b",
                    {
                        "heading": "ArchivoCondensed-Black.ttf",
                        "body": "ArchivoCondensed-ExtraBold.ttf",
                        "numbers": "JetBrainsMono-ExtraBold.ttf",
                    },
                )
            ),
            tmp_path,
        )
    )
    archivo = [first.fonts.heading, second.fonts.body, second.fonts.heading]
    jetbrains = [first.fonts.body, first.fonts.numbers, second.fonts.numbers]

    assert [style.weight for style in archivo] == ["bold", "extrabold", "black"]
    assert {style.stretch for style in archivo} == {"condensed"}
    assert [style.weight for style in jetbrains] == ["regular", "semibold", "extrabold"]

    def drawn(style: object) -> object:
        return elements.text(SAMPLE, style, 100, "#000000")  # type: ignore[arg-type]

    # Each heavier file covers more: none falls back to a lighter file of its family.
    for family in (archivo, jetbrains):
        areas = [ink(drawn(style)) for style in family]
        assert areas == sorted(areas) and len({round(area, 3) for area in areas}) == 3, areas
    # Archivo is drawn condensed, narrower than the same text in the wide bundled Inter.
    inter = load_theme("default", tmp_path).fonts.heading
    assert drawn(archivo[0]).width < drawn(inter).width * 0.85  # type: ignore[attr-defined]
    # JetBrains Mono is drawn in its own monospaced letters: an I is as wide as an M.
    for style in jetbrains:
        narrow = elements.text("0IIIIII0", style, 100, "#000000").width
        wide = elements.text("0MMMMMM0", style, 100, "#000000").width
        assert abs(narrow - wide) < 0.01


def test_a_counting_number_in_old_style_figures_does_not_jump(tmp_path: Path) -> None:
    import json

    import av
    import numpy as np

    from vizreel.render.engine import RenderOptions, render_spec

    data = yaml.safe_load((BUILTIN_DIR / "default.yaml").read_text(encoding="utf-8"))
    data["fonts"]["numbers"] = {"file": str(FONTS / "LibreCaslonText-Bold.ttf")}
    (tmp_path / "caslon.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    (tmp_path / "spec.yaml").write_text(
        "version: 1\nmeta: { theme: caslon.yaml, cues: true }\ncharts:\n"
        "  - { id: v, type: stat, value: 2250000000, number: { prefix: '$', compact: true },"
        " duration: 6 }\n",
        encoding="utf-8",
    )
    text = load_theme("caslon.yaml", tmp_path).colors.text

    [result] = render_spec(
        tmp_path / "spec.yaml", RenderOptions(out_dir=tmp_path, quality="preview"), reraise=True
    )

    assert result.video is not None and result.cues is not None
    with av.open(str(result.video)) as container:
        clip = [frame.to_ndarray(format="rgb24").astype(int) for frame in container.decode(video=0)]
    [reveal] = [
        cue
        for cue in json.loads(result.cues.read_text(encoding="utf-8"))["cues"]
        if cue["name"] == "reveal"
    ]
    target = [int(text[index : index + 2], 16) for index in (1, 3, 5)]

    def ink(frame: np.ndarray) -> np.ndarray:
        return np.all(np.abs(frame - target) <= 60, axis=2)

    final = ink(clip[-1])
    columns = np.nonzero(final.any(axis=0))[0]
    left, right = columns.min(), columns.max()
    edge = max(4, (right - left) // 12)

    def rows(frame: np.ndarray, start: int, stop: int) -> tuple[int, int]:
        found = np.nonzero(ink(frame)[:, start:stop].any(axis=1))[0]
        return int(found.min()), int(found.max())

    # The "$" at the left and the "B" at the right stay where they are while the digits count.
    counting = clip[reveal["start_frame"] + 2 : reveal["end_frame"]]
    assert len({rows(frame, left, left + edge) for frame in counting}) == 1
    assert len({rows(frame, right - edge, right + 1) for frame in counting}) == 1
