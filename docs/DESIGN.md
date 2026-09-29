# Design rules

vizreel output is watched, not studied. A viewer sees each chart for a few seconds, often on a phone. These rules exist so every chart is readable at a glance and looks like it belongs to one visual system. They apply to every chart type and every theme.

## 1. Form: one message per chart

- Every chart answers one question. If the title needs "and", it is two charts.
- One key number → `stat`, not a chart. A one-bar bar chart is always wrong.
- Change over time → `line`; amounts over time, or how a total over time divides → `area`. Comparing a few categories → `bar`. Order of events → `timeline`. One measure before and after → `compare`. How a value adds up from its parts → `waterfall`. Categories split into a few parts → `stacked`. The same few measures compared in each category → `grouped`. One whole split into parts → `share`. A few exact figures to read side by side → `table`. How far a value has come toward a goal → `progress`.
- **Emphasize one thing.** The element that carries the message gets the `highlight` color; everything else uses `muted`. Do not give every bar its own color.
- **Never two y-axes.** Two measures on different scales become two charts.
- Maximum 3 series on a line chart, 8 bars, 7 timeline events. The spec validator enforces these limits.

## 2. Legibility on a phone

Sizes are defined relative to a 1080p frame and scale with resolution. They refer to the short side of the frame, so a size is the same on a 9:16 vertical frame (1080×1920) as on a 16:9 one.

| Element | Minimum font size at 1080p |
|---|---|
| Title | 56 px |
| Big number (`stat`) | 160 px, or down to 80 px when it does not fit (see below) |
| Value labels, axis labels | 32 px |
| Source line | 24 px |

- **Safe area:** keep all content inside the central 90% of the frame (5% margin on every side). Video platforms and editors overlay controls near the edges. In a 9:16 frame, Shorts, Reels and TikTok cover more: menus at the top, the caption, channel name and buttons at the bottom and lower right. There the margins are 6% on the sides, 10% at the top and 20% at the bottom.
- **Narrow frames change the form, not the size.** Text is never shrunk to fit a vertical frame. Charts rearrange instead: bars become rows, a timeline runs down the frame, and titles wrap onto a second line. Wrapped lines have their baselines 1.2 times the font size apart, so a descender never touches the line below.
- **A square frame takes what fits.** At 1:1 the frame is as narrow as a vertical one but not as tall. Each chart uses its landscape arrangement (columns, a horizontal timeline, the legend beside the ring) when it fits, and its vertical one when it does not. A ring takes whichever arrangement leaves it larger. The safe margin is 5% on every side.
- **A vertical card fits its content.** A 9:16 chart with little content, such as three bars or a short timeline, does not float in the middle of an empty panel: the title, the source line and the panel close in around the content, and the card is centered in the safe area, with the footage visible around it. A chart whose content fills the frame, such as a line chart or a share ring, keeps the full panel.
- **The one exception is a big number.** A number cannot wrap, and a compact number with a long unit name (`1,85 milyar`) can be wider than a vertical frame. The big number of a `stat` and the values of a `compare` then shrink until they fit, down to half their size. The size is chosen for the widest text the count shows, not only the final value, and stays the same while it counts; a number that jumps in size draws the eye away from its value. A number too wide even at half size is an error that suggests `compact: short`.
- **Contrast:** text against its background must reach at least 4.5:1; large text (title, big numbers) at least 3:1. With transparent output, the chart draws its own background panel when the theme sets `background_panel: true`, because the footage underneath is unknown.
- **Text wears text colors.** Labels and values use `text` or `muted` from the theme, never a series color. A colored mark next to the label carries identity.
- **Direct labels over legends** for 1–3 series. A legend appears only when two or more series exist and direct labels would collide.
- **Selective labels.** Label the first value, the last value and the highlighted value. Never a number on every point.
- **Recessive structure.** Grid lines and axes use the `grid` color at thin weight, or are omitted. Data is the brightest thing on screen.
- Numbers use the theme's `numbers` font with tabular figures, so counting animations do not jitter.

## 3. Motion

Motion guides the eye to the message. It is never decoration.

- **Easing.** Every movement eases out (fast start, soft stop). No linear motion except the counting of numbers, which eases out as well. No bouncing or overshoot.
- **Order of appearance:** title → structure (axes, baseline) → data → highlight → hold.
- **Timing defaults** (seconds, overridable in the theme `motion` section):

| Phase | Default |
|---|---|
| Title fade-in | 0.5 |
| Structure draw | 0.6 |
| Data reveal | 40–50% of the clip |
| Stagger between bars / events | 0.08 |
| Highlight | 0.6 |
| Final hold (nothing moves) | at least 1.5 |

- **Reading time.** Any text that appears must stay on screen for at least 1 second per 3 words before the clip ends.
- **Highlight moment.** The highlight is a distinct beat: the highlighted element changes color, and everything else dims slightly. This is where the narration's key sentence lands, so it must be clearly visible in the timing.
- Lines draw from left to right. Bars grow from the baseline. Numbers count; they do not fade in.
- The last frame must be a complete, clean chart. Editors often freeze it. The exception is a clip asked to leave the screen (`exit`), which ends empty after its full hold.
- **Entrances and exits** (`motion` in the spec or theme) only fade, rise, sink, grow or shrink a little, easing out like everything else. They apply to the panel, titles, labels and legends, never to the data, which grows, draws or counts.

## 4. Color

- Colors come only from the theme's named roles. A chart module never contains a color value.
- Series colors are used in fixed order from `colors.series`. They are never generated, cycled or reassigned by rank.
- `positive` and `negative` mean up and down. They are not used as series colors.
- Themes are validated for contrast and color-vision-deficiency separation (`vizreel theme check`, see roadmap). A theme that fails is not shipped as built-in.

## 5. Typography

- Maximum two font families per theme (headings and body; numbers may reuse either).
- Built-in themes use bundled open-license fonts, so output looks the same on every machine.
- Titles in sentence case. No all-caps paragraphs; all-caps is allowed only for very short labels (1–2 words).
- Numbers are formatted by `format/numbers.py` only: thousands separators, compact notation (`$740M`), consistent decimals within one chart.
- **Text sits on baselines.** Labels in a row share a baseline, and gaps between lines of text are measured from the font's ascent and descent, not from the ink. A dotted capital İ, an accent or a descender never moves a label off its row or changes a gap.

## 6. Checking a chart

Before a chart type or theme change is considered done:

1. Render `examples/showcase.yaml` with `--still`, once as is, once with `--aspect 9:16` and once with `--aspect 1:1`.
2. Look at every PNG at 100% and at phone size (about 25%).
3. Check: nothing clipped, nothing outside the safe area, no overlapping labels, highlight is obvious at phone size, source line readable.
4. Play the clip once: motion eases, highlight beat is clear, final hold is still.
