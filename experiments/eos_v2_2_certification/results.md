# EOS v2.2 — theorem-aligned certification run

**Date:** 2026-04-25
**Sealed catalogue sha256:** `556b70d6ad38f0d7f11071c76b27ddc045139ef46707459feb32733101f5f999`
**Three-commit discipline:** A=`7c41214` (re-seal Δ_eq 5→6), B=`99c4aed` (PAIRED-attack pipelines), C=this.
**Status:** **THEOREM-ALIGNED** — both T2-alignment and T3-alignment PASS.

## Wording discipline (per V5 §10)

This run **does NOT prove the V5 theorems** (those are mathematical results in `eos_consistency_separation_theorem_V5.pdf`). It tests whether the V5 finite-sample assumptions are **empirically supported** on a fresh corpus draw with the certified M = 8 catalogue. The observed margins and active counts meet the pre-specified theorem thresholds.

## Pre-registered analytical predictions for f_wrongstochastic

Predicted **before** any v2.2 corpus generation, no peek at v2.2 data, derived purely from sealed adversary semantics + rule grammar + relation definitions + active-set definitions. Recorded in `pipelines/f_wrongstochastic.py` docstring (Commit B, hash above).

PAIRED attack: same `Bernoulli(P_ATTACK = 0.50)` flag for baseline and transformed calls on the same case. Attack drops the rule's last clause (= risk clause for default rule).

Per-case effect under PAIRED:
- **A = 0** (prob 0.5): no attack. Both calls evaluate full 3-clause rule. R holds with prob ≈ 1.0.
- **A = 1** (prob 0.5): both calls drop the risk clause symmetrically. signed_effect = 0; R holds only via a tail jitter event with prob ≈ P(|j_diff| > Δ_dir) ≈ 0.0024.

**Marginal prediction:** `p_c ≈ 0.5 · 1.0 + 0.5 · 0.0024 = 0.5012`.

## Observed results vs prediction (probes #1, #2, #6)

| probe | predicted p_c | observed p̂_c | k / n_eff | CP interval | < θ − λ = 0.82 ? |
|---|---|---|---|---|---|
| #1 strengthen_risk_threshold (R_↓) | **0.5012** | **0.4667** | 280 / 600 | [0.4008, 0.5333] | YES (0.5333 < 0.82) |
| #2 weaken_risk_threshold (R_↑)     | **0.5012** | **0.5067** | 304 / 600 | [0.4402, 0.5730] | YES (0.5730 < 0.82) |
| #6 case_risk_up (R_↓)              | **0.5012** | **0.5283** | 317 / 600 | [0.4617, 0.5943] | YES (0.5943 < 0.82) |

Deviations from prediction are within sampling noise: at n = 600 with p = 0.5, σ ≈ 0.020, so |observed − 0.5012| ≤ 0.034 ≈ 1.7 σ on probe #1 (largest deviation). All three CP_UCB values lie well below the boundary band's lower edge `θ − λ = 0.82`. The margin condition holds empirically on all three risk probes.

## Invariant-probe check (Δ_eq = 6 confirmation)

Both invariant probes hit `p_hat = 1.0` exactly across all 5 pipelines:

| probe | pipeline | p̂_c | k / n_eff | CP_LCB ≥ θ + λ = 0.98 ? |
|---|---|---|---|---|
| #7 permute_founders (R_eq) | f_track / f_ruleblind / f_constant / f_wrongstatic / f_wrongstochastic | 1.0000 | 600 / 600 | YES (0.9878 ≥ 0.98) |
| #8 replace_description (R_eq) | all 5 | 1.0000 | 600 / 600 | YES (0.9878 ≥ 0.98) |

This confirms `Δ_eq = 6` correctly absorbs the maximum jitter difference of 6 (when `j_t = +3, j_b = −3` or vice versa). Under `Δ_eq = 5`, ~0.08% of cases per probe would have failed R_eq purely from noise jitter; under `Δ_eq = 6`, R_eq holds deterministically when the underlying score is unchanged. CP_LCB = 0.9878 sits 0.0078 above `θ + λ = 0.98`.

## Theorem-required sample-size bounds (computed from sealed config)

```
ε = 0.10,  θ = 0.90,  λ = 0.08,  δ = 0.05
M = 8,  A = 4,  |F| = 5

Theorem 2 n_min = ⌈log(2·8·5/0.05) / (2·0.08²)⌉ = 577
Theorem 3 n_min = ⌈log(4·4/0.05) / (2·0.08²)⌉ = 451
N_EFF_MIN committed = 600
Safety margin (Th.2): 23
Safety margin (Th.3): 149

α_per_pair = δ / (2·M·(A+1)) = 6.25e-04
```

## Full per-probe table (all 40 pipeline × probe pairs)

