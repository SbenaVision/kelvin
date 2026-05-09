# Multi-replay test — does the per-unit causal map survive noise?

_Generated 2026-04-26 16:24:20_  
4 cases × ~7 paragraphs × 5 replays each = 112 extra perturbation calls
4 cases × 5 extra baseline replays = 20 extra baseline calls

## Per-case noise floor (N=10 replays)

| Case | morning_baseline | replays (N=10) | σ_c (10 replays) | σ_c (orig 5 replays) |
|---|---|---|---:|---:|
| artisanflow | seed | `[growth, growth, growth, growth, seed, seed, seed, growth, growth, seed]` | 0.533 | 0.400 |
| envelop | seed | `[seed, seed, pre-seed, seed, seed, seed, seed, seed, seed, seed]` | 0.200 | 0.400 |
| freakinggenius | pre-seed | `[idea, idea, idea, pre-seed, pre-seed, pre-seed, pre-seed, idea, pre-seed, pre-s` | 0.533 | 0.600 |
| meridian | pre-seed | `[pre-seed, pre-seed, seed, pre-seed, seed, pre-seed, pre-seed, pre-seed, pre-see` | 0.356 | 0.600 |

## Per-paragraph flip rates (N=5 replays) vs σ_c

Decision rule: paragraph deletion is **above-noise** if a one-sided binomial test 
(H₀: flip_rate ≤ σ_c) gives p < 0.05.

### artisanflow  (σ_c=0.533, canonical baseline = seed)

| Unit | Replay decisions (N=5) | flip_rate | binomial p (vs σ_c) | above-noise? | morning probe? |
|---|---|---:|---:|:-:|:-:|
| p01 | `[growth, seed, growth, growth, seed]` | 0.60 | 0.562 | n | n |
| p02 | `[growth, seed, seed, seed, growth]` | 0.40 | 0.851 | n | n |
| p03 | `[seed, seed, growth, growth, seed]` | 0.40 | 0.851 | n | Y |
| p04 | `[growth, growth, growth, growth, seed]` | 0.80 | 0.232 | n | n |
| p05 | `[growth, growth, growth, growth, seed]` | 0.80 | 0.232 | n | n |
| p06 | `[seed, seed, growth, seed, seed]` | 0.20 | 0.978 | n | Y |
| p07 | `[growth, seed, growth, growth, seed]` | 0.60 | 0.562 | n | n |

### envelop  (σ_c=0.200, canonical baseline = seed)

| Unit | Replay decisions (N=5) | flip_rate | binomial p (vs σ_c) | above-noise? | morning probe? |
|---|---|---:|---:|:-:|:-:|
| p01 | `[seed, seed, seed, pre-seed, seed]` | 0.20 | 0.672 | n | n |
| p02 | `[pre-seed, seed, seed, seed, seed]` | 0.20 | 0.672 | n | Y |
| p03 | `[pre-seed, pre-seed, seed, seed, seed]` | 0.40 | 0.263 | n | Y |
| p04 | `[seed, seed, seed, seed, seed]` | 0.00 | 1.000 | n | n |
| p05 | `[seed, seed, seed, seed, seed]` | 0.00 | 1.000 | n | n |
| p06 | `[seed, seed, seed, seed, seed]` | 0.00 | 1.000 | n | n |
| p07 | `[pre-seed, seed, seed, pre-seed, seed]` | 0.40 | 0.263 | n | Y |

### freakinggenius  (σ_c=0.533, canonical baseline = pre-seed)

