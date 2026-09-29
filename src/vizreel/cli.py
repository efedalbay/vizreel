"""Command-line interface. Parses arguments, calls the library and prints results."""

import io
import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape

from vizreel import __version__
from vizreel.charts.registry import chart_registry
from vizreel.errors import InputFileError, OutputError, VizreelError
from vizreel.render.engine import ChartResult, RenderOptions, render_spec
from vizreel.spec.loader import load_spec, spec_json_schema
from vizreel.spec.templates import spec_template
from vizreel.themes.check import check_theme
from vizreel.themes.loader import describe_builtin_themes, load_theme
from vizreel.watch import watch_spec

app = typer.Typer(
    name="vizreel",
    help="Animated charts for video, from YAML and CSV files.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_show_locals=False,
)


def _print_version(value: bool) -> None:
    if value:
        typer.echo(f"vizreel {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_print_version,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Show the full traceback of unexpected errors."),
    ] = False,
) -> None:
    """Animated charts for video, from YAML and CSV files."""
    _replace_unprintable_characters()
    ctx.obj = debug


@app.command()
def validate(
    ctx: typer.Context,
    spec: Annotated[Path, typer.Argument(help="Spec file to check.", show_default=False)],
) -> None:
    """Check a spec file and list every error."""
    _warn_about_plugins()
    with _reporting_errors(ctx):
        loaded = load_spec(spec)
    count = len(loaded.charts)
    noun = "chart" if count == 1 else "charts"
    _stdout().print(f"[green]{escape(str(spec))} is valid[/]: {count} {noun}")


class QualityChoice(StrEnum):
    """Values of --quality."""

    preview = "preview"
    final = "final"


class AspectChoice(StrEnum):
    """Values of --aspect."""

    landscape = "16:9"
    vertical = "9:16"
    square = "1:1"


class FpsChoice(StrEnum):
    """Values of --fps."""

    film_ntsc = "23.976"
    film = "24"
    pal = "25"
    ntsc = "29.97"
    web = "30"
    pal_high = "50"
    ntsc_high = "59.94"
    web_high = "60"


class FormatChoice(StrEnum):
    """Values of --format."""

    mov = "mov"
    webm = "webm"
    mp4 = "mp4"
    prores = "prores"
    png = "png"


@app.command()
def render(
    ctx: typer.Context,
    spec: Annotated[Path, typer.Argument(help="Spec file to render.", show_default=False)],
    out: Annotated[Path, typer.Option("--out", help="Output folder.")] = Path("out"),
    only: Annotated[
        list[str] | None,
        typer.Option(
            "--only", help="Render only this chart id. Repeat for several.", show_default=False
        ),
    ] = None,
    quality: Annotated[
        QualityChoice,
        typer.Option(help="preview is small and fast; final uses the spec settings."),
    ] = QualityChoice.final,
    output_format: Annotated[
        FormatChoice | None,
        typer.Option(
            "--format",
            help="mov, webm, prores (ProRes 4444) and png (a folder of PNG frames) keep "
            "transparency; mp4 uses the theme background. Default: meta.format.",
            show_default=False,
        ),
    ] = None,
    still: Annotated[
        bool, typer.Option("--still", help="Also save the last frame as PNG.")
    ] = False,
    aspect: Annotated[
        AspectChoice | None,
        typer.Option(
            "--aspect",
            help="16:9 is landscape; 9:16 is vertical, for Shorts, and adds .vertical to "
            "file names; 1:1 is square, for feeds, and adds .square. Default: meta.aspect.",
            show_default=False,
        ),
    ] = None,
    fps: Annotated[
        FpsChoice | None,
        typer.Option(
            "--fps",
            help="Frames per second of a final render; match your editor's timeline. "
            "Default: meta.fps.",
            show_default=False,
        ),
    ] = None,
    watch: Annotated[
        bool,
        typer.Option(
            "--watch",
            help="Keep running and render again whenever the spec or its theme changes. "
            "Only changed charts are rendered. Ctrl+C stops.",
        ),
    ] = False,
) -> None:
    """Render each chart of a spec to its own clip."""
    _warn_about_plugins()
    options = RenderOptions(
        out_dir=out,
        only=tuple(only or ()),
        quality=quality.value,
        format=output_format.value if output_format else None,
        still=still,
        aspect=aspect.value if aspect else None,
        fps=float(fps.value) if fps else None,
    )
    console = _stdout()
    if watch:
        _watch(ctx, spec, options, console)
        return
    with _reporting_errors(ctx), console.status("Rendering...") as status:
        results = render_spec(
            spec,
            options,
            on_start=lambda chart: status.update(f"Rendering {escape(chart.id)}..."),
            on_done=lambda result: _print_chart_result(console, result),
            reraise=bool(ctx.obj),
        )
    failed = sum(1 for result in results if result.error)
    summary = f"{len(results) - failed} rendered, {failed} failed"
    if failed:
        _stderr().print(f"[red]{summary}[/]")
        raise typer.Exit(1)
    console.print(f"[green]{summary}[/]")


