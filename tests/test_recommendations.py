"""Tests for kelvin.recommendations — hand-curated fix table."""

from __future__ import annotations

from kelvin.findings import Finding, compute_findings
from kelvin.recommendations import (
    Recommendation,
    compute_recommendations,
    recommendation_for,
    top_fix,
)
from kelvin.score import MaturityScore
from kelvin.taxonomy import Axis
from kelvin.types import RunScores


def _stub_run() -> RunScores:
    return RunScores(
        cases=[], seed=0,
        invariance=None, invariance_sample=0,
        sensitivity=None, sensitivity_sample=0,
        kelvin_score=None, sensitivity_by_type={},
        governing_types=[],
    )


def _maturity(*, drift: float, sens: float, eq: float) -> MaturityScore:
    return MaturityScore(
        score=5, category="Needs work",
        withheld=False, withheld_reason=None,
        sub_scores={Axis.DRIFT: 1 - drift, Axis.SENSITIVITY: sens, Axis.EQUIVALENCE: eq},
        metrics={Axis.DRIFT: drift, Axis.SENSITIVITY: sens, Axis.EQUIVALENCE: eq},
        pillar_coverage={"pillar_1": True, "pillar_2": True, "pillar_3": True},
        silent_pillars={},
    )


# ── Per-axis canned recommendations exist ─────────────────────────────────

def test_canned_rec_for_severe_drift():
    m = _maturity(drift=0.30, sens=1.0, eq=1.0)
    fs = compute_findings(m, _stub_run())
    drift_f = next(f for f in fs if f.axis == Axis.DRIFT)
    rec = recommendation_for(drift_f)
    assert not rec.needs_investigation
    assert "temperature" in rec.text.lower()


def test_canned_rec_for_severe_sens():
    m = _maturity(drift=0.0, sens=0.0, eq=1.0)
    fs = compute_findings(m, _stub_run())
    sens_f = next(f for f in fs if f.axis == Axis.SENSITIVITY)
    rec = recommendation_for(sens_f)
    assert not rec.needs_investigation
    assert "prompt" in rec.text.lower() or "rule" in rec.text.lower()


def test_canned_rec_for_severe_eq():
    m = _maturity(drift=0.0, sens=1.0, eq=0.0)
    fs = compute_findings(m, _stub_run())
    eq_f = next(f for f in fs if f.axis == Axis.EQUIVALENCE)
    rec = recommendation_for(eq_f)
    assert not rec.needs_investigation


def test_good_finding_yields_keep_doing_rec():
    m = _maturity(drift=0.0, sens=1.0, eq=1.0)
    fs = compute_findings(m, _stub_run())
    drift_f = next(f for f in fs if f.axis == Axis.DRIFT and f.severity == "good")
    rec = recommendation_for(drift_f)
    assert not rec.needs_investigation


# ── compute_recommendations preserves order ──────────────────────────────

def test_compute_recommendations_one_per_finding():
    m = _maturity(drift=0.30, sens=0.0, eq=0.20)
    fs = compute_findings(m, _stub_run())
    recs = compute_recommendations(fs)
    assert len(recs) == len(fs)
    for f, r in zip(fs, recs, strict=True):
        assert r.finding is f


# ── top_fix promotion ────────────────────────────────────────────────────

def test_top_fix_returns_highest_impact_actionable():
    m = _maturity(drift=0.30, sens=0.50, eq=0.20)
    fs = compute_findings(m, _stub_run())
    recs = compute_recommendations(fs)
    fix = top_fix(recs)
    assert fix is not None
    assert fix.finding.severity in ("severe", "moderate")
    # Among findings, the highest-impact actionable one wins.
    actionable = [r for r in recs if r.finding.severity != "good"]
    assert fix.finding.impact == max(r.finding.impact for r in actionable)


def test_top_fix_none_when_all_clean():
    m = _maturity(drift=0.0, sens=1.0, eq=1.0)
    fs = compute_findings(m, _stub_run())
    recs = compute_recommendations(fs)
    assert top_fix(recs) is None


def test_top_fix_skips_needs_investigation():
    """If the only actionable rec is needs_investigation, top_fix is None."""
    # Synthesize a finding that has no canned mapping by mutating axis.
    f = Finding(
        axis=Axis.WRONG_DIRECTION,
        severity="severe",
        title="x", description="x",
        current_value=0.5, expected_value=1.0,
        direction="higher-is-better", impact=0.5,
    )
    rec = recommendation_for(f)
    assert rec.needs_investigation is True
    assert top_fix([rec]) is None
