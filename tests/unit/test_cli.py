import json
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from vizreel import __version__, cli
from vizreel.cli import app

ROOT = Path(__file__).parents[2]
SHOWCASE = ROOT / "examples" / "showcase.yaml"
INVALID_DIR = Path(__file__).parent / "fixtures" / "invalid"

runner = CliRunner(env={"FORCE_COLOR": None, "TTY_COMPATIBLE": None})


def test_version_prints_package_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"vizreel {__version__}"


def test_help_exits_cleanly() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "vizreel" in result.stdout
    assert "validate" in result.stdout
    assert "schema" in result.stdout


def test_python_dash_m_runs_cli() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "vizreel", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == f"vizreel {__version__}"


def test_validate_valid_spec() -> None:
    result = runner.invoke(app, ["validate", str(SHOWCASE)])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"{SHOWCASE} is valid: 4 charts"


def test_validate_invalid_spec_lists_every_error() -> None:
    path = INVALID_DIR / "line-rules.yaml"

    result = runner.invoke(app, ["validate", str(path)])

    assert result.exit_code == 1
    lines = result.stderr.splitlines()
    assert lines[0] == f"{path}: 5 errors"
    assert lines[1] == '  charts[0].x[2]: "2020" is already used by x[1]; x labels must be unique'
    assert len(lines) == 6
    assert result.stdout == ""


def test_validate_missing_file() -> None:
    result = runner.invoke(app, ["validate", "missing.yaml"])

    assert result.exit_code == 1
    assert result.stderr.splitlines() == ["missing.yaml: 1 error", "  file not found"]


def test_validate_prints_markup_in_user_text_literally(tmp_path: Path) -> None:
    path = tmp_path / "markup.yaml"
    path.write_text('version: 1\ncharts: [{ id: a, type: stat, value: "[bold]1[/bold]" }]')

    result = runner.invoke(app, ["validate", str(path)])

    assert result.exit_code == 1
    assert 'got text "[bold]1[/bold]"' in result.stderr


def test_unexpected_error_suggests_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(path: Path) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "load_spec", fail)

    result = runner.invoke(app, ["validate", str(SHOWCASE)])

    assert result.exit_code == 1
    assert result.stderr.splitlines() == [
        "unexpected error: RuntimeError: boom",
        "Run again with --debug to see the full traceback.",
    ]


def test_debug_lets_unexpected_errors_through(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(path: Path) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "load_spec", fail)

    result = runner.invoke(app, ["--debug", "validate", str(SHOWCASE)])

    assert isinstance(result.exception, RuntimeError)


def test_schema_prints_json_schema() -> None:
    result = runner.invoke(app, ["schema"])

    assert result.exit_code == 0
    schema = json.loads(result.stdout)
    mapping = schema["properties"]["charts"]["items"]["discriminator"]["mapping"]
    assert sorted(mapping) == ["bar", "line", "stat", "timeline"]


def test_schema_output_writes_utf8_file(tmp_path: Path) -> None:
    path = tmp_path / "vizreel.schema.json"

    result = runner.invoke(app, ["schema", "-o", str(path)])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"Wrote JSON Schema to {path}"
    raw = path.read_bytes()
    assert not raw.startswith((b"\xef\xbb\xbf", b"\xff\xfe"))
    assert json.loads(raw.decode("utf-8"))["$schema"].startswith("https://json-schema.org/")


def test_schema_output_to_missing_folder(tmp_path: Path) -> None:
    path = tmp_path / "missing" / "vizreel.schema.json"

    result = runner.invoke(app, ["schema", "--output", str(path)])

    assert result.exit_code == 1
    assert result.stderr.strip() == f"error: cannot write {path}: the folder does not exist"
