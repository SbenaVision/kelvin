# stagehand — v0.4 prototype diagnosis (opportunity_score)

**Field:** opportunity_score (200-800 scale, derived from VVS dimensions P, M, C)

## Baseline
- Replays (N=10): [553.0, 553.0, 463.0, 500.0, 500.0, 500.0, 500.0, 500.0, 463.0, 500.0]
- mean = 503.2
- σ = 30.3

## Per-paragraph deletion impact

| Unit | n | deletion_mean | delta vs baseline | z | above-noise (|Δ|>2σ)? |
|---|---:|---:|---:|---:|:-:|
| `p02` | 5 | 465.8 | -37.4 | -2.75 | n |
| `p06` | 5 | 470.4 | -32.8 | -2.71 | n |
| `p04` | 5 | 473.4 | -29.8 | -2.11 | n |
| `p05` | 5 | 477.8 | -25.4 | -1.93 | n |
| `p03` | 5 | 488.2 | -15.0 | -1.05 | n |
| `p01` | 5 | 488.4 | -14.8 | -0.74 | n |

**Diagnosis:** No paragraph deletion moves opportunity_score by more than 2σ (30.3 × 2 = 60.6). The pipeline holds its score against unit removal at this sample size — either no single unit drives the score, or the noise floor exceeds any individual unit's contribution.

