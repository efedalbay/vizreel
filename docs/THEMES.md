# Themes

A theme sets every color, font, size and timing a chart uses. Charts never contain styling of their own, so switching the theme restyles every chart consistently.

vizreel ships two built-in themes:

```bash
vizreel themes list
```

| Name | Description |
|---|---|
| `default` | Dark panel, light text and an amber highlight. |
| `light` | Light panel, dark text and an orange highlight. |

## Using a theme

Set `meta.theme` in a spec to a built-in name or to the path of a theme file. A relative path is looked up in the folder of the spec file.

```yaml
meta:
  theme: themes/example-brand.yaml
```

`examples/themes/example-brand.yaml` is a complete custom theme to start from, and `examples/brand.yaml` uses it:

```yaml
description: Northwind brand colors on a navy panel.

colors:
  background: "#081A2B"   # frame of opaque (mp4) output
  surface: "#0B2239"      # panel behind the chart
  text: "#F2F6FA"
  muted: "#A9B8C8"
  grid: "#24425F"
  accent: "#4FC3F7"
  positive: "#4CC38A"
  negative: "#FF6B6B"
  highlight: "#FFC857"
  series: ["#4FC3F7", "#F78FB3", "#9575CD"]
  dim_opacity: 0.5
  brand:                  # named colors a race can give to its series
    contoso-coral: "#FF7A7A"
    fabrikam-violet: "#7E57C2"
    tailspin-teal: "#26A69A"

fonts:
  heading: { family: Inter, weight: bold }
  body: { family: Inter, weight: regular }
  numbers: { family: Inter, weight: bold }

sizes:                    # pixels at 1080p
  title: 66
  subtitle: 40
  big_number: 200
  affix_scale: 0.6    # units and currency signs of big numbers at 60% of the digits
  label: 40
  value: 38
  caption: 28
  panel_radius: 16
  panel_padding: 72
  line: 7
  grid_line: 2
  dot: 18

motion:                   # seconds
  easing: ease_out_quart
  title_fade: 0.4
  structure: 0.5
  stagger: 0.1
  highlight: 0.7
  hold: 2

background_panel: true

logo:                     # drawn in the lower right corner of every chart
  file: northwind-logo.svg
  height: 48
```

A theme is loaded, and checked against the minimum sizes, when a spec that uses it is validated or rendered; an error names the theme file and the field.

## Checking a theme

```bash
vizreel theme check themes/my-brand.yaml
```

The check fails, with exit code 1, if any of these is not met:

| Check | Minimum |
|---|---|
| `text` and `muted` against `surface` and `background` | contrast 4.5:1 (WCAG 1.4.3) |
| `accent`, `positive`, `negative`, `highlight`, every `series` color and every `brand` color against `surface` and `background` | contrast 3:1 (WCAG 1.4.11) |
| Every pair of `series` colors, `highlight` and each `series` color, `highlight` and `muted`; every pair of `brand` colors, and each `brand` color with `accent` and `highlight` | CIEDE2000 difference of 10, with normal vision and with simulated protanopia, deuteranopia and tritanopia |

The second group of pairs are the colors that appear side by side in a chart. Color vision deficiency is simulated with the matrices of Machado, Oliveira and Fernandes (2009) at full severity. Add `--verbose` to see every measured value. Built-in themes pass every check.

## Fields

A theme file has these sections. Every field is required unless marked optional. Unknown fields are errors.

### `description` (optional)

One line shown by `vizreel themes list`.

### `colors`

Colors are `#RRGGBB`.

