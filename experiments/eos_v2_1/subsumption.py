"""Subsumption filter — within R^Ω only.

Per relations.IMPLIES_OMEGA, the noise-aware family has no non-trivial
implications: equality and directional are not nested under the
margin Δ. So this is currently a no-op. The machinery is preserved so
that future catalogues with strict relations (e.g., R_lt, R_gt) can be
added without changing the discovery loop.
"""
from __future__ import annotations

from discover import GlobalInvarianceCandidate
from relations import IMPLIES_OMEGA


def drop_subsumed(candidates: list[GlobalInvarianceCandidate]) -> list[GlobalInvarianceCandidate]:
    by_key: dict[tuple[str, str], list[GlobalInvarianceCandidate]] = {}
    for c in candidates:
        if not c.accepted:
            continue
        by_key.setdefault((c.pipeline, c.t_name), []).append(c)

    kept_keys: set[tuple[str, str, str]] = set()
    for (_, _), group in by_key.items():
        r_names = {c.r_name for c in group}
        implied: set[str] = set()
        for r in r_names:
            implied |= IMPLIES_OMEGA.get(r, set())
        for c in group:
            if c.r_name in implied:
                continue
            kept_keys.add((c.pipeline, c.t_name, c.r_name))

    return [c for c in candidates if (c.pipeline, c.t_name, c.r_name) in kept_keys]
