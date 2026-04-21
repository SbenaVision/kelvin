from __future__ import annotations

from pathlib import Path

from kelvin.perturbations.pad import PadGenerator
from kelvin.types import Case, Unit


def _unit(type_: str, content: str, idx: int) -> Unit:
    return Unit(type=type_, content=content, raw_header=type_.replace("_", " ").title(), index=idx)


def _case(name: str, units: list[Unit], preamble: str = "") -> Case:
    return Case(name=name, source_path=Path(f"{name}.md"), preamble=preamble, units=units)


def _peers_with_n_units(total: int) -> list[Case]:
    """Build peer cases whose combined unit count equals `total`."""
    cases: list[Case] = []
    remaining = total
    i = 0
    while remaining > 0:
        n = min(remaining, 3)
        cases.append(
            _case(
                f"peer{i}",
                [_unit("interview", f"peer{i}-u{j}", j) for j in range(n)],
            )
        )
        remaining -= n
        i += 1
    return cases


class TestPad:
    def test_produces_three_variants_with_ample_pool(self) -> None:
        target = _case("acme", [_unit("interview", "A", 0)])
        peers = _peers_with_n_units(10)
        batch = PadGenerator().generate(
            target, [target, *peers], seed=0, governing_types=[]
        )
        assert len(batch.perturbations) == 3
        for p in batch.perturbations:
            assert p.kind == "pad"
            assert p.variant_id.startswith("pad-")
            assert 2 <= p.notes["insert_count"] <= 4

    def test_does_not_sample_from_self(self) -> None:
        target = _case(
            "acme",
            [_unit("interview", f"ACME_U{i}", i) for i in range(5)],
        )
        peers = _peers_with_n_units(10)
        batch = PadGenerator().generate(
            target, [target, *peers], seed=0, governing_types=[]
        )
        for p in batch.perturbations:
            for inserted in p.notes["inserted"]:
                assert inserted["from_case"] != "acme"

    def test_deterministic_given_same_seed(self) -> None:
        target = _case("acme", [_unit("interview", "A", 0)])
        peers = _peers_with_n_units(10)
        a = PadGenerator().generate(target, [target, *peers], seed=7, governing_types=[])
        b = PadGenerator().generate(target, [target, *peers], seed=7, governing_types=[])
        assert [p.notes for p in a.perturbations] == [p.notes for p in b.perturbations]

    def test_different_seeds_give_different_results(self) -> None:
        target = _case("acme", [_unit("interview", "A", 0)])
        peers = _peers_with_n_units(10)
        a = PadGenerator().generate(target, [target, *peers], seed=0, governing_types=[])
        b = PadGenerator().generate(target, [target, *peers], seed=999, governing_types=[])
        assert [p.notes for p in a.perturbations] != [p.notes for p in b.perturbations]

    def test_caps_insert_count_when_pool_below_four(self) -> None:
        target = _case("acme", [_unit("interview", "A", 0)])
        peers = _peers_with_n_units(3)
        batch = PadGenerator().generate(
            target, [target, *peers], seed=0, governing_types=[]
        )
        assert len(batch.perturbations) == 3
        for p in batch.perturbations:
            assert p.notes["insert_count"] <= 3
        assert len(batch.caps) == 1
        assert "capped at 3" in batch.caps[0]

    def test_pool_of_two_produces_two_inserts_per_variant(self) -> None:
        target = _case("acme", [_unit("interview", "A", 0)])
        peers = _peers_with_n_units(2)
        batch = PadGenerator().generate(
            target, [target, *peers], seed=0, governing_types=[]
        )
        assert len(batch.perturbations) == 3
        for p in batch.perturbations:
            assert p.notes["insert_count"] == 2

    def test_skipped_when_pool_has_less_than_two_units(self) -> None:
        target = _case("acme", [_unit("interview", "A", 0)])
        peers = _peers_with_n_units(1)
        batch = PadGenerator().generate(
            target, [target, *peers], seed=0, governing_types=[]
        )
        assert batch.perturbations == []
        assert len(batch.warnings) == 1
        assert "pad skipped" in batch.warnings[0]

    def test_skipped_when_only_one_case_in_run(self) -> None:
        target = _case("acme", [_unit("interview", "A", 0), _unit("interview", "B", 1)])
        batch = PadGenerator().generate(
            target, [target], seed=0, governing_types=[]
        )
        # Pool is empty (no peers). Skipped with warning.
        assert batch.perturbations == []
        assert len(batch.warnings) == 1

    def test_preamble_preserved(self) -> None:
        target = _case(
            "acme",
            [_unit("interview", "A", 0)],
            preamble="Acme preamble.",
        )
        peers = _peers_with_n_units(5)
        batch = PadGenerator().generate(
            target, [target, *peers], seed=0, governing_types=[]
        )
        for p in batch.perturbations:
            assert p.rendered_markdown.startswith("Acme preamble.")
