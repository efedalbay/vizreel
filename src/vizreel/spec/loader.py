"""Read a YAML spec into a validated `Spec`, collecting every error with its location."""

import datetime
import operator
from functools import cache, reduce
from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import Field, ValidationError, create_model
from pydantic_core import ErrorDetails

from vizreel.charts.registry import builtin_registry
from vizreel.errors import SpecError, SpecIssue
from vizreel.spec.models import RULE_ERROR_TYPE, Spec

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
_MAX_SHOWN_INPUT = 40


def load_spec(path: Path) -> Spec:
    """Read and validate a spec file.

    Raises:
        SpecError: The file cannot be read, is not valid YAML, or is not a valid spec.
    """
    source = str(path)
    if path.is_dir():
        raise _file_error(source, "is a directory, expected a YAML file")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise _file_error(source, "file not found") from None
    except PermissionError:
        raise _file_error(source, "permission denied") from None
    except UnicodeDecodeError:
        raise _file_error(source, "is not UTF-8 text; save the file as UTF-8") from None
    return parse_spec(text, source)


def parse_spec(text: str, source: str) -> Spec:
    """Validate spec YAML given as text.

    Args:
        text: The YAML document.
        source: Name of the document, used in error messages.

    Raises:
        SpecError: The text is not valid YAML or not a valid spec.
    """
    data = _parse_yaml(text, source)
    try:
        return spec_model().model_validate(data)
    except ValidationError as exc:
        raise SpecError(source, [_issue_from_error(error) for error in exc.errors()]) from None


def spec_json_schema() -> dict[str, Any]:
    """Return the JSON Schema of the spec format, including every registered chart type."""
    schema = spec_model().model_json_schema()
    return {"$schema": JSON_SCHEMA_DIALECT, **schema}


@cache
def spec_model() -> type[Spec]:
    """Return the `Spec` model with `charts` narrowed to every registered chart type."""
    models = builtin_registry().models()
    chart_union: Any = Annotated[reduce(operator.or_, models), Field(discriminator="type")]
    return create_model(
        "Spec",
        __base__=Spec,
        __doc__=Spec.__doc__,
        charts=(
            list[chart_union],
            Field(min_length=1, description="One or more charts. Each renders to its own file."),
        ),
    )


