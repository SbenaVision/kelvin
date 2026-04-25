# Phase 1 Addendum — Time-Boxed Corpus Investigation

**Date:** 2026-04-25
**Time-box:** 1 day (~2 hours actual)
**Hypothesis tested:** numeric anchor failures (brittle ≈ constant; one_moderate ≈ grounded) are corpus-driven, not score-model-driven.
**Outcome:** **MIXED** — corpus is the issue for one pair, score-model aggregation is the issue for the other.

## What changed

Three new cases added under `cases/` (existing cases untouched):

| File | Purpose |
|---|---|
| `case_iso_a.md` | LedgerLite — gate rule has revenue language + "All conditions are met" |
| `case_iso_b.md` | QuoteShelf — gate rule has revenue language + "Some conditions are met" |
| `case_gate_first.md` | RootStack — `## Gate Rule` is the FIRST section (atypical structure) for `brittle` to flip on under reorder |

**Design intent:**
- `case_iso_a` / `case_iso_b` form a paired test for the conditions-status axis. Both have similar revenue-language content; they differ on conditions-status only. The legacy `swap` family (which replaces an entire governing unit) can swap between them, exercising the conditions-status axis with revenue language held approximately constant.
- `case_gate_first` puts the gate_rule clause at unit-position 0. This means `brittle`'s baseline routing is "growth" (not the usual "pre-seed"), and reorder will move gate_rule away → brittle should flip more.

**No source code touched.** No anchors retuned. No pipeline internals changed.

## New numbers (calibration on 9-case corpus)

```
pipeline           |  η   | sens_cal | inv_cal | score | target | Δ |   category
-------------------+------+----------+---------+-------+--------+---+------------------------
constant           | 0.000| 0.000    | 1.000   |   1   |   1    | 0 | Not production-ready ✓
brittle            | 0.000| 0.000    | 0.940   |   1   |   2    |-1 | Not production-ready ✓
mid_issue          | 0.254| (None)   | (None)  |   4   |   4    | 0 | Needs work           ✓
one_moderate_issue | 0.000| 0.444    | 0.964   |   4   |   7    |-3 | Needs work           ✗
grounded_oracle    | 0.000| 0.667    | 0.972   |  10   |  10    | 0 | Production-ready     ✓

Numeric anchor pass rate (±1):  3/5  (constant, brittle, mid_issue)
Ordinality:                      PASS (1, 1, 4, 4, 10 — equality allowed)
Stability (mid_issue × 3):       range = 1, PASS
```

## What the new corpus DID change

### one_moderate_issue ≠ grounded_oracle (corpus issue confirmed for this pair)

Old 6-case corpus: `sens_cal = 0.667` for BOTH.
New 9-case corpus: `sens_cal = 0.444` (one_moderate) vs `0.667` (grounded). **Δ = 0.222.**

The paired iso_a / iso_b cases worked. With these in the corpus:
- Some `swap` perturbations cross JUST the conditions-status axis (replacing iso_a's gate_rule with iso_b's, or vice versa, while revenue language is approximately preserved).
- one_moderate ignores conditions-status → no decision change → contributes 0 to its sensitivity distance pool on these specific swaps.
- grounded reads conditions-status → decision changes → contributes 1 to its sensitivity pool.

Aggregate: one_moderate's sens_cal drops by ~0.22 vs grounded. **Real signal.**

