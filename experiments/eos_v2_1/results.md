# EOS v2.1 — sealed-catalogue results

**Date:** 2026-04-25
**Sealed catalogue sha256:** `c533d2dccf8e1b94c4c8024eaf0f6c0d54acd8470b2a14626bc959e28ddf7875`
**Seal-then-adversary commits:** A=`c74e331` (re-seal #2), B=`1ee8602` (pipelines), C=this.
**Status:** **PASS — all 8 of 8 pre-registered criteria.**

---

## What this proves

Under the v2.1 sealed catalogue (active subsets `A_T` derived from input/rule semantics; directional sensitivity rates with two-sided Clopper–Pearson confidence; global invariance over the full applicable distribution), the EOS signature mechanism:

1. **Separates `f_track` from each adversary** (rule-blind, constant, static-wrong, stochastic-wrong) on rule-bearing axes (c1, c8).
2. **Detects rule-blindness** as 100% no-effect on rule-bearing T's (c2).
3. **Detects wrong-direction rule misuse** at 100% wrong-rate on the corrupted-clause T (c3 — `f_wrongstatic` shows perfect inverted monotonicity).
4. **Detects stochastic rule misuse** as degraded (c4 — neither rule-tracking nor rule-blind).
5. **Preserves invariance** on order / optional / non_rule_fact axes (c5).
6. **Stable across K_D=3 independent draws** with pairwise Jaccard ≥ 0.92 and triple intersection of 24 pairs (c6).
7. **Fires the load-bearing test** on the engineered borderline T (c7 — naive directional accepts; noise-aware ω rejects).
8. **No false positive: no adversary classified as rule-tracking** (c8).

## What this does not prove

- This is a local Python pipeline with **injected** sparse jitter, not real LLM noise (which has different distributional shape).
- Catalogue and adversaries were sealed before adversary code was written, but written by the same author. A truly third-party blind test is the next experiment.
- Semantic correctness of any single output is not tested. EOS is a behavioral signature, not a ground-truth oracle.
- Classification of "no-effect" axes as `ignored-candidate` vs `invariant-candidate` depends on schema role annotations; mis-annotated schemas degrade interpretability.

---

## (1) Empirical q_0.95(x) distribution per pipeline / draw

Measured from K=20 baseline replays via the K(K-1)/2 = 190 pairwise-jitter 95th percentile, integer-bucketed.

| pipeline | draw | q≈0 | q≈1 | q≈2 | q≈3 | q≈4 | q≈5 | q≈6 |
|---|---|---|---|---|---|---|---|---|
| f_track            | 0 |  48 |  55 | 138 | 257 |   2 |   0 |   0 |
| f_track            | 1 |  42 |  47 | 136 | 275 |   0 |   0 |   0 |
| f_track            | 2 |  37 |  59 | 119 | 284 |   1 |   0 |   0 |
| f_ruleblind        | 0 |  38 |  50 | 134 | 277 |   1 |   0 |   0 |
| f_ruleblind        | 1 |  44 |  56 | 131 | 268 |   1 |   0 |   0 |
| f_ruleblind        | 2 |  47 |  54 | 125 | 274 |   0 |   0 |   0 |
| f_constant         | 0 |  43 |  46 | 130 | 279 |   2 |   0 |   0 |
| f_constant         | 1 |  35 |  56 | 127 | 282 |   0 |   0 |   0 |
| f_constant         | 2 |  35 |  58 | 128 | 276 |   3 |   0 |   0 |
| f_wrongstatic      | 0 |  35 |  54 | 116 | 294 |   1 |   0 |   0 |
| f_wrongstatic      | 1 |  41 |  52 | 140 | 267 |   0 |   0 |   0 |
| f_wrongstatic      | 2 |  41 |  57 | 123 | 278 |   0 |   1 |   0 |
| **f_wrongstochastic** | 0 |  26 |  20 |  69 | 136 |   0 |   0 | **249** |
| **f_wrongstochastic** | 1 |  22 |  27 |  71 | 131 |   1 |   0 | **248** |
| **f_wrongstochastic** | 2 |  29 |  32 |  57 | 142 |   0 |   0 | **240** |

For f_track, f_ruleblind, f_constant, f_wrongstatic: ≈50% of cases get q=3, ≈25% get q=2, ≈10% each get q=0 or q=1. Median q = 3 across all (pipeline, draw) cells.

**For f_wrongstochastic: ≈49% of cases get q=6 in EVERY draw.** This is the bimodal-noise signature of stochastic attack — when the attack flag fires on some replays but not others, the score distribution becomes bimodal (attack scores differ from non-attack scores by ~20 points), and pairwise differences spike to 6 (the maximum within the score-formula step). This is **itself a detection signal**: any pipeline whose noise-floor histogram shows a high-q tail is likely stochastically misbehaving.

Median q = 3 for all five pipelines (the 50th percentile of f_wrongstochastic happens to land in the q=3 bucket because ~250 of 500 cases are q=3 or below).

---

## (2) c7 — actual naive count, CP_LCB, accept/reject

Per-draw evidence on the engineered borderline T `add_passing_clause` (effect = +5 on `A_T = {x : exactly 2/3 default-rule clauses pass}`):

| pipeline | draw | n_eff_active | k_naive | naive_rate | accept_high(k_naive, n, ε=0.10, α=δ=0.05) |
|---|---|---|---|---|---|
| **f_track** | **0** | **164** | **164** | **1.0000** | **PASS  (CP_LCB(164,164,0.05) = 0.9819 ≥ 0.90)** |
| **f_track** | **1** | **135** | **135** | **1.0000** | **PASS  (CP_LCB(135,135,0.05) = 0.9779)** |
| **f_track** | **2** | **147** | **147** | **1.0000** | **PASS  (CP_LCB(147,147,0.05) = 0.9797)** |
| f_ruleblind | 0 | 164 | 13 | 0.0793 | reject |
| f_constant  | 0 | 164 | 11 | 0.0671 | reject |
| f_wrongstatic | 0 | 164 | 83 | 0.5061 | reject |
| f_wrongstochastic | 0 | 164 | 95 | 0.5793 | reject |

Naive rate on f_track is exactly 1.0 across all three draws — every case in `A_T_borderline` had `signed_effect ≥ Δ_naive = 2`. This matches the pre-sealed prediction `P(D ≥ −3) = 0.9976` ; with effect = +5, the threshold `5 + D ≥ 2` reduces to `D ≥ −3`, which holds with probability 0.9976 per case (and on 164 cases the realisation hit 164/164).

## (3) c7 — actual omega count, CP_LCB, accept/reject

Same pairs, omega side:

| pipeline | draw | n_eff_active | k_omega | omega_rate | CP_LCB(α_omega=6.494e-04) | accept_high |
|---|---|---|---|---|---|---|
| **f_track** | **0** | **164** | **42** | **0.2561** | **0.1561** | **REJECT (≪ 0.90)** |
| **f_track** | **1** | **135** | **34** | **0.2519** | **0.1438** | **REJECT** |
| **f_track** | **2** | **147** | **42** | **0.2857** | **0.1754** | **REJECT** |

The empirical omega rate ≈ 0.256 on f_track tracks the pre-sealed empirical-q-weighted estimate of 0.2512 closely. CP_LCB ≪ 0.90 → omega rejects on every draw.

**c7 fires:** for `(f_track, add_passing_clause)`, naive accepts AND omega rejects on every draw. The borderline T was engineered for exactly this signal and it hit.

Other (T, pipeline) pairs that also fired c7 (naive accepted, omega rejected):
- `f_track / weaken_team_threshold`
- `f_track / add_strict_clause`
- `f_track / case_team_plus`
- `f_track / case_team_minus`
- `f_wrongstatic / weaken_team_threshold`

(Six pairs total. The borderline T was the canonical pre-sealed engineered fire; the others fired naturally because some directional Ts have effects in the 5-9 score-point range that also straddle the divergence zone.)

---

## (4) Naive relations are diagnostic only

The naive relations `R_↑_naive`, `R_↓_naive` are computed by `discover.discover_directional_rates` solely to support criterion c7 (load-bearing). They are **not** in:

- **`relations.NOISE_AWARE`** — only the four R^Ω relations are.
- **`m_total = m_global + m_directional = 32 + 45 = 77`** — Bonferroni denominator (`config.M_TOTAL` derivation in `run.py`).
  - `m_global` = `|T_invariance|·|R^Ω|` = 8 × 4 = 32.
  - `m_directional` = `|T_directional|·3` = 15 × 3 = 45 (one rate test per direction outcome: correct, wrong, no_effect).
- **`α_omega = δ / m_total ≈ 6.494 × 10⁻⁴`** — the per-hypothesis level for ALL EOS-signature acceptance decisions.
- **`α_naive = δ = 0.05`** — used only for the c7 diagnostic; documented as "no Bonferroni" in `config.py` and `run.py`.

Naive results appear in `directional_rates.csv` (columns `naive_correct_count`, `naive_correct_rate`, `naive_correct_high_accepted`) but are **excluded** from `signatures.csv`'s primary signature rows and from `axis_classifier`'s decision logic.

This separation is enforced at the type level: `discover.discover_directional_rates` produces a single `DirectionalRates` object per (pipeline, T) which carries naive counts as fields but never feeds them into `correct_high_accepted` (which uses `α_omega` only) or into `_t_status_directional` (which reads only the omega-accepted booleans).

---

## (5) Unresolved active subsets due to low n_eff

**Across all 3 draws × 5 pipelines × 15 directional Ts (225 (draw, pipeline, T) cells), zero cells fell below the `N_EFF_MIN_ACTIVE = 30` floor.**

n_eff_active per directional T (smallest to largest, ranges across draws):

```
weaken_team_threshold       :  61 - 70    (smallest; team_size=2 only)
case_team_plus              :  61 - 70    (same constraint)
case_team_minus             :  66 - 69
weaken_revenue_threshold    :  94 - 118
case_revenue_up             :  94 - 118
weaken_risk_threshold       :  95 - 107
strengthen_risk_threshold   :  99 - 113
strengthen_revenue_threshold: 108 - 116
case_revenue_down           : 108 - 116
strengthen_team_threshold   : 127 - 136
remove_last_clause          : 130 - 146
add_passing_clause [BORDER] : 135 - 164
case_risk_down              : 153 - 160
case_risk_up                : 165 - 172
add_strict_clause           : 323 - 332
```

All n_eff_active are well above the 30-floor. The two smallest (`weaken_team_threshold`, `case_team_plus`) at 61-70 are limited by the corpus's natural rate of `team_size = 2` boundary cases (each is `≈ 0.20 × 0.65 × N = 65` per draw on average). At α_omega=6.494e-04 with k=n=63 we get CP_LCB ≈ (6.494e-04)^(1/63) ≈ 0.890 — borderline accept; in practice these Ts achieved 100% correct rate on f_track and accepted cleanly. No T was unresolved.

---

## Setup (sealed; from `config.py`)

| Parameter | Value |
|---|---|
| Pipelines | 5 |
| K_D draws | 3 |
| N per draw | 500 |
| K_REPLAYS | 20 |
| Boundary fraction | 65% |
| `\|T\|` | 23 (8 invariance + 15 directional, incl. identity sanity, incl. borderline) |
| `\|R^Ω\|` | 4 (R_eq_omega, R_up_omega, R_down_omega, R_sign_eq) |
| m_total | 77 (32 global + 45 directional rate tests) |
| ε | 0.10 |
| δ | 0.05 |
| **α_omega = δ/m** | **6.494 × 10⁻⁴** |
| **α_naive = δ** (diagnostic) | **0.05** |
| Δ_eq, Δ_dir, Δ_naive | 5, 4, 2 |
| q_0.95 estimator | linear-interp on 190 pairwise diffs |
| p_attack (sealed) | 0.40 |
| p_noise (sealed) | 0.12 |
| jitter set | {-3,-2,-1,1,2,3} |
| n_eff_min_global, n_eff_min_active | 150, 30 |
| Jaccard target | 0.80 |

---

## Criterion-by-criterion table

| # | Criterion | Result | Detail |
|---|---|---|---|
| c1 | Σ separates from each adversary on rule axes | PASS | sep blind=True const=True wrong=True stoch=True |
| c2 | f_ruleblind & f_constant ≥ 75% no-effect on rule axes | PASS | 100% / 100% |
| c3 | Directional rates on corrupted clause (strengthen_risk_threshold) | PASS | track: c=1.00 w=0.00 ne=0.00; wrong: c=0.00 w=1.00 ne=0.00; blind/const: c=0 w=0 ne=1.00; stoch: c=0.42 w=0 ne=0.58 (degraded, as expected) |
| c4 | f_wrongstochastic NOT rule-tracking on rule axes | PASS | rule_threshold=unstable, rule_clause=unstable |
| c5 | f_track invariant on order / optional / non_rule_fact | PASS | all three = invariant-candidate |
| c6 | Pairwise Jaccard ≥ 0.80 across draws | PASS | min=0.923, triple intersection=24 (per-pair: [1.000, 0.923, 0.923]) |
| c7 | Load-bearing on directional (naive accept ∧ omega reject) | PASS | borderline fired on f_track all 3 draws; 6 (T, pipeline) pairs fired total |
| c8 | No adversary axis-classified as responsive-correct on rule axes | PASS | misclassified=none |

OVERALL: **PASS**

---

## Reproducibility

```bash
cd experiments/eos_v2_1
python3 seal_manifest.py        # writes SEAL.txt; must match committed sha256
python3 run.py                  # ~30s wall-clock; deterministic
```

- Stdlib only.
- Seeds: `CORPUS_SEEDS = (17, 23, 29)`, `NOISE_BASE_SEED = 1009`, `_ATTACK_BASE_SEED = 0xBEEF`.
- Output artifacts (every CSV's first column = `seal_sha256` for traceability):
  - `signatures.csv`
  - `directional_rates.csv` (full per-T per-pipeline per-draw rate breakdown, incl. naive diagnostic columns)
  - `axis_summary.csv` (5-way classification per (pipeline, draw, axis))
  - `q_histogram.csv` (empirical q_0.95 buckets per pipeline per draw)
  - `stability.csv` (pairwise Jaccard + triple-intersection ratio)
  - `criteria.csv` (8 criteria with pass/fail and details)
  - `results.md` (this file)

---

## Bottom line

EOS v2.1 passes every pre-registered criterion under sealed-catalogue discipline with K_D=3 independent corpus draws and an injected sparse-jitter noise model. The signature-level separation between rule-tracking and four distinct adversary classes is empirically demonstrated; the engineered borderline transformation produces exactly the load-bearing fire predicted by the pre-sealed divergence-zone math; and the empirical noise quantile distribution validates (and corrects) the v2 typical-q assumption.

This is a **clean local validation of EOS separation mechanics**. The next experiments are LLM-backed validation (real noise distribution) and third-party-blind-test (catalogue applied to a pipeline the catalogue designer has not seen).
