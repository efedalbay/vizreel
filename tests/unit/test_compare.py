import pytest

from vizreel.charts.compare import ValueBlock, place_side_by_side, place_stacked
from vizreel.errors import RenderError, SpecError
from vizreel.spec.loader import parse_spec
from vizreel.spec.models import CompareChart

BLOCK = ValueBlock(ascent=1.0, depth=0.6)


def compare_chart(fields: str) -> CompareChart:
    spec = parse_spec(
        "version: 1\ncharts:\n"
        "  - { id: c, type: compare, before: { label: A, value: 10 }, "
        f"after: {{ label: B, value: 12 }}{fields} }}",
        "spec.yaml",
    )
    chart = spec.charts[0]
    assert isinstance(chart, CompareChart)
    return chart


def compare_errors(fields: str) -> list[str]:
    with pytest.raises(SpecError) as caught:
        compare_chart(fields)
    return [str(issue) for issue in caught.value.issues]


def test_defaults() -> None:
    chart = compare_chart("")

    assert (chart.change, chart.trend, chart.duration) == ("percent", "auto", 5)


def test_percent_change_from_zero_or_less_is_an_error() -> None:
    spec_text = (
        "version: 1\ncharts:\n  - { id: c, type: compare, "
        "before: { label: A, value: 0 }, after: { label: B, value: 5 } }"
    )
    with pytest.raises(SpecError) as caught:
        parse_spec(spec_text, "spec.yaml")
    [issue] = caught.value.issues

    assert str(issue) == (
        "charts[0].before.value: a percent change needs a value above zero, got 0; "
        "use change: absolute"
    )


def test_absolute_change_from_zero_is_fine() -> None:
    spec = parse_spec(
        "version: 1\ncharts:\n  - { id: c, type: compare, change: absolute, "
        "before: { label: A, value: 0 }, after: { label: B, value: 5 } }",
        "spec.yaml",
    )

    assert isinstance(spec.charts[0], CompareChart)


@pytest.mark.parametrize(
    ("fields", "location"),
    [(", change: ratio", "charts[0].change:"), (", trend: up", "charts[0].trend:")],
)
def test_unknown_change_or_trend_is_an_error(fields: str, location: str) -> None:
    [message] = compare_errors(fields)

    assert message.startswith(location)


def test_side_by_side_shares_a_baseline_around_the_arrow() -> None:
    placement = place_side_by_side(
        (0.0, 0.0),
        width=10.0,
        column_width=2.0,
        block=BLOCK,
        change_size=(1.0, 0.4),
        gap=0.5,
        min_arrow=3.0,
    )

    assert placement.before == pytest.approx((-(1.5 + 0.5 + 1.0), 0.8 - 1.0))
    assert placement.after == pytest.approx((1.5 + 0.5 + 1.0, 0.8 - 1.0))
    (start_x, start_y), (end_x, end_y) = placement.arrow
    assert (start_x, end_x) == pytest.approx((-1.5, 1.5))
    assert start_y == end_y == pytest.approx(-0.2 + 0.5)
    assert placement.change == pytest.approx((0.0, 0.3 + 0.5 + 0.2))


def test_a_long_change_lengthens_the_arrow() -> None:
    placement = place_side_by_side(
        (0.0, 0.0),
        width=10.0,
        column_width=2.0,
        block=BLOCK,
        change_size=(4.0, 0.4),
        gap=0.5,
        min_arrow=3.0,
    )

    (start_x, _), (end_x, _) = placement.arrow
    assert end_x - start_x == pytest.approx(5.0)


def test_values_too_wide_side_by_side_are_an_error() -> None:
    with pytest.raises(RenderError, match="too wide"):
        place_side_by_side(
            (0.0, 0.0),
            width=6.0,
            column_width=2.0,
            block=BLOCK,
            change_size=(0.0, 0.0),
            gap=0.5,
            min_arrow=3.0,
        )


def test_stacked_values_run_down_with_the_change_beside_the_arrow() -> None:
    placement = place_stacked(
        (0.0, 0.0),
        height=10.0,
        blocks=(BLOCK, BLOCK),
        change_size=(1.0, 0.4),
        gap=0.5,
        min_arrow=2.0,
    )
    total = 1.6 + 0.5 + 2.0 + 0.5 + 1.6

    assert placement.before == pytest.approx((0.0, total / 2 - 1.0))
    (_, arrow_top), (_, arrow_bottom) = placement.arrow
    assert arrow_top == pytest.approx(total / 2 - 1.6 - 0.5)
    assert arrow_top - arrow_bottom == pytest.approx(2.0)
    assert placement.after == pytest.approx((0.0, arrow_bottom - 0.5 - 1.0))
    assert placement.change == pytest.approx((0.5 + 0.5, (arrow_top + arrow_bottom) / 2))


def test_stacked_values_too_tall_are_an_error() -> None:
    with pytest.raises(RenderError, match="not enough room"):
        place_stacked(
            (0.0, 0.0),
            height=4.0,
            blocks=(BLOCK, BLOCK),
            change_size=(0.0, 0.0),
            gap=0.5,
            min_arrow=2.0,
        )
