"""Tests for kelvin.score — maturity score computation.

These tests build SYNTHETIC RunScores objects (no real pipeline runs)
to exercise the score function directly. The integration / calibration
test that actually runs `kelvin check` against the reference pipelines
lives in `experiments/v040_phase1_calibration/`.
"""

from __future__ import annotations

from typing import Iterable

import pytest

from kelvin.score import (
    ANCHORS,
    MaturityScore,
    compute_maturity,
    drift_calibration,
    eq_calibration,
    sens_calibration,
)
from kelvin.taxonomy import Axis
from kelvin.types import (
    CaseScores,
    InvocationResult,
    Perturbation,
    PerturbationKind,
    RunScores,
    ScoredPerturbation,
)
from pathlib import Path


# =====================================================================
# Helpers
# =====================================================================


def _sp(kind: PerturbationKind, distance: float) -> ScoredPerturbation:
    """Tiny ScoredPerturbation with synthetic distance."""
    pert = Perturbation(
        case_name="x",
        kind=kind,
        variant_id=f"{kind}-1",
        rendered_markdown="",
    )
    inv = InvocationResult(
        ok=True, exit_code=0,
        input_path=Path("/x"), output_path=Path("/y"),
    )
    return ScoredPerturbation(perturbation=pert, invocation=inv, distance=distance)


def _case_with_all_families(case_name: str) -> CaseScores:
    """Case with at least one ScoredPerturbation in every standard family."""
    cs = CaseScores(case_name=case_name)
    cs.reorder.append(_sp("reorder", 0.0))
    cs.pad_length.append(_sp("pad_length", 0.0))
    cs.pad_content.append(_sp("pad_content", 0.0))
    cs.swaps_by_type.setdefault("gate_rule", []).append(_sp("swap", 0.5))
    cs.swap_conditions_by_type.setdefault("gate_rule", []).append(
        _sp("swap_condition", 0.5))
    cs.whitespace_jitter.append(_sp("whitespace_jitter", 0.0))
    cs.punctuation_normalize.append(_sp("punctuation_normalize", 0.0))
    cs.bullet_reformat.append(_sp("bullet_reformat", 0.0))
    cs.non_governing_duplication.append(_sp("non_governing_duplication", 0.0))
    cs.numeric_magnitude.append(_sp("numeric_magnitude", 0.5))
    cs.comparator_flip.append(_sp("comparator_flip", 0.5))
    cs.polarity_flip.append(_sp("polarity_flip", 0.5))
    # Pillar 3 rhetorical pool — one entry per family kind so saw[] flips.
    for kind in ("hedge_injection", "politeness_injection",
                 "discourse_marker_injection", "meta_commentary_injection"):
        cs.rhetorical.append(_sp(kind, 0.0))  # type: ignore[arg-type]
    return cs


def _run(eta: float | None,
         sens_cal: float | None,
         inv_cal: float | None,
         *, all_families: bool = True,
         sens_condition: float | None = 0.5,
         mech_sens: float | None = 0.5) -> RunScores:
    """Build a RunScores with the listed metrics.

    Pillar 2 / Pillar 3 metrics default to non-None so the score
    isn't auto-flagged as Partially measured. Tests that exercise
    silent-pillar logic explicitly set them to None.
    """
    cases = [_case_with_all_families("c1")] if all_families else [CaseScores(case_name="c1")]
    return RunScores(
        cases=cases,
        seed=0,
        invariance=inv_cal,
        invariance_sample=10,
        sensitivity=sens_cal,
        sensitivity_sample=10,
        kelvin_score=None,
        sensitivity_by_type={},
        governing_types=["gate_rule"],
        noise_floor_eta=eta,
        invariance_calibrated=inv_cal,
        sensitivity_calibrated=sens_cal,
        kelvin_score_calibrated=None,
        sensitivity_condition=sens_condition,
        sensitivity_condition_sample=10 if sens_condition is not None else 0,
        mechanical_sensitivity=mech_sens,
        mechanical_sensitivity_sample=10 if mech_sens is not None else 0,
    )


# =====================================================================
# Per-axis sub-score sanity (anchors hit)
# =====================================================================


def test_drift_calibration_hits_anchors():
    """Each anchor's drift_metric → drift_subscore."""
    cal = drift_calibration()
    for a in ANCHORS:
        # PAV pools any tied anchor xs; equal-x anchors share the pooled mean.
        # All 4 anchors at η=0.0 share sub-score=1.0; pooling is trivial.
        if a.drift_metric == 0.0:
            assert cal(a.drift_metric) == pytest.approx(1.0, abs=0.05)
        else:
            assert cal(a.drift_metric) == pytest.approx(a.drift_subscore, abs=0.05)


