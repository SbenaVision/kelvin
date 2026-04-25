"""Discovery loop — v2.1.

Two parallel evaluations per pipeline:

(A) GLOBAL INVARIANCE on the full applicable distribution.
    For each (T, R^Ω) where T is invariance-kind, evaluate
    z_i = R^Ω(f(x_i), f(Tx_i); q_i) over all applicable x_i.
    Acceptance via accept_high (CP LCB ≥ 1−ε at α = δ/m_global).

(B) DIRECTIONAL SENSITIVITY RATES on pre-specified A_T subsets.
    For each directional T, evaluate per case in A_T(x_i):
        signed_effect = f(Tx_i) − f(x_i)
        category ∈ {correct, wrong, no_effect}:
            "correct"   : signed_effect satisfies expected direction
                          AND |signed_effect| ≥ q + Δ_dir
            "wrong"     : signed_effect satisfies OPPOSITE direction
                          AND |signed_effect| ≥ q + Δ_dir
            "no_effect" : otherwise
    Compute (correct_rate, wrong_rate, no_effect_rate) and CP bounds.

(C) NAIVE DIRECTIONAL on A_T (DIAGNOSTIC ONLY for c7 load-bearing).
    Same A_T evaluation, but using the naive directional predicates
    (no q term). Naive uses α = δ (no Bonferroni) per v2 convention.

Applicability filter: cases where T is not applicable to x_i are
DROPPED for that (T, R) pair (never counted as a hold).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from cp_lcb import accept_high, accept_low, cp_lcb, cp_ucb
from relations import NaiveDirectionalRelation, NoiseAwareRelation
from schema import Input
from transformations import Transform


PipelineFn = Callable[[Input, int], int]


# =====================================================================
# (A) Global invariance on full applicable corpus
# =====================================================================

@dataclass(frozen=True)
class GlobalInvarianceCandidate:
    pipeline: str
    t_name: str
    axis: str
    is_identity: bool
    r_name: str
    k: int
    n_eff: int
    n_raw: int
    p_hat: float
    cp_lcb_value: float
    accepted: bool
    skipped_low_neff: bool


def _global_invariance_evaluate(
    f: PipelineFn,
    inputs: list[Input],
    baseline_first: dict[int, int],
    q_per_case: dict[int, float],
    t: Transform,
    r: NoiseAwareRelation,
    transform_replay_idx: int,
) -> tuple[int, int]:
    rng = random.Random(0xA1A1)
    k = 0
    n_eff = 0
    for inp in inputs:
        if not t.is_applicable(inp):
            continue
        n_eff += 1
        y1 = baseline_first[inp.case.case_id]
        tx = t.apply(inp, rng)
        y2 = f(tx, transform_replay_idx)
        q = q_per_case[inp.case.case_id]
        if r.check(y1, y2, q):
            k += 1
    return k, n_eff


def discover_global_invariance(
    pipeline_name: str,
    f: PipelineFn,
    transforms: list[Transform],
    relations: list[NoiseAwareRelation],
    inputs: list[Input],
    baseline_first: dict[int, int],
    q_per_case: dict[int, float],
    *,
    eps: float,
    alpha: float,
    n_eff_min: int,
    transform_replay_idx: int,
) -> list[GlobalInvarianceCandidate]:
    """Run R^Ω over full corpus for INVARIANCE Ts only.

    Directional Ts are not evaluated here; their sensitivity rates
    are computed by `discover_directional_rates`.
    """
    out: list[GlobalInvarianceCandidate] = []
    for t in transforms:
        if t.sensitivity_kind != "invariance":
            continue
        for r in relations:
            k, n_eff = _global_invariance_evaluate(
                f, inputs, baseline_first, q_per_case,
                t, r, transform_replay_idx,
            )
            n_raw = len(inputs)
            p_hat = k / n_eff if n_eff > 0 else 0.0
            skipped = n_eff < n_eff_min
            if skipped:
                accepted = False
                lb = 0.0
            else:
                accepted = accept_high(k, n_eff, eps, alpha)
                lb = cp_lcb(k, n_eff, alpha)
            out.append(GlobalInvarianceCandidate(
                pipeline=pipeline_name, t_name=t.name, axis=t.axis,
                is_identity=t.is_identity, r_name=r.name,
                k=k, n_eff=n_eff, n_raw=n_raw,
                p_hat=p_hat, cp_lcb_value=lb,
                accepted=accepted, skipped_low_neff=skipped,
            ))
    return out


# =====================================================================
# (B) Directional sensitivity rates on A_T
# =====================================================================

@dataclass(frozen=True)
class DirectionalRates:
    pipeline: str
    t_name: str
    axis: str
    expected_direction: str
    is_borderline: bool

    n_eff_active: int
    n_active_below_floor: bool

    correct_count: int
    wrong_count: int
    no_effect_count: int

    correct_rate: float
    wrong_rate: float
    no_effect_rate: float

    correct_lcb: float
    wrong_ucb: float
    no_effect_lcb: float

    correct_high_accepted: bool          # rate ≥ 1 − ε
    wrong_low_accepted: bool             # rate ≤ ε

    # Naive-directional companion (diagnostic for c7):
    naive_correct_count: int
    naive_correct_rate: float
    naive_correct_high_accepted: bool    # naive rate ≥ 1 − ε at α = δ


def _classify(
    expected: str, signed_effect: int, q: float, delta_dir: int,
) -> str:
    """Return 'correct' | 'wrong' | 'no_effect' for a single case."""
    threshold = q + delta_dir
    if expected == "UP":
        if signed_effect >= threshold:
            return "correct"
        if signed_effect <= -threshold:
            return "wrong"
        return "no_effect"
    if expected == "DOWN":
        if signed_effect <= -threshold:
            return "correct"
        if signed_effect >= threshold:
            return "wrong"
        return "no_effect"
    raise ValueError(f"unsupported expected_direction: {expected!r}")


def _naive_correct(expected: str, signed_effect: int, delta_naive: int) -> bool:
    if expected == "UP":
        return signed_effect >= delta_naive
    if expected == "DOWN":
        return signed_effect <= -delta_naive
    raise ValueError(f"unsupported expected_direction: {expected!r}")


def discover_directional_rates(
    pipeline_name: str,
    f: PipelineFn,
    transforms: list[Transform],
    inputs: list[Input],
    baseline_first: dict[int, int],
    q_per_case: dict[int, float],
    *,
    eps: float,
    alpha_omega: float,
    alpha_naive: float,
    delta_dir: int,
    delta_naive: int,
    n_eff_active_min: int,
    transform_replay_idx: int,
) -> list[DirectionalRates]:
    out: list[DirectionalRates] = []
    rng = random.Random(0xB2B2)
    for t in transforms:
        if t.sensitivity_kind != "directional":
            continue
        assert t.active_subset is not None, f"{t.name} missing active_subset"

        c_count = w_count = n_count = 0
        naive_c_count = 0
        n_eff_active = 0
        for inp in inputs:
            if not t.is_applicable(inp):
                continue
            if not t.active_subset(inp):
                continue
            n_eff_active += 1
            y1 = baseline_first[inp.case.case_id]
            tx = t.apply(inp, rng)
            y2 = f(tx, transform_replay_idx)
            q = q_per_case[inp.case.case_id]
            signed = y2 - y1

            cat = _classify(t.expected_direction, signed, q, delta_dir)
            if cat == "correct":   c_count += 1
            elif cat == "wrong":   w_count += 1
            else:                  n_count += 1

            if _naive_correct(t.expected_direction, signed, delta_naive):
                naive_c_count += 1

        below = n_eff_active < n_eff_active_min
        if n_eff_active == 0:
            c_rate = w_rate = n_rate = 0.0
            naive_c_rate = 0.0
            c_lcb = 0.0
            w_ucb = 1.0
            n_lcb = 0.0
            c_high = False
            w_low = False
            naive_c_high = False
        else:
            c_rate = c_count / n_eff_active
            w_rate = w_count / n_eff_active
            n_rate = n_count / n_eff_active
            naive_c_rate = naive_c_count / n_eff_active
            if below:
                c_lcb = 0.0
                w_ucb = 1.0
                n_lcb = 0.0
                c_high = False
                w_low = False
                naive_c_high = False
            else:
                c_lcb = cp_lcb(c_count, n_eff_active, alpha_omega)
                w_ucb = cp_ucb(w_count, n_eff_active, alpha_omega)
                n_lcb = cp_lcb(n_count, n_eff_active, alpha_omega)
                c_high = accept_high(c_count, n_eff_active, eps, alpha_omega)
                w_low = accept_low(w_count, n_eff_active, eps, alpha_omega)
                naive_c_high = accept_high(naive_c_count, n_eff_active, eps, alpha_naive)

        out.append(DirectionalRates(
            pipeline=pipeline_name, t_name=t.name, axis=t.axis,
            expected_direction=t.expected_direction,
            is_borderline=t.is_borderline,
            n_eff_active=n_eff_active,
            n_active_below_floor=below,
            correct_count=c_count, wrong_count=w_count, no_effect_count=n_count,
            correct_rate=c_rate, wrong_rate=w_rate, no_effect_rate=n_rate,
            correct_lcb=c_lcb, wrong_ucb=w_ucb, no_effect_lcb=n_lcb,
            correct_high_accepted=c_high,
            wrong_low_accepted=w_low,
            naive_correct_count=naive_c_count,
            naive_correct_rate=naive_c_rate,
            naive_correct_high_accepted=naive_c_high,
        ))
    return out
