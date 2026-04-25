"""Practitioner-facing default reporter for `kelvin check`.

Renders a one-screen (< 30-line) summary tuned for a working
engineer who wants to know, at a glance:

    1. Is this pipeline ready to deploy?           ← category verdict
    2. What's wrong, in plain English?             ← top-3 findings
    3. What should I do first?                     ← "Top fix" line

Design constraints (from `docs/PHASE_2_SCOPE.md` and the Phase 2 spec):

- **Under 30 lines.** Findings + recommendations are NEVER
  truncated — text wraps in full inside the box border. If the
  30-line budget would be exceeded, we drop a finding (3 → 2 → 1)
  rather than truncate any text. A clipped fix is worse than no
  fix.
- **No statistical jargon.** Never uses "ANOVA", "F-stat", "residual",
  "variance", "p-value", "isotonic", etc. (AC3 — regex-grepped in
  tests.)
- **No fabrication.** When findings/recs/coverage data are missing,
  the corresponding section is suppressed rather than padded.
- **Silent-pillar handling is mandatory.** A run with any silent
  standard pillar produces verdict "Partially measured", regardless
  of how clean the measured axes look. Silent pillars are listed
  with cause text and the "Top fix" promotes the make-it-measurable
  action.
- **Numeric is hidden by default.** Surface only the category and
  the per-axis sub-scores (0.00–1.00). The 1–10 number lives behind
  `--verbose`.

Output shape (Needs work):

    ┌─ Kelvin v0.4 ─ Needs work ─────────────────────
    │
    │   Drift        ████░░░░░░  0.40
    │   Sensitivity  ███████░░░  0.70
    │   Equivalence  █████░░░░░  0.50
    │
    │   What's wrong:
    │     1. Drift — answers vary 10% of the time on...
    │        → Reduce sampling temperature (try 0.0...).
    │     2. Cosmetic sensitivity — formatting changes...
    │        → Identify which formatting changes flip...
    │
    │   Top fix: Reduce sampling temperature (try 0.0...).
    │
    │   Run with --verbose for per-axis and per-family detail.
    └

Public API
----------
    render(maturity, findings, recommendations, top_fix, *, out=None) -> None
    render_to_string(maturity, findings, recommendations, top_fix) -> str
"""

from __future__ import annotations

import sys
import textwrap
from typing import TextIO

from ..findings import Finding, whats_working, whats_wrong
from ..recommendations import Recommendation
from ..score import MaturityScore, PillarSilenceReason
from ..taxonomy import Axis
from ..types import RunScores
from ..variance import family_breakdown, top_axes_by_impact


# ── Layout constants ───────────────────────────────────────────────────────

_INNER_WIDTH = 64
_LINE_BUDGET = 30        # AC2 — default output strictly < this many lines
_BAR_CELLS = 10
_BAR_FILLED = "█"
_BAR_EMPTY = "░"

_AXIS_LABEL: dict[Axis, str] = {
    Axis.DRIFT:       "Drift",
    Axis.SENSITIVITY: "Sensitivity",
    Axis.EQUIVALENCE: "Equivalence",
    Axis.WRONG_DIRECTION: "Wrong direction",
}

# Practitioner-facing pillar labels.
_PILLAR_LABEL: dict[str, str] = {
    "pillar_1": "Pillar 1 (drift)",
    "pillar_2": "Pillar 2 (rule swap)",
    "pillar_3": "Pillar 3 (formatting)",
}

# Mapping from machine-readable silence reason → practitioner-readable
# explanation (kept short so it fits one wrapped line).
_SILENCE_EXPLANATION: dict[PillarSilenceReason, str] = {
    "noise_floor_disabled_or_no_replays":
        "noise floor disabled or no replays",
    "swap_condition_format_mismatch":
        "gate_rule format not recognized",
    "swap_condition_no_perturbations":
        "no swap_condition perturbations fired",
    "intra_slot_disabled":
        "intra_slot disabled in kelvin.yaml",
    "intra_slot_no_mechanical_samples":
        "no mechanical-sensitivity samples",
}

