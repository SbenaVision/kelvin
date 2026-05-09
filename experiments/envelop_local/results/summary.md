# Envelop local — Kelvin run

- **Corpus**: 8 cases at `experiments/envelop_local/cases/` spanning 3 Go (alpha, bravo, charlie), 3 Reshape (delta, echo, foxtrot), 2 No-Go (golf via D=1 kill-zone, hotel via compound weakness).
- **Decision field**: `verdict` ∈ {Go, Reshape, No-Go}.
- **Governing type**: `gate_rule`.
- **Engine**: Python port of `supabase/functions/venture-assessment/vvs-engine.ts` — pure function, no network, no LLM.

## Headline numbers

| Pipeline | η | Invariance | Sensitivity | K_raw | K_cal |
|---|---|---|---|---|---|
| constant (always No-Go) | 0.000 | 1.000 | 0.000 | **1.000** | **1.000** |
| brittle (first-section only) | 0.000 | 0.944 | 0.000 | **1.056** | **1.056** |
| envelop (VVS local) | 0.000 | 0.875 | 0.875 | **0.250** | **0.250** |

(8 cases × ~10 perturbations/case = 72 invariance samples, 8 sensitivity samples per run. Seed 0.)

## η for Envelop

**η = 0.0000** over 80 baseline replications (8 cases × 10 reps). The local VVS engine is a pure deterministic function of seven integer dimensions, a goal frame, and a stage profile — same input, same output, every time. Nothing to calibrate.

Kelvin 0.2.1 validates the `noise_floor:` YAML block but does not yet consume it in the scorer (Pillar 1 `K_cal` is held for v0.3 per CHANGELOG), so the replication measurement above was done outside Kelvin via `measure_noise_floor.py`. Running the same config with `noise_floor.enabled: true` produces byte-identical scoring output to the plain run — confirmed.

## Side-by-side vs VA API (η ≈ 0.13)

**Envelop-local is cleaner, not driftier.** The 0.13 noise floor on VA API is LLM-extraction stochasticity: document-extract and factsheet-synthesis steps don't roundtrip deterministically across replays, so ~13% of replications disagree with the modal verdict on unchanged inputs. Any Invariance drift below ~0.13 on VA API is statistically indistinguishable from noise. On local Envelop, Invariance drift at 0.125 (1 − 0.875) is entirely signal — all of it is the pipeline actually responding to perturbations (pad_content injecting a peer's Gate Rule ahead of the focal one, which my simple regex grabs first).

K_cal = K_raw for every local pipeline here. The comparison that matters:

- **VA API**: η ≈ 0.13. You back this out of K_raw before claiming anything about presentation-reactivity.
- **Envelop-local (this run)**: η = 0. No correction needed.
- **ΔK between grounded and degenerate**: 0.75 (constant 1.000 → envelop 0.250) — cleanly separates the two failure-mode archetypes on the same corpus with the same perturbation suite.

## Notes on the Envelop pipeline's 0.88 invariance

The drift isn't presentation bias in the classical sense — it's a real limitation of the pipeline's implementation: `SECTION_RE.search(text)` returns the *first* `## Gate Rule` it finds. Kelvin's `pad_content` perturbation occasionally injects a peer case's Gate Rule ahead of the focal one, and the pipeline reads the wrong one. Exactly the kind of diagnostic finding Kelvin is built to expose. A production implementation would either error on duplicates or scan all Gate Rule sections.

## Reproduction

```bash
cd experiments/envelop_local
export PYTHONPATH=../../src
for p in constant brittle envelop; do
  ( cd $p && rm -rf kelvin && python -m kelvin check )
done
python3 measure_noise_floor.py --pipeline pipelines/envelop.py --cases cases --n 10 --out results/noise_floor_envelop.json
```
