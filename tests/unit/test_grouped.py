from pathlib import Path

import pytest

from vizreel.charts.grouped import group_offsets
from vizreel.errors import SpecError
from vizreel.spec.loader import parse_spec
from vizreel.spec.models import GroupedChart

CATEGORIES = "[North, South, East]"


def grouped(series: str, extra: str = "", categories: str = CATEGORIES) -> GroupedChart:
    spec = parse_spec(
        "version: 1\ncharts:\n"
        f"  - {{ id: g, type: grouped, categories: {categories}, series: [{series}]{extra} }}",
        "spec.yaml",
    )
    chart = spec.charts[0]
    assert isinstance(chart, GroupedChart)
    return chart


def grouped_errors(series: str, extra: str = "", categories: str = CATEGORIES) -> list[str]:
    with pytest.raises(SpecError) as caught:
        grouped(series, extra, categories)
    return [str(issue) for issue in caught.value.issues]


TWO_SERIES = '{ name: "2022", values: [310, 240, 150] }, { name: "2023", values: [412, 298, 188] }'


def test_a_grouped_chart_takes_categories_and_series() -> None:
    chart = grouped(TWO_SERIES, ', highlight: { series: "2023" }')

    assert chart.categories == ["North", "South", "East"]
    assert [series.name for series in chart.series] == ["2022", "2023"]
    assert chart.layout == "auto"
    assert chart.duration == 6


def test_each_series_has_one_value_per_category() -> None:
    [message] = grouped_errors("{ name: A, values: [1, 2] }, { name: B, values: [3, 3, 3] }")

    assert message == (
        "charts[0].series[0].values: has 2 values but there are 3 categories; "
        "give one value per category"
    )


def test_categories_and_series_names_are_unique() -> None:
    messages = grouped_errors(
        "{ name: A, values: [1, 2, 3] }, { name: A, values: [3, 3, 3] }",
        categories="[North, South, North]",
    )

    assert messages == [
        'charts[0].categories[2]: "North" is already used by categories[0]; categories must '
        "be unique",
        'charts[0].series[1].name: "A" is already used by series[0]; series names must be unique',
    ]


def test_the_highlight_and_the_sequence_name_a_series() -> None:
    assert grouped_errors(TWO_SERIES, ", highlight: { series: Phones }") == [
        'charts[0].highlight.series: "Phones" does not match any series. Series: "2022", "2023"'
    ]
    assert grouped_errors(TWO_SERIES, ', sequence: ["2022", "2024"]') == [
        'charts[0].sequence[1]: "2024" does not match any series name. Choose from: "2022", "2023"'
    ]


@pytest.mark.parametrize(
    ("series", "categories", "location"),
    [
        ("{ name: A, values: [1, 2, 3] }", CATEGORIES, "charts[0].series:"),
        (
            ", ".join(f"{{ name: S{index}, values: [1, 2, 3] }}" for index in range(4)),
            CATEGORIES,
            "charts[0].series:",
        ),
        (TWO_SERIES, "[North]", "charts[0].categories:"),
        (
            "{ name: A, values: [1, 2, 3, 4, 5, 6, 7] }, "
            "{ name: B, values: [1, 2, 3, 4, 5, 6, 7] }",
            "[a, b, c, d, e, f, g]",
            "charts[0].categories:",
        ),
    ],
)
def test_two_or_three_series_and_two_to_six_categories(
    series: str, categories: str, location: str
) -> None:
    [message] = grouped_errors(series, categories=categories)

    assert message.startswith(location)


def test_negative_values_are_an_error() -> None:
    [message] = grouped_errors("{ name: A, values: [1, -2, 3] }, { name: B, values: [3, 3, 3] }")

    assert message.startswith("charts[0].series[0].values[1]:")


def test_bars_of_a_group_sit_side_by_side_around_its_center() -> None:
    assert group_offsets(2, 2.0) == [-0.5, 0.5]
    assert group_offsets(3, 3.0) == [-1.0, 0.0, 1.0]


def test_a_grouped_chart_reads_its_data_from_a_file(tmp_path: Path) -> None:
    (tmp_path / "data.csv").write_text("Region,2022,2023\nNorth,310,412\nSouth,240,298\n")
    spec = parse_spec(
        "version: 1\ncharts:\n  - { id: g, type: grouped, data: data.csv }\n", "s.yaml", tmp_path
    )
    chart = spec.charts[0]

    assert isinstance(chart, GroupedChart)
    assert chart.categories == ["North", "South"]
    assert [(series.name, series.values) for series in chart.series] == [
        ("2022", [310, 240]),
        ("2023", [412, 298]),
    ]
