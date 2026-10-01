"""Reading a chart's data from a CSV file or an Excel workbook."""

import csv
import io
from dataclasses import dataclass
from pathlib import Path

from vizreel.errors import VizreelError
from vizreel.format.locales import Locale
from vizreel.format.numbers import parse_number

DELIMITERS = ("\t", ";", ",")
"""The separators a data file can use between cells, in order of preference on a tie."""


class TableError(VizreelError):
    """A data file cannot be read, or does not hold what its chart needs.

    Attributes:
        message: What is wrong and, where possible, how to fix it.
        row: Line of the file the problem is on, or None for the file as a whole.
        column: Name of the column the problem is in, or None.
    """

    def __init__(self, message: str, row: int | None = None, column: str | None = None) -> None:
        self.message = message
        self.row = row
        self.column = column
        super().__init__(message)

    def where(self) -> str:
        """Where the problem is, e.g. `row 4, column "Revenue"`; empty for the whole file."""
        parts = []
        if self.row is not None:
            parts.append(f"row {self.row}")
        if self.column is not None:
            parts.append(f'column "{self.column}"')
        return ", ".join(parts)


@dataclass(frozen=True)
class Table:
    """The cells of a data file: a header row naming the columns, then rows of cells.

    Chart types read it in `ChartType.from_table`. Rows and columns count from 0, the header
    not included; errors name the line of the file and the column's header.

    Attributes:
        header: The name of each column.
        rows: The cells of each row, one per column, without surrounding spaces.
        lines: The line of the file each row ends on, counting from 1.
        locale: How the file writes numbers besides the plain way.
        numbers: The number each cell stores, or None for a cell that stores text, by row and
            column like `rows`; None for a whole CSV file, which stores only text. A stored
            number is read as it is, not from its text.
    """

    header: list[str]
    rows: list[list[str]]
    lines: list[int]
    locale: Locale
    numbers: list[list[float | None]] | None = None

    @property
    def width(self) -> int:
        """The number of columns."""
        return len(self.header)

    def require_width(self, count: int, what: str) -> None:
        """Check that the table has exactly `count` columns.

        Args:
            count: The number of columns the chart reads.
            what: What the chart reads, e.g. "a label and a value".

        Raises:
            TableError: The table has another number of columns.
        """
        if self.width != count:
            raise TableError(
                f"needs {count} columns, {what}; the file has {self.width}: "
                f"{_quoted(self.header)}. Choose them with columns: [...]"
            )

    def require_rows(self, count: int, what: str) -> None:
        """Check that the table has exactly `count` rows.

        Raises:
            TableError: The table has another number of rows.
        """
        if len(self.rows) != count:
            raise TableError(f"needs {count} rows, {what}; the file has {len(self.rows)}")

    def text(self, row: int, column: int) -> str:
        """Return a cell's text.

        Raises:
            TableError: The cell is empty.
        """
        cell = self.rows[row][column]
        if not cell:
            raise self.error(row, column, "is empty; write some text")
        return cell

    def number(self, row: int, column: int) -> float:
        """Return a cell's number.

        Raises:
            TableError: The cell is empty or not a number.
        """
        value = self.optional_number(row, column)
        if value is None:
            raise self.error(row, column, "is empty; write a number")
        return value

    def optional_number(self, row: int, column: int) -> float | None:
        """Return a cell's number, or None if the cell is empty.

        Raises:
            TableError: The cell is not a number.
        """
        stored = self._stored(row, column)
        if stored is not None:
            return stored
        cell = self.rows[row][column]
        if not cell:
            return None
        try:
            return parse_number(cell, locale=self.locale)
        except ValueError:
            raise self.error(
                row,
                column,
                f'is not a number: "{cell}". Write it without units, as {self.locale.name} writes '
                "numbers or as a plain number",
            ) from None

    def is_number(self, row: int, column: int) -> bool:
        """Whether a cell holds a number."""
        if self._stored(row, column) is not None:
            return True
        try:
            parse_number(self.rows[row][column], locale=self.locale)
        except ValueError:
            return False
        return True

    def _stored(self, row: int, column: int) -> float | None:
        return None if self.numbers is None else self.numbers[row][column]

    def error(self, row: int, column: int, message: str) -> TableError:
        """Return an error about one cell, naming its line and column."""
        return TableError(message, row=self.lines[row], column=self.header[column])