# Mapping from silence reason → "Top fix" suggestion.
_SILENCE_FIX: dict[PillarSilenceReason, str] = {
    "noise_floor_disabled_or_no_replays":
        "Enable noise_floor in kelvin.yaml (≥30 replays) so drift "
        "can be measured.",
    "swap_condition_format_mismatch":
        "Restructure gate_rule bodies to match Kelvin's expected "
        "pattern, or wait for v0.5's broader format coverage.",
    "swap_condition_no_perturbations":
        "Add paired cases that share a state phrase but differ in "
        "the governing rule, so swap_condition can fire.",
    "intra_slot_disabled":
        "Enable intra_slot in kelvin.yaml so formatting probes run.",
    "intra_slot_no_mechanical_samples":
        "Add cases with numeric thresholds, comparators, or "
        "polarity terms so mechanical sensitivity is measured.",
}


# ── Text helpers ───────────────────────────────────────────────────────────

def _bar(value: float) -> str:
    """Render a 0–1 value as a 10-cell bar."""
    v = max(0.0, min(1.0, value))
    filled = round(v * _BAR_CELLS)
    return _BAR_FILLED * filled + _BAR_EMPTY * (_BAR_CELLS - filled)


def _wrap_full(text: str, indent: str) -> list[str]:
    """Wrap *text* to fit the box width — NEVER truncate.

    Returns one or more lines, each prefixed with *indent*. If the
    text fits on a single line it returns a 1-element list; otherwise
    it returns as many lines as needed.

    Findings descriptions, recommendations, and the Top fix line all
    flow through here. Truncation would clip actionable advice mid-
    thought ("Confirm the rule is…") which is worse than no advice.
    """
    width = max(20, _INNER_WIDTH - len(indent))
    lines = textwrap.wrap(text, width=width)
    if not lines:
        return [indent.rstrip() or indent]
    return [f"{indent}{ln}" for ln in lines]


# ── Section builders ───────────────────────────────────────────────────────

def _header(maturity: MaturityScore) -> list[str]:
    """The header bar showing category verdict."""
    cat = maturity.category or "(score withheld)"
    title = f"─ Kelvin v0.4 ─ {cat} "
    pad = max(0, _INNER_WIDTH - len(title))
    return [f"┌{title}{'─' * pad}"]


def _sub_scores_block(maturity: MaturityScore) -> list[str]:
    """One line per measured axis: label, bar, numeric sub-score."""
    if not maturity.sub_scores:
        return []
    rows: list[str] = []
    # Stable axis order for display.
    for axis in (Axis.DRIFT, Axis.SENSITIVITY, Axis.EQUIVALENCE):
        if axis not in maturity.sub_scores:
            continue
        sub = maturity.sub_scores[axis]
        label = _AXIS_LABEL[axis]
        rows.append(f"│   {label:<12} {_bar(sub)}  {sub:0.2f}")
    return rows


def _pillar_coverage_block(maturity: MaturityScore) -> list[str]:
    """List per-pillar coverage for the Partially-measured state."""
    if not maturity.pillar_coverage:
        return []
    rows = ["│   Pillar coverage:"]
    for key in ("pillar_1", "pillar_2", "pillar_3"):
        if key not in maturity.pillar_coverage:
            continue
        label = _PILLAR_LABEL[key]
        if maturity.pillar_coverage[key]:
            rows.append(f"│     {label:<22} measured")
        else:
            reason = maturity.silent_pillars.get(key)
            why = (
                _SILENCE_EXPLANATION.get(reason, "silent")
                if reason else "silent"
            )
            rows.append(f"│     {label:<22} silent — {why}")
    return rows


def _whats_wrong_block(
    findings: list[Finding],
    recommendations: list[Recommendation],
    limit: int = 3,
) -> list[str]:
    """Top-N severe+moderate findings, each fully wrapped (no truncation).

    Format per finding:
        N. <title> — <description, wrapped to as many lines as needed>
           → <recommendation, wrapped to as many lines as needed>
    """
    bad = whats_wrong(findings, limit=limit)
    if not bad:
        return []
    rec_for: dict[int, Recommendation] = {
        id(r.finding): r for r in recommendations
    }
    rows = ["│   What's wrong:"]
    for n, f in enumerate(bad, start=1):
        rows.extend(_wrap_full(
            f"{n}. {f.title} — {f.description}",
            indent="│     ",
        ))
        rec = rec_for.get(id(f))
        if rec is not None:
            rows.extend(_wrap_full(f"→ {rec.text}", indent="│        "))
    return rows