def _watch(ctx: typer.Context, spec: Path, options: RenderOptions, console: Console) -> None:
    def rendering(ids: list[str]) -> None:
        if ids:
            console.print(f"Rendering {escape(', '.join(ids))}...")
        else:
            console.print("No chart changed.")

    def waiting() -> None:
        console.print(f"[dim]Watching {escape(str(spec))} for changes. Press Ctrl+C to stop.[/]")

    with _reporting_errors(ctx):
        try:
            watch_spec(
                spec,
                options,
                on_render=rendering,
                on_result=lambda result: _print_chart_result(console, result),
                on_error=_print_vizreel_error,
                on_wait=waiting,
            )
        except KeyboardInterrupt:
            console.print("Stopped watching.")


def _print_vizreel_error(error: VizreelError) -> None:
    if isinstance(error, InputFileError):
        _print_input_error(error)
    else:
        _stderr().print(f"[red]error:[/] {escape(str(error))}")


def _print_chart_result(console: Console, result: ChartResult) -> None:
    name = escape(result.chart_id)
    if result.step is not None:
        name += f" {result.step}/{result.steps}"
    if result.error:
        _stderr().print(f"  [red]{name}[/]: {escape(result.error)}")
        return
    files = ", ".join(escape(str(path)) for path in (result.video, result.still) if path)
    console.print(f"  [green]{name}[/]: {files} ({result.seconds:.1f}s)")


@app.command()
def schema(
    ctx: typer.Context,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write the schema to this file (UTF-8) instead of printing it.",
            show_default=False,
        ),
    ] = None,
) -> None:
    """Print the JSON Schema of the spec format, for editors and tools."""
    _warn_about_plugins()
    text = json.dumps(spec_json_schema(), indent=2) + "\n"
    if output is None:
        sys.stdout.write(text)
        return
    with _reporting_errors(ctx):
        _write_text(output, text)
    _stdout().print(f"Wrote JSON Schema to {escape(str(output))}")


@app.command()
def new(
    ctx: typer.Context,
    chart_type: Annotated[
        str,
        typer.Argument(
            metavar="TYPE",
            help="Chart type, e.g. stat or bar. vizreel types lists them all.",
            show_default=False,
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write the template to this new file (UTF-8) instead of printing it.",
            show_default=False,
        ),
    ] = None,
) -> None:
    """Print a commented spec template for a chart type."""
    _warn_about_plugins()
    with _reporting_errors(ctx):
        text = spec_template(chart_type)
        if output is not None and output.exists():
            raise OutputError(f"{output} already exists; choose another file name")
    if output is None:
        sys.stdout.write(text)
        return
    with _reporting_errors(ctx):
        _write_text(output, text)
    _stdout().print(f"Wrote a {escape(chart_type)} template to {escape(str(output))}")


