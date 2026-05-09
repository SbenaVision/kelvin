"""4-way axis classification per thesis §7.

For each (pipeline, axis), classify the axis's behavior based on the
*subsumed* accepted-pair set. Subsumption matters because if R_eq is
accepted for a T, we drop its weaker consequences (R_le, R_ge,
R_sign_eq) — otherwise "responsive" would never occur (R_eq always
implies R_le, R_ge).

Per-T classification (inputs: the set of accepted R names for this T
after subsumption):
  - T-invariant:  R_eq is in the accepted set. (R_eq is strongest;
                  subsumption guarantees nothing else survives alongside.)
  - T-responsive: at least one of {R_le, R_ge, R_sign_eq} accepted,
                  and R_eq is NOT.
  - T-null:       no relation accepted.

Axis classification:
  - responsive:          at least one T is T-responsive (monotone or
                         directional behavior observed).
  - invariant-candidate: all non-identity T on the axis are T-invariant,
                         AND the schema declares the axis non-causal.
  - ignored-candidate:   all non-identity T on the axis are T-invariant,
                         BUT the schema declares the axis rule-bearing or
                         causal. This is the key bug-symmetry discriminator
                         from the thesis.
  - unstable/noisy:      mix of T-invariant / T-null on the axis (no T
                         is T-responsive, but some pass R_eq and some
                         don't). Flags a catalogue-or-pipeline problem.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from discover import Candidate
from schema import AXIS_STATUS, AxisStatus
from transformations import CATALOGUE as T_CATALOGUE


AxisClass = Literal[
    "responsive",
    "invariant-candidate",
    "ignored-candidate",
    "unstable/noisy",
]


@dataclass(frozen=True)
class AxisReport:
    pipeline: str
    axis: str
    classification: AxisClass
    n_transforms: int
    n_responsive: int
    n_invariant: int
    n_null: int
    reason: str


def _t_status(accepted_r_for_t: set[str]) -> Literal["invariant", "responsive", "null"]:
    if "R_eq" in accepted_r_for_t:
        return "invariant"
    if accepted_r_for_t & {"R_le", "R_ge", "R_sign_eq"}:
        return "responsive"
    return "null"


def classify_axes(
    candidates_subsumed: list[Candidate],
) -> list[AxisReport]:
    # Build: accepted_by_t[(pipeline, t_name)] = set of r_names accepted
    accepted_by_t: dict[tuple[str, str], set[str]] = {}
    for c in candidates_subsumed:
        if not c.accepted:
            continue
        accepted_by_t.setdefault((c.pipeline, c.t_name), set()).add(c.r_name)

    # Build axis → non-identity T names.
    axis_to_ts: dict[str, list[str]] = {}
    for t in T_CATALOGUE:
        if t.is_identity:
            continue
        axis_to_ts.setdefault(t.axis, []).append(t.name)

    pipelines = sorted({c.pipeline for c in candidates_subsumed})

    reports: list[AxisReport] = []
    for pipeline in pipelines:
        for axis, t_names in axis_to_ts.items():
            t_statuses = [
                _t_status(accepted_by_t.get((pipeline, t), set()))
                for t in t_names
            ]
            n_resp = sum(1 for s in t_statuses if s == "responsive")
            n_inv = sum(1 for s in t_statuses if s == "invariant")
            n_null = sum(1 for s in t_statuses if s == "null")

            status: AxisClass
            reason: str
            axis_status = AXIS_STATUS.get(axis, AxisStatus.NON_CAUSAL)

            if n_resp >= 1:
                status = "responsive"
                reason = f"{n_resp}/{len(t_names)} T's show directional response"
            elif n_inv == len(t_names):
                # Every T on this axis is R_eq-accepted → uniform invariance.
                if axis_status == AxisStatus.NON_CAUSAL:
                    status = "invariant-candidate"
                    reason = (
                        "schema declares axis non-causal; uniform invariance is "
                        "consistent with the specification"
                    )
                else:
                    status = "ignored-candidate"
                    reason = (
                        f"schema declares axis {axis_status.value}; uniform "
                        f"invariance indicates the pipeline is ignoring this axis"
                    )
            else:
                status = "unstable/noisy"
                reason = (
                    f"mix of invariant ({n_inv}) and null ({n_null}) T's "
                    f"with no responsive T — see candidate-level report"
                )
            reports.append(AxisReport(
                pipeline=pipeline,
                axis=axis,
                classification=status,
                n_transforms=len(t_names),
                n_responsive=n_resp,
                n_invariant=n_inv,
                n_null=n_null,
                reason=reason,
            ))
    return reports
