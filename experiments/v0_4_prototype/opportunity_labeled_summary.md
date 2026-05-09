# v0.4 throwaway — labeled-classifier perturbation-response

_Generated 2026-04-27 00:32:58_

## Per-case overview

| Case | N units | Baseline mean | σ | 2σ threshold | N above-noise |
|---|---:|---:|---:|---:|---:|
| himom | 12 | 477.9 | 33.2 | 66.3 | **1** |
| stagehand | 12 | 499.5 | 32.9 | 65.7 | **0** |
| readyrounds | 10 | 504.7 | 48.8 | 97.6 | **0** |
| narma | 11 | 460.6 | 23.6 | 47.3 | **1** |

## Pass criterion

Today's stripped-prose run: **0 of 4** cases with ≥ 1 above-noise unit.
Throwaway pass criterion: **≥ 2 of 4** cases with ≥ 1 above-noise unit.
Throwaway result: **2 of 4** cases with ≥ 1 above-noise unit.

**PASS** — labeled inputs unblock per-unit signal that stripped prose did not.

## Per-unit details

### himom  (σ_baseline = 33.2, baseline mean = 477.9)

| Unit | Type | n | deletion_mean | Δ | z | above-noise? |
|---|---|---:|---:|---:|---:|:-:|
| u06 | s06 | 4 | 549.0 | +71.1 | 2.80 | **Y** |
| u11 | s11 | 5 | 521.4 | +43.5 | 2.22 | n |
| u09 | s09 | 5 | 517.0 | +39.1 | 1.60 | n |
| u07 | s07 | 5 | 513.8 | +35.9 | 2.01 | n |
| u01 | s01 | 5 | 512.2 | +34.3 | 1.93 | n |
| u10 | s10 | 5 | 509.4 | +31.5 | 1.39 | n |
| u03 | s03 | 5 | 494.2 | +16.3 | 0.99 | n |
| u08 | s08 | 5 | 491.4 | +13.5 | 0.64 | n |
| u12 | s12 | 5 | 488.4 | +10.5 | 0.51 | n |
| u05 | s05 | 5 | 485.4 | +7.5 | 0.30 | n |
| u02 | s02 | 5 | 481.0 | +3.1 | 0.15 | n |
| u04 | s04 | 5 | 477.8 | -0.1 | -0.01 | n |

### stagehand  (σ_baseline = 32.9, baseline mean = 499.5)

| Unit | Type | n | deletion_mean | Δ | z | above-noise? |
|---|---|---:|---:|---:|---:|:-:|
| u01 | s01 | 5 | 465.6 | -33.9 | -1.64 | n |
| u07 | s07 | 5 | 465.8 | -33.7 | -2.38 | n |
| u05 | s05 | 5 | 485.2 | -14.3 | -1.04 | n |
| u10 | s10 | 5 | 485.2 | -14.3 | -1.04 | n |
| u02 | s02 | 5 | 510.6 | +11.1 | 0.75 | n |
| u06 | s06 | 5 | 492.6 | -6.9 | -0.54 | n |
| u08 | s08 | 5 | 492.6 | -6.9 | -0.54 | n |
| u11 | s11 | 5 | 492.6 | -6.9 | -0.54 | n |
| u03 | s03 | 5 | 495.8 | -3.7 | -0.19 | n |
| u04 | s04 | 5 | 495.8 | -3.7 | -0.19 | n |
| u12 | s12 | 5 | 495.8 | -3.7 | -0.19 | n |
| u09 | s09 | 5 | 500.0 | +0.5 | 0.05 | n |

### readyrounds  (σ_baseline = 48.8, baseline mean = 504.7)

| Unit | Type | n | deletion_mean | Δ | z | above-noise? |
|---|---|---:|---:|---:|---:|:-:|
| u02 | s02 | 5 | 537.8 | +33.1 | 1.84 | n |
| u03 | s03 | 5 | 537.8 | +33.1 | 1.84 | n |
| u05 | s05 | 5 | 524.4 | +19.7 | 0.82 | n |
| u10 | s10 | 5 | 488.4 | -16.3 | -0.69 | n |
| u01 | s01 | 5 | 519.6 | +14.9 | 0.84 | n |
| u08 | s08 | 5 | 517.0 | +12.3 | 0.46 | n |
| u04 | s04 | 5 | 516.8 | +12.1 | 0.53 | n |
| u09 | s09 | 5 | 498.8 | -5.9 | -0.26 | n |
| u06 | s06 | 5 | 509.4 | +4.7 | 0.19 | n |
| u07 | s07 | 5 | 506.2 | +1.5 | 0.07 | n |

### narma  (σ_baseline = 23.6, baseline mean = 460.6)

| Unit | Type | n | deletion_mean | Δ | z | above-noise? |
|---|---|---:|---:|---:|---:|:-:|
| u07 | s07 | 5 | 509.2 | +48.6 | 2.98 | **Y** |
| u02 | s02 | 5 | 494.2 | +33.6 | 2.27 | n |
| u08 | s08 | 5 | 491.4 | +30.8 | 1.55 | n |
| u04 | s04 | 5 | 483.8 | +23.2 | 1.57 | n |
| u10 | s10 | 5 | 483.8 | +23.2 | 1.57 | n |
| u11 | s11 | 5 | 479.2 | +18.6 | 0.69 | n |
| u03 | s03 | 5 | 471.6 | +11.0 | 0.49 | n |
| u01 | s01 | 5 | 470.4 | +9.8 | 0.93 | n |
| u05 | s05 | 5 | 468.8 | +8.2 | 0.32 | n |
| u06 | s06 | 5 | 468.8 | +8.2 | 0.32 | n |
| u09 | s09 | 5 | 463.0 | +2.4 | 0.32 | n |

