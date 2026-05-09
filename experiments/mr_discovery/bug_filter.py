"""Bug-symmetry discriminator.

A discovered pair (T, R_eq) is a genuine invariance only if *some other*
transformation T' on the same axis is NOT an invariance — i.e., there
exists some way to perturb this axis that changes the output. If every
transformation on the axis yields R_eq, the axis is being ignored by the
pipeline. That is a bug, not a conservation law.

This implementation uses the empirical hold-rates already computed by
`discover.evaluate_pair` on ALL candidates (not just discovered ones):
for each axis with an R_eq invariance, check whether any T' on the same
axis has `hold_rate < 1.0` on R_eq.
"""
from __future__ import annotations

from dataclasses import dataclass

from discover import MRCandidate


@dataclass(frozen=True)
class FilterReport:
    kept: list[MRCandidate]
    rejected: list[MRCandidate]
    reason_by_name: dict[tuple[str, str], str]


def filter_bug_symmetries(
    discovered: list[MRCandidate],
    all_candidates: list[MRCandidate],
) -> FilterReport:
    # Build: for each axis, the set of T names whose R_eq hold_rate < 1.0
    # (i.e., T' that DO change the output on that axis).
    axis_has_discriminator: dict[str, bool] = {}
    for cand in all_candidates:
        if cand.r_name != "R_eq":
            continue
        axis = cand.axis
        if cand.hold_rate < 1.0:
            axis_has_discriminator[axis] = True
        else:
            axis_has_discriminator.setdefault(axis, False)

    kept: list[MRCandidate] = []
    rejected: list[MRCandidate] = []
    reasons: dict[tuple[str, str], str] = {}

    for cand in discovered:
        if cand.r_name != "R_eq":
            kept.append(cand)
            reasons[(cand.t_name, cand.r_name)] = "non-equality MR; filter N/A"
            continue
        if axis_has_discriminator.get(cand.axis, False):
            kept.append(cand)
            reasons[(cand.t_name, cand.r_name)] = (
                f"axis '{cand.axis}' has a discriminating T' — genuine invariance"
            )
        else:
            rejected.append(cand)
            reasons[(cand.t_name, cand.r_name)] = (
                f"axis '{cand.axis}' ignored by pipeline — bug-symmetry"
            )

    return FilterReport(kept=kept, rejected=rejected, reason_by_name=reasons)
