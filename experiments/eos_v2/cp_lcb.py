"""Exact one-sided Clopper–Pearson lower bound + Bonferroni-aware test.

Identical implementation to experiments/eos/cp_lcb.py — kept as a
self-contained sealed copy. Stdlib-only (math.lgamma + bisection).

Acceptance test (thesis §4 single-tail equivalent):
    accept_cp(k, n, eps, alpha) ⇔ Pr[X >= k | n, p=1-eps] <= alpha
    ⇔ CP one-sided 1-alpha lower bound is >= 1-eps.
"""
from __future__ import annotations

import math


def _log_choose(n: int, k: int) -> float:
    if k < 0 or k > n:
        return float("-inf")
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def binomial_tail(k: int, n: int, p: float) -> float:
    if k <= 0:  return 1.0
    if k > n:   return 0.0
    if p <= 0.0: return 0.0
    if p >= 1.0: return 1.0
    log_p = math.log(p)
    log_q = math.log1p(-p)
    log_terms = [
        _log_choose(n, j) + j * log_p + (n - j) * log_q
        for j in range(k, n + 1)
    ]
    m = max(log_terms)
    if m == float("-inf"):
        return 0.0
    s = sum(math.exp(t - m) for t in log_terms)
    return min(1.0, math.exp(m) * s)


def accept_cp(k: int, n: int, eps: float, alpha: float) -> bool:
    return binomial_tail(k, n, 1.0 - eps) <= alpha


def cp_lcb(k: int, n: int, alpha: float, tol: float = 1e-9, max_iter: int = 80) -> float:
    if n <= 0 or k <= 0:
        return 0.0
    if k >= n:
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
