"""`kelvin check` orchestrator.

Sequence:
  1. Load config + parse cases (all cases, for the peer pool).
  2. Phase 1 — baselines.
       For every case: write the baseline input, invoke the pipeline, capture
       result. If a baseline returns a parseable JSON object but the declared
       decision field is absent, abort the whole run (fail fast — decision
       field config is wrong). Any other baseline failure is a hard stop for
       that case: skip it and continue with remaining baselines. On the first
       successful baseline, validate that the decision value is a supported
       scalar; if not, abort.
  3. Phase 2 — perturbations.
       For every case whose baseline succeeded, generate reorder / pad / swap
       perturbations (with capping + warnings), write each input to disk,
       invoke the pipeline, score distance against the baseline.
  4. Aggregate into `RunScores`, write `report.json` per case and cross-case.

PR 2 stops here — no terminal or HTML report. Inspect the raw JSON files
under `./kelvin/` to review signal.
"""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any

from kelvin import fs
from kelvin.config import CONFIG_FILENAME, KelvinConfig
from kelvin.event_log import EventLogger, text_logger_for
from kelvin.messages import (
    CHECK_ALL_BASELINES_FAILED,
    CHECK_NO_CASES,
    CHECK_UNKNOWN_CASE,
    CHECK_USER_ABORTED,
    CONFIG_UNKNOWN_GOVERNING_TYPE,
    FormattedMessage,
    catalog,
)
from kelvin.parser import load_cases, render_case
from kelvin.perturbations import PerturbationGenerator
from kelvin.perturbations.pad import PadContentGenerator
from kelvin.perturbations.pad_length import PadLengthGenerator
from kelvin.perturbations.reorder import ReorderGenerator
from kelvin.perturbations.swap import SwapGenerator
from kelvin.reporters.terminal import render as render_terminal
from kelvin.runner import invoke
from kelvin.scorer import (
    DecisionFieldTypeError,
    DefaultScorer,
    Scorer,
    aggregate,
    validate_scalar,
)
from kelvin.types import (
    Case,
    CaseScores,
    InvocationResult,
    PerturbationBatch,
    RunScores,
    ScoredPerturbation,
)


class CheckError(Exception):
    """Raised for run-aborting errors (bad config, missing cases, etc.).

    Accepts either a `FormattedMessage` (preferred — carries the full
    what/why/how-to-fix triple) or a plain string for back-compat.
    """

    def __init__(self, message_or_text: Any, /) -> None:
        if isinstance(message_or_text, FormattedMessage):
            self.formatted_message: FormattedMessage | None = message_or_text
            super().__init__(message_or_text.as_text())
        else:
            self.formatted_message = None
            super().__init__(str(message_or_text))


class AbortRun(Exception):
    """Raised mid-run to abort — bad decision field, non-scalar, etc.

    Accepts either a `FormattedMessage` (preferred) or a plain string.
    """

    def __init__(self, message_or_text: Any, /) -> None:
        if isinstance(message_or_text, FormattedMessage):
            self.formatted_message: FormattedMessage | None = message_or_text
            super().__init__(message_or_text.as_text())
        else:
            self.formatted_message = None
            super().__init__(str(message_or_text))


DEFAULT_GENERATORS: tuple[PerturbationGenerator, ...] = (
    ReorderGenerator(),
    PadLengthGenerator(),
    PadContentGenerator(),
    SwapGenerator(),
)


# Expected perturbation counts per generator, used for the cost preamble.
# These match each generator's TARGET_COUNT and are an estimate — actual
# counts may be lower when caps or peer-pool shortages apply.
_EST_PER_CASE = {
    "reorder": 3,
    "pad_length": 3,
    "pad_content": 3,
    "swap_per_type": 3,
}


