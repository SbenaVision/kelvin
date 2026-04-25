"""Markdown reporter for `kelvin check --report-format markdown`.

Renders the same content as `practitioner.py` but in a format that
embeds cleanly in PR descriptions, GitHub issues, status pages, etc.

Same constraints as practitioner:
- No statistical jargon (AC3).
- No fabrication.
- Silent-pillar handling: verdict NEVER "Production-ready" when any
  standard pillar is silent.
- Numeric is hidden by default — sub-scores are shown, but the 1–10
  number isn't elevated above the category verdict.

Public API
----------
    render(maturity, findings, recommendations, top_fix, *, out=None) -> None
    render_to_string(maturity, findings, recommendations, top_fix) -> str
"""

from __future__ import annotations

import sys
from typing import TextIO

from ..findings import Finding, whats_working, whats_wrong
from ..recommendations import Recommendation
from ..score import MaturityScore, PillarSilenceReason
from ..taxonomy import Axis


_AXIS_LABEL: dict[Axis, str] = {
    Axis.DRIFT:       "Drift",
    Axis.SENSITIVITY: "Sensitivity",
    Axis.EQUIVALENCE: "Equivalence",
    Axis.WRONG_DIRECTION: "Wrong direction",
}

_PILLAR_LABEL: dict[str, str] = {
    "pillar_1": "Pillar 1 (drift)",
    "pillar_2": "Pillar 2 (rule swap)",
    "pillar_3": "Pillar 3 (formatting)",
}

_SILENCE_EXPLANATION: dict[PillarSilenceReason, str] = {
    "noise_floor_disabled_or_no_replays":
        "noise floor disabled or no replays returned",
    "swap_condition_format_mismatch":
        "gate_rule format not recognized (pipeline reads rules in "
        "a non-standard layout)",
    "swap_condition_no_perturbations":
        "no swap_condition perturbations fired (corpus needs more "
        "paired cases with matching state phrases)",
    "intra_slot_disabled":
        "intra_slot perturbations disabled in `kelvin.yaml`",
    "intra_slot_no_mechanical_samples":
        "no mechanical-sensitivity samples (numeric_magnitude / "
        "comparator_flip / polarity_flip) fired",
}

_SILENCE_FIX: dict[PillarSilenceReason, str] = {
    "noise_floor_disabled_or_no_replays":
        "Enable `noise_floor` in `kelvin.yaml` (≥30 replays) so "
        "drift can be measured.",
    "swap_condition_format_mismatch":
        "Restructure gate_rule bodies to match Kelvin's expected "
        "pattern (a `requires` or `when` clause naming the "
        "switching axis), or wait for v0.5's broader format coverage.",
    "swap_condition_no_perturbations":
        "Add paired cases that share a state phrase but differ in "
        "the governing rule, so `swap_condition` can fire.",
    "intra_slot_disabled":
        "Enable `intra_slot` in `kelvin.yaml` so formatting and "
        "mechanical-sensitivity probes run.",
    "intra_slot_no_mechanical_samples":
        "Add cases with numeric thresholds, comparators, or "
        "polarity terms so mechanical sensitivity is measured.",
}


def _verdict_emoji(category: str | None) -> str:
    """A small leading icon for visual scannability in MD."""
    return {
        "Production-ready":     "✅",
        "Needs work":           "⚠️",
        "Not production-ready": "❌",
        "Partially measured":   "🟨",
    }.get(category or "", "")


