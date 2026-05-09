# readyrounds — v0.4 prototype diagnosis

**Morning baseline:** idea
**Prototype canonical baseline:** idea
**Replays:** ['idea', 'idea', 'idea', 'idea', 'idea']
**σ_c (noise floor):** 0.0
**Morning labeled-run sensitivity (gate_rule swap):** 0.000

## paragraph-level
- raw sensitivity (all perts):   0.058823529411764705
- raw sensitivity (delete only): 0.14285714285714285
- calibrated (all):              0.058823529411764705
- calibrated (delete only):      0.14285714285714285

### Per-unit profile (delete-only above-noise)
- `p05`  raw=1.0  cal=1.000
- `p01`  raw=0.0  cal=0.000
- `p02`  raw=0.0  cal=0.000
- `p03`  raw=0.0  cal=0.000
- `p04`  raw=0.0  cal=0.000
- `p06`  raw=0.0  cal=0.000
- `p07`  raw=0.0  cal=0.000

**paragraph diagnosis:** Few or no unit deletions move the decision above noise — pipeline holds its decision regardless of which unit is removed.
**Highest above-noise causal effect on stage_assessment:** `p05`

