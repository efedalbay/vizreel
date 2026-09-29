from pathlib import Path

import pytest

from vizreel.charts.progress import filled_share
from vizreel.errors import SpecError
from vizreel.spec.loader import parse_spec
from vizreel.spec.models import ProgressChart


def progress(fields: str) -> ProgressChart:
    spec = parse_spec(f"version: 1\ncharts:\n  - {{ id: p, type: progress, {fields} }}", "s.yaml")
    chart = spec.charts[0]
    assert isinstance(chart, ProgressChart)
    return chart


def progress_errors(fields: str) -> list[str]:
    with pytest.raises(SpecError) as caught:
        progress(fields)
    return [str(issue) for issue in caught.value.issues]


def test_a_progress_chart_is_a_bar_by_default() -> None:
    chart = progress("value: 68000, goal: 100000")

    assert chart.style == "bar"
    assert chart.duration == 4


def test_the_value_is_zero_or_more_and_the_goal_above_zero() -> None:
    assert progress_errors("value: -1, goal: 0") == [
        "charts[0].value: must be at least 0, got -1",
        "charts[0].goal: must be greater than 0, got 0",
    ]


def test_the_style_is_bar_or_ring() -> None:
    [message] = progress_errors("value: 1, goal: 2, style: gauge")

    assert message.startswith("charts[0].style: expected one of")


def test_a_progress_chart_does_not_take_a_sequence_or_a_highlight() -> None:
    messages = progress_errors("value: 1, goal: 2, sequence: [a, b], highlight: { label: a }")

    assert [message.split(":")[0] for message in messages] == [
        "charts[0].sequence",
        "charts[0].highlight",
    ]


def test_the_fill_is_the_value_share_of_the_goal_at_most_all() -> None:
    assert filled_share(68, 100) == pytest.approx(0.68)
    assert filled_share(0, 100) == 0
    assert filled_share(150, 100) == 1


def test_a_progress_chart_does_not_read_a_data_file(tmp_path: Path) -> None:
    (tmp_path / "data.csv").write_text("Value,Goal\n1,2\n")

    with pytest.raises(SpecError) as caught:
        parse_spec(
            "version: 1\ncharts:\n  - { id: p, type: progress, value: 1, goal: 2, data: data.csv }",
            "s.yaml",
            tmp_path,
        )

    assert [str(issue) for issue in caught.value.issues] == [
        "charts[0].data: data.csv cannot be used: progress charts do not read data from a file"
    ]