def _whats_working_lines(findings: list[Finding]) -> list[str]:
    """Wrapped summary of `good`-severity findings.

    Returns an empty list when nothing is working.
    """
    good = whats_working(findings)
    if not good:
        return []
    titles = " · ".join(f.title for f in good)
    return _wrap_full("What's working: " + titles, indent="│   ")


def _top_fix_block(
    maturity: MaturityScore,
    top_fix: Recommendation | None,
) -> list[str]:
    """Promoted single fix line (≤ 3 wrap-lines).

    Priority:
      1. If any pillar is silent, promote the make-it-measurable fix
         for the FIRST silent pillar in (1, 2, 3) order.
      2. Otherwise, use the top_fix Recommendation if present.
      3. Otherwise, suppress the section.
    """
    # Silent-pillar override — make-it-measurable beats other fixes.
    for key in ("pillar_1", "pillar_2", "pillar_3"):
        if maturity.pillar_coverage.get(key) is False:
            reason = maturity.silent_pillars.get(key)
            if reason and reason in _SILENCE_FIX:
                return _wrap_full(
                    f"Top fix: {_SILENCE_FIX[reason]}",
                    indent="│   ",
                )

    if top_fix is None:
        return []
    return _wrap_full(f"Top fix: {top_fix.text}", indent="│   ")


def _trailer(verbose: bool) -> list[str]:
    """Hint line + bottom border. No leading blank — caller manages
    spacing."""
    if verbose:
        return ["└"]
    return [
        "│   Run with --verbose for per-axis and per-family detail.",
        "└",
    ]


def _verbose_block(
    maturity: MaturityScore,
    run: RunScores | None,
) -> list[str]:
    """Verbose-only addendum: numeric score, raw metrics, per-axis
    impact ranking, family breakdown.

    Per docs/PHASE_2_SCOPE.md: when any standard pillar is silent, the
    numeric score is **flagged** with a banner so it isn't compared to
    fully-measured pipelines.
    """
    rows: list[str] = ["│   ── Verbose detail ─────────────────────"]

    # Numeric score with partial-coverage banner.
    if maturity.score is not None:
        if maturity.category == "Partially measured":
            rows.append(
                f"│   Numeric: {maturity.score} / 10  "
                f"(⚠ partial coverage — not comparable to "
                f"fully-measured runs)"
            )
        else:
            rows.append(f"│   Numeric: {maturity.score} / 10")

    # Raw metrics for each measured axis.
    if maturity.metrics:
        rows.append("│   Raw metrics:")
        for axis in (Axis.DRIFT, Axis.SENSITIVITY, Axis.EQUIVALENCE):
            if axis not in maturity.metrics:
                continue
            label = _AXIS_LABEL[axis]
            rows.append(
                f"│     {label:<14} {maturity.metrics[axis]:0.4f}"
            )
    rows.append("│")

    # Top axes by impact.
    impacts = top_axes_by_impact(maturity)
    if impacts:
        rows.append("│   Per-axis impact (drag on score):")
        for ax in impacts:
            rows.append(
                f"│     {_AXIS_LABEL[ax.axis]:<14} "
                f"sub={ax.sub_score:0.2f}  impact={ax.impact:0.2f}"
            )
        rows.append("│")

    # Per-family breakdown.
    if run is not None:
        breakdown = family_breakdown(run)
        if breakdown:
            rows.append("│   Per-family contribution to invariance pool:")
            for fi in breakdown:
                rows.append(
                    f"│     {fi.family:<28} "
                    f"n={fi.n_samples:>3}  "
                    f"mean_dist={fi.mean_distance:0.3f}  "
                    f"share={fi.contribution_pct:5.1f}%  "
                    f"(P{fi.pillar})"
                )
            rows.append("│")

    return rows


# ── Main builder ───────────────────────────────────────────────────────────

