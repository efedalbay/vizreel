"""Reading YAML input files and turning Pydantic errors into messages a user can act on."""

import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from pydantic_core import ErrorDetails, InitErrorDetails, PydanticCustomError

from vizreel.errors import InputFileError, InputIssue

RULE_ERROR_TYPE = "vizreel_rule"
"""Pydantic error type for vizreel's own rules. The message is shown to the user as written."""

Location = tuple[str | int, ...]

_MAX_SHOWN_INPUT = 40


RuleViolation = tuple[Location, str]
"""A broken rule: where, relative to the model being validated, and what is wrong."""


def rule_error(message: str) -> PydanticCustomError:
    """Build a Pydantic error whose message is shown to the user as written."""
    return PydanticCustomError(RULE_ERROR_TYPE, "{message}", {"message": message})


def raise_rule_violations(model: str, violations: list[RuleViolation]) -> None:
    """Raise all violations at once from a model validator, each at its own location."""
    if violations:
        raise ValidationError.from_exception_data(
            model,
            [
                InitErrorDetails(type=rule_error(message), loc=loc, input=None)
                for loc, message in violations
            ],
        )


def read_yaml_mapping(
    path: Path, error_type: type[InputFileError], kind: str, required: tuple[str, ...]
) -> dict[str, Any]:
    """Read a UTF-8 YAML file whose top level is a mapping.

    Args:
        path: The file to read.
        error_type: Error raised for every problem, e.g. `SpecError`.
        kind: What the file is, for messages, e.g. "spec".
        required: Top-level fields the file needs, for messages.

    Raises:
        InputFileError: Of `error_type`, if the file cannot be read or is not a YAML mapping.
    """
    source = str(path)
    if path.is_dir():
        raise _file_error(error_type, source, "is a directory, expected a YAML file")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise _file_error(error_type, source, "file not found") from None
    except PermissionError:
        raise _file_error(error_type, source, "permission denied") from None
    except UnicodeDecodeError:
        message = "is not UTF-8 text; save the file as UTF-8"
        raise _file_error(error_type, source, message) from None
    return parse_yaml_mapping(text, source, error_type, kind, required)


def parse_yaml_mapping(
    text: str, source: str, error_type: type[InputFileError], kind: str, required: tuple[str, ...]
) -> dict[str, Any]:
    """Parse YAML text whose top level is a mapping. See `read_yaml_mapping`."""
    try:
        data = yaml.safe_load(text)
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark
        where = f" at line {mark.line + 1}, column {mark.column + 1}" if mark is not None else ""
        raise _file_error(error_type, source, f"invalid YAML{where}: {exc.problem}") from None
    except yaml.YAMLError as exc:
        raise _file_error(error_type, source, f"invalid YAML: {exc}") from None
    fields = [f"`{name}`" for name in required]
    if data is None:
        needs = f"{', '.join(fields[:-1])} and {fields[-1]}" if len(fields) > 1 else fields[0]
        raise _file_error(error_type, source, f"the file is empty; a {kind} needs {needs}")
    if not isinstance(data, dict):
        raise _file_error(
            error_type,
            source,
            f"expected {', '.join(fields)} and other fields at the top level, got {describe(data)}",
        )
    return data


def _file_error(error_type: type[InputFileError], source: str, message: str) -> InputFileError:
    return error_type(source, [InputIssue("", message)])


def issue_from_error(error: ErrorDetails, loc: Location, reference: str) -> InputIssue:
    """Turn one Pydantic error into a user-facing issue.

    Args:
        error: The Pydantic error.
        loc: Location to report, which may differ from the error's own `loc`.
        reference: Document that lists the valid fields, e.g. "docs/SPEC.md".
    """
    return InputIssue(format_location(loc), _message(error, reference))


def format_location(loc: Location) -> str:
    """Format a location as a path, e.g. ("charts", 1, "x") → "charts[1].x"."""
    parts: list[str] = []
    for part in loc:
        if isinstance(part, int):
            parts.append(f"[{part}]")
        else:
            parts.append(f".{part}" if parts else str(part))
    return "".join(parts)


def _message(error: ErrorDetails, reference: str) -> str:
    kind = error["type"]
    value = error.get("input")
    ctx = error.get("ctx", {})

    if kind == RULE_ERROR_TYPE:
        return str(ctx["message"])
    if kind == "missing":
        return "required field is missing"
    if kind == "extra_forbidden":
        return f"unknown field. Check the spelling against {reference}"
    if kind == "literal_error":
        expected = str(ctx["expected"]).replace("'", '"')
        return f"expected one of {expected}, got {show(value)}"
    if kind in ("float_type", "int_type", "float_parsing", "int_parsing", "int_from_float"):
        return _number_message(kind, value)
    if kind == "finite_number":
        return "must be a finite number"
    if kind == "string_type":
        return _text_message(value)
    if kind == "string_too_short":
        return "must not be empty"
    if kind == "bool_type":
        return f"expected true or false, got {show(value)}"
    if kind == "too_short":
        return f"expected at least {_items(ctx['min_length'])}, got {ctx['actual_length']}"
    if kind == "too_long":
        return f"expected at most {_items(ctx['max_length'])}, got {ctx['actual_length']}"
    if kind == "greater_than":
        return f"must be greater than {show(ctx['gt'])}, got {show(value)}"
    if kind == "greater_than_equal":
        return f"must be at least {show(ctx['ge'])}, got {show(value)}"
    if kind == "less_than_equal":
        return f"must be at most {show(ctx['le'])}, got {show(value)}"
    if kind in ("model_type", "model_attributes_type", "dict_type"):
        return f"expected fields (key: value), got {describe(value)}"
    if kind == "list_type":
        return f"expected a list, got {describe(value)}"
    return error["msg"]


def _number_message(kind: str, value: object) -> str:
    if kind == "int_from_float" or (kind == "int_type" and isinstance(value, float)):
        return f"expected a whole number, got {show(value)}"
    if isinstance(value, str):
        return (
            f"expected a number, got text {show(value)}. "
            "Write a plain number without quotes or units"
        )
    return f"expected a number, got {describe(value)}"


def _text_message(value: object) -> str:
    if isinstance(value, bool):
        return (
            "expected text, got a true/false value. "
            "YAML reads yes, no, on, off, true and false as booleans; put the text in quotes"
        )
    if isinstance(value, int | float):
        return f'expected text, got the number {show(value)}. Put it in quotes: "{value}"'
    if isinstance(value, datetime.date):
        return f'expected text, got a date. Put it in quotes: "{value.isoformat()}"'
    return f"expected text, got {describe(value)}"


def _items(count: int) -> str:
    return f"{count} item" if count == 1 else f"{count} items"


def describe(value: object) -> str:
    """Describe a YAML value in words, e.g. "a list" or "the number 3"."""
    if value is None:
        return "an empty value"
    if isinstance(value, bool):
        return f"{str(value).lower()}"
    if isinstance(value, str):
        return f"text {show(value)}"
    if isinstance(value, int | float):
        return f"the number {show(value)}"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, dict):
        return "fields (key: value)"
    if isinstance(value, datetime.date):
        return "a date"
    return type(value).__name__


def show(value: object) -> str:
    """Show a YAML value as the user wrote it, shortened if long: "8k", 24, true."""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, str):
        shown = value if len(value) <= _MAX_SHOWN_INPUT else value[: _MAX_SHOWN_INPUT - 3] + "..."
        return f'"{shown}"'
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)