The score formula then under-scores one_moderate (4 vs target 7) because the ANCHOR TABLE was fitted to the OLD 6-case corpus where one_moderate had sens_cal=0.667. With a re-anchored table fitted to the NEW corpus (one_moderate's anchor at sens=0.444 → sub=0.667), the score would land at ~7.

**Per the experiment's constraint ("do not retune ANCHORS"), I did not re-anchor.** The off-target score is a calibration-coupling effect, not a model-shape error.

### brittle still ≈ constant (score-model aggregation issue)

`case_gate_first` did not move brittle's score. Reasons:

1. **Reorder cap is 3 per case** (in `src/kelvin/perturbations/reorder.py`). Adding a single case adds at most 3 reorder perturbations to the pool.
2. **Pillar 3 families don't change the first header.** whitespace_jitter, punctuation_normalize, bullet_reformat, hedge_injection, etc. all leave the section ORDER unchanged. So brittle stays invariant under all 8+ Pillar 3 families.
3. **Aggregation dilutes single-family failures.** Kelvin's invariance pool flattens 11 invariance families into one mean distance. A pipeline that flips 100% of the time on reorder but 0% on the other 10 families produces an average distance of ≈ `1 × (n_reorder / n_total) = 3/24 ≈ 0.125`, giving inv_raw ≈ 0.875 — far from the 0.3 needed for eq_subscore = 0.111.

**No corpus engineering can fix this.** Even with hundreds of case_gate_first-style cases, brittle's pooled invariance can't drop below ~0.7 because the other 10 invariance families never flip. This is a STRUCTURAL aggregation issue in the score model, not a corpus issue.

## Hypothesis verdict

**Mixed:**
- ✓ Corpus IS the issue for `one_moderate_issue` vs `grounded_oracle`. The new iso_a / iso_b paired cases produce a measurable separation (0.222 in sens_cal). With re-anchoring permitted, the score would land near target.
- ✗ Corpus is NOT the issue for `brittle` vs `constant`. The score model's pooled-invariance aggregation flattens single-family failures by design. No corpus addition can recover this.

## Implications for Phase 2

Two structural realities to accept going forward:

1. **The score formula is calibration-coupled to the corpus.** Adding cases changes the empirical metric distribution, which silently changes what each anchor's metric → sub-score mapping means. Phase 2's reporter must be transparent about this: the numeric is corpus-relative, not absolute.

2. **Single-family failures are sub-threshold under pooled invariance.** A pipeline that's brittle to ONE perturbation family produces a score nearly indistinguishable from a fully-invariant constant pipeline. This is a real diagnostic blind spot — it means Kelvin can't surface "you're broken on reorder specifically" through the maturity score; only through per-family breakdowns.

Both of these have category-level workarounds:
- Category fallback is robust to anchor drift (the band edges are far from the anchor metric values).
- Per-family findings (Phase 2) can call out the brittle-on-reorder failure even if the maturity score doesn't.

## Recommendation for Phase 2

**Phase 2 with category-only as the practitioner-facing default.** Three reasons reinforced by this addendum:

1. **Category is robust to corpus drift.** Numeric is corpus-coupled.
2. **Findings (Phase 2 deliverable) recover the per-family signal.** A pipeline that's brittle on reorder will get a finding card that says so, even if its maturity score is "Not production-ready" alongside `constant`'s "Not production-ready".
3. **Scope is honest.** Shipping a 1–10 number that we know is sub-discriminating on real common failures (reorder fragility specifically) would mislead practitioners.

**Backlog for v0.5+** (post-Phase-3 ship):
- **Re-architect invariance aggregation** to MIN-over-per-family sub-scores instead of flat-mean across families. Brittle would surface as broken on reorder family, hitting eq_subscore ≈ 0 → maturity 1 (still 1 by MIN, but with diagnostic clarity).
- **Re-anchor the calibration** when a richer corpus or live LLM-pipeline data is available.
- **Drop the synthetic anchor pipelines** in favor of "anchor by behavior" — i.e., compute anchors at run time from the pipeline being tested, comparing to baseline expectations rather than absolute scales.

## Stability finding (bonus)

mid_issue stability with 9-case corpus: range = 1 (scores 4, 5, 4 across 3 runs) — PASS.
With 6-case corpus: range = 2.

Adding cases stabilizes the noise-floor measurement. That's a clean side benefit.

## Time accounted

- Case design: 30 min (read existing schema, design 3 cases that differ in targeted ways)
- Calibration runs: ~10 min wall-clock (3 anchors deterministic + 3 mid_issue stability)
- Analysis + this addendum: 1 hour

Well under the 1-day box.

## STOP

Phase 1 stops here per the calibration's authorized fallback path. Awaiting SBA review before Phase 2.
