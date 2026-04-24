"""Distance function and cross-case aggregation.

`Scorer` is a Protocol so a v2 semantic scorer can drop in without touching
the runner or the check orchestrator. `DefaultScorer` implements the v1 spec:

    enum / string  →  0 if equal else 1   (exact match — case- and
                                            whitespace-sensitive)
    numeric        →  min(1, |a-b| / max(|a|, |b|, 1))
    bool / None    →  0 if equal else 1   (falls under exact-match branch)
    list / dict    →  raises `DecisionFieldTypeError`
"""

from __future__ import annotations

from statistics import mean
from typing import Any, Protocol

from kelvin.messages import (
    SCORER_NON_SCALAR_DECISION,
    SCORER_NON_SCALAR_DECISION_FIELD,
    FormattedMessage,
    catalog,
)
from kelvin.types import CaseScores, RunScores


class DecisionFieldTypeError(ValueError):
    """Raised when the decision field value is not a supported scalar.

    Accepts either a `FormattedMessage` (preferred) or a plain string.
    """

    def __init__(self, message_or_text: Any, /) -> None:
        if isinstance(message_or_text, FormattedMessage):
            self.formatted_message: FormattedMessage | None = message_or_text
            super().__init__(message_or_text.as_text())
        else:
            self.formatted_message = None
            super().__init__(str(message_or_text))


class Scorer(Protocol):
    """Pluggable distance function on the declared decision field."""

    def distance(self, baseline: Any, perturbed: Any) -> float: ...


class DefaultScorer:
    """Spec-faithful v1 scorer."""

    def distance(self, baseline: Any, perturbed: Any) -> float:
        for v in (baseline, perturbed):
            if isinstance(v, (list, dict)):
                raise DecisionFieldTypeError(
                    catalog(
                        SCORER_NON_SCALAR_DECISION,
                        actual_type=type(v).__name__,
                    )
                )

        a_numeric = _is_numeric(baseline)
        b_numeric = _is_numeric(perturbed)
        if a_numeric and b_numeric:
            a, b = float(baseline), float(perturbed)
            denom = max(abs(a), abs(b), 1.0)
            return min(1.0, abs(a - b) / denom)

        # Everything else (str, bool, None, or mismatched types): exact equality.
        return 0.0 if baseline == perturbed else 1.0


def _is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def sigma_c(decisions: list[Any], scorer: Scorer) -> float | None:
    """Per-case stochasticity: mean pairwise distance across replay decisions.

    Returns `None` if fewer than 2 decisions are available (no pair to
    compute). Uses the given scorer's `distance` for commensurability
    with invariance / sensitivity — σ_c is measured on the same scale
    as Inv_raw and Sens_raw.
    """
    if len(decisions) < 2:
        return None
    pairs: list[float] = []
    for i in range(len(decisions)):
        for j in range(i + 1, len(decisions)):
            try:
                pairs.append(scorer.distance(decisions[i], decisions[j]))
            except DecisionFieldTypeError:
                # Non-scalar replay decision is a pipeline bug. Drop the
                # pair; aggregation handles missing data via None.
                continue
    if not pairs:
        return None
    return mean(pairs)


def calibrate(
    *,
    invariance_raw: float | None,
    sensitivity_raw: float | None,
    eta: float | None,
) -> tuple[float | None, float | None, float | None]:
    """Apply noise-floor calibration to invariance + sensitivity.

    Returns `(Inv_cal, Sens_cal, K_cal)`. Any component is `None` when
    inputs are missing or when `eta >= 1 - invariance_raw` — the
    stochasticity floor exceeds the observed invariance signal, so
    calibration would divide by a non-positive denominator and the
    signal is "unmeasurable through noise."

    Formula:
        Inv_cal  = max(0, (Inv_raw  - η) / (1 - η))
        Sens_cal = max(0, (Sens_raw - η) / (1 - η))
        K_cal    = (1 - Inv_cal) + (1 - Sens_cal)

    Degenerate preservation: a pipeline with η = 0 gets K_cal == K_raw
    exactly. The constant pipeline's K = 1.0 is preserved under
    calibration — AC-1.1 gate.
    """
    if eta is None or invariance_raw is None or sensitivity_raw is None:
        return (None, None, None)
    if eta <= 0:
        return (
            invariance_raw,
            sensitivity_raw,
            (1.0 - invariance_raw) + (1.0 - sensitivity_raw),
        )
    if eta >= 1.0 - invariance_raw:
        return (None, None, None)
    denom = 1.0 - eta
    inv_cal = max(0.0, (invariance_raw - eta) / denom)
    sens_cal = max(0.0, (sensitivity_raw - eta) / denom)
    return (inv_cal, sens_cal, (1.0 - inv_cal) + (1.0 - sens_cal))


