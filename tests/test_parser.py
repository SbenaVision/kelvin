from __future__ import annotations

from pathlib import Path

from kelvin.parser import (
    discover_unit_types,
    load_cases,
    normalize_type,
    parse_case,
    render_case,
)


def write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


class TestNormalizeType:
    def test_lowercases(self) -> None:
        assert normalize_type("Interview") == "interview"

    def test_trims_whitespace(self) -> None:
        assert normalize_type("  Interview  ") == "interview"

    def test_collapses_multiple_spaces_to_single_underscore(self) -> None:
        assert normalize_type("Gate  Rule") == "gate_rule"

    def test_whitespace_to_underscore(self) -> None:
        assert normalize_type("Gate Rule") == "gate_rule"

    def test_mixed_case_and_spaces(self) -> None:
        assert normalize_type("  BUDGET   Assumption ") == "budget_assumption"

    def test_tabs_are_whitespace(self) -> None:
        assert normalize_type("Gate\tRule") == "gate_rule"


class TestParseCase:
    def test_file_with_no_headers_has_empty_units(self, tmp_path: Path) -> None:
        p = write(tmp_path / "acme.md", "Just preamble.\n")
        case = parse_case(p)
        assert case.name == "acme"
        assert case.units == []
        assert case.preamble == "Just preamble."

    def test_empty_file_has_no_units_and_empty_preamble(self, tmp_path: Path) -> None:
        p = write(tmp_path / "empty.md", "")
        case = parse_case(p)
        assert case.preamble == ""
        assert case.units == []

    def test_single_unit_no_preamble(self, tmp_path: Path) -> None:
        p = write(tmp_path / "acme.md", "## Interview\nHello.\n")
        case = parse_case(p)
        assert case.preamble == ""
        assert len(case.units) == 1
        assert case.units[0].type == "interview"
        assert case.units[0].content == "Hello."
        assert case.units[0].raw_header == "Interview"
        assert case.units[0].index == 0

    def test_preamble_captured_before_first_header(self, tmp_path: Path) -> None:
        p = write(
            tmp_path / "acme.md",
            "Preamble line 1.\nPreamble line 2.\n\n## Interview\nBody.\n",
        )
        case = parse_case(p)
        assert case.preamble == "Preamble line 1.\nPreamble line 2."
        assert len(case.units) == 1
        assert case.units[0].content == "Body."

    def test_multiple_units_indexed_in_order(self, tmp_path: Path) -> None:
        p = write(
            tmp_path / "acme.md",
            (
                "## Interview\n"
                "First.\n"
                "\n"
                "## Interview\n"
                "Second.\n"
                "\n"
                "## Gate Rule\n"
                "Rule content.\n"
            ),
        )
        case = parse_case(p)
        assert [u.type for u in case.units] == ["interview", "interview", "gate_rule"]
        assert [u.index for u in case.units] == [0, 1, 2]
        assert [u.content for u in case.units] == ["First.", "Second.", "Rule content."]

    def test_headers_with_varied_casing_and_spacing_normalize_equal(
        self, tmp_path: Path
    ) -> None:
        p = write(
            tmp_path / "acme.md",
            "## interview\nA.\n\n## INTERVIEW\nB.\n\n## Interview\nC.\n",
        )
        case = parse_case(p)
        assert [u.type for u in case.units] == ["interview", "interview", "interview"]

    def test_header_with_trailing_whitespace_normalizes(self, tmp_path: Path) -> None:
        # "## Interview  " with trailing spaces/tab should still parse to type "interview".
        p = write(
            tmp_path / "acme.md",
            "## Interview  \nA.\n\n## Interview\t\nB.\n",
        )
        case = parse_case(p)
        assert [u.type for u in case.units] == ["interview", "interview"]
        assert [u.raw_header for u in case.units] == ["Interview", "Interview"]

    def test_empty_section_produces_unit_with_empty_content(self, tmp_path: Path) -> None:
        # Back-to-back headers: first unit has empty body.
        p = write(
            tmp_path / "acme.md",
            "## Interview\n## Gate Rule\nRule body.\n",
        )
        case = parse_case(p)
        assert len(case.units) == 2
        assert case.units[0].type == "interview"
        assert case.units[0].content == ""
        assert case.units[1].type == "gate_rule"
        assert case.units[1].content == "Rule body."

    def test_section_with_only_blank_lines_has_empty_content(self, tmp_path: Path) -> None:
        # A header followed only by blank lines before the next header.
        p = write(
            tmp_path / "acme.md",
            "## Interview\n\n\n\n## Gate Rule\nRule.\n",
        )
        case = parse_case(p)
        assert case.units[0].content == ""
        assert case.units[1].content == "Rule."

    def test_multi_paragraph_unit_content_preserved(self, tmp_path: Path) -> None:
        p = write(
            tmp_path / "acme.md",
            (
                "## Interview\n"
                "Paragraph one.\n"
                "\n"
                "Paragraph two.\n"
                "\n"
                "Paragraph three.\n"
                "\n"
                "## Gate Rule\n"
                "Rule.\n"
            ),
        )
        case = parse_case(p)
        assert len(case.units) == 2
        interview_content = case.units[0].content
        assert "Paragraph one." in interview_content
        assert "Paragraph two." in interview_content
        assert "Paragraph three." in interview_content
        # Paragraph structure (blank-line separation) is preserved inside the body.
        assert "\n\n" in interview_content

    def test_extra_blank_lines_between_sections_do_not_leak(self, tmp_path: Path) -> None:
        # Multiple blank lines between sections shouldn't be captured in unit content.
        p = write(
            tmp_path / "acme.md",
            "## Interview\nA.\n\n\n\n\n## Gate Rule\nB.\n\n\n",
        )
        case = parse_case(p)
        assert case.units[0].content == "A."
        assert case.units[1].content == "B."

    def test_trailing_whitespace_on_content_lines_is_stripped(self, tmp_path: Path) -> None:
        # Trailing whitespace at the very end of a unit's body block should be stripped.
        p = write(
            tmp_path / "acme.md",
            "## Interview\nA.   \n\n## Gate Rule\nB.\t\t\n",
        )
        case = parse_case(p)
        # End-of-body trailing whitespace removed by the strip() in parse_case.
        assert case.units[0].content.rstrip() == case.units[0].content
        assert case.units[1].content.rstrip() == case.units[1].content

    def test_preserves_raw_header_for_rerender(self, tmp_path: Path) -> None:
        p = write(tmp_path / "acme.md", "## Gate Rule\nBody.\n")
        case = parse_case(p)
        assert case.units[0].raw_header == "Gate Rule"

    def test_ignores_deeper_level_headers(self, tmp_path: Path) -> None:
        p = write(
            tmp_path / "acme.md",
            "## Interview\nText.\n### Subheading\nMore text.\n",
        )
        case = parse_case(p)
        assert len(case.units) == 1
        assert "### Subheading" in case.units[0].content

    def test_ignores_top_level_h1(self, tmp_path: Path) -> None:
        p = write(
            tmp_path / "acme.md",
            "# Title (preamble)\n\n## Interview\nBody.\n",
        )
        case = parse_case(p)
        assert "# Title (preamble)" in case.preamble
        assert len(case.units) == 1

    def test_units_of_type_filter(self, tmp_path: Path) -> None:
        p = write(
            tmp_path / "acme.md",
            "## Interview\nA.\n\n## Gate Rule\nB.\n\n## Interview\nC.\n",
        )
        case = parse_case(p)
        interviews = case.units_of_type("interview")
        assert [u.content for u in interviews] == ["A.", "C."]
        assert case.units_of_type("nonexistent") == []


