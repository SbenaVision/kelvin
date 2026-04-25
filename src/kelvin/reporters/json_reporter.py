"""Structured JSON reporter for `kelvin check --report-format json`.

Emits a versioned, machine-readable summary of a Kelvin v0.4 run:
the maturity verdict, per-axis sub-scores, pillar coverage, full
findings + recommendations, and the variance breakdown. Intended
for CI integration, dashboards, and downstream tooling.

The schema is **versioned** via the `schema_version` field; bumping
the major component (currently 1) is a breaking change. Adding new
optional fields is non-breaking.

Public API
----------
    render(maturity, findings, recommendations, top_fix, run, *, out=None)
        — write the JSON document to a stream.
    build_payload(maturity, findings, recommendations, top_fix, run)
        — return the dict that would be serialized; tests use this.
"""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from ..findings import Finding
from ..recommendations import Recommendation
from ..score import MaturityScore
from ..taxonomy import Axis
from ..types import RunScores
from ..variance import (
    family_breakdown,
    top_axes_by_impact,
)


SCHEMA_VERSION = "1.0"


def _axis_str(axis: Axis) -> str:
    return axis.value


def _finding_to_dict(f: Finding) -> dict[str, Any]:
    return {
        "axis": _axis_str(f.axis),
        "severity": f.severity,
        "title": f.title,
        "description": f.description,
        "current_value": round(f.current_value, 6),
        "expected_value": round(f.expected_value, 6),
        "direction": f.direction,
        "impact": round(f.impact, 6),
    }


def _recommendation_to_dict(r: Recommendation) -> dict[str, Any]:
    return {
        "finding_axis": _axis_str(r.finding.axis),
        "finding_severity": r.finding.severity,
        "text": r.text,
        "needs_investigation": r.needs_investigation,
    }


def build_payload(
    maturity: MaturityScore,
    findings: list[Finding],
    recommendations: list[Recommendation],
    top_fix_rec: Recommendation | None,
    run: RunScores,
) -> dict[str, Any]:
    """Build the JSON payload as a Python dict (no serialization).

    Layout is stable; downstream consumers can rely on field presence
    and types within a given `schema_version`.
    """
    sub_scores = {
        _axis_str(axis): round(sub, 6)
        for axis, sub in maturity.sub_scores.items()
    }
    metrics = {
        _axis_str(axis): round(val, 6)
        for axis, val in maturity.metrics.items()
    }

    # Variance / impact decomposition.
    impacts = [
        {
            "axis": _axis_str(ax.axis),
            "sub_score": round(ax.sub_score, 6),
            "impact": round(ax.impact, 6),
        }
        for ax in top_axes_by_impact(maturity)
    ]
    family = [
        {
            "family": fi.family,
            "n_samples": fi.n_samples,
            "mean_distance": round(fi.mean_distance, 6),
            "contribution_pct": fi.contribution_pct,
            "pillar": fi.pillar,
        }
        for fi in family_breakdown(run)
    ]

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kelvin_version": "0.4.0",
        "maturity": {
            "score": maturity.score,
            "category": maturity.category,
            "withheld": maturity.withheld,
            "withheld_reason": maturity.withheld_reason,
            "sub_scores": sub_scores,
            "metrics": metrics,
        },
        "pillar_coverage": dict(maturity.pillar_coverage),
        "silent_pillars": dict(maturity.silent_pillars),
        "findings": [_finding_to_dict(f) for f in findings],
        "recommendations": [_recommendation_to_dict(r) for r in recommendations],
        "top_fix": (
            _recommendation_to_dict(top_fix_rec)
            if top_fix_rec is not None
            else None
        ),
        "variance": {
            "top_axes_by_impact": impacts,
            "family_breakdown": family,
        },
        # Raw v0.3.0 metrics so downstream consumers can cross-check
        # without re-running. Mirrors the fields surfaced in the
        # `--research` (byte-compat) report.
        "raw_metrics": {
            "noise_floor_eta":           run.noise_floor_eta,
            "invariance":                run.invariance,
            "sensitivity":               run.sensitivity,
            "kelvin_score":              run.kelvin_score,
            "invariance_calibrated":     run.invariance_calibrated,
            "sensitivity_calibrated":    run.sensitivity_calibrated,
            "kelvin_score_calibrated":   run.kelvin_score_calibrated,
            "sensitivity_content":       run.sensitivity_content,
            "sensitivity_condition":     run.sensitivity_condition,
            "content_effect":            run.content_effect,
            "mechanical_sensitivity":    run.mechanical_sensitivity,
        },
    }
    return payload


def render(
    maturity: MaturityScore,
    findings: list[Finding],
    recommendations: list[Recommendation],
    top_fix_rec: Recommendation | None,
    run: RunScores,
    *,
    out: TextIO | None = None,
) -> None:
    """Serialize the payload as pretty-printed JSON to *out* (default stdout)."""
    if out is None:
        out = sys.stdout
    payload = build_payload(maturity, findings, recommendations, top_fix_rec, run)
    json.dump(payload, out, indent=2, sort_keys=False)
    out.write("\n")


def render_to_string(
    maturity: MaturityScore,
    findings: list[Finding],
    recommendations: list[Recommendation],
    top_fix_rec: Recommendation | None,
    run: RunScores,
) -> str:
    """Same as `render`, but returns a string."""
    payload = build_payload(maturity, findings, recommendations, top_fix_rec, run)
    return json.dumps(payload, indent=2, sort_keys=False) + "\n"
