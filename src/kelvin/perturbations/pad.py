"""Pad-content perturbation.

Insert 2-4 units drawn from other cases (never self-sampled) into the current
case at random positions. 3 variants per case. Skipped if the peer pool has
fewer than 2 units; the per-variant insert count caps at pool size when the
pool has fewer than 4.

Probes *distractor-content robustness*: does the decision drift when the
added units describe different entities or scenarios? Paired with
`PadLengthGenerator`, which probes presentation-length robustness using
neutral filler that shares no factual content with any case.
"""

from __future__ import annotations

from kelvin.parser import render_case
from kelvin.perturbations import peer_pool, rng_for
from kelvin.types import Case, Perturbation, PerturbationBatch

TARGET_COUNT = 3
MIN_INSERT = 2
MAX_INSERT = 4


class PadContentGenerator:
    kind = "pad_content"

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

        pool = peer_pool(case, peer_cases)
        if len(pool) < MIN_INSERT:
            warnings.append(
                f"{case.name}: pad_content skipped — peer pool has {len(pool)} "
                f"unit(s), need \u2265{MIN_INSERT}"
            )
            return PerturbationBatch(perturbations=[], warnings=warnings, caps=caps)

        max_insert_for_case = min(MAX_INSERT, len(pool))
        if max_insert_for_case < MAX_INSERT:
            caps.append(
                f"{case.name}: pad_content insert count capped at "
                f"{max_insert_for_case} (peer pool has {len(pool)} unit(s); "
                f"target up to {MAX_INSERT})"
            )

        rng = rng_for(seed, "pad_content", case.name)
        perturbations: list[Perturbation] = []

        for i in range(TARGET_COUNT):
            insert_count = rng.randint(MIN_INSERT, max_insert_for_case)
            picked = rng.sample(pool, insert_count)
            new_units = list(case.units)
            inserted_notes: list[dict] = []
            for source_case, unit in picked:
                pos = rng.randint(0, len(new_units))
                new_units.insert(pos, unit)
                inserted_notes.append(
                    {
                        "from_case": source_case,
                        "type": unit.type,
                        "source_index": unit.index,
                        "position": pos,
                    }
                )

            variant_id = f"pad_content-{i + 1:02d}"
            perturbations.append(
                Perturbation(
                    case_name=case.name,
                    kind="pad_content",
                    variant_id=variant_id,
                    rendered_markdown=render_case(case.preamble, new_units),
                    notes={
                        "insert_count": insert_count,
                        "inserted": inserted_notes,
                    },
                )
            )

        return PerturbationBatch(perturbations=perturbations, warnings=warnings, caps=caps)