@app.command()
def types(ctx: typer.Context) -> None:
    """List every chart type, built-in or from an installed package."""
    with _reporting_errors(ctx):
        registry = chart_registry()
    console = _stdout()
    names = registry.names()
    name_width = max(len(name) for name in names)
    source_width = max(len(registry.source(name)) for name in names)
    for name in names:
        summary = (registry.get(name).__doc__ or "").strip().split("\n")[0]
        console.print(
            f"[bold]{escape(name.ljust(name_width))}[/]  "
            f"{escape(registry.source(name).ljust(source_width))}  [dim]{escape(summary)}[/]"
        )
    _warn_about_plugins()


themes_app = typer.Typer(help="Built-in themes.", no_args_is_help=True)
app.add_typer(themes_app, name="themes")
theme_app = typer.Typer(help="Work with one theme.", no_args_is_help=True)
app.add_typer(theme_app, name="theme")


@themes_app.command("list")
def themes_list(ctx: typer.Context) -> None:
    """List the built-in themes."""
    with _reporting_errors(ctx):
        themes = describe_builtin_themes()
    console = _stdout()
    for name, description in themes:
        console.print(f"[bold]{escape(name)}[/]  {escape(description or '')}".rstrip())


@theme_app.command("check")
def theme_check(
    ctx: typer.Context,
    theme: Annotated[
        str,
        typer.Argument(
            help="Built-in theme name, or path to a theme YAML file.", show_default=False
        ),
    ],
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="List every check, not only failures.")
    ] = False,
) -> None:
    """Check a theme for text contrast and color vision separation."""
    with _reporting_errors(ctx):
        results = check_theme(load_theme(theme, Path.cwd()))
    console = _stdout()
    for result in results:
        if verbose or not result.passed:
            status = "[green]PASS[/]" if result.passed else "[red]FAIL[/]"
            console.print(f"  {status}  {escape(str(result))}")
    failed = sum(1 for result in results if not result.passed)
    if failed:
        _stderr().print(f"[red]{escape(theme)}: {failed} of {len(results)} checks failed[/]")
        raise typer.Exit(1)
    console.print(f"[green]{escape(theme)}: all {len(results)} checks passed[/]")


def _warn_about_plugins() -> None:
    """Say which chart types from installed packages could not be loaded."""
    for problem in chart_registry().problems:
        _stderr().print(f"[yellow]warning:[/] {escape(str(problem))}")


def _write_text(path: Path, text: str) -> None:
    try:
        path.write_text(text, encoding="utf-8")
    except FileNotFoundError:
        raise OutputError(f"cannot write {path}: the folder does not exist") from None
    except OSError as exc:
        raise OutputError(f"cannot write {path}: {exc.strerror}") from None


@contextmanager
def _reporting_errors(ctx: typer.Context) -> Iterator[None]:
    """Print expected errors for the user and exit with code 1."""
    try:
        yield
    except typer.Exit:
        raise
    except VizreelError as exc:
        _print_vizreel_error(exc)
        raise typer.Exit(1) from None
    except Exception as exc:
        if ctx.obj:
            raise
        _stderr().print(
            f"[red]unexpected error:[/] {escape(type(exc).__name__)}: {escape(str(exc))}\n"
            "Run again with --debug to see the full traceback."
        )
        raise typer.Exit(1) from None


def _print_input_error(error: InputFileError) -> None:
    console = _stderr()
    console.print(f"[red]{escape(str(error))}[/]")
    for issue in error.issues:
        if issue.location:
            console.print(f"  [bold]{escape(issue.location)}[/]: {escape(issue.message)}")
        else:
            console.print(f"  {escape(issue.message)}")


def _stdout() -> Console:
    return Console(highlight=False, soft_wrap=True)


def _stderr() -> Console:
    return Console(stderr=True, highlight=False, soft_wrap=True)


def _replace_unprintable_characters() -> None:
    """Keep output that the console encoding cannot show from crashing the command."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")
