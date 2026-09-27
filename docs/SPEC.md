# Spec format (version 1)

A spec is a YAML file that describes one or more charts. This document is the source of truth for the format: if the code and this file disagree, one of them is a bug.

All examples in this document use a fictional company, Northwind, and made-up numbers.

## Minimal example

```yaml
version: 1
charts:
  - id: users
    type: stat
    value: 1200000
    label: Monthly users
```

```bash
vizreel render users.yaml
```

To start from a commented template of any chart type:

```bash
vizreel new line -o revenue.yaml
```

## Top level

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `version` | integer | yes | — | Spec format version. Currently `1`. |
| `meta` | object | no | see below | Settings shared by all charts. |
| `charts` | list | yes | — | One or more charts. Each renders to its own file. |

### Rules that apply everywhere

- **Unknown fields are errors.** A misspelled field such as `lable:` is reported, not ignored.
- **Numbers are numbers, text is text.** A number field does not accept text (`"740M"`, `"12"`), and a text field does not accept a number. Put years and dates in quotes (`"2016"`, `"Mar 2016"`): unquoted, YAML reads `2016` as a number and `2016-03-01` as a date. YAML also reads `yes`, `no`, `on`, `off`, `true` and `false` as booleans, so quote them when you mean text.
- **Text fields cannot be empty**, except `prefix` and `suffix`.
- `inf` and `nan` are not valid numbers.

## `meta`

| Field | Type | Default | Description |
|---|---|---|---|
| `title` | string | — | Human-readable name of the spec. Not rendered. |
| `theme` | string | `default` | Built-in theme name, or a path to a theme YAML file (relative to the spec file). |
| `resolution` | `720p` \| `1080p` \| `1440p` \| `4k` | `1080p` | Output resolution, named by the short side of the frame: `1080p` is 1920×1080, or 1080×1920 at `9:16`. |
| `aspect` | `16:9` \| `9:16` | `16:9` | Frame shape. `16:9` is landscape; `9:16` is vertical, for Shorts, Reels and TikTok, and keeps clear of the platforms' buttons and captions. Vertical clips are named `ID.vertical.mov`. Quote the value: `aspect: "9:16"`. |
| `fps` | `30` \| `60` | `60` | Frames per second. |
| `format` | `mov` \| `webm` \| `mp4` | `mov` | `mov` and `webm` have a transparent background. `mp4` is opaque and uses the theme background color. |
| `locale` | `en-US` | `en-US` | Number and date formatting. Only `en-US` in v1. |

CLI flags override `meta` values.

## Fields shared by every chart

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `id` | string `[a-z0-9-]+` | yes | — | Unique in the spec. Used as the output file name, so it cannot be a name Windows reserves (`con`, `prn`, `aux`, `nul`, `com1`–`com9`, `lpt1`–`lpt9`). |
| `type` | string | yes | — | Chart type: `stat`, `line`, `bar`, `timeline`. |
| `title` | string | no | — | Shown at the top of the chart. Wraps onto a second line if it does not fit the width; a title that does not fit on two lines is an error. |
| `subtitle` | string | no | — | Smaller line under the title. Wraps like the title. |
| `source` | string | no | — | Short source label shown at the bottom, e.g. `"Source: Axios, 2023"`. Keep it short; it is on screen. |
| `duration` | number (seconds) | no | depends on type | Total clip length, including the final hold. Minimum 2. |
| `highlight` | object | no | — | Type-specific emphasis. See each type. `stat` has no `highlight`. |

### Number format (`number`)

Used by any field that displays values.

| Field | Type | Default | Example output |
|---|---|---|---|
| `prefix` | string | `""` | `$` |
| `suffix` | string | `""` | `%`, ` users` |
| `decimals` | integer, 0–6 | auto | `1` → `4.2` |
| `compact` | boolean | `false` | `true` → `740M`, `2.25B` |

