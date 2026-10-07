import struct
from pathlib import Path

import pytest
import yaml

from vizreel.errors import ThemeError
from vizreel.themes.fontfile import read_font_file
from vizreel.themes.loader import BUILTIN_DIR, load_theme

FONTS = Path(__file__).parents[1] / "fixtures" / "fonts"


def theme_errors(folder: Path, fonts: dict[str, dict[str, object]]) -> list[str]:
    data = yaml.safe_load((BUILTIN_DIR / "default.yaml").read_text(encoding="utf-8"))
    data["fonts"].update(fonts)
    (folder / "t.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ThemeError) as caught:
        load_theme("t.yaml", folder)
    return [str(issue) for issue in caught.value.issues]


def with_weight_class(source: Path, target: Path, weight_class: int) -> Path:
    """Copy a font file, giving the copy another weight class."""
    data = bytearray(source.read_bytes())
    (count,) = struct.unpack(">H", data[4:6])
    for index in range(count):
        tag, _, offset, _ = struct.unpack(">4sIII", data[12 + 16 * index : 28 + 16 * index])
        if tag == b"OS/2":
            data[offset + 4 : offset + 6] = struct.pack(">H", weight_class)
    target.write_bytes(bytes(data))
    return target


def test_a_font_file_says_its_family_weight_and_width() -> None:
    bold = read_font_file(FONTS / "ArchivoCondensed-Bold.ttf")
    extra = read_font_file(FONTS / "JetBrainsMono-ExtraBold.ttf")
    jetbrains_bold = read_font_file(FONTS / "JetBrainsMono-Bold.ttf")

    assert (bold.family, bold.weight, bold.stretch) == ("Archivo Condensed", "bold", "condensed")
    # A renderer may list the family without its width word.
    assert bold.names == ("Archivo Condensed", "Archivo")
    assert (extra.family, extra.style, extra.weight) == ("JetBrains Mono", "ExtraBold", "extrabold")
    # Weight class 558 is nearest semibold, and the file calls itself Bold: either name fits.
    assert jetbrains_bold.weight_class == 558
    assert jetbrains_bold.named_weights() == {"semibold", "bold"}


def test_a_file_that_is_not_a_font_cannot_be_read(tmp_path: Path) -> None:
    (tmp_path / "fake.ttf").write_bytes(b"not a font at all")

    with pytest.raises(ValueError):
        read_font_file(tmp_path / "fake.ttf")


def test_a_font_files_weight_and_width_are_read_from_it(tmp_path: Path) -> None:
    data = yaml.safe_load((BUILTIN_DIR / "default.yaml").read_text(encoding="utf-8"))
    data["fonts"] = {
        "heading": {"file": str(FONTS / "ArchivoCondensed-Black.ttf")},
        "body": {"file": str(FONTS / "JetBrainsMono-Regular.ttf")},
        "numbers": {"file": str(FONTS / "JetBrainsMono-Bold.ttf"), "weight": "bold"},
    }
    (tmp_path / "t.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")

    fonts = load_theme("t.yaml", tmp_path).fonts

    assert (fonts.heading.family, fonts.heading.weight, fonts.heading.stretch) == (
        "Archivo Condensed",
        "black",
        "condensed",
    )
    assert (fonts.body.weight, fonts.body.stretch) == ("regular", "normal")
    # Asked for as the renderer weighs it, so the Bold file is the one drawn.
    assert fonts.numbers.weight == "semibold"


def test_a_weight_or_width_the_file_does_not_have_is_an_error(tmp_path: Path) -> None:
    errors = theme_errors(
        tmp_path,
        {
            "heading": {"file": str(FONTS / "JetBrainsMono-ExtraBold.ttf"), "weight": "bold"},
            "body": {"file": str(FONTS / "ArchivoCondensed-Bold.ttf"), "stretch": "normal"},
        },
    )

    assert errors == [
        f"fonts.heading.weight: is bold but {FONTS / 'JetBrainsMono-ExtraBold.ttf'} is ExtraBold "
        "(weight 800), extrabold; leave out weight, which is read from the file",
        f"fonts.body.stretch: is normal but {FONTS / 'ArchivoCondensed-Bold.ttf'} is condensed; "
        "leave out stretch, which is read from the file",
    ]


def test_a_font_lighter_than_regular_is_an_error(tmp_path: Path) -> None:
    light = with_weight_class(FONTS / "JetBrainsMono-Regular.ttf", tmp_path / "light.ttf", 300)

    errors = theme_errors(tmp_path, {"heading": {"file": light.name}})

    assert errors == [
        "fonts.heading.file: light.ttf is Regular (weight 300); a theme draws weights from "
        "regular (400) to black (900)"
    ]


def test_two_files_the_renderer_draws_as_one_face_are_an_error(tmp_path: Path) -> None:
    (tmp_path / "copy.ttf").write_bytes((FONTS / "JetBrainsMono-Bold.ttf").read_bytes())

    errors = theme_errors(
        tmp_path,
        {
            "heading": {"file": str(FONTS / "JetBrainsMono-Bold.ttf")},
            "body": {"file": "copy.ttf"},
        },
    )

    assert errors == [
        "fonts.body.file: copy.ttf and the file of fonts.heading are both JetBrains Mono "
        "semibold to the text renderer, so one of them could not be drawn; use one of them for "
        "both roles"
    ]


def test_new_weights_and_widths_are_accepted_for_installed_fonts(tmp_path: Path) -> None:
    data = yaml.safe_load((BUILTIN_DIR / "default.yaml").read_text(encoding="utf-8"))
    data["fonts"]["heading"] = {"family": "Bahnschrift", "weight": "black", "stretch": "condensed"}
    (tmp_path / "t.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")

    heading = load_theme("t.yaml", tmp_path).fonts.heading

    assert (heading.weight, heading.stretch) == ("black", "condensed")
