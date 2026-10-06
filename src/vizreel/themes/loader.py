"""Find a theme by built-in name or path and validate it."""

from pathlib import Path
from typing import Any

from pydantic import ValidationError
from pydantic_core import ErrorDetails

from vizreel.errors import InputIssue, ThemeError
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


def font_family(path: Path) -> str:
    """Return the family name a font file holds, e.g. "IBM Plex Mono".

    Raises:
        OSError: The file is not a font.
    """
    from PIL import ImageFont

    family, _ = ImageFont.truetype(str(path), 16).getname()
    if not family:
        raise OSError(f"{path} names no font family")
    return family


def _read_font_files(data: dict[str, Any], path: Path) -> list[InputIssue]:
    """Give each font with a `file` the family that file holds and the file's full path.

    The data is changed in place, before validation, so the theme model always has a family.

    Returns:
        What is wrong with the font files: one missing, not a TTF or OTF file, unreadable, or
        holding another family than the one the theme names.
    """
    fonts = data.get("fonts")
    if not isinstance(fonts, dict):
        return []
    issues = []
    for role in FONT_ROLES:
        style = fonts.get(role)
        reference = style.get("file") if isinstance(style, dict) else None
        if not isinstance(style, dict) or not isinstance(reference, str) or not reference:
            continue
        font = path.parent / reference
        loc = f"fonts.{role}.file"
        if font.suffix.lower() not in FONT_SUFFIXES:
            issues.append(InputIssue(loc, f"{reference} is not a TTF or OTF font file"))
            continue
        if not font.is_file():
            issues.append(InputIssue(loc, f"{reference} was not found in {font.parent}"))
            continue
        try:
            family = font_family(font)
        except OSError:
            issues.append(InputIssue(loc, f"{reference} cannot be read as a font"))
            continue
        given = style.get("family")
        if given is not None and given != family:
            issues.append(
                InputIssue(
                    f"fonts.{role}.family",
                    f'is "{given}" but {reference} holds the family "{family}"; leave out '
                    "family or write it as the file names it",
                )
            )
            continue
        fonts[role] = {**style, "family": family, "file": str(font.resolve())}
    return issues


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
