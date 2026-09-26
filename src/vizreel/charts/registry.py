"""The only place that maps `type:` strings to chart type classes."""

import importlib
import pkgutil
from functools import cache
from typing import TypeVar, get_args

from vizreel.charts.base import ChartType
from vizreel.spec.models import BaseChart

ChartTypeT = TypeVar("ChartTypeT", bound=type[ChartType])


class ChartRegistry:
    """A set of chart types, looked up by their `type:` name."""

    def __init__(self) -> None:
        self._types: dict[str, type[ChartType]] = {}

    def register(self, chart_type: ChartTypeT) -> ChartTypeT:
        """Add a chart type. Usable as a class decorator.

        Raises:
            ValueError: The name is already registered.
            TypeError: The model's `type` field does not match the chart type's name, or the
                chart type has no template.
        """
        name = chart_type.name
        if name in self._types:
            raise ValueError(f"chart type {name!r} is already registered")
        type_field = chart_type.model.model_fields["type"]
        if get_args(type_field.annotation) != (name,):
            model_name = chart_type.model.__name__
            raise TypeError(f"{model_name}.type must be Literal[{name!r}] to match its chart type")
        if not getattr(chart_type, "template", "").strip():
            raise TypeError(f"chart type {name!r} needs a template for `vizreel new`")
        self._types[name] = chart_type
        return chart_type

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

    def names(self) -> list[str]:
        """Return every registered name, sorted."""
        return sorted(self._types)

    def models(self) -> list[type[BaseChart]]:
        """Return the spec model of every registered chart type, sorted by name."""
        return [self._types[name].model for name in self.names()]


_builtin_registry = ChartRegistry()


def register(chart_type: ChartTypeT) -> ChartTypeT:
    """Register a built-in chart type. Used as a class decorator in `vizreel.charts`."""
    return _builtin_registry.register(chart_type)


def builtin_registry() -> ChartRegistry:
    """Return the registry of built-in chart types, importing their modules on first use."""
    _import_chart_modules()
    return _builtin_registry


@cache
def _import_chart_modules() -> None:
    import vizreel.charts as package

    for module in pkgutil.iter_modules(package.__path__):
        if not module.name.startswith("_"):
            importlib.import_module(f"{package.__name__}.{module.name}")
