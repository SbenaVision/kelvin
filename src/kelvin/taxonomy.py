"""Axis taxonomy for Kelvin v0.4.0 maturity scoring.

Defines the small enumeration of orthogonal scoring AXES that the
maturity score aggregates over, and the set of perturbation FAMILIES
that must be enabled to produce a meaningful score.

Phase 1 scope: the four axes listed in the v0.4.0 spec are declared
here, but `score.py` consumes only three of them (drift, sensitivity,
equivalence) — the fourth (`wrong_direction`) is a hook for a Phase 2+
metric that doesn't yet have a v0.3.0 measurement.

Design notes:

- **Axis ≠ perturbation family.** A family (e.g., reorder) is a
  PRODUCER of measurements; an axis (e.g., equivalence) is a CATEGORY
  of behavior that the maturity score interprets. Many families
  contribute to the same axis.
- **STANDARD_SCORE_FAMILIES** is the set of v0.3.0 perturbation kinds
  the score function is calibrated against. If a user disables one
  via `kelvin.yaml`, the score is WITHHELD (per v0.4.0 spec) — the
  calibration only applies under the standard family set.
"""

from __future__ import annotations

from enum import Enum
from typing import FrozenSet


class Axis(str, Enum):
    """The four scoring axes declared by the v0.4.0 taxonomy.

    Phase 1 score consumes DRIFT, SENSITIVITY, and EQUIVALENCE.
    WRONG_DIRECTION is reserved — no v0.3.0 metric currently surfaces it.
    """

    DRIFT = "drift"
    """Stochastic instability: same input, different output. Measured by
    the noise-floor mean σ_c (Pillar 1's η)."""

    SENSITIVITY = "sensitivity"
    """Directional response to governing-content changes. Measured by
    the calibrated sensitivity (post-η subtraction). High = the pipeline
    actually reads the rule."""

    EQUIVALENCE = "equivalence"
    """Invariance under presentation-layer / order / non-causal-field
    changes. Measured by the calibrated invariance score. High = the
    pipeline ignores cosmetic changes."""

    WRONG_DIRECTION = "wrong_direction"
    """Whether sensitivity moves the WRONG way (strengthening a rule
    increases the score, etc.). No v0.3.0 measurement; placeholder for
    v0.5+."""


# v0.3.0 family identifiers. Mirrors `types.PerturbationKind` exactly;
# we re-declare here as a frozen set for the score-withholding check
# rather than importing PerturbationKind to keep this module dependency-
# free.
STANDARD_SCORE_FAMILIES: FrozenSet[str] = frozenset({
    # v0.2 inter-slot families
    "reorder",
    "pad_length",
    "pad_content",
    "swap",
    # v0.3 Pillar 2: counterfactual-controlled swap
    "swap_condition",
    # v0.3 Pillar 3: presentation-layer invariance
    "whitespace_jitter",
    "punctuation_normalize",
    "bullet_reformat",
    "non_governing_duplication",
    # v0.3 Pillar 3: mechanical sensitivity
    "numeric_magnitude",
    "comparator_flip",
    "polarity_flip",
    # v0.3 Pillar 3: rule-based rhetorical invariance
    "hedge_injection",
    "politeness_injection",
    "discourse_marker_injection",
    "meta_commentary_injection",
})
"""Perturbation families that the v0.4.0 maturity score is calibrated
against. The score is withheld if a user disables any of these via
`kelvin.yaml` — the calibration only applies under this canonical set.

Adding a new family in a future version means re-running the calibration
loop and updating this constant in lockstep.
"""


# Family → axis mapping. Used by Phase 2 variance-decomposition; declared
# here to keep all axis-related constants in one module.
FAMILY_AXIS: dict[str, Axis] = {
    # invariance families → EQUIVALENCE
    "reorder":                    Axis.EQUIVALENCE,
    "pad_length":                 Axis.EQUIVALENCE,
    "pad_content":                Axis.EQUIVALENCE,
    "whitespace_jitter":          Axis.EQUIVALENCE,
    "punctuation_normalize":      Axis.EQUIVALENCE,
    "bullet_reformat":            Axis.EQUIVALENCE,
    "non_governing_duplication":  Axis.EQUIVALENCE,
    "hedge_injection":            Axis.EQUIVALENCE,
    "politeness_injection":       Axis.EQUIVALENCE,
    "discourse_marker_injection": Axis.EQUIVALENCE,
    "meta_commentary_injection":  Axis.EQUIVALENCE,
    # sensitivity families → SENSITIVITY
    "swap":                       Axis.SENSITIVITY,
    "swap_condition":             Axis.SENSITIVITY,
    "numeric_magnitude":          Axis.SENSITIVITY,
    "comparator_flip":            Axis.SENSITIVITY,
    "polarity_flip":              Axis.SENSITIVITY,
}


def family_axis(family: str) -> Axis | None:
    """Return the scoring axis a perturbation family contributes to.

    Returns None for unknown families. DRIFT and WRONG_DIRECTION axes
    are populated from cross-cutting metrics, not from any single family.
    """
    return FAMILY_AXIS.get(family)
