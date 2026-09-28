"""The only place that maps `type:` strings to chart type classes.

Built-in chart types register themselves with `@register`. Chart types from other packages are
found through the `vizreel.chart_types` entry point group; see `docs/PLUGINS.md`.
"""

import importlib
import pkgutil
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from importlib.metadata import EntryPoint, entry_points
from typing import TypeVar, get_args

from vizreel.charts.base import CHART_API_VERSION, ChartType
from vizreel.spec.models import BaseChart

ChartTypeT = TypeVar("ChartTypeT", bound=type[ChartType])

ENTRY_POINT_GROUP = "vizreel.chart_types"
"""The entry point group other packages list their chart types under."""

BUILT_IN = "built-in"
"""The source of the chart types that ship with vizreel."""


@dataclass(frozen=True)
class PluginProblem:
    """A chart type from another package that could not be loaded.

    Attributes:
        name: The entry point's name, which is the chart type's `type:` value.
        source: The package that provides it, e.g. "vizreel-progress 0.1.0".
        message: What went wrong, for the user.
    """

    name: str
    source: str
    message: str

    def __str__(self) -> str:
        return f'chart type "{self.name}" from {self.source} was not loaded: {self.message}'


class ChartRegistry:
    """A set of chart types, looked up by their `type:` name."""

    def __init__(self) -> None:
        self._types: dict[str, type[ChartType]] = {}
        self._sources: dict[str, str] = {}
        self.problems: list[PluginProblem] = []
        """Chart types from other packages that could not be loaded."""

    def register(self, chart_type: ChartTypeT, source: str = BUILT_IN) -> ChartTypeT:
        """Add a chart type. Usable as a class decorator.

        Args:
            chart_type: The chart type class.
            source: Where it comes from: "built-in", or a package name and version.

        Raises:
            ValueError: The name is already registered.
            TypeError: The model's `type` field does not match the chart type's name, or the
                chart type has no template.
        """
        name = chart_type.name
        if name in self._types:
            raise ValueError(f"chart type {name!r} is already registered ({self._sources[name]})")
        type_field = chart_type.model.model_fields["type"]
        if get_args(type_field.annotation) != (name,):
            model_name = chart_type.model.__name__
            raise TypeError(f"{model_name}.type must be Literal[{name!r}] to match its chart type")
        if not getattr(chart_type, "template", "").strip():
            raise TypeError(f"chart type {name!r} needs a template for `vizreel new`")
        self._types[name] = chart_type
        self._sources[name] = source
        return chart_type

    def load_plugins(self, found: Iterable[EntryPoint]) -> None:
        """Register the chart types these entry points name, in name order.

        A chart type that cannot be loaded is skipped and recorded in `problems`, so that a
        broken package does not stop vizreel.
        """
        for entry_point in sorted(found, key=lambda entry_point: entry_point.name):
            source = _source(entry_point)
            try:
                self.register(_load(entry_point), source)
            except Exception as exc:
                self.problems.append(PluginProblem(entry_point.name, source, _describe(exc)))

    def get(self, name: str) -> type[ChartType]:
        """Return the chart type registered under `name`.

        Raises:
            KeyError: No chart type has that name.
        """
        try:
            return self._types[name]
        except KeyError:
            raise KeyError(
                f"unknown chart type {name!r}; registered: {', '.join(self.names())}"
            ) from None

    def unknown_type_hint(self, name: str) -> str:
        """Return why `name` may be missing: a package that provides it failed to load."""
        return "".join(f". The {problem}" for problem in self.problems if problem.name == name)

    def source(self, name: str) -> str:
        """Return where the chart type `name` comes from: "built-in" or its package."""
        return self._sources[name]

    def names(self) -> list[str]:
        """Return every registered name, sorted."""
        return sorted(self._types)

    def models(self) -> list[type[BaseChart]]:
        """Return the spec model of every registered chart type, sorted by name."""
        return [self._types[name].model for name in self.names()]


class _PluginError(Exception):
    """A chart type from another package breaks the chart type contract."""


def _load(entry_point: EntryPoint) -> type[ChartType]:
    try:
        loaded = entry_point.load()
    except Exception as exc:
        raise _PluginError(f"it could not be imported: {type(exc).__name__}: {exc}") from exc
    if not (isinstance(loaded, type) and issubclass(loaded, ChartType)):
        raise _PluginError(f"{entry_point.value} is not a ChartType subclass")
    if loaded.name != entry_point.name:
        raise _PluginError(
            f"the entry point is named {entry_point.name!r} but the chart type is {loaded.name!r}"
        )
    # ChartType's own value is for the built-in types; a plugin states the API it was written for.
    declaring = next(cls for cls in loaded.__mro__ if "api_version" in vars(cls))
    if declaring is ChartType:
        raise _PluginError("it does not declare api_version; see docs/PLUGINS.md")
    if loaded.api_version != CHART_API_VERSION:
        raise _PluginError(
            f"it was written for chart API {loaded.api_version}, and this vizreel has API "
            f"{CHART_API_VERSION}; install a version of the package made for it"
        )
    return loaded


def _describe(exc: Exception) -> str:
    if isinstance(exc, _PluginError):
        return str(exc)
    if isinstance(exc, (ValueError, TypeError)):
        return str(exc).replace("already registered (built-in)", "the name of a built-in type")
    return f"{type(exc).__name__}: {exc}"


def _source(entry_point: EntryPoint) -> str:
    dist = entry_point.dist
    return f"{dist.name} {dist.version}" if dist is not None else entry_point.value


_builtin_registry = ChartRegistry()


def register(chart_type: ChartTypeT) -> ChartTypeT:
    """Register a built-in chart type. Used as a class decorator in `vizreel.charts`."""
    return _builtin_registry.register(chart_type)


def builtin_registry() -> ChartRegistry:
    """Return the registry of built-in chart types, importing their modules on first use."""
    _import_chart_modules()
    return _builtin_registry


@cache
def chart_registry() -> ChartRegistry:
    """Return every chart type: the built-in ones, then those installed packages provide."""
    registry = ChartRegistry()
    builtins = builtin_registry()
    for name in builtins.names():
        registry.register(builtins.get(name))
    registry.load_plugins(entry_points(group=ENTRY_POINT_GROUP))
    return registry


@cache
def _import_chart_modules() -> None:
    import vizreel.charts as package

    for module in pkgutil.iter_modules(package.__path__):
        if not module.name.startswith("_"):
            importlib.import_module(f"{package.__name__}.{module.name}")
