"""Score-anchor reference pipelines for Kelvin v0.4.0 maturity calibration.

Each pipeline ships as a deterministic-ish (one is intentionally
stochastic) Python module runnable as

    python -m kelvin.reference_pipelines.<name> --input X --output Y

and conforming to the existing Kelvin pipeline contract: read a
markdown case at `--input`, write a JSON object containing
`stage_assessment` to `--output`.

The five anchors and their target maturity scores:

    constant.py            → 1  (no rule reading; flat output)
    brittle.py             → 2  (deterministic but fragile to reorder)
    mid_issue.py           → 4  (moderate stochasticity + missing axis)
    one_moderate_issue.py  → 7  (clean except risk-axis blindness)
    grounded_oracle.py     → 10 (rule-tracking, drift-free)

These anchors are used by `kelvin/score.py` to FIT the per-axis
isotonic calibration. Adding or modifying a reference pipeline
INVALIDATES the calibration and requires re-running the calibration
loop in `experiments/v040_phase1_calibration/`.
"""

from __future__ import annotations

# Public registry — useful for tests and the calibration script.
ANCHOR_NAMES: tuple[str, ...] = (
    "constant",
    "brittle",
    "mid_issue",
    "one_moderate_issue",
    "grounded_oracle",
)

ANCHOR_TARGETS: dict[str, int] = {
    "constant":           1,
    "brittle":            2,
    "mid_issue":          4,
    "one_moderate_issue": 7,
    "grounded_oracle":    10,
}
