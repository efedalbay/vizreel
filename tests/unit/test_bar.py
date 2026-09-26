import pytest

from vizreel.charts.bar import sorted_bars
from vizreel.spec.loader import parse_spec
from vizreel.spec.models import BarChart


def bar_chart(sort: str) -> BarChart:
    spec = parse_spec(
        "version: 1\ncharts:\n"
        f"  - {{ id: b, type: bar, sort: {sort}, bars: "
        "[{ label: A, value: 2 }, { label: B, value: 9 }, { label: C, value: 2 }, "
        "{ label: D, value: 5 }] }",
        "spec.yaml",
    )
    chart = spec.charts[0]
    assert isinstance(chart, BarChart)
    return chart


@pytest.mark.parametrize(
    ("sort", "order"),
    [("none", "ABCD"), ("asc", "ACDB"), ("desc", "BDAC")],
)
def test_sorted_bars_keeps_ties_in_spec_order(sort: str, order: str) -> None:
    assert "".join(bar.label for bar in sorted_bars(bar_chart(sort))) == order
