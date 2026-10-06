from pathlib import Path

import pytest
import yaml
from PIL import Image

from vizreel.errors import ThemeError
from vizreel.render.layout import Box
from vizreel.render.texture import corner_inset, cover_size, margin_center, ruled_rows
from vizreel.themes.check import average_color, check_theme
from vizreel.themes.loader import BUILTIN_DIR, load_theme, theme_input_files


def write_theme(path: Path, texture: object) -> Path:
    data = yaml.safe_load((BUILTIN_DIR / "light.yaml").read_text(encoding="utf-8"))
    data["texture"] = texture
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def theme_errors(path: Path) -> list[str]:
    with pytest.raises(ThemeError) as caught:
        load_theme(str(path), path.parent)
    return [str(issue) for issue in caught.value.issues]


def test_ruled_lines_are_spaced_evenly_inside_the_box() -> None:
    assert ruled_rows(10.0, 0.0, 3.0) == [7.0, 4.0, 1.0]
    assert ruled_rows(0, 10, 2.5) == [2.5, 5.0, 7.5]
    assert ruled_rows(9.0, 0.0, 3.0) == [6.0, 3.0]


def test_a_line_near_a_rounded_corner_is_shortened_to_stay_inside_it() -> None:
    assert corner_inset(5.0, 2.0) == 0.0
    assert corner_inset(2.0, 2.0) == 0.0
    assert corner_inset(0.0, 2.0) == pytest.approx(2.0)
    assert corner_inset(1.0, 2.0) == pytest.approx(2 - 3**0.5)
    assert corner_inset(0.5, 0.0) == 0.0


def test_the_margin_sits_halfway_into_the_space_left_of_the_content() -> None:
    frame = Box(0.0, 0.0, 16.0, 9.0)
    assert margin_center(frame, Box(2.0, 1.0, 14.0, 8.0), 1.0) == 1.5
    assert margin_center(frame, Box(0.4, 1.0, 14.0, 8.0), 1.0) == pytest.approx(0.2)


def test_a_picture_covers_a_box_keeping_its_proportions() -> None:
    assert cover_size(100, 50, 300, 300) == (600, 300)
    assert cover_size(100, 100, 300, 120) == (300, 300)


def test_a_theme_takes_ruled_lines_or_a_picture(tmp_path: Path) -> None:
    Image.new("RGB", (8, 8), "#CBAD7A").save(tmp_path / "paper.png")
    ruled = {"ruled": {"spacing": 54, "color": "#BCD0C2", "margin": "#B8322A"}}

    theme = load_theme(str(write_theme(tmp_path / "a.yaml", ruled)), tmp_path)
    picture = load_theme(
        str(write_theme(tmp_path / "b.yaml", {"image": {"file": "paper.png"}})), Path("x")
    )

    assert theme.texture is not None and theme.texture.ruled is not None
    assert (theme.texture.ruled.width, theme.texture.ruled.margin) == (2, "#B8322A")
    assert picture.texture is not None and picture.texture.image is not None
    assert picture.texture.image.fit == "cover"
    assert theme_input_files(picture) == [(tmp_path / "paper.png").resolve()]


def test_a_texture_needs_exactly_one_kind_and_lines_a_readable_spacing(tmp_path: Path) -> None:
    both = {"ruled": {"spacing": 54, "color": "#BCD0C2"}, "image": {"file": "p.png"}}

    assert theme_errors(write_theme(tmp_path / "a.yaml", {})) == [
        "texture: give one of ruled or image"
    ]
    assert theme_errors(write_theme(tmp_path / "b.yaml", both)) == [
        "texture: give one of ruled or image"
    ]
    assert theme_errors(
        write_theme(tmp_path / "c.yaml", {"ruled": {"spacing": 8, "color": "#BCD0C2"}})
    ) == ["texture.ruled.spacing: must be at least 16, got 8"]


def test_a_texture_picture_that_cannot_be_used_names_the_file(tmp_path: Path) -> None:
    (tmp_path / "broken.png").write_text("not a picture")

    assert theme_errors(write_theme(tmp_path / "a.yaml", {"image": {"file": "paper.gif"}})) == [
        "texture.image.file: paper.gif is not a PNG or JPEG file"
    ]
    assert theme_errors(write_theme(tmp_path / "b.yaml", {"image": {"file": "gone.png"}})) == [
        f"texture.image.file: gone.png was not found in {tmp_path}"
    ]
    assert theme_errors(write_theme(tmp_path / "c.yaml", {"image": {"file": "broken.png"}})) == [
        "texture.image.file: broken.png cannot be read as a picture"
    ]


def test_text_is_checked_against_the_pictures_average_color(tmp_path: Path) -> None:
    picture = Image.new("RGB", (2, 1))
    picture.putpixel((0, 0), (0, 0, 0))
    picture.putpixel((1, 0), (255, 255, 255))
    picture.save(tmp_path / "half.png")
    theme = load_theme(
        str(write_theme(tmp_path / "t.yaml", {"image": {"file": "half.png"}})), tmp_path
    )

    assert average_color(str(tmp_path / "half.png")) in ("#7F7F7F", "#808080")
    on_picture = [r for r in check_theme(theme) if r.description.endswith("on texture.image")]
    assert [r.description for r in on_picture][:2] == [
        "colors.text on texture.image",
        "colors.muted on texture.image",
    ]
