import pytest

from vizreel.charts.stacked import stack_bounds
from vizreel.errors import SpecError
from vizreel.spec.loader import parse_spec
from vizreel.spec.models import StackedChart

CATEGORIES = '["2021", "2022", "2023"]'


def stacked(series: str, extra: str = "", categories: str = CATEGORIES) -> StackedChart:
    spec = parse_spec(
        "version: 1\ncharts:\n"
        f"  - {{ id: s, type: stacked, categories: {categories}, series: [{series}]{extra} }}",
        "spec.yaml",
    )
    chart = spec.charts[0]
    assert isinstance(chart, StackedChart)
    return chart


def stacked_errors(series: str, extra: str = "", categories: str = CATEGORIES) -> list[str]:
    with pytest.raises(SpecError) as caught:
        stacked(series, extra, categories)
    return [str(issue) for issue in caught.value.issues]


TWO_SERIES = "{ name: Cloud, values: [1, 2, 4] }, { name: Devices, values: [3, 3, 3] }"


def test_parts_stack_from_zero_to_each_total() -> None:
    chart = stacked(TWO_SERIES)

    assert stack_bounds(chart) == [
        [(0, 1), (0, 2), (0, 4)],
        [(1, 4), (2, 5), (4, 7)],
    ]
    assert chart.totals() == [4, 5, 7]


def test_each_series_has_one_value_per_category() -> None:
    [message] = stacked_errors(
        "{ name: Cloud, values: [1, 2] }, { name: Devices, values: [3, 3, 3] }"
    )

    assert message == (
        "charts[0].series[0].values: has 2 values but there are 3 categories; "
        "give one value per category"
    )


def test_categories_and_series_names_are_unique() -> None:
    messages = stacked_errors(
        "{ name: Cloud, values: [1, 2, 3] }, { name: Cloud, values: [3, 3, 3] }",
        categories='["2021", "2022", "2021"]',
    )

    assert messages == [
        'charts[0].categories[2]: "2021" is already used by categories[0]; categories must be '
        "unique",
        'charts[0].series[1].name: "Cloud" is already used by series[0]; series names must be '
        "unique",
    ]


def test_the_highlight_names_a_series() -> None:
    [message] = stacked_errors(TWO_SERIES, ", highlight: { series: Phones }")

    assert message == (
        'charts[0].highlight.series: "Phones" does not match any series. Series: "Cloud", "Devices"'
    )


@pytest.mark.parametrize(
    "series",
    [
        "{ name: A, values: [1, 2, 3] }",
        ", ".join(f"{{ name: S{index}, values: [1, 2, 3] }}" for index in range(4)),
    ],
)
def test_two_or_three_series(series: str) -> None:
    [message] = stacked_errors(series)

    assert message.startswith("charts[0].series:")


def test_negative_values_are_an_error() -> None:
    [message] = stacked_errors(
        "{ name: Cloud, values: [1, -2, 3] }, { name: Devices, values: [3, 3, 3] }"
    )

    assert message.startswith("charts[0].series[0].values[1]:")
