"""Variance / impact decomposition for v0.4.0.

Two output shapes:

- `top_axes_by_impact()` — default. Per-axis ranking by how much
  each axis drags the maturity score down. Drives the "Top fix" line.
- `family_breakdown()` — verbose. Per-family hold-rate + contribution
  to invariance pool. Surfaced under --verbose only.

The "ANOVA-style" framing in the spec is intentionally informal here:
we report per-family % contribution to (1 − mean hold-rate), not
real ANOVA F-stats. The complexity of running real ANOVA against
unbalanced family panels would be wasted on a v0.4 surface that's
already gated behind --verbose. Real variance decomposition is a
v0.5+ research item.
"""

from __future__ import annotations

from dataclasses import dataclass

from .score import MaturityScore
from .taxonomy import Axis
from .types import RunScores


@dataclass(frozen=True)
class AxisImpact:
    """How much one axis drags the maturity score down."""
    axis: Axis
    sub_score: float
    impact: float  # 1 − sub_score, clamped to [0, 1]


@dataclass(frozen=True)
class FamilyImpact:
    """One perturbation family's contribution to a pooled axis."""
    family: str
    n_samples: int
    mean_distance: float       # 0 = pipeline matches baseline; 1 = always flips
    contribution_pct: float    # this family's share of (1 − mean) on its axis
    pillar: int                # 1, 2, or 3


def top_axes_by_impact(maturity: MaturityScore) -> list[AxisImpact]:
    """Rank measurable axes by how much each pulls the score down.

    Returns axes sorted by impact descending. Empty list when no
    axes were measured.
    """
    impacts = [
        AxisImpact(
            axis=axis,
            sub_score=sub,
            impact=max(0.0, min(1.0, 1.0 - sub)),
        )
        for axis, sub in maturity.sub_scores.items()
    ]
    impacts.sort(key=lambda x: -x.impact)
    return impacts


# =====================================================================
# Per-family breakdown (verbose only)
# =====================================================================

def _family_distances(case, family: str) -> list[float]:
    """Pull per-family distances from a CaseScores."""
    if family == "reorder":
        return [sp.distance for sp in case.reorder if sp.distance is not None]
    if family == "pad_length":
        return [sp.distance for sp in case.pad_length if sp.distance is not None]
    if family == "pad_content":
        return [sp.distance for sp in case.pad_content if sp.distance is not None]
    if family == "swap":
        return [
            sp.distance
            for sps in case.swaps_by_type.values()
            for sp in sps
            if sp.distance is not None
        ]
    if family == "swap_condition":
        return [
            sp.distance
            for sps in case.swap_conditions_by_type.values()
            for sp in sps
            if sp.distance is not None
        ]
    if family == "whitespace_jitter":
        return [sp.distance for sp in case.whitespace_jitter if sp.distance is not None]
    if family == "punctuation_normalize":
        return [sp.distance for sp in case.punctuation_normalize if sp.distance is not None]
    if family == "bullet_reformat":
        return [sp.distance for sp in case.bullet_reformat if sp.distance is not None]
    if family == "non_governing_duplication":
        return [sp.distance for sp in case.non_governing_duplication if sp.distance is not None]
    if family == "numeric_magnitude":
        return [sp.distance for sp in case.numeric_magnitude if sp.distance is not None]
    if family == "comparator_flip":
        return [sp.distance for sp in case.comparator_flip if sp.distance is not None]
    if family == "polarity_flip":
        return [sp.distance for sp in case.polarity_flip if sp.distance is not None]
    if family in ("hedge_injection", "politeness_injection",
                  "discourse_marker_injection", "meta_commentary_injection"):
        return [
            sp.distance for sp in case.rhetorical
            if sp.distance is not None
            and sp.perturbation.kind == family
        ]
    return []


# Family → pillar mapping for the verbose breakdown.
_FAMILY_PILLAR: dict[str, int] = {
    # v0.2 invariance families: count toward Pillar 3 invariance pool
    # in v0.3.0's accounting. Listed under their semantic pillar.
    "reorder": 3, "pad_length": 3, "pad_content": 3,
    "swap": 2,                  # v0.2 sensitivity probe
    "swap_condition": 2,        # Pillar 2
    "whitespace_jitter": 3, "punctuation_normalize": 3,
    "bullet_reformat": 3, "non_governing_duplication": 3,
    "numeric_magnitude": 3, "comparator_flip": 3, "polarity_flip": 3,
    "hedge_injection": 3, "politeness_injection": 3,
    "discourse_marker_injection": 3, "meta_commentary_injection": 3,
}


def family_breakdown(run: RunScores) -> list[FamilyImpact]:
    """Per-family hold-rate and contribution share.

    For each known family with at least one contributing sample,
    compute mean distance across cases and the family's share of
    (1 − mean). Sort by share descending.

    Used in --verbose mode only; the default reporter ignores this.
    """
    fam_distances: dict[str, list[float]] = {}
    for case in run.cases:
        for family in _FAMILY_PILLAR:
            ds = _family_distances(case, family)
            if ds:
                fam_distances.setdefault(family, []).extend(ds)

    if not fam_distances:
        return []

    total_movement = sum(
        sum(ds) / len(ds) for ds in fam_distances.values()
    )

    impacts: list[FamilyImpact] = []
    for family, ds in fam_distances.items():
        mean = sum(ds) / len(ds)
        share = (mean / total_movement) if total_movement > 0 else 0.0
        impacts.append(FamilyImpact(
            family=family,
            n_samples=len(ds),
            mean_distance=mean,
            contribution_pct=round(100 * share, 1),
            pillar=_FAMILY_PILLAR[family],
        ))
    impacts.sort(key=lambda x: -x.contribution_pct)
    return impacts
