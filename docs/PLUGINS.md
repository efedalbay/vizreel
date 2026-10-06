# Writing a chart type

vizreel finds chart types in other installed packages. Such a package, a plugin, adds a `type:` to the spec format that validates, renders, has a template for `vizreel new` and appears in the JSON Schema, just like the built-in types.

[`examples/plugin`](https://github.com/efedalbay/vizreel/tree/main/examples/plugin) is a complete plugin with a `dots` chart type, a grid of dots of which a number fill in. Copy it to start your own.

## The parts of a plugin

A plugin is an ordinary Python package with three things:

1. **A spec model**: a Pydantic model for the chart's fields, a subclass of `BaseChart`.
2. **A chart type**: a subclass of `ChartType` that builds the chart on a Manim scene.
3. **An entry point** in `pyproject.toml` that tells vizreel where the chart type is.

```toml
[project]
name = "vizreel-dots"
dependencies = ["vizreel>=0.12"]

[project.entry-points."vizreel.chart_types"]
dots = "vizreel_dots:DotsChartType"
```

The entry point's name (`dots`) must be the chart type's `name`, which is the `type:` value in the spec. It cannot be the name of a built-in type.

## The spec model

```python
from typing import Annotated, Literal

from pydantic import Field

from vizreel.plugin import BaseChart, Duration, NumberFormat, Text


class DotsChart(BaseChart):
    """How many of a group, as a grid of dots of which that many fill in."""

    type: Literal["dots"]
    duration: Duration = 4
    value: Annotated[int, Field(ge=0)]
    total: Annotated[int, Field(ge=2, le=100)]
    label: Text | None = None
    number: NumberFormat = Field(default_factory=NumberFormat)
```

- `type` must be `Literal` of the chart type's name.
- `BaseChart` brings `id`, `title`, `subtitle`, `source`, `duration`, `motion` and `data`; give `duration` a default that suits the chart.
- The model is strict, like the rest of the spec: unknown fields and loosely typed values are errors, reported with their location. Use Pydantic's constraints (`Field(gt=0)`) and validators for your own rules.
- To make the chart tellable as a [sequence](SPEC.md#sequences), subclass `SequencedChart` instead and implement `emphasis` (see below).

## The chart type

```python
from vizreel.plugin import CHART_API_VERSION, ChartType


class DotsChartType(ChartType):
    """A number that counts up while as many dots of a grid fill in."""

    name = "dots"
    model = DotsChart
    api_version = CHART_API_VERSION
    template = """\
- id: renewals
  type: dots
  value: 18
  total: 25
"""

    def build(self, scene):
        from manim import Dot

        from vizreel.plugin import render
        ...
```

| Attribute | What it is |
|---|---|
| `name` | The `type:` value in the spec. It cannot be the name of a built-in type. |
| `model` | The spec model. |
| `template` | A commented example chart as a YAML list item, printed by `vizreel new`. It must be valid. |
| `api_version` | The chart API version the chart type is written for, `CHART_API_VERSION`. Required. |
| `fits_to_content` | Optional, `True` by default. In a 9:16 frame, vizreel builds the chart once without recording to measure its content; if it leaves much of the frame empty, the chart is built again in a layout whose title, source and panel close in around it. Draw the header with `render.header`, the source with `render.source_line` and the panel around `layout.inner`, and center your content in `layout.content`, and this works by itself; set it to `False` if you place them yourself. |
| `own_header` | Optional, `False` by default. Set it to `True` if the chart sets its title and subtitle itself, at sizes of its own, rather than with `render.header`; its layout then has no title band, and `layout.content` reaches the top of `layout.inner`. |
| `build(scene)` | Adds mobjects to the Manim scene and plays the animation. |
| `emphasis(item)` | Only for a `SequencedChart`: the animations that move the emphasis to the element a sequence item names. |
| `logo_corner` | Optional, set in `build` before the first animation: where the lower right corner of the theme's logo goes, for a chart that draws its panel around its own content instead of `layout.inner`. By default the logo goes at the lower right of `layout.source`, and vizreel draws it with the chart's first animation, so a chart type needs nothing else for it. |
| `from_table(table, chart)` | Optional classmethod: lets a chart read its data from a CSV file or a sheet of an Excel workbook (`data:` in the spec; see "Data from files" in [SPEC.md](SPEC.md)). It returns the chart's data fields as the spec would write them, which are then validated with the rest. Read cells with `table.text(row, column)`, `table.number(row, column)` and `table.optional_number(row, column)`, which parse numbers in the spec's locale, return a number a workbook stores as it is, and raise `TableError` naming the line and column of a wrong cell; check the shape with `table.require_width` and `table.require_rows`. `chart` holds the fields the spec writes, not yet validated. Without it, a chart with `data:` is an error. |

In `build`, the chart type has:

- `self.chart`: the validated chart, an instance of `model`.
- `self.theme`: colors, fonts, sizes and motion timing.
- `self.layout`: the geometry of the frame: `content` is the box to draw the chart in, `title` and `source` the bands for the header and the source line, `vertical` whether the frame is 9:16, `panel` whether to draw a background panel.
- `self.locale`: how numbers are written. Pass it to every formatting call.

## The rules

A plugin chart looks at home next to the built-in ones when it follows the same rules:

- **Styling from the theme, geometry from the layout.** No literal colors, font names or pixel sizes. Convert theme sizes, which are px at 1080p, with `px()`.
- **Numbers through the formatting functions**, with `locale=self.locale`: `format_number`, `format_numbers`, `format_percent`, `format_change`. Counting numbers use `NumberGlyphs` from `vizreel.plugin.render`, which keeps digits from jittering, and pass `unit_of=` the value they count to, so they count in its unit.
- **Exactly `chart.duration` long.** Divide the clip with `split_duration` and end with the theme's hold, in which nothing moves. `check_reading_time` checks that text stays on screen long enough to be read.
- **Text that does not fit is an error, not smaller text.** `wrapped_block` wraps text onto two lines, or as many as its `max_lines`, and raises `RenderError` when it still does not fit; `check_fits` does the same for one mobject. A big number may shrink, with `fitting_number_size` and `count_samples`, as the built-in types do.
- **Expected failures raise `RenderError`** with a message the user can act on. Other exceptions are reported as unexpected errors in your package.
- **Honor the theme's highlight ring** if your chart has a highlighted value: when `theme.highlight_mark` is `ring`, build one with `render.highlight_ring(box, theme)` around the value and play `render.draw_ring` in the highlight beat; `render.erase_ring` takes it away when the emphasis moves.
- **Make the panel, titles, labels and legends appear with `render.appear`**, not Manim's `FadeIn`, so that they honor the entrance the theme or spec chooses (`fade`, `rise` or `zoom`). The exit at the end of a clip needs nothing from the chart type: vizreel plays it after the chart's last wait.
- **Rebuild a growing shape with `render.redrawn_shapes`**, not Manim's `always_redraw`, which copies every frame's new points into the old shape one by one and can take most of the render time. The example plugin, written for older versions, still uses `always_redraw`.
- **Import Manim and `vizreel.plugin.render` inside `build`**, not at the top of the module. vizreel imports every chart type to validate a spec, and importing Manim takes several seconds.

The [design rules](DESIGN.md) describe the look every chart follows: one highlighted element, large type, the safe area, eased motion.

## The API

Import everything from `vizreel.plugin` and `vizreel.plugin.render`. The rest of vizreel is internal and can change in any release.

| Module | Contains |
|---|---|
| `vizreel.plugin` | `ChartType`, `CHART_API_VERSION`, `BaseChart`, `SequencedChart`, `SpecModel`, `NumberFormat`, `Text`, `Duration`, `Theme`, `FontStyle`, `Layout`, `Box`, `Locale`, `RenderError`; `Table` and `TableError` for `from_table`; number formatting (`format_number`, `format_numbers`, `format_percent`, `format_change`, `change_amount`, `change_decimals`, `decimals_for`, `shared_decimals`, `whole_percents`, `MINUS_SIGN`); timing (`split_duration`, `Phases`, `check_reading_time`, `staggered_progress`, `sequential_progress`); sizes (`px`, `stack_gap`, `stroke_width`, `count_samples`, `fitting_number_size`, `SMALLEST_NUMBER_SCALE`); `arranged`, which picks a landscape or vertical geometry for the frame and tries both at 1:1; for tests, `render_spec`, `RenderOptions` and `ChartResult`. It does not import Manim. |
| `vizreel.plugin.render` | Manim building blocks: `appear`, `header`, `source_line`, `panel` (with the theme's texture, a group), `text`, `text_block`, `wrapped_block`, `TextBlock`, `line_metrics`, `NumberGlyphs`, `stack`, `bounds`, `check_fits`, `color`, `easing`, `fade_away`, `redrawn_shapes`; for the theme's highlight ring, `highlight_ring`, `draw_ring` and `erase_ring`. It imports Manim. |

Every name has a docstring. The built-in chart types in [`src/vizreel/charts`](https://github.com/efedalbay/vizreel/tree/main/src/vizreel/charts) use the same functions and are worth reading.

### Versions

`CHART_API_VERSION` is the version of this API. It goes up when a change to it would break chart types written for the previous version; the [changelog](https://github.com/efedalbay/vizreel/blob/main/CHANGELOG.md) says what changed. A chart type whose `api_version` does not match is not loaded, with a message asking for a version of the package made for this vizreel, rather than failing in the middle of a render.

Declare the lowest vizreel version that has everything you use as a dependency: `vizreel>=0.7` for API 1, or `vizreel>=0.12` if you use `render.appear`, as the example plugin does.

## Trying a plugin

In the plugin's folder, `uv run` installs the plugin and the vizreel it depends on into the plugin's own environment:

```bash
uv run vizreel types
uv run vizreel new dots -o chart.yaml
uv run vizreel render chart.yaml --quality preview --still
```

`vizreel types` lists every chart type with the package it comes from. A chart type that could not be loaded is not listed; vizreel prints a warning saying why, and so does every other command that reads specs. A spec that uses it gets an "unknown type" error with the same reason.

For tests, `render_spec` from `vizreel.plugin` renders a spec file and returns each clip's result, with its video file, its duration and any error; see how vizreel tests the example plugin in [`tests/render/test_render.py`](https://github.com/efedalbay/vizreel/blob/main/tests/render/test_render.py) (`test_the_example_plugin_renders`). Check the rendered stills against the design rules in 16:9, 9:16 and 1:1.

## Using a plugin

Install it in the same environment as vizreel. With uv, name the plugin's package, or its folder, next to vizreel:

```bash
uv tool install vizreel --with PLUGIN-PACKAGE
```

Installing a plugin runs its code whenever vizreel starts, like any Python package; install plugins you trust.
