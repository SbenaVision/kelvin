"""Theorem-aligned success criteria for v2.2 (sealed).

Per V5 theorem and the v2.2 build-plan:

(T2-aligned)
    For every (j, c) ∈ F × K, the empirical CP interval at
    α_per_pair = δ / (2·M·(A+1)) lies entirely on one side of the
    boundary band (θ − λ, θ + λ). This is equivalent to saying the
    margin condition |p_c(f_j) − θ| ≥ λ is empirically supported.

(T3-aligned)
    For each adversary f_j (j = 1..A), there exists at least one probe
    c such that p̂_c(f_track) and p̂_c(f_j) lie on opposite sides of θ
    with margin ≥ λ in their CP intervals.

These tests do NOT prove the V5 theorems (which are mathematical
results in the PDF). They report whether the run's empirical evidence
satisfies the theorems' finite-sample assumptions on this corpus draw.
"""
from __future__ import annotations

from config import LAMBDA, THETA
from discover import ProbeEstimate


def check_t2_alignment(
    estimates: list[ProbeEstimate],
) -> tuple[bool, list[ProbeEstimate]]:
    """Returns (aligned, violating_estimates).

    aligned = True iff every estimate's CP interval excludes the
    boundary band (θ − λ, θ + λ).
    """
    violators = [e for e in estimates if not e.margin_condition_supported]
    return len(violators) == 0, violators


def check_t3_alignment(
    estimates: list[ProbeEstimate],
    adversaries: list[str],
) -> tuple[bool, dict[str, str | None]]:
    """For each adversary, find at least one separating probe c such that
    p̂_c(f_track) and p̂_c(f_j) lie on opposite sides of θ with their CP
    intervals respecting the margin λ.

    Returns (aligned, separating_probe_per_adversary).
    """
    by_pipeline_probe: dict[tuple[str, int], ProbeEstimate] = {
        (e.pipeline, e.probe_idx): e for e in estimates
    }
    track_estimates = [e for e in estimates if e.pipeline == "f_track"]

    sep_per_adv: dict[str, str | None] = {}
    for adv in adversaries:
        found_sep: str | None = None
        for te in track_estimates:
            ae = by_pipeline_probe.get((adv, te.probe_idx))
            if ae is None:
                continue
            # Track on one side, adversary on the OPPOSITE side, both with margin.
            track_high = te.cp_lcb >= THETA + LAMBDA
            track_low = te.cp_ucb <= THETA - LAMBDA
            adv_high = ae.cp_lcb >= THETA + LAMBDA
            adv_low = ae.cp_ucb <= THETA - LAMBDA
            if (track_high and adv_low) or (track_low and adv_high):
                found_sep = te.probe_name
                break
        sep_per_adv[adv] = found_sep

    aligned = all(v is not None for v in sep_per_adv.values())
    return aligned, sep_per_adv