| Unit | Replay decisions (N=5) | flip_rate | binomial p (vs σ_c) | above-noise? | morning probe? |
|---|---|---:|---:|:-:|:-:|
| p01 | `[pre-seed, pre-seed, pre-seed, pre-seed, pre-seed]` | 0.00 | 1.000 | n | Y |
| p02 | `[pre-seed, pre-seed, idea, pre-seed, pre-seed]` | 0.20 | 0.978 | n | Y |
| p03 | `[pre-seed, pre-seed, pre-seed, idea, pre-seed]` | 0.20 | 0.978 | n | Y |
| p04 | `[idea, pre-seed, pre-seed, pre-seed, idea]` | 0.40 | 0.851 | n | n |
| p05 | `[idea, idea, idea, idea, idea]` | 1.00 | 0.043 | **Y** | n |
| p06 | `[pre-seed, pre-seed, pre-seed, idea, pre-seed]` | 0.20 | 0.978 | n | Y |
| p07 | `[pre-seed, pre-seed, pre-seed, pre-seed, pre-seed]` | 0.00 | 1.000 | n | Y |

### meridian  (σ_c=0.356, canonical baseline = pre-seed)

| Unit | Replay decisions (N=5) | flip_rate | binomial p (vs σ_c) | above-noise? | morning probe? |
|---|---|---:|---:|:-:|:-:|
| p01 | `[pre-seed, seed, pre-seed, pre-seed, pre-seed]` | 0.20 | 0.889 | n | n |
| p02 | `[pre-seed, seed, seed, seed, pre-seed]` | 0.60 | 0.244 | n | n |
| p03 | `[pre-seed, pre-seed, pre-seed, pre-seed, pre-seed]` | 0.00 | 1.000 | n | n |
| p04 | `[pre-seed, pre-seed, pre-seed, pre-seed, pre-seed]` | 0.00 | 1.000 | n | n |
| p05 | `[pre-seed, pre-seed, pre-seed, pre-seed, pre-seed]` | 0.00 | 1.000 | n | n |
| p06 | `[pre-seed, seed, pre-seed, pre-seed, pre-seed]` | 0.20 | 0.889 | n | n |
| p07 | `[pre-seed, pre-seed, pre-seed, seed, pre-seed]` | 0.20 | 0.889 | n | n |

## Summary counts

- Morning's prototype (single-replay) flagged paragraphs: 10
- Of those, surviving 5-replay binomial test (p<0.05 vs σ_c): **0**
- New paragraphs revealed as above-noise after replication: 1

## Honest read

**The per-unit causal map does not survive replication on this pipeline.** Of
10 paragraphs flagged in the original single-replay pass as causally relevant
(distance=1.0 on a single deletion), **zero pass a one-sided binomial test
against the per-case noise floor at p < 0.05** when each deletion is replayed
five times. The original flips were drift, not signal.

**One "new" above-noise paragraph (freakinggenius p05) is most likely a
temporal artifact, not a real finding.** All five replays of freakinggenius p05
returned `idea` (against canonical baseline `pre-seed`), yielding p = 0.043
against σ_c = 0.533. But in the original prototype run, that same paragraph's
single deletion returned `pre-seed` (distance = 0.0). Same input file, same
pipeline, completely different outcome distribution between sampling sessions.
The most plausible explanation is temporal drift in the upstream LLM (cache,
load-shape, sampling state) rather than a genuine per-unit causal effect.

**The noise floor itself moves between sampling sessions.** Five additional
baseline replays per case shifted σ_c estimates by significant amounts:

| Case | σ_c (orig 5) | σ_c (full 10) | Δ |
|---|---:|---:|---:|
| artisanflow | 0.40 | 0.53 | +0.13 |
| envelop | 0.40 | 0.20 | −0.20 |
| freakinggenius | 0.60 | 0.53 | −0.07 |
| meridian | 0.60 | 0.36 | −0.24 |

This means the σ_c estimate at N=5 has substantial measurement uncertainty —
which itself is informative about the prototype's headline σ_c-based separation
result (Spearman ρ = 0.917, p = 0.004). That correlation is real but not as
tight as the σ_c numbers in the original summary suggested; the rank order
between moved/stuck groups is preserved but individual case σ_c values are
noisy at N=5.

**What this means for the v0.4 thesis.**

