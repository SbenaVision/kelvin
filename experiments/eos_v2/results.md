# EOS v2 — sealed-catalogue results

**Date:** 2026-04-25
**Sealed catalogue sha256:** `f73ca3324a321d80dc3d63e6bf4afa9f6240cdfd0a658acacbe7209dc8c1b144`
**Status:** **PARTIAL PASS — 6 of 8 criteria.** Signature-level separation works; two criteria fail for diagnosable reasons (documented below).

---

## What this proves

When the sealed catalogue is run against five locally-implemented adversaries (f_track, f_ruleblind, f_constant, f_wrongstatic, f_wrongstochastic) with injected score-jitter noise, the per-pipeline EOS signatures Σ(·) computed under noise-aware Clopper–Pearson + Bonferroni acceptance:

1. **Separate cleanly at the (T, R) pair level.** Σ(f_track) ≠ Σ(f_ruleblind) ≠ Σ(f_constant) ≠ Σ(f_wrongstatic) ≠ Σ(f_wrongstochastic) on rule-bearing axes. Criterion c1 PASSES.
2. **Correctly flag rule-blind pipelines as ignored-candidate.** f_ruleblind and f_constant classify as `ignored-candidate` on 100% of rule-bearing T's. Criterion c2 PASSES at 100% (vs. 75% target).
3. **Correctly classify f_wrongstochastic as degraded.** Both rule-bearing axes register `unstable` (not `responsive-correct`) on the stochastic adversary. Criterion c4 PASSES.
4. **Preserve invariance on non-causal axes.** f_track classifies order, optional, and non_rule_fact as `invariant-candidate`. Criterion c5 PASSES.
5. **Stable across independent corpus draws.** Pairwise Jaccard(Σ_i, Σ_j) for f_track = 1.000 across all three pairs of K_D=3 draws; triple intersection size = 15. Criterion c6 PASSES.
6. **No adversary misclassified as rule-tracking.** Criterion c8 PASSES.

The signature-level claim — that EOS distinguishes rule-tracking from a defined adversary class — is upheld.

## What this does not prove

This is an **Envelop-LIKE local structured-decision pipeline**, not the production Envelop system. It tests EOS *separation mechanics* under deterministic + injected-noise conditions; it does not prove:

1. **Real LLM-backed EOS.** Native LLM stochasticity has different distributional shape (heavy-tailed, prompt-dependent) than the uniform integer jitter used here. Real-pipeline validation requires the LLM-backed experiment under the same sealed methodology.
2. **Universal applicability for arbitrary pipelines.** All five pipelines here are deterministic Python functions with shared injected noise. Generalisation to opaque pipelines remains open.
3. **That this catalogue would pass on a third-party pipeline.** The catalogue was sealed *before* adversary code was written, but f_track is implemented by the same author who wrote the catalogue. A truly independent black-box test is the next experiment.
4. **Semantic correctness of any single output.** EOS tests behavioural relations, not semantic ground truth.
5. **Completeness of the catalogue.** Uniform invariance on a non-causal axis is `invariant-candidate`, not "definitely irrelevant" — it could still be a saturation or under-tested artifact. Thesis §7 caveat retained explicitly.

---

## Setup (sealed; from `config.py`)

| Parameter | Value |
|---|---|
| Pipelines | 5 |
| K_D (independent draws) | 3 |
| N per draw | 300 |
| K_REPLAYS (baseline) | 20 |
| Boundary fraction | 65% |
| `\|T\|` | 22 (incl. identity sanity) |
| `\|R^Ω\|` | 4 (R_eq_omega, R_up_omega, R_down_omega, R_sign_eq) |
| m = `\|T\|·\|R^Ω\|` | 88 |
| ε | 0.10 |
| δ | 0.05 |
| α = δ/m | 5.682 × 10⁻⁴ |
| Δ_eq, Δ_dir | 5, 4 score points |
| Noise quantile | q_0.95 from K(K-1)/2 = 190 pairwise differences |
| Score noise injection | p_noise=0.12, jitter ∈ {-3,-2,-1,1,2,3} |
| f_wrongstochastic attack | p_attack = 0.40 (last clause skipped) |
| n_eff_min | 150 |
| Jaccard target | 0.80 |

