"""Kelvin CLI — `kelvin init` and `kelvin check`."""

from __future__ import annotations

import typer

app = typer.Typer(
    help="Kelvin — an unsupervised correctness signal for RAG pipelines.",
    no_args_is_help=True,
    add_completion=False,
)


@app.command()
def init() -> None:
    """Interactive setup. Writes `kelvin.yaml` in the current directory."""
    typer.echo("kelvin init: not implemented yet (arrives in PR 2)")
    raise typer.Exit(code=1)


@app.command()
def check(
    only: str | None = typer.Option(
        None,
        "--only",
        help="Run on a single case (by filename stem).",
    ),
    seed: int | None = typer.Option(
        None,
        "--seed",
        help="Override the seed from kelvin.yaml.",
    ),
) -> None:
    """Run perturbations, score outputs, write reports."""
    typer.echo("kelvin check: not implemented yet (arrives in PR 2)")
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
