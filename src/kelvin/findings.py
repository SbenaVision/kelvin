"""Plain-language findings derived from a MaturityScore + RunScores.

A *finding* is a single statement about one scoring axis: what the
pipeline is doing, why that's a problem (or a strength), and how big
a deal it is. Findings drive the practitioner-facing default output
("What's wrong" / "What's working" sections).

Design constraints:
- **No fabrication.** When all axes are clean and no pillar is silent,
  `compute_findings` returns an empty list. The reporter then says
  "No issues detected." Don't invent findings.
- **No statistical jargon** (AC3). Findings use plain English. Words
  like "variance", "ANOVA", "F-stat", "isotonic", "p-value" are
  forbidden in the description text.
- **Hand-curated thresholds.** No learning, no AI, no soft logic.
  Every rule lives in this file and is reviewable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .score import MaturityScore
from .taxonomy import Axis
from .types import RunScores


Severity = Literal["severe", "moderate", "good"]


@dataclass(frozen=True)
class Finding:
    """One axis-level statement about a pipeline.

    `impact` ranks findings for the top-3 cut: higher impact = worse
    drag on the maturity score. `good`-severity findings have impact 0.
    """
    axis: Axis
    severity: Severity
    title: str
    description: str
    current_value: float
    expected_value: float
    direction: Literal["lower-is-better", "higher-is-better"]
    impact: float


# =====================================================================
# Per-axis rule tables
# =====================================================================
#
# Each rule: (severity, threshold-predicate, title, description-template,
#             expected_value).
#
# Threshold predicates are evaluated in order; first match wins. The
# "good" branch is the catch-all.


# Drift (η). Lower is better. expected_value = 0.0.
_DRIFT_RULES: tuple[tuple[Severity, float, str, str], ...] = (
    ("severe",
     0.20,
     "Drift",
     "Your pipeline gives different answers for the same input "
     "{pct}% of the time. Same input should produce the same output."),
    ("moderate",
     0.05,
     "Drift",
     "Your pipeline sometimes gives different answers for the same "
     "input ({pct}% of the time). Production pipelines should be "
     "stable across re-runs."),
    ("good",
     0.0,
     "Stability",
     "Your pipeline gives the same answer when run twice on the same "
     "input."),
)


# Sensitivity (calibrated). Higher is better. expected_value = 1.0.
_SENS_RULES: tuple[tuple[Severity, float, str, str], ...] = (
    ("severe",
     0.30,  # below this → severe
     "Rule-blindness",
     "When you change the governing rule, the output barely changes. "
     "Your rules aren't actually being read."),
    ("moderate",
     0.65,
     "Reduced rule sensitivity",
     "Some rule changes don't reach the output. Either the pipeline "
     "is ignoring part of the rule, or some rule axes don't drive "
     "the decision."),
    ("good",
     1.0,
     "Rule responsiveness",
     "When you change the governing rule, the output responds."),
)


# Invariance / Equivalence (calibrated). Higher is better. expected_value = 1.0.
_EQ_RULES: tuple[tuple[Severity, float, str, str], ...] = (
    ("severe",
     0.50,
     "Brittleness",
     "Cosmetic changes (whitespace, reorder, padding) move the "
     "output. Your pipeline depends on surface form, not content."),
    ("moderate",
     0.85,
     "Cosmetic sensitivity",
     "Some non-meaningful changes (formatting, padding) move the "
     "output. The pipeline is partly tied to surface form."),
    ("good",
     1.0,
     "Robustness",
     "Cosmetic changes (typos, rephrasing, reformatting) don't move "
     "the output."),
)


def _drift_finding(eta: float) -> Finding:
    """Generate the drift Finding from η. Always returns one (good or bad)."""
    pct = round(eta * 100)
    for severity, threshold, title, template in _DRIFT_RULES:
        if severity == "good":
            return Finding(
                axis=Axis.DRIFT, severity="good", title=title,
                description=template,
                current_value=eta, expected_value=0.0,
                direction="lower-is-better", impact=0.0,
            )
        if eta >= threshold:
            return Finding(
                axis=Axis.DRIFT, severity=severity, title=title,
                description=template.format(pct=pct),
                current_value=eta, expected_value=0.0,
                direction="lower-is-better",
                impact=min(1.0, eta / 0.30),  # severe at η ≈ 0.30+
            )
    raise RuntimeError("unreachable")


def _sens_finding(sens_cal: float) -> Finding:
    """Generate the sensitivity Finding from sens_cal."""
    for severity, threshold, title, template in _SENS_RULES:
        if severity == "good":
            return Finding(
                axis=Axis.SENSITIVITY, severity="good", title=title,
                description=template,
                current_value=sens_cal, expected_value=1.0,
                direction="higher-is-better", impact=0.0,
            )
        if sens_cal < threshold:
            return Finding(
                axis=Axis.SENSITIVITY, severity=severity, title=title,
                description=template,
                current_value=sens_cal, expected_value=1.0,
                direction="higher-is-better",
                impact=1.0 - sens_cal,
            )
    raise RuntimeError("unreachable")


def _eq_finding(inv_cal: float) -> Finding:
    """Generate the invariance Finding from inv_cal."""
    for severity, threshold, title, template in _EQ_RULES:
        if severity == "good":
            return Finding(
                axis=Axis.EQUIVALENCE, severity="good", title=title,
                description=template,
                current_value=inv_cal, expected_value=1.0,
                direction="higher-is-better", impact=0.0,
            )
        if inv_cal < threshold:
            return Finding(
                axis=Axis.EQUIVALENCE, severity=severity, title=title,
                description=template,
                current_value=inv_cal, expected_value=1.0,
                direction="higher-is-better",
                impact=1.0 - inv_cal,
            )
    raise RuntimeError("unreachable")


# =====================================================================
# Public API
# =====================================================================


def compute_findings(
    maturity: MaturityScore,
    run: RunScores,
) -> list[Finding]:
    """Return per-axis findings ordered by impact (worst first).

    Each axis produces exactly one Finding. The reporter selects how
    many to show (default takes top-3 by impact among severe+moderate).

    Returns:
        A list of Finding objects, one per measurable axis. Ordering:
        severe → moderate → good, then by impact within severity.
        Empty list when no axis has metrics (withheld score).
    """
    if not maturity.metrics:
        return []

    findings: list[Finding] = []

    if Axis.DRIFT in maturity.metrics:
        findings.append(_drift_finding(maturity.metrics[Axis.DRIFT]))
    if Axis.SENSITIVITY in maturity.metrics:
        findings.append(_sens_finding(maturity.metrics[Axis.SENSITIVITY]))
    if Axis.EQUIVALENCE in maturity.metrics:
        findings.append(_eq_finding(maturity.metrics[Axis.EQUIVALENCE]))

    # Sort: severity desc, then impact desc.
    severity_order = {"severe": 0, "moderate": 1, "good": 2}
    findings.sort(key=lambda f: (severity_order[f.severity], -f.impact))
    return findings


def whats_wrong(findings: list[Finding], limit: int = 3) -> list[Finding]:
    """Top-N severe+moderate findings, by impact descending."""
    bad = [f for f in findings if f.severity in ("severe", "moderate")]
    return bad[:limit]


def whats_working(findings: list[Finding]) -> list[Finding]:
    """All `good`-severity findings."""
    return [f for f in findings if f.severity == "good"]
