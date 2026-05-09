"""Subsumption filter.

If (T, R_eq) holds, then (T, R_le) and (T, R_ge) also hold trivially —
they are implied consequences, not independent MRs. Keep only the
strongest relation per T.

Implication lattice (for relations in this experiment):
    R_eq ⇒ R_le
    R_eq ⇒ R_ge
    R_le, R_ge are incomparable.

Strength order (strongest first): R_eq > {R_le, R_ge}. We drop any
(T, R') from a discovered set whenever (T, R) is also in the set and
R ⇒ R'.
"""
from __future__ import annotations

from discover import MRCandidate


IMPLIES: dict[str, set[str]] = {
    "R_eq": {"R_le", "R_ge"},
    "R_le": set(),
    "R_ge": set(),
    "R_lt": {"R_le"},
    "R_gt": {"R_ge"},
}


def drop_subsumed(candidates: list[MRCandidate]) -> list[MRCandidate]:
    # Group by T name; within each group, drop any R' implied by a stronger R.
    by_t: dict[str, list[MRCandidate]] = {}
    for c in candidates:
        by_t.setdefault(c.t_name, []).append(c)

    kept: list[MRCandidate] = []
    for t_name, group in by_t.items():
        r_names = {c.r_name for c in group}
        implied: set[str] = set()
        for r in r_names:
            implied |= IMPLIES.get(r, set())
        for c in group:
            if c.r_name in implied:
                continue  # subsumed by a stronger R on the same T
            kept.append(c)
    return kept
