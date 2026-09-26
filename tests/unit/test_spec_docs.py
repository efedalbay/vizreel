"""Every spec example in the public docs must validate, so the docs cannot drift from the code."""

import re
import textwrap
from pathlib import Path

import pytest

from vizreel.spec.loader import load_spec, parse_spec

ROOT = Path(__file__).parents[2]
YAML_BLOCK = re.compile(r"```yaml\n(.*?)```", re.DOTALL)


def spec_examples(path: Path) -> list[str]:
    """Return each YAML block that is a full spec or a list of charts, as a full spec."""
    examples = []
    for block in YAML_BLOCK.findall(path.read_text(encoding="utf-8")):
        if block.startswith("version:"):
            examples.append(block)
        elif block.startswith("- id:"):
            examples.append("version: 1\ncharts:\n" + textwrap.indent(block, "  "))
    return examples


SPEC_EXAMPLES = spec_examples(ROOT / "docs" / "SPEC.md")
README_EXAMPLES = spec_examples(ROOT / "README.md")


def test_examples_are_found() -> None:
    assert len(SPEC_EXAMPLES) == 5
    assert len(README_EXAMPLES) == 1


@pytest.mark.parametrize("example", SPEC_EXAMPLES)
def test_spec_md_example_is_valid(example: str) -> None:
    parse_spec(example, "docs/SPEC.md")


@pytest.mark.parametrize("example", README_EXAMPLES)
def test_readme_example_is_valid(example: str) -> None:
    parse_spec(example, "README.md")


def test_showcase_is_valid() -> None:
    spec = load_spec(ROOT / "examples" / "showcase.yaml")

    assert sorted(chart.type for chart in spec.charts) == ["bar", "line", "stat", "timeline"]
