import pytest

from vizreel.charts.table import MAX_COLUMN_GAP, ROW_PITCH, place_table
from vizreel.errors import RenderError, SpecError
from vizreel.render.layout import px
from vizreel.spec.loader import parse_spec
from vizreel.spec.models import TableChart

COLUMNS = "[{ name: Market }, { name: Revenue }, { name: Office }]"


def table(rows: str, extra: str = "", columns: str = COLUMNS) -> TableChart:
    spec = parse_spec(
        "version: 1\ncharts:\n"
        f"  - {{ id: t, type: table, columns: {columns}, rows: [{rows}]{extra} }}",
        "spec.yaml",
    )
    chart = spec.charts[0]
    assert isinstance(chart, TableChart)
    return chart


def table_errors(rows: str, extra: str = "", columns: str = COLUMNS) -> list[str]:
    with pytest.raises(SpecError) as caught:
        table(rows, extra, columns)
    return [str(issue) for issue in caught.value.issues]


ROWS = "[Germany, 412, Berlin], [France, 298.5, Paris]"


def test_columns_hold_numbers_or_text() -> None:
    chart = table(ROWS)

    assert chart.row_names == ["Germany", "France"]
    assert [chart.numeric(column) for column in range(3)] == [False, True, False]
    assert chart.rows[0][1] == 412


def test_every_row_has_one_cell_per_column() -> None:
    [message] = table_errors("[Germany, 412, Berlin], [France, 298]")

    assert message == (
        "charts[0].rows[1]: has 2 cells but there are 3 columns; give one cell per column"
    )


def test_the_first_cell_names_the_row() -> None:
    [message] = table_errors("[Germany, 412, Berlin], [7, 298, Paris]")

    assert message == "charts[0].rows[1][0]: the first cell names the row; write it as text"


def test_a_column_holds_one_kind_of_cell() -> None:
    messages = table_errors("[Germany, 412, Berlin], [France, n/a, 3]")

    assert messages == [
        'charts[0].rows[1][1]: column "Revenue" holds numbers, as in its first row, so this '
        "cell must be numbers too",
        'charts[0].rows[1][2]: column "Office" holds text, as in its first row, so this cell '
        "must be text too",
    ]


def test_row_names_are_unique_and_the_highlight_matches_one() -> None:
    messages = table_errors(
        "[Germany, 412, Berlin], [Germany, 298, Paris]", ", highlight: { row: Japan }"
    )

    assert messages == [
        'charts[0].rows[1][0]: "Germany" is already used by rows[0]; row names must be unique',
        'charts[0].highlight.row: "Japan" does not match any row. Rows: "Germany"',
    ]


@pytest.mark.parametrize(
    ("rows", "columns"),
    [
        ("[A, 1], [B, 2]", "[{ name: Market }]"),
        (
            "[A, 1, 2, 3, 4], [B, 1, 2, 3, 4]",
            "[" + ", ".join(f"{{ name: C{index} }}" for index in range(5)) + "]",
        ),
        ("[A, 1, x]", COLUMNS),
    ],
)
def test_two_to_four_columns_and_two_to_eight_rows(rows: str, columns: str) -> None:
    messages = table_errors(rows, columns=columns)

    assert any(
        message.startswith(("charts[0].columns:", "charts[0].rows:")) for message in messages
    )


def test_columns_spread_up_to_the_widest_gap_and_the_table_is_centered() -> None:
    label = px(36)
    placement = place_table((0.0, 0.0), (16.0, 8.0), [1.0, 1.0, 1.0], 3, 36)
    gap = label * MAX_COLUMN_GAP

    assert placement.lefts == pytest.approx([-1.5 - gap, -0.5, 0.5 + gap])
    pitch = label * ROW_PITCH
    assert placement.baselines == pytest.approx(
        [placement.header_baseline - pitch * (row + 1) for row in range(3)]
    )
    total = pitch * 3 + label
    assert placement.header_baseline == pytest.approx(total / 2 - label)


def test_a_table_too_wide_is_an_error() -> None:
    with pytest.raises(RenderError, match="too wide"):
        place_table((0.0, 0.0), (4.0, 8.0), [2.0, 1.9], 2, 36)


def test_rows_that_do_not_fit_are_an_error() -> None:
    with pytest.raises(RenderError, match="not enough room"):
        place_table((0.0, 0.0), (16.0, 1.0), [1.0, 1.0], 8, 36)


def test_a_cell_that_is_neither_text_nor_a_number_is_one_error() -> None:
    [message] = table_errors("[Germany, true, Berlin], [France, 298, Paris]")

    assert message == "charts[0].rows[0][1]: expected text or a number, got true"
