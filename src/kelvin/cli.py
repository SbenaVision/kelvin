"""Kelvin CLI — `kelvin init` and `kelvin check`."""

from __future__ import annotations

from pathlib import Path

import typer

from kelvin.check import AbortRun, CheckError, run_check

app = typer.Typer(
    help="Kelvin — an unsupervised correctness signal for RAG pipelines.",
    no_args_is_help=True,
    add_completion=False,
)


@app.command()
def init() -> None:
    """Interactive setup. Writes `kelvin.yaml` in the current directory."""
    typer.echo("kelvin init: not implemented yet (arrives in PR 2 follow-up)")
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
    """Run perturbations, score outputs, write report.json files.

    PR 2: writes `kelvin/<case>/report.json` and `kelvin/report.json` to disk.
    Pretty terminal + HTML reports land in PR 3.
    """
    cwd = Path.cwd()
    try:
        run_check(cwd, only=only, seed_override=seed, echo=typer.echo)
    except CheckError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except AbortRun as exc:
        typer.echo(f"Aborting: {exc}", err=True)
        raise typer.Exit(code=2) from exc


if __name__ == "__main__":
    app()
