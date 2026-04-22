# Table 3 — grounded vs degenerate on the same suite

N cases: **6**.  Grounded perturbations: 60.  Degenerate perturbations: 60.

| Pipeline | Invariance | Sensitivity | Kelvin score `K` |
|---|---|---|---|
| Grounded (rule-based stand-in) | 0.85 | 0.67 | **0.48** |
| Degenerate (constant output) | 1.00 | 0.00 | **1.00** |

`K = (1 − Invariance) + (1 − Sensitivity)`, range `[0, 2]`, lower = more anchored.

## Interpretation

- **Degenerate pipeline: K = 1.00.** Invariance 1.00 (output never moves — trivially stable) and Sensitivity 0.00 (every governing-unit swap was ignored) together produce a K of exactly 1.0. This matches the §3.4 analytical prediction pinned in `tests/test_scorer.py::TestKelvinScore::test_constant_output_pipeline`.
- **Grounded pipeline: K = 0.48.** Invariance 0.85 (some drift under peer-content padding — Kelvin catches that the rule-based stand-in reads the first `## Gate Rule` section it finds, so perturbations that place a peer's gate rule earlier shift the decision) and Sensitivity 0.67 (most governing-unit swaps move the decision). Both axes carry signal.
- **Paired separation: ΔK = 0.52.** The paired diagnostic surfaces the difference between the two pipelines in a single scalar. The per-axis terminal diagnostic also fires correctly — "Gate rules are being ignored" shows on the degenerate run (6 of 6 swaps unchanged) and is silent on the grounded run.

## Scope and limitations

The grounded column uses a deterministic rule-based stand-in, not a full LLM-backed pipeline. It is reproducible with zero network cost and zero LLM spend, so these numbers are stable across any machine that runs `./run.sh`. A complementary live-Envelop column can be produced by running `kelvin check` against `harness/kelvin_runner.mjs` on the same case suite; see `experiments/tier3/README.md` for the command and notes on the retry behavior added to handle transient upstream 5xx responses.