| Field | Used for |
|---|---|
| `background` | Frame background of opaque (`mp4`) output. |
| `surface` | Panel behind charts in transparent output. |
| `text` | Titles, values and labels. |
| `muted` | Secondary text and de-emphasized data. |
| `grid` | Axes, grid lines and baselines. |
| `accent` | Data without an emphasis of its own: bars, race bars and points, timeline dots, the start and total of a `waterfall`; also the kicker of a `title-card`. |
| `positive` | Up: a `stat` with `trend: up`, a rising `compare`, an increase in a `waterfall`. |
| `negative` | Down: a `stat` with `trend: down`, a falling `compare`, a decrease in a `waterfall`. |
| `highlight` | The one element that carries the message: a highlighted bar or point, the followed series of a race, the fill of a `progress`. |
| `series` | The series of `line`, `area`, `stacked`, `grouped` and `line-race` charts, in this order. At least three; a chart never reuses one for a second series. |
| `dim_opacity` | How much of their color other elements keep during the highlight beat, from 0 (exclusive) to 1. |
| `mark` | Optional. The pen of the highlight ring (`highlight_mark: ring`); the `highlight` color if left out, so a theme can keep its highlighted bar green and ring it in red. |
| `brand` | Optional. Named brand colors, such as `{ contoso-coral: "#FF7A7A" }`, which a `bar-race` or `scatter-race` gives to its series by name (`colors` in the spec), so a company can race in its own color. Names are lowercase letters, digits and hyphens. |

### `fonts`

`heading` (titles, title-card headlines and dates), `body` (labels, subtitles, the source line) and `numbers` (values), each with:

| Field | Values |
|---|---|
| `family` | A font family name. The bundled family is `Inter`; another family must be installed, or come from `file`. Optional with `file`, which names it. |
| `weight` | `regular` (default), `semibold` or `bold`. With `file`, give the weight of the file. |
| `file` | Optional. A TTF or OTF font file, relative to the theme file, so the theme looks the same on a computer that does not have the font installed. Its family is read from the file; a `family` that names another is an error, and so is a file that is missing, of another kind or not a font. |

Each role may use its own family, from a file or installed:

```yaml
fonts:
  heading: { file: fonts/LibreCaslonDisplay-Regular.ttf }
  body: { file: fonts/LibreCaslonText-Regular.ttf }
  numbers: { file: fonts/IBMPlexMono-Regular.ttf }
```

Keep the font files next to the theme and share the folder: the theme renders the same from any spec, on any computer. Check the license of a font before sharing its file; fonts under the SIL Open Font License, such as those of Google Fonts, may be shared.

Numbers are drawn with tabular figures, so that a counting number does not shift sideways. `vizreel render` warns when the number font's digits do not share one width, as in fonts with old-style figures or with kerning between digits.

### `sizes`

Pixels at 1080p; they scale with the output resolution. Text sizes are font sizes.

| Field | Used for | Minimum |
|---|---|---|
| `title` | Chart title | 56 |
| `subtitle` | Line under the title | 32 |
| `headline` | Optional, 96 by default. The headline of a `title-card` | 56 |
| `big_number` | The number of a `stat` and the percent of a `progress` bar; at 2/3 of it the `compare` values and the percent in a `share` or `progress` ring, and at 1/2 the period of a `bar-race` or `scatter-race` | 160 |
| `affix_scale` | Optional, 0.6 by default. Size of what surrounds the digits of a big number (the `stat` number, the `compare` values, the `share` percent), relative to the digits: 0.6 sets `milyar` in `1,85 milyar` and `$` in `$740M` at 60% of the digits, on their baseline; 1 sets them at the size of the digits. Not a pixel size. | 0.5, at most 1 |
| `label` | Axis labels, category labels, event labels, the `stat` label | 32 |
| `value` | Value labels on charts | 32 |
| `caption` | Source line | 24 |
| `panel_radius` | Corner radius of the background panel | 0 |
| `panel_padding` | Space between the panel edge and its content | 0 |
| `line` | Stroke width of data lines and the timeline axis | more than 0 |
| `grid_line` | Stroke width of grid lines, baselines and stems | more than 0 |
| `dot` | Diameter of data point markers | more than 0 |

The minimum text sizes keep charts readable on a phone (see `docs/DESIGN.md` §2).

### `motion`