def _build_once(
    maturity: MaturityScore,
    findings: list[Finding],
    recommendations: list[Recommendation],
    top_fix: Recommendation | None,
    *,
    verbose: bool,
    run: RunScores | None,
    findings_limit: int,
) -> list[str]:
    """Compose the practitioner output ONCE with a fixed findings_limit.

    `_build` wraps this with a budget-retry loop that drops findings
    (3 → 2 → 1 → 0) when the rendered output would exceed the line
    budget. Per the spec, we drop findings rather than truncate any
    text — a clipped recommendation is worse than no recommendation.
    """
    rows: list[str] = []

    # Header + spacer.
    rows.extend(_header(maturity))
    rows.append("│")

    # Withheld branch (rare — disabled families or genuinely missing
    # metrics). Show the reason and stop early.
    if maturity.withheld:
        rows.append("│   Score withheld.")
        if maturity.withheld_reason:
            rows.extend(_wrap_full(maturity.withheld_reason, indent="│   "))
        rows.append("│")
        rows.extend(_trailer(verbose))
        return rows

    # Sub-scores (3 lines for full runs).
    sub_rows = _sub_scores_block(maturity)
    if sub_rows:
        rows.extend(sub_rows)
        rows.append("│")

    # Partially-measured: list pillar coverage.
    if maturity.category == "Partially measured":
        cov = _pillar_coverage_block(maturity)
        if cov:
            rows.extend(cov)
            rows.append("│")

    # What's wrong (top-N findings, fully wrapped).
    bad = _whats_wrong_block(findings, recommendations, limit=findings_limit)
    if bad:
        rows.extend(bad)
        rows.append("│")
    elif maturity.category == "Production-ready":
        rows.append("│   No issues detected. All v0.4 checks passed.")
        rows.append("│")

    # What's working — wrapped, no truncation.
    working = _whats_working_lines(findings)
    if working:
        rows.extend(working)
        rows.append("│")

    # Top fix line (fully wrapped).
    fix = _top_fix_block(maturity, top_fix)
    if fix:
        rows.extend(fix)
        rows.append("│")

    # Verbose addendum (only shown when --verbose is passed).
    if verbose:
        rows.extend(_verbose_block(maturity, run))

    rows.extend(_trailer(verbose))
    return rows


def _build(
    maturity: MaturityScore,
    findings: list[Finding],
    recommendations: list[Recommendation],
    top_fix: Recommendation | None,
    *,
    verbose: bool = False,
    run: RunScores | None = None,
) -> list[str]:
    """Compose the practitioner output with a line-budget retry.

    Tries findings_limit = 3, 2, 1, 0 in turn; returns the first
    rendering that fits under `_LINE_BUDGET` (30) lines. The text
    itself is never truncated — wrapping is fine, dropping a finding
    is fine, but a clipped recommendation is forbidden.

    The verbose addendum is exempt from the budget (it's intentionally
    detailed and shown only when the user opts in).
    """
    if verbose:
        # Verbose has no line cap — show everything.
        return _build_once(
            maturity, findings, recommendations, top_fix,
            verbose=True, run=run, findings_limit=3,
        )

    last_rendered: list[str] = []
    for limit in (3, 2, 1, 0):
        rendered = _build_once(
            maturity, findings, recommendations, top_fix,
            verbose=False, run=run, findings_limit=limit,
        )
        last_rendered = rendered
        if len(rendered) < _LINE_BUDGET:
            return rendered
    # All retries blew the budget. Return the most-aggressive trim
    # (limit=0). Practically unreachable for the calibrated rule
    # tables, but defensible behavior.
    return last_rendered


# ── Public entry point ─────────────────────────────────────────────────────

def render(
    maturity: MaturityScore,
    findings: list[Finding],
    recommendations: list[Recommendation],
    top_fix: Recommendation | None,
    *,
    out: TextIO | None = None,
    verbose: bool = False,
    run: RunScores | None = None,
) -> None:
    """Print the practitioner one-screen summary to *out* (default stdout).

    When ``verbose=True``, also pass ``run`` so the per-family breakdown
    can be computed.
    """
    if out is None:
        out = sys.stdout
    for line in _build(
        maturity, findings, recommendations, top_fix,
        verbose=verbose, run=run,
    ):
        print(line, file=out)


def render_to_string(
    maturity: MaturityScore,
    findings: list[Finding],
    recommendations: list[Recommendation],
    top_fix: Recommendation | None,
    *,
    verbose: bool = False,
    run: RunScores | None = None,
) -> str:
    """Same as `render`, but returns a string."""
    return "\n".join(
        _build(
            maturity, findings, recommendations, top_fix,
            verbose=verbose, run=run,
        )
    ) + "\n"
