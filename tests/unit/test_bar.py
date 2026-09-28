from pathlib import Path

import pytest

from vizreel.charts._bars import MAX_ROW_GAP, by_bar_layout, plan_rows
from vizreel.charts.bar import sorted_bars
from vizreel.errors import RenderError, SpecError
from vizreel.render.layout import BAR_FILL, build_layout
from vizreel.spec.loader import parse_spec
from vizreel.spec.models import BarChart
from vizreel.themes.loader import load_theme

SIZES = load_theme("default", Path(".")).sizes
NO_TEXT = {"title_lines": 0, "subtitle_lines": 0, "source_lines": 0}


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


def chart_with_layout(layout: str) -> BarChart:
    spec = parse_spec(
        "version: 1\ncharts:\n"
        f"  - {{ id: b, type: bar, layout: {layout}, "
        "bars: [{ label: A, value: 1 }, { label: B, value: 2 }] }",
        "spec.yaml",
    )
    chart = spec.charts[0]
    assert isinstance(chart, BarChart)
    return chart


@pytest.mark.parametrize(
    ("layout", "landscape", "vertical"),
    [("auto", False, True), ("columns", False, False), ("rows", True, True)],
)
def test_layout_picks_rows_or_columns(layout: str, landscape: bool, vertical: bool) -> None:
    chart = chart_with_layout(layout)

    def rows_in(aspect: str) -> bool:
        frame = build_layout(SIZES, aspect=aspect, panel=True, **NO_TEXT)  # type: ignore[arg-type]
        return by_bar_layout(chart.layout, frame, lambda: False, lambda: True)

    assert rows_in("16:9") is landscape
    assert rows_in("9:16") is vertical
    assert rows_in("1:1") is (layout == "rows")


def test_a_square_frame_falls_back_to_rows_when_columns_do_not_fit() -> None:
    frame = build_layout(SIZES, aspect="1:1", panel=True, **NO_TEXT)

    def columns() -> str:
        raise RenderError("too wide")

    assert by_bar_layout("auto", frame, columns, lambda: "rows") == "rows"
    with pytest.raises(RenderError):
        by_bar_layout("columns", frame, columns, lambda: "rows")


def test_unknown_layout_is_rejected() -> None:
    with pytest.raises(SpecError) as caught:
        chart_with_layout("grid")
    [issue] = caught.value.issues
    assert str(issue).startswith("charts[0].layout:")


THICKNESS = (0.1, 0.5)


def test_rows_share_the_height_and_keep_their_order() -> None:
    rows = plan_rows(
        4, top=4.0, bottom=-4.0, label_height=0.3, label_gap=0.1, thickness_range=(0.1, 9)
    )

    thickness = (2.0 - 0.4) * BAR_FILL
    assert [row.thickness for row in rows] == pytest.approx([thickness] * 4)
    pitches = [a.label_top - b.label_top for a, b in zip(rows, rows[1:], strict=False)]
    assert pitches == pytest.approx([2.0] * 3)
    last_bottom = rows[-1].bar_center - thickness / 2
    assert rows[0].label_top == pytest.approx(-last_bottom)
    assert rows[0].label_top <= 4.0


def test_few_rows_stay_together_in_the_middle() -> None:
    rows = plan_rows(
        2, top=6.0, bottom=-6.0, label_height=0.3, label_gap=0.1, thickness_range=THICKNESS
    )
    row_height = 0.3 + 0.1 + 0.5

    assert [row.thickness for row in rows] == [0.5, 0.5]
    assert rows[0].label_top - rows[1].label_top == pytest.approx(row_height * (1 + MAX_ROW_GAP))
    top = rows[0].label_top
    bottom = rows[1].bar_center - 0.25
    assert (top + bottom) / 2 == pytest.approx(0.0)


def test_rows_that_would_be_too_thin_are_an_error() -> None:
    with pytest.raises(RenderError, match="not enough room"):
        plan_rows(
            8, top=1.0, bottom=-1.0, label_height=0.2, label_gap=0.05, thickness_range=THICKNESS
        )
