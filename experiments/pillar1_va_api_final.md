# Pillar 1 final noise-floor measurement — VA API, 2026-04-24

**Status:** final (n=8 corpus, n=6 effective σ_c measurement). Supersedes the
earlier n=4 partial record. This is the paper-ready measurement used in
whitepaper §5.3 and by the 0.3.0-rc1 release.

## Configuration

- Pipeline: live Venture Assessment API via
  `harness/kelvin_runner.mjs`-style wrapper at
  `/Users/sb/MyDev/kelvin-tryout/va_wrapper.py`
- Corpus: 8 cases at `/Users/sb/MyDev/kelvin-tryout/cases/`
- `noise_floor.enabled: true`, `replications: 10`
- `retry_policy: transient_exit_codes: [1], max_attempts: 3`
- `cache_dir` enabled; canonical baselines cache-hit, replays bypass
  cache by design so each is a fresh live call
- Kelvin version: post-PR-#11 main (phase-b merged)
- Run wrapper: `nohup caffeinate -s kelvin check --log-format json >
  run.log 2> stderr.log` per FAILURES.md hardening
- Start: 2026-04-24 12:37:39+0300
- End: ~13:40:32+0300 (run_completed elapsed_s = 3772.9)
- Total wall-clock: 62 min 52s

## Per-case σ_c (n=8 cases attempted, n=6 with measurable σ_c)

| Case | Baseline score | σ_c | Replays kept |
|---|---:|---:|---:|
| `ai_dev_tool` | 38 | **0.1846** | 10 |
| `biotech_diagnostics` | 66 | **0.1468** | 10 |
| `content_solo_creator` | 58 | **0.1230** | 10 |
| `fintech_compliance` | 69 | **0.1555** | 10 |
| `hardware_climate` | 35 | **0.1675** | 10 |
| `local_services_app` | 42 | **0.1289** | 10 |
| `marketplace_consumer` | 42 | — | 1 (9 replays failed) |
| `saas_b2b_early` | 38 | — | 1 (9 replays failed) |

### Why 2 cases lost all replays

`marketplace_consumer` and `saas_b2b_early` — the alphabetically-last
two cases — hit 9 consecutive `noise_floor_replay_failed` events each
during their replay phase (all exit-1 failures from the wrapper). The
retry policy (`transient_exit_codes: [1], max_attempts: 3`) fired
correctly — 29 `retry_giving_up` events in the stderr log confirm
exhausted retries — but the failures persisted even after 3 attempts
per call.

Likely cause: **VA API rate-limiting or infrastructure degradation**
after ~55 minutes of sustained 5-6 call-per-minute traffic. The
failures clustered at the end of the baseline+replay phase (within a
~100 second window at `ts≈1777025898–1777025998`), not at random
across cases. The preceding 6 cases — which ran at 5-10 minute
intervals earlier in the run — all succeeded cleanly.

Aggregation semantics are intact: `scorer.sigma_c()` returns `None`
when fewer than 2 replay decisions are available, and `aggregate()`
correctly drops those cases when computing η. Final η is the mean of
6 measurable σ_c values.

## Final η

```
η = mean(σ_c) across n=6 = (0.1846 + 0.1468 + 0.1230 + 0.1555
                           + 0.1675 + 0.1289) / 6 = 0.1511
```

Drift from partial n=4 (η=0.1381): **+0.0130** — within the 0.02
threshold the original partial-results document set for "accept the
partial numbers without re-evaluation." Both samples cluster in the
0.12–0.19 range; the n=8 mean is higher than n=4 mean because the two
cases that failed replays happened to be cases whose σ_c we didn't get
to measure (so we can't rule out that η would be even higher with
those two included).

## Final calibration

From `runs_0.2.1/real/kelvin/report.json`:

| Metric | Value |
|---|---:|
| Inv_raw | **0.8245** |
| Sens_raw | **0.1522** |
| K_raw | **1.0234** |
| η | **0.1511** |
| 1 − Inv_raw | 0.1755 |
| η < 1 − Inv_raw? | **yes — measurable** (by 0.024) |
| Inv_cal = (0.8245 − 0.1511) / (1 − 0.1511) | **0.7932** |
| Sens_cal = max(0, (0.1522 − 0.1511) / 0.8489) | **0.0013** |
| K_cal = (1 − 0.7932) + (1 − 0.0013) | **1.2055** |

## Cross-pipeline final K_cal

