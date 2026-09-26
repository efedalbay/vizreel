"""The contract every chart type implements."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from vizreel.spec.models import BaseChart

if TYPE_CHECKING:
    from manim import Scene


class ChartType(ABC):
    """A chart type: its spec model and how it builds itself on a Manim scene.

    Attributes:
        name: The `type:` value in the spec, e.g. "line".
        model: Pydantic model for this chart's fields.
    """

    name: ClassVar[str]
    model: ClassVar[type[BaseChart]]

    @abstractmethod
    def build(self, scene: "Scene") -> None:
        """Add mobjects and play animations on the given scene."""
