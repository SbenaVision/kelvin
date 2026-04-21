"""Perturbation generators.

`PerturbationGenerator` is a Protocol so v2 semantic-swap can drop in
without touching the runner.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from kelvin.types import Case, PerturbationBatch, PerturbationKind


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