def _build(
    maturity: MaturityScore,
    findings: list[Finding],
    recommendations: list[Recommendation],
    top_fix_rec: Recommendation | None,
) -> list[str]:
    """Compose the markdown output as a list of lines."""
    out: list[str] = []
    cat = maturity.category or "(score withheld)"
    icon = _verdict_emoji(maturity.category)

    out.append(f"# Kelvin v0.4 — {icon} {cat}".rstrip())
    out.append("")

    if maturity.withheld:
        out.append("**Score withheld.**")
        if maturity.withheld_reason:
            out.append("")
            out.append(maturity.withheld_reason)
        return out

    # Per-axis sub-scores as a small table.
    if maturity.sub_scores:
        out.append("## Sub-scores")
        out.append("")
        out.append("| Axis | Sub-score |")
        out.append("| --- | --- |")
        for axis in (Axis.DRIFT, Axis.SENSITIVITY, Axis.EQUIVALENCE):
            if axis in maturity.sub_scores:
                sub = maturity.sub_scores[axis]
                out.append(f"| {_AXIS_LABEL[axis]} | {sub:0.2f} |")
        out.append("")

    # Pillar coverage block — always shown for partially-measured runs;
    # otherwise only listed if any pillar is False (defensive).
    if maturity.pillar_coverage and (
        maturity.category == "Partially measured"
        or any(not v for v in maturity.pillar_coverage.values())
    ):
        out.append("## Pillar coverage")
        out.append("")
        for key in ("pillar_1", "pillar_2", "pillar_3"):
            if key not in maturity.pillar_coverage:
                continue
            label = _PILLAR_LABEL[key]
            if maturity.pillar_coverage[key]:
                out.append(f"- **{label}** — measured")
            else:
                reason = maturity.silent_pillars.get(key)
                why = (
                    _SILENCE_EXPLANATION.get(reason, "silent")
                    if reason else "silent"
                )
                out.append(f"- **{label}** — silent: {why}")
        out.append("")

    # What's wrong (top-3 findings).
    bad = whats_wrong(findings, limit=3)
    rec_for: dict[int, Recommendation] = {
        id(r.finding): r for r in recommendations
    }
    if bad:
        out.append("## What's wrong")
        out.append("")
        for n, f in enumerate(bad, start=1):
            out.append(f"{n}. **{f.title}** — {f.description}")
            rec = rec_for.get(id(f))
            if rec is not None:
                out.append(f"   - **Fix:** {rec.text}")
        out.append("")
    elif maturity.category == "Production-ready":
        out.append("## Result")
        out.append("")
        out.append("No issues detected. All v0.4 checks passed.")
        out.append("")

    # What's working.
    good = whats_working(findings)
    if good:
        out.append("## What's working")
        out.append("")
        for f in good:
            out.append(f"- {f.title}")
        out.append("")

    # Top fix — silent-pillar override mirrors practitioner reporter.
    fix_text: str | None = None
    for key in ("pillar_1", "pillar_2", "pillar_3"):
        if maturity.pillar_coverage.get(key) is False:
            reason = maturity.silent_pillars.get(key)
            if reason and reason in _SILENCE_FIX:
                fix_text = _SILENCE_FIX[reason]
                break
    if fix_text is None and top_fix_rec is not None:
        fix_text = top_fix_rec.text

    if fix_text is not None:
        out.append("## Top fix")
        out.append("")
        out.append(fix_text)
        out.append("")

    out.append(
        "_Run with `--verbose` for per-axis sub-score detail and the "
        "per-family breakdown._"
    )
    return out


def render(
    maturity: MaturityScore,
    findings: list[Finding],
    recommendations: list[Recommendation],
    top_fix_rec: Recommendation | None,
    *,
    out: TextIO | None = None,
) -> None:
    """Print the markdown report to *out* (default stdout)."""
    if out is None:
        out = sys.stdout
    for line in _build(maturity, findings, recommendations, top_fix_rec):
        print(line, file=out)


def render_to_string(
    maturity: MaturityScore,
    findings: list[Finding],
    recommendations: list[Recommendation],
    top_fix_rec: Recommendation | None,
) -> str:
    """Same as `render`, but returns a string."""
    return "\n".join(
        _build(maturity, findings, recommendations, top_fix_rec)
    ) + "\n"


# ── Back-compat shim ───────────────────────────────────────────────────────
# v0.3.0 had a `render_case_markdown` stub here. Preserve the symbol so
# any importer doesn't break — Phase 2 doesn't need a per-case markdown
# reporter beyond the practitioner-style one above.

def render_case_markdown(*args, **kwargs) -> str:
    raise NotImplementedError(
        "render_case_markdown is not implemented in v0.4. "
        "Use kelvin.reporters.markdown.render() for the v0.4 "
        "practitioner-style markdown report."
    )
