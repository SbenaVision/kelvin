"""Python port of Envelop's computeVVS (supabase/functions/venture-assessment/vvs-engine.ts).

Pure, deterministic scoring over 7 dimensions (P/M/C/D/L/F/E) given a goal_frame
(lifestyle/growth/moonshot) and stage_profile (early/growth). Returns a band
and a derived Go/Reshape/No-Go verdict.

The verdict mapping is the local-eval addition — Envelop's production engine
emits a band label and goal_interpretation; the three-way verdict here is a
simple rule over those outputs so Kelvin has a discrete decision field.
"""

from __future__ import annotations

ALL_DIMS = ("P", "M", "C", "D", "L", "F", "E")

STAGE_WEIGHTS = {
    "early":  {"P": 3, "M": 1, "C": 3, "D": 1, "L": 2, "F": 1, "E": 2},
    "growth": {"P": 2, "M": 2, "C": 2, "D": 3, "L": 2, "F": 3, "E": 2},
}
STAGE_RANGES = {
    "early":  {"min": 13, "max": 65},
    "growth": {"min": 16, "max": 80},
}

BANDS = [
    (200, 399, "Non-viable"),
    (400, 499, "Weak path to revenue"),
    (500, 599, "Possible, but major gaps"),
    (600, 699, "Promising path to first revenue"),
    (700, 749, "High probability to generate cash"),
    (750, 800, "Unusually strong cash potential"),
]

KILL_ZONE_CAP = 350


def _kill_zone(dims: dict) -> tuple[bool, str | None]:
    # Rule 1: any non-E dimension at 1.
    ones = [d for d in ALL_DIMS if d != "E" and dims[d] == 1]
    if ones:
        return True, f"Dimension(s) {','.join(ones)} scored 1"
    # Rule 2: three or more dimensions <= 2.
    weak = [d for d in ALL_DIMS if dims[d] <= 2]
    if len(weak) >= 3:
        return True, f"Compound weakness: {','.join(weak)} <= 2"
    return False, None


def _band(score: int) -> str:
    for lo, hi, label in BANDS:
        if lo <= score <= hi:
            return label
    return "Non-viable"


def compute(dims: dict, goal_frame: str, stage_profile: str) -> dict:
    """Returns {'score', 'band', 'kill_zone', 'verdict'}."""
    for d in ALL_DIMS:
        v = dims[d]
        if not isinstance(v, int) or v < 1 or v > 5:
            raise ValueError(f"dimension {d} must be int 1-5, got {v!r}")
    if stage_profile not in STAGE_WEIGHTS:
        raise ValueError(f"stage_profile must be 'early'|'growth', got {stage_profile!r}")
    if goal_frame not in ("lifestyle", "growth", "moonshot"):
        raise ValueError(f"goal_frame invalid: {goal_frame!r}")

    weights = STAGE_WEIGHTS[stage_profile]
    rng = STAGE_RANGES[stage_profile]
    weighted_index = sum(dims[d] * weights[d] for d in ALL_DIMS)

    score = round(200 + ((weighted_index - rng["min"]) / (rng["max"] - rng["min"])) * 600)
    score = max(200, min(800, score))

    kz, kz_reason = _kill_zone(dims)
    if kz and score > KILL_ZONE_CAP:
        score = KILL_ZONE_CAP

    band = _band(score)

    # Verdict derivation:
    #   score >= 600                  → Go
    #   400 <= score < 600            → Reshape
    #   score < 400 or kill-zone      → No-Go
    if kz or score < 400:
        verdict = "No-Go"
    elif score < 600:
        verdict = "Reshape"
    else:
        verdict = "Go"

    return {
        "score": score,
        "band": band,
        "kill_zone": kz,
        "kill_zone_reason": kz_reason,
        "verdict": verdict,
    }
