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
| `aspect` | `16:9` \| `9:16` \| `1:1` | `16:9` | Frame shape. `16:9` is landscape; `9:16` is vertical, for Shorts, Reels and TikTok, and keeps clear of the platforms' buttons and captions; `1:1` is square, for feeds. Vertical clips are named `ID.vertical.mov` and square ones `ID.square.mov`. Quote the value: `aspect: "9:16"`. |
| `fps` | `23.976` \| `24` \| `25` \| `29.97` \| `30` \| `50` \| `59.94` \| `60` | `60` | Frames per second. Use your editor timeline's rate: a clip at another rate is blended or loses frames. 25 and 50 are the PAL rates used in Europe, 29.97 and 59.94 the NTSC rates, 23.976 and 24 film. The NTSC rates are stored exactly (29.97 is 30000/1001), and a clip always has `round(duration × fps)` frames. |
| `format` | `mov` \| `webm` \| `mp4` \| `prores` \| `png` | `mov` | `mov` (QuickTime Animation), `webm`, `prores` and `png` have a transparent background. `prores` is ProRes 4444, the professional editors' standard, written as `ID.prores.mov`. `png` writes a folder named like the clip, holding one PNG per frame (`ID/ID_00001.png`, ...), which every editor imports as an image sequence. `mp4` is opaque and uses the theme background color. |
| `motion` | object | — | Motion settings for every chart: how things appear and leave, and the easing. See [Motion](#motion). |
| `locale` | `en-US` \| `tr-TR` \| `es-ES` \| `pt-BR` \| `fr-FR` | `en-US` | How numbers are written: separators, the percent sign and compact unit names. See [Locales](#locales). Text you write, such as labels and dates, is shown as written. |

CLI flags override `meta` values.

## Fields shared by every chart

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `id` | string `[a-z0-9-]+` | yes | — | Unique in the spec. Used as the output file name, so it cannot be a name Windows reserves (`con`, `prn`, `aux`, `nul`, `com1`–`com9`, `lpt1`–`lpt9`). |
| `type` | string | yes | — | Chart type: `stat`, `progress`, `line`, `area`, `bar`, `timeline`, `compare`, `waterfall`, `stacked`, `grouped`, `share`, `table`, or a type from an installed [plugin](PLUGINS.md); `vizreel types` lists them all. A plugin documents its own fields. |
| `title` | string | no | — | Shown at the top of the chart. Wraps onto a second line if it does not fit the width; a title that does not fit on two lines is an error. |
| `subtitle` | string | no | — | Smaller line under the title. Wraps like the title. |
| `source` | string | no | — | Short source label shown at the bottom, e.g. `"Source: Axios, 2023"`. Keep it short; it is on screen. |
| `duration` | number (seconds) | no | depends on type | Total clip length, including the final hold. Minimum 2. |
| `highlight` | object | no | — | Type-specific emphasis. See each type. `stat` has no `highlight`. |
| `motion` | object | no | — | Motion settings for this chart, over those of `meta.motion`. See [Motion](#motion). |
| `data` | string or object | no | — | A CSV file that gives the chart's data, such as its bars, in place of writing them in the spec. See [Data from files](#data-from-files). |

### Number format (`number`)

Used by any field that displays values.

| Field | Type | Default | Example output |
|---|---|---|---|
| `prefix` | string | `""` | `$` |
| `suffix` | string | `""` | `%`, ` users` |
| `decimals` | integer, 0–6 | auto | `1` → `4.2` |
| `compact` | `true` \| `false` \| `long` \| `short` | `false` | `true` → `740M`, `2.25B`; `long` → `740 million`; `short` → `740M` |

`compact: true` names the units the way the spec's locale usually does: abbreviated in `en-US` (`740M`), in full elsewhere (`740 milyon`). `long` and `short` choose: `short` is narrower, which helps a big number in a vertical clip; `long` needs no knowledge of abbreviations. See [Locales](#locales) for every locale's names.

Values in the spec are always plain numbers. `740000000` with `prefix: "$"` and `compact: true` renders as `$740M`. Never write `"740M"` as a value.

Formatting rules, shown for `en-US` (see [Locales](#locales) for the others):

- **Thousands separators:** `1200000` → `1,200,000`.
- **Automatic decimals** (no `decimals` set): whole numbers get none; other numbers get at most 2, without trailing zeros (`4.2`, `0.05`, `1.23`). With `compact: true`, abbreviated numbers keep 3 significant digits (`740M`, `2.25B`, `1.2M`, `12.3M`).
- **Fixed decimals** (`decimals` set): always that many, trailing zeros kept (`decimals: 2` → `2.20`). With `compact: true`, `decimals` applies to the abbreviated number (`decimals: 1` → `740.0M`).
- **Compact units:** `K` from 1,000, `M` from 1,000,000, `B` from 1,000,000,000, `T` from 1,000,000,000,000. Numbers below 1,000 are not abbreviated. When rounding reaches 1,000 of a unit, the next unit is used: `999950` → `1M`, not `1000K`.
- **Counting:** a value that counts up or grows is shown in the unit of its final value, so its unit and width do not jump: `$0.37B` on the way to `$1.85B`, not `$370M`. A final value that would count through fewer than 10 values in its own unit, such as `$2B`, counts through the smaller units instead.
- **Rounding:** halves round away from zero: `2.675` → `2.68`, `2.5` → `3`.
- **Negative numbers:** the minus sign (−, U+2212) comes before the prefix: `−$1.2M`. A value that rounds to zero never shows a sign.
- **Same decimals within a chart:** values shown together in one chart, such as axis or bar labels, share the number of decimals of the most precise value: `$0.05B`, `$0.20B`, `$2.25B`. With `compact: true`, only values with the same unit share decimals: `$1.25B`, `$412.0M`, `$7.8M`.

### Locales

`meta.locale` sets how every number in the spec is written. The rules above hold in every locale; only the way the result is written changes.

| | `en-US` | `tr-TR` | `es-ES` | `pt-BR` | `fr-FR` |
|---|---|---|---|---|---|
| Separators | `1,846.5` | `1.846,5` | `1846,5` · `18.460` | `1.846,5` | `1 846,5` |
| Percent | `47%` | `%47` | `47 %` | `47%` | `47 %` |
| Percent change | `−72%` · `+4.5%` | `−%72` · `+%4,5` | `−72 %` · `+4,5 %` | `−72%` · `+4,5%` | `−72 %` · `+4,5 %` |
| `compact: long` | `12.3 thousand` · `740 million` · `2.25 billion` · `3.2 trillion` | `12,3 bin` · `740 milyon` · `2,25 milyar` · `3,2 trilyon` | `12,3 mil` · `740 millones` · `2,25 mil millones` · `3,2 billones` | `12,3 mil` · `740 milhões` · `2,25 bilhões` · `3,2 trilhões` | `12,3 mille` · `740 millions` · `2,25 milliards` · `3,2 billions` |
| `compact: short` | `12.3K` · `740M` · `2.25B` · `3.2T` | `12,3 B` · `740 Mn` · `2,25 Mr` · `3,2 Tn` | `12,3 mil` · `740 M` · `2,25 mil M` · `3,2 B` | `12,3 mil` · `740 mi` · `2,25 bi` · `3,2 tri` | `12,3 k` · `740 M` · `2,25 Md` · `3,2 Bn` |
| `compact: true` | short | long | long | long | long |

The conventions follow the [Unicode CLDR](https://cldr.unicode.org/):

- Spanish groups digits only in numbers of five digits or more: `1846`, but `18.460`.
- French separates groups with a narrow no-break space, and puts one before `%`; Spanish puts a no-break space before `%`.
- A unit name is joined to its number by a no-break space so the two never part; only the English abbreviations follow the number directly (`740M`). Where a long name has a plural, it agrees with the number shown: `1 millón` and `1,2 millones` in Spanish; `1,5 milhão` and `2 milhões` in Portuguese; `1,5 million` and `2 millions` in French.
- In Turkish, the short `B` means *bin* (thousand), not billion. Viewers who know English may misread it, which is why `compact: true` writes the names in full.
- The minus sign comes first in every locale: `−%72`, `−5 €`.

`prefix` and `suffix` are shown exactly as written, in every locale, so write them for yours. In Turkish the percent sign goes before the number: write `prefix: "%"` for `%12,5`. A currency after the number takes its space in the suffix: `suffix: " TL"` gives `740 milyon TL`.

```yaml
version: 1
meta:
  locale: tr-TR

charts:
  - id: revenue
    type: stat
    value: 740000000
    label: Northwind'in yıllık geliri
    number: { suffix: " TL", compact: true }
```

This renders `740 milyon TL`.

---

## `stat` — big number card

A single number that counts up (or down) to its value. Use it for the one figure the viewer must remember. A number too wide for the frame, such as a long compact number in a vertical clip, shrinks until it fits, down to half the theme's size; one wider still is an error asking you to use `compact: short`.

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

## `progress` — toward a goal

How far a value has come toward a goal, e.g. money raised for a fundraiser. A bar fills from the left under a big percent, or, with `style: ring`, a ring fills clockwise from the top with the percent in its middle. Under either, the value and the goal (`$68K / $100K`) count up, then the label. The fill is in the theme's `highlight` color on a track in its `grid` color. A value past the goal fills the bar or ring and shows more than 100%. The percent shrinks to fit, like the number of a stat.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `value` | number | yes | — | How far it has come. Zero or more. |
| `goal` | number | yes | — | Where it is going. Above zero. |
| `style` | `bar` \| `ring` | no | `bar` | A bar that fills from the left, or a ring that fills clockwise with the percent inside. |
| `label` | string | no | — | Line under the chart. |
| `number` | number format | no | — | Formatting of the value and the goal. |

Default `duration`: 4.

```yaml
- id: fundraiser
  type: progress
  title: Northwind's fundraiser
  value: 68000
  goal: 100000
  style: ring
  label: raised for the new library
  number: { prefix: "$", compact: true }
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
| `sequence` | list | no | — | Tells the chart as a sequence of clips, one per item, each moving the emphasis on. See [Sequences](#sequences). |
| `step_duration` | number | no | `3` | Length in seconds of each clip of a sequence after the first. |

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
| `sequence` | list | no | — | Tells the chart as a sequence of clips, one per item, each moving the emphasis on. See [Sequences](#sequences). |
| `step_duration` | number | no | `3` | Length in seconds of each clip of a sequence after the first. |

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
| `sequence` | list | no | — | Tells the chart as a sequence of clips, one per item, each moving the emphasis on. See [Sequences](#sequences). |
| `step_duration` | number | no | `3` | Length in seconds of each clip of a sequence after the first. |

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

## `compare` — before and after

One measure at two moments: the earlier value, an arrow, the later value, and the change between them.

The earlier value counts up and the arrow draws; then the later value counts from the earlier value to its own, so the viewer sees the change happen. At the highlight beat the earlier value dims and the change counts in. The values sit side by side at 16:9, and one above the other at 9:16 or when they are too wide to sit side by side. Values too wide even for that shrink until they fit, down to half their size; values wider still are an error asking you to use `compact: short`.

The change is always signed. In percent it is a whole number from 10% up (`−72%`) and keeps one decimal below (`+4.5%`); as a difference it uses the chart's `number` format (`+$150M`). With `trend: auto` a rise is drawn in the theme's `positive` color and a fall in its `negative` color; use `trend: none` when a rise is bad news, such as costs.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `before.label` | string | yes | — | When or what the earlier value is, e.g. `"2019"` or `"Before the redesign"`. |
| `before.value` | number | yes | — | The earlier value. Above zero when `change` is `percent`. |
| `after.label` | string | yes | — | When or what the later value is. |
| `after.value` | number | yes | — | The later value. |
| `change` | `percent` \| `absolute` \| `none` | no | `percent` | The change in percent of the earlier value, as the difference, or not shown. |
| `trend` | `auto` \| `none` | no | `auto` | `auto` colors the change by its direction; `none` keeps it in the text color. |
| `number` | number format | no | — | Formatting of both values, and of the change when it is `absolute`. |

Default `duration`: 5.

```yaml
- id: headcount
  type: compare
  title: Northwind's employees
  before: { label: "2019", value: 1200 }
  after: { label: "2022", value: 340 }
```

## `waterfall` — from a start to a total

How a starting value becomes a total through increases and decreases, e.g. revenue becoming profit.

The start grows from zero. Each step then grows from where the previous one ended: up in the theme's `positive` color for an increase, down in its `negative` color for a decrease, with a thin line joining each bar to the next. The total, the start plus every step, grows last. At the highlight beat the highlighted bar turns to the `highlight` color and the others dim, keeping their colors. The start and the total show their value; each step shows its change with a sign (`−$5.0M`, `+$500K`).

Bars are drawn as columns or rows, as for bar charts (`layout`); rows have no joining lines. The running total must stay at zero or above in version 1.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `start.label` | string | yes | — | What the starting value is, e.g. `Revenue`. |
| `start.value` | number | yes | — | The starting value. Zero or more. |
| `steps` | list | yes | — | 1–6 changes, in order. |
| `steps[].label` | string | yes | — | What the change is, e.g. `Salaries`. |
| `steps[].value` | number | yes | — | The change: positive adds, negative takes away. |
| `end.label` | string | no | `Total` | What the total is, e.g. `Profit`. Its value is computed. |
| `number` | number format | no | — | Formatting of the values. |
| `layout` | `auto` \| `columns` \| `rows` | no | `auto` | As for bar charts: `auto` uses columns at 16:9 and rows at 9:16. |
| `highlight.label` | string | no | the total | The bar to draw in the `highlight` color: the start, a step or the end. |
| `sequence` | list | no | — | Tells the chart as a sequence of clips, one per item, each moving the emphasis on. See [Sequences](#sequences). |
| `step_duration` | number | no | `3` | Length in seconds of each clip of a sequence after the first. |

Labels are unique across the start, the steps and the end. Default `duration`: 6.

```yaml
- id: profit
  type: waterfall
  title: How Northwind's revenue became profit
  start: { label: Revenue, value: 12000000 }
  steps:
    - { label: Salaries, value: -5000000 }
    - { label: Marketing, value: -2000000 }
    - { label: Other income, value: 500000 }
  end: { label: Profit }
  number: { prefix: "$", compact: true }
```

## `stacked` — bars made of parts

One bar per category, each made of two or three parts stacked on each other, e.g. revenue per year split by product.

A legend under the title names the parts by color, in the theme's `series` colors, in order. Each bar shows its total; the parts do not show their own values. The parts grow one series at a time: the first part in every bar, then the next part on top of it, while each total counts up. At the highlight beat the highlighted series keeps its color and the others dim. Bars are drawn as columns or rows, as for bar charts (`layout`).

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `categories` | list of strings | yes | — | 2–8 categories, one bar each, in order. Unique. |
| `series` | list | yes | — | 2–3 parts of each bar, from the bottom (or the left) up. |
| `series[].name` | string | yes | — | Shown in the legend. Unique. |
| `series[].values` | list of numbers | yes | — | One value per category, zero or more. |
| `number` | number format | no | — | Formatting of the totals. |
| `layout` | `auto` \| `columns` \| `rows` | no | `auto` | As for bar charts: `auto` uses columns at 16:9 and rows at 9:16. |
| `highlight.series` | string | no | — | The series that keeps its color while the others dim. |
| `sequence` | list | no | — | Tells the chart as a sequence of clips, one per item, each moving the emphasis on. See [Sequences](#sequences). |
| `step_duration` | number | no | `3` | Length in seconds of each clip of a sequence after the first. |

Default `duration`: 6.

```yaml
- id: revenue-mix
  type: stacked
  title: Northwind revenue by product
  categories: ["2021", "2022", "2023"]
  series:
    - { name: Cloud, values: [1.2, 2.4, 3.9] }
    - { name: Devices, values: [3.1, 2.9, 3.2] }
  number: { prefix: "$", suffix: "B" }
  highlight: { series: Cloud }
```

## `grouped` — bars side by side

Bars in groups of two or three, one group per category, e.g. revenue in each region for two years.

A legend under the title names the series by color, in the theme's `series` colors, in order, and every bar shows its value. The groups grow one after another while their values count up. At the highlight beat the highlighted series keeps its color and the others dim. Bars are drawn as columns or rows (`layout`); with `auto`, a 9:16 frame uses rows, and other frames use columns unless the values are too wide to sit side by side, when they use rows.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `categories` | list of strings | yes | — | 2–6 categories, one group each, in order. Unique. |
| `series` | list | yes | — | 2–3 series, one bar in each group, in order within the group (from the left, or from the top in rows). |
| `series[].name` | string | yes | — | Shown in the legend. Unique. |
| `series[].values` | list of numbers | yes | — | One value per category, zero or more. |
| `number` | number format | no | — | Formatting of the values. |
| `layout` | `auto` \| `columns` \| `rows` | no | `auto` | `auto` uses rows at 9:16, and columns elsewhere unless the values do not fit side by side. |
| `highlight.series` | string | no | — | The series that keeps its color while the others dim. |
| `sequence` | list | no | — | Tells the chart as a sequence of clips, one per item, each moving the emphasis on. See [Sequences](#sequences). |
| `step_duration` | number | no | `3` | Length in seconds of each clip of a sequence after the first. |

Default `duration`: 6.

```yaml
- id: region-growth
  type: grouped
  title: Northwind revenue by region
  subtitle: In millions of dollars
  categories: [North, South, East, West]
  series:
    - { name: "2022", values: [310, 240, 150, 280] }
    - { name: "2023", values: [412, 298, 188, 356] }
  number: { prefix: "$", suffix: "M" }
  highlight: { series: "2023" }
```

## `area` — amounts over time

One to three series drawn from left to right as filled areas, e.g. users per platform over five years. With `stack: true` the areas sit on each other, so the top edge shows their total; otherwise each area fills from zero and they overlap, translucent.

Grid lines and axis labels appear first. Then the areas fill from left to right behind a line along their top, with a label at the tip that counts along: the series name (when there is more than one series) and its own value, not the running total. A stacked area's label points at the middle of its band. At the highlight beat the highlighted series keeps its color and the others dim. The vertical axis always starts at zero, since an area's height is its amount.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `x` | list of strings | yes | — | Labels on the horizontal axis, in order. At least 2. Unique. |
| `series` | list | yes | — | 1–3 series, drawn in order; stacked, the first is at the bottom. |
| `series[].name` | string | if more than one series | — | Shown next to the area's end. Unique. |
| `series[].values` | list of numbers | yes | — | One value per x label, zero or more. No gaps: an area needs every value. |
| `stack` | boolean | no | `false` | Stack the areas on each other instead of overlapping them from zero. |
| `number` | number format | no | — | Formatting of axis and value labels. |
| `highlight.series` | string | no | — | The series that keeps its color while the others dim. |
| `sequence` | list | no | — | Tells the chart as a sequence of clips, one per item, each moving the emphasis on. See [Sequences](#sequences). |
| `step_duration` | number | no | `3` | Length in seconds of each clip of a sequence after the first. |

Default `duration`: 6.

```yaml
- id: users
  type: area
  title: Northwind users by platform
  subtitle: Monthly active users
  x: ["2020", "2021", "2022", "2023", "2024"]
  series:
    - { name: Web, values: [1.2, 1.9, 2.4, 2.8, 3.0] }
    - { name: Mobile, values: [0.4, 1.1, 2.2, 3.6, 4.9] }
  stack: true
  number: { suffix: "M" }
  highlight: { series: Mobile }
```

## `share` — parts of a whole

How a whole divides into two to six parts, e.g. shares of a market, as a ring.

The ring draws clockwise from the top, and a legend beside it (under it at 9:16) lists each part with its percent of the total, which counts up as its part draws. The parts are shades of the theme's `muted` color. At the highlight beat the highlighted part turns to the `highlight` color and its percent counts up in the middle of the ring, with its label under it when both fit.

Percents are whole numbers that always add up to 100: three equal parts show 34%, 33% and 33%, not 33% three times.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `parts` | list | yes | — | 2–6 parts, clockwise from the top. |
| `parts[].label` | string | yes | — | What the part is. Unique. |
| `parts[].value` | number | yes | — | The part's size in any unit, above zero; shown as a percent of the total. |
| `highlight.label` | string | no | the largest part | The part drawn in the `highlight` color, with its percent in the middle. On a tie, the first of the largest. |
| `sequence` | list | no | — | Tells the chart as a sequence of clips, one per item, each moving the emphasis on. See [Sequences](#sequences). |
| `step_duration` | number | no | `3` | Length in seconds of each clip of a sequence after the first. |

Default `duration`: 6.

```yaml
- id: market
  type: share
  title: Northwind's share of the market
  parts:
    - { label: Northwind, value: 47 }
    - { label: Contoso, value: 28 }
    - { label: Others, value: 25 }
```

## `table` — rows and columns

A few rows and columns: each row's name, then numbers or text.

The column names and a thin line under them appear first; then the rows appear one after another from the top, their numbers counting up. Text is set flush left and numbers flush right, with tabular figures so that digits line up. The cells use the largest of the theme's text sizes (title, subtitle, value, label) at which the table fits, so a short table is easy to read on a phone; a table that does not fit even at the label size is an error. At the highlight beat a soft band in the `highlight` color appears behind the highlighted row and the other rows dim.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `columns` | list | yes | — | 2–4 columns. The first holds the row names. |
| `columns[].name` | string | yes | — | Shown above the column. |
| `columns[].number` | number format | no | — | Formatting of the column's numbers, with consistent decimals down the column. |
| `rows` | list of lists | yes | — | 2–8 rows, each with one cell per column. |
| `rows[][0]` | string | yes | — | The row's name. Unique. |
| `rows[][1:]` | number or string | yes | — | A column holds either numbers or text in every row; which one is decided by its first row. Quote years and codes that should stay text: `"2016"`. |
| `highlight.row` | string | no | — | Name of the row to emphasize. |
| `sequence` | list | no | — | Tells the chart as a sequence of clips, one per item, each moving the emphasis on. See [Sequences](#sequences). |
| `step_duration` | number | no | `3` | Length in seconds of each clip of a sequence after the first. |

Default `duration`: 6.

```yaml
- id: top-markets
  type: table
  title: Northwind's largest markets
  columns:
    - { name: Market }
    - { name: Revenue, number: { prefix: "$", compact: true } }
    - { name: Growth, number: { suffix: "%" } }
  rows:
    - [Germany, 412000000, 12]
    - [France, 298000000, -3]
    - [Japan, 187500000, 21]
  highlight: { row: Japan }
```

---

## Sequences

A chart that emphasizes one element can also be told as a **sequence**: the same chart in several clips, the emphasis moving on in each, for a narration that walks through the data ("first 2016... then 2018..."). Cut the clips back to back in an editor and they play as one continuous chart.

```yaml
- id: history
  type: timeline
  title: How Northwind grew
  events:
    - { date: "2016", label: "Founded" }
    - { date: "2018", label: "Opens offices in three countries" }
    - { date: "2020", label: "Reaches one million users" }
  sequence: ["2016", "2018", "2020"]
```

```
out/
├── history.1.mov    ← the chart draws, then emphasizes 2016 (length: duration)
├── history.2.mov    ← starts on the last frame of history.1, the emphasis moves to 2018
└── history.3.mov    ← starts on the last frame of history.2, the emphasis moves to 2020
```

The first clip is the chart as usual, emphasizing the first item. Each later clip starts on exactly the frame the one before ended on, with no title or drawing animation; the emphasis moves to its item, the one before returns to how the other elements look, and the frame holds. Its length is `step_duration` (default 3 seconds), at least the theme's highlight time plus its final hold. Clip numbers come before the other suffixes: `history.2.vertical.preview.mov`.

| Chart type | A `sequence` item names |
|---|---|
| `bar`, `waterfall` | A bar label. |
| `timeline` | An event date. A date used by two events cannot be named. |
| `stacked`, `grouped`, `area` | A series name. |
| `share` | A part label. |
| `table` | A row name. |
| `line` | An x label that has a value, or a point with a callout: `{ x: "2018", label: "Series C closes" }`. |

A sequence has 2–8 items; an item may come back later. A chart with a `sequence` has no `highlight` (and a timeline no event with `emphasis`), since the sequence says what to emphasize in each clip. `stat`, `progress` and `compare` charts have no elements to emphasize and no sequence.

---

## Motion

Every chart moves as the [design rules](DESIGN.md#3-motion) say: data grows, draws or counts, every movement eases out, and the clip ends on a hold. `motion` chooses, within those rules, how the rest appears, whether the clip leaves the screen at the end, and the easing curve:

```yaml
version: 1
meta:
  motion: { entrance: rise }       # every chart
charts:
  - id: offers
    type: bar
    bars:
      - { label: North, value: 412 }
      - { label: South, value: 298 }
    motion: { exit: fade }          # this chart
```

| Field | Type | Default | Description |
|---|---|---|---|
| `entrance` | `fade` \| `rise` \| `zoom` | the theme's, `fade` | How the panel, title, labels and legends appear: fading in, also rising a little into place, or also growing a little into place. Data appears as always. |
| `exit` | `none` \| `fade` \| `sink` \| `zoom` | the theme's, `none` | How the clip ends: on the complete chart, or leaving the screen by fading out, also sinking a little, or also shrinking a little. |
| `easing` | `ease_out_sine` \| `ease_out_cubic` \| `ease_out_quart` \| `ease_out_expo` | the theme's | The curve of every movement and of counting numbers. |

Each field of a chart's `motion` goes over `meta.motion`, which goes over the theme's `motion` (see [THEMES.md](THEMES.md)).

An exit takes the theme's `exit_time` (0.5 seconds in the built-in themes) from the end of the clip, after the full hold, so the clip keeps its `duration` and still holds still long enough; a `duration` too short for both says how long it must be. The clip then ends on an empty, transparent frame, and `--still` saves the complete chart from just before the exit. A chart told as a [sequence](#sequences) leaves only at the end of its last clip, so the clips still cut together.

---

## Data from files

A chart can read its data from a CSV file instead of the spec, so numbers exported from a spreadsheet or a script render without being copied by hand. `data` names the file, relative to the spec file:

```yaml
- id: regions
  type: bar
  title: Northwind revenue by region
  data: data/regions.csv
  number: { prefix: "$", compact: true }
  highlight: { label: East }
```

```csv
Region,Revenue
North,412000000
South,298000000
East,187500000
West,356000000
```

The file gives the chart's data fields, listed below; every other field, such as `title`, `number`, `highlight` or `sequence`, is written in the spec as usual. Writing a field the file gives as well is an error. The data is checked as if it were written in the spec: a bar chart still takes two to eight bars, zero or more each, and an error in a field the file gave names the file: `charts[0].bars[1].value: must be at least 0, got -2 (from data/regions.csv)`. `examples/data.yaml` has a chart of each kind.

### The file

- The first row names the columns.
- Cells are separated by commas, semicolons or tabs, whichever the first row uses most, so the semicolons Excel writes in many European languages work too. Put a cell that holds the separator in double quotes: `"Revenue, net"`.
- The file is UTF-8, with or without a byte order mark. In Excel, save it as *CSV UTF-8*.
- Empty rows and spaces around cells are ignored.
- Text is shown as written. Years and dates need no quotes: `2016` in a label column stays the text `2016`.
- A number is written plainly, `1234.5`, or the way `meta.locale` writes numbers: `1.234,5` in `tr-TR`, with or without its group separators. Where the two read the same text differently, the locale's way wins: in `tr-TR`, `1.234` is one thousand two hundred and thirty-four. Leave out units, currencies and percent signs (`$12M` is an error) and format the numbers with `number`.
- An error in the file names the file, the row, counted as lines of the file, and the column: `charts[0].data: data/regions.csv, row 4, column "Revenue" is not a number: "187,5M"`.

`vizreel render --watch` renders again when a data file is saved.

### Choosing columns

With more columns than the chart reads, name the ones to read, in order:

```yaml
- id: markets
  type: bar
  title: Northwind revenue by market
  data: { file: data/markets.csv, columns: [Market, Revenue] }
  number: { prefix: "$", compact: true }
```

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | string | yes | Path to the CSV file, relative to the spec file. |
| `columns` | list of strings | no | The columns to read, by the names in the first row, in this order. All of them if left out. |

### What each chart type reads

| Type | Columns | Rows | Gives |
|---|---|---|---|
| `bar` | A label and a value. | One bar each. | `bars` |
| `share` | A label and a value. | One part each. | `parts` |
| `timeline` | A date and a label. | One event each. Emphasize an event with a `sequence`. | `events` |
| `line` | The x labels, then one column per series, named by its first row. | One x label each; an empty cell leaves a gap. | `x`, `series` |
| `stacked` | The categories, then one column per series, named by its first row. | One bar each. | `categories`, `series` |
| `grouped` | The categories, then one column per series, named by its first row. | One group each. | `categories`, `series` |
| `area` | The x labels, then one column per series, named by its first row. | One x label each; every cell needs a value. | `x`, `series` |
| `waterfall` | A label and a value. | The first row is the start and the others are steps; a last row with a label and no value names the total. | `start`, `steps`, and `end` if the last row names it |
| `compare` | A label and a value. | Two: the earlier value, then the later one. | `before`, `after` |
| `table` | Two to four. A column holds numbers if its first row does; the first holds the row names. | One row each. | `rows`, and `columns` named by the first row, unless the spec writes `columns` to name them and set their number formats |

`stat` and `progress` charts read no data file. A chart type from a [plugin](PLUGINS.md) documents whether it reads one.

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