def run_check(
    cwd: Path,
    *,
    only: str | None = None,
    seed_override: int | None = None,
    scorer: Scorer | None = None,
    generators: tuple[PerturbationGenerator, ...] = DEFAULT_GENERATORS,
    echo: Any = print,
    logger: EventLogger | None = None,
    confirm_before_phase2: bool = False,
    auto_accept: bool = False,
) -> RunScores:
    """Run `kelvin check` end-to-end.

    `echo` is pluggable so callers (tests, the CLI) control output; it receives
    one string per call.

    Raises:
        CheckError  — config / case-discovery problems before any pipeline run.
        AbortRun    — bad decision field on the first successful baseline.
    """
    _start = time.monotonic()
    # If caller didn't supply a structured logger, wrap the `echo` callable
    # so legacy consumers (tests using list.append, typer.echo) keep working
    # without change.
    if logger is None:
        logger = text_logger_for(echo)
    cfg = _load_config(cwd)
    effective_seed = seed_override if seed_override is not None else cfg.seed

    cases_dir = cfg.cases if cfg.cases.is_absolute() else (cwd / cfg.cases)
    cache_dir = _resolve_cache_dir(cfg, cwd)
    all_cases = load_cases(cases_dir)
    if not all_cases:
        raise CheckError(catalog(CHECK_NO_CASES, cases_dir=cases_dir))

    logger.info(
        "config_loaded",
        cases_dir=str(cases_dir),
        n_cases=len(all_cases),
        decision_field=cfg.decision_field,
        governing_types=list(cfg.governing_types),
        seed=effective_seed,
    )

    # Footgun: declared governing_types must match at least one discovered unit
    # type, otherwise swap generates nothing silently. Also surface normalized
    # type discovery so users catch `## Gate Rule` -> gate_rule surprises.
    _validate_governing_types(all_cases, cfg.governing_types)
    _echo_discovered_types(all_cases, logger)

    cases_to_run = _filter_cases(all_cases, only=only)

    run_warnings: list[str] = []
    single_case_run = len(all_cases) == 1
    if single_case_run:
        msg = (
            "Only one case in the run: pad_content and swap will be skipped "
            "(no peers). reorder and pad_length still run."
        )
        run_warnings.append(msg)
        logger.info("single_case_run", text=f"\u26a0  {msg}", n_cases=1)

    active_scorer: Scorer = scorer or DefaultScorer()

    # Phase 1 — baselines
    phase1_start = time.monotonic()
    case_scores, _decision_validated = _run_baselines(
        cases_to_run=cases_to_run,
        cfg=cfg,
        cwd=cwd,
        logger=logger,
        cache_dir=cache_dir,
    )
    phase1_elapsed_s = time.monotonic() - phase1_start
    if cache_dir is not None:
        logger.info("cache_path", text=f"Cache: {cache_dir}", cache_dir=str(cache_dir))

    # Cost preamble: estimate perturbation count and wall-time based on baseline
    # elapsed so users can Ctrl-C before burning compute on expensive pipelines.
    forecast = _echo_cost_preamble(
        case_scores, cfg.governing_types, single_case_run,
        phase1_elapsed_s=phase1_elapsed_s, logger=logger,
    )

    if not any(c.baseline_ok for c in case_scores):
        # Every case's baseline failed. Write what we have and bail.
        _write_per_case_reports(case_scores, cwd, cfg)
        run_scores = aggregate(
            case_scores,
            seed=effective_seed,
            governing_types=cfg.governing_types,
            run_warnings=run_warnings,
            run_caps=[],
            single_case_run=single_case_run,
        )
        _write_run_report(run_scores, cwd, cfg, only=only)
        raise AbortRun(catalog(CHECK_ALL_BASELINES_FAILED))

    # Forecast prompt: opt-in via `confirm_before_phase2`. When the prompt
    # is active, --yes and non-TTY stdin both bypass (CI-safe).
    if confirm_before_phase2 and forecast is not None:
        if not _accept_forecast(auto_accept=auto_accept):
            _write_per_case_reports(case_scores, cwd, cfg)
            run_scores = aggregate(
                case_scores,
                seed=effective_seed,
                governing_types=cfg.governing_types,
                run_warnings=run_warnings,
                run_caps=[],
                single_case_run=single_case_run,
            )
            _write_run_report(run_scores, cwd, cfg, only=only)
            raise AbortRun(catalog(CHECK_USER_ABORTED))

    # Phase 2 — perturbations for cases with successful baselines
    for case, scores in zip(cases_to_run, case_scores, strict=True):
        if not scores.baseline_ok:
            continue
        _run_perturbations_for_case(
            case=case,
            peer_cases=all_cases,
            scores=scores,
            cfg=cfg,
            cwd=cwd,
            seed=effective_seed,
            generators=generators,
            scorer=active_scorer,
            logger=logger,
            cache_dir=cache_dir,
        )

    # Write per-case reports, aggregate, write run report.
    _write_per_case_reports(case_scores, cwd, cfg)
    run_scores = aggregate(
        case_scores,
        seed=effective_seed,
        governing_types=cfg.governing_types,
        run_warnings=run_warnings,
        run_caps=[],
        single_case_run=single_case_run,
    )
    _write_run_report(run_scores, cwd, cfg, only=only)
    render_terminal(
        run_scores,
        elapsed_s=time.monotonic() - _start,
        decision_field=cfg.decision_field,
    )
    logger.info(
        "run_completed",
        elapsed_s=time.monotonic() - _start,
        n_cases=len(run_scores.cases),
        invariance=run_scores.invariance,
        sensitivity=run_scores.sensitivity,
        kelvin_score=run_scores.kelvin_score,
        invariance_sample=run_scores.invariance_sample,
        sensitivity_sample=run_scores.sensitivity_sample,
    )
    return run_scores


