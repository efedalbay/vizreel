from pathlib import Path

import pytest

from vizreel.charts.title_card import line_starts
from vizreel.errors import SpecError
from vizreel.render.scales import balanced_lines
from vizreel.spec.loader import parse_spec
from vizreel.spec.models import TitleCardChart
from vizreel.themes.loader import load_theme


def title_card(fields: str) -> TitleCardChart:
    spec = parse_spec(f"version: 1\ncharts:\n  - {{ id: t, type: title-card{fields} }}", "t.yaml")
    chart = spec.charts[0]
    assert isinstance(chart, TitleCardChart)
    return chart


def test_a_title_card_takes_a_headline_and_lines_above_and_under_it() -> None:
    chart = title_card(", kicker: Part 2, title: How Northwind grew, subtitle: 2019 to 2024")

    assert (chart.kicker, chart.title, chart.subtitle) == (
        "Part 2",
        "How Northwind grew",
        "2019 to 2024",
    )
    assert chart.duration == 3


def test_a_title_card_needs_its_headline() -> None:
    with pytest.raises(SpecError) as caught:
        title_card(", kicker: Part 2")

    assert [str(issue) for issue in caught.value.issues] == [
        "charts[0].title: required field is missing"
    ]


def test_a_title_card_reads_no_data_file(tmp_path: Path) -> None:
    (tmp_path / "data.csv").write_text("A,B\n1,2\n")

    with pytest.raises(SpecError) as caught:
        parse_spec(
            "version: 1\ncharts:\n  - { id: t, type: title-card, title: Hi, data: data.csv }",
            "t.yaml",
            tmp_path,
        )

    assert [str(issue) for issue in caught.value.issues] == [
        "charts[0].data: data.csv cannot be used: title-card charts do not read data from a file"
    ]


def test_the_headline_size_is_96_unless_the_theme_sets_another() -> None:
    assert load_theme("default", Path(".")).sizes.headline == 96


def test_lines_start_one_after_another_and_all_finish_together() -> None:
    starts = line_starts(3, 1.6, lag=0.3)

    each = 1.6 / 1.6
    assert starts == pytest.approx([0.0, 0.3 * each, 0.6 * each])
    assert starts[-1] + each == pytest.approx(1.6)
    assert line_starts(1, 2.0) == [0.0]


def test_words_spread_evenly_over_the_lines() -> None:
    assert balanced_lines("How Northwind grew to five countries", len, 2) == [
        "How Northwind grew",
        "to five countries",
    ]
    assert balanced_lines("aaaa bb cc dd", len, 2) == ["aaaa bb", "cc dd"]
    assert balanced_lines("one two three", len, 3) == ["one", "two", "three"]
