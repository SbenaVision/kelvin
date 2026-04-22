#!/usr/bin/env python3
"""Degenerate pipeline for the Tier 3 experiment.

Returns a constant `stage_assessment` regardless of input. Operationally
useless by design — this is the pipeline whitepaper §3.4 warns about:
invariance 1.0 is trivially satisfied (output never moves under any
perturbation) while sensitivity is 0.0 (output also never moves under
governing-unit substitution, which is the whole point of the diagnostic).
The paired Kelvin score K should land at exactly 1.0 — matching the
test_constant_output_pipeline prediction pinned in tests/test_scorer.py.
"""

from __future__ import annotations

import argparse
import json
import sys


CONSTANT_DECISION = "pre-seed"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"stage_assessment": CONSTANT_DECISION}, f)
    print(f"degenerate: stage_assessment={CONSTANT_DECISION}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
