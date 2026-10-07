# vizreel

**Animated charts for video, from YAML, CSV and Excel files.**

vizreel turns a short YAML file, with the data written in it or read from a CSV file or an Excel sheet, into animated chart clips that are ready to drop into a video editor: big numbers that count, bars that grow, lines that draw, races through the years. Each chart becomes its own clip, with a transparent background by default, so it sits directly over your footage.

> **Status: 0.17.0, an early release.** The spec format is version 1. See the [changelog](https://github.com/efedalbay/vizreel/blob/main/CHANGELOG.md) and the [roadmap](https://github.com/efedalbay/vizreel/blob/main/docs/ROADMAP.md).

| | |
|---|---|
| ![A stat chart counting up to $740M](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/stat.gif) | ![A progress ring filling to 68% of a fundraising goal](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/progress.gif) |
| ![A line chart drawing from left to right](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/line.gif) | ![A stacked area chart of users by platform](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/area.gif) |
| ![A bar chart with one highlighted bar](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/bar.gif) | ![A grouped bar chart comparing two years in four regions](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/grouped.gif) |
| ![A bar chart race in which Northwind climbs to first place](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/bar-race.gif) | ![A line race drawing users by platform](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/line-race.gif) |
| ![A compare chart counting from 1,200 down to 340, a change of −72%](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/compare.gif) | ![A waterfall chart from revenue to profit](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/waterfall.gif) |
| ![A stacked bar chart of revenue by product](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/stacked.gif) | ![A share ring with 47% in the middle](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/share.gif) |
| ![A timeline with an emphasized event](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/timeline.gif) | ![A table with a highlighted row](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/table.gif) |
| ![A scatter race of revenue and staff with Northwind's path](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/scatter-race.gif) | ![A title card whose kicker, headline and subtitle appear in turn](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/title-card.gif) |

## Why vizreel

Most chart tools are made for reports and dashboards. On video their charts look static and crowded, and animating each one by hand in a motion graphics tool takes time.

- **Describe, don't animate.** You write the chart and its data in YAML, or point to a CSV file or an Excel sheet; vizreel does the motion. No code, no timeline.
- **Made to be watched.** Large type, one message per chart, a clear highlight moment, eased motion and a clean final frame, following written [design rules](https://github.com/efedalbay/vizreel/blob/main/docs/DESIGN.md).
- **Ready for your editor.** One clip per chart, transparent, at your timeline's frame rate, in landscape, vertical or square, up to 4K.
- **Consistent.** Colors, fonts and timing come from a theme, so every chart in a video matches.
- **Easy to install.** Pure Python: no LaTeX, no separate FFmpeg.

## Installation

vizreel needs Python 3.11 or 3.12. It is tested on Windows and Linux; macOS has [not been tested yet](#help-test-vizreel).

With [uv](https://docs.astral.sh/uv/) (recommended), which puts the `vizreel` command on your PATH:

```bash
uv tool install vizreel
vizreel --version
```

With pip, in a virtual environment. On Windows, in PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install vizreel
vizreel --version
```

If PowerShell says that running scripts is disabled, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and activate again. On Linux and macOS, activate with `source .venv/bin/activate`.

## Quickstart

Start from a template, render a quick preview, and look at it:

```bash
vizreel new stat -o chart.yaml
vizreel render chart.yaml --quality preview --still
```

```
out/
├── customers.preview.mov    ← a quick, low-resolution clip with a transparent background
└── customers.preview.png    ← its last frame
```

Open `chart.yaml`, change the number and the label, and render again. Add `--watch` and vizreel renders again every time you save. When the preview looks right, render the clip you edit with:

```bash
vizreel render chart.yaml
```

This writes `out/customers.mov`: 1080p at 60 frames per second unless the spec says otherwise. Previews have their own file names, so they never replace a final clip.

## How a spec works

A spec is a YAML file with a `version`, optional shared settings in `meta`, and a list of `charts`. Each chart has an `id`, which names its clip, a `type`, and its data: written in the spec, or read from a CSV file or an Excel sheet. Here the data is written in the spec:

```yaml
version: 1
meta:
  theme: default
  resolution: 1080p

charts:
  - id: peak-valuation
    type: stat
    value: 740000000
    label: Northwind's peak valuation
    number: { prefix: "$", compact: true }

  - id: offers
    type: bar
    title: Offers Northwind received
    bars:
      - { label: "Buyer A (2015)", value: 740000000 }
      - { label: "Buyer B (2016)", value: 70000000 }
      - { label: "Buyer C (2016)", value: 40000000 }
    number: { prefix: "$", compact: true }
    highlight: { label: "Buyer C (2016)" }
```

```bash
vizreel render charts.yaml
```

```
out/
├── peak-valuation.mov    ← $740M, counting up
└── offers.mov            ← three bars growing, then Buyer C highlighted
```

The same bars could come from a spreadsheet instead: `data: data/offers.csv`, or a sheet of a workbook such as `data: data/offers.xlsx`, in place of `bars` (see [Data from CSV and Excel files](#data-from-csv-and-excel-files)); every chart type but `stat`, `progress` and `title-card` can read one. Values are always plain numbers; `number` decides how they are written (`$740M`). Every chart can also have a `title`, a `subtitle`, a `source` line and a `duration`. `vizreel validate charts.yaml` lists every mistake at once with its location, such as `charts[1].bars[2].value: must be at least 0, got -4`. The [spec reference](https://github.com/efedalbay/vizreel/blob/main/docs/SPEC.md) describes every field, and `vizreel new TYPE` prints a commented template for each chart type.

## Chart types

| Type | Use it for | Sequence | Data file |
|---|---|---|---|
| `stat` | One number the viewer must remember, counting up to its value | | |
| `progress` | How far a value has come toward a goal, as a bar or a ring that fills | | |
| `compare` | One measure before and after, with the change in percent or as a difference | | ✓ |
| `line` | Values over time, up to 3 series, with a highlighted point | ✓ | ✓ |
| `area` | Amounts over time as filled areas, up to 3 series, overlapping or stacked | ✓ | ✓ |
| `timeline` | Up to 7 events in order, with one emphasized | ✓ | ✓ |
| `bar` | Up to 8 categories, as columns or rows, with one highlighted | ✓ | ✓ |
| `grouped` | Bars side by side in groups of 2 or 3, such as two years in each region | ✓ | ✓ |
| `stacked` | Bars made of 2 or 3 parts, such as revenue per year split by product | ✓ | ✓ |
| `waterfall` | How a start becomes a total through up to 6 increases and decreases | ✓ | ✓ |
| `share` | How a whole divides into up to 6 parts, as a ring | ✓ | ✓ |
| `table` | A few rows and columns of numbers or text | ✓ | ✓ |
| `bar-race` | Bars racing through up to 200 periods, changing places as they pass each other | | ✓ |
| `line-race` | Lines racing through up to 200 periods, the axis growing with them | | ✓ |
| `scatter-race` | Points moving on two axes through up to 200 periods, sized by a third value | | ✓ |
| `title-card` | A headline that opens a video or a part of it, with a line above and under it | | |

**Sequence**: the chart can be told in several clips that cut together ([below](#sequences)). **Data file**: it can read its data from a CSV file or an Excel sheet ([below](#data-from-csv-and-excel-files)). Other packages can add chart types too ([Extending vizreel](#extending-vizreel)).

## Features

### Vertical and square clips

The same spec renders as vertical 9:16 clips for Shorts, Reels and TikTok, or as square clips for feeds:

```bash
vizreel render charts.yaml --aspect 9:16
vizreel render charts.yaml --aspect 1:1
```

Text keeps its size; charts rearrange instead. In a vertical frame bars become rows, timelines run down the frame, long titles wrap, and a chart with little content gets a card that fits it. Wider margins keep everything clear of the buttons and captions those apps draw over the video. A square frame uses the landscape arrangement where it fits and the vertical one where it does not. Vertical clips are named `ID.vertical.mov` and square ones `ID.square.mov`; set `aspect` in `meta` to make one the default.

### Data from CSV and Excel files

A chart can take its data from a CSV file or a sheet of an Excel workbook:

```yaml
- id: regions
  type: bar
  title: Northwind revenue by region
  data: data/regions.csv
  number: { prefix: "$", compact: true }
```

The first row names the columns; a bar chart reads a label and a value from each row after it. Commas, semicolons and tabs all work, numbers may be written as your locale writes them (`1.234,5` with `locale: tr-TR`), and an error names the file, row and column. From a workbook, `data: { file: data/northwind.xlsx, sheet: Markets }` reads one sheet, the first if `sheet` is left out; numbers are read as Excel stores them, not as it shows them: a cell showing `$412,000,000` is 412000000, and one showing `12%` is 0.12. With more columns than a chart reads, `columns: [Market, Revenue]` picks them. [`examples/data.yaml`](https://github.com/efedalbay/vizreel/blob/main/examples/data.yaml) has a chart of every type that reads one, including a race of ten companies through 24 years. The spec reference says [what each type reads](https://github.com/efedalbay/vizreel/blob/main/docs/SPEC.md#data-from-files).

### Sequences

When a narration walks through a chart ("first 2016... then 2018..."), tell the chart as a sequence: one clip per element to emphasize, each continuing from the last.

```yaml
- id: history
  type: timeline
  events:
    - { date: "2016", label: "Founded" }
    - { date: "2018", label: "Opens offices in three countries" }
    - { date: "2020", label: "Reaches one million users" }
  sequence: ["2016", "2018", "2020"]
```

This renders `history.1.mov`, `history.2.mov` and `history.3.mov`. The first draws the chart and emphasizes 2016; each later clip starts on exactly the last frame of the one before and moves the emphasis on. Put them one after another on a track, with your narration between the moves, and they play as one continuous chart. See [Sequences](https://github.com/efedalbay/vizreel/blob/main/docs/SPEC.md#sequences).

### Motion

By default the panel and titles fade in and the clip ends on the complete chart, which an editor can freeze. `motion` makes them rise or grow into place instead, lets the clip leave the screen by itself at the end, and chooses the easing:

```yaml
- id: offers-motion
  type: bar
  bars:
    - { label: North, value: 412 }
    - { label: South, value: 298 }
  motion: { entrance: rise, exit: fade }
```

The exit is part of the clip's duration, after the full hold. `meta.motion` sets motion for every chart at once. See [Motion](https://github.com/efedalbay/vizreel/blob/main/docs/SPEC.md#motion).

### Number locales

Numbers are written the way your audience reads them. Set `locale` in `meta` to `en-US` (the default), `tr-TR`, `es-ES`, `pt-BR` or `fr-FR`:

| | `en-US` | `tr-TR` | `es-ES` | `pt-BR` | `fr-FR` |
|---|---|---|---|---|---|
| Number | `1,846.5` | `1.846,5` | `1846,5` | `1.846,5` | `1 846,5` |
| Percent | `47%` | `%47` | `47 %` | `47%` | `47 %` |
| Compact | `740M` | `740 milyon` | `740 millones` | `740 milhões` | `740 millions` |

`compact: long` or `compact: short` chooses full unit names or abbreviations in any locale. Titles, labels and dates are shown as you write them. See [Locales](https://github.com/efedalbay/vizreel/blob/main/docs/SPEC.md#locales), and [`examples/showcase-tr.yaml`](https://github.com/efedalbay/vizreel/blob/main/examples/showcase-tr.yaml) for every chart type in Turkish.

### Themes

A theme sets the colors, fonts, text sizes and motion timing of every chart. vizreel ships two, `default` (dark) and `light`; your own is a YAML file you point to from the spec:

```yaml
meta:
  theme: themes/my-brand.yaml
```

A theme can also carry your logo, drawn in the corner of every chart; named brand colors, which a race gives to companies so each races in its own color; its fonts as files, so it looks the same on any computer; ruled lines or a picture behind the chart, such as ledger paper; and a pen ring around the highlighted value. [`examples/themes/example-ledger.yaml`](https://github.com/efedalbay/vizreel/blob/main/examples/themes/example-ledger.yaml) puts these together. Start from [`examples/themes/example-brand.yaml`](https://github.com/efedalbay/vizreel/blob/main/examples/themes/example-brand.yaml), and run `vizreel theme check` on it to test its contrast and its colors for color vision deficiency. The [theme reference](https://github.com/efedalbay/vizreel/blob/main/docs/THEMES.md) describes every field.

## Using the clips in a video editor

By default clips are `mov` files (QuickTime Animation) with a transparent background: place them on a track above your footage. Many media players, such as the Windows media player, cannot play them; that is expected, open them in your editor. Other formats, with `--format` or `format` in `meta`:

| Format | Transparent | Use it for |
|---|---|---|
| `mov` (default) | yes | Most editors. Tested in CapCut on Windows. |
| `prores` | yes | ProRes 4444 (`ID.prores.mov`), the format professional editors such as DaVinci Resolve, Premiere Pro and Final Cut Pro expect for transparent clips. |
| `png` | yes | A folder of numbered PNG frames, which any editor imports as an image sequence. |
| `webm` | yes | Web use. CapCut on Windows shows it on a dark background. |
| `mp4` | no | When you do not need transparency: the chart is drawn on the theme's background color. |

Match `--fps` to your timeline (`23.976`, `24`, `25`, `29.97`, `30`, `50`, `59.94` or `60`); a clip at another rate gets blended or loses frames. Every clip is exactly as long as its `duration`, down to the frame.

## Command reference

```bash
vizreel new line -o charts.yaml         # start from a commented template
vizreel validate charts.yaml            # check a spec and list every error
vizreel render charts.yaml              # render every chart to ./out
vizreel render charts.yaml --only offers --quality preview --still
vizreel render charts.yaml --quality preview --still --watch   # render again on every save
vizreel types                           # every chart type, built-in or from a plugin
vizreel themes list                     # the built-in themes
vizreel theme check my-brand.yaml       # contrast and color vision checks for a theme
vizreel schema -o vizreel.schema.json   # JSON Schema for editors and tools
```

| `render` option | Description |
|---|---|
| `--out DIR` | Output folder (default `out`) |
| `--only ID` | Render only this chart; repeat for several |
| `--quality preview\|final` | `preview` is low resolution and fast, and writes `ID.preview.mov`; `final` uses the spec settings |
| `--format mov\|webm\|mp4\|prores\|png` | Output format; see [Using the clips in a video editor](#using-the-clips-in-a-video-editor) |
| `--aspect 16:9\|9:16\|1:1` | Frame shape: landscape, vertical (`ID.vertical.mov`) or square (`ID.square.mov`) |
| `--fps RATE` | Frames per second of a final render. Default `meta.fps`, or 60 |
| `--still` | Also save the final frame as a PNG |
| `--cues` | Also write `ID.cues.json` with the seconds and frames of each clip's title, data, highlight, ring, hold and last frame, for placing sound effects. See [Cue files](https://github.com/efedalbay/vizreel/blob/main/docs/SPEC.md#cue-files) |
| `--watch` | Keep running and render again whenever the spec, its theme file or a data file is saved. Only charts that changed are rendered; an invalid spec prints its errors and watching goes on. Ctrl+C stops |

Options on the command line override the spec's `meta`. `vizreel --debug COMMAND` shows the full traceback of an unexpected error.

## Help test vizreel

Two things have not been tested yet, because we do not have the setup:

- **macOS**: installing vizreel and rendering the showcase.
- **DaVinci Resolve**: whether transparent clips (`mov`, `prores`, `png`, `webm`) keep their transparency over footage.

If you can try one of them, or any editor not listed above, please [open a test report](https://github.com/efedalbay/vizreel/issues/new?template=test-report.yml). A report that something works helps as much as one that it does not. To render every chart type:

```bash
vizreel render examples/showcase.yaml --format prores
```

(from a clone of this repository; `examples/showcase.yaml` has one chart of every type).

## Extending vizreel

- **Chart types from other packages.** Install a package that provides chart types next to vizreel, and its types validate, render and have templates like the built-in ones. `vizreel types` lists every type and where it comes from. [Writing a chart type](https://github.com/efedalbay/vizreel/blob/main/docs/PLUGINS.md) is the guide, and [`examples/plugin`](https://github.com/efedalbay/vizreel/tree/main/examples/plugin) a complete example.
- **Editors and AI assistants.** `vizreel schema -o vizreel.schema.json` writes the JSON Schema of the spec format. Editors such as VS Code use it to complete and check specs as you type, and tools that write specs can check theirs against it; see [JSON Schema](https://github.com/efedalbay/vizreel/blob/main/docs/SPEC.md#json-schema).

## Documentation

| Document | What it covers |
|---|---|
| [Spec reference](https://github.com/efedalbay/vizreel/blob/main/docs/SPEC.md) | Every field of every chart type, number formats, locales, sequences, motion and data files |
| [Theme reference](https://github.com/efedalbay/vizreel/blob/main/docs/THEMES.md) | Writing and checking a theme |
| [Design rules](https://github.com/efedalbay/vizreel/blob/main/docs/DESIGN.md) | The visual rules every chart follows, and how to choose a chart type |
| [Writing a chart type](https://github.com/efedalbay/vizreel/blob/main/docs/PLUGINS.md) | Adding chart types from your own package |
| [Architecture](https://github.com/efedalbay/vizreel/blob/main/docs/ARCHITECTURE.md) | How the code is organized, for contributors |
| [Roadmap](https://github.com/efedalbay/vizreel/blob/main/docs/ROADMAP.md) and [changelog](https://github.com/efedalbay/vizreel/blob/main/CHANGELOG.md) | What was planned, and what each release changed |

## Development

```bash
git clone https://github.com/efedalbay/vizreel.git
cd vizreel
uv sync
uv run pytest -m "not render"   # fast tests
uv run pytest -m render         # rendering tests
uv run ruff check . ; uv run mypy src
```

## Contributing

Issues and pull requests are welcome. Report a problem with the [bug report form](https://github.com/efedalbay/vizreel/issues/new?template=bug-report.yml), and before starting on a larger change, open an issue to discuss it. New chart types follow the [chart type contract](https://github.com/efedalbay/vizreel/blob/main/docs/ARCHITECTURE.md#chart-type-contract) and the [design rules](https://github.com/efedalbay/vizreel/blob/main/docs/DESIGN.md).

## License

[MIT](https://github.com/efedalbay/vizreel/blob/main/LICENSE)

vizreel is built on [Manim Community Edition](https://www.manim.community/). It bundles the [Inter](https://rsms.me/inter/) typeface by The Inter Project Authors, licensed under the SIL Open Font License 1.1 (see `src/vizreel/assets/fonts/Inter-OFL.txt`).
