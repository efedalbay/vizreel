# Architecture

vizreel turns a declarative YAML spec into short, animated chart clips for video editing. This document describes how the code is organized and why.

## Goals

1. **Declarative input.** A spec file fully describes every chart. No code is needed to make a chart.
2. **Editor-ready output.** Each chart renders to its own clip, with a transparent background by default, so it can be layered over footage in any video editor.
3. **Consistent look.** All visual decisions (colors, fonts, timing) come from a theme. Charts never hard-code styling.
4. **Easy to extend.** A new chart type is one new module. Nothing else in the codebase has to change.
5. **Easy to install.** `pip install vizreel` on Windows, Linux and macOS. No LaTeX, no separate FFmpeg install.

## Non-goals (v1)

- A graphical user interface.
- Editing or cutting video. vizreel produces clips; the editor assembles them.
- Mathematical typesetting (LaTeX). All text is rendered with Manim's `Text` (Pango).
- Live data fetching. The spec contains the data.

## Stack

| Concern | Choice | Reason |
|---|---|---|
| Language | Python 3.11+ | Data-oriented, largest ecosystem |
| Animation engine | Manim Community Edition (v0.21.x) | Mature, programmatic, smooth animation primitives. Since v0.19 it uses PyAV, so no separate FFmpeg install |
| CLI | Typer | Typed commands, automatic help |
| Spec validation | Pydantic v2 | Clear error messages, JSON Schema export |
| YAML | PyYAML (`safe_load` only) | Standard, safe |
| Terminal output | Rich | Readable progress and errors |
| Packaging | `pyproject.toml`, `src/` layout, uv for development | Modern, reproducible |
| Tests | pytest | Standard |
| Lint / format | ruff | Fast, one tool |
| Type check | mypy (strict on `spec/`, `themes/`, `format/`) | Catches errors in data code |

## Directory layout

```
vizreel/
├── pyproject.toml
├── README.md
├── LICENSE
├── docs/
│   ├── ARCHITECTURE.md      ← this file
│   ├── SPEC.md              ← spec format reference (source of truth)
│   ├── THEMES.md            ← theme format reference and checks
│   ├── DESIGN.md            ← visual quality rules
│   ├── ROADMAP.md           ← milestones and acceptance criteria
│   └── images/              ← README GIFs, made by scripts/readme_gifs.py
├── src/vizreel/
│   ├── __init__.py          ← version
│   ├── __main__.py          ← `python -m vizreel`
│   ├── cli.py               ← Typer app, no business logic
│   ├── errors.py            ← VizreelError hierarchy
│   ├── validation.py        ← YAML reading and user-facing validation messages
│   ├── watch.py             ← `render --watch`: poll files, re-render changed charts
│   ├── spec/
│   │   ├── models.py        ← Pydantic models for the spec
│   │   ├── data.py          ← read a chart's CSV data file into a Table
│   │   └── loader.py        ← read YAML and data files → validated Spec
│   ├── themes/
│   │   ├── models.py        ← Theme model
│   │   ├── loader.py        ← resolve theme by name or path
│   │   └── builtin/         ← default.yaml, light.yaml
│   ├── charts/
│   │   ├── base.py          ← ChartType base class, timing helpers
│   │   ├── registry.py      ← @register decorator, plugin entry points, lookup by type name
│   │   ├── stat.py
│   │   ├── line.py
│   │   ├── bar.py
│   │   ├── timeline.py
│   │   ├── compare.py
│   │   ├── waterfall.py
│   │   ├── stacked.py
│   │   ├── grouped.py
│   │   ├── share.py
│   │   ├── table.py
│   │   └── _bars.py         ← parts the bar-like types share; not a chart type
│   ├── render/
│   │   ├── engine.py        ← render a Spec: loop charts, configure Manim, write files
│   │   ├── scene.py         ← generic Manim Scene that hosts one chart; fits vertical cards
│   │   ├── layout.py        ← frame geometry in scene units (pure functions)
│   │   ├── elements.py      ← shared Manim building blocks: text, panel, easing
│   │   ├── numbers_text.py  ← counting numbers composed from cached glyphs
│   │   ├── scales.py        ← axis ranges, ticks, label placement (pure functions)
│   │   └── fonts.py         ← register bundled fonts with Pango
│   ├── plugin/              ← the public API for chart types in other packages
│   │   ├── __init__.py      ← contract, models, formatting, timing (no Manim)
│   │   └── render.py        ← Manim building blocks
│   ├── format/
│   │   ├── numbers.py       ← number formatting (pure functions)
│   │   └── locales.py       ← separators, percent sign and unit names per locale
│   └── assets/
│       └── fonts/           ← bundled open-license fonts + their licenses
├── examples/
│   ├── showcase.yaml        ← one of every chart type (fictional data)
│   ├── showcase-tr.yaml     ← the showcase in Turkish, numbers written for tr-TR
│   ├── brand.yaml           ← charts in the example brand theme
│   ├── data.yaml, data/     ← charts that read their data from CSV files
│   ├── themes/example-brand.yaml  ← a complete custom theme
│   └── plugin/              ← vizreel-progress, an example plugin package
├── scripts/
│   └── readme_gifs.py       ← development tool: README GIFs
└── tests/
    ├── unit/                ← fast, no rendering
    └── render/              ← slow, marked `@pytest.mark.render`
```

