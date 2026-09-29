# Changelog

All notable changes to vizreel are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [0.13.0] - 2026-09-29

### Added

- The `bar-race` chart type: bars that grow and change places as their values change over up to 200 periods, the largest `show` of up to 30 series on screen, the period large above them. The race runs at one pace and slows to a stop on the last period; bars slide past each other briefly when their values cross, and enter or leave at the bottom. A followed series is drawn in the highlight color.
- The `line-race` chart type: one to six lines drawn through up to 200 periods by one pen, each with its name and value at its tip, the vertical axis growing with the largest value drawn so far.
- Both read their data from a CSV file, the periods in the first column and a series in each other column; `examples/data.yaml` races ten companies through 24 years.

### Changed

- Counting numbers are built much faster, which shortens the render of every chart that counts.

## [0.12.0] - 2026-09-29

### Added

- Motion options, in a chart's `motion`, in `meta.motion` for every chart, or in a theme's `motion`:
  - `entrance: rise` or `zoom` makes the panel, title, labels and legends rise or grow a little into place as they fade in; `fade` is the default.
  - `exit: fade`, `sink` or `zoom` makes a clip leave the screen at its end, after the full hold and within its duration; `--still` saves the complete chart from just before. A sequence leaves only at the end of its last clip.
  - `easing` chooses the ease-out curve.
- Themes take `entrance`, `exit` and `exit_time` in `motion`.
- `render.appear` in `vizreel.plugin.render`, for chart types from other packages to honor the entrance.

## [0.11.2] - 2026-09-29

### Added

- The `progress` chart type: how far a value has come toward a goal. A bar fills from the left under a big percent, or with `style: ring` a ring fills clockwise from the top with the percent in its middle, while the value and the goal count up beneath. A value past the goal fills it and shows more than 100%.

### Changed

- The example plugin in `examples/plugin` is now `vizreel-dots`, with a `dots` chart type: a number that counts up while as many dots of a grid fill in, such as 18 of 25 customers. Its `progress` type makes way for a built-in `progress` type.

## [0.11.1] - 2026-09-29

### Added

- The `area` chart type: one to three series as filled areas drawn from left to right, overlapping from zero or stacked with `stack: true` so the top shows their total. A label rides each area's tip with its name and own value, and a highlighted series keeps its color while the others dim. It can be told as a sequence and read its data from a CSV file.

## [0.11.0] - 2026-09-28

### Added

- The `grouped` chart type: bars side by side in groups of two or three, one group per category, each bar with its value, under a legend. The groups grow one after another, and a highlighted series keeps its color while the others dim. Columns at 16:9 and 1:1, rows at 9:16, and rows in any frame when the values are too wide to sit side by side. It can be told as a sequence and read its data from a CSV file.

## [0.10.0] - 2026-09-28

### Added

- Data from CSV files: `data: data/regions.csv` gives a chart its bars, series, events, parts or rows from a file exported from a spreadsheet, and `data: { file, columns }` picks the columns to read. Every chart type but `stat` reads one. Cells may be separated by commas, semicolons or tabs, numbers may be written as the spec's locale writes them (`1.234,5` in `tr-TR`), the data passes the same checks as data written in the spec, and an error names the file, row and column. `examples/data.yaml` has a chart of each type.
- `render --watch` renders again when a data file is saved, including one that made the spec invalid.
- Chart types from other packages can read data files too, by implementing `ChartType.from_table`; `Table` and `TableError` are part of `vizreel.plugin`.

### Changed

- The built-in themes set what surrounds the digits of a big number, a unit name, a currency or a percent sign, at 60% of the digits: a large `1,85` followed by a smaller `milyar TL`. `affix_scale` is now 0.6 by default; a theme sets it to 1 for the earlier look.

## [0.9.0] - 2026-09-28

### Added

- Every common frame rate: `meta.fps` and the new `--fps` option take 23.976, 24, 25, 29.97, 30, 50, 59.94 or 60, so a clip matches the editor's timeline instead of being blended. NTSC rates are stored exactly (29.97 is 30000/1001), and a clip has exactly `round(duration × fps)` frames at every rate.
- Square 1:1 clips for feeds: `aspect: "1:1"` or `--aspect 1:1`, named `ID.square.mov`. Each chart takes its landscape arrangement when it fits the square and its vertical one when it does not.
- `--format prores` writes ProRes 4444 with alpha (`ID.prores.mov`), the format professional editors expect for transparent clips, and `--format png` a folder of PNG frames with alpha that any editor imports as an image sequence.