# ─── Phase helpers ──────────────────────────────────────────────────────────


def _load_config(cwd: Path) -> KelvinConfig:
    return KelvinConfig.load(cwd / CONFIG_FILENAME)


def _resolve_cache_dir(cfg: KelvinConfig, cwd: Path) -> Path | None:
    """Absolute path of the opt-in invocation cache, or None if disabled."""
    if cfg.cache_dir is None:
        return None
    return cfg.cache_dir if cfg.cache_dir.is_absolute() else (cwd / cfg.cache_dir)


def _filter_cases(all_cases: list[Case], *, only: str | None) -> list[Case]:
    if only is None:
        return list(all_cases)
    selected = [c for c in all_cases if c.name == only]
    if not selected:
        names = [c.name for c in all_cases]
        raise CheckError(catalog(CHECK_UNKNOWN_CASE, only=only, available=names))
    return selected


def _run_baselines(
    *,
    cases_to_run: list[Case],
    cfg: KelvinConfig,
    cwd: Path,
    logger: EventLogger,
    cache_dir: Path | None = None,
) -> tuple[list[CaseScores], bool]:
    case_scores: list[CaseScores] = []
    decision_validated = False

    for case in cases_to_run:
        bdir = fs.ensure(fs.baseline_dir(cwd, case.name))
        input_path = bdir / "input.md"
        output_path = bdir / "output.json"
        input_path.write_text(
            render_case(case.preamble, case.units), encoding="utf-8"
        )

        result = invoke(
            cfg.run,
            input_path,
            output_path,
            cfg.decision_field,
            timeout_s=cfg.timeout_s,
            cache_dir=cache_dir,
            retry_policy=cfg.retry_policy,
            logger=logger,
        )

        if not result.ok:
            # If the pipeline produced a valid JSON object that simply doesn't
            # have the declared decision field, that's a run-level config bug
            # and we abort rather than silently skipping case after case.
            if (
                result.parsed_output is not None
                and cfg.decision_field not in result.parsed_output
            ):
                raise AbortRun(result.error or "missing decision field")

            logger.info(
                "baseline_completed",
                text=f"Baseline failed for {case.name}: {result.error}",
                case=case.name,
                ok=False,
                error=result.error,
            )
            case_scores.append(
                CaseScores(
                    case_name=case.name,
                    baseline_ok=False,
                    baseline_error=result.error,
                )
            )
            continue

        if not decision_validated:
            try:
                validate_scalar(result.decision_value, cfg.decision_field)
            except DecisionFieldTypeError as exc:
                raise AbortRun(str(exc)) from exc
            decision_validated = True

        case_scores.append(
            CaseScores(
                case_name=case.name,
                baseline_ok=True,
                baseline_decision=result.decision_value,
            )
        )
        logger.info(
            "baseline_completed",
            text=(
                f"Baseline ok for {case.name}: "
                f"{cfg.decision_field}={result.decision_value!r}"
            ),
            case=case.name,
            ok=True,
            decision_field=cfg.decision_field,
            decision_value=result.decision_value,
        )

    return case_scores, decision_validated


