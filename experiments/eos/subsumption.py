"""Subsumption filter for the relation lattice.

If (T, R_eq) is accepted, it trivially implies (T, R_le), (T, R_ge),
(T, R_sign_eq) — they are logical consequences, not independent MRs.
Keep only the strongest R per T.

Operates on the list of Candidate records from discover.evaluate_all.
Subsumption is applied per pipeline, per transformation.
"""
from __future__ import annotations

from discover import Candidate
from relations import IMPLIES


def drop_subsumed(candidates: list[Candidate]) -> list[Candidate]:
    # Group accepted candidates by (pipeline, t_name); within each group,
    # drop any R' that is implied by a stronger R on the same T.
    by_key: dict[tuple[str, str], list[Candidate]] = {}
    for c in candidates:
        if not c.accepted:
            continue
        by_key.setdefault((c.pipeline, c.t_name), []).append(c)

    kept_keys: set[tuple[str, str, str]] = set()
    for (pipeline, t_name), group in by_key.items():
        r_names = {c.r_name for c in group}
        implied: set[str] = set()
        for r in r_names:
            implied |= IMPLIES.get(r, set())
        for c in group:
            if c.r_name in implied:
                continue
            kept_keys.add((c.pipeline, c.t_name, c.r_name))

    return [c for c in candidates if (c.pipeline, c.t_name, c.r_name) in kept_keys]