---

## Criterion-by-criterion results

| # | Criterion | Result | Detail |
|---|---|---|---|
| c1 | Σ(f_track) separates from each adversary on rule-bearing axes | **PASS** | sep-blind=True, sep-const=True, sep-wrong=True, sep-stoch=True |
| c2 | f_ruleblind & f_constant ≥75% ignored on rule-bearing T's | **PASS** | 100% / 100% |
| c3 | f_wrongstatic wrong-direction on corrupted clause | **FAIL** | axis=unstable (0 directional accepts) — see diagnosis |
| c4 | f_wrongstochastic degraded rule-axis signature | **PASS** | rule_threshold=unstable, rule_clause=unstable |
| c5 | f_track order/optional/non_rule_fact invariant | **PASS** | all three = invariant-candidate |
| c6 | f_track pairwise Jaccard ≥ 0.80 | **PASS** | min=1.000, triple-intersection=15 |
| c7 | Load-bearing noise floor (some naive accepted but R^Ω rejected) | **FAIL** | 0 pairs in the divergence zone — see diagnosis |
| c8 | No adversary misclassified as rule-tracking | **PASS** | none |

---

## Diagnosis of the two failures

Both failures come from **configuration choices in the seal** interacting with the relation-form requirements, not from EOS methodology breaking.

### c3 — wrong-direction not detected at axis level

The wrong-direction signal **is** present at the (T, R) pair level. On `strengthen_risk_threshold`, draw 0:

```
f_track:        R_down_omega  k = 70/300  (correct direction, p̂ = 0.23)
f_wrongstatic:  R_up_omega    k = 70/300  (WRONG direction, p̂ = 0.23)
                R_down_omega  k =  0/300
```

The pipelines respond in opposite directions on exactly this axis — that *is* the detection. Both fall well below the acceptance threshold (1−ε = 0.90 with α = 5.7×10⁻⁴). The axis classifier therefore sees `null` on these T's and reports `unstable`.

**Root cause.** The noise-aware directional relation `R_up_omega: y₂ − y₁ ≥ q + Δ_dir` requires the directional effect to hold *on every applicable case*. Rule-threshold perturbations produce effects only on cases whose value sits between the old and new threshold (e.g., `strengthen_risk_threshold: 40 → 30` flips only cases with risk_score in [31, 40]). Even on the active-boundary subset, this is a minority (~30%). The relation is structurally incapable of accepting "directional response on the responsive subset" through universal Bernoulli evaluation alone.

**Fix path (not applied — would violate the seal).** Either:
- a per-T effective-applicability filter that restricts evaluation to cases the perturbation can flip (would push n_eff below the 150 floor → `unresolved`); or
- a new relation `R_consistent_dir`: "y₂−y₁ has the predicted sign or is within q+Δ_eq of zero" (sparse-effect-friendly); or
- evaluate rule-axis relations on the active-boundary subset for *all* pipelines (currently restricted to f_wrongstochastic per plan §11.4).

The first option is best for v3.

### c7 — load-bearing not exercised

No (T, R) pair shows naive accepted while R^Ω rejected. Naive R_up_naive accepts at `y₂−y₁ ≥ 4`; R^Ω_up at `y₂−y₁ ≥ q+4 ≈ 7`. The two only diverge when the score effect lands in [4, 6].

**Root cause.** Score noise in the seal is `{-3,-2,-1,+1,+2,+3}` (max ±3). Rule-flip effects are exactly 20 (`60·(1/total_clauses)`). There is no transformation in the catalogue that produces a 4–6 score-point effect — every effect is either ~0 (no flip, just jitter) or ≥20 (flip). The naive-vs-omega divergence zone is empty.

**Fix path (not applied).** Either widen the noise distribution to include ±5 / ±7 deltas (so jitter alone could pass naive directional but fail omega), or add transformations with smaller effect sizes (e.g., a `bump_revenue_by_500` whose effect is sub-flip).

This is *not* a methodology failure — it's a calibration finding. In a real LLM-backed pipeline, native noise would routinely sit in the 3–8 score-point range, and the divergence zone would be populated.

