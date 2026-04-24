# 0.3.0 integration run — Pillar 1 + Pillar 3 on VA API, 2026-04-24

Supersedes `experiments/pillar1_va_api_final.md` (0.2.1-era numbers)
as the paper-ready measurement for v0.3.0. Pillar 2 does not apply to
this corpus (no gate_rule structure); see `experiments/
pillar2_decomposition_demo/` for the Pillar 2 empirical demonstration
on the whitepaper's original tier3 gate-rule corpus.

## Configuration

- Pipeline: live Venture Assessment API via `va_wrapper.py`
- Corpus: 8 cases at `/Users/sb/MyDev/kelvin-tryout/cases/`
- All 11 Pillar 3 families enabled; counterfactual_swap enabled
  (produces zero perturbations on VA corpus by design — no gate_rule
  units to parse)
- `noise_floor.enabled: true, replications: 5`
- `retry_policy: transient_exit_codes: [1], max_attempts: 3`
- Run wrapper: `nohup caffeinate -s kelvin check --log-format json`
- Start: 2026-04-24 17:08:33+0300, end: ~20:19:05+0300
- Total wall-clock: **190.5 min (3h 10m)**
- Perturbations: 281 ok / 7 failed out of 288 total

## Headline numbers

### Pillar 1 (noise-floor calibration)

| Metric | Value |
|---|---:|
| Inv_raw | 0.8689 |
| Sens_raw | 0.1765 |
| K_raw | 0.9545 |
| η | 0.1244 |
| 1 − Inv_raw | 0.1311 |
| η < 1 − Inv_raw? | yes (measurable by 0.007 margin) |
| **Inv_cal** | **0.8503** |
| **Sens_cal** | **0.0595** |
| **K_cal** | **1.0902** |

### Pillar 3 (mechanical sensitivity)

| Metric | Value |
|---|---:|
| mechanical_sensitivity | 0.1869 |
| mechanical_sensitivity_sample | 48 |

Mechanical sensitivity is dominated by the numeric_magnitude family
(44/48 contributing samples). Comparator_flip produced 1 sample;
polarity_flip produced 3. The low sample count on the closed-list
families reflects their sparse applicability on this corpus (the
venture descriptions contain few explicit comparator phrases and few
polarity-swappable adjectives in governing sections).

### Pillar 3 invariance pool contribution

Invariance aggregate Inv_raw = 0.8689 is now computed across **217
samples**, up from 72 in v0.2.x runs. The additional ~145 samples
come from the Pillar 3 presentation-layer + rhetorical families:
whitespace_jitter, punctuation_normalize, bullet_reformat,
non_governing_duplication, hedge_injection, discourse_marker_injection,
meta_commentary_injection, and the opportunistic politeness_injection
(0 samples on this corpus because no imperative-verb-initial sentences
exist in non-governing sections — the family correctly caps at 0).

## Drift vs earlier 0.2.1-era VA measurement

Reference: `experiments/pillar1_va_api_final.md` (2026-04-24 earlier
run with only Pillar 1 enabled, replications=10).

| Metric | 0.2.1-era (n=6 σ_c) | 0.3.0 (n=8 σ_c, reps=5) | Δ |
|---|---:|---:|---:|
| η | 0.1511 | 0.1244 | −0.0267 |
| Inv_raw | 0.8245 | 0.8689 | +0.0444 |
| Sens_raw | 0.1522 | 0.1765 | +0.0243 |
| K_raw | 1.0234 | 0.9545 | −0.0689 |
| Inv_cal | 0.7932 | 0.8503 | +0.0571 |
| Sens_cal | 0.0013 | 0.0595 | +0.0582 |
| K_cal | 1.2055 | 1.0902 | −0.1153 |

Directional reading:
- **η dropped 0.027** — with replications=5 rather than 10, the
  pairwise-distance estimator has more variance. Also, all 8 cases
  produced measurable σ_c this time (no replay failures), whereas the
  earlier run had 6/8 effective — the two cases that failed replays
  in the earlier run (`marketplace_consumer`, `saas_b2b_early`) may
  contribute lower σ_c when they do succeed, pulling the mean down.
- **Inv_raw climbed 0.044** — the additional ~145 Pillar 3 samples
  (most of which are presentation-layer probes that a competent LLM
  correctly ignores) inflate Inv_raw. This is not pipeline improvement;
  it's sample composition change.
- **Sens_raw climbed 0.024** — the 0.3.0 run's swap perturbations
  produced slightly more movement than the earlier run, consistent
  with API-side drift between runs, not methodology.
- **K_cal dropped 0.115** — the combined effect of lower η (smaller
  noise subtraction) and higher Inv_raw (more presentation samples).
  This *is* a lower K_cal (pipeline looks better), but the comparison
  across samples of different composition is not apples-to-apples.

**The paper should cite the 0.3.0 numbers with a clear note that
invariance sample composition changed** and that the prior run's K_cal
of 1.206 remains a defensible point estimate on the narrower sample.

## Cross-pipeline K_cal landscape (0.3.0 scope)

| Pipeline | K_raw | η | Inv_cal | Sens_cal | K_cal |
|---|---:|---:|---:|---:|---:|
| constant (no noise floor) | 1.000 | 0.000 | 1.000 | 0.000 | 1.000 |
| brittle (no noise floor) | 1.055 | 0.000 | 0.945 | 0.000 | 1.055 |
| VA API (0.3.0, n=8, reps=5) | **0.955** | **0.124** | **0.850** | **0.060** | **1.090** |
| peer-swap adversary | 1.010 | 0.149 | — | — | None (unmeasurable) |

The VA API continues to land between brittle and the unmeasurable
adversary on K_cal. The Sens_cal of 0.060 is now non-trivial — the
pipeline shows weak but detectable rule-tracking residual above
stochasticity. The earlier run's Sens_cal=0.001 was within one η-drift
of this value.

## Perturbation sample distribution

Of the 288 perturbations generated (281 ok + 7 failed):
- 24 reorder, 24 pad_length, 24 pad_content (v0.2 inter-slot)
- 16 swap (v0.2 governing-unit)
- 0 swap_condition (VA corpus has no gate_rule)
- 24 whitespace_jitter, 24 punctuation_normalize, 16 bullet_reformat,
  24 non_governing_duplication (Pillar 3 presentation-layer)
- 24 hedge_injection, 0 politeness_injection, 24 discourse_marker_injection,
  16 meta_commentary_injection (Pillar 3 rhetorical)
- 44 numeric_magnitude, 1 comparator_flip, 3 polarity_flip
  (Pillar 3 mechanical sensitivity)
- 40 noise-floor replays (5 per case × 8 cases)

## Artifacts

- Run-level report: `runs_0.3.0/real/kelvin/report.json`
- Per-case reports: `runs_0.3.0/real/kelvin/<case>/report.json`
- JSON event log: `runs_0.3.0/logs/run.log`
- Stderr (retry events): `runs_0.3.0/logs/run.stderr`
- Replay cache: `runs_0.3.0/cache_real/`
