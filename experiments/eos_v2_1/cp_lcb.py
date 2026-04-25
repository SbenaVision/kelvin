"""Exact one-sided Clopper–Pearson bounds + Bonferroni-aware tests.

LCB (lower confidence bound) at level 1−α:
  p_L = min{p : Pr[Bin(n, p) ≥ k] ≥ α}

UCB (upper confidence bound) at level 1−α:
  p_U = max{p : Pr[Bin(n, p) ≤ k] ≥ α}

Acceptance forms (single-tail equivalents, faster than bisection):

  HIGH-RATE accept (rate ≥ 1−ε):
    accept_high(k, n, eps, alpha)  ⇔  Pr[X ≥ k | n, p=1−eps] ≤ alpha
    ⇔  CP one-sided 1−α LCB is ≥ 1−ε.

  LOW-RATE accept (rate ≤ ε):
    accept_low(k, n, eps, alpha)   ⇔  Pr[X ≤ k | n, p=eps] ≤ alpha
    ⇔  CP one-sided 1−α UCB is ≤ ε.

All in stdlib (math.lgamma + bisection). No scipy.
"""
from __future__ import annotations

import math


def _log_choose(n: int, k: int) -> float:
    if k < 0 or k > n:
        return float("-inf")
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def binomial_tail_upper(k: int, n: int, p: float) -> float:
    """Pr[Bin(n, p) ≥ k]."""
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


def binomial_tail_lower(k: int, n: int, p: float) -> float:
    """Pr[Bin(n, p) ≤ k]."""
    if k < 0:   return 0.0
    if k >= n:  return 1.0
    if p <= 0.0: return 1.0
    if p >= 1.0: return 0.0
    log_p = math.log(p)
    log_q = math.log1p(-p)
    log_terms = [
        _log_choose(n, j) + j * log_p + (n - j) * log_q
        for j in range(0, k + 1)
    ]
    m = max(log_terms)
    if m == float("-inf"):
        return 0.0
    s = sum(math.exp(t - m) for t in log_terms)
    return min(1.0, math.exp(m) * s)


def accept_high(k: int, n: int, eps: float, alpha: float) -> bool:
    """Accept rate ≥ 1−ε iff Pr[X ≥ k | n, p=1−ε] ≤ α."""
    if n <= 0:
        return False
    return binomial_tail_upper(k, n, 1.0 - eps) <= alpha


def accept_low(k: int, n: int, eps: float, alpha: float) -> bool:
    """Accept rate ≤ ε iff Pr[X ≤ k | n, p=ε] ≤ α."""
    if n <= 0:
        return False
    return binomial_tail_lower(k, n, eps) <= alpha


def cp_lcb(k: int, n: int, alpha: float, tol: float = 1e-9, max_iter: int = 80) -> float:
    if n <= 0 or k <= 0:
        return 0.0
    if k >= n:
        return alpha ** (1.0 / n)
    lo, hi = 0.0, 1.0
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        if binomial_tail_upper(k, n, mid) < alpha:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


def cp_ucb(k: int, n: int, alpha: float, tol: float = 1e-9, max_iter: int = 80) -> float:
    if n <= 0:
        return 1.0
    if k >= n:
        return 1.0
    if k <= 0:
        return 1.0 - alpha ** (1.0 / n)
    lo, hi = 0.0, 1.0
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        if binomial_tail_lower(k, n, mid) < alpha:
            hi = mid
        else:
            lo = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


# Backwards-compat: kept so external callers using v2-style accept_cp
# still work. accept_cp ≡ accept_high.
accept_cp = accept_high
