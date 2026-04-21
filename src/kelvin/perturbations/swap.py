"""Swap perturbation.

Replace one unit of a governing type in the case with a same-type unit drawn
from a peer case (without replacement from the peer pool). Target is 3 swaps
per governing type per case, capped by available case positions and peer
units.
"""

from __future__ import annotations

from kelvin.parser import render_case
from kelvin.perturbations import peer_pool, rng_for
from kelvin.types import Case, Perturbation, PerturbationBatch, Unit

TARGET_COUNT = 3


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
        warnings: list[str] = []
        caps: list[str] = []
        perturbations: list[Perturbation] = []

        for gtype in governing_types:
            case_units = case.units_of_type(gtype)
            if not case_units:
                warnings.append(
                    f"{case.name}: swap skipped for type '{gtype}' — "
                    f"case has no units of this type"
                )
                continue

            pool = peer_pool(case, peer_cases, type_filter=gtype)
            if not pool:
                warnings.append(
                    f"{case.name}: swap skipped for type '{gtype}' — "
                    f"peer pool has no units of this type"
                )
                continue

            effective = min(TARGET_COUNT, len(case_units), len(pool))
            if effective < TARGET_COUNT:
                caps.append(
                    f"{case.name}: swap-{gtype} capped at {effective} "
                    f"(case positions={len(case_units)}, peer pool={len(pool)}, "
                    f"target={TARGET_COUNT})"
                )

            rng = rng_for(seed, "swap", case.name, gtype)
            # Deterministic "without replacement" selection from both the case's
            # governing positions and the peer pool.
            target_positions: list[Unit] = rng.sample(case_units, effective)
            peer_choices: list[tuple[str, Unit]] = rng.sample(pool, effective)

            for i, (target_unit, (peer_case, peer_unit)) in enumerate(
                zip(target_positions, peer_choices, strict=True)
            ):
                new_units: list[Unit] = []
                for u in case.units:
                    if u.index == target_unit.index:
                        # Replace: keep position in the case; take peer's header
                        # and content since the swap is a content replacement.
                        new_units.append(
                            Unit(
                                type=peer_unit.type,
                                content=peer_unit.content,
                                raw_header=peer_unit.raw_header,
                                index=target_unit.index,
                            )
                        )
                    else:
                        new_units.append(u)

                variant_id = f"swap-{gtype}-{i + 1:02d}"
                perturbations.append(
                    Perturbation(
                        case_name=case.name,
                        kind="swap",
                        variant_id=variant_id,
                        rendered_markdown=render_case(case.preamble, new_units),
                        notes={
                            "governing_type": gtype,
                            "position_replaced": target_unit.index,
                            "original_header": target_unit.raw_header,
                            "from_case": peer_case,
                            "peer_source_index": peer_unit.index,
                        },
                    )
                )

        return PerturbationBatch(perturbations=perturbations, warnings=warnings, caps=caps)
