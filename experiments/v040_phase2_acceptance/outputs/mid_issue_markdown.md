# Kelvin v0.4 — ⚠️ Needs work

## Sub-scores

| Axis | Sub-score |
| --- | --- |
| Drift | 0.33 |
| Sensitivity | 0.38 |
| Equivalence | 0.50 |

## What's wrong

1. **Drift** — Your pipeline gives different answers for the same input 25% of the time. Same input should produce the same output.
   - **Fix:** Set temperature=0 in your LLM calls and re-check. If your pipeline isn't LLM-backed, look for non-deterministic input (timestamps, randomized retrieval order, time-of-day code paths).
2. **Brittleness** — Cosmetic changes (whitespace, reorder, padding) move the output. Your pipeline depends on surface form, not content.
   - **Fix:** Don't route off surface features (first character, byte length, raw header). Parse the input semantically before branching, and treat formatting as cosmetic in your routing.
3. **Reduced rule sensitivity** — Some rule changes don't reach the output. Either the pipeline is ignoring part of the rule, or some rule axes don't drive the decision.
   - **Fix:** Audit which parts of the rule your pipeline reads. If only some clauses drive the output, decide whether that's by design (skip the others) or a bug (add them to the prompt).

## Top fix

Set temperature=0 in your LLM calls and re-check. If your pipeline isn't LLM-backed, look for non-deterministic input (timestamps, randomized retrieval order, time-of-day code paths).

_Run with `--verbose` for per-axis sub-score detail and the per-family breakdown._
