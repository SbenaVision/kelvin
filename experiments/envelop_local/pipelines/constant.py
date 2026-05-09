#!/usr/bin/env python3
"""Constant pipeline — always emits `verdict = "No-Go"`.

The §3.4 degenerate. Invariance 1.0 (output never moves under any perturbation)
and Sensitivity 0.0 (output also doesn't move on governing-unit swaps), so the
Kelvin score K lands at exactly 1.0. Serves as the noise floor for the
paired signal.
"""
from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"verdict": "No-Go"}, f)
    print("constant: verdict=No-Go", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
