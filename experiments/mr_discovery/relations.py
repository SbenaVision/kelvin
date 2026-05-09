"""Output relation catalogue.

Each relation is a decidable binary predicate on outputs. Together with
a transformation T, it forms a metamorphic relation: R(f(x), f(Tx)).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Relation:
    name: str
    check: Callable[[int, int], bool]


def _eq(a: int, b: int) -> bool:
    return a == b


def _le(a: int, b: int) -> bool:
    """Monotone-up: f(x) ≤ f(Tx)."""
    return a <= b


def _ge(a: int, b: int) -> bool:
    """Monotone-down: f(x) ≥ f(Tx)."""
    return a >= b


def _lt(a: int, b: int) -> bool:
    """Strict monotone-up."""
    return a < b


def _gt(a: int, b: int) -> bool:
    """Strict monotone-down."""
    return a > b


CATALOGUE: list[Relation] = [
    Relation("R_eq", _eq),
    Relation("R_le", _le),
    Relation("R_ge", _ge),
    Relation("R_lt", _lt),
    Relation("R_gt", _gt),
]
