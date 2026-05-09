"""Exact one-sided Clopper–Pearson lower confidence bound.

Definition. For k successes in n Bernoulli trials, the one-sided
1−α lower bound on the success probability p is:

    p_L = min { p ∈ [0, 1] : P[Binomial(n, p) ≥ k] ≥ α }

Equivalently p_L is the α-quantile of Beta(k, n−k+1). We compute p_L
by bisection on the monotone-increasing function

    T(p) := P[Binomial(n, p) ≥ k]

Edge cases:
  k = 0 → p_L = 0.0
  k = n → p_L = α^(1/n)

Numerical implementation. Binomial tail is summed in log space to
avoid underflow for n≥500 and p near 1. We use log-sum-exp on the
range [k, n] of log-binomial pmf terms.

Accept rule (thesis §4, equivalent form):
    accept  ⇔  p_L ≥ 1 − ε
            ⇔  T(1 − ε) ≤ α              (by monotonicity of T in p)

so we expose `accept_cp(k, n, eps, alpha)` which does *only* the
one-shot tail computation (no bisection) when we just need a decision.
`cp_lcb(k, n, alpha)` returns the actual p_L value for reporting.

All in stdlib. No scipy.
"""
from __future__ import annotations

import math


def _log_choose(n: int, k: int) -> float:
    if k < 0 or k > n:
        return float("-inf")
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def binomial_tail(k: int, n: int, p: float) -> float:
    """P[Binomial(n, p) ≥ k]. Returns a value in [0, 1]."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0

    log_p = math.log(p)
    log_q = math.log1p(-p)

    # Collect log-pmf terms for j = k..n, then log-sum-exp.
    log_terms = [_log_choose(n, j) + j * log_p + (n - j) * log_q for j in range(k, n + 1)]
    m = max(log_terms)
    if m == float("-inf"):
        return 0.0
    s = sum(math.exp(t - m) for t in log_terms)
    return min(1.0, math.exp(m) * s)


def accept_cp(k: int, n: int, eps: float, alpha: float) -> bool:
    """Accept (T, R) iff the one-sided CP lower bound at level 1−α is ≥ 1−ε.

    Uses the equivalent single-tail check: T(1−ε) ≤ α.
    """
    return binomial_tail(k, n, 1.0 - eps) <= alpha


def cp_lcb(k: int, n: int, alpha: float, tol: float = 1e-9, max_iter: int = 80) -> float:
    """Exact one-sided Clopper–Pearson lower bound p_L for confidence 1−α.

    Returns p_L = min{p : T(p) ≥ α}, where T(p) = P[Bin(n, p) ≥ k].
    """
    if n <= 0:
        return 0.0
    if k <= 0:
        return 0.0
    if k >= n:
        # T(p) = p^n; solve p^n = α → p = α^(1/n)
        return alpha ** (1.0 / n)

    lo, hi = 0.0, 1.0
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        t = binomial_tail(k, n, mid)
        if t < alpha:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)