Values in the spec are always plain numbers. `740000000` with `prefix: "$"` and `compact: true` renders as `$740M`. Never write `"740M"` as a value.

Formatting rules (en-US):

- **Thousands separators:** `1200000` → `1,200,000`.
- **Automatic decimals** (no `decimals` set): whole numbers get none; other numbers get at most 2, without trailing zeros (`4.2`, `0.05`, `1.23`). With `compact: true`, abbreviated numbers keep 3 significant digits (`740M`, `2.25B`, `1.2M`, `12.3M`).
- **Fixed decimals** (`decimals` set): always that many, trailing zeros kept (`decimals: 2` → `2.20`). With `compact: true`, `decimals` applies to the abbreviated number (`decimals: 1` → `740.0M`).
- **Compact units:** `K` from 1,000, `M` from 1,000,000, `B` from 1,000,000,000, `T` from 1,000,000,000,000. Numbers below 1,000 are not abbreviated. When rounding reaches 1,000 of a unit, the next unit is used: `999950` → `1M`, not `1000K`.
- **Rounding:** halves round away from zero: `2.675` → `2.68`, `2.5` → `3`.
- **Negative numbers:** the minus sign (−, U+2212) comes before the prefix: `−$1.2M`. A value that rounds to zero never shows a sign.
- **Same decimals within a chart:** values shown together in one chart, such as axis or bar labels, share the number of decimals of the most precise value: `$0.05B`, `$0.20B`, `$2.25B`. With `compact: true`, only values with the same unit share decimals: `$1.25B`, `$412.0M`, `$7.8M`.

---

## `stat` — big number card

A single number that counts up (or down) to its value. Use it for the one figure the viewer must remember.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `value` | number | yes | — | Final value. |
| `start` | number | no | `0` | Value the count starts from. |
| `label` | string | no | — | Line under the number. |
| `number` | number format | no | — | Formatting of the value. |
| `trend` | `up` \| `down` \| `none` | no | `none` | Colors the number with `positive` / `negative` from the theme. |

Default `duration`: 3.

```yaml
- id: peak-valuation
  type: stat
  value: 740000000
  label: Northwind's peak valuation
  number: { prefix: "$", compact: true }
  source: "Source: example data"
```

## `line` — values over time

One or more series drawn from left to right.

Each line draws with a label at its tip that counts along. The first value of each series is labeled once the tip has moved on, and the last value stays labeled at the end of the line; with more than one series, the end label also shows the series name next to a mark in the series color. End labels that would overlap are moved apart. Axis labels on the horizontal axis are thinned when they do not all fit, always keeping the first and the last.

At the highlight beat the lines dim, the highlighted point gets a guide line and a dot, and `highlight.label` appears above the plot. With a single series the callout also shows the value.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `x` | list of strings | yes | — | Labels on the horizontal axis, in order (e.g. years). At least 2, each unique. |
| `series` | list | yes | — | 1–3 series. |
| `series[].name` | string | if more than one series | — | Shown in the legend. |
| `series[].values` | list of numbers or `null` | yes | — | Same length as `x`. `null` leaves a gap. At least one value must be a number. |
| `number` | number format | no | — | Formatting of axis and value labels. |
| `y_min` / `y_max` | number | no | auto | Axis range. Auto range starts at 0 when all values are positive. `y_min` must be less than `y_max`, and every value must lie inside the range. |
| `highlight.x` | string | if `highlight` is given | — | An `x` label to mark with a vertical line and dot. At least one series must have a value there. |
| `highlight.label` | string | no | — | Callout text at the highlighted point. |

Default `duration`: 6.

```yaml
- id: valuation
  type: line
  title: Northwind's valuation
  x: ["2016", "2017", "2018", "2019", "2020"]
  series:
    - values: [0.05, 0.2, 2.25, 2.25, null]
  number: { prefix: "$", suffix: "B", decimals: 2 }
  highlight: { x: "2018", label: "Series C closes" }
  source: "Source: example data"
```

