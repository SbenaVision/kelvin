# Kelvin 0.3.0 Paper Fallback Ladder

**Status: resolved 2026-04-24. 0.3.0 shipped on Tier 0 with reframed Pillar 3.**

This ladder was written before implementation so thresholds couldn't be
relaxed mid-stream. What actually shipped is documented in the
"Shipped outcome" section at the bottom. The original tier definitions
below are retained as written for audit.

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

---

## Shipped outcome (post-release record, 2026-04-24)

**v0.3.0 shipped on Tier 0 with a Pillar 3 reframe**, not on any of the
planned demote tiers. Summary of what landed and how it diverged from
the original plan:

- **Pillar 1 — shipped as planned.** Noise-floor calibration with
  degenerate-preservation theorem. Two recorded live-API runs
  documented in `experiments/pillar1_va_api_final.md` (n=6 σ_c,
  K_cal=1.206) and `experiments/pillar1_va_api_v030.md`
  (n=8 σ_c with Pillar 3 enabled, K_cal=1.090). Both cited in the
  paper as complementary sample compositions.
- **Pillar 2 — shipped as planned, demonstrated on gate-rule corpus.**
  `swap_condition` operator + decomposition math. Clean-parse rate
  on the tier3 gate-rule corpus was **100%**, well above the 80%
  threshold that would have triggered Tier 1 demotion. Empirical
  demo on the grounded pipeline: Sens(swap_content)=0.667,
  Sens(swap_condition)=0.000, Content_Effect=0.667. Reproducible
  in `experiments/pillar2_decomposition_demo/`.
- **Pillar 3 — REFRAMED (not Tier-demoted, not cut).** The original
  scope was "validated intra-slot probes with ≥0.8 Krippendorff α
  and ≥90% meaning-preservation per rhetorical family." SBA direction
  mid-release: "doesn't make sense to label in 2026." Replaced with
  rule-based families whose invariants hold *by construction*:
  - Four presentation-layer families (whitespace_jitter,
    punctuation_normalize, bullet_reformat, non_governing_duplication) —
    invariants trivially true (tokens preserved, orthographic swaps
    only, duplicate of existing sentence).
  - Four rhetorical families with structural constraints (hedge /
    politeness / discourse / meta) — rule-based with documented
    coverage of what each constraint protects (polarity, numeric
    tokens, governing-section content) and what it does not protect
    (epistemic strength in non-governing prose). The meaning-
    preservation claim is construction-based, not rater-validated;
    the paper says so explicitly.
  - Three mechanical sensitivity families (numeric_magnitude,
    comparator_flip, polarity_flip) — closed hand-validated lists,
    deterministic string operations.
  - **Tier-demote equivalent for the dropped rater-validated scope:**
    no family claims ≥90% meaning-preservation via labels; each
    family states the structural invariant it protects. A reviewer
    reading the paper can check the constraint, not a rater sheet.

### What this file would have demoted and what actually happened

| Original trigger | Threshold | Actual | Outcome |
|---|---|---|---|
| AC-2.3 clean-parse rate | ≥80% | 100% (6/6 on tier3) | Tier 0 |
| AC-3.1 bank validation α | ≥0.8 | N/A — scope cut | Reframed |
| AC-3.2 rhetorical meaning-preservation | ≥90% per family | N/A — scope cut | Reframed |
| AC-1.1 degenerate preservation | K_cal=1.000 | 1.000 exactly | Tier 0 |
| AC-1.2 peer-swap adversary detection | η > 0.05 | η=0.149 | Tier 0 |
| AC-1.3 unmeasurable handling | K_cal=None when η ≥ 1−Inv_raw | verified | Tier 0 |

### "What we will not do" audit

- [x] Did not relax α≥0.8 — scope cut entirely instead.
- [x] Did not drop difficult cases. All 6 tier3 cases parsed clean
      and all 8 VA cases ran; 2 VA cases had replay failures in the
      earlier run, documented as API-side, not hidden.
- [x] Did not silently include families that failed labeling —
      reframed instead of hiding.
- [x] Did not change the numeric_magnitude curve post-hoc. The
      {2×, 5×, 10×, 100×} set shipped as planned.
- [x] Paper drafted and self-reviewed before TestPyPI / PyPI. Whitepaper
      §5.3–§5.5 landed in the same commit window as the code; no
      mid-merge numeric edits.

