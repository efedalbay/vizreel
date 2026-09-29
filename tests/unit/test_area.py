from pathlib import Path

import pytest

from vizreel.charts.area import band, label_anchor
from vizreel.errors import SpecError
from vizreel.spec.loader import parse_spec
from vizreel.spec.models import AreaChart

X = '["2020", "2021", "2022"]'
TWO_SERIES = "{ name: Web, values: [1, 2, 3] }, { name: Mobile, values: [2, 2, 1] }"


def area(series: str, extra: str = "", x: str = X) -> AreaChart:
    spec = parse_spec(
        f"version: 1\ncharts:\n  - {{ id: a, type: area, x: {x}, series: [{series}]{extra} }}",
        "spec.yaml",
    )
    chart = spec.charts[0]
    assert isinstance(chart, AreaChart)
    return chart


def area_errors(series: str, extra: str = "", x: str = X) -> list[str]:
    with pytest.raises(SpecError) as caught:
        area(series, extra, x)
    return [str(issue) for issue in caught.value.issues]


def test_overlapping_areas_fill_from_zero() -> None:
    chart = area(TWO_SERIES)

    assert chart.stack is False
    assert chart.tops() == [[1, 2, 3], [2, 2, 1]]
    assert chart.bottoms() == [[0, 0, 0], [0, 0, 0]]


def test_stacked_areas_sit_on_each_other() -> None:
    chart = area(TWO_SERIES, ", stack: true")

    assert chart.tops() == [[1, 2, 3], [3, 4, 4]]
    assert chart.bottoms() == [[0, 0, 0], [1, 2, 3]]


def test_a_single_series_needs_no_name() -> None:
    chart = area("{ values: [1, 2, 3] }")

    assert chart.series[0].name is None
    assert chart.sequence_names() == []


def test_every_series_has_one_value_per_x_label() -> None:
    assert area_errors("{ name: Web, values: [1, 2] }, { name: Mobile, values: [2, 2, 1] }") == [
        "charts[0].series[0].values: expected 3 values (same as x), got 2"
    ]


def test_gaps_and_negative_values_are_an_error() -> None:
    messages = area_errors("{ values: [1, null, -3] }")

    assert [message.split(":")[0] for message in messages] == [
        "charts[0].series[0].values[1]",
        "charts[0].series[0].values[2]",
    ]


def test_names_are_required_with_several_series_and_unique() -> None:
    assert area_errors("{ values: [1, 2, 3] }, { name: Web, values: [1, 2, 3] }") == [
        "charts[0].series[0].name: required when the chart has more than one series"
    ]
    assert area_errors("{ name: Web, values: [1, 2, 3] }, { name: Web, values: [1, 2, 3] }") == [
        'charts[0].series[1].name: "Web" is already used by series[0]; series names must be unique'
    ]


def test_x_labels_are_unique() -> None:
    [message] = area_errors(TWO_SERIES, x='["2020", "2021", "2020"]')

    assert message.startswith('charts[0].x[2]: "2020" is already used by x[0]')


def test_the_highlight_and_the_sequence_name_a_series() -> None:
    assert area_errors(TWO_SERIES, ", highlight: { series: Desktop }") == [
        'charts[0].highlight.series: "Desktop" does not match any series. Series: "Web", "Mobile"'
    ]
    assert area_errors(TWO_SERIES, ", sequence: [Web, Desktop]") == [
        'charts[0].sequence[1]: "Desktop" does not match any series name. Choose from: "Web", '
        '"Mobile"'
    ]


def test_one_to_three_series() -> None:
    four = ", ".join(f"{{ name: S{index}, values: [1, 2, 3] }}" for index in range(4))

    [message] = area_errors(four)

    assert message.startswith("charts[0].series:")


def test_an_area_is_outlined_along_its_top_then_back_along_its_bottom() -> None:
    tops = [(0.0, 3.0), (1.0, 4.0)]
    bottoms = [(0.0, 1.0), (1.0, 2.0)]

    assert band(tops, bottoms) == [(0.0, 3.0), (1.0, 4.0), (1.0, 2.0), (0.0, 1.0)]


def test_an_end_label_points_at_the_middle_of_a_stacked_band() -> None:
    assert label_anchor(4.0, 2.0, stack=True) == 3.0
    assert label_anchor(4.0, 0.0, stack=False) == 4.0


def test_an_area_chart_reads_its_data_from_a_file(tmp_path: Path) -> None:
    (tmp_path / "data.csv").write_text("Year,Web,Mobile\n2020,1.2,0.4\n2021,1.9,1.1\n")
    spec = parse_spec(
        "version: 1\ncharts:\n  - { id: a, type: area, data: data.csv }\n", "s.yaml", tmp_path
    )
    chart = spec.charts[0]

    assert isinstance(chart, AreaChart)
    assert chart.x == ["2020", "2021"]
    assert [(series.name, series.values) for series in chart.series] == [
        ("Web", [1.2, 1.9]),
        ("Mobile", [0.4, 1.1]),
    ]


def test_an_empty_cell_in_an_area_chart_file_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "data.csv").write_text("Year,Web\n2020,1.2\n2021,\n")

    with pytest.raises(SpecError) as caught:
        parse_spec(
            "version: 1\ncharts:\n  - { id: a, type: area, data: data.csv }\n", "s.yaml", tmp_path
        )

    assert [str(issue) for issue in caught.value.issues] == [
        'charts[0].data: data.csv, row 3, column "Web" is empty; write a number'
    ]
