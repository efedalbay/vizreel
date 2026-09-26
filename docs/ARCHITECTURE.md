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
│   ├── DESIGN.md            ← visual quality rules
│   └── ROADMAP.md           ← milestones and acceptance criteria
├── src/vizreel/
│   ├── __init__.py          ← version
│   ├── __main__.py          ← `python -m vizreel`
│   ├── cli.py               ← Typer app, no business logic
│   ├── errors.py            ← VizreelError hierarchy
│   ├── validation.py        ← YAML reading and user-facing validation messages
│   ├── spec/
│   │   ├── models.py        ← Pydantic models for the spec
│   │   └── loader.py        ← read YAML → validated Spec
│   ├── themes/
│   │   ├── models.py        ← Theme model
│   │   ├── loader.py        ← resolve theme by name or path
│   │   └── builtin/         ← default.yaml, light.yaml
│   ├── charts/
│   │   ├── base.py          ← ChartType base class, timing helpers
│   │   ├── registry.py      ← @register decorator, lookup by type name
│   │   ├── stat.py
│   │   ├── line.py
│   │   ├── bar.py
│   │   └── timeline.py
│   ├── render/
│   │   ├── engine.py        ← render a Spec: loop charts, configure Manim, write files
│   │   ├── scene.py         ← generic Manim Scene that hosts one chart
│   │   ├── layout.py        ← frame geometry in scene units (pure functions)
│   │   ├── elements.py      ← shared Manim building blocks: text, panel, easing
│   │   └── fonts.py         ← register bundled fonts with Pango
│   ├── format/
│   │   └── numbers.py       ← number/currency/date formatting (pure functions)
│   └── assets/
│       └── fonts/           ← bundled open-license fonts + their licenses
├── examples/
│   ├── showcase.yaml        ← one of every chart type (fictional data)
│   └── themes/example-brand.yaml  ← added in M5
└── tests/
    ├── unit/                ← fast, no rendering
    └── render/              ← slow, marked `@pytest.mark.render`
```

## Data flow

```
spec.yaml
   │  spec/loader.py  (YAML → dict → Pydantic Spec, all errors collected)
   ▼
Spec ──► themes/loader.py resolves theme (built-in name or file path)
   │
   ▼
render/engine.py
   for each chart in spec (optionally filtered by --only):
       ChartType = registry.get(chart.type)
       layout = build_layout(theme sizes, panel, title/subtitle/source lines)
       configure Manim (resolution, fps, transparency, output path) via tempconfig
       ChartScene(ChartType(chart, theme, layout)).render()
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

    def __init__(self, chart: BaseChart, theme: Theme, layout: Layout): ...

    @abstractmethod
    def build(self, scene: Scene) -> None:
        """Add mobjects and play animations on the given scene."""
```

Rules:

- Registered with `@register` from `charts/registry.py`. The registry is the only place that maps `type` strings to classes.
- A chart reads **all** styling from `theme` and **all** geometry from `layout` (safe area, title area, plot area). No literal colors, font names or pixel sizes inside chart modules.
- A chart builds from Manim primitives (`Line`, `Rectangle`, `Text`, `VGroup`, `ValueTracker`) rather than Manim's high-level `BarChart`/`Axes` when those limit styling.
- A chart must respect `chart.duration`. The shared timing helpers in `base.py` split duration into intro, main animation, highlight and hold phases, and check that text stays on screen long enough to be read.
- Number and date text always goes through `format/numbers.py`.
- A chart module imports Manim, and `render/elements.py`, inside `build`, not at the top. `vizreel validate` imports every chart module through the registry, and importing Manim takes several seconds.
- Text is never shrunk to fit. Text that does not fit at the theme size is a `RenderError` asking the user to shorten it.

Adding a new chart type = one module in `charts/` + one Pydantic model + one section in `docs/SPEC.md` + one example in `examples/showcase.yaml` + tests. Nothing else.

## Spec models

- `Spec` has `version`, `meta` and `charts`.
- `charts` is a Pydantic **discriminated union** on the `type` field, built from the registry. Unknown types produce an error that lists valid types.
- Chart `id`s must be unique and filesystem-safe (`[a-z0-9-]+`).
- `vizreel schema` exports the JSON Schema of `Spec`. External tools (including AI assistants that write specs) use it to produce valid files.

## Theme system

A theme is a YAML file validated by `themes/models.py`. It contains:

- `colors`: named roles (`background`, `surface`, `text`, `muted`, `grid`, `accent`, `positive`, `negative`, `highlight`, `series` list of at least 3).
- `fonts`: `heading`, `body`, `numbers`, each a `family` and a `weight` (`regular`, `semibold`, `bold`). At most two families. Bundled fonts are registered with ManimPango at startup.
- `sizes`: `title`, `subtitle`, `big_number`, `label`, `value`, `caption`, `panel_radius`, `panel_padding`.
- `motion`: `easing` (ease-out curves only), `title_fade`, `structure`, `stagger`, `highlight`, `hold`, in seconds.
- `background_panel`: whether to draw a rounded panel behind the chart when rendering with transparency.

Sizes are **font sizes in pixels at 1080p**, the unit `docs/DESIGN.md` uses, so a theme can be checked against the design rules directly. They scale with the output resolution; the layout converts them to scene units in one place. The theme model enforces the minimum sizes of `docs/DESIGN.md` §2 and a final hold of at least 1.5 seconds.

Resolution order for `meta.theme`: built-in name → path relative to the spec file → absolute path. Missing theme = clear error.

## Rendering

- Resolution presets: `720p`, `1080p` (default), `1440p`, `4k`. Aspect ratio 16:9. Vertical `1080x1920` preset for Shorts is planned (see roadmap).
- Quality flag: `--quality preview` (low resolution, 15 fps, fast) or `final` (spec resolution and fps).
- Formats: `mov` with alpha (default), `webm` with alpha, `mp4` opaque (uses theme background). Alpha compatibility with common editors is verified in milestone M2 and documented in the README.
- `--still` also writes the final frame as PNG. This is how both humans and Claude Code check a chart visually without playing video.
- Output is deterministic: same spec + theme → same frames. No randomness.
- Manim's own cache and partial-movie files go to a temporary directory, not to the user's output folder.

## Errors

- All expected failures raise a subclass of `VizreelError` with a user-facing message.
- The CLI catches `VizreelError`, prints it with Rich, and exits with code 1. Unexpected exceptions show a traceback only with `--debug`.
- Spec errors point to the exact location: `charts[2].data[4].y: value must be a number`.

## Cross-platform notes

- Use `pathlib.Path` everywhere. Never build paths with string concatenation.
- Primary development and test platform: Windows. CI also runs on Ubuntu. macOS is expected to work but is untested until someone can test it.
- Output file names are ASCII-safe even if chart titles contain other characters.