def validate_scalar(value: Any, field_name: str) -> None:
    """Raise if the value isn't one of Kelvin's supported scalar types.

    Used in the first-baseline preflight to fail fast on non-scalar decision
    fields — before we burn compute generating perturbations.
    """
    if isinstance(value, (list, dict)):
        raise DecisionFieldTypeError(
            catalog(
                SCORER_NON_SCALAR_DECISION_FIELD,
                field_name=field_name,
                actual_type=type(value).__name__,
            )
        )


def aggregate(
    cases: list[CaseScores],
    *,
    seed: int,
    governing_types: list[str],
    run_warnings: list[str] | None = None,
    run_caps: list[str] | None = None,
    single_case_run: bool = False,
    dry_run: bool = False,
) -> RunScores:
    """Roll up per-case distances into cross-case `RunScores`.

    Overall invariance and sensitivity are uniform means across every
    contributing perturbation, regardless of case — small cases don't get
    outsized weight.
    """
    all_invariance = [d for c in cases for d in c.invariance_distances]
    all_swap = [d for c in cases for d in c.swap_distances]

    invariance_mean = mean(all_invariance) if all_invariance else None
    invariance = (1.0 - invariance_mean) if invariance_mean is not None else None
    sensitivity = mean(all_swap) if all_swap else None

    if invariance is not None and sensitivity is not None:
        kelvin_score = (1.0 - invariance) + (1.0 - sensitivity)
    else:
        kelvin_score = None

    by_type: dict[str, list[float]] = {}
    for c in cases:
        for gtype, swaps in c.swaps_by_type.items():
            by_type.setdefault(gtype, []).extend(
                sp.distance for sp in swaps if sp.distance is not None
            )

    sensitivity_by_type: dict[str, tuple[float, int]] = {
        gtype: (mean(dists) if dists else 0.0, len(dists))
        for gtype, dists in by_type.items()
    }

    # Collect warnings and caps surfaced from cases plus any run-level ones.
    warnings: list[str] = list(run_warnings or [])
    caps: list[str] = list(run_caps or [])
    for c in cases:
        warnings.extend(c.warnings)
        caps.extend(c.caps)

    # Pillar 1: compute noise floor η as the mean per-case σ_c across
    # cases that actually produced replay data. When noise floor was not
    # enabled (all σ_c are None), η stays None and calibrated scores
    # stay None — the report shape is unchanged for non-noise-floor runs.
    case_sigmas = [c.noise_floor_sigma_c for c in cases if c.noise_floor_sigma_c is not None]
    eta = mean(case_sigmas) if case_sigmas else None
    inv_cal, sens_cal, k_cal = calibrate(
        invariance_raw=invariance,
        sensitivity_raw=sensitivity,
        eta=eta,
    )

    return RunScores(
        cases=cases,
        seed=seed,
        invariance=invariance,
        invariance_sample=len(all_invariance),
        sensitivity=sensitivity,
        sensitivity_sample=len(all_swap),
        kelvin_score=kelvin_score,
        sensitivity_by_type=sensitivity_by_type,
        governing_types=list(governing_types),
        single_case_run=single_case_run,
        dry_run=dry_run,
        noise_floor_eta=eta,
        invariance_calibrated=inv_cal,
        sensitivity_calibrated=sens_cal,
        kelvin_score_calibrated=k_cal,
        warnings=warnings,
        caps=caps,
    )
