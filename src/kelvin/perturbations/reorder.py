"""Reorder perturbation — to be implemented in PR 2."""

from __future__ import annotations

from kelvin.types import Case, PerturbationBatch


class ReorderGenerator:
    kind = "reorder"

    def generate(
        self,
        case: Case,
        peer_cases: list[Case],
        *,
        seed: int,
        governing_types: list[str],
    ) -> PerturbationBatch:
        raise NotImplementedError("reorder generator arrives in PR 2")