def _run_perturbations_for_case(
    *,
    case: Case,
    peer_cases: list[Case],
    scores: CaseScores,
    cfg: KelvinConfig,
    cwd: Path,
    seed: int,
    generators: tuple[PerturbationGenerator, ...],
    scorer: Scorer,
    logger: EventLogger,
    cache_dir: Path | None = None,
) -> None:
    work_items: list[tuple[Any, Path, Path]] = []
    for gen in generators:
        batch: PerturbationBatch = gen.generate(
            case=case,
            peer_cases=peer_cases,
            seed=seed,
            governing_types=cfg.governing_types,
        )
        scores.warnings.extend(batch.warnings)
        scores.caps.extend(batch.caps)

        for perturbation in batch.perturbations:
            vdir = fs.ensure(fs.variant_dir(cwd, case.name, perturbation.variant_id))
            input_path = vdir / "input.md"
            output_path = vdir / "output.json"
            input_path.write_text(perturbation.rendered_markdown, encoding="utf-8")
            work_items.append((perturbation, input_path, output_path))

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_map = {
            executor.submit(
                invoke,
                cfg.run,
                inp,
                outp,
                cfg.decision_field,
                timeout_s=cfg.timeout_s,
                cache_dir=cache_dir,
                retry_policy=cfg.retry_policy,
                logger=logger,
            ): pert
            for pert, inp, outp in work_items
        }

        for future in as_completed(future_map):
            perturbation = future_map[future]
            result = future.result()
            distance = _maybe_distance(result, scores.baseline_decision, scorer)

            sp = ScoredPerturbation(
                perturbation=perturbation,
                invocation=result,
                distance=distance,
            )
            _dispatch_scored(sp, scores)

            if not result.ok:
                logger.info(
                    "perturbation_completed",
                    text=(
                        f"  {case.name}/{perturbation.variant_id}: "
                        f"perturbation failed ({result.error})"
                    ),
                    case=case.name,
                    variant_id=perturbation.variant_id,
                    kind=perturbation.kind,
                    ok=False,
                    error=result.error,
                )
            else:
                logger.info(
                    "perturbation_completed",
                    text=(
                        f"  {case.name}/{perturbation.variant_id}: "
                        f"{cfg.decision_field}={result.decision_value!r} "
                        f"distance={distance:.3f}"
                    ),
                    case=case.name,
                    variant_id=perturbation.variant_id,
                    kind=perturbation.kind,
                    ok=True,
                    decision_field=cfg.decision_field,
                    decision_value=result.decision_value,
                    distance=distance,
                )


def _maybe_distance(
    result: InvocationResult,
    baseline_decision: Any,
    scorer: Scorer,
) -> float | None:
    if not result.ok:
        return None
    try:
        return scorer.distance(baseline_decision, result.decision_value)
    except DecisionFieldTypeError:
        # The baseline already passed `validate_scalar`. A perturbation decision
        # being non-scalar is a pipeline bug; surface as a failed distance so
        # the user can investigate, but don't crash the run.
        return None


def _dispatch_scored(sp: ScoredPerturbation, scores: CaseScores) -> None:
    kind = sp.perturbation.kind
    if kind == "reorder":
        scores.reorder.append(sp)
    elif kind == "pad_length":
        scores.pad_length.append(sp)
    elif kind == "pad_content":
        scores.pad_content.append(sp)
    elif kind == "swap":
        gtype = sp.perturbation.notes.get("governing_type", "unknown")
        scores.swaps_by_type.setdefault(gtype, []).append(sp)


