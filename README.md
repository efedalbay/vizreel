# vizreel

**Animated charts for video, from a YAML file.**

vizreel turns a short YAML spec into clean, animated chart clips (big numbers, progress toward a goal, line and area charts, bar charts, timelines, before/after comparisons, waterfalls, stacked and grouped bars, shares of a whole and tables) ready to drop into any video editor. Clips render with a transparent background by default, so they layer directly over your footage.

> **Status: 0.11.2, an early release.** The spec format is version 1. See the [changelog](https://github.com/efedalbay/vizreel/blob/main/CHANGELOG.md) and the [roadmap](https://github.com/efedalbay/vizreel/blob/main/docs/ROADMAP.md).

| | |
|---|---|
| ![A stat chart counting up to $740M](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/stat.gif) | ![A line chart drawing from left to right](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/line.gif) |
| ![A bar chart with one highlighted bar](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/bar.gif) | ![A timeline with an emphasized event](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/timeline.gif) |
| ![A compare chart counting from 1,200 down to 340, a change of −72%](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/compare.gif) | ![A waterfall chart from revenue to profit](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/waterfall.gif) |
| ![A stacked bar chart of revenue by product](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/stacked.gif) | ![A share ring with 47% in the middle](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/share.gif) |
| ![A table with a highlighted row](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/table.gif) | ![A grouped bar chart comparing two years in four regions](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/grouped.gif) |
| ![A stacked area chart of users by platform](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/area.gif) | ![A progress ring filling to 68% of a fundraising goal](https://raw.githubusercontent.com/efedalbay/vizreel/main/docs/images/progress.gif) |

## Why

Most chart tools are made for reports and dashboards. On video they look static and crowded, and animating them by hand in a motion graphics tool takes time for every chart.

vizreel is built for video from the start:

- **Declarative.** Describe the chart and its data in YAML. No code, no timeline editing.
- **Made to be watched.** Large type, one message per chart, a clear highlight moment, smooth eased motion, a clean final frame. See the [design rules](https://github.com/efedalbay/vizreel/blob/main/docs/DESIGN.md).
- **Editor-ready.** One clip per chart, transparent background, 1080p or 4K at the frame rate of your timeline, landscape, vertical or square.
- **Consistent.** Colors, fonts and timing come from a theme, so every chart in a video matches.
- **Easy to install.** Pure Python. No LaTeX, no separate FFmpeg install.

## Installation

**Requirements:** Python 3.11 or 3.12 on Windows or Linux. Other Python versions and macOS may work but are untested.

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

Create a spec from a template, then render it:

```bash
vizreel new stat -o chart.yaml
vizreel render chart.yaml --quality preview --still
```

```
out/
├── customers.preview.mov    ← a quick, low-resolution clip with a transparent background
└── customers.preview.png    ← its last frame
```

Open `chart.yaml`, change the number and the label, and render again. When the preview looks right, render without `--quality preview` for the clip you edit with, `customers.mov`: 1080p at 60 fps unless the spec says otherwise. Preview files have their own names, so they never replace a final clip.

## Example

A spec can hold several charts; each renders to its own clip:

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
├── peak-valuation.mov
└── offers.mov
```

## Chart types

| Type | Use it for |
|---|---|
| `stat` | One number the viewer must remember, counting up to its value |
| `progress` | How far a value has come toward a goal, as a bar or a ring that fills |
| `line` | Values over time, up to 3 series, with an optional highlighted point |
| `area` | Amounts over time as filled areas, up to 3 series, overlapping or stacked into a total |
| `bar` | Comparing up to 8 categories, with one highlighted bar, as columns or rows |
| `timeline` | A sequence of up to 7 events, with an emphasized moment |
| `compare` | One measure before and after, with the change in percent or as a difference |
| `waterfall` | How a starting value becomes a total through up to 6 increases and decreases |
| `stacked` | Bars made of 2 or 3 parts, e.g. revenue per year split by product |
| `grouped` | Bars side by side in groups of 2 or 3, e.g. two years compared in each region |
| `share` | How a whole divides into up to 6 parts, as a ring with the key part's percent inside |
| `table` | A few rows and columns of numbers or text, the rows appearing one after another |

`vizreel new TYPE` prints a commented template for each. Every field is documented in the [spec reference](https://github.com/efedalbay/vizreel/blob/main/docs/SPEC.md).

Other packages can add chart types: install one next to vizreel and its type works like the built-in ones. `vizreel types` lists every type and where it comes from. To write your own, see [Writing a chart type](https://github.com/efedalbay/vizreel/blob/main/docs/PLUGINS.md) and the example plugin in [`examples/plugin`](https://github.com/efedalbay/vizreel/tree/main/examples/plugin).

## Vertical and square clips

The same spec renders as vertical 9:16 clips for Shorts, Reels and TikTok:

```bash
vizreel render charts.yaml --aspect 9:16
```

Text stays the same size; charts rearrange for the narrow frame instead. Bar charts become rows, timelines run down the frame and long titles wrap onto a second line. A wider margin at the top and bottom keeps charts clear of the buttons and captions those apps draw over the video. To make vertical the default for a spec, set `aspect: "9:16"` in its `meta`.

For square feed posts, use `--aspect 1:1`. A square frame is as narrow as a vertical one but not as tall, so each chart takes its landscape arrangement when it fits and its vertical one when it does not: three bars stay columns, five become rows.

## Sequences

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

This renders `history.1.mov`, `history.2.mov` and `history.3.mov`. The first draws the chart and emphasizes 2016; each later clip starts on exactly the last frame of the one before and moves the emphasis on. Put them one after another on a track, with your narration between the moves, and they play as one continuous chart. Bar, line, area, timeline, waterfall, stacked, grouped, share and table charts can be told as sequences; see the [spec reference](https://github.com/efedalbay/vizreel/blob/main/docs/SPEC.md#sequences).

## Data from CSV files

A chart can read its data from a CSV file, such as one exported from a spreadsheet, instead of the spec:

```yaml
- id: regions
  type: bar
  title: Northwind revenue by region
  data: data/regions.csv
  number: { prefix: "$", compact: true }
```

The first row of the file names the columns, and a bar chart reads a label and a value from each row after it. Commas, semicolons and tabs all work, and numbers may be written the way your locale writes them (`1.234,5` with `locale: tr-TR`). An error names the file, row and column, and `--watch` renders again when the file is saved. Every chart type but `stat` can read one; see the [spec reference](https://github.com/efedalbay/vizreel/blob/main/docs/SPEC.md#data-from-files) for what each reads, and [`examples/data.yaml`](https://github.com/efedalbay/vizreel/blob/main/examples/data.yaml).

## Number locales

Numbers are written the way your audience reads them. Set `locale` in the spec's `meta` to `en-US` (the default), `tr-TR`, `es-ES`, `pt-BR` or `fr-FR`:

| | `en-US` | `tr-TR` | `es-ES` | `pt-BR` | `fr-FR` |
|---|---|---|---|---|---|
| Number | `1,846.5` | `1.846,5` | `1846,5` | `1.846,5` | `1 846,5` |
| Percent | `47%` | `%47` | `47 %` | `47%` | `47 %` |
| Compact | `740M` | `740 milyon` | `740 millones` | `740 milhões` | `740 millions` |

`compact: long` or `compact: short` chooses between full unit names and abbreviations in any locale: `740 million` or `740M`, `740 milyon` or `740 Mn`. Labels, titles and dates are shown as you write them. See the [spec reference](https://github.com/efedalbay/vizreel/blob/main/docs/SPEC.md#locales) for the details, and [`examples/showcase-tr.yaml`](https://github.com/efedalbay/vizreel/blob/main/examples/showcase-tr.yaml) for every chart type in Turkish.

## Usage

```bash
vizreel new line -o charts.yaml         # start from a commented template
vizreel validate charts.yaml            # check a spec and list every error
vizreel render charts.yaml              # render all charts to ./out
vizreel render charts.yaml --only offers --quality preview --still
vizreel render charts.yaml --quality preview --still --watch   # render again on every save
vizreel render charts.yaml --aspect 9:16   # vertical clips for Shorts
vizreel render examples/sequence.yaml   # a chart told as three clips
vizreel schema -o vizreel.schema.json   # JSON Schema for editors and tools
vizreel types                           # every chart type, built-in or from a plugin
vizreel themes list                     # built-in themes
vizreel theme check my-brand.yaml       # contrast and color vision checks for a theme
```

| `render` option | Description |
|---|---|
| `--out DIR` | Output folder (default `out`) |
| `--only ID` | Render only this chart; repeat for several |
| `--quality preview\|final` | `preview` is low resolution and fast, and writes `ID.preview.mov`; `final` uses the spec settings |
| `--format mov\|webm\|mp4\|prores\|png` | `mov`, `webm`, `prores` (ProRes 4444, `ID.prores.mov`) and `png` (a folder of PNG frames) keep transparency; `mp4` uses the theme background |
| `--still` | Also save the final frame as a PNG |
| `--fps RATE` | Frames per second of a final render: `23.976`, `24`, `25`, `29.97`, `30`, `50`, `59.94` or `60`. Match your editor's timeline. Default `meta.fps`, or 60 |
| `--aspect 16:9\|9:16\|1:1` | `9:16` renders vertical clips for Shorts, Reels and TikTok, named `ID.vertical.mov`; `1:1` renders square clips for feeds, named `ID.square.mov` |
| `--watch` | Keep running and render again whenever the spec, its theme file or a data file is saved. Only the charts that changed are rendered; an invalid spec prints its errors and watching goes on. Ctrl+C stops |

## Using the clips in a video editor

`mov` clips (the default) keep a transparent background: place them on a track above your footage. They use the QuickTime Animation codec, which editors read but many media players, such as the Windows media player, cannot play. That is expected; open them in your editor.

| Editor (Windows) | `mov` (default) | `webm` | `mp4` |
|---|---|---|---|
| CapCut | Transparent | Not transparent (dark background) | Opaque, by design |
| DaVinci Resolve | Not tested yet | Not tested yet | Opaque, by design |

`webm` clips also contain transparency, but not every editor reads it. `--format prores` writes ProRes 4444, the format professional editors such as DaVinci Resolve, Premiere Pro and Final Cut Pro expect for transparent clips, and `--format png` a folder of PNG frames that any editor imports as an image sequence. Use `--format mp4` when you do not need transparency: the chart is drawn on the theme's background color.

## Themes

A theme sets colors, fonts, text sizes and motion timing for every chart. vizreel ships with two built-in themes, `default` (dark) and `light`, and you can write your own in YAML and point to it from your spec:

```yaml
meta:
  theme: themes/my-brand.yaml
```

Start from [`examples/themes/example-brand.yaml`](https://github.com/efedalbay/vizreel/blob/main/examples/themes/example-brand.yaml), and run `vizreel theme check` on your theme to test its contrast and its colors for color vision deficiency. Every field is described in the [theme reference](https://github.com/efedalbay/vizreel/blob/main/docs/THEMES.md).

## Documentation

- [Spec reference](https://github.com/efedalbay/vizreel/blob/main/docs/SPEC.md)
- [Theme reference](https://github.com/efedalbay/vizreel/blob/main/docs/THEMES.md)
- [Design rules](https://github.com/efedalbay/vizreel/blob/main/docs/DESIGN.md)
- [Writing a chart type](https://github.com/efedalbay/vizreel/blob/main/docs/PLUGINS.md)
- [Architecture](https://github.com/efedalbay/vizreel/blob/main/docs/ARCHITECTURE.md)
- [Roadmap](https://github.com/efedalbay/vizreel/blob/main/docs/ROADMAP.md)
- [Changelog](https://github.com/efedalbay/vizreel/blob/main/CHANGELOG.md)

## Development

```bash
git clone https://github.com/efedalbay/vizreel.git
cd vizreel
uv sync
uv run pytest -m "not render"   # fast tests
uv run pytest -m render         # rendering tests
```

## Contributing

Issues and pull requests are welcome. Before starting on a larger change, please open an issue to discuss it. New chart types follow the contract in the [architecture document](https://github.com/efedalbay/vizreel/blob/main/docs/ARCHITECTURE.md#chart-type-contract) and the rules in the [design document](https://github.com/efedalbay/vizreel/blob/main/docs/DESIGN.md).

## License

[MIT](https://github.com/efedalbay/vizreel/blob/main/LICENSE)

vizreel is built on [Manim Community Edition](https://www.manim.community/). It bundles the [Inter](https://rsms.me/inter/) typeface by The Inter Project Authors, licensed under the SIL Open Font License 1.1 (see `src/vizreel/assets/fonts/Inter-OFL.txt`).
