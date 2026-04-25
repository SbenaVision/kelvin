"""Tests for kelvin.findings — plain-language axis findings."""

from __future__ import annotations

import pytest

from kelvin.findings import (
    Finding,
    compute_findings,
    whats_working,
    whats_wrong,
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
    """Synthetic MaturityScore using only the metrics this module reads."""
    return MaturityScore(
        score=5,
        category="Needs work",
        withheld=False,
        withheld_reason=None,
        sub_scores={
            Axis.DRIFT: 1 - drift,
            Axis.SENSITIVITY: sens,
            Axis.EQUIVALENCE: eq,
        },
        metrics={
            Axis.DRIFT: drift,
            Axis.SENSITIVITY: sens,
            Axis.EQUIVALENCE: eq,
        },
        pillar_coverage={"pillar_1": True, "pillar_2": True, "pillar_3": True},
        silent_pillars={},
    )


# ── compute_findings: one finding per axis ────────────────────────────────

def test_compute_findings_emits_one_per_axis():
    m = _maturity(drift=0.10, sens=0.50, eq=0.50)
    fs = compute_findings(m, _stub_run())
    axes = {f.axis for f in fs}
    assert axes == {Axis.DRIFT, Axis.SENSITIVITY, Axis.EQUIVALENCE}


def test_compute_findings_empty_when_metrics_missing():
    """No metrics → no findings (no fabrication)."""
    m = MaturityScore(
        score=None, category=None, withheld=True,
        withheld_reason="missing", sub_scores={}, metrics={},
        pillar_coverage={}, silent_pillars={},
    )
    assert compute_findings(m, _stub_run()) == []


# ── Drift severity boundaries ─────────────────────────────────────────────

@pytest.mark.parametrize("eta,severity", [
    (0.30, "severe"),
    (0.20, "severe"),       # threshold inclusive (η ≥ 0.20)
    (0.19, "moderate"),
    (0.05, "moderate"),     # threshold inclusive (η ≥ 0.05)
    (0.04, "good"),
    (0.0,  "good"),
])
def test_drift_severity(eta: float, severity: str):
    m = _maturity(drift=eta, sens=1.0, eq=1.0)
    fs = compute_findings(m, _stub_run())
    drift_finding = next(f for f in fs if f.axis == Axis.DRIFT)
    assert drift_finding.severity == severity


def test_drift_severe_includes_pct_in_description():
    m = _maturity(drift=0.30, sens=1.0, eq=1.0)
    fs = compute_findings(m, _stub_run())
    f = next(x for x in fs if x.axis == Axis.DRIFT)
    assert "30" in f.description  # pct = round(0.30 * 100)


# ── Sensitivity severity boundaries ───────────────────────────────────────

@pytest.mark.parametrize("sens,severity", [
    (0.0,  "severe"),
    (0.29, "severe"),       # below 0.30
    (0.30, "moderate"),     # threshold inclusive
    (0.64, "moderate"),
    (0.65, "good"),         # threshold for good
    (1.0,  "good"),
])
def test_sens_severity(sens: float, severity: str):
    m = _maturity(drift=0.0, sens=sens, eq=1.0)
    fs = compute_findings(m, _stub_run())
    f = next(x for x in fs if x.axis == Axis.SENSITIVITY)
    assert f.severity == severity


# ── Invariance severity boundaries ────────────────────────────────────────

@pytest.mark.parametrize("eq,severity", [
    (0.0,  "severe"),
    (0.49, "severe"),
    (0.50, "moderate"),
    (0.84, "moderate"),
    (0.85, "good"),
    (1.0,  "good"),
])
def test_eq_severity(eq: float, severity: str):
    m = _maturity(drift=0.0, sens=1.0, eq=eq)
    fs = compute_findings(m, _stub_run())
    f = next(x for x in fs if x.axis == Axis.EQUIVALENCE)
    assert f.severity == severity


# ── whats_wrong / whats_working ───────────────────────────────────────────

def test_whats_wrong_top_n_by_impact():
    """Severe findings sort before moderate; tie-break on impact."""
    m = _maturity(drift=0.30, sens=0.10, eq=0.20)
    fs = compute_findings(m, _stub_run())
    bad = whats_wrong(fs, limit=2)
    assert len(bad) == 2
    assert bad[0].severity in ("severe", "moderate")
    # First should have the highest impact among severe.
    assert bad[0].impact >= bad[1].impact


def test_whats_wrong_excludes_good():
    m = _maturity(drift=0.0, sens=1.0, eq=1.0)
    fs = compute_findings(m, _stub_run())
    assert whats_wrong(fs) == []


def test_whats_working_returns_only_good():
    m = _maturity(drift=0.30, sens=1.0, eq=1.0)
    fs = compute_findings(m, _stub_run())
    good = whats_working(fs)
    assert len(good) == 2
    assert all(f.severity == "good" for f in good)
    assert {f.axis for f in good} == {Axis.SENSITIVITY, Axis.EQUIVALENCE}


# ── Plain-language constraint (AC3 spot-check on description text) ────────

_FORBIDDEN = ("ANOVA", "F-stat", "F-statistic", "p-value", "isotonic",
              "residual variance")


def test_findings_have_no_statistical_jargon():
    """Spot check: across many parameter combinations, no finding's
    description contains forbidden statistics jargon."""
    for drift in (0.0, 0.10, 0.30):
        for sens in (0.0, 0.50, 1.0):
            for eq in (0.0, 0.50, 1.0):
                m = _maturity(drift=drift, sens=sens, eq=eq)
                fs = compute_findings(m, _stub_run())
                for f in fs:
                    for term in _FORBIDDEN:
                        assert term.lower() not in f.description.lower(), (
                            f"finding description leaked '{term}': "
                            f"{f.description!r}"
                        )
