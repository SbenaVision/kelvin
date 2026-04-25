"""Kelvin CLI — `kelvin init` and `kelvin check`.

v0.4 surface
------------
The default `kelvin check` output is the practitioner reporter:

    - Category verdict (Production-ready / Needs work / Not production-ready
      / Partially measured) — never a 1–10 number by default.
    - Per-axis sub-scores (drift / sensitivity / equivalence).
    - Top-3 findings with recommendations.
    - "Top fix" line.

Switching modes:

    --verbose           Add the numeric 1–10 score, raw metrics, and the
                        per-family invariance breakdown to the practitioner
                        output. The numeric is banner-flagged when any
                        standard pillar is silent (per docs/PHASE_2_SCOPE.md).

    --research          Preserve the v0.3.0 terminal box output BYTE-FOR-BYTE
                        (AC6) for downstream tooling that pinned the v0.3
                        format.

    --report-format     practitioner (default) | json | markdown
                        Selects the writer. JSON emits a versioned, structured
                        document; markdown is suitable for PR descriptions
                        and status pages.

    --version           Print "kelvin {version}" and exit.

`--research` and `--report-format=json|markdown` are mutually exclusive
with each other; `--verbose` composes with everything.
"""

from __future__ import annotations

from pathlib import Path

import typer

from kelvin import __version__
from kelvin.check import AbortRun, CheckError, run_check
from kelvin.event_log import EventLogger
from kelvin.findings import compute_findings
from kelvin.recommendations import compute_recommendations, top_fix
from kelvin.reporters import json_reporter, markdown, practitioner
from kelvin.score import compute_maturity

app = typer.Typer(
    help="Kelvin — practitioner-facing reliability check for AI/RAG pipelines.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kelvin {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print the kelvin version and exit.",
    ),
) -> None:
    """Top-level callback for the `--version` flag."""
    return None


@app.command()
def init() -> None:
    """Interactive setup. Writes `kelvin.yaml` in the current directory."""
    typer.echo("kelvin init: not implemented yet (arrives in PR 2 follow-up)")
    raise typer.Exit(code=1)


# Allowed values for --report-format. Practitioner is the default.
_REPORT_FORMATS = ("practitioner", "json", "markdown")


def _emit_v04_report(
    run_scores,
    *,
    report_format: str,
    verbose: bool,
) -> None:
    """Compute MaturityScore + findings + recs and dispatch to the
    selected v0.4 reporter."""
    maturity = compute_maturity(run_scores)
    findings = compute_findings(maturity, run_scores)
    recs = compute_recommendations(findings)
    fix = top_fix(recs)

    if report_format == "json":
        json_reporter.render(maturity, findings, recs, fix, run_scores)
        return
    if report_format == "markdown":
        markdown.render(maturity, findings, recs, fix)
        return
    # default: practitioner
    practitioner.render(maturity, findings, recs, fix,
                        verbose=verbose, run=run_scores)


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
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Generate perturbation inputs and write reports without "
        "invoking the pipeline. No subprocesses spawn; no output JSON "
        "produced. --confirm is bypassed when --dry-run is active.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Show the numeric 1–10 maturity score, raw per-axis metrics, "
        "and the per-family invariance breakdown alongside the "
        "practitioner output. The numeric is banner-flagged when any "
        "standard pillar is silent.",
    ),
    research: bool = typer.Option(
        False,
        "--research",
        help="Preserve v0.3.0 terminal box output byte-for-byte (suppresses "
        "the v0.4 practitioner reporter). Mutually exclusive with "
        "--report-format=json|markdown.",
    ),
    report_format: str = typer.Option(
        "practitioner",
        "--report-format",
        help="Output format for the v0.4 reporter: practitioner (default), "
        "json, or markdown. Has no effect under --research.",
    ),
) -> None:
    """Run perturbations, score outputs, write report.json, render summary.

    The default summary is the v0.4 practitioner reporter
    (`docs/PHASE_2_SCOPE.md`). Use `--research` to retain the v0.3.0
    output for byte-compat tooling.
    """
    cwd = Path.cwd()
    if log_format not in ("text", "json"):
        typer.echo(
            f"Error: --log-format must be 'text' or 'json', got {log_format!r}",
            err=True,
        )
        raise typer.Exit(code=1)

    if report_format not in _REPORT_FORMATS:
        typer.echo(
            f"Error: --report-format must be one of {list(_REPORT_FORMATS)}, "
            f"got {report_format!r}",
            err=True,
        )
        raise typer.Exit(code=1)

    if research and report_format != "practitioner":
        typer.echo(
            "Error: --research is mutually exclusive with "
            "--report-format=json|markdown.",
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
        run_scores = run_check(
            cwd,
            only=only,
            seed_override=seed,
            logger=logger,
            confirm_before_phase2=confirm,
            auto_accept=yes,
            dry_run=dry_run,
            # AC6: --research preserves v0.3.0 terminal output;
            # otherwise we suppress it and emit the v0.4 reporter
            # ourselves.
            render_v03_terminal=research,
        )
    except CheckError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except AbortRun as exc:
        typer.echo(f"Aborting: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    # In dry-run, the run produces no scoring data — skip the v0.4 reporter.
    if dry_run:
        return

    if not research:
        _emit_v04_report(
            run_scores,
            report_format=report_format,
            verbose=verbose,
        )


if __name__ == "__main__":
    app()