## Data flow

```
spec.yaml
   │  spec/loader.py  (YAML → dict; each chart's `data:` CSV file → spec/data.py Table
   │                   → ChartType.from_table fills its fields; dict → Pydantic Spec,
   │                   all errors collected)
   ▼
Spec ──► themes/loader.py resolves theme (built-in name or file path)
   │
   ▼
render/engine.py
   for each chart in spec (optionally filtered by --only):
       ChartType = chart_registry().get(chart.type)   # built-in or from a plugin
       layout = build_layout(theme sizes, panel, title/subtitle/source lines)
       configure Manim (resolution, fps, transparency, output path) via tempconfig
       ChartScene(ChartType(chart, theme, layout, locale)).render()
   │
   ▼
out/<chart-id>.<ext>   (+ optional <chart-id>.png still)
```

Each chart renders independently. One failing chart must not stop the others; the engine reports all failures at the end and exits non-zero.

## Chart type contract

Every chart type is a subclass of `ChartType` in `charts/base.py`:

```python
class ChartType(ABC):
    name: ClassVar[str]                 # the `type:` value in the spec, e.g. "line"
    model: ClassVar[type[BaseChart]]    # Pydantic model for this chart's fields
    template: ClassVar[str]             # commented example chart, printed by `vizreel new`

    def __init__(self, chart: BaseChart, theme: Theme, layout: Layout, locale: Locale): ...

    @abstractmethod
    def build(self, scene: Scene) -> None:
        """Add mobjects and play animations on the given scene."""

    def emphasis(self, item) -> list[Animation]:
        """Animations that move the emphasis to the element a sequence item names."""

    @classmethod
    def from_table(cls, table: Table, chart: dict) -> dict:
        """The chart's data fields, as a spec writes them, read from a CSV data file."""
```

