"""Read a YAML spec into a validated `Spec`, collecting every error with its location."""

import operator
import re
from dataclasses import dataclass, field
from functools import cache, reduce
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, ValidationError, create_model
from pydantic_core import ErrorDetails

from vizreel.charts.registry import chart_registry
from vizreel.errors import InputIssue, SpecError
from vizreel.format.locales import EN_US, LOCALES, Locale
from vizreel.spec.data import TableError, read_table
from vizreel.spec.models import DataFile, Spec
from vizreel.validation import (
    Location,
    describe,
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
    """Read and validate a spec file, with the data files its charts read.

    Raises:
        SpecError: The file cannot be read, is not valid YAML, or is not a valid spec.
    """
    data = read_yaml_mapping(path, SpecError, _KIND, _REQUIRED)
    return _validate(data, str(path), path.parent)


def parse_spec(text: str, source: str, base_dir: Path | None = None) -> Spec:
    """Validate spec YAML given as text.

    Args:
        text: The YAML document.
        source: Name of the document, used in error messages.
        base_dir: The folder data file paths are relative to. The current folder if None.

    Raises:
        SpecError: The text is not valid YAML or not a valid spec.
    """
    data = parse_yaml_mapping(text, source, SpecError, _KIND, _REQUIRED)
    return _validate(data, source, base_dir or Path())


def spec_input_files(path: Path) -> list[Path]:
    """Return the data and image files that exist among those a spec file names.

    The spec is read loosely, so this works even if it is invalid. Watching uses it to render
    again when one of these files changes, including one that made the spec invalid.
    """
    try:
        data = read_yaml_mapping(path, SpecError, _KIND, _REQUIRED)
    except SpecError:
        return []
    charts = data.get("charts")
    references: list[object] = []
    for chart in charts if isinstance(charts, list) else []:
        if not isinstance(chart, dict):
            continue
        reference = chart.get("data")
        references.append(reference.get("file") if isinstance(reference, dict) else reference)
        images = chart.get("images")
        references += list(images.values()) if isinstance(images, dict) else []
    files = [
        path.parent / reference
        for reference in references
        if isinstance(reference, str) and reference and (path.parent / reference).is_file()
    ]
    return list(dict.fromkeys(files))


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


@dataclass
class _Filled:
    """A spec's data after the charts' data files have filled in their fields.

    Attributes:
        data: The spec, each chart with the fields its data file gives.
        issues: What is wrong with the data files and their references.
        files: For each chart that reads a data file, by index: the file as the spec names it
            and the fields it gave; empty if it could not be read.
    """

    data: dict[str, Any]
    issues: list[InputIssue] = field(default_factory=list)
    files: dict[int, tuple[str, set[str]]] = field(default_factory=dict)

    def origin(self, loc: Location) -> str | None:
        """The data file that gave the field at `loc`, or None if the spec wrote it."""
        if len(loc) < 3 or loc[0] != "charts" or not isinstance(loc[1], int):
            return None
        file, fields = self.files.get(loc[1], ("", set()))
        return file if loc[2] in fields else None

    def unread(self, loc: Location) -> bool:
        """Whether `loc` is a chart field that a data file could not give, being unreadable."""
        if len(loc) != 3 or loc[0] != "charts" or loc[1] not in self.files:
            return False
        _, fields = self.files[int(loc[1])]
        return not fields


def _validate(data: dict[str, Any], source: str, base_dir: Path) -> Spec:
    filled = _fill_from_data_files(data, base_dir)
    filled.issues += _resolve_images(filled.data, base_dir)
    try:
        spec = spec_model().model_validate(filled.data)
    except ValidationError as exc:
        issues = [*filled.issues, *_issues_from_errors(exc.errors(), filled)]
        raise SpecError(source, sorted(issues, key=_chart_order)) from None
    if filled.issues:
        raise SpecError(source, filled.issues)
    return spec


IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".svg")
"""The image files a chart can show."""


