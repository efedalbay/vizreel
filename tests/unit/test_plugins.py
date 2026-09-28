"""Chart types from other packages, found through entry points.

Each test lays out a fake installed package on `sys.path`: a module and a `.dist-info` folder
with its entry points. `importlib.metadata` finds it exactly as it finds a package installed
with pip or uv, so these tests go through the real discovery.
"""

import importlib
import subprocess
import sys
import textwrap
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from vizreel.charts.registry import ENTRY_POINT_GROUP, chart_registry
from vizreel.cli import app
from vizreel.errors import SpecError, UsageError
from vizreel.render import engine
from vizreel.spec.loader import parse_spec, spec_json_schema, spec_model
from vizreel.spec.templates import spec_template
from vizreel.themes.loader import load_theme

Install = Callable[..., None]

runner = CliRunner(env={"FORCE_COLOR": None, "TTY_COMPATIBLE": None})


def chart_module(name: str, *, api_version: str = "CHART_API_VERSION", extra: str = "") -> str:
    """Source of a module with a small valid chart type called `name`."""
    title = name.title().replace("-", "")
    return textwrap.dedent(f"""\
        from typing import Literal

        from vizreel.plugin import CHART_API_VERSION, BaseChart, ChartType, Duration


        class {title}Chart(BaseChart):
            type: Literal["{name}"]
            duration: Duration = 3
            value: float


        class {title}ChartType(ChartType):
            \"\"\"A {name} chart.\"\"\"

            name = "{name}"
            model = {title}Chart
            template = "- id: example\\n  type: {name}\\n  value: 1\\n"
            api_version = {api_version}

            def build(self, scene):
                pass
        {extra}""")


