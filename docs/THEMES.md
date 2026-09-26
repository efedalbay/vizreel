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

`examples/themes/example-brand.yaml` is a complete custom theme to start from, and `examples/brand.yaml` uses it.

## Checking a theme

```bash
vizreel theme check themes/my-brand.yaml
```

The check fails, with exit code 1, if any of these is not met:

| Check | Minimum |
|---|---|
| `text` and `muted` against `surface` and `background` | contrast 4.5:1 (WCAG 1.4.3) |
| `accent`, `positive`, `negative`, `highlight` and every `series` color against `surface` and `background` | contrast 3:1 (WCAG 1.4.11) |
| Every pair of `series` colors, `highlight` and each `series` color, `highlight` and `muted` | CIEDE2000 difference of 10, with normal vision and with simulated protanopia, deuteranopia and tritanopia |

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
| `accent` | Data without a highlight: bars, timeline dots. |
| `positive` | A `stat` with `trend: up`. |
| `negative` | A `stat` with `trend: down`. |
| `highlight` | The one element that carries the message. |
| `series` | Line chart series, in this order. At least three. |
| `dim_opacity` | How much of their color other elements keep during the highlight beat, from 0 (exclusive) to 1. |

### `fonts`

`heading` (titles and dates), `body` (labels, subtitles, the source line) and `numbers` (values), each with:

| Field | Values |
|---|---|
| `family` | A font family name. The bundled family is `Inter`; other families must be installed. |
| `weight` | `regular` (default), `semibold` or `bold`. |

A theme uses at most two font families. Numbers are drawn with tabular figures, so the family should have them.

### `sizes`

Pixels at 1080p; they scale with the output resolution. Text sizes are font sizes.

| Field | Used for | Minimum |
|---|---|---|
| `title` | Chart title | 56 |
| `subtitle` | Line under the title | 32 |
| `big_number` | The number of a `stat` | 160 |
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

Seconds, except `easing`.

| Field | Used for | Minimum |
|---|---|---|
| `easing` | Curve of every movement: `ease_out_sine`, `ease_out_cubic`, `ease_out_quart` or `ease_out_expo` | — |
| `title_fade` | Fade-in of the title | more than 0 |
| `structure` | Drawing of axes and baselines | more than 0 |
| `stagger` | Delay between bars appearing one after another | 0 |
| `highlight` | The highlight beat | more than 0 |
| `hold` | Final hold, where nothing moves | 1.5 |

### `background_panel`

`true` to draw a panel in the `surface` color behind charts in transparent output, because the footage underneath is unknown.
