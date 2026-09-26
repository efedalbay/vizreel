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
_REFERENCE = "the built-in default theme"


def builtin_theme_names() -> list[str]:
    """Return the names of the built-in themes, sorted."""
    return sorted(path.stem for path in BUILTIN_DIR.glob("*.yaml"))


def resolve_theme_path(ref: str, spec_dir: Path) -> Path:
    """Find the file of a theme.

    Args:
        ref: `meta.theme` from the spec: a built-in name or a path to a YAML file.
        spec_dir: Folder of the spec file. Relative paths are resolved from here.

    Raises:
        ThemeError: No built-in theme has that name and no file exists at that path.
    """
    if ref in builtin_theme_names():
        return BUILTIN_DIR / f"{ref}.yaml"
    path = Path(ref)
    if not path.is_absolute():
        path = spec_dir / path
    if path.is_file():
        return path
    raise ThemeError(
        str(path),
        [
            InputIssue(
                "",
                f'theme "{ref}" not found. Built-in themes: {", ".join(builtin_theme_names())}. '
                "A custom theme is a path to a YAML file, relative to the spec file",
            )
        ],
    )


def load_theme(ref: str, spec_dir: Path) -> Theme:
    """Resolve and validate a theme.

    Args:
        ref: `meta.theme` from the spec: a built-in name or a path to a YAML file.
        spec_dir: Folder of the spec file. Relative paths are resolved from here.

    Raises:
        ThemeError: The theme cannot be found, read or validated.
    """
    path = resolve_theme_path(ref, spec_dir)
    data = read_yaml_mapping(path, ThemeError, _KIND, _REQUIRED)
    try:
        return Theme.model_validate(data)
    except ValidationError as exc:
        raise ThemeError(str(path), [_issue_from_error(error) for error in exc.errors()]) from None


def _issue_from_error(error: ErrorDetails) -> InputIssue:
    loc = error["loc"]
    if error["type"] == "string_pattern_mismatch":
        message = f'expected a color as #RRGGBB, e.g. "#F2B53A", got {show(error.get("input"))}'
        return InputIssue(format_location(loc), message)
    return issue_from_error(error, loc, _REFERENCE)
