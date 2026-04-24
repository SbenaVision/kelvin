# Pillar 1 partial noise-floor measurement — VA API, 2026-04-24

**Status:** partial (n=4 of 8 cases). Full n=8 measurement scheduled for the
0.3.0-rc1 verification run before paper submission.

## Why partial

The B6 run on 2026-04-24 was killed silently by the OS after completing
4 of 8 cases' baseline + noise-floor replay phase (see
[FAILURES.md](../FAILURES.md) at repo root for the post-mortem). The
JSON log preserves per-case σ_c for the 4 completed cases; the
`report.json` was never written because `run_completed` never fired.

## Configuration

- Pipeline: live Venture Assessment API via
  `harness/kelvin_runner.mjs`-style wrapper at
  `/Users/sb/MyDev/kelvin-tryout/va_wrapper.py`
- Corpus: 8 cases at `/Users/sb/MyDev/kelvin-tryout/cases/`
- `noise_floor.enabled: true`, `replications: 10`
- `retry_policy: transient_exit_codes: [1], max_attempts: 3`
- `cache_dir` enabled for canonical baseline calls; replays bypass
  cache by design
- Kelvin version: `0.3.0-dev` (phase-b worktree, post-B5)

## Per-case σ_c (what we have)

| Case | σ_c | Replays | Baseline score |
|---|---:|---:|---:|
| `ai_dev_tool` | **0.1716** | 10 | 38 |
| `biotech_diagnostics` | **0.0982** | 10 | 66 |
| `content_solo_creator` | **0.0978** | 10 | 58 |
| `fintech_compliance` | **0.1847** | 10 | 69 |

## Partial η

```
η = mean(σ_c) across n=4 = (0.1716 + 0.0982 + 0.0978 + 0.1847) / 4 = 0.1381
```

**Caveat**: n=4 is half the planned sample. The four completed cases
span the decision space (SaaS, biotech, content, fintech verticals)
but do not include the marketplace, hardware, local-services, or
consumer-app cases. True η could drift if the remaining 4 cases
cluster differently.

## Projected K_cal (using partial η and 2026-04-24 K_raw numbers)

Applying `scorer.calibrate()` with partial η against the VA API's
K_raw numbers from the 2026-04-24 0.2.1 verification run (which did
NOT have noise floor enabled):

```
Inv_raw = 0.8361     (from runs_0.2.1/real/kelvin/report.json)
Sens_raw = 0.2068
K_raw = 0.9571

η = 0.1381
1 - Inv_raw = 0.1639   →   η < 1 - Inv_raw, K_cal is measurable

Inv_cal  = (0.8361 - 0.1381) / (1 - 0.1381) = 0.6980 / 0.8619 = 0.8098
Sens_cal = (0.2068 - 0.1381) / (1 - 0.1381) = 0.0688 / 0.8619 = 0.0798
K_cal    = (1 - 0.8098) + (1 - 0.0798) = 0.1902 + 0.9202 = 1.1104
```

## Executive reading

K_cal is **measurable-but-barely-better-than-constant**. Pillar 1
reveals that the VA API's K_raw = 0.957 — which looked like clean
evidence-tracking — was **mostly LLM stochasticity rather than
presentation-reactivity**.

Cross-pipeline K_cal (this session, all with noise_floor.enabled):

| Pipeline | K_raw | η | K_cal |
|---|---:|---:|---:|
| constant | 1.000 | 0.000 | **1.000** (theorem preserved) |
| brittle | 1.055 | 0.000 | **1.055** |
| VA API (projected, n=4) | 0.957 | 0.138 | **1.110** |
| peer-swap adversary | 1.010 | 0.149 | **None** (unmeasurable) |

The VA API scores **worse than the brittle pipeline** on K_cal after
calibration — despite scoring better on K_raw. Interpretation: the
VA API's invariance gap (0.164 on raw) was consumed mostly by
stochasticity, leaving a thin anchoring signal that doesn't
outperform the brittle first-500-chars heuristic under fair
comparison.

This is the §3.4 paired-signal argument reaching its full form:
K_raw credits a pipeline for noise-driven output changes that look
like sensitivity; K_cal refuses that credit. The whitepaper §5.3
update captures the finding for the 0.3.0 paper revision.

## 0.3.0-rc1 verification checklist

Full n=8 re-run before paper submission. See
[FAILURES.md](../FAILURES.md) for the process-hygiene requirements.
Specifically for this measurement:

- [ ] `caffeinate -s` wrapper on the kelvin invocation
- [ ] Separate stderr file (not merged via `2>&1`)
- [ ] Minimum N=10 replays preserved
- [ ] σ_c values for all 8 cases land
- [ ] `run_completed` event fires; `report.json` at
      `runs/real/kelvin/report.json` is the final source of truth for
      paper numbers
- [ ] If η shifts by >0.02 from the partial 0.138 once n=8 lands,
      update whitepaper §5.3 and this document; do not silently roll
      the new number into the paper without re-evaluating whether
      K_cal becomes unmeasurable
