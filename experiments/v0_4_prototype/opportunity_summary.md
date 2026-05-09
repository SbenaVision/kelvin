# v0.4 prototype on opportunity_score — summary

_Generated 2026-04-26 21:15:03_

## Per-case overview

| Case | Baseline mean | σ | N units | N above-noise |
|---|---:|---:|---:|---:|
| himom | 482.4 | 32.9 | 6 | 0 |
| stagehand | 503.2 | 30.3 | 6 | 0 |
| readyrounds | 516.8 | 35.9 | 7 | 0 |
| narma | 481.5 | 42.8 | 6 | 0 |

## Cross-case comparison

| Case | Strongest driver (unit_id, Δ) | 2nd (unit_id, Δ) |
|---|---|---|
| himom | `p02` (+21.0) | `p04` (-12.0) |
| stagehand | `p02` (-37.4) | `p06` (-32.8) |
| readyrounds | `p03` (-25.6) | `p06` (+10.6) |
| narma | `p02` (+20.1) | `p04` (-18.5) |

## Per-case z-score patterns (Welch z, signed)

| Case | z range | All same sign? | Strongest |z| |
|---|---|:-:|---:|
| himom | −0.94 to +0.68 | mixed | 0.94 |
| stagehand | −2.75 to −0.74 | **all negative** | 2.75 |
| readyrounds | −1.56 to +0.50 | mostly + with one dip | 1.56 |
| narma | −1.37 to +1.19 | mixed | 1.37 |

## Honest read

**Headline: 0 of 25 paragraph deletions clear |Δ| > 2σ_baseline across all four
cases.** Same shape as the morning's multi-replay test on `stage_assessment`,
on a different decision field (scalar `opportunity_score`) and a different
case set. Switching to scalar didn't recover above-noise per-unit signal.

**The noise floor is the dominant story.** σ_baseline values are 30-43 points
on a 200-800 scale — 5-8% noise. The 2σ threshold is 60-90 points. Worth
contrasting with the morning's structured-input run (with `## Heading` markers
preserved): σ_c was 0 across every gate_rule-bearing case. **Stripping headers
introduces ~30-40 points of stochastic noise per call**, which is what kills
the per-unit signal here. The pipeline is not inherently noisy — it's noisy
when its input structure is removed.

**Baseline cluster is also informative — and discouraging.** All four cases
land at 482, 503, 517, 482. Cross-case σ ≈ 16; within-case σ averages 35.5.
**Within-case noise exceeds cross-case signal.** The pipeline is not strongly
distinguishing between these four ventures at the `opportunity_score` level
when given unstructured prose. They all sit in the "borderline / Non-viable
to Mediocre" band (350-553).

**One sub-noise pattern worth naming: stagehand's all-negative z-stripe.**
Every paragraph deletion drops stagehand's score (range −14.8 to −37.4); no
positive z. Not single-driver — the coherent *direction* across all 6
paragraphs suggests the pipeline reads stagehand's pitch as marginally
holding its score, and any reduction in evidence pushes it down. himom and
narma show mixed signs (no coherent direction). readyrounds is mostly flat
with one moderate dip on p03.

**Comparison across cases — your question.** Different *shapes*, not
different *drivers*. None of the four cases has an above-noise per-paragraph
driver. Stagehand alone shows a coherent global shape (all-negative z).
The other three are noise-dominated.

**What the prototype confirms about v0.4 design.**

This run replicates the negative finding from the morning's multi-replay
test, on a fresh corpus and a finer-grained decision field. The pattern
holds: **per-unit causal attribution via deletion on stripped prose is
below the noise floor at N=10 baselines + N=5 deletion replays per
paragraph on the live Envelop pipeline.**

What v0.4 *can* produce robustly from the unlabeled-input approach:

1. **Per-case baseline mean + σ_baseline.** These are above-noise statistics
   in their own right (10 replays each); reading them tells you a pipeline's
   stability and where it places this venture on its score scale.
2. **Coherent global per-case shape** (e.g., stagehand's all-negative
   z-stripe). Sub-paragraph but supra-case patterns are visible even when
   no single paragraph clears 2σ.

What it cannot produce robustly:

1. **A per-paragraph causal map.** Single paragraph deletions on stripped
   prose do not exceed the noise floor at this budget on this pipeline.

**Implications for the v0.4 spec — same as before, now with scalar
confirmation.** The breakthrough framing ("Kelvin grades any pipeline
without labels via per-unit causal map") remains overstated by the data.
The defensible v0.4 product is per-case σ_baseline and per-case
opportunity_score grading — labels-free, governing-types-free, but not
per-unit-attributed.

If you want per-unit attribution to clear noise on this kind of input,
two paths:

- **Preserve structural cues.** σ goes from ~35 to ~0 when `## Heading`
  markers are kept. v0.4 could ship "auto-unitize but preserve markers
  if present" — strictly weaker promise than "any prose" but actually works.
- **Much heavier replay budget.** N=20-30 deletion replays per paragraph
  *might* surface stagehand's borderline z's as significant. Cost: 4-6×
  this run. Worth pricing only after methodology is settled.
