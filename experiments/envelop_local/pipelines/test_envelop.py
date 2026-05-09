"""Unit tests for envelop.py focal-section disambiguation.

Reproduces the Kelvin-observed bug where SECTION_RE.search picked the first
`## Gate Rule` after pad_content injected a peer's Gate Rule ahead of the
focal one, causing Invariance to drop from 1.000 to 0.875.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from envelop import parse_gate_rule

CASES_DIR = Path(__file__).resolve().parent.parent / "cases"

BRAVO_FOCAL_BODY = (
    "\n"
    "Goal frame: growth\n"
    "Stage profile: growth\n"
    "Dimensions: P=4 M=5 C=4 D=5 L=4 F=4 E=4"
)

PEER_GATE_RULE = (
    "## Gate Rule\n"
    "\n"
    "Goal frame: lifestyle\n"
    "Stage profile: early\n"
    "Dimensions: P=3 M=3 C=3 D=3 L=3 F=3 E=3\n"
)

BRAVO_GATE_RULE = (
    "## Gate Rule\n"
    "\n"
    "Goal frame: growth\n"
    "Stage profile: growth\n"
    "Dimensions: P=4 M=5 C=4 D=5 L=4 F=4 E=4\n"
)


class FocalGateRuleTests(unittest.TestCase):
    def test_single_gate_rule_parses(self):
        text = "## Intro\n\nfiller\n\n" + BRAVO_GATE_RULE
        parsed = parse_gate_rule(text)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["goal_frame"], "growth")
        self.assertEqual(parsed["stage_profile"], "growth")
        self.assertEqual(parsed["dimensions"]["M"], 5)

    def test_peer_before_focal_picks_focal_when_case_inferable(self):
        # Simulate Kelvin's perturbation input path so the wrapper can
        # identify the focal case from the directory structure.
        text = PEER_GATE_RULE + "\n## Filler\n\nx\n\n" + BRAVO_GATE_RULE
        fake_path = Path("/tmp/run/bravo/perturbations/pad_content-03/input.md")
        parsed = parse_gate_rule(text, fake_path)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["goal_frame"], "growth")
        self.assertEqual(parsed["stage_profile"], "growth")
        self.assertEqual(
            parsed["dimensions"],
            {"P": 4, "M": 5, "C": 4, "D": 5, "L": 4, "F": 4, "E": 4},
        )

    def test_peer_after_focal_still_picks_focal(self):
        text = BRAVO_GATE_RULE + "\n## Filler\n\nx\n\n" + PEER_GATE_RULE
        fake_path = Path("/tmp/run/bravo/perturbations/pad_content-02/input.md")
        parsed = parse_gate_rule(text, fake_path)
        self.assertEqual(parsed["stage_profile"], "growth")
        self.assertEqual(parsed["dimensions"]["M"], 5)

    def test_no_path_context_falls_back_to_first_match(self):
        # Preserves pre-fix behavior when caller doesn't pass input_path.
        text = PEER_GATE_RULE + "\n" + BRAVO_GATE_RULE
        parsed = parse_gate_rule(text)
        self.assertEqual(parsed["stage_profile"], "early")
        self.assertEqual(parsed["dimensions"]["M"], 3)

    def test_missing_gate_rule_returns_none(self):
        self.assertIsNone(parse_gate_rule("## Intro\n\nno rule here\n"))

    def test_baseline_case_file_is_reachable(self):
        # Regression: the focal-body lookup depends on CASES_DIR resolution.
        # If this breaks, every perturbation silently falls back to first-match.
        self.assertTrue((CASES_DIR / "bravo.md").exists(),
                        f"expected bravo.md in {CASES_DIR}")


if __name__ == "__main__":
    unittest.main()
