"""Hand-curated fix recommendations per finding.

Each recommendation is a 1–2 sentence concrete action a practitioner
can take in <1 hour (AC4). When no concrete fix is known, the
recommendation says so explicitly via `needs_investigation=True` —
we don't fabricate.

The map from (axis, severity) → recommendation is hand-written and
auditable here. Adding a new pattern means editing this file.
"""

from __future__ import annotations

from dataclasses import dataclass

from .findings import Finding
from .taxonomy import Axis


@dataclass(frozen=True)
class Recommendation:
    """One actionable fix tied to a Finding.

    `needs_investigation = True` when no canned recommendation
    applies; the text instructs the user to inspect the per-family
    breakdown manually.
    """
    finding: Finding
    text: str
    needs_investigation: bool


# Map (axis, severity) → recommendation text. Hand-curated; covers
# the common practitioner failure modes that v0.4 expects to surface.
_RECOMMENDATION_TABLE: dict[tuple[Axis, str], str] = {
    # Drift
    (Axis.DRIFT, "severe"): (
        "Set temperature=0 in your LLM calls and re-check. If your "
        "pipeline isn't LLM-backed, look for non-deterministic input "
        "(timestamps, randomized retrieval order, time-of-day code "
        "paths)."
    ),
    (Axis.DRIFT, "moderate"): (
        "Reduce sampling temperature (try 0.0–0.2). If the pipeline "
        "is rule-based, audit any code path that reads time, RNG, or "
        "set-iteration order."
    ),
    # Sensitivity (rule-blindness)
    (Axis.SENSITIVITY, "severe"): (
        "Check your prompt or routing code: the rule text isn't "
        "reaching the decision logic. Confirm the rule is being "
        "passed to the model and isn't being truncated, summarized, "
        "or pre-emptied by a system prompt."
    ),
    (Axis.SENSITIVITY, "moderate"): (
        "Audit which parts of the rule your pipeline reads. If only "
        "some clauses drive the output, decide whether that's by "
        "design (skip the others) or a bug (add them to the prompt)."
    ),
    # Invariance / Equivalence
    (Axis.EQUIVALENCE, "severe"): (
        "Don't route off surface features (first character, byte "
        "length, raw header). Parse the input semantically before "
        "branching, and treat formatting as cosmetic in your routing."
    ),
    (Axis.EQUIVALENCE, "moderate"): (
        "Identify which formatting changes flip your output (look at "
        "the per-family breakdown in --verbose). Normalize that "
        "axis at the entry point or in your prompt."
    ),
}


def recommendation_for(finding: Finding) -> Recommendation:
    """Return the canned recommendation for a finding, or a
    needs-investigation stub when no canned text applies."""
    if finding.severity == "good":
        # No fix needed — but we synthesize a "keep doing this" stub
        # for symmetry. Reporter typically skips good findings.
        return Recommendation(
            finding=finding,
            text="Already on track. Keep this stable as the pipeline evolves.",
            needs_investigation=False,
        )

    text = _RECOMMENDATION_TABLE.get((finding.axis, finding.severity))
    if text is None:
        return Recommendation(
            finding=finding,
            text=(
                "No canned recommendation for this combination. "
                "Inspect the per-family breakdown via --verbose, then "
                "audit the failing axis in your pipeline code."
            ),
            needs_investigation=True,
        )
    return Recommendation(finding=finding, text=text, needs_investigation=False)


def compute_recommendations(findings: list[Finding]) -> list[Recommendation]:
    """Return one Recommendation per Finding, in input order."""
    return [recommendation_for(f) for f in findings]


def top_fix(recommendations: list[Recommendation]) -> Recommendation | None:
    """The single highest-impact actionable recommendation.

    Skips good-severity recs (no fix needed) and needs_investigation
    recs (we don't promote those as the headline). Returns None when
    nothing actionable exists — caller should suppress the "Top fix"
    line in that case.
    """
    actionable = [
        r for r in recommendations
        if r.finding.severity in ("severe", "moderate")
        and not r.needs_investigation
    ]
    if not actionable:
        return None
    return max(actionable, key=lambda r: r.finding.impact)