def _parse_yaml(text: str, source: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(text)
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark
        where = f" at line {mark.line + 1}, column {mark.column + 1}" if mark is not None else ""
        raise _file_error(source, f"invalid YAML{where}: {exc.problem}") from None
    except yaml.YAMLError as exc:
        raise _file_error(source, f"invalid YAML: {exc}") from None
    if data is None:
        raise _file_error(source, "the file is empty; a spec needs `version` and `charts`")
    if not isinstance(data, dict):
        raise _file_error(
            source,
            "expected `version`, `charts` and other fields at the top level, "
            f"got {_describe(data)}",
        )
    return data


def _file_error(source: str, message: str) -> SpecError:
    return SpecError(source, [SpecIssue("", message)])


def _issue_from_error(error: ErrorDetails) -> SpecIssue:
    loc = _strip_chart_tag(error["loc"])
    kind = error["type"]
    if kind in ("union_tag_invalid", "union_tag_not_found"):
        loc = (*loc, "type")
    return SpecIssue(_format_location(loc), _message(error, loc))


def _strip_chart_tag(loc: tuple[int | str, ...]) -> tuple[int | str, ...]:
    """Remove the chart type name Pydantic inserts after `charts[i]` in discriminated unions."""
    is_chart_field = len(loc) >= 3 and loc[0] == "charts" and isinstance(loc[1], int)
    if is_chart_field and loc[2] in builtin_registry().names():
        return (*loc[:2], *loc[3:])
    return loc


def _format_location(loc: tuple[int | str, ...]) -> str:
    parts: list[str] = []
    for part in loc:
        if isinstance(part, int):
            parts.append(f"[{part}]")
        else:
            parts.append(f".{part}" if parts else str(part))
    return "".join(parts)


def _message(error: ErrorDetails, loc: tuple[int | str, ...]) -> str:
    kind = error["type"]
    value = error.get("input")
    ctx = error.get("ctx", {})
    valid_types = ", ".join(builtin_registry().names())

    if kind == RULE_ERROR_TYPE:
        return str(ctx["message"])
    if kind == "union_tag_invalid":
        return f'unknown type "{ctx["tag"]}". Valid types: {valid_types}'
    if kind == "union_tag_not_found":
        return f"required field is missing. Valid types: {valid_types}"
    if kind == "missing":
        return "required field is missing"
    if kind == "extra_forbidden":
        return "unknown field. Check the spelling against docs/SPEC.md"
    if kind == "literal_error" and loc == ("version",):
        return f"unsupported spec version {_show(value)}. This version of vizreel reads version 1"
    if kind == "literal_error":
        expected = str(ctx["expected"]).replace("'", '"')
        return f"expected one of {expected}, got {_show(value)}"
    if kind in ("float_type", "int_type", "float_parsing", "int_parsing", "int_from_float"):
        return _number_message(kind, value)
    if kind == "finite_number":
        return "must be a finite number"
    if kind == "string_type":
        return _text_message(value)
    if kind == "string_too_short":
        return "must not be empty"
    if kind == "string_pattern_mismatch" and loc[-1:] == ("id",):
        return (
            f"{_show(value)} is not a valid id. "
            'Use only lowercase letters, digits and hyphens, e.g. "peak-valuation"'
        )
    if kind == "bool_type":
        return f"expected true or false, got {_show(value)}"
    if kind == "too_short":
        return f"expected at least {_items(ctx['min_length'])}, got {ctx['actual_length']}"
    if kind == "too_long":
        return f"expected at most {_items(ctx['max_length'])}, got {ctx['actual_length']}"
    if kind == "greater_than_equal":
        return f"must be at least {_show(ctx['ge'])}, got {_show(value)}"
    if kind == "less_than_equal":
        return f"must be at most {_show(ctx['le'])}, got {_show(value)}"
    if kind in ("model_type", "model_attributes_type", "dict_type"):
        return f"expected fields (key: value), got {_describe(value)}"
    if kind == "list_type":
        return f"expected a list, got {_describe(value)}"
    return error["msg"]


def _number_message(kind: str, value: object) -> str:
    if kind == "int_from_float" or (kind == "int_type" and isinstance(value, float)):
        return f"expected a whole number, got {_show(value)}"
    if isinstance(value, str):
        return (
            f"expected a number, got text {_show(value)}. "
            "Write a plain number without quotes or units"
        )
    return f"expected a number, got {_describe(value)}"


def _text_message(value: object) -> str:
    if isinstance(value, bool):
        return (
            "expected text, got a true/false value. "
            "YAML reads yes, no, on, off, true and false as booleans; put the text in quotes"
        )
    if isinstance(value, int | float):
        return f'expected text, got the number {_show(value)}. Put it in quotes: "{value}"'
    if isinstance(value, datetime.date):
        return f'expected text, got a date. Put it in quotes: "{value.isoformat()}"'
    return f"expected text, got {_describe(value)}"


def _items(count: int) -> str:
    return f"{count} item" if count == 1 else f"{count} items"


def _describe(value: object) -> str:
    if value is None:
        return "an empty value"
    if isinstance(value, bool):
        return f"{str(value).lower()}"
    if isinstance(value, str):
        return f"text {_show(value)}"
    if isinstance(value, int | float):
        return f"the number {_show(value)}"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, dict):
        return "fields (key: value)"
    if isinstance(value, datetime.date):
        return "a date"
    return type(value).__name__


def _show(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, str):
        shown = value if len(value) <= _MAX_SHOWN_INPUT else value[: _MAX_SHOWN_INPUT - 3] + "..."
        return f'"{shown}"'
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)
