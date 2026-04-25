"""Per-probe Bernoulli evaluation (sealed).

For each (pipeline j, probe c), we evaluate the V5 theorem's
Bernoulli indicator
    Z_i = ρ_c(X_i, f_j(X_i, W_1), f_j(T_c X_i, W_2))
on n_eff = N_EFF_MIN samples X_i ~ D(·|A_c) (drawn by corpus.py).

W_1, W_2 are drawn from the pre-specified coupling Γ_{j,c} via
the deterministic seeding in pipelines/_noise.py: independent jitter
draws indexed by (case_id, replay_idx, pipeline_id) with
replay_idx = BASELINE_REPLAY_IDX = 0 for the baseline call and
replay_idx = TRANSFORM_REPLAY_IDX = 1 for the transformed call.

Output:
    p̂_c(f_j) = (1/n_eff) Σ Z_i
    CP_LCB(α), CP_UCB(α) at α = α_per_pair
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from config import (
    ALPHA_PER_PAIR, BASELINE_REPLAY_IDX, N_EFF_MIN, THEOREM2_N_MIN,
    TRANSFORM_REPLAY_IDX,
)
from cp_lcb import cp_lcb, cp_ucb
from relations import RELATION_BY_NAME
from schema import Input
from transformations import Probe


PipelineFn = Callable[[Input, int], int]


@dataclass(frozen=True)
class ProbeEstimate:
    pipeline: str
    probe_idx: int
    probe_name: str
    relation: str
    expected_direction: str
    n_eff: int
    k: int
    p_hat: float
    cp_lcb: float
    cp_ucb: float
    margin_from_theta: float          # |p_hat − θ|
    n_min_required: int               # theorem-required minimum
    margin_condition_supported: bool  # CP interval excludes (θ − λ, θ + λ)


def evaluate_probe(
    pipeline_name: str,
    f: PipelineFn,
    probe: Probe,
    inputs: list[Input],
    *,
    theta: float,
    lam: float,
    alpha: float,
) -> ProbeEstimate:
    R = RELATION_BY_NAME[probe.relation]
    rng = random.Random(probe.idx ^ 0xCAFE)

    k = 0
    n_eff = 0
    for inp in inputs:
        n_eff += 1
        y1 = f(inp, BASELINE_REPLAY_IDX)
        tx = probe.apply(inp, rng)
        y2 = f(tx, TRANSFORM_REPLAY_IDX)
        if R(y1, y2):
            k += 1

    p_hat = k / n_eff if n_eff else 0.0
    lcb = cp_lcb(k, n_eff, alpha) if n_eff else 0.0
    ucb = cp_ucb(k, n_eff, alpha) if n_eff else 1.0

    # The empirical CP interval [lcb, ucb] supports the margin condition iff
    # it lies entirely above θ + λ OR entirely below θ − λ.
    margin_supported = (lcb >= theta + lam) or (ucb <= theta - lam)

    return ProbeEstimate(
        pipeline=pipeline_name,
        probe_idx=probe.idx,
        probe_name=probe.name,
        relation=probe.relation,
        expected_direction=probe.expected_direction,
        n_eff=n_eff,
        k=k,
        p_hat=p_hat,
        cp_lcb=lcb,
        cp_ucb=ucb,
        margin_from_theta=abs(p_hat - theta),
        n_min_required=THEOREM2_N_MIN,
        margin_condition_supported=margin_supported,
    )
