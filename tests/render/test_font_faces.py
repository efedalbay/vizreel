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
