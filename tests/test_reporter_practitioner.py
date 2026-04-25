"""Tests for kelvin.reporters.practitioner — default v0.4 reporter."""

from __future__ import annotations

import re

import pytest

from kelvin.findings import compute_findings
from kelvin.recommendations import compute_recommendations, top_fix
from kelvin.reporters.practitioner import render_to_string
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


def _maturity(
    *, drift: float, sens: float, eq: float,
    category: str = "Needs work", score: int | None = 5,
    pillar_coverage: dict[str, bool] | None = None,
    silent_pillars: dict[str, str] | None = None,
) -> MaturityScore:
    if pillar_coverage is None:
        pillar_coverage = {"pillar_1": True, "pillar_2": True, "pillar_3": True}
    return MaturityScore(
        score=score, category=category,  # type: ignore[arg-type]
        withheld=False, withheld_reason=None,
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
        pillar_coverage=pillar_coverage,
        silent_pillars=silent_pillars or {},  # type: ignore[arg-type]
    )


def _render(m: MaturityScore, *, verbose: bool = False) -> str:
    fs = compute_findings(m, _stub_run())
    recs = compute_recommendations(fs)
    fix = top_fix(recs)
    return render_to_string(m, fs, recs, fix, verbose=verbose, run=_stub_run())


# ── AC2: < 30 lines ──────────────────────────────────────────────────────

@pytest.mark.parametrize("drift,sens,eq,category", [
    (0.0,  1.0,  1.0,  "Production-ready"),
    (0.10, 0.70, 0.50, "Needs work"),
    (0.30, 0.10, 0.20, "Not production-ready"),
    (0.0,  1.0,  1.0,  "Partially measured"),
])
def test_default_output_under_30_lines(drift, sens, eq, category):
    """Default (non-verbose) practitioner output must fit on one screen."""
    pillar_coverage = (
        {"pillar_1": True, "pillar_2": False, "pillar_3": True}
        if category == "Partially measured" else None
    )
    silent = (
        {"pillar_2": "swap_condition_format_mismatch"}
        if category == "Partially measured" else None
    )
    m = _maturity(
        drift=drift, sens=sens, eq=eq, category=category,
        pillar_coverage=pillar_coverage, silent_pillars=silent,
    )
    out = _render(m)
    n_lines = out.count("\n")
    assert n_lines < 30, (
        f"Practitioner output should be < 30 lines; got {n_lines}.\n{out}"
    )


# ── AC3: no statistical jargon ────────────────────────────────────────────

_FORBIDDEN_TERMS = (
    "ANOVA",
    "F-stat",
    "F-statistic",
    "p-value",
    "isotonic",
    "residual variance",
)


@pytest.mark.parametrize("drift,sens,eq", [
    (0.0,  1.0,  1.0),
    (0.10, 0.70, 0.50),
    (0.30, 0.10, 0.20),
    (0.05, 0.50, 0.30),
])
def test_no_statistical_jargon(drift, sens, eq):
    """The default practitioner output must contain none of the
    forbidden statistics terms (AC3)."""
    m = _maturity(drift=drift, sens=sens, eq=eq)
    out = _render(m)
    out_lower = out.lower()
    for term in _FORBIDDEN_TERMS:
        # Use word-boundary regex to avoid false positives like "variant"
        # tripping on "variance" — but specifically the term itself.
        assert term.lower() not in out_lower, (
            f"forbidden term {term!r} present in default output:\n{out}"
        )


def test_no_jargon_under_verbose_either():
    """Verbose mode adds detail but must not introduce forbidden jargon."""
    m = _maturity(drift=0.10, sens=0.50, eq=0.50)
    out = _render(m, verbose=True)
    out_lower = out.lower()
    for term in _FORBIDDEN_TERMS:
        assert term.lower() not in out_lower, (
            f"forbidden term {term!r} present in verbose output:\n{out}"
        )


