from __future__ import annotations

from pathlib import Path

from kelvin.perturbations.swap import SwapGenerator
from kelvin.types import Case, Unit


def _unit(type_: str, content: str, idx: int) -> Unit:
    return Unit(type=type_, content=content, raw_header=type_.replace("_", " ").title(), index=idx)


def _case(name: str, units: list[Unit], preamble: str = "") -> Case:
    return Case(name=name, source_path=Path(f"{name}.md"), preamble=preamble, units=units)


class TestSwap:
    def test_produces_three_swaps_per_governing_type(self) -> None:
        target = _case(
            "acme",
            [
                _unit("interview", "I1", 0),
                _unit("gate_rule", "A_G1", 1),
                _unit("gate_rule", "A_G2", 2),
                _unit("gate_rule", "A_G3", 3),
            ],
        )
        peer = _case(
            "zeta",
            [
                _unit("gate_rule", "Z_G1", 0),
                _unit("gate_rule", "Z_G2", 1),
                _unit("gate_rule", "Z_G3", 2),
                _unit("gate_rule", "Z_G4", 3),
            ],
        )
        batch = SwapGenerator().generate(
            target, [target, peer], seed=0, governing_types=["gate_rule"]
        )
        assert len(batch.perturbations) == 3
        assert all(p.variant_id.startswith("swap-gate_rule-") for p in batch.perturbations)
        assert batch.caps == []
        for p in batch.perturbations:
            assert p.notes["governing_type"] == "gate_rule"
            assert p.notes["from_case"] == "zeta"

    def test_three_swaps_per_type_multiple_types(self) -> None:
        target = _case(
            "acme",
            [
                _unit("gate_rule", "A_G1", 0),
                _unit("gate_rule", "A_G2", 1),
                _unit("gate_rule", "A_G3", 2),
                _unit("policy_clause", "A_P1", 3),
                _unit("policy_clause", "A_P2", 4),
                _unit("policy_clause", "A_P3", 5),
            ],
        )
        peer = _case(
            "zeta",
            [
                _unit("gate_rule", "Z_G1", 0),
                _unit("gate_rule", "Z_G2", 1),
                _unit("gate_rule", "Z_G3", 2),
                _unit("policy_clause", "Z_P1", 3),
                _unit("policy_clause", "Z_P2", 4),
                _unit("policy_clause", "Z_P3", 5),
            ],
        )
        batch = SwapGenerator().generate(
            target, [target, peer], seed=0, governing_types=["gate_rule", "policy_clause"]
        )
        # 3 per type * 2 types = 6 swaps
        assert len(batch.perturbations) == 6
        by_type = {p.notes["governing_type"] for p in batch.perturbations}
        assert by_type == {"gate_rule", "policy_clause"}
        assert sum(1 for p in batch.perturbations if p.notes["governing_type"] == "gate_rule") == 3
        assert (
            sum(1 for p in batch.perturbations if p.notes["governing_type"] == "policy_clause") == 3
        )

    def test_caps_at_case_positions_when_fewer_than_three(self) -> None:
        target = _case(
            "acme",
            [_unit("gate_rule", "A_G1", 0)],  # only one governing unit
        )
        peer = _case(
            "zeta",
            [_unit("gate_rule", f"Z_G{i}", i) for i in range(5)],
        )
        batch = SwapGenerator().generate(
            target, [target, peer], seed=0, governing_types=["gate_rule"]
        )
        assert len(batch.perturbations) == 1
        assert len(batch.caps) == 1
        assert "capped at 1" in batch.caps[0]

    def test_caps_at_peer_pool_when_fewer_than_three(self) -> None:
        target = _case(
            "acme",
            [_unit("gate_rule", f"A_G{i}", i) for i in range(5)],
        )
        peer = _case(
            "zeta",
            [_unit("gate_rule", "Z_G1", 0), _unit("gate_rule", "Z_G2", 1)],
        )
        batch = SwapGenerator().generate(
            target, [target, peer], seed=0, governing_types=["gate_rule"]
        )
        assert len(batch.perturbations) == 2
        assert len(batch.caps) == 1
        assert "capped at 2" in batch.caps[0]

    def test_skipped_when_case_has_no_governing_units(self) -> None:
        target = _case(
            "acme",
            [_unit("interview", "I1", 0), _unit("budget_assumption", "B1", 1)],
        )
        peer = _case("zeta", [_unit("gate_rule", "Z_G1", 0)])
        batch = SwapGenerator().generate(
            target, [target, peer], seed=0, governing_types=["gate_rule"]
        )
        assert batch.perturbations == []
        assert len(batch.warnings) == 1
        assert "no units of this type" in batch.warnings[0]

    def test_skipped_when_peer_pool_has_no_matching_type(self) -> None:
        target = _case("acme", [_unit("gate_rule", "A_G1", 0)])
        peer = _case("zeta", [_unit("interview", "Z_I1", 0)])
        batch = SwapGenerator().generate(
            target, [target, peer], seed=0, governing_types=["gate_rule"]
        )
        assert batch.perturbations == []
        assert any("peer pool has no units of this type" in w for w in batch.warnings)

    def test_without_replacement_in_peer_pool(self) -> None:
        # Three swaps, 3 peer units — all peers used exactly once.
        target = _case("acme", [_unit("gate_rule", f"A_G{i}", i) for i in range(3)])
        peer = _case("zeta", [_unit("gate_rule", f"Z_G{i}", i) for i in range(3)])
        batch = SwapGenerator().generate(
            target, [target, peer], seed=0, governing_types=["gate_rule"]
        )
        picked_peer_indices = [p.notes["peer_source_index"] for p in batch.perturbations]
        assert sorted(picked_peer_indices) == [0, 1, 2]

    def test_without_replacement_in_case_positions(self) -> None:
        # Each of 3 swaps replaces a different governing position in the case.
        target = _case("acme", [_unit("gate_rule", f"A_G{i}", i) for i in range(5)])
        peer = _case("zeta", [_unit("gate_rule", f"Z_G{i}", i) for i in range(5)])
        batch = SwapGenerator().generate(
            target, [target, peer], seed=0, governing_types=["gate_rule"]
        )
        positions = [p.notes["position_replaced"] for p in batch.perturbations]
        assert len(set(positions)) == 3  # all distinct

    def test_deterministic_given_same_seed(self) -> None:
        target = _case("acme", [_unit("gate_rule", f"A_G{i}", i) for i in range(4)])
        peer = _case("zeta", [_unit("gate_rule", f"Z_G{i}", i) for i in range(4)])
        a = SwapGenerator().generate(
            target, [target, peer], seed=3, governing_types=["gate_rule"]
        )
        b = SwapGenerator().generate(
            target, [target, peer], seed=3, governing_types=["gate_rule"]
        )
        assert [p.notes for p in a.perturbations] == [p.notes for p in b.perturbations]

    def test_preamble_preserved(self) -> None:
        target = _case(
            "acme",
            [_unit("gate_rule", "A_G1", 0)],
            preamble="Acme preamble.",
        )
        peer = _case("zeta", [_unit("gate_rule", "Z_G1", 0)])
        batch = SwapGenerator().generate(
            target, [target, peer], seed=0, governing_types=["gate_rule"]
        )
        for p in batch.perturbations:
            assert p.rendered_markdown.startswith("Acme preamble.")
