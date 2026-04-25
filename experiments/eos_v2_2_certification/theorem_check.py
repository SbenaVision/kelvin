"""V5 theorem alignment checker (sealed).

Computes the theorem-required sample sizes from the formulas in the
V5 PDF and verifies that pre-committed N_EFF_MIN satisfies them.

Theorem 2 (uniform recovery over family):
    n_min ≥ ⌈ (1 / 2λ²) · log( 2·M·(A+1) / δ ) ⌉

Theorem 3 (separation alone):
    n_sep_min ≥ ⌈ (1 / 2λ²) · log( 4A / δ ) ⌉

Both bounds are reported. The run uses N_EFF_MIN per (j, c) which
must dominate Theorem 2's bound to certify uniform recovery (the
stronger guarantee).

This module is sealed; its outputs are recorded in results.md and in
the JSON theorem_check artifact written by run.py.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from config import A, A_PLUS_1, DELTA, LAMBDA, M, N_EFF_MIN


@dataclass(frozen=True)
class TheoremBounds:
    M: int
    A: int
    family_size: int
    epsilon: float
    theta: float
    lam: float
    delta: float
    theorem2_n_min: int
    theorem3_n_min: int
    n_eff_min_committed: int
    safety_margin_t2: int
    safety_margin_t3: int


def compute_bounds() -> TheoremBounds:
    # Theorem 2: 2*M*(A+1) / delta inside the log
    t2 = math.ceil(math.log(2 * M * A_PLUS_1 / DELTA) / (2 * LAMBDA * LAMBDA))
    # Theorem 3: 4*A / delta
    t3 = math.ceil(math.log(4 * A / DELTA) / (2 * LAMBDA * LAMBDA))
    from config import EPS, THETA
    return TheoremBounds(
        M=M, A=A, family_size=A_PLUS_1,
        epsilon=EPS, theta=THETA, lam=LAMBDA, delta=DELTA,
        theorem2_n_min=t2, theorem3_n_min=t3,
        n_eff_min_committed=N_EFF_MIN,
        safety_margin_t2=N_EFF_MIN - t2,
        safety_margin_t3=N_EFF_MIN - t3,
    )


def format_report(b: TheoremBounds) -> str:
    return (
        "V5 theorem sample-size bounds (computed from sealed config):\n"
        f"  M = {b.M},  A = {b.A},  |F| = {b.family_size}\n"
        f"  ε = {b.epsilon},  θ = {b.theta},  λ = {b.lam},  δ = {b.delta}\n"
        f"  Theorem 2 n_min = ⌈log(2·{b.M}·{b.family_size}/{b.delta}) / (2·{b.lam}²)⌉ = {b.theorem2_n_min}\n"
        f"  Theorem 3 n_min = ⌈log(4·{b.A}/{b.delta}) / (2·{b.lam}²)⌉ = {b.theorem3_n_min}\n"
        f"  N_EFF_MIN committed = {b.n_eff_min_committed}\n"
        f"  Safety margin (Th.2): {b.safety_margin_t2}\n"
        f"  Safety margin (Th.3): {b.safety_margin_t3}\n"
    )


if __name__ == "__main__":
    print(format_report(compute_bounds()))
