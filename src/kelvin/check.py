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
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from kelvin import fs
from kelvin.config import CONFIG_FILENAME, KelvinConfig
from kelvin.parser import load_cases, render_case
from kelvin.perturbations import PerturbationGenerator
from kelvin.perturbations.pad import PadGenerator
from kelvin.perturbations.reorder import ReorderGenerator
from kelvin.perturbations.swap import SwapGenerator
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    """Raised for run-aborting errors (bad config, missing cases, etc.)."""


class AbortRun(Exception):
    """Raised mid-run to abort — bad decision field, non-scalar, etc."""


DEFAULT_GENERATORS: tuple[PerturbationGenerator, ...] = (
    ReorderGenerator(),
    PadGenerator(),
    SwapGenerator(),
)


def run_check(
    cwd: Path,
    *,
    only: str | None = None,
    seed_override: int | None = None,
    scorer: Scorer | None = None,
    generators: tuple[PerturbationGenerator, ...] = DEFAULT_GENERATORS,
    echo: Any = print,
) -> RunScores:
    """Run `kelvin check` end-to-end.

    `echo` is pluggable so callers (tests, the CLI) control output; it receives
    one string per call.

    Raises:
        CheckError  — config / case-discovery problems before any pipeline run.
        AbortRun    — bad decision field on the first successful baseline.
    """
    _start = time.monotonic()
    cfg = _load_config(cwd)
    effective_seed = seed_override if seed_override is not None else cfg.seed

    cases_dir = cfg.cases if cfg.cases.is_absolute() else (cwd / cfg.cases)
    all_cases = load_cases(cases_dir)
    if not all_cases:
        raise CheckError(
            f"No cases found in {cases_dir}. Add one or more `*.md` files."
        )

    cases_to_run = _filter_cases(all_cases, only=only)

    run_warnings: list[str] = []
    if len(all_cases) == 1:
        run_warnings.append(
            "Only one case in the run: pad and swap will be skipped (no peers)."
        )

    active_scorer: Scorer = scorer or DefaultScorer()

    # Phase 1 — baselines
    case_scores, _decision_validated = _run_baselines(
        cases_to_run=cases_to_run,
        cfg=cfg,
        cwd=cwd,
        echo=echo,
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
        )
        _write_run_report(run_scores, cwd, cfg, only=only)
        raise AbortRun(
            "All baselines failed. See kelvin/<case>/report.json for details."
        )

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
            echo=echo,
        )

    # Write per-case reports, aggregate, write run report.
    _write_per_case_reports(case_scores, cwd, cfg)
    run_scores = aggregate(
        case_scores,
        seed=effective_seed,
        governing_types=cfg.governing_types,
        run_warnings=run_warnings,
        run_caps=[],
    )
    _write_run_report(run_scores, cwd, cfg, only=only)
    render_terminal(
        run_scores,
        elapsed_s=time.monotonic() - _start,
        decision_field=cfg.decision_field,
    )
    return run_scores


# ─── Phase helpers ──────────────────────────────────────────────────────────


def _load_config(cwd: Path) -> KelvinConfig:
    return KelvinConfig.load(cwd / CONFIG_FILENAME)


def _filter_cases(all_cases: list[Case], *, only: str | None) -> list[Case]:
    if only is None:
        return list(all_cases)
    selected = [c for c in all_cases if c.name == only]
    if not selected:
        names = [c.name for c in all_cases]
        raise CheckError(
            f"--only '{only}': no such case. Available: {names}"
        )
    return selected


def _run_baselines(
    *,
    cases_to_run: list[Case],
    cfg: KelvinConfig,
    cwd: Path,
    echo: Any,
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

        result = invoke(cfg.run, input_path, output_path, cfg.decision_field, timeout_s=60)

        if not result.ok:
            # If the pipeline produced a valid JSON object that simply doesn't
            # have the declared decision field, that's a run-level config bug
            # and we abort rather than silently skipping case after case.
            if (
                result.parsed_output is not None
                and cfg.decision_field not in result.parsed_output
            ):
                raise AbortRun(result.error or "missing decision field")

            echo(f"Baseline failed for {case.name}: {result.error}")
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
        echo(f"Baseline ok for {case.name}: {cfg.decision_field}={result.decision_value!r}")

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
    echo: Any,
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
                invoke, cfg.run, inp, outp, cfg.decision_field, timeout_s=60
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
                echo(
                    f"  {case.name}/{perturbation.variant_id}: "
                    f"perturbation failed ({result.error})"
                )
            else:
                echo(
                    f"  {case.name}/{perturbation.variant_id}: "
                    f"{cfg.decision_field}={result.decision_value!r} "
                    f"distance={distance:.3f}"
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
    elif kind == "pad":
        scores.pad.append(sp)
    elif kind == "swap":
        gtype = sp.perturbation.notes.get("governing_type", "unknown")
        scores.swaps_by_type.setdefault(gtype, []).append(sp)


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
        "case": scores.case_name,
        "baseline": {
            "ok": scores.baseline_ok,
            "error": scores.baseline_error,
            "decision_value": scores.baseline_decision,
            "decision_field": decision_field,
        },
        "perturbations": [
            _scored_dict(sp) for sp in (*scores.reorder, *scores.pad)
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
