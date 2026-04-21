"""Reorder perturbation.

Shuffle the unit order within the case. Preamble stays pinned at the top.
Deterministic by seed. If a case has fewer than 2 units, reorder is skipped.
"""

from __future__ import annotations

from kelvin.parser import render_case
from kelvin.perturbations import rng_for
from kelvin.types import Case, Perturbation, PerturbationBatch

TARGET_COUNT = 3


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
        warnings: list[str] = []
        caps: list[str] = []

        if len(case.units) < 2:
            warnings.append(
                f"{case.name}: reorder skipped — case has {len(case.units)} unit(s), need \u22652"
            )
            return PerturbationBatch(perturbations=[], warnings=warnings, caps=caps)

        rng = rng_for(seed, "reorder", case.name)
        perturbations: list[Perturbation] = []

        for i in range(TARGET_COUNT):
            shuffled = list(case.units)
            # Reshuffle until we have a non-identity permutation. With n>=2 this
            # terminates quickly (50% for n=2, ~1 try for n>=3).
            for _attempt in range(16):
                rng.shuffle(shuffled)
                if [u.index for u in shuffled] != [u.index for u in case.units]:
                    break

            variant_id = f"reorder-{i + 1:02d}"
            perturbations.append(
                Perturbation(
                    case_name=case.name,
                    kind="reorder",
                    variant_id=variant_id,
                    rendered_markdown=render_case(case.preamble, shuffled),
                    notes={"order": [u.index for u in shuffled]},
                )
            )

        return PerturbationBatch(perturbations=perturbations, warnings=warnings, caps=caps)
