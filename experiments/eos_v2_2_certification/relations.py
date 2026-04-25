"""Raw relations for the certification run (sealed).

Per the V5 theorem and the v2.2 build plan:
  R_up  (y1, y2)  := y2 − y1 ≥ Δ_dir       (directional, score increased)
  R_down(y1, y2)  := y1 − y2 ≥ Δ_dir       (directional, score decreased)
  R_eq  (y1, y2)  := |y2 − y1| ≤ Δ_eq      (invariance)

No noise term. No q estimation. Δ_dir and Δ_eq are sealed in config.py.

These are the ρ_c relations of the V5 theorem in their simplest form
(ρ_c(x, y, y') = R(y, y') with no x-dependence).
"""
from __future__ import annotations

from typing import Callable

from config import DELTA_DIR, DELTA_EQ


def R_up(y1: int, y2: int) -> bool:
    return (y2 - y1) >= DELTA_DIR


def R_down(y1: int, y2: int) -> bool:
    return (y1 - y2) >= DELTA_DIR


def R_eq(y1: int, y2: int) -> bool:
    return abs(y2 - y1) <= DELTA_EQ


RELATION_BY_NAME: dict[str, Callable[[int, int], bool]] = {
    "R_up":   R_up,
    "R_down": R_down,
    "R_eq":   R_eq,
}
