# Kelvin Backlog

Captured items for v0.5+ that surfaced during v0.4 development. Each
item names the problem it fixes and the diagnostic that produced it.

## High priority — must-fix-soon

### B-3 (PROMOTED). Pillar 2 swap_condition format coverage

**Status: HIGH PRIORITY.** Promoted from "v0.5 — Score model" on
2026-04-25 after the Phase 1 Envelop run produced a misleading 10/10
"Production-ready" verdict because Pillar 2 silently failed to fire.

**Why this is high priority.**
- Until B-3 lands, **Envelop's Kelvin score is uninterpretable**: the
  Phase 1 run reported maturity 10/10 / Production-ready, but
  `sensitivity_condition` and `content_effect` were both `None`
  because Envelop's gate_rule format
  (`Goal frame: ... / Stage profile: ... / Dimensions: ...`) doesn't
  match Kelvin's expected `requires: <list>. <state_phrase>. <details>`.
- **Any user pipeline with a non-standard gate_rule format will
  produce the same false-positive verdict.** A practitioner could ship
  a pipeline that Kelvin says is Production-ready when in fact one of
  the three pillars wasn't even measured.
- This is the exact failure mode v0.4's verdict surface is supposed to
  prevent.

**Mitigation in v0.4 Phase 2.** Reporter must surface silent pillars
explicitly (see "Reporters / UX → silent-pillar handling" below) so
the verdict is never "Production-ready" when a standard pillar didn't
fire. That contains the symptom; B-3 fixes the cause.

**Problem.** Pillar 2 (counterfactual-controlled swap) requires the
gate_rule body to match the regex `^(.*?\brequires:\s+)(.+?)\.\s+(.+)$`
and the state_phrase to be one of a fixed canonical list ("All
conditions are met.", etc.). Pipelines that use a different gate_rule
schema don't match → `swap_condition` produces zero contributing
perturbations → Pillar 2 metrics are all None.

**Diagnostic that produced it.** Phase 1 Envelop run on
`experiments/envelop_local/pipelines/envelop.py` with K=30 replays:
`sensitivity_condition = None`, `content_effect = None`,
`sensitivity_content = None`. The `swap_condition` family fired zero
perturbations because Envelop's gate_rule doesn't have "requires:"
+ state_phrase.

**Fix options.**
- Generalize `swap_condition` to accept pluggable gate_rule grammars
  (config-declared rule shape — e.g., a `gate_rule_grammar:` block in
  `kelvin.yaml` that names a parser plugin or supplies a regex with
  named capture groups for the swappable axes).
- Or: ship a no-Pillar-2 mode that hides Pillar 2 metrics from the
  report when no perturbations fire (currently emits None fields).
  This is a coverage workaround, not a real fix.

**Impact when fixed.** Pipeline authors using non-canonical gate_rule
formats can extract Pillar 2 signal directly. Envelop becomes
meaningfully evaluable through Kelvin (currently it isn't).

**Blockers explicitly named.**
- This blocks meaningful Envelop evaluation.
- This blocks any v0.5 LLM-backed re-anchoring (B-2) on a non-standard
  pipeline.
- This blocks generalizing Kelvin to "any structured-decision RAG"
  pipelines, since most real pipelines won't use Kelvin's exact
  `requires: ...` format.

---

## v0.5 — Score model

### B-1. MIN-over-per-family invariance aggregation

**Problem.** The v0.3.0 invariance signal is a flat mean across all 11
invariance perturbation families. A pipeline that's brittle on ONE
family (e.g., reorder) produces an average distance ≈ 1×(n_reorder /
n_total) ≈ 0.07–0.13. After η subtraction, inv_cal is still ≥ 0.9 —
indistinguishable from a fully-invariant pipeline.

**Diagnostic that produced it.** Phase 1 calibration: `brittle` (which
fails ONLY on reorder by design) produced inv_cal = 0.94, identical to
`constant` (which fails on nothing). Pipeline-by-pipeline:

| pipeline | inv_cal | failure mode |
|---|---|---|
| constant | 1.000 | always returns same answer |
| brittle | 0.940 | flips on reorder; invariant elsewhere |

The pooled-mean structure dilutes single-family failures by ~10× and
makes them sub-threshold for any plausible eq_subscore anchor.

**Fix.** Re-architect `kelvin/scorer.py` and `kelvin/score.py` so the
equivalence axis aggregates as **MIN across per-family sub-scores**,
not flat mean across all families. A pipeline that fails on one family
(reorder hold-rate ≈ 0.3) gets eq_subscore ≈ 0.1 from MIN aggregation;
the other 10 families' near-perfect hold-rates are correctly ignored.

**Impact.** brittle scores 1–2 (matching its design intent) instead of
collapsing to constant's 1. Per-family findings (Phase 2 deliverable)
already surface the per-family signal; the score gains alignment with
findings.

**Risk.** MIN aggregation is more pessimistic. A pipeline that's 99%
invariant on 10 families and 50% invariant on 1 family will MIN-score
worse than its mean would suggest. This is by design (Kelvin should
flag ANY broken axis), but practitioners may need education.

### B-2. Re-anchor calibration with live LLM-pipeline data

**Problem.** The v0.4 ANCHORS table is fitted to the synthetic
deterministic reference pipelines on the v0.3 cases/ corpus. Real
LLM-backed pipelines have:

- Native stochasticity (η > 0 even when nothing is wrong).
- Different invariance distributions (LLMs treat whitespace_jitter
  differently than rule-based pipelines).
- Potentially richer separation across axes (the corpus collapse that
  hit `brittle ≈ constant` may not hit real LLM pipelines).

**Diagnostic that produced it.** Phase 1 addendum: corpus expansion
moved `one_moderate_issue`'s sens_cal from 0.667 → 0.444 — real signal
that the OLD corpus was hiding. The current ANCHORS table was fit to
the 6-case corpus and now under-scores `one_moderate_issue` on the
9-case corpus.

**Fix.** Once Envelop (or another live LLM-backed pipeline) is run
multiple times and the empirical metric distribution is characterized,
refit the ANCHORS table. Specifically:

- Run live Envelop with K=20 baseline replays × 3–5 corpus draws.
- Measure per-axis (η, sens_cal, inv_cal) distributions.
- Set anchors at empirical extremes + "good" reference target.
- Cross-validate against synthetic reference pipelines.

**Impact.** Score becomes robust to corpus drift and reflects what
practitioners actually see on production pipelines.

### B-3 — see "High priority" section above.

## v0.5 — Reporters / UX

### B-4. Per-family findings card

Already in scope for Phase 2. Listed here for cross-reference: a
practitioner-facing card that surfaces per-family hold rates and
flags axes where the score is sub-threshold. This is the natural
companion to B-1 (MIN aggregation) — even before B-1 lands, the
findings card recovers the per-family signal that the maturity score
washes out.

## v0.5 — Documentation

### B-5. Calibration coupling note in docs/methodology.md

The maturity score's anchor table is corpus-coupled. Document this
explicitly: numeric scores produced by Kelvin v0.4 are calibrated
against a specific reference set on a specific corpus, and the same
pipeline can score differently if the corpus changes substantially.
Recommend the category surface as the durable signal.

---

## Backlog hygiene

- Items here are NOT promised features — they're tracked diagnostics.
- Each item names the experimental finding that produced it. If the
  finding is invalidated by later work, the backlog item retires.
- Items move into a release plan only when paired with a roadmap
  decision; no implicit promotion.

Last updated: 2026-04-25 (Phase 1 + Envelop run).