def test_sens_calibration_hits_anchors():
    cal = sens_calibration()
    for a in ANCHORS:
        # Anchor sens_metric values: 0.0, 0.5, 0.667, 0.667, 1.0.
        # The duplicated 0.667 anchors target sub-scores 0.667 each (no
        # pooling needed — both are identical).
        assert cal(a.sens_metric) == pytest.approx(a.sens_subscore, abs=0.05)


def test_eq_calibration_hits_anchors():
    cal = eq_calibration()
    for a in ANCHORS:
        # Each anchor's eq_metric → eq_subscore (within tolerance).
        # Anchors at eq_metric=1.0 are pooled trivially.
        assert cal(a.eq_metric) == pytest.approx(a.eq_subscore, abs=0.05)


# =====================================================================
# MIN aggregation + maturity mapping
# =====================================================================


def test_min_aggregation_clean_pipeline_scores_10():
    """All sub-scores at 1.0 → maturity 10."""
    run = _run(eta=0.0, sens_cal=1.0, inv_cal=1.0)
    m = compute_maturity(run)
    assert not m.withheld
    assert m.score == 10
    assert m.category == "Production-ready"


def test_min_aggregation_constant_pipeline_scores_1():
    """sens=0 dominates → maturity 1."""
    run = _run(eta=0.0, sens_cal=0.0, inv_cal=1.0)
    m = compute_maturity(run)
    assert not m.withheld
    assert m.score == 1
    assert m.category == "Not production-ready"


def test_brittle_collapses_to_score_1_on_this_corpus():
    """Brittle's first-header-based design + cases/ corpus → sens=0,
    inv≈0.94. Per the accepted Phase 1 anchor retarget, brittle scores
    1 on this corpus (indistinguishable from constant). Category:
    Not production-ready (still correctly classified as failure)."""
    run = _run(eta=0.0, sens_cal=0.0, inv_cal=0.935)
    m = compute_maturity(run)
    assert not m.withheld
    assert m.score == 1
    assert m.category == "Not production-ready"


def test_min_aggregation_mid_issue_scores_4():
    """Mid_issue's empirical metrics (η=0.181) → maturity 4 (Needs work)."""
    run = _run(eta=0.181, sens_cal=0.593, inv_cal=0.513)
    m = compute_maturity(run)
    assert not m.withheld
    assert m.score == 4
    assert m.category == "Needs work"


def test_one_moderate_collapses_to_score_10_on_this_corpus():
    """one_moderate_issue's missing-axis design isn't expressed in
    swap_condition perturbations on the cases/ corpus, so empirical
    metrics are indistinguishable from grounded. Per the accepted
    Phase 1 anchor retarget, one_moderate scores 10 (Production-ready
    — same as grounded). Category remains correct."""
    run = _run(eta=0.000, sens_cal=0.667, inv_cal=0.964)
    m = compute_maturity(run)
    assert not m.withheld
    assert m.score == 10
    assert m.category == "Production-ready"


# =====================================================================
# Category boundaries
# =====================================================================


@pytest.mark.parametrize("score, expected", [
    (1, "Not production-ready"),
    (3, "Not production-ready"),
    (4, "Needs work"),
    (6, "Needs work"),
    (7, "Production-ready"),
    (10, "Production-ready"),
])
def test_category_boundaries(score: int, expected: str):
    """Verify the 1–3 / 4–6 / 7–10 partition by constructing runs that
    produce each integer score."""
    # Map score → MIN sub-score = (score - 1) / 9.
    min_sub = (score - 1) / 9.0
    # Set sens to that min_sub; everything else clean.
    run = _run(eta=0.0, sens_cal=min_sub, inv_cal=1.0)
    m = compute_maturity(run)
    assert m.category == expected, (m, score, expected)


# =====================================================================
# Withholding
# =====================================================================


def test_withholds_when_required_metric_missing():
    """sens_calibrated = None → withhold."""
    run = _run(eta=0.0, sens_cal=None, inv_cal=1.0)
    m = compute_maturity(run)
    assert m.withheld
    assert m.score is None
    assert m.category is None
    assert m.withheld_reason is not None
    assert "calibrated" in m.withheld_reason.lower()


def test_withholds_when_invariance_missing():
    run = _run(eta=0.0, sens_cal=1.0, inv_cal=None)
    m = compute_maturity(run)
    assert m.withheld
    assert m.score is None


