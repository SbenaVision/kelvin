# narma — v0.4 prototype diagnosis (opportunity_score)

**Field:** opportunity_score (200-800 scale, derived from VVS dimensions P, M, C)

## Baseline
- Replays (N=10): [515.0, 553.0, 402.0, 463.0, 463.0, 463.0, 515.0, 463.0, 515.0, 463.0]
- mean = 481.5
- σ = 42.8

## Per-paragraph deletion impact

| Unit | n | deletion_mean | delta vs baseline | z | above-noise (|Δ|>2σ)? |
|---|---:|---:|---:|---:|:-:|
| `p02` | 5 | 501.6 | +20.1 | 1.19 | n |
| `p04` | 5 | 463.0 | -18.5 | -1.37 | n |
| `p01` | 5 | 471.6 | -9.9 | -0.40 | n |
| `p05` | 5 | 483.8 | +2.3 | 0.12 | n |
| `p06` | 5 | 483.8 | +2.3 | 0.12 | n |
| `p03` | 5 | 480.8 | -0.7 | -0.04 | n |

**Diagnosis:** No paragraph deletion moves opportunity_score by more than 2σ (42.8 × 2 = 85.7). The pipeline holds its score against unit removal at this sample size — either no single unit drives the score, or the noise floor exceeds any individual unit's contribution.

