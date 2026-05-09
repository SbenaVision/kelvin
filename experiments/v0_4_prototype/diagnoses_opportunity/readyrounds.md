# readyrounds — v0.4 prototype diagnosis (opportunity_score)

**Field:** opportunity_score (200-800 scale, derived from VVS dimensions P, M, C)

## Baseline
- Replays (N=10): [553.0, 553.0, 515.0, 515.0, 500.0, 463.0, 463.0, 553.0, 500.0, 553.0]
- mean = 516.8
- σ = 35.9

## Per-paragraph deletion impact

| Unit | n | deletion_mean | delta vs baseline | z | above-noise (|Δ|>2σ)? |
|---|---:|---:|---:|---:|:-:|
| `p03` | 5 | 491.2 | -25.6 | -1.56 | n |
| `p06` | 5 | 527.4 | +10.6 | 0.50 | n |
| `p02` | 5 | 522.6 | +5.8 | 0.42 | n |
| `p04` | 5 | 512.2 | -4.6 | -0.25 | n |
| `p05` | 5 | 513.8 | -3.0 | -0.14 | n |
| `p07` | 5 | 519.8 | +3.0 | 0.15 | n |
| `p01` | 5 | 519.6 | +2.8 | 0.19 | n |

**Diagnosis:** No paragraph deletion moves opportunity_score by more than 2σ (35.9 × 2 = 71.8). The pipeline holds its score against unit removal at this sample size — either no single unit drives the score, or the noise floor exceeds any individual unit's contribution.

