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

from kelvin.types import CaseScores, RunScores


class DecisionFieldTypeError(ValueError):
    """Raised when the decision field value is not a supported scalar."""


class Scorer(Protocol):
    """Pluggable distance function on the declared decision field."""

    def distance(self, baseline: Any, perturbed: Any) -> float: ...


class DefaultScorer:
    """Spec-faithful v1 scorer."""

    def distance(self, baseline: Any, perturbed: Any) -> float:
        for v in (baseline, perturbed):
            if isinstance(v, (list, dict)):
                raise DecisionFieldTypeError(
                    f"decision field must be scalar (str, number, bool, null); "
                    f"got {type(v).__name__}"
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


def validate_scalar(value: Any, field_name: str) -> None:
    """Raise if the value isn't one of Kelvin's supported scalar types.

    Used in the first-baseline preflight to fail fast on non-scalar decision
    fields — before we burn compute generating perturbations.
    """
    if isinstance(value, (list, dict)):
        raise DecisionFieldTypeError(
            f"decision field '{field_name}' must be scalar "
            f"(str, number, bool, null); got {type(value).__name__}"
        )


def aggregate(
    cases: list[CaseScores],
    *,
    seed: int,
    governing_types: list[str],
    run_warnings: list[str] | None = None,
    run_caps: list[str] | None = None,
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

    return RunScores(
        cases=cases,
        seed=seed,
        invariance=invariance,
        invariance_sample=len(all_invariance),
        sensitivity=sensitivity,
        sensitivity_sample=len(all_swap),
        sensitivity_by_type=sensitivity_by_type,
        governing_types=list(governing_types),
        warnings=warnings,
        caps=caps,
    )
