# vizreel-dots

An example plugin for [vizreel](https://github.com/efedalbay/vizreel): a `dots` chart type that shows how many of a group, such as 18 of 25 customers, as a grid of dots. The number counts up while as many dots fill in, one after another.

It is a starting point for your own chart types, not a published package. [Writing a chart type](https://github.com/efedalbay/vizreel/blob/main/docs/PLUGINS.md) explains every part.

## Try it

From the root of a clone of the vizreel repository, install it into the development environment next to vizreel:

```bash
uv pip install --no-deps -e ./examples/plugin
uv run --no-sync vizreel types
uv run --no-sync vizreel render examples/plugin/dots.yaml --quality preview --still
```

`uv sync`, and `uv run` without `--no-sync`, remove it again, since the project does not depend on it; install it again after syncing.

To use it with an installed vizreel, install it next to vizreel:

```bash
uv tool install vizreel --with ./examples/plugin
```

## Fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `value` | whole number ≥ 0 | yes | — | How many of the group: the dots that fill in. At most `total`. |
| `total` | whole number, 2–100 | yes | — | How many there are in all: the dots in the grid. |
| `label` | string | no | — | Line under the grid, e.g. "of 25 customers renew their plan". |
| `number` | object | no | `{}` | Formatting of the value, as for any vizreel chart. |
| `duration` | number | no | `4` | Seconds, at least 2. |

`title`, `subtitle` and `source` work as for every chart type.

## Files

- `pyproject.toml` lists the chart type under the `vizreel.chart_types` entry point group.
- `src/vizreel_dots/__init__.py` holds the spec model and the chart type.
- `dots.yaml` is an example spec.
