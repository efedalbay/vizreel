"""Find a theme by built-in name or path and validate it."""

from pathlib import Path
from typing import Any

from pydantic import ValidationError
from pydantic_core import ErrorDetails

from vizreel.errors import InputIssue, ThemeError
from vizreel.themes.fontfile import LIGHTEST_CLASS, FontFile, read_font_file
from vizreel.themes.models import Theme
from vizreel.validation import format_location, issue_from_error, read_yaml_mapping, show

BUILTIN_DIR = Path(__file__).with_name("builtin")
_KIND = "theme"
_REQUIRED = ("colors", "fonts", "sizes", "motion", "background_panel")
_REFERENCE = "docs/THEMES.md"


def builtin_theme_names() -> list[str]:
    """Return the names of the built-in themes, sorted."""
    return sorted(path.stem for path in BUILTIN_DIR.glob("*.yaml"))


def describe_builtin_themes() -> list[tuple[str, str | None]]:
    """Return the name and description of each built-in theme, sorted by name."""
    return [(name, load_theme(name, BUILTIN_DIR).description) for name in builtin_theme_names()]


def resolve_theme_path(ref: str, base_dir: Path) -> Path:
    """Find the file of a theme.

    Args:
        ref: `meta.theme` from the spec: a built-in name or a path to a YAML file.
        base_dir: Folder that relative paths start from: the spec's folder, or the
            current folder for `vizreel theme check`.

    Raises:
        ThemeError: No built-in theme has that name and no file exists at that path.
    """
    if ref in builtin_theme_names():
        return BUILTIN_DIR / f"{ref}.yaml"
    path = Path(ref)
    if not path.is_absolute():
        path = base_dir / path
    if path.is_file():
        return path
    raise ThemeError(
        str(path),
        [
            InputIssue(
                "",
                f'theme "{ref}" not found. Built-in themes: {", ".join(builtin_theme_names())}. '
                "A custom theme is a path to a YAML file; "
                f"a relative path is looked up in {base_dir}",
            )
        ],
    )


def load_theme(ref: str, base_dir: Path) -> Theme:
    """Resolve and validate a theme.

    Args:
        ref: `meta.theme` from the spec: a built-in name or a path to a YAML file.
        base_dir: Folder that relative paths start from: the spec's folder, or the
            current folder for `vizreel theme check`.

    Raises:
        ThemeError: The theme cannot be found, read or validated.
    """
    path = resolve_theme_path(ref, base_dir)
    data = read_yaml_mapping(path, ThemeError, _KIND, _REQUIRED)
    font_issues = _read_font_files(data, path)
    if font_issues:
        raise ThemeError(str(path), font_issues)
    try:
        theme = Theme.model_validate(data)
    except ValidationError as exc:
        raise ThemeError(str(path), [_issue_from_error(error) for error in exc.errors()]) from None
    return _with_texture_path(_with_logo_path(theme, path), path)


LOGO_SUFFIXES = (".png", ".jpg", ".jpeg", ".svg")
"""The image files a theme logo can be."""


def _with_logo_path(theme: Theme, path: Path) -> Theme:
    """Return the theme with its logo file as a full path, checking the file.

    Raises:
        ThemeError: The logo file is missing or not a PNG, JPEG or SVG file.
    """
    if theme.logo is None:
        return theme
    reference = theme.logo.file
    logo = path.parent / reference
    if logo.suffix.lower() not in LOGO_SUFFIXES:
        message = f"{reference} is not a PNG, JPEG or SVG file"
    elif not logo.is_file():
        message = f"{reference} was not found in {logo.parent}"
    else:
        resolved = theme.logo.model_copy(update={"file": str(logo.resolve())})
        return theme.model_copy(update={"logo": resolved})
    raise ThemeError(str(path), [InputIssue("logo.file", message)])


def theme_input_files(theme: Theme) -> list[Path]:
    """Return the files a loaded theme reads besides itself: its logo and its font files."""
    fonts = theme.fonts
    styles = (fonts.heading, fonts.body, fonts.numbers)
    files = [theme.logo.file] if theme.logo else []
    files += [style.file for style in styles if style.file]
    if theme.texture and theme.texture.image:
        files.append(theme.texture.image.file)
    return [Path(file) for file in dict.fromkeys(files)]


FONT_SUFFIXES = (".ttf", ".otf")
"""The font files a theme can bring."""
FONT_ROLES = ("heading", "body", "numbers")