Seconds, except `easing`, `entrance` and `exit`. A spec can override `easing`, `entrance` and `exit` for all its charts or for one; see [Motion](SPEC.md#motion).

| Field | Used for | Minimum |
|---|---|---|
| `easing` | Curve of every movement: `ease_out_sine`, `ease_out_cubic`, `ease_out_quart` or `ease_out_expo` | — |
| `title_fade` | Fade-in of the title | more than 0 |
| `structure` | Drawing of axes and baselines | more than 0 |
| `stagger` | Delay between bars appearing one after another | 0 |
| `highlight` | The highlight beat | more than 0 |
| `hold` | Final hold, where nothing moves | 1.5 |
| `entrance` | How the panel, titles, labels and legends appear: `fade`, `rise` (also rising a little) or `zoom` (also growing a little). Optional, `fade` by default | — |
| `exit` | How a clip ends: `none` (on the complete chart), `fade`, `sink` (also sinking a little) or `zoom` (also shrinking a little). Optional, `none` by default | — |
| `exit_time` | Length of the exit, taken from the end of the clip after the full hold. Optional, 0.5 by default | more than 0 |

### `background_panel`

`true` to draw a panel in the `surface` color behind charts in transparent output, because the footage underneath is unknown.

### `highlight_mark` (optional)

`none` (default) or `ring`. With `ring`, the highlight beat also draws a ring around the highlighted value, as if with a pen: a slightly leaning ellipse whose two ends pass each other, drawn from its start to its end in the `mark` color. It never crosses the value's text, and its size follows the text, so it works in every frame shape. Chart types that draw it:

- `bar`: around the value of the highlighted bar, as columns or rows. Told as a sequence, the ring moves from value to value with the emphasis.
- `stat`: around the number, drawn after it has counted, in a beat of the theme's `highlight` length. The card grows to hold the ring. A `duration` too short for that beat keeps its length; the clip has no ring, and `vizreel render` warns how long it would need.

Other chart types keep their usual highlight.

### `texture` (optional)

Ruled lines or a picture on the background, such as ledger paper or a manila folder. In transparent output it fills the background panel, inside its round corners, and appears and leaves with it; with `background_panel: false` there is none. In opaque output (`mp4`) it covers the whole frame and never moves. It is drawn on the `surface` color in the panel and on the `background` color over the frame, and always behind the chart. Give one of:

`ruled`, lines across the background:

| Field | Used for | Minimum |
|---|---|---|
| `spacing` | Distance between two lines, in pixels at 1080p | 16 |
| `color` | Color of the lines. Keep them faint, close to the paper's color, so text stays easy to read over them | — |
| `width` | Width of the lines, in pixels at 1080p. Optional, 2 by default | more than 0 |
| `margin` | Optional. Color of a double line down the left side, halfway between the edge and the content | — |

`image`, a picture behind the chart:

| Field | Used for | Minimum |
|---|---|---|
| `file` | A PNG or JPEG file, relative to the theme file. A missing file, or one of another kind, is an error when the theme loads | — |
| `fit` | `cover` (default) scales the picture to cover the background, cropping what does not fit; `tile` repeats it at its own size, its pixels taken as pixels at 1080p | — |

```yaml
texture:
  ruled: { spacing: 54, color: "#BCD0C2", width: 2, margin: "#B8322A" }
```

Sizes are pixels at 1080p and scale with the resolution, so lines are as far apart in a 4K clip, a vertical one or a square one as in 1080p. `vizreel theme check` checks the text and data colors against a picture's average color too, besides `surface` and `background`.

### `logo` (optional)

A logo drawn in the lower right corner of every chart, at the right end of the source line's band, which grows to fit it; a `stat` puts it in the lower right corner of its card. It appears with the chart's first animation and leaves with the clip's exit.

| Field | Used for | Minimum |
|---|---|---|
| `file` | A PNG, JPEG or SVG file, relative to the theme file. A missing file, or one of another kind, is an error when the theme loads. | — |
| `height` | Its height in pixels at 1080p. Optional, 48 by default. | 16 |
