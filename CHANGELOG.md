# Changelog

All notable changes to vizreel are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- A theme can bring its fonts as files: `fonts: { numbers: { file: fonts/IBMPlexMono-Regular.ttf } }` loads a TTF or OTF file next to the theme and reads its family from it, so the theme looks the same on any computer. Each role may now use its own family. `vizreel render` warns when the number font's digits do not share one width, which makes counting numbers shift.
- Background textures: `texture: { ruled: { spacing: 54, color: ..., margin: ... } }` draws ledger lines with an optional double margin line, and `texture: { image: { file: paper.png, fit: tile } }` a picture. In transparent output the texture fills the panel inside its round corners; in opaque output it covers the frame. Sizes scale with the resolution, every aspect works, and `vizreel theme check` checks text against a picture's average color.
- Accounting negatives: `number: { negative: parentheses }` writes `($1.2M)`, `(360)` or `(12%)` instead of a minus sign, in every locale, with the parentheses at the size of the digits. A fall in a `compare` or a `waterfall` step reads `($5.0M)`, a rise keeps `+$500K`. Data files may write negatives in parentheses too.
- A highlight ring: `highlight_mark: ring` in a theme draws a leaning pen ring around the highlighted value at the highlight beat, in the new optional `colors.mark` color, in `bar` charts (moving with a sequence's emphasis) and `stat` charts (after the count; a duration too short for it keeps its length, leaves the ring out and warns). It never crosses the value's text.
- Chart types can report warnings (`ChartType.warnings`), which `vizreel render` prints under the clip.
- Cue files: `vizreel render --cues` or `meta.cues: true` writes `ID.cues.json` next to each clip, with the seconds and frames of its title, structure, reveal, highlight, highlight ring (`mark`), hold, exit and last frame, for placing sound effects. Chart types name their animations with `scene.play(..., cue=...)`.

## [0.16.1] - 2026-10-01

### Changed

- Charts take about 30% less time to render. Every chart type but the races, which already did, now builds its growing bars, lines and counting numbers anew on each frame instead of reshaping the last frame's point by point. Frames look the same.
- Chart types from other packages can do the same with `render.redrawn_shapes`.
- The source package leaves out the README's GIFs, which the README shows from GitHub: 2.7 MB instead of 9.1 MB.

### Fixed

- A duration too short to read a text, or for a race's periods, suggests a duration rounded up, so following it is always enough: a clip of 3 seconds no longer asks for "at least 3.0s".
- `vizreel --help` and the package description mention Excel files, and the help of `--watch` says that it watches the data files a spec reads.
- The guides cover the scatter race, the title card and Excel workbooks everywhere they list chart types, theme colors and data files, and name the reading-time rule for every chart.

## [0.16.0] - 2026-10-01

### Added

- The `title-card` chart type: a headline that opens a video or a part of one, with a short `kicker` line above it and the `subtitle` under it, centered and appearing one line after another. The headline wraps onto up to three lines with its words spread evenly over them. Themes get an optional `sizes.headline`, 96 by default. The showcase opens with one.
- Data from Excel workbooks: `data: report.xlsx`, or `data: { file: report.xlsx, sheet: Markets, columns: [...] }`, gives every chart type that reads a CSV file the same data from a sheet. Numbers are read as the workbook stores them, whatever their format or the locale, dates as ISO text and formulas as their last calculated values; errors name the file, the sheet, the row and the column. `examples/data/northwind.xlsx` is an example workbook. vizreel now depends on openpyxl.
- Chart types, including those from other packages, can set `own_header = True` to set their title themselves, without a title band.

## [0.15.0] - 2026-09-29

### Added

- The `scatter-race` chart type: two to thirty points moving over up to 200 periods on two value axes, sized by a third value, the axes growing with the largest values seen so far. Names sit beside their points only where they are clear of every point and other name. `trail: true` draws the path of the followed series. Its CSV file has a row per period and series; `examples/data.yaml` races ten companies' revenue and staff through 24 years.

## [0.14.1] - 2026-09-29

### Fixed

- vizreel installs a Pillow below 13. Manim, which vizreel draws with, passes Pillow an argument that Pillow 13 removes, so the images of a race and a theme's logo would fail to render once Pillow 13 is out.

## [0.14.0] - 2026-09-29

### Added

- Brand colors: a theme names colors in `colors.brand`, `vizreel theme check` tests them like the other data colors, and a `bar-race` gives them to its series by name with `colors: { Contoso: contoso-coral }`. `examples/brand.yaml` races in the example brand theme's colors.
- Images in a `bar-race`: `images: { Northwind: logos/northwind.svg }` draws a logo or a flag, from a PNG, JPEG or SVG file next to the spec, at the end of the series' bar. `--watch` renders again when one is saved. The race in `examples/data.yaml` shows logos of the fictional companies.
- A logo in the theme: `logo: { file: logo.svg, height: 48 }` draws it in the lower right corner of every chart, inside the panel, appearing with the chart and leaving with the clip's exit. Chart types from other packages show it too; one that fits its own card can place it with `logo_corner`.
- A running total in a `bar-race`: `total: Market` shows the sum of every series under the period, after that label, counting as the race runs.
- Captions over a race: `captions: [{ period: "2008", text: "The crisis" }]` in a `bar-race` or `line-race` fades in at its period and stays until the next one, checked to stay long enough to be read.

### Changed

- In a 9:16 frame, and in a 1:1 frame when they do not fit beside the bars, a `bar-race` puts the names above the bars, so the bars keep the width they need.

## [0.13.0] - 2026-09-29

### Added

- The `bar-race` chart type: bars that grow and change places as their values change over up to 200 periods, the largest `show` of up to 30 series on screen, the period large above them. The race runs at one pace and slows to a stop on the last period; bars slide past each other briefly when their values cross, and enter or leave at the bottom. A followed series is drawn in the highlight color.
- The `line-race` chart type: one to six lines drawn through up to 200 periods by one pen, each with its name and value at its tip, the vertical axis growing with the largest value drawn so far.
- Both read their data from a CSV file, the periods in the first column and a series in each other column; `examples/data.yaml` races ten companies through 24 years.
- "Help test vizreel" in the README lists what has not been tested yet, macOS and transparent clips in DaVinci Resolve, with a test report form on GitHub Issues; a bug report form joins it.

### Changed

- Counting numbers are built much faster, which shortens the render of every chart that counts.
- The README is rewritten around what vizreel does today, with every chart type's sequence and CSV support at a glance, and the spec reference gains a table of contents and a table of all chart types, grouped as in the README.

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

[0.16.1]: https://github.com/efedalbay/vizreel/releases/tag/v0.16.1
[0.16.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.16.0
[0.15.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.15.0
[0.14.1]: https://github.com/efedalbay/vizreel/releases/tag/v0.14.1
[0.14.0]: https://github.com/efedalbay/vizreel/releases/tag/v0.14.0
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
