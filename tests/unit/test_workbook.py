from datetime import date, datetime, time
from pathlib import Path

import pytest
from openpyxl import Workbook

from vizreel.errors import SpecError
from vizreel.format.locales import EN_US, LOCALES
from vizreel.spec.data import TableError, read_table
from vizreel.spec.loader import parse_spec
from vizreel.spec.models import BarChart, BarRaceChart
from vizreel.spec.workbook import cell_text


def save_workbook(path: Path, sheets: dict[str, list[list[object]]]) -> Path:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, rows in sheets.items():
        sheet = workbook.create_sheet(name)
        for row in rows:
            sheet.append(row)
    workbook.save(path)
    return path


def test_a_workbook_is_read_as_its_first_sheet(tmp_path: Path) -> None:
    path = save_workbook(
        tmp_path / "data.xlsx",
        {"2024": [["Region", "Revenue"], ["North", 120], ["South", 95.5]], "Other": [["A"]]},
    )

    table = read_table(path, EN_US)

    assert table.header == ["Region", "Revenue"]
    assert table.rows == [["North", "120"], ["South", "95.5"]]
    assert table.lines == [2, 3]
    assert table.number(1, 1) == 95.5


def test_a_sheet_is_chosen_by_name(tmp_path: Path) -> None:
    path = save_workbook(tmp_path / "data.xlsx", {"A": [["X"], [1]], "B": [["Y"], [2]]})

    assert read_table(path, EN_US, sheet="B").rows == [["2"]]
    with pytest.raises(TableError) as caught:
        read_table(path, EN_US, sheet="C")
    assert caught.value.message == 'has no sheet "C". Sheets: "A", "B"'


def test_a_stored_number_is_read_as_it_is_whatever_the_locale(tmp_path: Path) -> None:
    path = save_workbook(tmp_path / "data.xlsx", {"S": [["V", "T"], [1.234, "1.234"]]})

    table = read_table(path, LOCALES["tr-TR"])

    # A number the cell stores keeps its decimals; text is read as tr-TR writes numbers.
    assert table.number(0, 0) == 1.234
    assert table.number(0, 1) == 1234


def test_cells_are_written_as_text_the_way_a_spec_would() -> None:
    assert cell_text(2024) == ("2024", 2024.0)
    assert cell_text(2024.0) == ("2024", 2024.0)
    assert cell_text(0.25) == ("0.25", 0.25)
    assert cell_text(datetime(2024, 3, 31)) == ("2024-03-31", None)
    assert cell_text(datetime(2024, 3, 31, 9, 30)) == ("2024-03-31 09:30", None)
    assert cell_text(date(2024, 3, 31)) == ("2024-03-31", None)
    assert cell_text(time(9, 30)) == ("09:30:00", None)
    assert cell_text(True) == ("TRUE", None)
    assert cell_text(None) == ("", None)
    assert cell_text("  North ") == ("North", None)


def test_empty_rows_and_empty_columns_right_of_the_header_are_skipped(tmp_path: Path) -> None:
    path = save_workbook(
        tmp_path / "data.xlsx",
        {"S": [[None], ["A", "B", None], [None, None], [1, 2, None], [3, None]]},
    )

    table = read_table(path, EN_US)

    assert table.header == ["A", "B"]
    assert table.rows == [["1", "2"], ["3", ""]]
    assert table.lines == [4, 5]
    assert table.optional_number(1, 1) is None


def test_a_cell_right_of_the_header_is_an_error_naming_its_row_and_column(
    tmp_path: Path,
) -> None:
    path = save_workbook(tmp_path / "data.xlsx", {"S": [["A", "B"], [1, 2], [3, 4, 5]]})

    with pytest.raises(TableError) as caught:
        read_table(path, EN_US)

    assert caught.value.row == 3
    assert caught.value.message == (
        "has a cell right of the last column the header names, in column C; name its column in "
        "the first row or empty it"
    )


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ([], "is empty; the first row names the columns"),
        ([["A", "B"]], "has a header row but no rows of data"),
    ],
)
def test_a_sheet_needs_a_header_and_rows(
    tmp_path: Path, rows: list[list[object]], message: str
) -> None:
    path = save_workbook(tmp_path / "data.xlsx", {"S": rows})

    with pytest.raises(TableError) as caught:
        read_table(path, EN_US)

    assert caught.value.message == message


def test_columns_are_chosen_from_a_sheet_with_their_numbers(tmp_path: Path) -> None:
    path = save_workbook(tmp_path / "data.xlsx", {"S": [["A", "B", "C"], ["x", 1.5, 2.5]]})

    table = read_table(path, LOCALES["tr-TR"], columns=["C", "A"])

    assert table.rows == [["2.5", "x"]]
    assert table.number(0, 0) == 2.5


