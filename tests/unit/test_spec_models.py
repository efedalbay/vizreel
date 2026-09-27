import pytest

from vizreel.errors import SpecError
from vizreel.spec.loader import parse_spec, spec_json_schema
from vizreel.spec.models import (
    BarChart,
    LineChart,
    Meta,
    NumberFormat,
    Spec,
    StatChart,
    TimelineChart,
)


def parse(charts_yaml: str) -> Spec:
    return parse_spec(f"version: 1\ncharts:\n{charts_yaml}", "test.yaml")


def error_messages(charts_yaml: str) -> list[str]:
    with pytest.raises(SpecError) as caught:
        parse(charts_yaml)
    return [str(issue) for issue in caught.value.issues]


def bars_yaml(count: int) -> str:
    bars = ", ".join(f"{{ label: B{i}, value: {i} }}" for i in range(count))
    return f"  - {{ id: b, type: bar, bars: [{bars}] }}"


def events_yaml(count: int) -> str:
    events = ", ".join(f'{{ date: "{2000 + i}", label: E{i} }}' for i in range(count))
    return f"  - {{ id: t, type: timeline, events: [{events}] }}"


def series_yaml(count: int) -> str:
    series = ", ".join(f"{{ name: S{i}, values: [1, 2] }}" for i in range(count))
    return f'  - {{ id: l, type: line, x: ["a", "b"], series: [{series}] }}'


def test_meta_defaults() -> None:
    spec = parse("  - { id: users, type: stat, value: 1 }")

    assert spec.meta == Meta(
        title=None,
        theme="default",
        resolution="1080p",
        aspect="16:9",
        fps=60,
        format="mov",
        locale="en-US",
    )


def test_meta_aspect_accepts_vertical_and_rejects_others() -> None:
    vertical = parse_spec(
        'version: 1\nmeta: { aspect: "9:16" }\ncharts: [{ id: a, type: stat, value: 1 }]', "t.yaml"
    )

    assert vertical.meta.aspect == "9:16"
    with pytest.raises(SpecError) as caught:
        parse_spec(
            'version: 1\nmeta: { aspect: "4:3" }\ncharts: [{ id: a, type: stat, value: 1 }]',
            "t.yaml",
        )
    [issue] = caught.value.issues
    assert str(issue).startswith("meta.aspect:")
    assert "16:9" in str(issue) and "9:16" in str(issue)


def test_charts_become_their_type_specific_models() -> None:
    spec = parse(
        "  - { id: s, type: stat, value: 1 }\n"
        '  - { id: l, type: line, x: ["a", "b"], series: [{ values: [1, 2] }] }\n'
        "  - { id: b, type: bar, bars: [{ label: A, value: 1 }, { label: B, value: 2 }] }\n"
        '  - { id: t, type: timeline, events: [{ date: "1", label: A }, { date: "2", label: B }] }'
    )

    assert [type(chart) for chart in spec.charts] == [StatChart, LineChart, BarChart, TimelineChart]


@pytest.mark.parametrize(
    ("chart_yaml", "duration"),
    [
        ("{ id: s, type: stat, value: 1 }", 3),
        ('{ id: l, type: line, x: ["a", "b"], series: [{ values: [1, 2] }] }', 6),
        ("{ id: b, type: bar, bars: [{ label: A, value: 1 }, { label: B, value: 2 }] }", 5),
        (
            '{ id: t, type: timeline, events: [{ date: "1", label: A }, { date: "2", label: B }] }',
            7,
        ),
    ],
)
def test_default_duration_depends_on_type(chart_yaml: str, duration: float) -> None:
    spec = parse(f"  - {chart_yaml}")

    assert spec.charts[0].duration == duration


def test_stat_defaults() -> None:
    chart = parse("  - { id: users, type: stat, value: 1200000 }").charts[0]

    assert isinstance(chart, StatChart)
    assert chart.start == 0
    assert chart.trend == "none"
    assert chart.number == NumberFormat(prefix="", suffix="", decimals=None, compact=False)


def test_integers_are_accepted_as_numbers() -> None:
    chart = parse("  - { id: users, type: stat, value: 1200000, duration: 4 }").charts[0]

    assert isinstance(chart, StatChart)
    assert chart.value == 1200000
    assert chart.duration == 4


def test_stat_has_no_highlight() -> None:
    assert error_messages('  - { id: s, type: stat, value: 1, highlight: { label: "x" } }') == [
        "charts[0].highlight: unknown field. Check the spelling against docs/SPEC.md"
    ]


def test_empty_text_is_rejected() -> None:
    assert error_messages('  - { id: s, type: stat, value: 1, title: "" }') == [
        "charts[0].title: must not be empty"
    ]


def test_prefix_and_suffix_may_be_empty() -> None:
    chart = parse('  - { id: s, type: stat, value: 1, number: { prefix: "", suffix: "" } }').charts[
        0
    ]

    assert isinstance(chart, StatChart)
    assert chart.number.prefix == ""