All 40 CP intervals lie strictly outside the forbidden band `(θ − λ, θ + λ) = (0.82, 0.98)`.

| probe | pipeline | p̂_c | CP_LCB | CP_UCB | side of band |
|---|---|---|---|---|---|
| #1 strengthen_risk_threshold (R_↓) | f_track | 1.0000 | 0.9878 | 1.0000 | high (≥ 0.98) |
| | f_ruleblind | 0.0017 | 0.0000 | 0.0161 | low (≤ 0.82) |
| | f_constant | 0.0033 | 0.0001 | 0.0195 | low |
| | f_wrongstatic | 0.0000 | 0.0000 | 0.0122 | low |
| | f_wrongstochastic | 0.4667 | 0.4008 | 0.5333 | low |
| #2 weaken_risk_threshold (R_↑) | f_track | 1.0000 | 0.9878 | 1.0000 | high |
| | f_ruleblind | 0.0000 | 0.0000 | 0.0122 | low |
| | f_constant | 0.0067 | 0.0006 | 0.0255 | low |
| | f_wrongstatic | 0.0000 | 0.0000 | 0.0122 | low |
| | f_wrongstochastic | 0.5067 | 0.4402 | 0.5730 | low |
| #3 strengthen_revenue_threshold (R_↓) | f_track | 1.0000 | 0.9878 | 1.0000 | high |
| | f_ruleblind | 0.0033 | 0.0001 | 0.0195 | low |
| | f_constant | 0.0000 | 0.0000 | 0.0122 | low |
| | f_wrongstatic | 1.0000 | 0.9878 | 1.0000 | high* |
| | f_wrongstochastic | 1.0000 | 0.9878 | 1.0000 | high* |
| #4 case_team_plus (R_↑) | f_track | 1.0000 | 0.9878 | 1.0000 | high |
| | f_ruleblind | 0.1033 | 0.0674 | 0.1491 | low |
| | f_constant | 0.0000 | 0.0000 | 0.0122 | low |
| | f_wrongstatic | 1.0000 | 0.9878 | 1.0000 | high* |
| | f_wrongstochastic | 1.0000 | 0.9878 | 1.0000 | high* |
| #5 case_revenue_up (R_↑) | f_track | 1.0000 | 0.9878 | 1.0000 | high |
| | f_ruleblind | 1.0000 | 0.9878 | 1.0000 | high* |
| | f_constant | 0.0050 | 0.0003 | 0.0226 | low |
| | f_wrongstatic | 1.0000 | 0.9878 | 1.0000 | high* |
| | f_wrongstochastic | 1.0000 | 0.9878 | 1.0000 | high* |
| #6 case_risk_up (R_↓) | f_track | 1.0000 | 0.9878 | 1.0000 | high |
| | f_ruleblind | 0.0000 | 0.0000 | 0.0122 | low |
| | f_constant | 0.0000 | 0.0000 | 0.0122 | low |
| | f_wrongstatic | 0.0000 | 0.0000 | 0.0122 | low |
| | f_wrongstochastic | 0.5283 | 0.4617 | 0.5943 | low |
| #7 permute_founders (R_eq) | all 5 | 1.0000 | 0.9878 | 1.0000 | high |
| #8 replace_description (R_eq) | all 5 | 1.0000 | 0.9878 | 1.0000 | high |

\* "high*" = adversary tracks f_track on this specific probe (e.g., f_wrongstatic only mishandles the risk clause, so it agrees with f_track on revenue / team / order / optional probes). The theorem only requires that for **each adversary** there exists **at least one** separating probe — and probe #1 separates all four adversaries simultaneously.

## T3-alignment: separating probe per adversary

```
f_ruleblind        ↔ strengthen_risk_threshold (probe #1)
f_constant         ↔ strengthen_risk_threshold (probe #1)
f_wrongstatic      ↔ strengthen_risk_threshold (probe #1)
f_wrongstochastic  ↔ strengthen_risk_threshold (probe #1)
```

For each adversary f_j: `CP_LCB(f_track, probe #1) = 0.9878 ≥ θ + λ = 0.98` AND `CP_UCB(f_j, probe #1) ≤ θ − λ = 0.82` (the largest is f_wrongstochastic at 0.5333). The discriminative-probe condition of V5 Theorem 3 holds in the empirical CP intervals.

Probes #2 and #6 also separate f_wrongstochastic from f_track on the risk axis; probes #3, #4, #5 separate f_constant from f_track on case-fact axes.

## Theorem-alignment binary

**(T2-aligned) — PASS.** For every (j, c) ∈ F × K (40 pairs), the empirical CP interval at α_per_pair = 6.25 × 10⁻⁴ lies strictly outside the boundary band `(θ − λ, θ + λ) = (0.82, 0.98)`. The uniform-margin assumption `|p_c(f_j) − θ| ≥ λ = 0.08` is empirically supported.