# ─── Footgun helpers (Tier 2) ───────────────────────────────────────────────


def _validate_governing_types(all_cases: list[Case], governing_types: list[str]) -> None:
    """Raise `CheckError` if a declared governing_type matches zero discovered units.

    Without this, `swap` silently generates nothing for the offending type and
    the user has no idea their config is wrong. Common cause: the user wrote
    `Gate Rule` in their yaml without normalizing, or declared a type that
    doesn't appear in any case file.
    """
    if not governing_types:
        return
    discovered = {u.type for c in all_cases for u in c.units}
    unknown = [t for t in governing_types if t not in discovered]
    if unknown:
        raise CheckError(
            catalog(
                CONFIG_UNKNOWN_GOVERNING_TYPE,
                unknown=unknown,
                discovered=sorted(discovered),
            )
        )


def _echo_discovered_types(all_cases: list[Case], logger: EventLogger) -> None:
    """One-line summary of normalized unit types across all cases.

    Makes normalization outcomes visible so users spot surprises like
    `## Gate Rule` -> `gate_rule` before the run proceeds.
    """
    counts: dict[str, int] = {}
    for c in all_cases:
        for u in c.units:
            counts[u.type] = counts.get(u.type, 0) + 1
    if not counts:
        return
    summary = ", ".join(f"{t}\u00d7{n}" for t, n in sorted(counts.items()))
    logger.info(
        "types_discovered",
        text=f"Discovered types across {len(all_cases)} case(s): {summary}",
        n_cases=len(all_cases),
        counts=counts,
    )


def _echo_cost_preamble(
    case_scores: list[CaseScores],
    governing_types: list[str],
    single_case_run: bool,
    *,
    phase1_elapsed_s: float,
    logger: EventLogger,
) -> dict[str, Any] | None:
    """Log estimated perturbation count and wall-time before Phase 2 fires.

    Returns the forecast fields so the caller can offer an interactive
    confirmation prompt (when `confirm_before_phase2` is set).
    """
    n_ok = sum(1 for c in case_scores if c.baseline_ok)
    if n_ok == 0:
        return None

    per_case = _EST_PER_CASE["reorder"] + _EST_PER_CASE["pad_length"]
    if not single_case_run:
        per_case += _EST_PER_CASE["pad_content"]
        per_case += _EST_PER_CASE["swap_per_type"] * len(governing_types)
    est_total = per_case * n_ok

    avg_baseline_s = phase1_elapsed_s / n_ok if n_ok else 0.0
    est_wall_s = est_total * avg_baseline_s

    wall_txt = (
        f"~{est_wall_s / 60:.1f} min" if est_wall_s >= 60 else f"~{est_wall_s:.0f} s"
    )

    text = (
        f"Running ~{est_total} perturbations across {n_ok} case(s) "
        f"(est. {wall_txt} at baseline speed). Ctrl-C to abort."
    )
    logger.info(
        "cost_preamble",
        text=text,
        est_total=est_total,
        est_wall_s=est_wall_s,
        n_cases=n_ok,
        governing_types=list(governing_types),
        single_case_run=single_case_run,
    )
    return {
        "est_total": est_total,
        "est_wall_s": est_wall_s,
        "n_cases": n_ok,
    }


def _accept_forecast(*, auto_accept: bool, input_fn: Any = input, isatty: Any = None) -> bool:
    """Return True if the user accepts the forecast (or bypasses the prompt).

    Bypass conditions (either independently skips the prompt):
      - `auto_accept` (the --yes flag)
      - stdin is not a TTY (CI safety — no interactive input available)

    The prompt is written to stdout via `input_fn` so terminal users can
    respond. Accepts "y"/"yes" (case-insensitive); anything else rejects.
    """
    if auto_accept:
        return True
    if isatty is None:
        isatty = sys.stdin.isatty
    if not isatty():
        return True
    try:
        response = input_fn("Proceed? [y/N] ").strip().lower()
    except EOFError:
        # Stdin closed mid-prompt — treat as rejection to avoid accidental
        # continuation on broken pipes.
        return False
    return response in ("y", "yes")


