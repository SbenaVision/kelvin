"""Pad perturbation — to be implemented in PR 2."""

from __future__ import annotations

from kelvin.types import Case, PerturbationBatch


class PadGenerator:
    kind = "pad"

    def generate(
        self,
        case: Case,
        peer_cases: list[Case],
        *,
        seed: int,
        governing_types: list[str],
    ) -> PerturbationBatch:
        raise NotImplementedError("pad generator arrives in PR 2")