class TestRenderCase:
    def test_roundtrip_preserves_types_and_content(self, tmp_path: Path) -> None:
        source = (
            "Preamble.\n\n"
            "## Interview\nFirst.\n\n"
            "## Gate Rule\nRule.\n"
        )
        p = write(tmp_path / "acme.md", source)
        case = parse_case(p)
        rendered = render_case(case.preamble, case.units)
        reparsed = parse_case(write(tmp_path / "round.md", rendered))
        assert reparsed.preamble == case.preamble
        assert [u.type for u in reparsed.units] == [u.type for u in case.units]
        assert [u.content for u in reparsed.units] == [u.content for u in case.units]

    def test_render_without_preamble(self) -> None:
        from kelvin.types import Unit

        units = [Unit(type="interview", content="Body.", raw_header="Interview", index=0)]
        out = render_case("", units)
        assert out.startswith("## Interview")
        assert "Body." in out

    def test_render_empty_units_and_preamble(self) -> None:
        assert render_case("", []) == ""


class TestLoadCases:
    def test_returns_cases_sorted_by_filename(self, tmp_path: Path) -> None:
        write(tmp_path / "zeta.md", "## Interview\nZ.\n")
        write(tmp_path / "acme.md", "## Interview\nA.\n")
        cases = load_cases(tmp_path)
        assert [c.name for c in cases] == ["acme", "zeta"]

    def test_ignores_non_markdown_files(self, tmp_path: Path) -> None:
        write(tmp_path / "acme.md", "## Interview\nA.\n")
        write(tmp_path / "notes.txt", "not a case")
        cases = load_cases(tmp_path)
        assert [c.name for c in cases] == ["acme"]

    def test_missing_directory_returns_empty(self, tmp_path: Path) -> None:
        assert load_cases(tmp_path / "nope") == []


class TestDiscoverUnitTypes:
    def test_returns_sorted_unique_types(self, tmp_path: Path) -> None:
        write(tmp_path / "a.md", "## Interview\nA.\n\n## Gate Rule\nB.\n")
        write(tmp_path / "b.md", "## Budget Assumption\nC.\n\n## Interview\nD.\n")
        assert discover_unit_types(tmp_path) == [
            "budget_assumption",
            "gate_rule",
            "interview",
        ]

    def test_empty_directory_returns_empty(self, tmp_path: Path) -> None:
        assert discover_unit_types(tmp_path) == []