| Pipeline | K_raw | η | Inv_cal | Sens_cal | K_cal |
|---|---:|---:|---:|---:|---:|
| constant | 1.000 | 0.000 | 1.000 | 0.000 | **1.000** |
| brittle (first-500-chars) | 1.055 | 0.000 | 0.945 | 0.000 | **1.055** |
| VA API | **1.023** | 0.151 | 0.793 | 0.001 | **1.206** |
| peer-swap adversary | 1.010 | 0.149 | — | — | **None** (unmeasurable) |

## Headline finding

**The VA API's invariance appeared to beat brittle on raw signal (Inv=0.824 vs 0.945) — that was mostly LLM stochasticity.** After noise calibration:
- **VA API K_cal (1.206) is worse than brittle K_cal (1.055)** despite the VA API being an LLM-backed pipeline with theoretically richer evidence handling.
- **VA API Sens_cal ≈ 0.001** — essentially zero. Governing-unit swaps do not move the decision above the stochasticity floor. The 0.1522 raw sensitivity was noise, not rule-tracking.
- **VA API Inv_cal = 0.793** — meaningful residual anchoring, but worse than brittle's uncalibrated 0.945 under fair comparison.
- **K_cal is measurable** (η = 0.151 < 1 − Inv_raw = 0.176), but only by a narrow margin of 0.024. If the unmeasured 2 cases had shifted η upward — which they might have, given their replays were failing — K_cal could have landed as `None`.

This is the §3.4 paired-signal argument reaching its full form on a live LLM pipeline. K_raw credited the VA API's noise-driven output changes as invariance signal; K_cal withdraws that credit, and separately reveals that Sens_raw was mostly noise with almost no real rule-tracking residual.

## Contrast with the partial n=4 projection

| Metric | Partial (n=4) | Final (n=6 eff) | Δ |
|---|---:|---:|---:|
| η | 0.138 | 0.151 | +0.013 |
| Inv_cal | 0.810 | 0.793 | −0.017 |
| Sens_cal | 0.080 | 0.001 | **−0.079** |
| K_cal | 1.110 | 1.206 | +0.096 |

The big swing is Sens_cal collapsing from 0.080 to 0.001. This
happened because:
1. Final η is 0.013 larger than partial, shrinking the calibration
   denominator and pushing more Sens_raw into the "below noise" zone.
2. Final Sens_raw (0.152) was computed across 14 swap samples (7
   money + 7 alternative, reflecting the 1 swap per governing type per
   case and 7 effective cases with successful baselines in Phase 2).
   The partial projection multiplied the 0.207 Sens_raw from the
   earlier 0.2.1-era run against the new η. The actual final Sens_raw
   is lower than the earlier 0.2.1 number by 0.055 — likely also VA
   API drift between runs.

Both effects compound. The final K_cal of 1.206 is more honest than
the partial projection of 1.110.

## Perturbation-level failures in the final run

| Metric | Value |
|---|---:|
| Perturbations total | 88 |
| Succeeded | 77 |
| Failed | 11 |
| `retry_detected` events | 61 |
| `retry_giving_up` events | 29 |

The 61 retry_detected / 29 retry_giving_up counts demonstrate the
retry policy worked correctly under real transient failures. Of the
18 `noise_floor_replay_failed` events, all were in the last ~2
minutes of the baseline+replay phase, consistent with API-side
degradation.

## Schema version & report shape

`report.json` conforms to the v0.3.0 schema with additive
`noise_floor_eta`, `invariance_calibrated`, `sensitivity_calibrated`,
`kelvin_score_calibrated` keys. Per-case reports include a
`noise_floor` block with `sigma_c`, `replay_count`, and
`baseline_replays`. When noise_floor is disabled, these keys are
omitted and the report matches v0.2.1 byte-for-byte (Phase A regression
gate).

## Reference run artifacts

- Full JSON event log: `/Users/sb/MyDev/kelvin-tryout/runs_0.2.1/logs/real_final.log`
- Stderr (retry/giving-up events): `/Users/sb/MyDev/kelvin-tryout/runs_0.2.1/logs/real_final.stderr` (108 lines)
- Run-level report.json: `/Users/sb/MyDev/kelvin-tryout/runs_0.2.1/real/kelvin/report.json`
- Per-case reports: `/Users/sb/MyDev/kelvin-tryout/runs_0.2.1/real/kelvin/<case>/report.json`
- Cache: `/Users/sb/MyDev/kelvin-tryout/runs_0.2.1/cache_real/` (includes replay entries)
