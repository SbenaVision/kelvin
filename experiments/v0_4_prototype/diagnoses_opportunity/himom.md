# himom — v0.4 prototype diagnosis (opportunity_score)

**Field:** opportunity_score (200-800 scale, derived from VVS dimensions P, M, C)

## Baseline
- Replays (N=10): [463.0, 463.0, 463.0, 463.0, 515.0, 463.0, 463.0, 463.0, 515.0, 553.0]
- mean = 482.4
- σ = 32.9

## Per-paragraph deletion impact

| Unit | n | deletion_mean | delta vs baseline | z | above-noise (|Δ|>2σ)? |
|---|---:|---:|---:|---:|:-:|
| `p02` | 5 | 503.4 | +21.0 | 0.68 | n |
| `p04` | 5 | 470.4 | -12.0 | -0.94 | n |
| `p06` | 5 | 470.4 | -12.0 | -0.94 | n |
| `p05` | 5 | 491.4 | +9.0 | 0.43 | n |
| `p03` | 5 | 488.4 | +6.0 | 0.29 | n |
| `p01` | 5 | 480.8 | -1.6 | -0.10 | n |

**Diagnosis:** No paragraph deletion moves opportunity_score by more than 2σ (32.9 × 2 = 65.8). The pipeline holds its score against unit removal at this sample size — either no single unit drives the score, or the noise floor exceeds any individual unit's contribution.

