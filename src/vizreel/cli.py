"""Command-line interface. Parses arguments, calls the library and prints results."""

from typing import Annotated

import typer

from vizreel import __version__

app = typer.Typer(
    name="vizreel",
    help="Animated charts for video, from a YAML file.",
    no_args_is_help=True,
    add_completion=False,
)


def _print_version(value: bool) -> None:
    if value:
        typer.echo(f"vizreel {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_print_version,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """Animated charts for video, from a YAML file."""
