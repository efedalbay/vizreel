# Changelog

All notable changes to vizreel are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [0.4.4] - 2026-09-28

### Added

- The `table` chart type: two to four columns and two to eight rows of numbers or text. The rows appear one after another, their numbers counting up; the cells use the largest theme text size at which the table fits, and a highlighted row gets a soft band while the others dim.

## [0.4.3] - 2026-09-27

### Added

- The `share` chart type: how a whole divides into two to six parts, as a ring with a legend of each part's percent. At the highlight beat the highlighted part, the largest by default, turns to the highlight color and its percent counts up in the middle. Percents are whole numbers that add up to 100.

## [0.4.2] - 2026-09-27

### Added

- The `stacked` chart type: bars made of two or three parts, one bar per category, with each bar's total and a legend. The parts grow one series at a time, and a highlighted series keeps its color while the others dim. Columns at 16:9 and rows at 9:16, as for bar charts.

## [0.4.1] - 2026-09-27

### Added

- The `waterfall` chart type: how a starting value becomes a total through up to six increases and decreases. Each step grows from where the previous one ended, green for an increase and red for a decrease, and the total grows last. Columns at 16:9 and rows at 9:16, as for bar charts.

## [0.4.0] - 2026-09-27

### Added

- The `compare` chart type: one measure before and after. The later value counts from the earlier one to its own, and the change counts in at the highlight beat, in percent (`−72%`) or as a difference (`+$150M`). The change is colored by its direction; `trend: none` keeps it neutral, for rises that are bad news.

## [0.3.0] - 2026-09-27

### Added

- Vertical 9:16 clips for Shorts, Reels and TikTok: `meta.aspect: "9:16"` or `--aspect 9:16`. The same spec renders in both shapes; vertical files are named `ID.vertical.mov`, and a vertical safe area keeps clear of the platforms' buttons and captions.
- Bar charts can be drawn as rows (`layout: rows`), each bar under its label, which suits long labels. `layout: auto`, the default, uses columns at 16:9 and rows at 9:16.
- Timelines run down the frame in a 9:16 frame.
- Titles and subtitles wrap onto a second line when they do not fit on one; so do the lines of a stat card.

### Fixed

- Text wrapped at the width of the video, so a title could wrap in a preview although it fit in the final render.

## [0.2.0] - 2026-09-27

### Added

- `vizreel render --watch` renders again whenever the spec or its theme file is saved. Only the charts that changed are rendered, an invalid spec prints its errors without stopping, and Ctrl+C stops watching.

## [0.1.1] - 2026-09-27

Fixes found while making the first real clips with 0.1.0.

### Changed

- `--quality preview` writes `ID.preview.mov` (and `ID.preview.png` with `--still`), so a preview no longer replaces a final clip of the same chart.

### Fixed

- The first render after installing no longer prints `SyntaxWarning: invalid escape sequence` warnings from pydub, a Manim dependency.
- Timeline labels sit on a common baseline. A dotted capital İ, an accent or a descender used to move a label a few pixels off its row.
- The same holds for bar labels, the x labels of line charts and the series names next to their values. The gap between a title and its subtitle no longer depends on whether the title has descenders.
- The first-value labels of a line chart no longer overlap each other or a line. Each goes above or below its point, wherever it is clear of labels and lines; if neither side is clear, the labels stack above the lines.

## [0.1.0] - 2026-09-26

The first release.

### Added

- Four chart types, each rendered to its own clip: `stat` (a number that counts to its value), `line` (up to three series drawn from left to right), `bar` (up to eight bars with one highlighted) and `timeline` (up to seven events with one emphasized).
- The YAML spec format, version 1, validated with every error reported at once and its location. `vizreel validate` checks a spec; `vizreel schema` writes its JSON Schema for editors and tools.
- `vizreel render` with `--out`, `--only`, `--quality preview|final`, `--format mov|webm|mp4` and `--still`. Clips are exactly as long as their `duration`; `mov` and `webm` keep a transparent background.
- Number formatting with prefixes, suffixes, fixed or automatic decimals, compact units (K, M, B, T) and consistent decimals within a chart.
- Two built-in themes, `default` and `light`, and custom themes loaded by path. `vizreel themes list` lists the built-in themes; `vizreel theme check` tests a theme's contrast (WCAG) and its colors for color vision deficiency.
- `vizreel new TYPE` prints a commented template for each chart type.
- The Inter typeface, bundled so that output looks the same on every machine.

[0.4.4]: https://github.com/efedalbay/vizreel/releases/tag/v0.4.4
[0.4.3]: https://github.com/efedalbay/vizreel/releases/tag/v0.4.3
[0.4.2]: https://github.com/efedalbay/vizreel/releases/tag/v0.4.2
[0.4.1]: https://github.com/efedalbay/vizreel/releases/tag/v0.4.1
[0.4.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.4.0
[0.3.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.3.0
[0.2.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.2.0
[0.1.1]: https://github.com/efedalbay/vizreel/releases/tag/v0.1.1
[0.1.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.1.0
