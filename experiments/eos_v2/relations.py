"""Relation catalogue (sealed) — naive AND noise-aware.

Per plan §6 (corrected):

  R^Ω_eq(y1, y2; q)        := |y2 - y1| ≤ q + Δ_eq
  R^Ω_↑ (y1, y2; q)        := y2 - y1  ≥ q + Δ
  R^Ω_↓ (y1, y2; q)        := y1 - y2  ≥ q + Δ
  R_sign_eq(y1, y2)        := (y1 ≥ τ) == (y2 ≥ τ)        (no noise term)

Naive counterparts (Δ but no q) are kept as DIAGNOSTIC ONLY:
they are computed by run.py for the load-bearing check, but they are
NOT included in the Bonferroni m and NOT part of the EOS signature.

Subsumption operates only within R^Ω. Cross-family edges
(R_eq_naive ⇒ R^Ω_eq, R^Ω_↑ ⇒ R_↑_naive) are suppressed deliberately
because the families serve different roles.

Within R^Ω:
  R^Ω_eq ⇒ R^Ω_↑ (when q + Δ_eq ≥ q + Δ_dir, i.e., Δ_eq ≥ Δ_dir)?
  No — equality (|d| ≤ thr) does not imply directional (d ≥ thr_d). For
  instance d = 0 satisfies equality but not directional.
  Likewise R^Ω_eq does not imply R_sign_eq universally (a 5-point flip
  through τ=50 would satisfy R^Ω_eq with Δ_eq=5 but flip the decision).

Therefore the noise-aware family has NO non-trivial implications. We
keep IMPLIES = {} for R^Ω; subsumption is a no-op in this experiment
but the machinery is preserved for future catalogues that might add
strict relations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from config import DECISION_THRESHOLD, DELTA_DIR, DELTA_EQ


@dataclass(frozen=True)
class NoiseAwareRelation:
    """R(y1, y2, q_noise) → bool. Includes Δ margin internally."""
    name: str
    check: Callable[[int, int, float], bool]


@dataclass(frozen=True)
class NaiveRelation:
    """R(y1, y2) → bool. No noise term."""
    name: str
    check: Callable[[int, int], bool]


# ---- Noise-aware (PRIMARY signature) ----

def _eq_noise(y1: int, y2: int, q: float) -> bool:
    return abs(y2 - y1) <= q + DELTA_EQ


def _up_noise(y1: int, y2: int, q: float) -> bool:
    return (y2 - y1) >= q + DELTA_DIR


def _down_noise(y1: int, y2: int, q: float) -> bool:
    return (y1 - y2) >= q + DELTA_DIR


def _sign_eq(y1: int, y2: int, q: float) -> bool:
    # No noise adjustment: decision is binary, threshold-only.
    return (y1 >= DECISION_THRESHOLD) == (y2 >= DECISION_THRESHOLD)


NOISE_AWARE: list[NoiseAwareRelation] = [
    NoiseAwareRelation("R_eq_omega",   _eq_noise),
    NoiseAwareRelation("R_up_omega",   _up_noise),
    NoiseAwareRelation("R_down_omega", _down_noise),
    NoiseAwareRelation("R_sign_eq",    _sign_eq),
]


# ---- Naive (DIAGNOSTIC only — load-bearing check) ----

def _eq_naive(y1: int, y2: int) -> bool:
    return abs(y2 - y1) <= DELTA_EQ


def _up_naive(y1: int, y2: int) -> bool:
    return (y2 - y1) >= DELTA_DIR


def _down_naive(y1: int, y2: int) -> bool:
    return (y1 - y2) >= DELTA_DIR


NAIVE: list[NaiveRelation] = [
    NaiveRelation("R_eq_naive",   _eq_naive),
    NaiveRelation("R_up_naive",   _up_naive),
    NaiveRelation("R_down_naive", _down_naive),
]


# Subsumption within R^Ω: no non-trivial implications (see module docstring).
IMPLIES_OMEGA: dict[str, set[str]] = {
    "R_eq_omega":   set(),
    "R_up_omega":   set(),
    "R_down_omega": set(),
    "R_sign_eq":    set(),
}
