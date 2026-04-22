from __future__ import annotations

from pathlib import Path

from kelvin.perturbations.pad_length import PadLengthGenerator
from kelvin.types import Case, Unit


def _unit(type_: str, content: str, idx: int) -> Unit:
    return Unit(type=type_, content=content, raw_header=type_.replace("_", " ").title(), index=idx)


def _case(name: str, units: list[Unit], preamble: str = "") -> Case:
    return Case(name=name, source_path=Path(f"{name}.md"), preamble=preamble, units=units)


class TestPadLength:
    def test_produces_three_variants(self) -> None:
        target = _case("acme", [_unit("interview", "A", 0)])
        batch = PadLengthGenerator().generate(
            target, [target], seed=0, governing_types=[]
        )
        assert len(batch.perturbations) == 3
        for p in batch.perturbations:
            assert p.kind == "pad_length"
            assert p.variant_id.startswith("pad_length-")
            assert 2 <= p.notes["insert_count"] <= 4
            assert p.notes["total_chars"] > 0

    def test_runs_with_no_peer_cases(self) -> None:
        # Core differentiator from pad_content: pad_length does not need peers.
        # Single-case runs still produce the full 3 variants.
        target = _case("acme", [_unit("interview", "A", 0)])
        batch = PadLengthGenerator().generate(
            target, [target], seed=0, governing_types=[]
        )
        assert len(batch.perturbations) == 3
        assert batch.warnings == []

    def test_filler_uses_reference_note_header(self) -> None:
        target = _case("acme", [_unit("interview", "A", 0)])
        batch = PadLengthGenerator().generate(
            target, [target], seed=0, governing_types=[]
        )
        for p in batch.perturbations:
            assert "## Reference Note" in p.rendered_markdown

    def test_filler_does_not_reference_peer_cases(self) -> None:
        # pad_length must not import factual content from other cases — that's
        # pad_content's job. Filler comes from a fixed neutral bank only.
        peer = _case("other", [_unit("interview", "PEER_SECRET_TOKEN", 0)])
        target = _case("acme", [_unit("interview", "A", 0)])
        batch = PadLengthGenerator().generate(
            target, [target, peer], seed=0, governing_types=[]
        )
        for p in batch.perturbations:
            assert "PEER_SECRET_TOKEN" not in p.rendered_markdown

    def test_deterministic_given_same_seed(self) -> None:
        target = _case("acme", [_unit("interview", "A", 0)])
        a = PadLengthGenerator().generate(target, [target], seed=7, governing_types=[])
        b = PadLengthGenerator().generate(target, [target], seed=7, governing_types=[])
        assert [p.rendered_markdown for p in a.perturbations] == [
            p.rendered_markdown for p in b.perturbations
        ]

    def test_different_seeds_give_different_results(self) -> None:
        target = _case("acme", [_unit("interview", "A", 0)])
        a = PadLengthGenerator().generate(target, [target], seed=0, governing_types=[])
        b = PadLengthGenerator().generate(target, [target], seed=999, governing_types=[])
        assert [p.rendered_markdown for p in a.perturbations] != [
            p.rendered_markdown for p in b.perturbations
        ]

    def test_preamble_preserved(self) -> None:
        target = _case(
            "acme",
            [_unit("interview", "A", 0)],
            preamble="Acme preamble.",
        )
        batch = PadLengthGenerator().generate(
            target, [target], seed=0, governing_types=[]
        )
        for p in batch.perturbations:
            assert p.rendered_markdown.startswith("Acme preamble.")

    def test_inserted_notes_record_position_and_length(self) -> None:
        target = _case("acme", [_unit("interview", "A", 0)])
        batch = PadLengthGenerator().generate(
            target, [target], seed=0, governing_types=[]
        )
        for p in batch.perturbations:
            for entry in p.notes["inserted"]:
                assert "position" in entry
                assert entry["length_chars"] > 0