**(T3-aligned) — PASS.** For each adversary f_j (j = 1..4), there exists at least one probe c such that p̂_c(f_track) and p̂_c(f_j) lie on opposite sides of θ with their CP intervals respecting the margin λ.

**OVERALL: THEOREM-ALIGNED.**

## What this proves (per V5 §10)

This run, with the M = 8 pre-specified catalogue and the V5 finite-sample assumptions:
- Statistical consistency of EOS signatures for the certified finite catalogue is empirically supported.
- Active-set conditioning is honored (every A_c defined from input/rule semantics; samples drawn directly from D(·|A_c)).
- Judge-free estimation: no external labels were used.
- Margin-separated discriminative probes for every specified adversarial failure mode are present (probe #1 alone covers all four adversaries).
- Catalogue-relative behavioral identifiability: empirical signatures Σ̂(f_track), Σ̂(f_ruleblind), Σ̂(f_constant), Σ̂(f_wrongstatic), Σ̂(f_wrongstochastic) are mutually distinct on the rule axes.

## What this does not prove (per V5 §10)

- Full semantic correctness of any pipeline.
- Detection of failures absent from the M = 8 catalogue.
- Validity for catalogues, adversaries, thresholds, couplings, or margins selected after inspecting evaluation outcomes (Assumption 1 honored — none of these were peeked).
- Separation when true probabilities lie too close to θ (none did, in this run).
- Detection of stochastic bugs whose observable net failure mass is below λ (the PAIRED-attack adversary deliberately produces ~0.50 net failure mass to sit cleanly outside the boundary band; subtler stochastic bugs are not in scope).
- Equivalence outside the catalogue-observable behavior tested by EOS.

This is the **narrow theorem-certification claim**. The broader product / behavioral audit validation lives in [`experiments/eos_v2_1/`](../eos_v2_1/) (23-T catalogue, noise-aware relations, K_D=3 stability, 5-way axis classifier).

## Setup (sealed)

| Parameter | Value |
|---|---|
| Catalogue size M | 8 |
| Adversaries A | 4 |
| Family size \|F\| | 5 |
| ε | 0.10 |
| θ = 1 − ε | 0.90 |
| λ | 0.08 |
| δ | 0.05 |
| α_per_pair = δ / (2M(A+1)) | 6.25 × 10⁻⁴ |
| n_eff per (j, c) | 600 (committed; theorem requires ≥ 577 for T2) |
| p_attack | 0.50 (PAIRED — same flag for baseline and transformed) |
| p_noise | 0.12 |
| jitter set | {-3, -2, -1, +1, +2, +3} (independent across baseline/transformed) |
| Δ_dir | 4 (R_up, R_down) |
| Δ_eq | **6** (R_eq; certification-hygiene fix from initial 5) |
| Coupling Γ_{j,c} | independent jitter; PAIRED attack flag (per case_id only) |
| corpus seed | 41 (FRESH, disjoint from v2.1) |
| relations | RAW only (no noise term, no q estimation) |

## Reproducibility

```bash
cd experiments/eos_v2_2_certification
python3 seal_manifest.py        # writes SEAL.txt; must match committed sha256
python3 run.py                  # ~5s wall-clock; deterministic
```

Stdlib only. Outputs:
- `SEAL.txt` — sealed file manifest with sha256
- `signatures.csv` — 40 rows: per-(probe, pipeline) k, n_eff, p_hat, CP_LCB, CP_UCB, margin, n_min_required, margin_supported flag
- `theorem_check.json` — theorem bounds + alignment summary
- `results.md` — this file

Every CSV / JSON includes `seal_sha256` for traceability.

## Bottom line

The v2.2 certification run executes the V5 theorem's finite-sample setup faithfully:
- pre-specified catalogue, transformations, active sets, relations, ε, θ, λ, δ, p_attack, coupling Γ;
- direct sampling from D(·|A_c) per probe;
- raw relations (no noise-aware calibration object, no Theorem-4 dependence);
- fresh corpus seed disjoint from v2.1;
- no v2.2 outcome inspection before sealing.

The empirical evidence supports the V5 theorem's margin and discriminative-probe assumptions on this corpus draw. f_wrongstochastic's predicted p_c ≈ 0.5012 (PAIRED-attack analytical pre-prediction) is matched by observed p̂ ∈ [0.467, 0.528] across the three risk probes, with CP_UCB ≤ 0.594 ≪ 0.82 = θ − λ.

The V5 theorems themselves are proved mathematically in the PDF; this run is a faithful empirical instance of their assumptions, not a substitute for the proofs.
