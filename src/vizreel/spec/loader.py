"""Read a YAML spec into a validated `Spec`, collecting every error with its location."""

import operator
from functools import cache, reduce
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, ValidationError, create_model
from pydantic_core import ErrorDetails

from vizreel.charts.registry import chart_registry
from vizreel.errors import InputIssue, SpecError
from vizreel.spec.models import Spec
from vizreel.validation import (
    Location,
    format_location,
    issue_from_error,
    parse_yaml_mapping,
    read_yaml_mapping,
    show,
)

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
_KIND = "spec"
_REQUIRED = ("version", "charts")
_REFERENCE = "docs/SPEC.md"


def load_spec(path: Path) -> Spec:
    """Read and validate a spec file.

    Raises:
        SpecError: The file cannot be read, is not valid YAML, or is not a valid spec.
    """
    data = read_yaml_mapping(path, SpecError, _KIND, _REQUIRED)
    return _validate(data, str(path))


def parse_spec(text: str, source: str) -> Spec:
    """Validate spec YAML given as text.

    Args:
        text: The YAML document.
        source: Name of the document, used in error messages.

    Raises:
        SpecError: The text is not valid YAML or not a valid spec.
    """
    data = parse_yaml_mapping(text, source, SpecError, _KIND, _REQUIRED)
    return _validate(data, source)


def spec_json_schema() -> dict[str, Any]:
    """Return the JSON Schema of the spec format, including every registered chart type."""
    schema = spec_model().model_json_schema()
    return {"$schema": JSON_SCHEMA_DIALECT, **schema}


@cache
def spec_model() -> type[Spec]:
    """Return the `Spec` model with `charts` narrowed to every registered chart type."""
    models = chart_registry().models()
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


_COMPACT_VALUES = 'true, false, "long" or "short"'
_UNION_BRANCHES: dict[str, str] = {
    "constrained-str": "text or a number",
    "float": "text or a number",
    "bool": _COMPACT_VALUES,
    "literal['long','short']": _COMPACT_VALUES,
}
"""Names Pydantic appends to the location of a value that matches no branch of a union field,
such as a table cell or `compact`, each branch reporting its own error; and what the field takes."""


def _validate(data: dict[str, Any], source: str) -> Spec:
    try:
        return spec_model().model_validate(data)
    except ValidationError as exc:
        raise SpecError(source, _issues_from_errors(exc.errors())) from None


def _issues_from_errors(errors: list[ErrorDetails]) -> list[InputIssue]:
    """Turn Pydantic's errors into issues, one per union value rather than per branch."""
    issues = []
    reported: set[Location] = set()
    for error in errors:
        loc = _strip_chart_tag(error["loc"])
        if loc and loc[-1] in _UNION_BRANCHES:
            if loc[:-1] not in reported:
                reported.add(loc[:-1])
                value = show(error.get("input"))
                issues.append(_issue(loc[:-1], f"expected {_UNION_BRANCHES[loc[-1]]}, got {value}"))
            continue
        issues.append(_issue_from_error(error))
    return issues


def _issue_from_error(error: ErrorDetails) -> InputIssue:
    loc = _strip_chart_tag(error["loc"])
    kind = error["type"]
    value = error.get("input")
    registry = chart_registry()
    valid_types = ", ".join(registry.names())

    if kind == "union_tag_invalid":
        tag = error.get("ctx", {})["tag"]
        hint = registry.unknown_type_hint(tag)
        return _issue((*loc, "type"), f'unknown type "{tag}". Valid types: {valid_types}{hint}')
    if kind == "union_tag_not_found":
        return _issue((*loc, "type"), f"required field is missing. Valid types: {valid_types}")
    if kind == "literal_error" and loc == ("version",):
        return _issue(
            loc, f"unsupported spec version {show(value)}. This version of vizreel reads version 1"
        )
    if kind == "string_pattern_mismatch" and loc[-1:] == ("id",):
        return _issue(
            loc,
            f"{show(value)} is not a valid id. "
            'Use only lowercase letters, digits and hyphens, e.g. "peak-valuation"',
        )
    return issue_from_error(error, loc, _REFERENCE)


def _issue(loc: Location, message: str) -> InputIssue:
    return InputIssue(format_location(loc), message)


def _strip_chart_tag(loc: Location) -> Location:
    """Remove the chart type name Pydantic inserts after `charts[i]` in discriminated unions."""
    is_chart_field = len(loc) >= 3 and loc[0] == "charts" and isinstance(loc[1], int)
    if is_chart_field and loc[2] in chart_registry().names():
        return (*loc[:2], *loc[3:])
    return loc
