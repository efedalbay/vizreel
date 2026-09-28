from pathlib import Path

import pytest

from vizreel.errors import SpecError
from vizreel.format.locales import EN_US, FR_FR, NARROW_NO_BREAK_SPACE, NO_BREAK_SPACE, TR_TR
from vizreel.format.numbers import parse_number
from vizreel.spec.data import Table, TableError, read_table
from vizreel.spec.loader import load_spec, parse_spec, spec_data_files, spec_json_schema
from vizreel.spec.models import (
    BarChart,
    CompareChart,
    LineChart,
    ShareChart,
    StackedChart,
    TableChart,
    TimelineChart,
    WaterfallChart,
)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("1,234.5", 1234.5),
        ("1234.5", 1234.5),
        ("12", 12),
        ("-3", -3),
        ("−3", -3),
        ("+2", 2),
        (" 7 ", 7),
        ("1,234,567", 1234567),
    ],
)
def test_numbers_are_read_as_en_us_writes_them(text: str, value: float) -> None:
    assert parse_number(text, locale=EN_US) == value


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("1.234,5", 1234.5),
        ("1234,5", 1234.5),
        ("1.234", 1234),
        ("1.5", 1.5),
        ("1234.5", 1234.5),
        ("-0,25", -0.25),
    ],
)
def test_numbers_are_read_as_tr_tr_writes_them_or_plain(text: str, value: float) -> None:
    assert parse_number(text, locale=TR_TR) == value


@pytest.mark.parametrize("space", [" ", NO_BREAK_SPACE, NARROW_NO_BREAK_SPACE])
def test_a_space_groups_digits_in_fr_fr_whichever_space_it_is(space: str) -> None:
    assert parse_number(f"1{space}234,5", locale=FR_FR) == 1234.5


@pytest.mark.parametrize("text", ["", "12a", "1,2,3", "1.234.5", "$12", "1e6", "nan", "12 %"])
def test_text_that_is_not_a_number_is_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        parse_number(text, locale=EN_US)


def write(folder: Path, name: str, text: str) -> Path:
    path = folder / name
    path.write_bytes(text.encode("utf-8"))
    return path


@pytest.mark.parametrize("delimiter", [",", ";", "\t"])
def test_cells_are_separated_by_what_the_header_uses(tmp_path: Path, delimiter: str) -> None:
    path = write(tmp_path, "d.csv", f"Region{delimiter}Revenue\nNorth{delimiter}12\n")

    table = read_table(path, EN_US)

    assert table.header == ["Region", "Revenue"]
    assert table.rows == [["North", "12"]]


def test_a_separator_inside_quotes_does_not_count(tmp_path: Path) -> None:
    path = write(tmp_path, "d.csv", '"Revenue, net";Year;Units\n"1,5";2024;3\n')

    table = read_table(path, TR_TR)

    assert table.header == ["Revenue, net", "Year", "Units"]
    assert table.number(0, 0) == 1.5


def test_a_byte_order_mark_and_spaces_around_cells_are_dropped(tmp_path: Path) -> None:
    path = write(tmp_path, "d.csv", "﻿Region , Revenue\n North , 12 \n")

    assert read_table(path, EN_US).header == ["Region", "Revenue"]
    assert read_table(path, EN_US).rows == [["North", "12"]]


def test_empty_rows_are_skipped_and_rows_keep_their_line(tmp_path: Path) -> None:
    path = write(tmp_path, "d.csv", "\nRegion,Revenue\nNorth,12\n\n,\nSouth,9\n")

    table = read_table(path, EN_US)

    assert table.rows == [["North", "12"], ["South", "9"]]
    assert table.lines == [3, 6]


def test_columns_are_chosen_by_name_and_order(tmp_path: Path) -> None:
    path = write(tmp_path, "d.csv", "Year,North,South\n2024,1,2\n")

    table = read_table(path, EN_US, ["South", "Year"])

    assert table.header == ["South", "Year"]
    assert table.rows == [["2", "2024"]]


