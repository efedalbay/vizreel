"""Command-line interface. Parses arguments, calls the library and prints results."""

import io
import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape

from vizreel import __version__
from vizreel.errors import InputFileError, OutputError, VizreelError
from vizreel.spec.loader import load_spec, spec_json_schema

app = typer.Typer(
    name="vizreel",
    help="Animated charts for video, from a YAML file.",
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
    """Animated charts for video, from a YAML file."""
    _replace_unprintable_characters()
    ctx.obj = debug


@app.command()
def validate(
    ctx: typer.Context,
    spec: Annotated[Path, typer.Argument(help="Spec file to check.", show_default=False)],
) -> None:
    """Check a spec file and list every error."""
    with _reporting_errors(ctx):
        loaded = load_spec(spec)
    count = len(loaded.charts)
    noun = "chart" if count == 1 else "charts"
    _stdout().print(f"[green]{escape(str(spec))} is valid[/]: {count} {noun}")


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
    text = json.dumps(spec_json_schema(), indent=2) + "\n"
    if output is None:
        sys.stdout.write(text)
        return
    with _reporting_errors(ctx):
        _write_text(output, text)
    _stdout().print(f"Wrote JSON Schema to {escape(str(output))}")


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
    except InputFileError as exc:
        _print_input_error(exc)
        raise typer.Exit(1) from None
    except VizreelError as exc:
        _stderr().print(f"[red]error:[/] {escape(str(exc))}")
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
