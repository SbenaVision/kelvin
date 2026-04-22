# Tier 3 — grounded vs degenerate empirical comparison

This experiment addresses the reviewer's "pre-empirical" critique by shipping Kelvin's central methodological claim as a runnable artifact: the paired signal (Invariance × Sensitivity, summarized as `K`) separates an evidence-tracking pipeline from a constant-output pipeline on the *same* case suite.

## The claim being tested

From whitepaper §3.4:

> A degenerate pipeline that always returns the same answer scores Invariance 1.0 and Sensitivity 0.0 by construction. A grounded pipeline that reads the governing unit scores lower Invariance (presentation-sensitive in places) and meaningfully non-zero Sensitivity (moves with the governing evidence). Neither axis alone cleanly distinguishes them; the *paired* signal does.

Table 3 is the empirical counterpart to that prediction.

## What the experiment ships

- `pipelines/grounded.py` — a deterministic rule-based pipeline that routes `stage_assessment` by matching keywords in the `## Gate Rule` section and cross-referencing `## Traction Signal`. Zero LLM, zero network, zero cost. Reproducible bit-for-bit.
- `pipelines/degenerate.py` — always returns `stage_assessment = "pre-seed"`, regardless of input. The §3.4 degenerate.
- `grounded/kelvin.yaml`, `degenerate/kelvin.yaml` — Kelvin configs pointing each pipeline at the same `cases/` directory at the repo root (6 cases: envelop, freakinggenius, artisanflow, meridian, northpass, rhodium).
- `run.sh` — runs both pipelines, builds the comparison table.
- `build_table.py` — reads both `report.json` files and emits `results/table_3.md` with numbers and interpretation derived from the actual run.

## Reproducing Table 3

```bash
cd experiments/tier3
./run.sh
```

Completes in under 10 seconds on a laptop. Writes:

- `grounded/kelvin/report.json` — full per-case scores for the grounded run.
- `degenerate/kelvin/report.json` — same, for the degenerate run.
- `results/table_3.md` — the side-by-side comparison with interpretation.

The experiment's `run.sh` pins Kelvin to this repo's `src/` via `PYTHONPATH`, so it uses the exact library version being evaluated rather than whatever is installed in a surrounding virtualenv.

## Latest results

See [`results/table_3.md`](results/table_3.md) for the current numbers. Re-running the experiment overwrites this file deterministically; the committed version reflects the last run.

## Scope and honest limitations

- **Grounded is synthetic, not LLM-backed.** The rule-based stand-in is enough to demonstrate that the paired signal separates grounded from degenerate on identical perturbations, but it is obviously not a full production RAG pipeline. Its specific invariance score surfaces a specific (and realistic) failure mode of rule-based pipelines — reading the first matching header rather than the focal one — which Kelvin catches under pad_content perturbations. That is informative about Kelvin's diagnostic behavior, but the *absolute* numbers should not be read as "how a real LLM pipeline scores."
- **Live-Envelop column is available on request.** To add a third column using the live Envelop edge function:
  ```bash
  cd experiments/tier3
  ln -s ../../harness harness   # optional: keep the runner close
  cp ../../kelvin.yaml envelop_live/kelvin.yaml   # or craft a fresh one
  ( cd envelop_live && python3 -m kelvin check )
  ```
  This costs real Supabase/LLM spend (~72 calls for the 6-case suite, each ~30–40 s, counted against the user's quota) and is subject to transient upstream 5xx responses. The Envelop harness now retries with exponential backoff on 500/502/503/504 (see `harness/kelvin_runner.mjs`), which addresses the 2-of-14 failures flagged in the original reviewer feedback.
- **n = 6 cases.** The reviewer asked for n ≥ 6. The cases range deliberately across the decision space: `idea`-adjacent (northpass), `pre-seed` / `idea` (freakinggenius), `pre-seed` (meridian), `seed` (envelop), `growth` (artisanflow), `scale` (rhodium). A larger corpus would narrow confidence intervals; the current six are enough to demonstrate the methodological claim testably.

## What this experiment does **not** claim

It does **not** claim that the grounded pipeline here represents typical real-world RAG performance. It does not claim the sensitivity or invariance *magnitudes* are calibrated for cross-pipeline comparison. It does not address the content-leakage limitation in raw swap (whitepaper §3.3) — that is addressed by `swap_condition` in v0.3, not here.

What it *does* claim, and demonstrates empirically, is that the paired diagnostic separates evidence-tracking from evidence-blind pipelines on a common perturbation suite, using the same code path for both, with the constant-output degenerate landing at the exact K predicted by §3.4.