@pytest.mark.parametrize(
    ("text", "columns", "message", "row"),
    [
        ("", None, "is empty; the first row names the columns", None),
        ("Region,Revenue\n", None, "has a header row but no rows of data", None),
        ("Region,Revenue\nNorth,12\nSouth\n", None, "has 1 cells but the header has 2", 3),
        (
            "Region,Revenue\nNorth,12\n",
            ["Profit"],
            'has no column "Profit". Columns: "Region", "Revenue"',
            None,
        ),
        ("A,A\n1,2\n", ["A"], 'has 2 columns named "A"; rename all but one', None),
    ],
)
def test_a_file_that_is_not_a_table_is_an_error(
    tmp_path: Path, text: str, columns: list[str] | None, message: str, row: int | None
) -> None:
    path = write(tmp_path, "d.csv", text)

    with pytest.raises(TableError) as caught:
        read_table(path, EN_US, columns)

    assert (caught.value.message, caught.value.row) == (message, row)


def test_a_file_that_is_not_utf_8_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "d.csv"
    path.write_bytes("Bölge,Gelir\nKuzey,1\n".encode("cp1254"))

    with pytest.raises(TableError, match="is not UTF-8 text; save it as CSV UTF-8"):
        read_table(path, EN_US)


def test_a_missing_file_or_a_folder_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(TableError, match="was not found in"):
        read_table(tmp_path / "nope.csv", EN_US)
    with pytest.raises(TableError, match="is a directory"):
        read_table(tmp_path, EN_US)


def test_a_cell_error_names_its_line_and_column() -> None:
    table = Table(["Region", "Revenue"], [["North", "12a"], ["", "3"]], [2, 4], EN_US)

    with pytest.raises(TableError) as caught:
        table.number(0, 1)
    assert caught.value.where() == 'row 2, column "Revenue"'
    assert caught.value.message.startswith('is not a number: "12a". Write it without units')

    with pytest.raises(TableError) as caught:
        table.text(1, 0)
    assert caught.value.where() == 'row 4, column "Region"'
    assert table.optional_number(1, 1) == 3


def spec_with(tmp_path: Path, chart: str, csv: str, meta: str = "{}") -> object:
    """Validate a spec whose one chart reads `csv` from data.csv."""
    write(tmp_path, "data.csv", csv)
    text = f"version: 1\nmeta: {meta}\ncharts:\n  - {{ id: c, {chart} }}\n"
    return parse_spec(text, "spec.yaml", tmp_path).charts[0]


def errors_of(tmp_path: Path, chart: str, csv: str, meta: str = "{}") -> list[str]:
    with pytest.raises(SpecError) as caught:
        spec_with(tmp_path, chart, csv, meta)
    return [str(issue) for issue in caught.value.issues]


def test_a_bar_chart_reads_a_label_and_a_value_per_row(tmp_path: Path) -> None:
    chart = spec_with(
        tmp_path,
        "type: bar, data: data.csv, highlight: { label: Güney }",
        "Bölge;Gelir\nKuzey;1.234,5\nGüney;980\n",
        "{ locale: tr-TR }",
    )

    assert isinstance(chart, BarChart)
    assert [(bar.label, bar.value) for bar in chart.bars] == [("Kuzey", 1234.5), ("Güney", 980)]


def test_a_share_chart_reads_its_parts(tmp_path: Path) -> None:
    chart = spec_with(
        tmp_path, "type: share, data: data.csv", "Name,Share\nNorthwind,47\nOthers,53\n"
    )

    assert isinstance(chart, ShareChart)
    assert [part.label for part in chart.parts] == ["Northwind", "Others"]


def test_a_timeline_reads_a_date_and_a_label_per_row(tmp_path: Path) -> None:
    chart = spec_with(
        tmp_path, "type: timeline, data: data.csv", "When,What\n2016,Founded\n2018,Expands\n"
    )

    assert isinstance(chart, TimelineChart)
    assert [(event.date, event.label) for event in chart.events] == [
        ("2016", "Founded"),
        ("2018", "Expands"),
    ]


