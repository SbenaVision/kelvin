"""Kelvin CLI — `kelvin init` and `kelvin check`."""

from __future__ import annotations

from pathlib import Path

import typer

from kelvin.check import AbortRun, CheckError, run_check
from kelvin.event_log import EventLogger

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
    confirm: bool = typer.Option(
        False,
        "--confirm",
        help="Prompt y/n after baselines before Phase 2 perturbations run.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Skip the --confirm prompt (auto-accept). Also auto-accepts when "
        "stdin is not a TTY.",
    ),
    log_format: str = typer.Option(
        "text",
        "--log-format",
        help="Output format for progress events: 'text' (default) or 'json' "
        "(one JSON record per line with ts/level/event/fields).",
    ),
) -> None:
    """Run perturbations, score outputs, write report.json files.

    PR 2: writes `kelvin/<case>/report.json` and `kelvin/report.json` to disk.
    Pretty terminal + HTML reports land in PR 3.
    """
    cwd = Path.cwd()
    if log_format not in ("text", "json"):
        typer.echo(
            f"Error: --log-format must be 'text' or 'json', got {log_format!r}",
            err=True,
        )
        raise typer.Exit(code=1)

    # In text mode, route info events through typer.echo so CLI output
    # stays on the same channel as v0.2. In json mode, write records to
    # stdout/stderr directly.
    logger = EventLogger(
        fmt=log_format,
        text_fallback=typer.echo if log_format == "text" else None,
    )

    try:
        run_check(
            cwd,
            only=only,
            seed_override=seed,
            logger=logger,
            confirm_before_phase2=confirm,
            auto_accept=yes,
        )
    except CheckError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except AbortRun as exc:
        typer.echo(f"Aborting: {exc}", err=True)
        raise typer.Exit(code=2) from exc


if __name__ == "__main__":
    app()
