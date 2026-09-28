# vizreel-progress

An example plugin for [vizreel](https://github.com/efedalbay/vizreel): a `progress` chart type that shows how far a value has come toward a goal. The bar fills while the percent counts up.

It is a starting point for your own chart types, not a published package. [Writing a chart type](https://github.com/efedalbay/vizreel/blob/main/docs/PLUGINS.md) explains every part.

## Try it

From a clone of the vizreel repository:

```bash
uv run --with ./examples/plugin vizreel types
uv run --with ./examples/plugin vizreel render examples/plugin/progress.yaml --quality preview --still
```

To use it with an installed vizreel, install it next to vizreel:

```bash
uv tool install vizreel --with ./examples/plugin
```

## Fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `value` | number ≥ 0 | yes | — | How far it has come. |
| `goal` | number > 0 | yes | — | Where it is going. A value past the goal fills the bar and shows more than 100%. |
| `label` | string | no | — | Line under the bar. |
| `number` | object | no | `{}` | Formatting of the value and the goal, as for any vizreel chart. |
| `duration` | number | no | `4` | Seconds, at least 2. |

`title`, `subtitle` and `source` work as for every chart type.

## Files

- `pyproject.toml` lists the chart type under the `vizreel.chart_types` entry point group.
- `src/vizreel_progress/__init__.py` holds the spec model and the chart type.
- `progress.yaml` is an example spec.
