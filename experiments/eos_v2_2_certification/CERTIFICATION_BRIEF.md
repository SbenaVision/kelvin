# EOS v2.2 — Certification Run Brief

*Companion to `eos_consistency_separation_theorem_V5.pdf` (Apr 25, 2026).
Date: 2026-04-25.   `seal_sha256 = 556b70d6...28ddf7875`.*

## What we tested

A faithful empirical instance of the V5 theorem's setup on a sealed
finite catalogue of structured-decision pipelines, with **PAIRED**
stochastic-coupling adversaries and direct sampling from each
catalogue item's input-semantic active set.

## Setup (PDF §1)

- **Family** F = {f_track, f_ruleblind, f_constant, f_wrongstatic, f_wrongstochastic}, |F| = 5.
- **Catalogue** K = {c₁,…,c₈}, M = 8. Each cᵢ = (Tᵢ, ρᵢ, Aᵢ) is pre-specified.
- **Coupling Γ_{j,c}**: independent jitter (replay 0 vs replay 1); attack
  flag PAIRED across baseline and transformed for f_wrongstochastic
  (seed depends on case_id only, not replay_idx).
- **Pre-specification (Assumption 1)** enforced by sealed git commit
  before any v2.2 corpus generation, pipeline call, or peek.

## Pre-committed parameters

| ε | θ | λ | δ | M | A | n_eff | α_per_pair |
|---|---|---|---|---|---|---|---|
| 0.10 | 0.90 | 0.08 | 0.05 | 8 | 4 | 600 | δ/(2M(A+1)) = 6.25×10⁻⁴ |

`Δ_dir = 4`, `Δ_eq = 6` (= max\|jitter_diff\|, ensures invariance probes
hit p_c = 1 deterministically). `p_attack = 0.50`. Corpus seed 41
(disjoint from v2.1).

## Catalogue (M = 8 probes)

| # | T | ρ | A_c |
|---|---|---|---|
| 1 | strengthen_risk_threshold | R_↓ | 30 < risk ≤ 40 |
| 2 | weaken_risk_threshold | R_↑ | 40 < risk ≤ 50 |
| 3 | strengthen_revenue_threshold | R_↓ | 10k ≤ rev < 20k |
| 4 | case_team_plus | R_↑ | team = 2 |
| 5 | case_revenue_up | R_↑ | 5k ≤ rev < 10k |
| 6 | case_risk_up | R_↓ | 21 ≤ risk ≤ 40 |
| 7 | permute_founders | R_eq | ≥2 founders |
| 8 | replace_description | R_eq | X |

## Theorem-required sample sizes (PDF §11)

```
Theorem 2 (uniform recovery):  n_min = ⌈log(2M(A+1)/δ) / 2λ²⌉ = 577
Theorem 3 (separation alone):  n_min = ⌈log(4A/δ)     / 2λ²⌉ = 451
Committed: n_eff = 600     (safety: T2 +23, T3 +149)
```

## Result — T2 alignment (PDF §3, Theorem 2)

For every (j, c) ∈ F × K (40 pairs), the empirical Clopper–Pearson
interval at α_per_pair = 6.25×10⁻⁴ lies **strictly outside the
boundary band (θ−λ, θ+λ) = (0.82, 0.98)**. The uniform-margin
assumption `|p_c(f_j) − θ| ≥ λ = 0.08` is empirically supported on
all 40 (pipeline, probe) cells.

## Result — T3 alignment (PDF §5, Theorem 3)

For each adversary fⱼ, the discriminative-probe condition holds
empirically on probe #1 (`strengthen_risk_threshold, R_↓`):

| pipeline | CP interval on probe #1 | side of band |
|---|---|---|
| f_track | [0.9878, 1.0000] | high (≥ 0.98) |
| f_ruleblind | [0.0000, 0.0161] | low (≤ 0.82) |
| f_constant | [0.0001, 0.0195] | low |
| f_wrongstatic | [0.0000, 0.0122] | low |
| f_wrongstochastic | [0.4008, 0.5333] | low |

Σ̂(f_track) ≠ Σ̂(fⱼ) for every adversary, with margin ≥ λ in both directions.

## Pre-registered prediction vs observed (PDF §6, Lemma 1)

For PAIRED-attack f_wrongstochastic on the three risk probes, derived
analytically from sealed adversary semantics + jitter model **before
the corpus was generated**:

```
p_c (PAIRED) = 0.5·[R holds when no attack] + 0.5·[R holds via jitter tail]
            = 0.5·1.0000 + 0.5·0.0024 = 0.5012
```

| probe | predicted | observed p̂ | CP_UCB | < θ−λ |
|---|---|---|---|---|
| #1 | 0.5012 | 0.4667 | 0.5333 | ✓ |
| #2 | 0.5012 | 0.5067 | 0.5730 | ✓ |
| #6 | 0.5012 | 0.5283 | 0.5943 | ✓ |

All three observed values fall within sampling noise of the
analytical prediction (≤ 1.7σ at n=600).

## What this run proves (PDF §10)

1. The V5 theorems' **finite-sample assumptions** are empirically
   supported on a fresh corpus draw with a pre-specified M=8 catalogue.
2. **Active-set conditioning**, **stochastic coupling specification**,
   and **margin-separated discriminative probes** all hold in measurable form.
3. **Catalogue-relative behavioral identifiability**: empirical
   signatures Σ̂(f_track), Σ̂(f_ruleblind), Σ̂(f_constant),
   Σ̂(f_wrongstatic), Σ̂(f_wrongstochastic) are mutually distinct
   on the rule axes with confidence ≥ 1 − δ at the Bonferroni-corrected α.

## What this run does NOT prove (PDF §10, deliberate scope)

- It does **not** prove the V5 theorems. Those are mathematical results in the PDF; this is one empirical instance of their assumptions.
- It does **not** prove semantic correctness of any pipeline.
- It does **not** detect failures absent from the M=8 catalogue.
- It does **not** validate noise-aware (Theorem-4) calibration; raw relations only.
- It does **not** generalize to LLM-backed pipelines without a separate sealed run under the same discipline.

## Sealing discipline (PDF Assumption 1)

Three-commit sequence enforced via git:

```
A   7c41214   sealed catalogue + parameters + criteria (no adversary code)
B   99c4aed   five adversary pipelines (PAIRED attack)
C   6b5d7bb   run.py + signatures.csv + theorem_check.json + results.md
```

Catalogue, transformations, active sets, relations, ε, θ, λ, δ,
p_attack, coupling, corpus seed, and success criteria all sealed in
Commit A and verified by `seal_manifest.py` at every run start.

## Reproducibility

`stdlib only · ~5s wall-clock · deterministic from CORPUS_SEED=41`

```bash
cd experiments/eos_v2_2_certification
python3 seal_manifest.py    # verifies SEAL.txt
python3 run.py              # writes signatures.csv, theorem_check.json
```

---

**Conclusion.** The V5 theorem describes a finite-sample
catalogue-relative consistency-and-separation result. v2.2 is a
faithful empirical instance: the theorem's assumptions are checked
on a fresh corpus draw with a pre-specified catalogue and the
predicted population behavior is matched within sampling noise. The
narrow claim — that EOS works as a finite, judge-free, behavioral
test for a defined adversary class on this specific structured-decision
setting — is empirically supported. Broader claims (universal
correctness, semantic correctness, LLM-backed validity) remain explicitly
out of scope, per V5 §10.
