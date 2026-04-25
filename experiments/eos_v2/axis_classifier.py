"""5-way axis classifier.

Per plan §10:
  responsive-correct          — axis responds AND in predicted direction
                                (matches PREDICTED_DIRECTION on f_track).
  responsive-wrong-direction  — axis responds but with the OPPOSITE
                                directional relation accepted.
  ignored-candidate           — uniform R^Ω_eq across the axis on a
                                schema-rule-bearing or causal axis.
  unstable                    — mix of T-null and T-invariant; some
                                accept R_eq_omega, others accept nothing.
                                (or no R^Ω accepted at all on responsive
                                axis).
  unresolved                  — too few applicable cases or low-n_eff
                                pairs across the axis.

`PREDICTED_DIRECTION` is the catalogue's expectation for f_track. We
classify f_wrongstatic and f_wrongstochastic against the SAME predicted
directions; their wrong-direction acceptance is the detection signal.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from discover import CandidateOmega
from schema import AXIS_STATUS, AxisStatus
from transformations import CATALOGUE as T_CATALOGUE
from transformations import PREDICTED_DIRECTION


AxisClass = Literal[
    "responsive-correct",
    "responsive-wrong-direction",
    "ignored-candidate",
    "unstable",
    "unresolved",
    "invariant-candidate",
]


@dataclass(frozen=True)
class AxisReport:
    pipeline: str
    axis: str
    classification: AxisClass
    n_transforms: int
    n_correct: int
    n_wrong: int
    n_invariant: int
    n_null: int
    n_unresolved: int
    reason: str


def _t_status_omega(
    accepted_r: set[str],
    predicted: str,
) -> Literal["correct", "wrong", "invariant", "null"]:
    """Per-T classification using ONLY the noise-aware accepted set.

    correct  — predicted direction's R^Ω is accepted.
    wrong    — opposite direction's R^Ω is accepted.
    invariant — R_eq_omega accepted but no directional in predicted dir.
    null     — nothing accepted.

    If both directional and equality accepted (rare given the Δ
    margins), prefer the directional reading. R_sign_eq alone (without
    eq or directional) is treated as invariant for classification
    purposes — it indicates decision preservation but not score
    invariance.
    """
    if predicted == "UP":
        if "R_up_omega" in accepted_r:
            return "correct"
        if "R_down_omega" in accepted_r:
            return "wrong"
    elif predicted == "DOWN":
        if "R_down_omega" in accepted_r:
            return "correct"
        if "R_up_omega" in accepted_r:
            return "wrong"
    elif predicted == "EQ":
        if "R_eq_omega" in accepted_r:
            return "invariant"
        if "R_up_omega" in accepted_r or "R_down_omega" in accepted_r:
            return "wrong"

    if "R_eq_omega" in accepted_r:
        return "invariant"
    return "null"


def classify_axes(
    candidates_subsumed: list[CandidateOmega],
) -> list[AxisReport]:
    accepted_by_t: dict[tuple[str, str], set[str]] = {}
    skipped_by_t: dict[tuple[str, str], bool] = {}
    for c in candidates_subsumed:
        key = (c.pipeline, c.t_name)
        if c.skipped_low_neff:
            skipped_by_t[key] = True
            continue
        if c.accepted:
            accepted_by_t.setdefault(key, set()).add(c.r_name)

    axis_to_ts: dict[str, list[str]] = {}
    for t in T_CATALOGUE:
        if t.is_identity:
            continue
        axis_to_ts.setdefault(t.axis, []).append(t.name)

    pipelines = sorted({c.pipeline for c in candidates_subsumed})

    reports: list[AxisReport] = []
    for pipeline in pipelines:
        for axis, t_names in axis_to_ts.items():
            n_correct = n_wrong = n_inv = n_null = n_unres = 0
            for t in t_names:
                key = (pipeline, t)
                if skipped_by_t.get(key, False) and key not in accepted_by_t:
                    n_unres += 1
                    continue
                accepted = accepted_by_t.get(key, set())
                pred = PREDICTED_DIRECTION.get(t, "NONE")
                status = _t_status_omega(accepted, pred)
                if status == "correct":   n_correct += 1
                elif status == "wrong":   n_wrong += 1
                elif status == "invariant": n_inv += 1
                else:                      n_null += 1

            n = len(t_names)
            axis_status = AXIS_STATUS.get(axis, AxisStatus.NON_CAUSAL)

            cls: AxisClass
            reason: str
            if n_unres == n:
                cls = "unresolved"
                reason = "all T's on axis fail n_eff floor"
            elif n_correct >= 1 and n_wrong == 0:
                cls = "responsive-correct"
                reason = (
                    f"{n_correct}/{n} T's accept the predicted directional R^Ω"
                )
            elif n_wrong >= 1:
                cls = "responsive-wrong-direction"
                reason = (
                    f"{n_wrong}/{n} T's accept the OPPOSITE-direction R^Ω "
                    f"({n_correct} correct, {n_inv} invariant, {n_null} null)"
                )
            elif n_inv == n - n_unres and n - n_unres > 0:
                # Uniform invariance on the axis (no directional response).
                if axis_status == AxisStatus.NON_CAUSAL:
                    cls = "invariant-candidate"
                    reason = "schema declares axis non-causal; uniform R^Ω_eq"
                else:
                    cls = "ignored-candidate"
                    reason = (
                        f"schema declares axis {axis_status.value}; uniform "
                        f"R^Ω_eq on a rule-bearing/causal axis is the "
                        f"rule-blind signal"
                    )
            else:
                cls = "unstable"
                reason = (
                    f"mix of {n_inv} invariant, {n_null} null, "
                    f"{n_correct} correct, {n_wrong} wrong"
                )

            reports.append(AxisReport(
                pipeline=pipeline, axis=axis, classification=cls,
                n_transforms=n,
                n_correct=n_correct, n_wrong=n_wrong,
                n_invariant=n_inv, n_null=n_null, n_unresolved=n_unres,
                reason=reason,
            ))
    return reports