## `bar` — compare categories

One bar per category, with its value at the end of the bar, so there is no value axis. The bars grow one after another; at the highlight beat the highlighted bar turns to the `highlight` color and the others to `muted`.

Bars are drawn as **columns** or as **rows**:

- Columns grow up from a baseline, with the labels under it. A label that does not fit under its column is split into two lines. With many bars each label has little room (about 10 characters per line with 8 bars at the default theme); a label that does not fit on two lines is an error.
- Rows grow to the right, each bar under its label, with the value after the bar. A label has the whole width, so rows suit long labels; a label wider than the chart is split into two lines.

`layout: auto` uses columns in a 16:9 frame and rows in a 9:16 frame, where columns would be too narrow.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `bars` | list | yes | — | 2–8 bars. |
| `bars[].label` | string | yes | — | Category label. Each label is unique. |
| `bars[].value` | number | yes | — | Bar length. Zero or more; negative values are not supported in version 1. |
| `number` | number format | no | — | Formatting of value labels. |
| `sort` | `none` \| `asc` \| `desc` | no | `none` | Order of bars: left to right as columns, top to bottom as rows. |
| `layout` | `auto` \| `columns` \| `rows` | no | `auto` | Columns or rows, see above. `auto` picks by the frame's aspect. |
| `highlight.label` | string | if `highlight` is given | — | Bar to draw in the `highlight` color. Others use `muted`. Must match a bar label. |

Default `duration`: 5.

```yaml
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

## `timeline` — sequence of events

Events placed in order along a line: horizontal in a 16:9 frame, vertical in a 9:16 frame.

The line draws from its start to its end, and each event appears as the line reaches it. Events are evenly spaced. On a horizontal line, labels sit below the line when each fits its own space in at most two lines; otherwise they alternate below and above the line, with more room and up to three lines each. On a vertical line, events run from top to bottom and each label sits to the right of its event, with the whole width for up to three lines. A date always stays on one line. A date or label that still does not fit is an error asking you to shorten it.

At the highlight beat the emphasized event's dot grows and turns to the `highlight` color, its date turns to the `highlight` color, and the other events' marks dim.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `events` | list | yes | — | 2–7 events, in chronological order. |
| `events[].date` | string | yes | — | Displayed as written, e.g. `"Mar 2016"`. |
| `events[].label` | string | yes | — | Short description, max ~40 characters for readability. |
| `events[].emphasis` | boolean | no | `false` | Draws this event in the `highlight` color, larger. At most one event per timeline. |

Default `duration`: 7.

```yaml
- id: final-years
  type: timeline
  title: Northwind's last three years
  events:
    - { date: "2018", label: "Raises $865M" }
    - { date: "2020", label: "Revenue reaches $1.75B" }
    - { date: "Jun 2021", label: "Files for bankruptcy", emphasis: true }
```

---

## Validation

```bash
vizreel validate spec.yaml
```

Reports every error at once, with its location, for example:

```
spec.yaml: 2 errors
  charts[1].series[0].values: expected 5 values (same as x), got 4
  charts[2].type: unknown type "pie". Valid types: bar, line, stat, timeline
```

The exit code is `0` when the spec is valid and `1` when it is not.

## JSON Schema

```bash
vizreel schema -o vizreel.schema.json
```

Without `-o`, the schema is printed. Prefer `-o` over `>` on Windows PowerShell 5.1, which saves redirected output as UTF-16 and some tools cannot read that.

Editors (VS Code with the YAML extension) and AI assistants can use this schema to write valid specs. In VS Code, point a spec at the schema with a comment on its first line:

```yaml
# yaml-language-server: $schema=./vizreel.schema.json
```

## Versioning

- Adding optional fields does not change `version`.
- Renaming or removing a field, or changing a default in a way that changes output, requires a new `version`. The old version keeps working until the next major release.