@pytest.mark.parametrize("count", [2, 8])
def test_bar_count_limits_accept(count: int) -> None:
    chart = parse(bars_yaml(count)).charts[0]

    assert isinstance(chart, BarChart)
    assert len(chart.bars) == count


@pytest.mark.parametrize(
    ("count", "message"),
    [(1, "expected at least 2 items, got 1"), (9, "expected at most 8 items, got 9")],
)
def test_bar_count_limits_reject(count: int, message: str) -> None:
    assert error_messages(bars_yaml(count)) == [f"charts[0].bars: {message}"]


@pytest.mark.parametrize("count", [2, 7])
def test_event_count_limits_accept(count: int) -> None:
    chart = parse(events_yaml(count)).charts[0]

    assert isinstance(chart, TimelineChart)
    assert len(chart.events) == count


@pytest.mark.parametrize(
    ("count", "message"),
    [(1, "expected at least 2 items, got 1"), (8, "expected at most 7 items, got 8")],
)
def test_event_count_limits_reject(count: int, message: str) -> None:
    assert error_messages(events_yaml(count)) == [f"charts[0].events: {message}"]


@pytest.mark.parametrize("count", [1, 3])
def test_series_count_limits_accept(count: int) -> None:
    chart = parse(series_yaml(count)).charts[0]

    assert isinstance(chart, LineChart)
    assert len(chart.series) == count


@pytest.mark.parametrize(
    ("count", "message"),
    [(0, "expected at least 1 item, got 0"), (4, "expected at most 3 items, got 4")],
)
def test_series_count_limits_reject(count: int, message: str) -> None:
    assert error_messages(series_yaml(count)) == [f"charts[0].series: {message}"]


def test_line_needs_two_x_labels() -> None:
    assert error_messages('  - { id: l, type: line, x: ["a"], series: [{ values: [1] }] }') == [
        "charts[0].x: expected at least 2 items, got 1"
    ]


def test_line_null_values_leave_gaps() -> None:
    chart = parse(
        '  - { id: l, type: line, x: ["a", "b", "c"], series: [{ values: [1, null, 3] }] }'
    ).charts[0]

    assert isinstance(chart, LineChart)
    assert chart.series[0].values == [1, None, 3]


def test_line_single_series_needs_no_name() -> None:
    chart = parse('  - { id: l, type: line, x: ["a", "b"], series: [{ values: [1, 2] }] }').charts[
        0
    ]

    assert isinstance(chart, LineChart)
    assert chart.series[0].name is None


def test_line_values_on_range_boundaries_are_allowed() -> None:
    chart = parse(
        '  - { id: l, type: line, x: ["a", "b"], y_min: 1, y_max: 2, series: [{ values: [1, 2] }] }'
    ).charts[0]

    assert isinstance(chart, LineChart)
    assert (chart.y_min, chart.y_max) == (1, 2)


def test_line_value_below_y_min() -> None:
    assert error_messages(
        '  - { id: l, type: line, x: ["a", "b"], y_min: 0, series: [{ values: [-1.5, 2] }] }'
    ) == ["charts[0].series[0].values[0]: -1.5 is below y_min (0)"]


def test_line_highlight_needs_x() -> None:
    assert error_messages(
        '  - { id: l, type: line, x: ["a", "b"], series: [{ values: [1, 2] }], '
        'highlight: { label: "Peak" } }'
    ) == ["charts[0].highlight.x: required field is missing"]


def test_line_highlight_on_existing_point() -> None:
    chart = parse(
        '  - { id: l, type: line, x: ["a", "b"], series: [{ values: [1, 2] }], '
        'highlight: { x: "b", label: "Peak" } }'
    ).charts[0]

    assert isinstance(chart, LineChart)
    assert chart.highlight is not None
    assert chart.highlight.x == "b"


def test_bar_zero_value_is_allowed() -> None:
    chart = parse(
        "  - { id: b, type: bar, bars: [{ label: A, value: 0 }, { label: B, value: 2 }] }"
    )

    assert isinstance(chart.charts[0], BarChart)


def test_timeline_single_emphasis_is_allowed() -> None:
    chart = parse(
        '  - { id: t, type: timeline, events: [{ date: "1", label: A, emphasis: true }, '
        '{ date: "2", label: B }] }'
    ).charts[0]

    assert isinstance(chart, TimelineChart)
    assert [event.emphasis for event in chart.events] == [True, False]


def test_json_schema_lists_every_chart_type() -> None:
    schema = spec_json_schema()

    discriminator = schema["properties"]["charts"]["items"]["discriminator"]
    assert discriminator["propertyName"] == "type"
    assert sorted(discriminator["mapping"]) == [
        "bar",
        "compare",
        "line",
        "stacked",
        "stat",
        "timeline",
        "waterfall",
    ]
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_json_schema_includes_field_descriptions() -> None:
    schema = spec_json_schema()

    theme = schema["$defs"]["Meta"]["properties"]["theme"]
    assert theme["description"].startswith("Built-in theme name")
    assert schema["$defs"]["StatChart"]["properties"]["id"]["pattern"] == "^[a-z0-9-]+$"
