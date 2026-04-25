# Kelvin v0.4 — 🟨 Partially measured

## Sub-scores

| Axis | Sub-score |
| --- | --- |
| Drift | 1.00 |
| Sensitivity | 1.00 |
| Equivalence | 1.00 |

## Pillar coverage

- **Pillar 1 (drift)** — measured
- **Pillar 2 (rule swap)** — silent: gate_rule format not recognized (pipeline reads rules in a non-standard layout)
- **Pillar 3 (formatting)** — measured

## What's working

- Stability
- Rule responsiveness
- Robustness

## Top fix

Restructure gate_rule bodies to match Kelvin's expected pattern (a `requires` or `when` clause naming the switching axis), or wait for v0.5's broader format coverage.

_Run with `--verbose` for per-axis sub-score detail and the per-family breakdown._
