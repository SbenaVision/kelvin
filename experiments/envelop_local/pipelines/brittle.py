#!/usr/bin/env python3
"""Brittle pipeline — reads ONLY the first section of the input.

Demonstrates classic retrieval-position bias: the decision depends on
which unit happens to appear first, so under reorder perturbations the
verdict flips even though no decision-relevant content has changed.

Rule:
  - If the first section is `## Gate Rule`, parse dimensions and route
    through computeVVS (i.e. the correct answer).
  - Otherwise, fall back to "Reshape" as a lazy default.

This is presentation-reactive by construction. When Kelvin's reorder
perturbation moves Gate Rule off the top, the output flips to "Reshape"
regardless of the underlying evidence.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from envelop import parse_gate_rule  # noqa: E402
from vvs import compute  # noqa: E402


FIRST_HEADER_RE = re.compile(r"^##\s+([^\n]+)", re.MULTILINE)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    text = Path(args.input).read_text(encoding="utf-8")
    m = FIRST_HEADER_RE.search(text)
    first = (m.group(1).strip().lower() if m else "")

    if first == "gate rule":
        parsed = parse_gate_rule(text)
        if parsed is not None:
            r = compute(parsed["dimensions"], parsed["goal_frame"], parsed["stage_profile"])
            verdict = r["verdict"]
        else:
            verdict = "Reshape"
    else:
        verdict = "Reshape"

    Path(args.output).write_text(json.dumps({"verdict": verdict}), encoding="utf-8")
    print(f"brittle: first_section={first!r} verdict={verdict}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
