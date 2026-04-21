"""Swap perturbation — to be implemented in PR 2."""

from __future__ import annotations

from kelvin.types import Case, PerturbationBatch


class SwapGenerator:
    kind = "swap"

    def generate(
        self,
        case: Case,
        peer_cases: list[Case],
        *,
        seed: int,
        governing_types: list[str],
    ) -> PerturbationBatch:
        raise NotImplementedError("swap generator arrives in PR 2")
