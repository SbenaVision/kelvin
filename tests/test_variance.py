"""Tests for kelvin.variance — axis-impact and family-breakdown."""

from __future__ import annotations

from pathlib import Path

import pytest

from kelvin.score import MaturityScore
from kelvin.taxonomy import Axis
from kelvin.types import (
    CaseScores,
    InvocationResult,
    Perturbation,
    PerturbationKind,
    RunScores,
    ScoredPerturbation,
)
from kelvin.variance import (
    AxisImpact,
    FamilyImpact,
    family_breakdown,
    top_axes_by_impact,
)


def _sp(kind: PerturbationKind, distance: float) -> ScoredPerturbation:
    pert = Perturbation(
        case_name="x", kind=kind, variant_id=f"{kind}-1", rendered_markdown="",
    )
    inv = InvocationResult(
        ok=True, exit_code=0,
        input_path=Path("/x"), output_path=Path("/y"),
    )
    return ScoredPerturbation(perturbation=pert, invocation=inv, distance=distance)


def _maturity(**subs: float) -> MaturityScore:
    return MaturityScore(
        score=5, category="Needs work",
        withheld=False, withheld_reason=None,
        sub_scores={
            Axis.DRIFT: subs.get("drift", 1.0),
            Axis.SENSITIVITY: subs.get("sens", 1.0),
            Axis.EQUIVALENCE: subs.get("eq", 1.0),
        },
        metrics={},
        pillar_coverage={"pillar_1": True, "pillar_2": True, "pillar_3": True},
        silent_pillars={},
    )


# ── top_axes_by_impact ────────────────────────────────────────────────────

def test_top_axes_by_impact_sorted_descending():
    m = _maturity(drift=0.40, sens=0.20, eq=0.80)
    out = top_axes_by_impact(m)
    assert [a.axis for a in out] == [Axis.SENSITIVITY, Axis.DRIFT, Axis.EQUIVALENCE]
    # Impact = 1 - sub_score.
    assert out[0].impact == pytest.approx(0.80)
    assert out[1].impact == pytest.approx(0.60)
    assert out[2].impact == pytest.approx(0.20)


def test_top_axes_clamps_impact_to_unit_interval():
    m = _maturity(drift=1.0, sens=1.5, eq=-0.2)  # noisy floats outside [0, 1]
    out = top_axes_by_impact(m)
    for ax in out:
        assert 0.0 <= ax.impact <= 1.0


def test_top_axes_empty_when_no_subscores():
    m = MaturityScore(
        score=None, category=None, withheld=True,
        withheld_reason="", sub_scores={}, metrics={},
        pillar_coverage={}, silent_pillars={},
    )
    assert top_axes_by_impact(m) == []


# ── family_breakdown ──────────────────────────────────────────────────────

def test_family_breakdown_empty_when_no_distances():
    run = RunScores(
        cases=[CaseScores(case_name="c1")], seed=0,
        invariance=None, invariance_sample=0,
        sensitivity=None, sensitivity_sample=0,
        kelvin_score=None, sensitivity_by_type={},
        governing_types=[],
    )
    assert family_breakdown(run) == []


def test_family_breakdown_aggregates_distances_per_family():
    cs = CaseScores(case_name="c1")
    cs.reorder.extend([_sp("reorder", 1.0), _sp("reorder", 1.0)])
    cs.whitespace_jitter.append(_sp("whitespace_jitter", 0.0))

    run = RunScores(
        cases=[cs], seed=0,
        invariance=None, invariance_sample=0,
        sensitivity=None, sensitivity_sample=0,
        kelvin_score=None, sensitivity_by_type={},
        governing_types=[],
    )
    breakdown = family_breakdown(run)
    families = {fi.family: fi for fi in breakdown}

    assert "reorder" in families
    assert families["reorder"].n_samples == 2
    assert families["reorder"].mean_distance == pytest.approx(1.0)
    # Reorder is the only non-zero contributor → 100% share.
    assert families["reorder"].contribution_pct == pytest.approx(100.0)


def test_family_breakdown_pillar_assignment():
    cs = CaseScores(case_name="c1")
    cs.reorder.append(_sp("reorder", 0.5))             # pillar 3 in our table
    cs.swap_conditions_by_type.setdefault("gate_rule", []).append(
        _sp("swap_condition", 0.5)
    )                                                   # pillar 2
    cs.swaps_by_type.setdefault("gate_rule", []).append(
        _sp("swap", 0.5)
    )                                                   # pillar 2 in table
    run = RunScores(
        cases=[cs], seed=0,
        invariance=None, invariance_sample=0,
        sensitivity=None, sensitivity_sample=0,
        kelvin_score=None, sensitivity_by_type={},
        governing_types=[],
    )
    pillars = {fi.family: fi.pillar for fi in family_breakdown(run)}
    assert pillars["reorder"] == 3
    assert pillars["swap_condition"] == 2
    assert pillars["swap"] == 2


def test_family_breakdown_sorted_by_share_desc():
    cs = CaseScores(case_name="c1")
    cs.reorder.extend([_sp("reorder", 1.0)])
    cs.pad_length.extend([_sp("pad_length", 0.5)])
    cs.whitespace_jitter.extend([_sp("whitespace_jitter", 0.1)])
    run = RunScores(
        cases=[cs], seed=0,
        invariance=None, invariance_sample=0,
        sensitivity=None, sensitivity_sample=0,
        kelvin_score=None, sensitivity_by_type={},
        governing_types=[],
    )
    breakdown = family_breakdown(run)
    pcts = [fi.contribution_pct for fi in breakdown]
    assert pcts == sorted(pcts, reverse=True)