def _read_font_files(data: dict[str, Any], path: Path) -> list[InputIssue]:
    """Give each font with a `file` the family, weight and width that file holds.

    The data is changed in place, before validation, so the theme model always has them and
    the text renderer is asked for exactly the file's face: another weight or width would
    draw another file of the family, or a fallback font.

    Returns:
        What is wrong with the font files: one missing, not a TTF or OTF file, unreadable,
        lighter than regular, named otherwise than the theme names it, or drawn as the same
        face as another file of its family.
    """
    fonts = data.get("fonts")
    if not isinstance(fonts, dict):
        return []
    issues: list[InputIssue] = []
    faces: dict[tuple[str, str, str], tuple[str, str]] = {}
    for role in FONT_ROLES:
        style = fonts.get(role)
        reference = style.get("file") if isinstance(style, dict) else None
        if not isinstance(style, dict) or not isinstance(reference, str) or not reference:
            continue
        font = path.parent / reference
        loc = f"fonts.{role}"
        if font.suffix.lower() not in FONT_SUFFIXES:
            issues.append(InputIssue(f"{loc}.file", f"{reference} is not a TTF or OTF font file"))
            continue
        if not font.is_file():
            issues.append(InputIssue(f"{loc}.file", f"{reference} was not found in {font.parent}"))
            continue
        try:
            info = read_font_file(font)
        except (OSError, ValueError):
            issues.append(InputIssue(f"{loc}.file", f"{reference} cannot be read as a font"))
            continue
        problem = _font_file_problem(style, reference, info)
        if problem is not None:
            issues.append(InputIssue(f"{loc}.{problem[0]}", problem[1]))
            continue
        face = (info.family, info.weight, info.stretch)
        resolved = str(font.resolve())
        if face in faces and faces[face][1] != resolved:
            other_role, _ = faces[face]
            issues.append(
                InputIssue(
                    f"{loc}.file",
                    f"{reference} and the file of fonts.{other_role} are both {info.family} "
                    f"{info.weight}{_width_words(info.stretch)} to the text renderer, so one of "
                    "them could not be drawn; use one of them for both roles",
                )
            )
            continue
        faces[face] = (role, resolved)
        fonts[role] = {
            **style,
            "family": info.family,
            "weight": info.weight,
            "stretch": info.stretch,
            "file": resolved,
        }
    return issues


def _font_file_problem(
    style: dict[str, Any], reference: str, info: FontFile
) -> tuple[str, str] | None:
    """What is wrong with a font file for its role: the field and the message, or None."""
    if info.weight_class < LIGHTEST_CLASS:
        return (
            "file",
            f"{reference} is {info.style or 'a light font'} (weight {info.weight_class}); a theme "
            "draws weights from regular (400) to black (900)",
        )
    given = style.get("family")
    if given is not None and given not in info.names:
        return (
            "family",
            f'is "{given}" but {reference} holds the family "{info.family}"; leave out family '
            "or write it as the file names it",
        )
    weight = style.get("weight")
    if weight is not None and weight not in info.named_weights():
        return (
            "weight",
            f"is {weight} but {reference} is {info.style} (weight {info.weight_class}), "
            f"{info.weight}; leave out weight, which is read from the file",
        )
    stretch = style.get("stretch")
    if stretch is not None and stretch != info.stretch:
        return (
            "stretch",
            f"is {stretch} but {reference} is {info.stretch}; leave out stretch, which is read "
            "from the file",
        )
    return None


def _width_words(stretch: str) -> str:
    return "" if stretch == "normal" else f" {stretch}"


TEXTURE_SUFFIXES = (".png", ".jpg", ".jpeg")
"""The picture files a theme texture can be."""


def _with_texture_path(theme: Theme, path: Path) -> Theme:
    """Return the theme with its texture picture as a full path, checking the file.

    Raises:
        ThemeError: The picture is missing, not a PNG or JPEG file, or cannot be read.
    """
    texture = theme.texture
    if texture is None or texture.image is None:
        return theme
    reference = texture.image.file
    picture = path.parent / reference
    if picture.suffix.lower() not in TEXTURE_SUFFIXES:
        message = f"{reference} is not a PNG or JPEG file"
    elif not picture.is_file():
        message = f"{reference} was not found in {picture.parent}"
    elif not _readable_picture(picture):
        message = f"{reference} cannot be read as a picture"
    else:
        image = texture.image.model_copy(update={"file": str(picture.resolve())})
        return theme.model_copy(update={"texture": texture.model_copy(update={"image": image})})
    raise ThemeError(str(path), [InputIssue("texture.image.file", message)])


def _readable_picture(path: Path) -> bool:
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(path) as image:
            image.load()
    except (OSError, UnidentifiedImageError):
        return False
    return True


def _issue_from_error(error: ErrorDetails) -> InputIssue:
    loc = error["loc"]
    if error["type"] == "string_pattern_mismatch":
        message = f'expected a color as #RRGGBB, e.g. "#F2B53A", got {show(error.get("input"))}'
        return InputIssue(format_location(loc), message)
    return issue_from_error(error, loc, _REFERENCE)
