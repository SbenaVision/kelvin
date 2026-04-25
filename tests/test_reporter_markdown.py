"""Tests for kelvin.reporters.markdown — practitioner-style MD output."""

from __future__ import annotations

from kelvin.findings import compute_findings
from kelvin.recommendations import compute_recommendations, top_fix
from kelvin.reporters.markdown import render_to_string
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


def _maturity_needs_work() -> MaturityScore:
    return MaturityScore(
        score=4, category="Needs work",
        withheld=False, withheld_reason=None,
        sub_scores={Axis.DRIFT: 0.4, Axis.SENSITIVITY: 0.7, Axis.EQUIVALENCE: 0.5},
        metrics={Axis.DRIFT: 0.10, Axis.SENSITIVITY: 0.70, Axis.EQUIVALENCE: 0.60},
        pillar_coverage={"pillar_1": True, "pillar_2": True, "pillar_3": True},
        silent_pillars={},
    )


def _render(m: MaturityScore) -> str:
    fs = compute_findings(m, _stub_run())
    recs = compute_recommendations(fs)
    fix = top_fix(recs)
    return render_to_string(m, fs, recs, fix)


# ── Markdown structure ────────────────────────────────────────────────────

def test_starts_with_h1_header():
    out = _render(_maturity_needs_work())
    assert out.startswith("# Kelvin v0.4")


def test_includes_subscores_table():
    out = _render(_maturity_needs_work())
    assert "## Sub-scores" in out
    assert "| Axis | Sub-score |" in out
    assert "| Drift |" in out


def test_includes_whats_wrong_section():
    out = _render(_maturity_needs_work())
    assert "## What's wrong" in out


def test_includes_top_fix_section():
    out = _render(_maturity_needs_work())
    assert "## Top fix" in out


# ── Production-ready clean ────────────────────────────────────────────────

def test_production_ready_clean_uses_result_section():
    m = MaturityScore(
        score=10, category="Production-ready",
        withheld=False, withheld_reason=None,
        sub_scores={Axis.DRIFT: 1.0, Axis.SENSITIVITY: 1.0, Axis.EQUIVALENCE: 1.0},
        metrics={Axis.DRIFT: 0.0, Axis.SENSITIVITY: 0.95, Axis.EQUIVALENCE: 0.98},
        pillar_coverage={"pillar_1": True, "pillar_2": True, "pillar_3": True},
        silent_pillars={},
    )
    out = _render(m)
    assert "## Result" in out
    assert "No issues detected" in out


# ── Partially measured ────────────────────────────────────────────────────

def test_partially_measured_lists_pillar_coverage():
    m = MaturityScore(
        score=10, category="Partially measured",
        withheld=False, withheld_reason=None,
        sub_scores={Axis.DRIFT: 1.0, Axis.SENSITIVITY: 1.0, Axis.EQUIVALENCE: 1.0},
        metrics={Axis.DRIFT: 0.0, Axis.SENSITIVITY: 0.95, Axis.EQUIVALENCE: 0.98},
        pillar_coverage={"pillar_1": True, "pillar_2": False, "pillar_3": True},
        silent_pillars={"pillar_2": "swap_condition_format_mismatch"},
    )
    out = _render(m)
    assert "## Pillar coverage" in out
    assert "Partially measured" in out
    assert "Pillar 2" in out and "silent" in out


# ── No statistical jargon ─────────────────────────────────────────────────

_FORBIDDEN = ("ANOVA", "F-stat", "F-statistic", "p-value",
              "isotonic", "residual variance")


def test_no_statistical_jargon_in_markdown():
    out_lower = _render(_maturity_needs_work()).lower()
    for term in _FORBIDDEN:
        assert term.lower() not in out_lower
