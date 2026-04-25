"""Score-2 anchor: brittle pipeline (flips decision on reorder).

Spec: "flips decision on reorder". Implementation reads the case's
FIRST `## <header>` and routes off that. When reorder perturbs the
unit order, "first header" changes, and the decision flips.

Deterministic. No drift. Failure mode: equivalence axis broken.
"""

from __future__ import annotations

import argparse
import json
import re
import sys


def assess(text: str) -> str:
    m = re.search(r"^##\s+([^\n]+)", text, re.MULTILINE)
    first_header = m.group(1).strip().lower() if m else ""
    if "gate rule" in first_header:
        return "growth"
    if "traction" in first_header:
        return "seed"
    return "pre-seed"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    with open(args.input, encoding="utf-8") as f:
        text = f.read()
    decision = assess(text)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"stage_assessment": decision}, f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
