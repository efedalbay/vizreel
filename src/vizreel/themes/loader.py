"""Find a theme by built-in name or path and validate it."""

from pathlib import Path

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
    try:
        theme = Theme.model_validate(data)
    except ValidationError as exc:
        raise ThemeError(str(path), [_issue_from_error(error) for error in exc.errors()]) from None
    return _with_logo_path(theme, path)


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


def _issue_from_error(error: ErrorDetails) -> InputIssue:
    loc = error["loc"]
    if error["type"] == "string_pattern_mismatch":
        message = f'expected a color as #RRGGBB, e.g. "#F2B53A", got {show(error.get("input"))}'
        return InputIssue(format_location(loc), message)
    return issue_from_error(error, loc, _REFERENCE)
