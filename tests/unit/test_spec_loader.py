from pathlib import Path

import pytest

from vizreel.errors import SpecError
from vizreel.spec.loader import load_spec, parse_spec
from vizreel.spec.models import StatChart

INVALID_DIR = Path(__file__).parent / "fixtures" / "invalid"
VALID_TYPES = (
    "Valid types: area, bar, compare, grouped, line, share, stacked, stat, table, timeline, "
    "waterfall"
)

EXPECTED_ERRORS: dict[str, list[str]] = {
    "bar-rules": [
        'charts[0].bars[2].label: "Buyer A (2015)" is already used by bars[0]; '
        "bar labels must be unique",
        'charts[0].highlight.label: "Buyer D (2017)" does not match any bar. '
        'Bar labels: "Buyer A (2015)", "Buyer B (2016)"',
    ],
    "duplicate-ids": [
        'charts[2].id: "users" is already used by charts[0]; ids must be unique',
    ],
    "empty": [
        "the file is empty; a spec needs `version` and `charts`",
    ],
    "invalid-id": [
        'charts[0].id: "Peak Valuation" is not a valid id. '
        'Use only lowercase letters, digits and hyphens, e.g. "peak-valuation"',
        'charts[1].id: "con" is a reserved file name on Windows. Choose another id',
    ],
    "limits": [
        "charts[0].duration: must be at least 2, got 1",
        "charts[0].value: must be a finite number",
        "charts[1].number.decimals: must be at most 6, got 7",
        'charts[1].number.compact: expected true, false, "long" or "short", got "yes"',
    ],
    "line-highlight-gap": [
        'charts[0].highlight.x: "2020" has no value in any series; nothing to highlight',
    ],
    "line-range-order": [
        "charts[0].y_max: must be greater than y_min (10), got 5",
    ],
    "line-rules": [
        'charts[0].x[2]: "2020" is already used by x[1]; x labels must be unique',
        "charts[0].series[1].values: needs at least one number, not only null",
        "charts[0].series[1].name: required when the chart has more than one series",
        "charts[0].series[0].values[1]: 12 is above y_max (10)",
        'charts[0].highlight.x: "2021" is not one of the x labels: "2019", "2020"',
    ],
    "meta": [
        'meta.resolution: expected one of "720p", "1080p", "1440p" or "4k", got "8k"',
        "meta.fps: 45 is not a supported frame rate. "
        "Use 23.976, 24, 25, 29.97, 30, 50, 59.94 or 60",
        "meta.theem: unknown field. Check the spelling against docs/SPEC.md",
    ],
    "missing-type": [
        f"charts[0].type: required field is missing. {VALID_TYPES}",
    ],
    "missing-version": [
        "version: required field is missing",
    ],
    "negative-bar": [
        "charts[0].bars[1].value: must be at least 0, got -3",
    ],
    "no-charts": [
        "charts: expected at least 1 item, got 0",
    ],
    "series-length": [
        "charts[0].series[0].values: expected 5 values (same as x), got 4",
    ],
    "text-as-number": [
        'charts[0].value: expected a number, got text "740M". '
        "Write a plain number without quotes or units",
    ],
    "too-many-bars": [
        "charts[0].bars: expected at most 8 items, got 9",
    ],
    "top-level-list": [
        "expected `version`, `charts` and other fields at the top level, got a list",
    ],
    "two-emphasized-events": [
        "charts[0].events[2].emphasis: only one event can have emphasis; events[0] already has it",
    ],
    "unknown-field": [
        "charts[0].lable: unknown field. Check the spelling against docs/SPEC.md",
    ],
    "unknown-type": [
        f'charts[0].type: unknown type "pie". {VALID_TYPES}',
    ],
    "unquoted-date-and-boolean": [
        'charts[0].events[0].date: expected text, got a date. Put it in quotes: "2018-03-01"',
        "charts[0].events[1].label: expected text, got a true/false value. "
        "YAML reads yes, no, on, off, true and false as booleans; put the text in quotes",
    ],
    "unquoted-year": [
        'charts[0].x[0]: expected text, got the number 2016. Put it in quotes: "2016"',
    ],
    "unsupported-version": [
        "version: unsupported spec version 2. This version of vizreel reads version 1",
    ],
    "yaml-syntax": [
        "invalid YAML at line 5, column 4: expected <block end>, but found '<block mapping start>'",
    ],
}


def test_every_fixture_has_expected_errors() -> None:
    fixtures = {path.stem for path in INVALID_DIR.glob("*.yaml")}

    assert fixtures == set(EXPECTED_ERRORS)


@pytest.mark.parametrize("name", sorted(EXPECTED_ERRORS))
def test_invalid_spec_reports_expected_errors(name: str) -> None:
    path = INVALID_DIR / f"{name}.yaml"

    with pytest.raises(SpecError) as caught:
        load_spec(path)

    assert [str(issue) for issue in caught.value.issues] == EXPECTED_ERRORS[name]
    assert caught.value.source == str(path)


def test_errors_from_several_charts_are_reported_together() -> None:
    text = """
version: 1
charts:
  - { id: users, type: stat, value: "1.2M" }
  - { id: offers, type: bar, bars: [{ label: A, value: 1 }] }
  - { id: events, type: timeline, events: [{ date: "2018", label: A }, { date: "2019" }] }
"""
    with pytest.raises(SpecError) as caught:
        parse_spec(text, "several.yaml")

    assert [issue.location for issue in caught.value.issues] == [
        "charts[0].value",
        "charts[1].bars",
        "charts[2].events[1].label",
    ]
    assert str(caught.value) == "several.yaml: 3 errors"


def test_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "missing.yaml"

    with pytest.raises(SpecError) as caught:
        load_spec(path)

    assert [str(issue) for issue in caught.value.issues] == ["file not found"]


def test_directory_instead_of_file(tmp_path: Path) -> None:
    with pytest.raises(SpecError) as caught:
        load_spec(tmp_path)

    assert [str(issue) for issue in caught.value.issues] == ["is a directory, expected a YAML file"]


def test_file_that_is_not_utf8(tmp_path: Path) -> None:
    path = tmp_path / "latin1.yaml"
    path.write_bytes(
        "version: 1\ncharts: [{ id: a, type: stat, value: 1, label: Größe }]".encode("latin-1")
    )

    with pytest.raises(SpecError) as caught:
        load_spec(path)

    assert [str(issue) for issue in caught.value.issues] == [
        "is not UTF-8 text; save the file as UTF-8"
    ]


def test_utf8_with_bom_and_non_ascii_text(tmp_path: Path) -> None:
    path = tmp_path / "bom.yaml"
    text = "version: 1\ncharts:\n  - { id: users, type: stat, value: 1, label: Kullanıcı sayısı }\n"
    path.write_text(text, encoding="utf-8-sig")

    chart = load_spec(path).charts[0]

    assert isinstance(chart, StatChart)
    assert chart.label == "Kullanıcı sayısı"


def test_boolean_version_is_rejected() -> None:
    with pytest.raises(SpecError) as caught:
        parse_spec("version: true\ncharts: [{ id: a, type: stat, value: 1 }]", "spec.yaml")

    assert [str(issue) for issue in caught.value.issues] == ["version: expected 1, got true"]


def test_long_text_input_is_shortened_in_messages() -> None:
    long_value = "x" * 60

    with pytest.raises(SpecError) as caught:
        parse_spec(f"version: 1\ncharts: [{{ id: a, type: stat, value: {long_value} }}]", "s.yaml")

    message = caught.value.issues[0].message
    assert '"' + "x" * 37 + '..."' in message
    assert long_value not in message
