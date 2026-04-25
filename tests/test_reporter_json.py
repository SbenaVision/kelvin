"""Tests for kelvin.reporters.json_reporter — structured output."""

from __future__ import annotations

import json

from kelvin.findings import compute_findings
from kelvin.recommendations import compute_recommendations, top_fix
from kelvin.reporters.json_reporter import (
    SCHEMA_VERSION,
    build_payload,
    render_to_string,
)
from kelvin.score import MaturityScore
from kelvin.taxonomy import Axis
from kelvin.types import RunScores


def _stub_run() -> RunScores:
    return RunScores(
        cases=[], seed=0,
        invariance=0.50, invariance_sample=0,
        sensitivity=0.70, sensitivity_sample=0,
        kelvin_score=None, sensitivity_by_type={},
        governing_types=[],
        noise_floor_eta=0.10,
        sensitivity_calibrated=0.70,
        invariance_calibrated=0.50,
    )


def _maturity() -> MaturityScore:
    return MaturityScore(
        score=4, category="Needs work",
        withheld=False, withheld_reason=None,
        sub_scores={Axis.DRIFT: 0.4, Axis.SENSITIVITY: 0.7, Axis.EQUIVALENCE: 0.5},
        metrics={Axis.DRIFT: 0.10, Axis.SENSITIVITY: 0.70, Axis.EQUIVALENCE: 0.60},
        pillar_coverage={"pillar_1": True, "pillar_2": True, "pillar_3": True},
        silent_pillars={},
    )


def _payload() -> dict:
    m = _maturity()
    run = _stub_run()
    fs = compute_findings(m, run)
    recs = compute_recommendations(fs)
    fix = top_fix(recs)
    return build_payload(m, fs, recs, fix, run)


# ── Schema basics ────────────────────────────────────────────────────────

def test_schema_version_is_set():
    p = _payload()
    assert p["schema_version"] == SCHEMA_VERSION
    assert p["kelvin_version"].startswith("0.4")


def test_payload_top_level_keys_stable():
    p = _payload()
    expected = {
        "schema_version", "kelvin_version", "maturity",
        "pillar_coverage", "silent_pillars", "findings",
        "recommendations", "top_fix", "variance", "raw_metrics",
    }
    assert expected.issubset(p.keys())


# ── Maturity block round-trip ────────────────────────────────────────────

def test_maturity_block_contents():
    p = _payload()
    m = p["maturity"]
    assert m["score"] == 4
    assert m["category"] == "Needs work"
    assert m["withheld"] is False
    assert "drift" in m["sub_scores"]
    assert "sensitivity" in m["sub_scores"]
    assert "equivalence" in m["sub_scores"]


def test_pillar_coverage_block_contents():
    p = _payload()
    cov = p["pillar_coverage"]
    assert cov == {"pillar_1": True, "pillar_2": True, "pillar_3": True}


def test_findings_serialized_with_severity_and_axis():
    p = _payload()
    findings = p["findings"]
    assert len(findings) > 0
    first = findings[0]
    assert "axis" in first
    assert "severity" in first
    assert first["severity"] in ("severe", "moderate", "good")


def test_top_fix_serialized_when_actionable():
    p = _payload()
    fix = p["top_fix"]
    assert fix is not None
    assert "text" in fix
    assert fix["needs_investigation"] is False


# ── Render returns valid JSON ────────────────────────────────────────────

def test_render_to_string_returns_parseable_json():
    m = _maturity()
    run = _stub_run()
    fs = compute_findings(m, run)
    recs = compute_recommendations(fs)
    fix = top_fix(recs)
    s = render_to_string(m, fs, recs, fix, run)
    parsed = json.loads(s)  # must not raise
    assert parsed["schema_version"] == SCHEMA_VERSION


# ── Silent-pillar info propagated ────────────────────────────────────────

def test_silent_pillars_propagate_to_json():
    m = MaturityScore(
        score=10, category="Partially measured",
        withheld=False, withheld_reason=None,
        sub_scores={Axis.DRIFT: 1.0, Axis.SENSITIVITY: 1.0, Axis.EQUIVALENCE: 1.0},
        metrics={Axis.DRIFT: 0.0, Axis.SENSITIVITY: 0.95, Axis.EQUIVALENCE: 0.98},
        pillar_coverage={"pillar_1": True, "pillar_2": False, "pillar_3": True},
        silent_pillars={"pillar_2": "swap_condition_format_mismatch"},
    )
    run = _stub_run()
    fs = compute_findings(m, run)
    recs = compute_recommendations(fs)
    fix = top_fix(recs)
    p = build_payload(m, fs, recs, fix, run)
    assert p["maturity"]["category"] == "Partially measured"
    assert p["pillar_coverage"]["pillar_2"] is False
    assert p["silent_pillars"]["pillar_2"] == "swap_condition_format_mismatch"


# ── Raw metrics passthrough ──────────────────────────────────────────────

def test_raw_metrics_block_passes_through_run_fields():
    p = _payload()
    raw = p["raw_metrics"]
    assert raw["noise_floor_eta"] == 0.10
    assert raw["invariance_calibrated"] == 0.50
    assert raw["sensitivity_calibrated"] == 0.70