def test_files_that_are_not_workbooks_say_what_to_do(tmp_path: Path) -> None:
    (tmp_path / "fake.xlsx").write_text("not a zip")
    (tmp_path / "old.xls").write_bytes(b"\xd0\xcf\x11\xe0")
    (tmp_path / "data.csv").write_text("A\n1\n")

    messages = []
    for name, sheet in (("fake.xlsx", None), ("old.xls", None), ("data.csv", "S")):
        with pytest.raises(TableError) as caught:
            read_table(tmp_path / name, EN_US, sheet=sheet)
        messages.append(caught.value.message)

    assert messages == [
        "is not an Excel workbook; save it again as .xlsx",
        "is an Excel 97-2003 workbook; save it as .xlsx or as CSV UTF-8",
        "is not an Excel workbook, so it has no sheets; leave out sheet",
    ]


def test_a_chart_reads_its_data_from_a_sheet(tmp_path: Path) -> None:
    save_workbook(
        tmp_path / "data.xlsx",
        {
            "Notes": [["Nothing here"]],
            "Offers": [["Company", "Offer"], ["Northwind", 1200000], ["Contoso", 950000]],
        },
    )

    spec = parse_spec(
        "version: 1\ncharts:\n  - { id: b, type: bar, data: { file: data.xlsx, sheet: Offers } }",
        "s.yaml",
        tmp_path,
    )

    chart = spec.charts[0]
    assert isinstance(chart, BarChart)
    assert [(bar.label, bar.value) for bar in chart.bars] == [
        ("Northwind", 1200000),
        ("Contoso", 950000),
    ]


def test_a_race_reads_years_stored_as_numbers_as_its_periods(tmp_path: Path) -> None:
    save_workbook(
        tmp_path / "race.xlsx",
        {"S": [["Year", "Northwind", "Contoso"], [2023, 10, 8], [2024, 14, None]]},
    )

    spec = parse_spec(
        "version: 1\ncharts:\n  - { id: r, type: bar-race, data: race.xlsx }", "s.yaml", tmp_path
    )

    chart = spec.charts[0]
    assert isinstance(chart, BarRaceChart)
    assert chart.periods == ["2023", "2024"]
    assert [(item.name, item.values) for item in chart.series] == [
        ("Northwind", [10, 14]),
        ("Contoso", [8, None]),
    ]


def test_an_error_in_a_sheet_names_the_file_sheet_row_and_column(tmp_path: Path) -> None:
    save_workbook(tmp_path / "data.xlsx", {"Offers": [["Company", "Offer"], ["Northwind", "?"]]})

    with pytest.raises(SpecError) as caught:
        parse_spec(
            "version: 1\ncharts:\n  - { id: b, type: bar, data: { file: data.xlsx, sheet: "
            "Offers } }",
            "s.yaml",
            tmp_path,
        )

    assert [str(issue) for issue in caught.value.issues] == [
        'charts[0].data: data.xlsx, sheet "Offers", row 2, column "Offer" is not a number: "?". '
        "Write it without units, as en-US writes numbers or as a plain number"
    ]


EXAMPLES = Path(__file__).parents[2] / "examples"


def workbook_from_csv(csv_path: Path, xlsx_path: Path) -> None:
    """Save a CSV file as a workbook, storing each cell that holds a number as a number."""
    table = read_table(csv_path, EN_US)
    rows: list[list[object]] = [list(table.header)]
    for row in range(len(table.rows)):
        rows.append(
            [
                table.number(row, column) if table.is_number(row, column) else cell or None
                for column, cell in enumerate(table.rows[row])
            ]
        )
    save_workbook(xlsx_path, {"Data": rows})


def test_every_chart_reads_the_same_data_from_a_sheet_as_from_its_csv_file(
    tmp_path: Path,
) -> None:
    import yaml

    spec = yaml.safe_load((EXAMPLES / "data.yaml").read_text(encoding="utf-8"))
    from_csv = parse_spec(yaml.safe_dump(spec), "data.yaml", EXAMPLES)
    for chart in spec["charts"]:
        reference = chart["data"]
        file = reference if isinstance(reference, str) else reference["file"]
        if not file.endswith(".csv"):
            chart["data"] = {**reference, "file": str(EXAMPLES / file)}
            continue
        workbook = Path(file).with_suffix(".xlsx").name
        if not (tmp_path / workbook).exists():
            workbook_from_csv(EXAMPLES / file, tmp_path / workbook)
        chart["data"] = workbook if isinstance(reference, str) else {**reference, "file": workbook}
    for chart in spec["charts"]:
        for key in ("images",):
            for name, image in chart.get(key, {}).items():
                chart[key][name] = str(EXAMPLES / image)

    from_sheet = parse_spec(yaml.safe_dump(spec), "data.yaml", tmp_path)

    types = {chart.type for chart in from_csv.charts}
    assert len(types) >= 12
    for csv_chart, sheet_chart in zip(from_csv.charts, from_sheet.charts, strict=True):
        assert csv_chart.model_dump(exclude={"data"}) == sheet_chart.model_dump(exclude={"data"}), (
            csv_chart.id
        )