---

## Signature differences (draw 0, accepted post-subsumption, non-identity)

| | `\|Σ\|` |
|---|---|
| f_track | 15 |
| f_wrongstatic | 16 |
| f_ruleblind | 37 |
| f_constant | 21 |
| f_wrongstochastic | 7 |

f_ruleblind has the largest signature because it is uniformly invariant on every axis (R_eq_omega + R_sign_eq accepted nearly everywhere — the rule-blind signal). f_wrongstochastic has the smallest because its bimodal output distribution (attack-fired vs. attack-not-fired) inflates q_0.95 on rule axes and breaks invariance there.

### Σ(track) ∖ Σ(ruleblind)
0 pairs that ruleblind doesn't already accept — but f_track accepts FEWER than ruleblind on rule axes; the *missing* pairs are the signal. Σ(ruleblind) ∖ Σ(track) = 22 pairs, all R_eq_omega and R_sign_eq accepts on rule-threshold and rule-clause T's. This is the "uniform invariance on rule-bearing axes" pattern that classifies ruleblind as `ignored-candidate`.

### Σ(track) ∖ Σ(wrongstatic) and Σ(wrongstatic) ∖ Σ(track)
Three pairs total — small but non-empty:
- f_track has `rule_clause/add_strict_clause/R_sign_eq` (decision preserved when adding a strict clause that mostly rejects).
- f_wrongstatic has `case_fact/case_team_plus/R_sign_eq` and `rule_threshold/weaken_team_threshold/R_sign_eq` — different decision-preservation pattern from the inverted last clause.

### Σ(track) ∖ Σ(wrongstochastic)
Σ(wrongstochastic) is a strict subset of the non-rule axes. f_track has 8 additional accepts on rule-clause and case-fact axes that f_wrongstochastic loses to bimodal noise. That's the degradation signal (criterion c4).

---

## Active-boundary subset (f_wrongstochastic only, plan §11.4)

n_active_boundary ≈ 195/300 per draw (cases with risk in [25, 55]). Active-boundary signatures recorded in `signatures_active_boundary.csv`. The bimodal-noise effect on f_wrongstochastic is preserved on the subset; rule-threshold pairs continue to fail acceptance.

---

## Reproducibility

```bash
cd experiments/eos_v2
python3 seal_manifest.py          # writes SEAL.txt; must match committed sha256
python3 run.py                    # ~30s wall-clock
```

Stdlib only. Deterministic from `CORPUS_SEEDS = (17, 23, 29)` and `NOISE_BASE_SEED = 1009`.

Output artifacts:
- `signatures.csv` — every (pipeline, draw, T, R^Ω) row with k, n_eff, p_hat, cp_lcb, accepted, in_signature
- `axis_summary.csv` — five-way axis classification per (pipeline, draw, axis)
- `stability.csv` — pairwise Jaccard + triple-intersection ratio
- `signatures_active_boundary.csv` — f_wrongstochastic on the active-boundary subset

Every CSV is prefixed with the seal sha256 in column 1.

---

## Bottom line

**EOS separation works.** Σ(f_track) is empirically distinct from Σ(f_ruleblind), Σ(f_constant), Σ(f_wrongstatic), and Σ(f_wrongstochastic) on rule-bearing axes, stably across three independent corpus draws (Jaccard = 1.000), with the methodology preserving the seal-then-adversary commit discipline.

**Two criteria fail for documented configuration reasons** (c3: relation form requires universal effects which sparse rule-threshold transformations can't satisfy; c7: noise/effect-size ratio leaves the load-bearing divergence zone empty). Both are addressable by changes to the *next* sealed run, not to this one.

**Bottom-line binary.** PARTIAL PASS — 6/8 criteria.

A clean PASS requires either: (a) per-T effective-applicability filtering with reduced n_eff_min, (b) a `R_consistent_dir` relation that handles sparse effects, or (c) wider score-noise and finer-grained transformations to populate the load-bearing divergence zone. Recommendation: implement (a) and (b) for v3; defer (c) to LLM-backed validation where native noise will populate the zone naturally.
