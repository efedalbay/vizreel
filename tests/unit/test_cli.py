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


def test_render_unknown_chart_id() -> None:
    result = runner.invoke(app, ["render", str(SHOWCASE), "--only", "nope"])

    assert result.exit_code == 1
    assert "error: no chart with id 'nope'" in result.stderr


def test_render_invalid_spec() -> None:
    path = INVALID_DIR / "unknown-type.yaml"

    result = runner.invoke(app, ["render", str(path)])

    assert result.exit_code == 1
    assert result.stderr.splitlines()[0] == f"{path}: 1 error"


def test_render_missing_theme(tmp_path: Path) -> None:
    path = tmp_path / "spec.yaml"
    path.write_text(
        "version: 1\nmeta: { theme: brand.yaml }\ncharts: [{ id: a, type: stat, value: 1 }]"
    )

    result = runner.invoke(app, ["render", str(path)])

    assert result.exit_code == 1
    assert 'theme "brand.yaml" not found' in result.stderr


def test_render_rejects_unknown_quality() -> None:
    result = runner.invoke(app, ["render", str(SHOWCASE), "--quality", "draft"])

    assert result.exit_code == 2


def test_themes_list_shows_names_and_descriptions() -> None:
    result = runner.invoke(app, ["themes", "list"])

    assert result.exit_code == 0
    assert "default  Dark panel, light text and an amber highlight." in result.stdout


def test_theme_check_passing_theme() -> None:
    result = runner.invoke(app, ["theme", "check", "default"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "default: all 46 checks passed"


def test_theme_check_verbose_lists_every_check() -> None:
    result = runner.invoke(app, ["theme", "check", "default", "--verbose"])

    lines = result.stdout.splitlines()
    assert result.exit_code == 0
    assert len([line for line in lines if line.startswith("  PASS  ")]) == 46
    assert "  PASS  colors.text on colors.surface: contrast 15.53:1, needs at least 4.5:1" in lines


def test_theme_check_failing_theme(tmp_path: Path) -> None:
    from vizreel.themes.loader import BUILTIN_DIR

    text = (BUILTIN_DIR / "default.yaml").read_text(encoding="utf-8")
    path = tmp_path / "grey.yaml"
    path.write_text(text.replace('muted: "#9BA4AE"', 'muted: "#30363D"'), encoding="utf-8")

    result = runner.invoke(app, ["theme", "check", str(path)])

    assert result.exit_code == 1
    assert "  FAIL  colors.muted on colors.surface: contrast 1.42:1, needs at least 4.5:1" in (
        result.stdout.splitlines()
    )
    assert "checks failed" in result.stderr


def test_theme_check_missing_theme() -> None:
    result = runner.invoke(app, ["theme", "check", "nope"])

    assert result.exit_code == 1
    assert 'theme "nope" not found' in result.stderr


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
