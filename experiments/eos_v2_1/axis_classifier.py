"""Axis classifier — v2.1.

Per-axis aggregation now uses BOTH:
  - Global invariance pairs (R^Ω over full corpus)
  - Directional rates (correct/wrong/no_effect over A_T)

Per-T classification (sensitivity Ts only):
  T-correct : correct_rate ≥ 1 − ε AND wrong_rate ≤ ε
  T-wrong   : wrong_rate   ≥ 1 − ε AND correct_rate ≤ ε
  T-no-effect: no_effect_rate ≥ 1 − ε
  T-degraded: none of the above; correct_rate < 1 − ε; wrong_rate not high
  T-unresolved: n_eff_active below floor

Per-T classification (invariance Ts):
  T-invariant : R^Ω_eq accepted on full corpus
  T-violated  : R^Ω_eq rejected (some accepts, some don't, or none)

Axis classifications (5-way, per v2.1 spec §10):
  responsive-correct          — ≥1 directional T is T-correct, no T-wrong
  responsive-wrong-direction  — ≥1 directional T is T-wrong
  ignored-candidate           — all directional T's on axis are T-no-effect
                                AND axis is rule-bearing/causal
  invariant-candidate         — all invariance T's on axis are T-invariant
                                AND axis is non-causal
  unstable                    — mix; no clean reading
  unresolved                  — all T's on axis below n_eff_active floor
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from discover import DirectionalRates, GlobalInvarianceCandidate
from schema import AXIS_STATUS, AxisStatus
from transformations import CATALOGUE as T_CATALOGUE


AxisClass = Literal[
    "responsive-correct",
    "responsive-wrong-direction",
    "ignored-candidate",
    "invariant-candidate",
    "unstable",
    "unresolved",
]


@dataclass(frozen=True)
class AxisReport:
    pipeline: str
    axis: str
    classification: AxisClass
    n_transforms_total: int
    n_correct: int
    n_wrong: int
    n_no_effect: int
    n_degraded: int
    n_invariant: int
    n_violated: int
    n_unresolved: int
    reason: str


def _t_status_directional(rate: DirectionalRates, eps: float) -> str:
    if rate.n_active_below_floor:
        return "unresolved"
    if rate.correct_high_accepted and rate.wrong_low_accepted:
        return "correct"
    if rate.wrong_rate >= 1 - eps and rate.correct_rate <= eps:
        return "wrong"
    if rate.no_effect_rate >= 1 - eps:
        return "no_effect"
    return "degraded"


def _t_status_invariance(c: GlobalInvarianceCandidate) -> str:
    if c.skipped_low_neff:
        return "unresolved"
    return "invariant" if c.accepted else "violated"


def classify_axes(
    invariance_candidates: list[GlobalInvarianceCandidate],
    directional_rates: list[DirectionalRates],
    eps: float,
) -> list[AxisReport]:
    # Index invariance candidates: only R_eq_omega is the invariance signal.
    inv_by_t: dict[tuple[str, str], GlobalInvarianceCandidate] = {}
    for c in invariance_candidates:
        if c.r_name == "R_eq_omega":
            inv_by_t[(c.pipeline, c.t_name)] = c
    rate_by_t: dict[tuple[str, str], DirectionalRates] = {
        (r.pipeline, r.t_name): r for r in directional_rates
    }

    axis_to_ts: dict[str, list[str]] = {}
    for t in T_CATALOGUE:
        if t.is_identity:
            continue
        axis_to_ts.setdefault(t.axis, []).append(t.name)

    pipelines: set[str] = set()
    pipelines.update(c.pipeline for c in invariance_candidates)
    pipelines.update(r.pipeline for r in directional_rates)

    reports: list[AxisReport] = []
    for pipeline in sorted(pipelines):
        for axis, t_names in axis_to_ts.items():
            n_correct = n_wrong = n_no_effect = n_degraded = 0
            n_invariant = n_violated = n_unresolved = 0
            for tname in t_names:
                # Distinguish directional vs invariance via catalogue lookup.
                t_obj = next(t for t in T_CATALOGUE if t.name == tname)
                if t_obj.sensitivity_kind == "invariance":
                    inv = inv_by_t.get((pipeline, tname))
                    if inv is None:
                        n_unresolved += 1
                        continue
                    s = _t_status_invariance(inv)
                    if s == "invariant":   n_invariant += 1
                    elif s == "violated":  n_violated += 1
                    else:                  n_unresolved += 1
                else:
                    rate = rate_by_t.get((pipeline, tname))
                    if rate is None:
                        n_unresolved += 1
                        continue
                    s = _t_status_directional(rate, eps)
                    if s == "correct":     n_correct += 1
                    elif s == "wrong":     n_wrong += 1
                    elif s == "no_effect": n_no_effect += 1
                    elif s == "degraded":  n_degraded += 1
                    else:                  n_unresolved += 1

            n_total = len(t_names)
            n_resolved = n_total - n_unresolved
            axis_status = AXIS_STATUS.get(axis, AxisStatus.NON_CAUSAL)

            cls: AxisClass
            reason: str

            if n_resolved == 0:
                cls = "unresolved"
                reason = f"all {n_total} T's below n_eff floor"
            elif n_wrong >= 1:
                cls = "responsive-wrong-direction"
                reason = (
                    f"{n_wrong}/{n_total} T's wrong-direction; "
                    f"{n_correct} correct, {n_no_effect} no-effect, "
                    f"{n_degraded} degraded"
                )
            elif n_correct >= 1 and n_degraded == 0:
                cls = "responsive-correct"
                reason = (
                    f"{n_correct}/{n_total} T's correct-direction; "
                    f"{n_no_effect} no-effect, {n_unresolved} unresolved"
                )
            elif (
                n_no_effect == n_resolved - n_invariant
                and n_no_effect + n_invariant > 0
                and axis_status in (AxisStatus.RULE_BEARING, AxisStatus.CAUSAL)
            ):
                cls = "ignored-candidate"
                reason = (
                    f"axis declared {axis_status.value}; all directional "
                    f"T's no-effect ({n_no_effect}) — pipeline ignores axis"
                )
            elif (
                n_invariant + n_no_effect == n_resolved
                and axis_status == AxisStatus.NON_CAUSAL
            ):
                cls = "invariant-candidate"
                reason = (
                    f"axis declared non-causal; uniform invariance / no-effect "
                    f"({n_invariant} inv, {n_no_effect} no-effect)"
                )
            else:
                cls = "unstable"
                reason = (
                    f"mixed: {n_correct}c {n_wrong}w {n_no_effect}ne "
                    f"{n_degraded}d  inv={n_invariant} viol={n_violated}"
                )

            reports.append(AxisReport(
                pipeline=pipeline, axis=axis, classification=cls,
                n_transforms_total=n_total,
                n_correct=n_correct, n_wrong=n_wrong,
                n_no_effect=n_no_effect, n_degraded=n_degraded,
                n_invariant=n_invariant, n_violated=n_violated,
                n_unresolved=n_unresolved,
                reason=reason,
            ))
    return reports