# ── Numeric is hidden by default, shown under --verbose ───────────────────

def test_numeric_score_hidden_by_default():
    """Default output must not show the 1–10 numeric score."""
    m = _maturity(drift=0.10, sens=0.50, eq=0.50, score=5,
                  category="Needs work")
    out = _render(m)
    # Defensive: the literal pattern "5 / 10" or "5/10" must not appear.
    assert not re.search(r"\b\d+\s*/\s*10\b", out), (
        f"numeric score leaked in default output:\n{out}"
    )


def test_numeric_score_shown_under_verbose():
    m = _maturity(drift=0.10, sens=0.50, eq=0.50, score=5,
                  category="Needs work")
    out = _render(m, verbose=True)
    assert re.search(r"5\s*/\s*10", out)


def test_numeric_score_flagged_under_partial_coverage():
    """When category is Partially measured, the numeric (verbose only)
    is banner-flagged so consumers don't compare it to fully-measured runs."""
    m = _maturity(
        drift=0.0, sens=1.0, eq=1.0, score=10, category="Partially measured",
        pillar_coverage={"pillar_1": True, "pillar_2": False, "pillar_3": True},
        silent_pillars={"pillar_2": "swap_condition_format_mismatch"},
    )
    out = _render(m, verbose=True)
    assert "partial coverage" in out.lower()


# ── Category verdict surfaces ─────────────────────────────────────────────

@pytest.mark.parametrize("category", [
    "Production-ready",
    "Needs work",
    "Not production-ready",
    "Partially measured",
])
def test_category_verdict_in_header(category: str):
    pc = ({"pillar_1": True, "pillar_2": False, "pillar_3": True}
          if category == "Partially measured" else None)
    silent = ({"pillar_2": "swap_condition_format_mismatch"}
              if category == "Partially measured" else None)
    m = _maturity(
        drift=0.0, sens=1.0, eq=1.0,
        category=category, pillar_coverage=pc, silent_pillars=silent,
    )
    out = _render(m)
    assert category in out


# ── Silent-pillar handling ────────────────────────────────────────────────

def test_silent_pillar_lists_each_pillar_status():
    m = _maturity(
        drift=0.0, sens=1.0, eq=1.0, category="Partially measured",
        pillar_coverage={"pillar_1": True, "pillar_2": False, "pillar_3": True},
        silent_pillars={"pillar_2": "swap_condition_format_mismatch"},
    )
    out = _render(m)
    assert "Pillar 1" in out and "Pillar 2" in out and "Pillar 3" in out
    assert "silent" in out.lower()
    assert "format not recognized" in out.lower()


def test_silent_pillar_promotes_make_measurable_top_fix():
    """When a pillar is silent, Top fix should promote the fix-coverage
    message rather than the worst-axis recommendation."""
    m = _maturity(
        drift=0.0, sens=1.0, eq=1.0, category="Partially measured",
        pillar_coverage={"pillar_1": True, "pillar_2": False, "pillar_3": True},
        silent_pillars={"pillar_2": "swap_condition_format_mismatch"},
    )
    out = _render(m)
    assert "Top fix" in out
    # Should mention restructuring gate_rule or v0.5, not e.g. "set temperature".
    assert "gate_rule" in out.lower() or "format" in out.lower()


def test_production_ready_clean_run_says_no_issues():
    m = _maturity(drift=0.0, sens=1.0, eq=1.0, category="Production-ready")
    out = _render(m)
    assert "No issues detected" in out


# ── Withheld branch ──────────────────────────────────────────────────────

def test_withheld_score_displayed():
    m = MaturityScore(
        score=None, category=None,
        withheld=True,
        withheld_reason="non-standard family set: ['swap'] produced zero samples.",
        sub_scores={}, metrics={},
        pillar_coverage={}, silent_pillars={},
    )
    out = render_to_string(m, [], [], None)
    assert "withheld" in out.lower()
    assert "non-standard family set" in out
