import subprocess
import sys

from typer.testing import CliRunner

from vizreel import __version__
from vizreel.cli import app

runner = CliRunner()


def test_version_prints_package_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"vizreel {__version__}"


def test_help_exits_cleanly() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "vizreel" in result.stdout


def test_python_dash_m_runs_cli() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "vizreel", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == f"vizreel {__version__}"
