import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from vizreel import __version__, cli
from vizreel.cli import app
from vizreel.errors import RenderError

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


def test_redirected_output_is_utf8_so_a_turkish_path_reads_right(tmp_path: Path) -> None:
    import os

    folder = tmp_path / "kitaplık"
    folder.mkdir()
    (folder / "spec.yaml").write_text(
        "version: 1\ncharts:\n  - { id: a, type: stat, value: 1 }\n", encoding="utf-8"
    )
    (folder / "bad.yaml").write_text(
        "version: 1\ncharts:\n  - { id: a, type: stat, value: x }\n", encoding="utf-8"
    )
    env = {key: value for key, value in os.environ.items() if key != "PYTHONIOENCODING"}

    def run(name: str) -> subprocess.CompletedProcess[bytes]:
        command = [sys.executable, "-m", "vizreel", "validate", str(folder / name)]
        return subprocess.run(command, capture_output=True, env=env, check=False)

    valid, invalid = run("spec.yaml"), run("bad.yaml")

    assert "kitaplık" in valid.stdout.decode("utf-8")
    assert "kitaplık" in invalid.stderr.decode("utf-8")


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
    assert result.stdout.strip() == f"{SHOWCASE} is valid: 16 charts"


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


def test_render_watch_prints_progress_and_stops_on_ctrl_c(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def watch(spec: Path, options: object, **callbacks: Any) -> None:
        callbacks["on_render"](["peak-valuation"])
        callbacks["on_error"](RenderError("something went wrong"))
        callbacks["on_render"]([])
        callbacks["on_wait"]()
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "watch_spec", watch)

    result = runner.invoke(app, ["render", str(SHOWCASE), "--watch"])

    assert result.exit_code == 0
    assert result.stdout.splitlines() == [
        "Rendering peak-valuation...",
        "No chart changed.",
        f"Watching {SHOWCASE} for changes. Press Ctrl+C to stop.",
        "Stopped watching.",
    ]
    assert result.stderr.strip() == "error: something went wrong"


def test_render_rejects_unknown_quality() -> None:
    result = runner.invoke(app, ["render", str(SHOWCASE), "--quality", "draft"])

    assert result.exit_code == 2


def test_themes_list_shows_names_and_descriptions() -> None:
    result = runner.invoke(app, ["themes", "list"])

    assert result.exit_code == 0
    assert result.stdout.splitlines() == [
        "default  Dark panel, light text and an amber highlight.",
        "light  Light panel, dark text and an orange highlight.",
    ]


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


def test_new_prints_a_valid_template() -> None:
    from vizreel.spec.loader import parse_spec

    result = runner.invoke(app, ["new", "line"])

    assert result.exit_code == 0
    assert [chart.type for chart in parse_spec(result.stdout, "line.yaml").charts] == ["line"]


def test_new_writes_a_template_file(tmp_path: Path) -> None:
    path = tmp_path / "stat.yaml"

    result = runner.invoke(app, ["new", "stat", "-o", str(path)])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"Wrote a stat template to {path}"
    assert path.read_text(encoding="utf-8").startswith("# A stat chart.")


def test_new_does_not_overwrite_a_file(tmp_path: Path) -> None:
    path = tmp_path / "mine.yaml"
    path.write_text("keep me", encoding="utf-8")

    result = runner.invoke(app, ["new", "bar", "--output", str(path)])

    assert result.exit_code == 1
    assert "already exists; choose another file name" in result.stderr
    assert path.read_text(encoding="utf-8") == "keep me"


def test_new_unknown_type() -> None:
    result = runner.invoke(app, ["new", "pie"])

    assert result.exit_code == 1
    assert (
        'unknown chart type "pie". Valid types: '
        "area, bar, bar-race, compare, grouped, line, line-race, progress, scatter-race, share, "
        "stacked, stat, table, timeline, title-card, waterfall" in result.stderr
    )


def test_schema_prints_json_schema() -> None:
    result = runner.invoke(app, ["schema"])

    assert result.exit_code == 0
    schema = json.loads(result.stdout)
    mapping = schema["properties"]["charts"]["items"]["discriminator"]["mapping"]
    assert sorted(mapping) == [
        "area",
        "bar",
        "bar-race",
        "compare",
        "grouped",
        "line",
        "line-race",
        "progress",
        "scatter-race",
        "share",
        "stacked",
        "stat",
        "table",
        "timeline",
        "title-card",
        "waterfall",
    ]


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
