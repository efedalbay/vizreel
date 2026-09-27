import pytest

from vizreel.charts.waterfall import WaterfallBar, sequential_progress, waterfall_bars
from vizreel.errors import SpecError
from vizreel.spec.loader import parse_spec
from vizreel.spec.models import WaterfallChart


def waterfall(steps: str, extra: str = "") -> WaterfallChart:
    spec = parse_spec(
        "version: 1\ncharts:\n"
        "  - { id: w, type: waterfall, start: { label: Revenue, value: 12 }, "
        f"steps: [{steps}]{extra} }}",
        "spec.yaml",
    )
    chart = spec.charts[0]
    assert isinstance(chart, WaterfallChart)
    return chart


def waterfall_errors(steps: str, extra: str = "") -> list[str]:
    with pytest.raises(SpecError) as caught:
        waterfall(steps, extra)
    return [str(issue) for issue in caught.value.issues]


def test_the_total_is_called_total_unless_named() -> None:
    chart = waterfall("{ label: Costs, value: -5 }")

    assert chart.labels == ["Revenue", "Costs", "Total"]
    assert waterfall("{ label: Costs, value: -5 }", ", end: { label: Profit }").labels[-1] == (
        "Profit"
    )


def test_bars_run_from_the_start_through_each_step_to_the_total() -> None:
    chart = waterfall(
        "{ label: Salaries, value: -5 }, { label: Marketing, value: -2 }, "
        "{ label: Other, value: 0.5 }"
    )

    assert waterfall_bars(chart) == [
        WaterfallBar("Revenue", 0, 12, "total"),
        WaterfallBar("Salaries", 12, 7, "down"),
        WaterfallBar("Marketing", 7, 5, "down"),
        WaterfallBar("Other", 5, 5.5, "up"),
        WaterfallBar("Total", 0, 5.5, "total"),
    ]


def test_a_bar_shows_its_total_or_its_change() -> None:
    down = WaterfallBar("Salaries", 12, 7, "down")

    assert down.amount == -5
    assert down.top == 12


def test_a_running_total_below_zero_is_an_error() -> None:
    [message] = waterfall_errors("{ label: Costs, value: -5 }, { label: Loss, value: -9 }")

    assert message == (
        "charts[0].steps[1].value: the running total falls to -2 here; a waterfall stays at "
        "zero or above in version 1"
    )


def test_labels_must_be_unique_across_start_steps_and_end() -> None:
    messages = waterfall_errors(
        "{ label: Costs, value: -5 }, { label: Revenue, value: 1 }", ", end: { label: Costs }"
    )

    assert messages == [
        'charts[0].steps[1].label: "Revenue" is already used by start.label; labels must be unique',
        'charts[0].end.label: "Costs" is already used by steps[0].label; labels must be unique',
    ]


def test_the_highlight_must_match_a_bar() -> None:
    [message] = waterfall_errors("{ label: Costs, value: -5 }", ", highlight: { label: Tax }")

    assert message == (
        'charts[0].highlight.label: "Tax" does not match any bar. '
        'Labels: "Revenue", "Costs", "Total"'
    )


def test_at_most_six_steps() -> None:
    steps = ", ".join(f"{{ label: S{index}, value: 1 }}" for index in range(7))

    [message] = waterfall_errors(steps)

    assert message.startswith("charts[0].steps:")


def test_a_negative_start_is_an_error() -> None:
    with pytest.raises(SpecError) as caught:
        parse_spec(
            "version: 1\ncharts:\n  - { id: w, type: waterfall, "
            "start: { label: A, value: -1 }, steps: [{ label: B, value: 2 }] }",
            "spec.yaml",
        )
    [issue] = caught.value.issues

    assert str(issue).startswith("charts[0].start.value:")


@pytest.mark.parametrize(
    ("progress", "expected"),
    [(0.0, [0, 0, 0, 0]), (0.25, [1, 0, 0, 0]), (0.375, [1, 0.5, 0, 0]), (1.0, [1, 1, 1, 1])],
)
def test_items_run_one_after_another(progress: float, expected: list[float]) -> None:
    assert [sequential_progress(progress, index, 4) for index in range(4)] == pytest.approx(
        expected
    )