def test_a_line_chart_reads_a_series_from_each_column_after_the_first(tmp_path: Path) -> None:
    chart = spec_with(
        tmp_path, "type: line, data: data.csv", "Quarter,North,South\nQ1,10,5\nQ2,,7\nQ3,14,9\n"
    )

    assert isinstance(chart, LineChart)
    assert chart.x == ["Q1", "Q2", "Q3"]
    assert [(series.name, series.values) for series in chart.series] == [
        ("North", [10, None, 14]),
        ("South", [5, 7, 9]),
    ]


def test_a_stacked_chart_reads_categories_and_series(tmp_path: Path) -> None:
    chart = spec_with(
        tmp_path,
        "type: stacked, data: data.csv",
        "Year,Cloud,Devices\n2022,1.2,3.1\n2023,2.4,2.9\n",
    )

    assert isinstance(chart, StackedChart)
    assert chart.categories == ["2022", "2023"]
    assert [series.values for series in chart.series] == [[1.2, 2.4], [3.1, 2.9]]


def test_a_waterfall_names_its_total_in_a_last_row_without_a_value(tmp_path: Path) -> None:
    chart = spec_with(
        tmp_path,
        "type: waterfall, data: data.csv",
        "Item,Amount\nRevenue,1200\nSalaries,-500\nOther,50\nProfit,\n",
    )

    assert isinstance(chart, WaterfallChart)
    assert (chart.start.label, chart.start.value) == ("Revenue", 1200)
    assert [step.label for step in chart.steps] == ["Salaries", "Other"]
    assert chart.end.label == "Profit"


def test_a_waterfall_without_a_total_row_takes_every_row_after_the_start(tmp_path: Path) -> None:
    chart = spec_with(
        tmp_path,
        "type: waterfall, data: data.csv, end: { label: Profit }",
        "Item,Amount\nRevenue,1200\nSalaries,-500\n",
    )

    assert isinstance(chart, WaterfallChart)
    assert [step.label for step in chart.steps] == ["Salaries"]
    assert chart.end.label == "Profit"


def test_a_compare_chart_reads_two_rows(tmp_path: Path) -> None:
    chart = spec_with(
        tmp_path, "type: compare, data: data.csv", "Year,Staff\n2019,1200\n2022,340\n"
    )

    assert isinstance(chart, CompareChart)
    assert (chart.before.label, chart.after.value) == ("2019", 340)
    assert errors_of(tmp_path, "type: compare, data: data.csv", "Y,S\n1,1\n2,2\n3,3\n") == [
        "charts[0].data: data.csv needs 2 rows, the earlier value and the later one; the file has 3"
    ]


def test_a_table_reads_numbers_where_its_first_row_has_them(tmp_path: Path) -> None:
    chart = spec_with(
        tmp_path, "type: table, data: data.csv", "Market,Revenue,Note\nGermany,412,Up\n2024,9,New\n"
    )

    assert isinstance(chart, TableChart)
    assert [column.name for column in chart.columns] == ["Market", "Revenue", "Note"]
    assert chart.rows == [["Germany", 412, "Up"], ["2024", 9, "New"]]


def test_a_table_with_columns_in_the_spec_keeps_their_formats(tmp_path: Path) -> None:
    chart = spec_with(
        tmp_path,
        "type: table, data: data.csv, columns: [{ name: Market }, { name: Revenue, number: "
        '{ prefix: "$" } }]',
        "M,R\nGermany,412\nFrance,298\n",
    )

    assert isinstance(chart, TableChart)
    assert [column.number.prefix for column in chart.columns] == ["", "$"]
    assert chart.rows[1] == ["France", 298]


