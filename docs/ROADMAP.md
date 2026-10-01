# Roadmap

Work proceeds one milestone at a time. A milestone is done only when every acceptance criterion is met, tests pass on Windows, and the relevant docs are updated.

Every milestone below is done, as of 0.16.0. From here vizreel grows from real use: bugs and missing pieces found while making videos with it come in as [bug reports](https://github.com/efedalbay/vizreel/issues/new?template=bug-report.yml) and become fixes in the next release.

## M0 — Project skeleton

- `pyproject.toml` with `src/` layout, package name `vizreel`, Python `>=3.11`, entry point `vizreel = vizreel.cli:app`.
- Dependencies: `manim`, `typer`, `pydantic>=2`, `pyyaml`, `rich`. Dev: `pytest`, `ruff`, `mypy`.
- `vizreel --version` and `vizreel --help` work.
- ruff and pytest configured in `pyproject.toml`.
- GitHub Actions: lint + unit tests on `windows-latest` and `ubuntu-latest`, Python 3.11 and 3.12.

**Done when:** `uv sync` then `uv run vizreel --version` works on Windows; CI is green.

## M1 — Spec and validation

- Pydantic models for everything in `docs/SPEC.md` (all four chart types, number format, meta).
- Discriminated union on `type`, built from the chart registry (chart classes may still be stubs).
- `vizreel validate <spec>`: reports all errors with locations; exit code 0/1.
- `vizreel schema`: prints JSON Schema.
- `format/numbers.py`: prefix, suffix, decimals, compact (`K`, `M`, `B`, `T`), negative numbers, rounding rules. Fully unit-tested.

**Done when:** every example in `docs/SPEC.md` validates; a set of deliberately broken specs in `tests/unit/fixtures/` produce the expected error messages.

## M2 — Render pipeline + `stat`

- Theme model, `default` built-in theme, theme loader.
- Bundled fonts registered at startup (open license, license file included).
- `render/engine.py` and `render/scene.py`: one clip per chart, output folder, `--only`, `--quality preview|final`, `--still`, `--format`.
- `stat` chart type fully implemented to `docs/DESIGN.md`.
- Verify transparent output imports correctly in DaVinci Resolve and CapCut on Windows. If a format does not keep alpha in an editor, add a re-encode step (for example ProRes 4444 via PyAV) and document which format to use for which editor.

**Done when:** `vizreel render examples/showcase.yaml --only <stat-id> --still` produces a clip and PNG that pass the checklist in `docs/DESIGN.md` §6; alpha import verified and documented.

## M3 — `line` and `bar`

- Axis/range computation as pure, tested functions (nice tick values, auto range from 0 for positive data).
- Direct labels with collision avoidance for up to 3 series.
- Highlight beat for both types.

**Done when:** showcase line and bar charts pass the design checklist at 1080p and 4k.

## M4 — `timeline`

- Even spacing for events, label placement alternating above/below when needed.
- Emphasis event styling and highlight beat.

**Done when:** showcase timeline with 2, 4 and 7 events passes the design checklist.

## M5 — Themes and polish

- Second built-in theme (`light`).
- `vizreel themes list`, `vizreel theme check <theme>`: WCAG contrast of text roles against background/panel, and color-vision-deficiency separation of `series` colors. Fails with clear messages.
- `examples/themes/example-brand.yaml` showing a custom theme.
- `vizreel new <type>`: prints a commented template for a chart type.

**Done when:** both built-in themes pass `theme check`; a custom theme loads by path.

## M6 — Release v0.1.0

- README complete: install on Windows, quickstart, GIFs of each chart type, spec reference link, theme guide, editor import notes.
- `CHANGELOG.md`, version `0.1.0`, tag and GitHub release.
- Publish to PyPI (trusted publishing from GitHub Actions).

**Done when:** `pip install vizreel` in a clean Windows environment, then the README quickstart, works exactly as written.

From here on, each milestone ends with a minor release (M7 → 0.2.0, M8 → 0.3.0, …). M9 adds its chart types one release at a time: the first in 0.4.0, each further type in 0.4.1, 0.4.2 and so on.

## M7 — Watch mode

- `vizreel render SPEC --watch`: render once, then re-render whenever the spec file, or a theme file it uses, changes. Ctrl+C stops.
- Only the charts that changed are rendered again; a change to `meta` or to the theme renders every chart.
- An invalid spec while editing prints its errors and keeps watching.
- No new dependency: the files are polled.

**Done when:** saving a spec starts a render within about a second, only changed charts are re-rendered, an invalid save does not stop watching, and Ctrl+C exits with code 0.

## M8 — Vertical 9:16

- Vertical resolution presets for Shorts, and a layout for every chart type in the vertical frame.
- Revisit the bar label length limit, which is tighter in a narrow frame: with 8 bars at the default theme a category label fits about 10 characters per line on two lines at 16:9, and a longer label is an error. An option is to let labels shrink down to the theme's minimum size.

**Done when:** every showcase chart passes the design checklist in both 16:9 and 9:16.

## M9 — New chart types

- Animated `table`, `compare` (before/after), `waterfall`, stacked `bar`, `share` (part-to-whole, max 6 parts). Each has its own plan and follows the chart type contract.

**Done when:** each new type is in `examples/showcase.yaml`, passes the design checklist in 16:9 and 9:16, and is documented in `docs/SPEC.md`.

## M10 — Chart states across clips

- The same chart used several times in a video, each clip continuing from the last: the highlight moves (the next timeline event, the next bar) and a clip can start from where the previous one ended instead of drawing again.

**Done when:** a sequence of clips cut back to back in an editor looks like one continuous chart.

## M11 — Number locales

- A locale for number formatting: `en-US`, `tr-TR`, `es-ES`, `pt-BR` and `fr-FR` (`1,846` / `1.846` / `1 846`, `47%` / `%47` / `47 %`), with compact unit names in full or abbreviated.

**Done when:** every number format option works in every locale and is documented.

## M12 — Third-party chart types

- Chart types from other packages via Python entry points, using the same chart type contract as the built-in types.

**Done when:** an example plugin package installs next to vizreel and its chart type validates, renders and appears in `vizreel new`.

## M13 — Output for every editor

- Every common frame rate: 23.976, 24, 25, 29.97, 30, 50, 59.94 and 60, in `meta.fps` and with `--fps`. A clip whose rate differs from the timeline's is blended or dropped by the editor.
- A square 1:1 frame for feeds (`aspect: "1:1"`), named `ID.square.mov`.
- ProRes 4444 with alpha (`--format prores`), the professional editors' standard, and a PNG sequence with alpha (`--format png`), which every editor reads.

**Done when:** every showcase chart renders at every rate with the exact frame count, passes the design checklist at 1:1, and the ProRes and PNG outputs keep their transparency.

## M14 — Data from files

- A chart's data read from a CSV file next to the spec instead of written in the YAML, for every chart type whose data is a list or a table. Standard library only.

**Done when:** every such chart type in the showcase can take its data from a CSV file, errors name the file, row and column, and `--watch` renders again when the CSV file is saved.

## M15 — More chart types

- `grouped`: bars in groups of two or three, one group per category.
- `area`: one to three series as filled areas, optionally stacked.
- `progress`: how far a value has come toward a goal, as a bar or a gauge ring. The example plugin gets a chart type of its own.

**Done when:** each new type is in `examples/showcase.yaml`, passes the design checklist in 16:9, 9:16 and 1:1, and is documented in `docs/SPEC.md`.

## M16 — Motion options

- An optional exit at the end of a clip, so a chart can leave the screen by itself.
- A choice of entrance for the elements that appear, and of easing, within what the design rules allow.

**Done when:** every chart type honors the exit and entrance options, clips keep their exact length, and sequences still cut seamlessly.

## M17 — Races

- A bar chart race: categories whose values change over periods, the bars growing and changing places, the period counting on. A line race draws series over periods with their labels following the lines.

**Done when:** a race from a CSV file with at least 20 periods renders smoothly in 16:9, 9:16 and 1:1, with bars that change places without overlapping.

## M18 — Richer races and a brand logo

- Images next to the bars of a `bar-race`, such as logos or flags, one per series, from image files next to the spec.
- Captions that appear over a race at the periods they name ("2008: the crisis"), in `bar-race` and `line-race`.
- A running total of every series in the corner of a `bar-race`.
- A logo in the theme, drawn in a corner of every chart's safe area.

**Done when:** a race with images, three captions and a total renders in 16:9, 9:16 and 1:1 without anything overlapping, the theme logo appears on every chart type inside the safe area, and a missing or unreadable image is an error that names the file.

## M19 — Scatter race

- A `scatter-race`: points for each series moving over periods on two value axes, sized by a third value if given, with their names, the axes growing to keep them in the frame. Its CSV file has a row per period and series.

**Done when:** a scatter race from a CSV file with at least 20 periods renders smoothly in 16:9, 9:16 and 1:1, with labels that do not overlap.

## M20 — Title cards and Excel files

- A `title-card` chart type: a headline card, with an optional line above and below it, to open a video or a section. (`title-card` rather than `title`, which every chart already has as a field.)
- Data read from a sheet of an Excel file (`.xlsx`) as well as from CSV.

**Done when:** a title card honors the themes, the frame shapes and the motion options like every chart type, and every chart type that reads CSV reads the same data from an Excel sheet.

## Testing by the community

Every milestone up to M20 is done. Two checks need a setup the project does not have, so they are left to users, and the README asks for them under "Help test vizreel":

- **macOS**: installing vizreel and rendering the showcase.
- **DaVinci Resolve**: whether transparent clips (`mov`, `prores`, `png`, `webm`) keep their alpha over footage.

Results come in as [test reports](https://github.com/efedalbay/vizreel/issues/new?template=test-report.yml) on GitHub Issues. A report of a problem becomes a fix in the next release; the README's editor table records what is confirmed to work.
