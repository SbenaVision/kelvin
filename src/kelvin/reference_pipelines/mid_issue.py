"""Score-4 anchor: moderate drift + one wrong-direction sensitivity.

Spec: "moderate drift + one wrong-direction sensitivity". Implementation:

1. **Moderate drift.** With probability `_DRIFT_RATE` (≈10%) the pipeline
   returns an off-by-one stage relative to its baseline routing.
2. **Wrong-direction sensitivity.** The traction-signal axis is
   intentionally INVERTED: when the traction signal mentions
   "paying subscribers" or "annual revenue" (positive), the routing
   moves DOWNWARD to "pre-seed" instead of upward to "growth".

Failure modes hit two axes simultaneously: drift contaminates everything,
and the inverted traction reading produces wrong-direction sensitivity
on revenue-language perturbations.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import secrets
import sys


_DRIFT_RATE = 0.10


_STAGES_LADDER: tuple[str, ...] = (
    "idea",
    "pre-seed",
    "seed",
    "growth",
    "scale",
)


def section(text: str, header: str) -> str:
    pattern = rf"^##\s+{re.escape(header)}\s*\n(.*?)(?=\n##\s|\Z)"
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
    return m.group(1).lower().strip() if m else ""


def _drifted(decision: str, rng: random.Random) -> str:
    try:
        i = _STAGES_LADDER.index(decision)
    except ValueError:
        return decision
    if i == 0:
        return _STAGES_LADDER[1]
    if i == len(_STAGES_LADDER) - 1:
        return _STAGES_LADDER[-2]
    return _STAGES_LADDER[i + (1 if rng.random() < 0.5 else -1)]


def _grounded_with_inverted_traction(text: str) -> str:
    """Like grounded routing, but with TRACTION axis inverted: positive
    traction signals push the decision DOWN, not up."""
    gate = section(text, "Gate Rule")
    traction = section(text, "Traction Signal")

    # Scale (unchanged from grounded).
    if (
        "advance to scale" in gate
        and "all conditions are met" in gate
        and ("annual revenue run-rate" in gate or "arr" in gate)
    ):
        return "scale"
    # Idea (unchanged).
    if (
        "none of these conditions are currently met" in gate
        or ("no users" in traction and "no validation" in traction)
    ):
        return "idea"
    # WRONG-DIRECTION: positive traction signals → pre-seed (not growth).
    positive_traction = (
        "paying subscribers" in traction
        or "annual revenue" in traction
    )
    if "all conditions are met" in gate:
        if positive_traction:
            return "pre-seed"  # ← INVERTED: real growth signal becomes downgrade
        return "seed"
    if "some conditions are met" in gate or "loi" in gate:
        return "pre-seed"
    return "pre-seed"


def assess(text: str, rng: random.Random) -> str:
    base = _grounded_with_inverted_traction(text)
    if rng.random() < _DRIFT_RATE:
        return _drifted(base, rng)
    return base


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    rng = random.Random(secrets.token_bytes(16))
    with open(args.input, encoding="utf-8") as f:
        text = f.read()
    decision = assess(text, rng)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"stage_assessment": decision}, f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
