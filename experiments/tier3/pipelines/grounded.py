#!/usr/bin/env python3
"""Rule-based grounded stand-in pipeline for the Tier 3 experiment.

Reads a Kelvin case markdown and emits a scalar `stage_assessment` by
matching keywords in the `## Gate Rule` section and cross-referencing the
`## Traction Signal` section. Deterministic, zero-cost, reproducible —
no LLM, no network. Serves as a controllable "grounded" comparator in the
grounded-vs-degenerate comparison; see experiments/tier3/README.md for
the scope and limitations of this stand-in.

The routing here is simple *by design*: Kelvin perturbations should still
produce (high invariance, high sensitivity) because the decision genuinely
depends on `## Gate Rule` content, not on presentation order. If the
routing below gets clever enough to read surrounding context, the
sensitivity signal will pick it up; if too brittle, the invariance signal
will. Both outcomes are informative.
"""

from __future__ import annotations

import argparse
import json
import re
import sys


def section(text: str, header: str) -> str:
    """Return the body of a `## <header>` section, lowercased, or '' if absent."""
    pattern = rf"^##\s+{re.escape(header)}\s*\n(.*?)(?=\n##\s|\Z)"
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
    return m.group(1).lower().strip() if m else ""


def assess(text: str) -> str:
    gate = section(text, "Gate Rule")
    traction = section(text, "Traction Signal")

    # Stage rails probe §3.4's paired-signal prediction:
    #   - gate_rule content drives the decision (→ sensitivity)
    #   - traction content refines but only when gate says conditions are met
    #   - presentation order must not matter (→ invariance)

    # Scale — advance-to-scale language AND all-conditions-met AND real ARR.
    if (
        "advance to scale" in gate
        and "all conditions are met" in gate
        and ("annual revenue run-rate" in gate or "arr" in gate)
    ):
        return "scale"

    # Idea — explicit non-satisfaction, in either section.
    if (
        "none of these conditions are currently met" in gate
        or ("no users" in traction and "no validation" in traction)
    ):
        return "idea"

    # Growth — conditions met AND durable revenue evidence in gate or traction.
    if "all conditions are met" in gate and (
        "paying subscribers" in gate
        or "paying subscribers" in traction
        or "annual revenue" in gate
        or "annual revenue" in traction
    ):
        return "growth"

    # Seed — conditions met (founder capital + demand + active usage) but no
    # durable-revenue language.
    if "all conditions are met" in gate:
        return "seed"

    # Pre-seed — partial signal: LOIs, beta, some conditions met, or paid capital
    # without durable revenue.
    if (
        "some conditions are met" in gate
        or "loi" in gate
        or "design partners" in gate
        or "beta" in traction
    ):
        return "pre-seed"

    # Default.
    return "pre-seed"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        text = f.read()
    stage = assess(text)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"stage_assessment": stage}, f)
    print(f"grounded: stage_assessment={stage}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