def _resolve_images(data: dict[str, Any], base_dir: Path) -> list[InputIssue]:
    """Replace the image paths of each chart's `images` with full paths, checking each file.

    A chart type draws its images long after the spec is read, from wherever vizreel runs, so
    the paths are made absolute here, relative to the spec file as a user writes them.
    """
    charts = data.get("charts")
    if not isinstance(charts, list):
        return []
    issues: list[InputIssue] = []
    for index, chart in enumerate(charts):
        images = chart.get("images") if isinstance(chart, dict) else None
        if not isinstance(images, dict):
            continue
        resolved = dict(images)
        for name, reference in images.items():
            if not isinstance(reference, str) or not reference:
                continue
            path = base_dir / reference
            loc: Location = ("charts", index, "images", str(name))
            if path.suffix.lower() not in IMAGE_SUFFIXES:
                issues.append(_issue(loc, f"{reference} is not a PNG, JPEG or SVG file"))
            elif not path.is_file():
                issues.append(_issue(loc, f"{reference} was not found in {path.parent}"))
            else:
                resolved[name] = str(path.resolve())
        charts[index] = {**chart, "images": resolved}
    return issues


def _chart_order(issue: InputIssue) -> int:
    """The index of the chart an issue is in, or -1 outside the charts, to sort issues by."""
    match = re.match(r"charts\[(\d+)\]", issue.location)
    return int(match.group(1)) if match else -1


def _fill_from_data_files(data: dict[str, Any], base_dir: Path) -> _Filled:
    """Give each chart that names a data file the fields its chart type reads from it."""
    charts = data.get("charts")
    if not isinstance(charts, list):
        return _Filled(data)
    filled = _Filled({**data, "charts": list(charts)})
    locale = _spec_locale(data)
    registry = chart_registry()
    for index, chart in enumerate(charts):
        if not isinstance(chart, dict) or "data" not in chart:
            continue
        name = chart.get("type")
        if not isinstance(name, str) or name not in registry.names():
            continue
        loc: Location = ("charts", index, "data")
        reference = _data_reference(chart["data"], loc, filled.issues)
        filled.files[index] = ("", set())
        if reference is None:
            filled.data["charts"][index] = {key: chart[key] for key in chart if key != "data"}
            continue
        try:
            table = read_table(base_dir / reference.file, locale, reference.columns)
            fields = registry.get(name).from_table(table, chart)
        except TableError as exc:
            where = f", {exc.where()}" if exc.where() else ""
            filled.issues.append(_issue(loc, f"{reference.file}{where} {exc.message}"))
            continue
        for key in fields:
            if key in chart:
                message = f"cannot be used together with data; {reference.file} gives the {key}"
                filled.issues.append(_issue(("charts", index, key), message))
        filled.data["charts"][index] = {**chart, **fields}
        filled.files[index] = (reference.file, set(fields))
    return filled


def _data_reference(value: object, loc: Location, issues: list[InputIssue]) -> DataFile | None:
    """Read the `data` field of a chart, adding what is wrong with it to `issues`."""
    if isinstance(value, str):
        if value:
            return DataFile(file=value)
        issues.append(_issue(loc, "must not be empty"))
        return None
    if not isinstance(value, dict):
        expected = "expected the path of a CSV file, or file and columns"
        issues.append(_issue(loc, f"{expected}, got {describe(value)}"))
        return None
    try:
        return DataFile.model_validate(value)
    except ValidationError as exc:
        issues.extend(
            issue_from_error(error, (*loc, *error["loc"]), _REFERENCE) for error in exc.errors()
        )
        return None


def _spec_locale(data: dict[str, Any]) -> Locale:
    """The locale the spec names, for reading its data files; validation reports a wrong one."""
    meta = data.get("meta")
    name = meta.get("locale") if isinstance(meta, dict) else None
    return LOCALES.get(name, EN_US) if isinstance(name, str) else EN_US


def _issues_from_errors(errors: list[ErrorDetails], filled: _Filled) -> list[InputIssue]:
    """Turn Pydantic's errors into issues, one per union value rather than per branch.

    A field missing from a chart whose data file could not be read is left out: the file
    would give it. A problem in a field that a data file gave names the file.
    """
    issues = []
    reported: set[Location] = set()
    for error in errors:
        loc = _strip_chart_tag(error["loc"])
        if error["type"] == "missing" and filled.unread(loc):
            continue
        if loc and loc[-1] in _UNION_BRANCHES:
            if loc[:-1] not in reported:
                reported.add(loc[:-1])
                value = show(error.get("input"))
                issue = _issue(loc[:-1], f"expected {_UNION_BRANCHES[loc[-1]]}, got {value}")
            else:
                continue
        else:
            issue = _issue_from_error(error)
        origin = filled.origin(loc)
        if origin is not None:
            issue = InputIssue(issue.location, f"{issue.message} (from {origin})")
        issues.append(issue)
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