@pytest.fixture
def install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Install]:
    """Install fake packages; the registry and spec model see them from then on."""

    def install_package(
        package: str, entry_points: dict[str, str], modules: dict[str, str], version: str = "1.0"
    ) -> None:
        site = tmp_path / package
        dist_info = site / f"{package.replace('-', '_')}-{version}.dist-info"
        dist_info.mkdir(parents=True)
        (dist_info / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {package}\nVersion: {version}\n", encoding="utf-8"
        )
        lines = [f"[{ENTRY_POINT_GROUP}]"] + [f"{k} = {v}" for k, v in entry_points.items()]
        (dist_info / "entry_points.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        for module, source in modules.items():
            (site / f"{module}.py").write_text(source, encoding="utf-8")
        monkeypatch.syspath_prepend(str(site))
        chart_registry.cache_clear()
        spec_model.cache_clear()

    yield install_package
    chart_registry.cache_clear()
    spec_model.cache_clear()


def test_a_chart_type_from_a_package_is_registered(install: Install) -> None:
    install("vizreel-dot", {"dot": "fake_dot:DotChartType"}, {"fake_dot": chart_module("dot")})

    registry = chart_registry()

    assert "dot" in registry.names()
    assert registry.source("dot") == "vizreel-dot 1.0"
    assert registry.source("bar") == "built-in"
    assert registry.problems == []


def test_a_chart_type_from_a_package_validates_and_has_a_template_and_schema(
    install: Install,
) -> None:
    install("vizreel-dot", {"dot": "fake_dot2:DotChartType"}, {"fake_dot2": chart_module("dot")})

    spec = parse_spec("version: 1\ncharts:\n  - { id: a, type: dot, value: 2 }\n", "spec.yaml")
    template = spec_template("dot")

    assert spec.charts[0].type == "dot"
    assert "It comes from vizreel-dot 1.0" in template
    parse_spec(template, "template")
    assert "DotChart" in spec_json_schema()["$defs"]


def test_a_package_whose_chart_type_cannot_be_imported_is_skipped(install: Install) -> None:
    broken = "import vizreel_missing_dependency\n"
    install("vizreel-broken", {"broken": "fake_broken:X"}, {"fake_broken": broken})

    [problem] = chart_registry().problems

    assert "broken" not in chart_registry().names()
    assert problem.name == "broken"
    assert problem.source == "vizreel-broken 1.0"
    assert "could not be imported: ModuleNotFoundError" in problem.message


def test_an_unknown_type_names_the_package_that_failed_to_load(install: Install) -> None:
    install("vizreel-broken", {"broken": "fake_broken2:X"}, {"fake_broken2": "raise OSError()\n"})

    with pytest.raises(SpecError) as caught:
        parse_spec("version: 1\ncharts:\n  - { id: a, type: broken }\n", "spec.yaml")
    with pytest.raises(UsageError, match="from vizreel-broken 1.0 was not loaded"):
        spec_template("broken")

    [issue] = [str(issue) for issue in caught.value.issues]
    assert 'unknown type "broken"' in issue
    assert 'chart type "broken" from vizreel-broken 1.0 was not loaded' in issue


@pytest.mark.parametrize(
    ("entry_point", "module", "message"),
    [
        (
            "fake_bar:BarChartType",
            chart_module("bar"),
            "chart type 'bar' is the name of a built-in type",
        ),
        (
            "fake_old:OldChartType",
            chart_module("old", api_version="0"),
            "written for chart API 0, and this vizreel has API 1",
        ),
        (
            "fake_bare:BareChartType",
            chart_module("bare").replace("    api_version = CHART_API_VERSION\n", ""),
            "does not declare api_version",
        ),
        (
            "fake_plain:thing",
            "thing = 42\n",
            "fake_plain:thing is not a ChartType subclass",
        ),
        (
            "fake_named:NamedChartType",
            chart_module("named"),
            "the entry point is named 'other' but the chart type is 'named'",
        ),
        (
            "fake_empty:EmptyChartType",
            chart_module("empty").replace('template = "', 'template = ""\n    _ = "'),
            "needs a template",
        ),
    ],
    ids=[
        "built-in-name",
        "old-api",
        "no-api-version",
        "not-a-chart-type",
        "misnamed",
        "no-template",
    ],
)
def test_a_chart_type_that_breaks_the_contract_is_skipped(
    install: Install, entry_point: str, module: str, message: str
) -> None:
    name = "other" if "named" in entry_point else entry_point.split(":")[0].removeprefix("fake_")
    install("vizreel-bad", {name: entry_point}, {entry_point.split(":")[0]: module})

    [problem] = chart_registry().problems

    assert message in problem.message
    assert chart_registry().source("bar") == "built-in"


def test_one_broken_package_does_not_stop_another(install: Install) -> None:
    install("vizreel-broken", {"broken": "fake_broken3:X"}, {"fake_broken3": "1/0\n"})
    install("vizreel-dot", {"dot": "fake_dot3:DotChartType"}, {"fake_dot3": chart_module("dot")})

    registry = chart_registry()

    assert "dot" in registry.names()
    assert [problem.name for problem in registry.problems] == ["broken"]


def test_types_command_lists_sources_and_warns_about_broken_packages(install: Install) -> None:
    install("vizreel-broken", {"broken": "fake_broken4:X"}, {"fake_broken4": "1/0\n"})
    install("vizreel-dot", {"dot": "fake_dot4:DotChartType"}, {"fake_dot4": chart_module("dot")})

    result = runner.invoke(app, ["types"])

    assert result.exit_code == 0
    lines = result.stdout.splitlines()
    assert any(line.split()[:3] == ["dot", "vizreel-dot", "1.0"] for line in lines)
    assert any(line.split()[:2] == ["bar", "built-in"] for line in lines)
    assert "warning:" in result.stderr
    assert "vizreel-broken 1.0 was not loaded: it could not be imported" in result.stderr


def test_an_unexpected_error_in_a_plugin_names_its_package(
    install: Install, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install("vizreel-dot", {"dot": "fake_dot5:DotChartType"}, {"fake_dot5": chart_module("dot")})
    spec = parse_spec("version: 1\ncharts:\n  - { id: a, type: dot, value: 2 }\n", "spec.yaml")

    def fail(*args: object) -> None:
        raise ZeroDivisionError("division by zero")

    monkeypatch.setattr(engine, "render_chart", fail)
    result = engine._render_safely(
        engine.ClipPlan(spec.charts[0]),
        None,
        load_theme("default", tmp_path),
        engine.locale_for("en-US"),
        engine.FrameSettings(854, 480, 15, "mov"),
        engine.RenderOptions(out_dir=tmp_path),
        reraise=False,
    )

    assert result.error == (
        "unexpected error in chart type dot from vizreel-dot 1.0: "
        "ZeroDivisionError: division by zero"
    )


def test_the_plugin_api_does_not_import_manim() -> None:
    code = "import sys, vizreel.plugin; print('manim' in sys.modules)"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )

    assert result.stdout.strip() == "False"


@pytest.mark.parametrize("module", ["vizreel.plugin", "vizreel.plugin.render"])
def test_every_public_name_of_the_plugin_api_exists(module: str) -> None:
    imported = importlib.import_module(module)

    assert imported.__all__
    assert all(hasattr(imported, name) for name in imported.__all__)