# =====================================================================
# Silent-pillar handling (per docs/PHASE_2_SCOPE.md)
# =====================================================================


def test_silent_pillar_2_blocks_production_ready():
    """When sensitivity_condition is None, the verdict must be
    'Partially measured' regardless of how clean other axes are."""
    run = _run(eta=0.0, sens_cal=1.0, inv_cal=1.0, sens_condition=None)
    m = compute_maturity(run)
    assert not m.withheld
    assert m.category == "Partially measured", (
        f"clean axes + silent Pillar 2 should be Partially measured; "
        f"got {m.category}"
    )
    assert m.pillar_coverage["pillar_2"] is False
    assert m.pillar_coverage["pillar_1"] is True
    assert m.pillar_coverage["pillar_3"] is True
    # Numeric IS computed (downstream reporter decides what to show).
    assert m.score == 10


def test_silent_pillar_3_blocks_production_ready():
    run = _run(eta=0.0, sens_cal=1.0, inv_cal=1.0, mech_sens=None)
    m = compute_maturity(run)
    assert m.category == "Partially measured"
    assert m.pillar_coverage["pillar_3"] is False
    # mechanical samples present in case fixture, so reason is "no samples"
    # rather than "disabled".
    assert m.silent_pillars["pillar_3"] == "intra_slot_no_mechanical_samples"


def test_silent_pillar_1_blocks_production_ready():
    """eta=None → Pillar 1 silent → Partially measured."""
    run = _run(eta=None, sens_cal=1.0, inv_cal=1.0)
    m = compute_maturity(run)
    assert m.category == "Partially measured"
    assert m.pillar_coverage["pillar_1"] is False
    assert m.silent_pillars["pillar_1"] == "noise_floor_disabled_or_no_replays"


def test_silent_pillar_2_distinguishes_format_mismatch_from_no_perturbations():
    """When clean_parse_rate is None or 0, reason is format mismatch.
    When clean_parse_rate > 0 but sens_condition is None, reason is
    no_perturbations."""
    # Format mismatch case (clean_parse_rate not set → defaults to None).
    run = _run(eta=0.0, sens_cal=1.0, inv_cal=1.0, sens_condition=None)
    run.swap_condition_clean_parse_rate = None
    m = compute_maturity(run)
    assert m.silent_pillars["pillar_2"] == "swap_condition_format_mismatch"

    # No-perturbations case.
    run.swap_condition_clean_parse_rate = 1.0
    m2 = compute_maturity(run)
    assert m2.silent_pillars["pillar_2"] == "swap_condition_no_perturbations"


def test_all_pillars_measured_yields_normal_category():
    """When all three pillars measured, normal 1–10 → category mapping
    applies (not 'Partially measured')."""
    run = _run(eta=0.0, sens_cal=1.0, inv_cal=1.0)
    m = compute_maturity(run)
    assert m.category == "Production-ready"
    assert all(m.pillar_coverage.values())
    assert m.silent_pillars == {}


def test_withholds_when_family_disabled():
    """Run without the all-families fixture → some standard family
    has zero contributing samples → withhold."""
    run = _run(eta=0.0, sens_cal=1.0, inv_cal=1.0, all_families=False)
    m = compute_maturity(run)
    assert m.withheld
    assert m.withheld_reason is not None
    assert "non-standard family" in m.withheld_reason


def test_eta_none_treated_as_zero_drift():
    """When noise_floor was disabled (eta=None) but paired metrics
    exist, drift defaults to 0 — the score is computable."""
    run = _run(eta=None, sens_cal=1.0, inv_cal=1.0)
    m = compute_maturity(run)
    assert not m.withheld
    assert m.score == 10


# =====================================================================
# Sub-scores and metrics surface for debugging
# =====================================================================


def test_subscores_populated_on_success():
    run = _run(eta=0.20, sens_cal=0.667, inv_cal=0.7)
    m = compute_maturity(run)
    assert Axis.DRIFT in m.sub_scores
    assert Axis.SENSITIVITY in m.sub_scores
    assert Axis.EQUIVALENCE in m.sub_scores
    # All sub-scores in [0, 1].
    for v in m.sub_scores.values():
        assert 0.0 <= v <= 1.0


def test_metrics_populated_on_success():
    run = _run(eta=0.20, sens_cal=0.667, inv_cal=0.7)
    m = compute_maturity(run)
    assert m.metrics[Axis.DRIFT] == pytest.approx(0.20)
    assert m.metrics[Axis.SENSITIVITY] == pytest.approx(0.667)
    assert m.metrics[Axis.EQUIVALENCE] == pytest.approx(0.7)
