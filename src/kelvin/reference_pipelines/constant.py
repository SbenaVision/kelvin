"""Score-1 anchor: constant-output pipeline.

Returns the same `stage_assessment` regardless of input. Equivalent to
`experiments/tier3/pipelines/degenerate.py` and serves the same
diagnostic role: invariance is trivially 1.0 (output never moves), but
sensitivity is exactly 0.0 (output also never moves under governing-
unit substitution). Calibrated maturity: 1.

Deterministic. No drift. Sub-scores by design:

    drift = 1.0   (perfectly stable; no replay variance)
    sens  = 0.0   (broken: rule changes ignored)
    eq    = 1.0   (perfectly invariant — for the wrong reason)
    MIN   = 0.0  → maturity = 1
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