A chart type whose model is a `SequencedChart` (every type with a highlight) implements `emphasis`, and its own highlight beat plays it. `emphasis` sets the final look of every element that can be emphasized, whatever it looked like before, so emphasizing an element always ends on the same frame. That is what lets a sequence cut seamlessly: the engine renders a later clip of a sequence with `ChartType.continue_to`, which builds the chart emphasizing the previous item inside `ChartScene.unrecorded()` (Manim finishes every animation without writing a frame, leaving the scene on the previous clip's last frame), then plays `emphasis` for the next item and holds. `render/engine.py` plans the clips with `plan_clips`. Anything the emphasis makes appear must start invisible, and anything it removes fades by opacity (`elements.fade_away`) rather than with Manim's FadeOut, which reshapes curves; a render test compares the frames at every cut, for every type and aspect.

Rules:

- Registered with `@register` from `charts/registry.py`. The registry is the only place that maps `type` strings to classes.
- A chart type with a landscape and a vertical arrangement builds its geometry with `arranged(layout, landscape, vertical)` from `base.py`: 16:9 takes the first, 9:16 the second, and 1:1 tries the first and falls back to the second when it raises `RenderError`. Geometry is built before anything is added to the scene, so a failed attempt leaves nothing behind.
- In a 9:16 frame, `ChartScene.fit_to_content` builds the chart once without recording and measures what it draws inside `layout.content`. If that is less than 90% of its height, the chart is built again in `Layout.fitted_to_content`: the title and source bands and `inner` close in around the content, and `content` keeps its size but moves, so the chart draws exactly the same content, shifted. That is why every chart centers its content in `layout.content` and draws its panel around `layout.inner`; a chart type that does not (`stat`, which fits its own card) sets `fits_to_content = False`.
- A chart type that can read its data from a file implements `from_table`. The loader reads the file named by `data:` into a `Table` (`spec/data.py`: header, cells, the line of each row, and number parsing in the spec's locale through `format/numbers.py`), and puts the fields `from_table` returns into the chart before Pydantic validates it, so data from a file passes exactly the checks written data does. A field the spec also writes is an error. `Table.text` and `Table.number` raise `TableError` naming the line and column of a wrong cell. The default `from_table` raises, so a type reads data files only if it says how.
- `api_version` is the version of the contract (`CHART_API_VERSION`) the chart type is written for. Built-in types inherit the current one; a plugin must declare it.
- A chart reads **all** styling from `theme` and **all** geometry from `layout` (safe area, title area, plot area). No literal colors, font names or pixel sizes inside chart modules.
- A chart builds from Manim primitives (`Line`, `Rectangle`, `Text`, `VGroup`, `ValueTracker`) rather than Manim's high-level `BarChart`/`Axes` when those limit styling.
- A chart must respect `chart.duration`. The shared timing helpers in `base.py` split duration into intro, main animation, highlight and hold phases, and check that text stays on screen long enough to be read.
- Number text always goes through `format/numbers.py`, with the chart's `self.locale`. The `locale` argument of its formatting functions has no default, so a call that forgets it fails type checking instead of writing English numbers into a Turkish video.
- A chart module imports Manim, and `render/elements.py`, inside `build`, not at the top. `vizreel validate` imports every chart module through the registry, and importing Manim takes several seconds.
- Text is never shrunk to fit. Text that does not fit at the theme size is a `RenderError` asking the user to shorten it. The exception is a big number, which cannot wrap: `fitting_number_size` in `base.py` shrinks it to at most half its size, for the widest text of its count (`count_samples`); see `docs/DESIGN.md` §2.

### Chart types from other packages

`chart_registry()` holds the built-in types and, after them, the chart types installed packages list under the `vizreel.chart_types` entry point group (`importlib.metadata`, no extra dependency). Everything that needs chart types (the spec's discriminated union, the JSON Schema, `vizreel new`, the engine) reads this one registry, so a plugin type needs no code of its own anywhere else. A plugin that cannot be imported, uses a built-in name, has a mismatched `api_version` or breaks the contract is skipped and recorded in `registry.problems`; the CLI prints them as warnings, and an unknown type in a spec names the reason. A broken plugin must never make vizreel unusable. Plugins build only on `vizreel.plugin` and `vizreel.plugin.render`, which re-export the stable part of the code; `docs/PLUGINS.md` is the guide for authors.

Adding a new built-in chart type = one module in `charts/` (with its template) + one Pydantic model + one section in `docs/SPEC.md` + one example in `examples/showcase.yaml` + tests. Nothing else. The registry refuses a chart type without a template, and a test checks that every template is a valid spec, also with its commented optional fields uncommented.

## Spec models

- `Spec` has `version`, `meta` and `charts`.
- `charts` is a Pydantic **discriminated union** on the `type` field, built from the registry. Unknown types produce an error that lists valid types.
- Chart `id`s must be unique and filesystem-safe (`[a-z0-9-]+`).
- `vizreel schema` exports the JSON Schema of `Spec`. External tools (including AI assistants that write specs) use it to produce valid files.

## Theme system

A theme is a YAML file validated by `themes/models.py`. It contains:

- `colors`: named roles (`background`, `surface`, `text`, `muted`, `grid`, `accent`, `positive`, `negative`, `highlight`, `series` list of at least 3), and `dim_opacity` for everything except the highlighted element during the highlight beat.
- `fonts`: `heading`, `body`, `numbers`, each a `family` and a `weight` (`regular`, `semibold`, `bold`). At most two families. Bundled fonts are registered with ManimPango at startup.
- `sizes`: `title`, `subtitle`, `big_number`, `label`, `value`, `caption`, `panel_radius`, `panel_padding`, and the stroke widths `line`, `grid_line` and the marker diameter `dot`.
- `motion`: `easing` (ease-out curves only), `title_fade`, `structure`, `stagger`, `highlight`, `hold`, in seconds.
- `background_panel`: whether to draw a rounded panel behind the chart when rendering with transparency.
- `description`: optional one line shown by `vizreel themes list`.

`themes/check.py` checks a theme with pure functions: WCAG contrast of text and data colors against the panel and background, and the CIEDE2000 difference between colors that appear side by side, with normal vision and simulated protanopia, deuteranopia and tritanopia. `vizreel theme check` runs it; built-in themes must pass.

Sizes are **pixels at 1080p** (font sizes for text), the unit `docs/DESIGN.md` uses, so a theme can be checked against the design rules directly. They scale with the output resolution; the layout converts them to scene units in one place. The theme model enforces the minimum sizes of `docs/DESIGN.md` §2 and a final hold of at least 1.5 seconds.

Resolution order for `meta.theme`: built-in name → path relative to the spec file → absolute path. Missing theme = clear error.

## Rendering

- Resolution presets: `720p`, `1080p` (default), `1440p`, `4k`, named by the short side of the frame. Aspect `16:9` (default) or `9:16` (`meta.aspect`, `--aspect`). The short side of Manim's frame is 8 scene units in both aspects, so one scene unit is 135 pixels at 1080p either way and theme sizes need no conversion per aspect; `layout.py` gives each aspect its frame size and safe margins. Vertical files are named `<id>.vertical.<format>`.
- Chart types adapt to a vertical frame through `Layout.vertical`: bar charts use rows (`layout: auto`) and timelines run down the frame. Titles and subtitles wrap onto a second line when they do not fit; the engine measures them before it builds the layout, so the title band is as tall as the wrapped lines.
- Text is laid out by Pango on a fixed 4096-pixel surface, not one the size of the video, so it wraps and positions the same way in every output size (`elements.TEXT_SURFACE_PX`).
- Quality flag: `--quality preview` (low resolution, 15 fps, fast) or `final` (spec resolution and fps). A chart renders to `<id>.<format>`; preview files are named `<id>.preview.<format>` so that a preview never replaces a final clip that may already be in an editor project.
- Formats: `mov` with alpha (default), `webm` with alpha, `mp4` opaque (uses theme background). Alpha compatibility with common editors is verified in milestone M2 and documented in the README.
- A clip has exactly `round(duration × fps)` frames. Manim rounds every animation up to whole frames, so `ChartScene` rounds each animation through a frame clock that keeps the running total on the wanted time. Every `scene.play` in a chart passes an explicit `run_time`; the final hold is a frozen frame, so nothing can move during it.
- `--still` also writes the final frame as PNG. This is how both humans and Claude Code check a chart visually without playing video.
- Output is deterministic: same spec + theme → same frames. No randomness.
- Manim's own cache and partial-movie files go to a temporary directory, not to the user's output folder.

### Watch mode

`vizreel render --watch` runs `watch.py`. It renders once, then polls the spec file and the theme file it resolves to (standard library only, no file-system event dependency: at most two files are watched). A change is read only after the files have stayed unchanged for a moment, because some editors save in several steps. Each render compares the new spec with the last one that loaded: if `meta` or the theme changed every chart renders, otherwise only charts that are new or whose model differs. Charts that failed are rendered again on the next change. A spec or theme that fails to load is reported and watching goes on. The pure parts (`FileWatcher` with an injectable clock, `charts_to_render`) are unit-tested.

## Errors

- All expected failures raise a subclass of `VizreelError` with a user-facing message.
- The CLI catches `VizreelError`, prints it with Rich, and exits with code 1. Unexpected exceptions show a traceback only with `--debug`.
- Spec errors point to the exact location: `charts[2].data[4].y: value must be a number`.

## Cross-platform notes

- Use `pathlib.Path` everywhere. Never build paths with string concatenation.
- Primary development and test platform: Windows. CI also runs on Ubuntu. macOS is expected to work but is untested until someone can test it.
- Output file names are ASCII-safe even if chart titles contain other characters.