def read_table(
    path: Path, locale: Locale, columns: list[str] | None = None, sheet: str | None = None
) -> Table:
    """Read a CSV file or a sheet of an Excel workbook whose first row names its columns.

    A CSV file is UTF-8, with or without a byte order mark, and separates cells with commas,
    semicolons or tabs, whichever its header uses most. A workbook is an .xlsx or .xlsm file,
    read by `workbook.read_workbook`. Empty rows are skipped.

    Args:
        path: The file to read.
        locale: How the file writes numbers besides the plain way.
        columns: The columns to keep, by name and in this order. All of them if None.
        sheet: The sheet of a workbook to read; its first sheet if None.

    Raises:
        TableError: The file cannot be read, has no rows, has a row with another number of
            cells than the header, or lacks one of `columns` or `sheet`.
    """
    from vizreel.spec.workbook import WORKBOOK_SUFFIXES, read_workbook

    suffix = path.suffix.lower()
    if suffix in WORKBOOK_SUFFIXES:
        table = read_workbook(path, locale, sheet)
        return table if columns is None else _select(table, columns)
    if suffix == ".xls":
        raise TableError("is an Excel 97-2003 workbook; save it as .xlsx or as CSV UTF-8")
    if sheet is not None:
        raise TableError("is not an Excel workbook, so it has no sheets; leave out sheet")
    text = _read_text(path)
    first_line = next((line for line in text.splitlines() if line.strip()), None)
    if first_line is None:
        raise TableError("is empty; the first row names the columns")
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=_delimiter(first_line))
    header: list[str] | None = None
    rows, row_lines = [], []
    for raw_cells in reader:
        cells = [cell.strip() for cell in raw_cells]
        if not any(cells):
            continue
        if header is None:
            header = cells
            continue
        if len(cells) != len(header):
            raise TableError(
                f"has {len(cells)} cells but the header has {len(header)}", row=reader.line_num
            )
        rows.append(cells)
        row_lines.append(reader.line_num)
    if header is None or not rows:
        raise TableError("has a header row but no rows of data")
    table = Table(header, rows, row_lines, locale)
    return table if columns is None else _select(table, columns)


def _read_text(path: Path) -> str:
    if path.is_dir():
        raise TableError("is a directory, expected a CSV file or an Excel workbook")
    try:
        return path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise TableError(f"was not found in {path.parent}") from None
    except PermissionError:
        raise TableError("cannot be read: permission denied") from None
    except UnicodeDecodeError:
        raise TableError("is not UTF-8 text; save it as CSV UTF-8") from None


def _delimiter(header: str) -> str:
    """The separator the header line uses most, outside quotes."""
    counts = dict.fromkeys(DELIMITERS, 0)
    quoted = False
    for char in header:
        if char == '"':
            quoted = not quoted
        elif not quoted and char in counts:
            counts[char] += 1
    return max(DELIMITERS, key=lambda delimiter: counts[delimiter])


def _select(table: Table, columns: list[str]) -> Table:
    indexes = []
    for name in columns:
        found = [index for index, header in enumerate(table.header) if header == name]
        if not found:
            raise TableError(f'has no column "{name}". Columns: {_quoted(table.header)}')
        if len(found) > 1:
            raise TableError(f'has {len(found)} columns named "{name}"; rename all but one')
        indexes.append(found[0])
    rows = [[row[index] for index in indexes] for row in table.rows]
    numbers = (
        None
        if table.numbers is None
        else [[row[index] for index in indexes] for row in table.numbers]
    )
    return Table(list(columns), rows, table.lines, table.locale, numbers)


def _quoted(names: list[str]) -> str:
    return ", ".join(f'"{name}"' for name in names)
