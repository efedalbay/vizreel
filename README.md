# vizreel

**Animated charts for video, from a YAML file.**

vizreel turns a short YAML spec into clean, animated chart clips (big numbers, line charts, bar charts and timelines) ready to drop into any video editor. Clips render with a transparent background by default, so they layer directly over your footage.

> **Status: early development.** vizreel is not usable yet. The spec format and architecture are designed; implementation is in progress. See the [roadmap](docs/ROADMAP.md) for what is being built and in which order.

## Why

Most chart tools are made for reports and dashboards. On video they look static and crowded, and animating them by hand in a motion graphics tool takes time for every chart.

vizreel is built for video from the start:

- **Declarative.** Describe the chart and its data in YAML. No code, no timeline editing.
- **Made to be watched.** Large type, one message per chart, a clear highlight moment, smooth eased motion, a clean final frame. See the [design rules](docs/DESIGN.md).
- **Editor-ready.** One clip per chart, transparent background, 1080p or 4K at 60 fps.
- **Consistent.** Colors, fonts and timing come from a theme, so every chart in a video matches.
- **Easy to install.** Pure Python. No LaTeX, no separate FFmpeg install.

## Example

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
| `line` | Values over time, up to 3 series, with an optional highlighted point |
| `bar` | Comparing up to 8 categories, with one highlighted bar |
| `timeline` | A sequence of up to 7 events, with an emphasized moment |

Every field is documented in the [spec reference](docs/SPEC.md).

## Installation

vizreel will be published on PyPI when it reaches v0.1.0. Until then, install from source.

**Requirements:** Python 3.11 or newer. Windows and Linux are tested; macOS is expected to work but is untested.

Using [uv](https://docs.astral.sh/uv/) (recommended):

```bash
git clone <this repository's URL>
cd vizreel
uv sync
uv run vizreel --help
```

Using pip:

```bash
git clone <this repository's URL>
cd vizreel
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -e .
vizreel --help
```

## Usage

```bash
vizreel validate charts.yaml            # check a spec and list every error
vizreel render charts.yaml              # render all charts to ./out
vizreel render charts.yaml --only offers --quality preview --still
vizreel schema > vizreel.schema.json    # JSON Schema for editors and tools
```

| Option | Description |
|---|---|
| `--out DIR` | Output folder (default `out`) |
| `--only ID` | Render a single chart |
| `--quality preview\|final` | `preview` is low resolution and fast; `final` uses the spec settings |
| `--format mov\|webm\|mp4` | `mov` and `webm` keep transparency; `mp4` uses the theme background |
| `--still` | Also save the final frame as a PNG |

## Themes

A theme sets colors, fonts, text sizes and motion timing for every chart. vizreel ships with built-in themes, and you can write your own in YAML and point to it from your spec:

```yaml
meta:
  theme: ./themes/my-brand.yaml
```

Theme reference and examples will be added in milestone M5.

## Documentation

- [Spec reference](docs/SPEC.md)
- [Design rules](docs/DESIGN.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)

## Contributing

Issues and pull requests are welcome. Before starting on a larger change, please open an issue to discuss it. New chart types follow the contract in the [architecture document](docs/ARCHITECTURE.md#chart-type-contract) and the rules in the [design document](docs/DESIGN.md).

## License

[MIT](LICENSE)

vizreel is built on [Manim Community Edition](https://www.manim.community/).
