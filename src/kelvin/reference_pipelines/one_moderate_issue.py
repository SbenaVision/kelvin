"""Score-7 anchor: clean except one moderate axis is broken.

Spec: "clean except one axis with moderate issue". Implementation:
grounded routing for everything EXCEPT it ignores the conditions-status
distinction ("all conditions are met" vs "some conditions are met").
That makes swap_condition perturbations on that axis invisible to the
pipeline, contributing zero sensitivity on that axis. All other axes
behave correctly.

Deterministic. No drift. Failure mode: sensitivity axis partially broken.
"""

from __future__ import annotations

import argparse
import json
import re
import sys


def section(text: str, header: str) -> str:
    pattern = rf"^##\s+{re.escape(header)}\s*\n(.*?)(?=\n##\s|\Z)"
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
    return m.group(1).lower().strip() if m else ""


def assess(text: str) -> str:
    """Routes off revenue + traction language only — conditions-status
    distinction is intentionally ignored."""
    gate = section(text, "Gate Rule")
    traction = section(text, "Traction Signal")

    # Scale — explicit advance-to-scale language anchored on revenue evidence.
    if (
        "advance to scale" in gate
        and ("annual revenue run-rate" in gate or "arr" in gate)
    ):
        return "scale"
    # Idea — only on explicit non-existence in traction.
    if "no users" in traction and "no validation" in traction:
        return "idea"
    # Growth — durable revenue evidence anywhere.
    if (
        "paying subscribers" in gate
        or "paying subscribers" in traction
        or "annual revenue" in gate
        or "annual revenue" in traction
    ):
        return "growth"
    # Seed — partial / loose signal.
    if "loi" in gate or "design partners" in gate or "beta" in traction:
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
