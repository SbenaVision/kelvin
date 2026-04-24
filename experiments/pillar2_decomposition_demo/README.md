# Pillar 2 decomposition demo — grounded rule-based pipeline

Paper-ready Pillar 2 empirical demonstration for v0.3.0. Runs the new
`swap_condition` generator on the 6-case whitepaper tier3 corpus
(envelop, freakinggenius, artisanflow, meridian, northpass, rhodium)
against the deterministic rule-based grounded pipeline at
`experiments/tier3/pipelines/grounded.py`. Zero LLM spend.

## Reproduce

```
cd kelvin_repo
pip install -e .
cat > /tmp/p2/kelvin.yaml <<EOF
run: python3 experiments/tier3/pipelines/grounded.py --input {input} --output {output}
cases: cases/
decision_field: stage_assessment
governing_types: [gate_rule]
seed: 0
counterfactual_swap:
  enabled: true
EOF
cd /tmp/p2 && kelvin check
```

## Numbers

| Metric | Value |
|---|---:|
| Inv_raw | 0.852 |
| Sens_raw (swap_content) | **0.667** |
| Sens(swap_condition) | **0.000** |
| Content_Effect | **0.667** |
| K_raw | 0.481 |
| Invariance samples | 54 (9 per case × 6 cases) |
| Swap samples | 6 (1 gate_rule swap per case × 6 cases) |
| swap_condition samples | 6 (1 per case where peer with matching state phrase + different condition list existed) |

## Interpretation

- **Sens(swap_content) = 0.667.** Swapping the entire gate_rule unit
  from a peer moves the grounded pipeline's decision in 4 of 6 cases.
- **Sens(swap_condition) = 0.000.** Swapping only the condition list —
  "requires: A, B, C" — while preserving the state phrase ("All
  conditions are met" etc.) and details from the focal case produces
  zero change in the grounded pipeline's decision across all 6 cases.
- **Content_Effect = 0.667.** The entire raw-swap sensitivity on this
  pipeline is Content_Effect. The grounded pipeline's routing keys off
  the state phrase and content tokens (ARR, annual revenue, paying
  subscribers) — never the condition list itself. This is precisely
  the failure mode §3.3 flagged: v0.2 raw swap sensitivity conflates
  rule-tracking with content-leakage. Pillar 2 separates them cleanly.

## Clean-parse rate

All 6 cases parsed successfully against the
`_GATE_RULE_RE` regex and a known state phrase. **Clean-parse rate:
6/6 = 100%**. Well above the FALLBACKS.md Tier 1 threshold of 80%.

## Relationship to VA corpus

The VA API tryout corpus (8 cases) uses `money` and `alternative` as
governing types, which are plain descriptive prose without the
"requires: …" / state phrase / details structure. `swap_condition`
correctly produces 0 perturbations there — clean-parse rate 0% — and
aggregation sets sensitivity_content / sensitivity_condition /
content_effect to None. Pillar 2 is a corpus-specific diagnostic;
its applicability depends on the governing unit having an
identifiable condition-vs-state partition.

## Artifacts

Full run output under this directory:
- `report.json` — run-level with decomposition fields populated
- `<case>/report.json` — per-case reports
- `<case>/baseline/` and `<case>/perturbations/` — inputs + outputs