# ─── On-disk serialization ──────────────────────────────────────────────────


def _write_per_case_reports(
    case_scores: list[CaseScores], cwd: Path, cfg: KelvinConfig
) -> None:
    for scores in case_scores:
        cdir = fs.ensure(fs.case_dir(cwd, scores.case_name))
        (cdir / "report.json").write_text(
            json.dumps(
                _case_report_dict(scores, decision_field=cfg.decision_field),
                indent=2,
                default=_json_default,
            ),
            encoding="utf-8",
        )


def _case_report_dict(scores: CaseScores, *, decision_field: str) -> dict:
    return {
        "schema_version": 1,
        "case": scores.case_name,
        "baseline": {
            "ok": scores.baseline_ok,
            "error": scores.baseline_error,
            "decision_value": scores.baseline_decision,
            "decision_field": decision_field,
        },
        "perturbations": [
            _scored_dict(sp)
            for sp in (*scores.reorder, *scores.pad_length, *scores.pad_content)
        ]
        + [
            _scored_dict(sp)
            for swaps in scores.swaps_by_type.values()
            for sp in swaps
        ],
        "scores": {
            "invariance": _one_minus_mean(scores.invariance_distances),
            "invariance_sample": len(scores.invariance_distances),
            "sensitivity": _mean_or_none(scores.swap_distances),
            "sensitivity_sample": len(scores.swap_distances),
            "sensitivity_by_type": {
                gtype: {
                    "mean": _mean_or_none(
                        [sp.distance for sp in swaps if sp.distance is not None]
                    ),
                    "sample": sum(1 for sp in swaps if sp.distance is not None),
                }
                for gtype, swaps in scores.swaps_by_type.items()
            },
        },
        "warnings": list(scores.warnings),
        "caps": list(scores.caps),
    }


def _scored_dict(sp: ScoredPerturbation) -> dict:
    return {
        "variant_id": sp.perturbation.variant_id,
        "kind": sp.perturbation.kind,
        "notes": sp.perturbation.notes,
        "invocation": {
            "ok": sp.invocation.ok,
            "error": sp.invocation.error,
            "decision_value": sp.invocation.decision_value,
            "stderr_tail": sp.invocation.stderr_tail,
        },
        "distance": sp.distance,
        "input_path": str(sp.invocation.input_path),
        "output_path": str(sp.invocation.output_path),
    }


def _write_run_report(
    run_scores: RunScores, cwd: Path, cfg: KelvinConfig, *, only: str | None
) -> None:
    rdir = fs.ensure(fs.run_root(cwd))
    payload = {
        "schema_version": 1,
        "seed": run_scores.seed,
        "only": only,
        "decision_field": cfg.decision_field,
        "governing_types": list(run_scores.governing_types),
        "cases": {
            "run": [c.case_name for c in run_scores.cases],
            "baseline_ok": [c.case_name for c in run_scores.cases if c.baseline_ok],
            "baseline_failed": [
                {"case": c.case_name, "error": c.baseline_error}
                for c in run_scores.cases
                if not c.baseline_ok
            ],
        },
        "invariance": run_scores.invariance,
        "invariance_sample": run_scores.invariance_sample,
        "sensitivity": run_scores.sensitivity,
        "sensitivity_sample": run_scores.sensitivity_sample,
        "kelvin_score": run_scores.kelvin_score,
        "single_case_run": run_scores.single_case_run,
        "sensitivity_by_type": {
            gtype: {"mean": mean_val, "sample": sample}
            for gtype, (mean_val, sample) in run_scores.sensitivity_by_type.items()
        },
        "warnings": list(run_scores.warnings),
        "caps": list(run_scores.caps),
    }
    (rdir / "report.json").write_text(
        json.dumps(payload, indent=2, default=_json_default),
        encoding="utf-8",
    )


def _one_minus_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return 1.0 - (sum(values) / len(values))


def _mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Path):
        return str(obj)
    try:
        return asdict(obj)
    except TypeError:
        pass
    return str(obj)
