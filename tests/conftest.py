"""Fixtures shared by unit and render tests."""

import tomllib
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from vizreel.charts.registry import ENTRY_POINT_GROUP, chart_registry
from vizreel.spec.loader import spec_model

EXAMPLE_PLUGIN = Path(__file__).parents[1] / "examples" / "plugin"


@pytest.fixture
def install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., None]]:
    """Install fake packages; the registry and spec model see them from then on.

    A package is a `.dist-info` folder with its entry points, and its modules, on `sys.path`.
    `importlib.metadata` finds it exactly as it finds a package installed with pip or uv, so
    tests that use it go through the real discovery.
    """

    def install_package(
        package: str,
        entry_points: dict[str, str],
        modules: dict[str, str] | None = None,
        version: str = "1.0",
        source_dir: Path | None = None,
    ) -> None:
        site = tmp_path / package
        dist_info = site / f"{package.replace('-', '_')}-{version}.dist-info"
        dist_info.mkdir(parents=True)
        (dist_info / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {package}\nVersion: {version}\n", encoding="utf-8"
        )
        lines = [f"[{ENTRY_POINT_GROUP}]"] + [f"{k} = {v}" for k, v in entry_points.items()]
        (dist_info / "entry_points.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        for module, source in (modules or {}).items():
            (site / f"{module}.py").write_text(source, encoding="utf-8")
        monkeypatch.syspath_prepend(str(site))
        if source_dir is not None:
            monkeypatch.syspath_prepend(str(source_dir))
        chart_registry.cache_clear()
        spec_model.cache_clear()

    yield install_package
    chart_registry.cache_clear()
    spec_model.cache_clear()


@pytest.fixture
def example_plugin(install: Callable[..., None]) -> None:
    """Install `examples/plugin` with the entry points its pyproject.toml declares."""
    project = tomllib.loads((EXAMPLE_PLUGIN / "pyproject.toml").read_text(encoding="utf-8"))
    install(
        project["project"]["name"],
        project["project"]["entry-points"][ENTRY_POINT_GROUP],
        version=project["project"]["version"],
        source_dir=EXAMPLE_PLUGIN / "src",
    )
