"""Score-10 anchor: rule-tracking grounded pipeline.

The reference implementation of "what good looks like":
- reads only the `## Gate Rule` and `## Traction Signal` sections;
- decision depends on rule content (sensitive to rule changes);
- decision is invariant to presentation/order/non-governing changes;
- deterministic (no drift).

Modelled on `experiments/tier3/pipelines/grounded.py` and refined for
clean v0.4.0 calibration. Designed sub-scores:

    drift = 1.0
    sens  = 1.0
    eq    = 1.0
    MIN   = 1.0  → maturity = 10
"""

from __future__ import annotations

import argparse
import json
import re
import sys


def section(text: str, header: str) -> str:
    """Return the body of a `## <header>` section, lowercased; '' if absent.

    Matches by exact (case-insensitive) header label and stops at the
    next `## ` line or end of file.
    """
    pattern = rf"^##\s+{re.escape(header)}\s*\n(.*?)(?=\n##\s|\Z)"
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
    return m.group(1).lower().strip() if m else ""


def assess(text: str) -> str:
    gate = section(text, "Gate Rule")
    traction = section(text, "Traction Signal")

    # Scale — explicit advance-to-scale language anchored on revenue evidence.
    if (
        "advance to scale" in gate
        and "all conditions are met" in gate
        and ("annual revenue run-rate" in gate or "arr" in gate)
    ):
        return "scale"

    # Idea — explicit non-satisfaction in either section.
    if (
        "none of these conditions are currently met" in gate
        or ("no users" in traction and "no validation" in traction)
    ):
        return "idea"

    # Growth — conditions met AND durable revenue evidence.
    if "all conditions are met" in gate and (
        "paying subscribers" in gate
        or "paying subscribers" in traction
        or "annual revenue" in gate
        or "annual revenue" in traction
    ):
        return "growth"

    # Seed — conditions met but no durable-revenue language.
    if "all conditions are met" in gate:
        return "seed"

    # Pre-seed — partial signal in either section.
    if (
        "some conditions are met" in gate
        or "loi" in gate
        or "design partners" in gate
        or "beta" in traction
    ):
        return "pre-seed"

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
