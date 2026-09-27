from pathlib import Path

import pytest

from vizreel.charts.base import Continuation
from vizreel.errors import SpecError
from vizreel.render.engine import FrameSettings, RenderOptions, output_paths, plan_clips
from vizreel.spec.loader import parse_spec
from vizreel.spec.models import (
    BarChart,
    BaseChart,
    LineChart,
    LineHighlight,
    SequencedChart,
    TimelineChart,
)

BARS = "bars: [{ label: A, value: 1 }, { label: B, value: 2 }, { label: C, value: 3 }]"


def chart(yaml: str) -> BaseChart:
    return parse_spec(f"version: 1\ncharts:\n  - {{ id: c, {yaml} }}", "spec.yaml").charts[0]


def errors(yaml: str) -> list[str]:
    with pytest.raises(SpecError) as caught:
        chart(yaml)
    return [str(issue) for issue in caught.value.issues]


@pytest.mark.parametrize(
    ("yaml", "item"),
    [
        (f"type: bar, {BARS}", "B"),
        ("type: timeline, events: [{ date: Spring, label: A }, { date: Fall, label: B }]", "Fall"),
        ("type: line, x: [a, b], series: [{ values: [1, 2] }]", "b"),
        (
            "type: waterfall, start: { label: S, value: 5 }, steps: [{ label: D, value: -1 }]",
            "D",
        ),
        (
            "type: stacked, categories: [x, y], series: [{ name: P, values: [1, 2] }, "
            "{ name: Q, values: [3, 4] }]",
            "Q",
        ),
        ("type: share, parts: [{ label: P, value: 1 }, { label: Q, value: 2 }]", "P"),
        ("type: table, columns: [{ name: N }, { name: V }], rows: [[P, 1], [Q, 2]]", "Q"),
    ],
)
def test_every_chart_with_a_highlight_can_be_a_sequence(yaml: str, item: str) -> None:
    sequenced = chart(f"{yaml}, sequence: [{item}, {item}]")

    assert isinstance(sequenced, SequencedChart)
    assert sequenced.sequence == [item, item]
    assert sequenced.step_duration == 3
    assert not sequenced.has_highlight()
    assert sequenced.with_highlight(item).has_highlight()


@pytest.mark.parametrize(
    "yaml",
    [
        "type: stat, value: 1",
        "type: compare, before: { label: A, value: 1 }, after: { label: B, value: 2 }",
    ],
)
def test_charts_without_a_highlight_have_no_sequence(yaml: str) -> None:
    [message] = errors(f"{yaml}, sequence: [a, b]")

    assert message.startswith("charts[0].sequence:")


def test_sequence_items_must_name_an_element() -> None:
    [message] = errors(f"type: bar, {BARS}, sequence: [A, Z]")

    assert message == (
        'charts[0].sequence[1]: "Z" does not match any bar label. Choose from: "A", "B", "C"'
    )


def test_a_sequence_and_a_highlight_do_not_go_together() -> None:
    [message] = errors(f"type: bar, {BARS}, sequence: [A, B], highlight: {{ label: A }}")

    assert message.startswith("charts[0].sequence: cannot be used together with a highlight")


def test_a_timeline_sequence_and_an_emphasized_event_do_not_go_together() -> None:
    messages = errors(
        'type: timeline, events: [{ date: "1", label: A, emphasis: true }, '
        '{ date: "2", label: B }], sequence: ["1", "2"]'
    )

    assert messages[0].startswith("charts[0].sequence: cannot be used together")


def test_a_timeline_date_used_twice_cannot_be_named() -> None:
    [message] = errors(
        'type: timeline, events: [{ date: "1", label: A }, { date: "1", label: B }, '
        '{ date: "2", label: C }], sequence: ["1", "2"]'
    )

    assert message == ('charts[0].sequence[0]: "1" does not match any event date. Choose from: "2"')


def test_a_line_sequence_names_points_with_values_and_may_add_callouts() -> None:
    line = chart(
        "type: line, x: [a, b, c], series: [{ values: [1, null, 3] }], "
        "sequence: [a, { x: c, label: Peak }]"
    )
    assert isinstance(line, LineChart)

    assert line.sequence == ["a", LineHighlight(x="c", label="Peak")]
    assert line.with_highlight("a").highlight == LineHighlight(x="a")
    assert errors(
        "type: line, x: [a, b, c], series: [{ values: [1, null, 3] }], sequence: [a, b]"
    ) == ['charts[0].sequence[1]: "b" does not match any x label. Choose from: "a", "c"']


@pytest.mark.parametrize(("items", "valid"), [("[A]", False), ("[A, B]", True)])
def test_a_sequence_has_two_to_eight_items(items: str, valid: bool) -> None:
    yaml = f"type: bar, {BARS}, sequence: {items}"
    if valid:
        assert isinstance(chart(yaml), BarChart)
    else:
        assert errors(yaml)[0].startswith("charts[0].sequence:")


def test_step_duration_is_at_least_two_seconds() -> None:
    [message] = errors(f"type: bar, {BARS}, sequence: [A, B], step_duration: 1")

    assert message.startswith("charts[0].step_duration:")


def test_a_chart_without_a_sequence_is_one_clip() -> None:
    bar = chart(f"type: bar, {BARS}")

    assert plan_clips(bar) == [plan_clips(bar)[0]]
    assert plan_clips(bar)[0].chart is bar
    assert plan_clips(bar)[0].step is None


def test_each_clip_of_a_sequence_continues_from_the_one_before() -> None:
    timeline = chart(
        'type: timeline, events: [{ date: "1", label: A }, { date: "2", label: B }, '
        '{ date: "3", label: C }], sequence: ["1", "3", "2"], step_duration: 4'
    )

    plans = plan_clips(timeline)

    def emphasized(plan_chart: BaseChart) -> list[str]:
        assert isinstance(plan_chart, TimelineChart)
        return [event.date for event in plan_chart.events if event.emphasis]

    assert [plan.step for plan in plans] == [1, 2, 3]
    assert [emphasized(plan.chart) for plan in plans] == [["1"], ["1"], ["3"]]
    assert [plan.continuation for plan in plans] == [
        None,
        Continuation("3", 4),
        Continuation("2", 4),
    ]


def test_clips_of_a_sequence_are_numbered_before_the_other_suffixes() -> None:
    vertical = FrameSettings(480, 854, 15, "mov", "9:16")

    assert output_paths("history", RenderOptions(quality="preview"), vertical, step=2) == (
        Path("out/history.2.vertical.preview.mov"),
        None,
    )
    assert output_paths("history", RenderOptions(), FrameSettings(1, 1, 60, "mov"), 1)[0] == (
        Path("out/history.1.mov")
    )
