# Envelop run — practitioner interpretation

**Date:** 2026-04-25 · K=30 replays · 8 cases · pipeline `experiments/envelop_local/pipelines/envelop.py`

## Headline

```
Maturity:  10 / 10
Verdict:   Production-ready
```

## Per-axis raw metrics

| Axis | Raw metric | Sub-score (0–1) |
|---|---|---|
| Drift (η) | 0.0000 | 1.000 |
| Sensitivity (calibrated) | 0.875 | 1.000 |
| Equivalence / Invariance (calibrated) | 1.000 | 1.000 |

## Per-family breakdown

```
invariance (overall):   1.000           ← perfectly invariant under reorder/pad/Pillar 3
sensitivity (overall):  0.875           ← reads the rule and responds
sensitivity_by_type:    {gate_rule: {mean: 0.875, sample: 8}}
mechanical_sensitivity: 0.750           ← numeric/comparator/polarity flips move the verdict 75% of the time
sensitivity_content:    None            ← Pillar 2 (counterfactual swap) silent
sensitivity_condition:  None            ← (see "Findings" below)
content_effect:         None            ← (idem)
```

## Top weakest axes

All three axes hit sub-score 1.000. There is no weakest axis.

## What would the practitioner fix?

**Nothing concrete.** The breakdown is consistent with a deterministic,
rule-tracking, drift-free pipeline. Specifically:

- **Drift = 0.** Verdict is a pure function of the seven dimensions
  + goal frame + stage profile, computed by `vvs.compute()`. No
  randomness to fix.
- **Invariance = 1.0.** Reorder, padding, whitespace_jitter,
  punctuation_normalize, bullet_reformat, non_governing_duplication,
  and the four rhetorical families (hedge / politeness / discourse /
  meta) all preserve the verdict. The pipeline reads ONLY the
  `## Gate Rule` section, so cosmetic perturbations elsewhere are
  invisible to it.
- **Sensitivity = 0.875.** When the gate_rule is swapped for a peer's,
  the verdict moves on 7 of 8 cases. The one case that doesn't move
  is consistent with band quantization (see below).

## Two non-actionable observations worth surfacing

1. **`mechanical_sensitivity = 0.75 < overall sens = 0.875`.**
   A small fraction of numeric_magnitude / comparator_flip /
   polarity_flip perturbations don't change the verdict. This is
   *not* a bug — it's an artifact of Envelop's coarse band
   quantization (`vvs.BANDS` partitions VVS scores into 6 bands of
   width ~50–100 points). A small numeric flip on one of the seven
   dimensions can leave the score in the same band → same verdict.
   This is band-design behavior, not pipeline brittleness.

2. **Pillar 2 (`sensitivity_condition`) is `None`.**
   Kelvin's `swap_condition` family expects a gate_rule body matching
   `requires: <list>. <state_phrase>. <details>`. Envelop's gate_rule
   format is structured differently (`Goal frame: ... / Stage profile:
   ... / Dimensions: P=5 ...`), so `swap_condition` produced zero
   contributing perturbations. **This is a Kelvin coverage gap, not an
   Envelop issue.** Tracked in the v0.5 backlog as B-3.

## Honest assessment

**The maturity score is correct for Envelop and confirms what the
pipeline author already knows: the rule-routing layer is sound.** The
breakdown does NOT suggest anything for the practitioner to fix.
That is a finding worth recording — it's evidence that:

- Kelvin's invariance + sensitivity machinery works on a real
  rule-tracking pipeline.
- The category surface ("Production-ready") gives the right top-line
  signal.
- The numeric ("10 / 10") is informative on the WIN side too — it
  tells the practitioner "no axes are weak; you don't need to spend
  time investigating".

## What this means for Phase 2 scope

The Phase 2 reporter should handle BOTH cases gracefully:

- **Pipeline scores Production-ready with no weakest axis.** Default
  output: `Maturity: Production-ready. No issues found in the v0.4
  catalogue.` (No top-fix line; no findings card.)
- **Pipeline scores below Production-ready.** Default output:
  category + top-3 weakest axes + top-1 fix recommendation.

Findings + recommendations machinery is still required for
sub-Production cases. The Envelop run shows the "clean bill of
health" path is also a real shape we'll encounter and should not
fabricate findings for.

## Phase 2 implication: don't over-engineer findings

For pipelines that are clean (like Envelop), the reporter should NOT
generate fake findings or bogus recommendations. A hand-curated
findings table (per the Phase 2 spec) plus a "no issues" fall-through
keeps it honest.

## Reproducibility

```bash
cd /Users/sb/MyDev/Kelvin/.claude/worktrees/v040-phase1
.venv/bin/python experiments/v040_phase1_calibration/run_envelop.py
```

Output: `experiments/v040_phase1_calibration/envelop_results.json`.