def test_data_columns_choose_what_a_chart_reads(tmp_path: Path) -> None:
    chart = spec_with(
        tmp_path,
        "type: bar, data: { file: data.csv, columns: [Region, Units] }",
        "Region,Revenue,Units\nNorth,12,3\nSouth,9,4\n",
    )

    assert isinstance(chart, BarChart)
    assert [bar.value for bar in chart.bars] == [3, 4]


def test_a_table_with_too_many_columns_for_the_chart_is_an_error(tmp_path: Path) -> None:
    assert errors_of(tmp_path, "type: bar, data: data.csv", "A,B,C\nx,1,2\n") == [
        'charts[0].data: data.csv needs 2 columns, a label and a value; the file has 3: "A", '
        '"B", "C". Choose them with columns: [...]'
    ]


def test_a_cell_error_names_the_file_row_and_column(tmp_path: Path) -> None:
    assert errors_of(
        tmp_path, "type: bar, data: data.csv", "Region,Revenue\nNorth,12\nSouth,9k\n"
    ) == [
        'charts[0].data: data.csv, row 3, column "Revenue" is not a number: "9k". Write it '
        "without units, as en-US writes numbers or as a plain number"
    ]


def test_a_field_the_file_gives_cannot_also_be_written(tmp_path: Path) -> None:
    errors = errors_of(
        tmp_path, "type: bar, data: data.csv, bars: [{ label: A, value: 1 }]", "R,V\nN,1\nS,2\n"
    )

    assert errors == ["charts[0].bars: cannot be used together with data; data.csv gives the bars"]


def test_a_problem_in_a_field_the_file_gave_names_the_file(tmp_path: Path) -> None:
    assert errors_of(tmp_path, "type: bar, data: data.csv", "R,V\nN,1\nS,-2\n") == [
        "charts[0].bars[1].value: must be at least 0, got -2 (from data.csv)"
    ]


def test_an_unreadable_file_does_not_also_report_the_fields_it_would_give(tmp_path: Path) -> None:
    errors = errors_of(tmp_path, "type: bar, data: nope.csv, duration: 1", "")

    assert len(errors) == 2
    assert errors[0].startswith("charts[0].data: nope.csv was not found in ")
    assert errors[1] == "charts[0].duration: must be at least 2, got 1"


def test_a_chart_type_without_from_table_does_not_read_data(tmp_path: Path) -> None:
    assert errors_of(tmp_path, "type: stat, value: 1, data: data.csv", "A,B\n1,2\n") == [
        "charts[0].data: data.csv cannot be used: stat charts do not read data from a file"
    ]


@pytest.mark.parametrize(
    ("data", "error"),
    [
        (
            "5",
            "charts[0].data: expected the path of a CSV file, or file and columns, got the "
            "number 5",
        ),
        ('""', "charts[0].data: must not be empty"),
        ("{ columns: [A] }", "charts[0].data.file: required field is missing"),
        (
            "{ file: data.csv, sheet: 1 }",
            "charts[0].data.sheet: unknown field. Check the spelling against docs/SPEC.md",
        ),
    ],
)
def test_a_wrong_data_field_is_an_error(tmp_path: Path, data: str, error: str) -> None:
    assert errors_of(tmp_path, f"type: bar, data: {data}", "A,B\nx,1\ny,2\n") == [error]


def test_data_files_are_read_from_the_spec_folder(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    write(tmp_path / "data", "sales.csv", "R,V\nN,1\nS,2\n")
    spec_path = write(
        tmp_path,
        "spec.yaml",
        "version: 1\ncharts:\n  - { id: a, type: bar, data: data/sales.csv }\n"
        "  - { id: b, type: bar, data: data/missing.csv }\n",
    )

    with pytest.raises(SpecError):
        load_spec(spec_path)
    assert spec_data_files(spec_path) == [tmp_path / "data" / "sales.csv"]


def test_the_json_schema_describes_the_data_field() -> None:
    schema = spec_json_schema()

    assert "DataFile" in schema["$defs"]
    assert "data" in schema["$defs"]["BarChart"]["properties"]