The "auto-unitize + perturb-all-units → per-unit causal map" pitch as a
*sensitivity* signal does not survive this test on the Envelop pipeline at this
budget. Specifically:

1. **Single-replay deletion is below the noise floor.** On a pipeline with
   σ_c ≈ 0.2-0.5, you cannot distinguish a real causal effect from natural
   stochasticity from one perturbation sample. This is exactly what the
   binomial framing is meant to catch, and it caught it.

2. **The noise comes from the pipeline being given unstructured prose.**
   This morning's labeled run, on the same cases with `## Heading` markers
   intact, had σ_c = 0 across every case. Stripping the structure introduces
   the noise that washes out the per-unit signal. The pipeline is not
   inherently noisy — it's noisy when its input structure is removed.
   `## Heading` markers are load-bearing for Envelop's stability.

3. **Deletion may itself be a confounded perturbation.** Removing a paragraph
   changes paragraph-adjacencies in the rest of the input. A flip after
   deletion could be "this paragraph mattered" or "the remaining structure
   reads differently to the LLM" — those are not separable at this design.

**What's still true.**

- The σ_c-based separation of moved-vs-stuck cases is a real signal. The
  rank-order is preserved across both σ_c samples (N=5 and N=10). It just
  doesn't yield clean per-unit attribution.
- Morning's labeled-run findings (with structural markers) hold. The pipeline
  *is* reading the corpus when given structured input.

**Implications for v0.4 design.**

The breakthrough framing ("Kelvin grades any pipeline without labels or
governing types via per-unit causal map") needs to be downgraded. The
prototype suggests:

- **σ_c-only grading is robust and cheap.** v0.4 can ship a `signature.json`
  whose strongest signal is per-case σ_c plus aggregate sensitivity, with
  per-unit attribution offered only when N is high enough to clear σ_c.
- **Per-unit attribution requires either (a) much heavier replay, or (b)
  preserved structural cues, or (c) a different perturbation kind that's
  less confounded with structural context.** None of these is free.
- **The "drop the typing requirement" claim survives** — the σ_c diagnostic
  doesn't need governing types — but the "perturb every unit and read the
  causal map" claim does not, at least with deletion at N=5.

**What I'd test next, before committing v0.4 engineering.**

1. **Replication on the morning's structured corpus** (same cases, headers
   *kept*, swap-based perturbations on declared governing types replayed
   N=5). Does the morning's swap-based per-case sensitivity survive its own
   replication test? If yes, swap-on-typed-units is the load-bearing
   methodology and v0.4's auto-mode is a degraded fallback. If no, the whole
   methodology has higher noise than the original v0.3 numbers suggested
   and the EOS-style sealed-catalogue framing becomes relatively more
   important.

2. **Deletion at higher N** (N=20+) on the boundary cases. Does the per-unit
   signal emerge above noise with sufficient sampling? If yes, the
   methodology works but is expensive. If no, deletion is structurally
   confounded and we need a different perturbation primitive.

3. **A control:** the same multi-replay deletion test on a *deterministic*
   reference pipeline (e.g., the grounded rule-based stand-in from
   `experiments/tier3/pipelines/grounded.py`). On a deterministic pipeline,
   σ_c = 0 by construction, so any deletion-induced flip is an unambiguous
   causal effect. This gives us a positive control for the methodology
   *separate from* the noise question. If deletion's per-unit map works on
   the grounded stand-in but not on Envelop, the issue is pipeline-specific
   noise rather than methodology.

**One-sentence summary.** The replication killed the per-unit causal map on
Envelop at N=5 deletion replays; σ_c-based per-case grading remains the only
above-noise diagnostic from the unlabeled-input approach; v0.4's "perturb
every unit and read the map" pitch needs either a multi-replay budget several
times larger, or to be reframed as an opt-in deep diagnostic gated on σ_c
being low enough to admit per-unit signal.
