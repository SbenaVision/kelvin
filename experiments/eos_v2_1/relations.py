"""Relation catalogue (sealed) — noise-aware AND naive.

R^Ω (PRIMARY signature):
  R^Ω_eq(y₁, y₂; q)        := |y₂ − y₁| ≤ q + Δ_eq
  R^Ω_↑ (y₁, y₂; q)        := y₂ − y₁  ≥ q + Δ_dir
  R^Ω_↓ (y₁, y₂; q)        := y₁ − y₂  ≥ q + Δ_dir
  R_sign_eq(y₁, y₂)        := (y₁ ≥ τ) == (y₂ ≥ τ)        (no noise term)

Naive directional (DIAGNOSTIC ONLY — load-bearing test, c7):
  R_↑_naive(y₁, y₂)        := y₂ − y₁  ≥ Δ_naive            (no noise term)
  R_↓_naive(y₁, y₂)        := y₁ − y₂  ≥ Δ_naive

Naive equality is NOT used (per v2.1 §9: load-bearing must compare
directional, not equality). Equality without noise is strictly tighter
than R^Ω_eq with q ≥ 0, so naive_eq accepted ⇒ omega_eq accepted; the
divergence is uninteresting.

Subsumption within R^Ω: see relations docstring in v2 — empty.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from config import DECISION_THRESHOLD, DELTA_DIR, DELTA_EQ, DELTA_NAIVE


@dataclass(frozen=True)
class NoiseAwareRelation:
    name: str
    check: Callable[[int, int, float], bool]


@dataclass(frozen=True)
class NaiveDirectionalRelation:
    name: str
    check: Callable[[int, int], bool]


def _eq_noise(y1: int, y2: int, q: float) -> bool:
    return abs(y2 - y1) <= q + DELTA_EQ


def _up_noise(y1: int, y2: int, q: float) -> bool:
    return (y2 - y1) >= q + DELTA_DIR


def _down_noise(y1: int, y2: int, q: float) -> bool:
    return (y1 - y2) >= q + DELTA_DIR


def _sign_eq(y1: int, y2: int, q: float) -> bool:
    return (y1 >= DECISION_THRESHOLD) == (y2 >= DECISION_THRESHOLD)


NOISE_AWARE: list[NoiseAwareRelation] = [
    NoiseAwareRelation("R_eq_omega",   _eq_noise),
    NoiseAwareRelation("R_up_omega",   _up_noise),
    NoiseAwareRelation("R_down_omega", _down_noise),
    NoiseAwareRelation("R_sign_eq",    _sign_eq),
]


def _up_naive(y1: int, y2: int) -> bool:
    return (y2 - y1) >= DELTA_NAIVE


def _down_naive(y1: int, y2: int) -> bool:
    return (y1 - y2) >= DELTA_NAIVE


NAIVE_DIRECTIONAL: list[NaiveDirectionalRelation] = [
    NaiveDirectionalRelation("R_up_naive",   _up_naive),
    NaiveDirectionalRelation("R_down_naive", _down_naive),
]


# Subsumption within R^Ω: no non-trivial implications.
IMPLIES_OMEGA: dict[str, set[str]] = {
    "R_eq_omega":   set(),
    "R_up_omega":   set(),
    "R_down_omega": set(),
    "R_sign_eq":    set(),
}
