"""Perturbation generators.

`PerturbationGenerator` is a Protocol so v2 semantic-swap can drop in
without touching the runner.
"""

from __future__ import annotations

import hashlib
import random
from typing import Protocol, runtime_checkable

from kelvin.types import Case, PerturbationBatch, PerturbationKind, Unit


@runtime_checkable
class PerturbationGenerator(Protocol):
    """Interface every perturbation generator implements."""

    kind: PerturbationKind

    def generate(
        self,
        case: Case,
        peer_cases: list[Case],
        *,
        seed: int,
        governing_types: list[str],
    ) -> PerturbationBatch: ...


def rng_for(seed: int, *components: str) -> random.Random:
    """Derive a deterministic RNG from the root seed and qualifying components.

    Uses `hashlib.sha256` explicitly so the derivation does not depend on
    Python's built-in `hash()` (which varies with PYTHONHASHSEED) or on
    internals of `random.seed()`'s string handling. The resulting seed is
    stable across Python versions and interpreter invocations.
    """
    key = "|".join((str(seed), *components)).encode("utf-8")
    digest = hashlib.sha256(key).digest()
    int_seed = int.from_bytes(digest[:8], "big")
    return random.Random(int_seed)


def peer_pool(
    case: Case,
    peer_cases: list[Case],
    *,
    type_filter: str | None = None,
) -> list[tuple[str, Unit]]:
    """Return `(source_case_name, unit)` pairs from all peer cases, excluding self.

    If `type_filter` is set, only units of that normalized type are returned.
    Ordering is deterministic (source-case order, then unit order within case).
    """
    result: list[tuple[str, Unit]] = []
    for c in peer_cases:
        if c.name == case.name:
            continue
        for u in c.units:
            if type_filter is None or u.type == type_filter:
                result.append((c.name, u))
    return result
