# Kelvin 0.3.0 Paper Fallback Ladder

Written before implementation starts so thresholds aren't relaxed mid-stream
to save a headline. If a pillar fails its acceptance criterion, it demotes
or is cut. The paper narrative adapts down the ladder, not across it.

## Ladder

### Tier 0 — Full scope (target)
Noise-calibrated K + counterfactual-controlled sensitivity decomposition +
three validated intra-slot families (bank invariance, numeric_magnitude,
comparator_flip, polarity_flip) + six rhetorical intra-slot families with
≥90% meaning-preservation rates.

Paper title: "Noise-Calibrated Metamorphic Diagnostics for LLM-backed RAG
with Counterfactual-Controlled Sensitivity."

### Tier 1 — Pillar 2 demotes to appendix
Triggered by: AC-2.3 clean-parse rate falls below 50% on the 8-case corpus.

Paper leads with Pillar 1 + Pillar 3. Decomposition theorem stated
analytically in an appendix with empirical validation deferred. Title
shifts to "...with Validated Intra-Slot Rhetorical Probes" — Pillar 3
becomes the second headline contribution.

### Tier 2 — Rhetorical families cut below threshold
Triggered by: AC-3.2 cuts ≥3 of the six rhetorical families (meaning-
preservation <90%).

Paper drops the rhetorical-robustness story. Leads with Pillar 1 +
bank invariance (irrelevant_paragraph_injection) + the three sensitivity
families (numeric_magnitude/comparator_flip/polarity_flip). Still a
methods contribution: noise calibration for LLM-backed RAG + three
sensitivity operators with validated pair lists.

### Tier 3 — Pillar 1 alone is the contribution
Triggered by: Tier 1 AND Tier 2 both fire, AND AC-3.1 bank validation
fails (α < 0.8).

Paper is "Noise-Calibrated Metamorphic Diagnostics" — Pillar 1 stands on
its own with the degenerate-preservation theorem, the adversarial-
detection result (peer-swap adversary), and the live VA API
demonstration showing K_cal < K_raw. Ships as 0.3.0. The Pillars 2 & 3
attempts are documented in the appendix as "what we tried" with the
measurement gaps.

## Threshold Discipline

The thresholds in the AC list are the thresholds. If the data comes in
at 87% meaning-preservation where the threshold is 90%, the family
demotes to opt-in. No rounding, no "close enough," no post-hoc rubric
adjustment.

Rater disagreements (α below 0.8) trigger one round of rubric revision
and re-labeling — this is explicit in the Phase C2/D3 timeline. A second
failure cuts the family.

## What We Will Not Do

- Relax α ≥ 0.8 to 0.7 to save the bank.
- Drop difficult cases from the corpus to raise clean-parse rate.
- Report an aggregated family score when individual families failed and
  were silently included.
- Change the sensitivity-curve amplitude set post-hoc to produce a
  cleaner monotone.
- Publish 0.3.0 before the paper is drafted and self-reviewed.

## When This File Is Updated

Only as a post-release artifact recording what actually happened. No
mid-stream edits. If SBA or the assistant is tempted to edit this file
during Phase C-F, the correct response is to stop and discuss.
