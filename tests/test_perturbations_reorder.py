from __future__ import annotations

from pathlib import Path

from kelvin.perturbations.reorder import ReorderGenerator
from kelvin.types import Case, Unit


def _unit(type_: str, content: str, idx: int) -> Unit:
    return Unit(type=type_, content=content, raw_header=type_.replace("_", " ").title(), index=idx)


def _case(name: str, units: list[Unit], preamble: str = "") -> Case:
    return Case(name=name, source_path=Path(f"{name}.md"), preamble=preamble, units=units)


class TestReorder:
    def test_produces_three_variants(self) -> None:
        case = _case(
            "acme",
            [
                _unit("interview", "I1", 0),
                _unit("interview", "I2", 1),
                _unit("gate_rule", "G1", 2),
            ],
        )
        batch = ReorderGenerator().generate(
            case, [case], seed=0, governing_types=["gate_rule"]
        )
        assert len(batch.perturbations) == 3
        assert [p.variant_id for p in batch.perturbations] == [
            "reorder-01",
            "reorder-02",
            "reorder-03",
        ]
        for p in batch.perturbations:
            assert p.kind == "reorder"
            assert p.case_name == "acme"
            assert "order" in p.notes

    def test_avoids_identity_permutation(self) -> None:
        case = _case(
            "acme",
            [_unit("interview", "I1", 0), _unit("interview", "I2", 1), _unit("gate_rule", "G1", 2)],
        )
        batch = ReorderGenerator().generate(case, [case], seed=0, governing_types=[])
        original_order = [0, 1, 2]
        for p in batch.perturbations:
            assert p.notes["order"] != original_order

    def test_deterministic_given_same_seed(self) -> None:
        case = _case(
            "acme",
            [
                _unit("interview", "I1", 0),
                _unit("interview", "I2", 1),
                _unit("gate_rule", "G1", 2),
                _unit("budget_assumption", "B1", 3),
            ],
        )
        a = ReorderGenerator().generate(case, [case], seed=42, governing_types=[])
        b = ReorderGenerator().generate(case, [case], seed=42, governing_types=[])
        assert [p.notes["order"] for p in a.perturbations] == [
            p.notes["order"] for p in b.perturbations
        ]

    def test_different_seeds_give_different_orders(self) -> None:
        case = _case(
            "acme",
            [_unit("a", f"u{i}", i) for i in range(5)],
        )
        a = ReorderGenerator().generate(case, [case], seed=0, governing_types=[])
        b = ReorderGenerator().generate(case, [case], seed=999, governing_types=[])
        assert [p.notes["order"] for p in a.perturbations] != [
            p.notes["order"] for p in b.perturbations
        ]

    def test_preamble_preserved_in_rendered_markdown(self) -> None:
        case = _case(
            "acme",
            [_unit("interview", "I1", 0), _unit("interview", "I2", 1)],
            preamble="Preamble text.",
        )
        batch = ReorderGenerator().generate(case, [case], seed=0, governing_types=[])
        for p in batch.perturbations:
            assert p.rendered_markdown.startswith("Preamble text.")

    def test_skipped_when_case_has_zero_units(self) -> None:
        case = _case("empty", [])
        batch = ReorderGenerator().generate(case, [case], seed=0, governing_types=[])
        assert batch.perturbations == []
        assert len(batch.warnings) == 1
        assert "reorder skipped" in batch.warnings[0]

    def test_skipped_when_case_has_one_unit(self) -> None:
        case = _case("single", [_unit("interview", "only", 0)])
        batch = ReorderGenerator().generate(case, [case], seed=0, governing_types=[])
        assert batch.perturbations == []
        assert len(batch.warnings) == 1
        assert "reorder skipped" in batch.warnings[0]
