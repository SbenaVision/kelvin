"""Output relation catalogue + implication lattice.

A relation R: Y × Y → {0, 1} is a decidable predicate. Each R(f(x),
f(Tx)) is a Bernoulli trial used by the discovery loop.

Subsumption (implication) lattice:
    R_eq ⇒ R_le      (a == b ⇒ a ≤ b)
    R_eq ⇒ R_ge      (a == b ⇒ a ≥ b)
    R_eq ⇒ R_sign_eq (a == b ⇒ sign(a − τ) == sign(b − τ))
    R_le ⇏ R_sign_eq (counter: a=40, b=60, τ=50 → R_le holds, sign flips)
    R_ge ⇏ R_sign_eq (symmetric counter)

After discovery, any (T, R') whose R' is implied by a stronger R on
the same T is dropped, so the signature contains only the strongest
relation per T.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from schema import DECISION_THRESHOLD


@dataclass(frozen=True)
class Relation:
    name: str
    check: Callable[[int, int], bool]


def _eq(a: int, b: int) -> bool:
    return a == b


def _le(a: int, b: int) -> bool:
    """f(x) ≤ f(Tx): T increases (or preserves) the score."""
    return a <= b


def _ge(a: int, b: int) -> bool:
    """f(x) ≥ f(Tx): T decreases (or preserves) the score."""
    return a >= b


def _sign_eq(a: int, b: int) -> bool:
    """Decision is preserved across T."""
    da = a >= DECISION_THRESHOLD
    db = b >= DECISION_THRESHOLD
    return da == db


CATALOGUE: list[Relation] = [
    Relation("R_eq",      _eq),
    Relation("R_le",      _le),
    Relation("R_ge",      _ge),
    Relation("R_sign_eq", _sign_eq),
]


# For subsumption.drop_subsumed.
IMPLIES: dict[str, set[str]] = {
    "R_eq":      {"R_le", "R_ge", "R_sign_eq"},
    "R_le":      set(),
    "R_ge":      set(),
    "R_sign_eq": set(),
}