### Changed

- The percent in the middle of a share chart shrinks to fit a ring that has little room, as other big numbers do, instead of making the chart an error.

### Fixed

- When a line chart's first-value label had to stack above the lines, a line climbing steeply just past the label's corner could touch it.

## [0.8.0] - 2026-09-28

### Added

- `sizes.affix_scale` in themes sets what surrounds the digits of a big number (a unit name, a currency, a percent sign) smaller than the digits, on their baseline: `affix_scale: 0.6` gives a large `1,85` followed by a smaller `milyar TL`. The built-in themes keep 1; the example brand theme uses 0.6.

### Changed

- A compact number counts in the unit of its final value: `0.37B` on the way to `1.85B` instead of passing through thousands and millions, so its unit and width no longer jump. A value too small in its unit to count smoothly, such as `2B`, still counts through the smaller units.
- A vertical chart with little content, such as three bars, a short timeline or a small table, no longer floats in the middle of an empty panel. The title, the source line and the panel close in around the content, and the card is centered in the safe area.

### Fixed

- Wrapped titles, subtitles and labels had almost no space between their lines, so a descender nearly touched the line below. Their baselines are now 1.2 times the font size apart.

## [0.7.0] - 2026-09-28

### Added

- Chart types from other packages. A package lists its chart types under the `vizreel.chart_types` entry point group, and once it is installed next to vizreel they validate, render, appear in `vizreel new` and in the JSON Schema like the built-in types. A package that fails to load, uses a built-in name or was written for another chart API version is skipped with a warning, and a spec that uses its type says why. [Writing a chart type](https://github.com/efedalbay/vizreel/blob/main/docs/PLUGINS.md) is the guide.
- `vizreel.plugin` and `vizreel.plugin.render`, the API for these chart types, versioned by `CHART_API_VERSION` (now 1).
- `vizreel types` lists every chart type and where it comes from.
- `examples/plugin`: an example plugin package with a `progress` chart type, a bar that fills toward a goal.

## [0.6.0] - 2026-09-28

### Added

- Number locales: `meta.locale` takes `tr-TR`, `es-ES`, `pt-BR` and `fr-FR` besides `en-US`. Each writes numbers the way its readers expect, following the Unicode CLDR: its separators (`1.846,5`, `1 846,5`), the place of the percent sign (`%47`, `47 %`) and the names of the compact units (`740 milyon`, `1,5 milhão`, `2 millions`), agreeing in number where the language has a plural.
- `compact: long` and `compact: short` choose full unit names or abbreviations in any locale: `740 million` or `740M`, `740 milyon` or `740 Mn`. `compact: true` keeps each locale's usual names.
- `examples/showcase-tr.yaml`: every chart type in Turkish.

### Changed

- The big number of a stat and the values of a compare shrink to fit when they are too wide for the frame, down to half their size, instead of being an error. The size fits the widest text the count shows and stays the same while it counts.

## [0.5.0] - 2026-09-28

### Added

- Sequences: a bar, line, timeline, waterfall, stacked, share or table chart takes a `sequence` of 2 to 8 elements to emphasize and renders one clip per element, `ID.1.mov`, `ID.2.mov` and so on. Each clip after the first starts on exactly the last frame of the one before and moves the emphasis on, so the clips cut together into one continuous chart. `step_duration` sets the length of those clips, 3 seconds by default.

### Changed

- The percent in the middle of a share chart fades in as it counts up.

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

[0.13.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.13.0
[0.12.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.12.0
[0.11.2]: https://github.com/efedalbay/vizreel/releases/tag/v0.11.2
[0.11.1]: https://github.com/efedalbay/vizreel/releases/tag/v0.11.1
[0.11.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.11.0
[0.10.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.10.0
[0.9.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.9.0
[0.8.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.8.0
[0.7.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.7.0
[0.6.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.6.0
[0.5.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.5.0
[0.4.4]: https://github.com/efedalbay/vizreel/releases/tag/v0.4.4
[0.4.3]: https://github.com/efedalbay/vizreel/releases/tag/v0.4.3
[0.4.2]: https://github.com/efedalbay/vizreel/releases/tag/v0.4.2
[0.4.1]: https://github.com/efedalbay/vizreel/releases/tag/v0.4.1
[0.4.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.4.0
[0.3.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.3.0
[0.2.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.2.0
[0.1.1]: https://github.com/efedalbay/vizreel/releases/tag/v0.1.1
[0.1.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.1.0
