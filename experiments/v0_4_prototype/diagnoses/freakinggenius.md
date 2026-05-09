# freakinggenius — v0.4 prototype diagnosis

**Morning baseline:** pre-seed
**Prototype canonical baseline:** idea
**Replays:** ['idea', 'idea', 'idea', 'pre-seed', 'pre-seed']
**σ_c (noise floor):** 0.6
**Morning labeled-run sensitivity (gate_rule swap):** 1.000

## paragraph-level
- raw sensitivity (all perts):   0.9047619047619048
- raw sensitivity (delete only): 0.7142857142857143
- calibrated (all):              None
- calibrated (delete only):      None

### Per-unit profile (delete-only above-noise)
- `p01`  raw=1.0  cal=—
- `p02`  raw=1.0  cal=—
- `p03`  raw=1.0  cal=—
- `p04`  raw=0.0  cal=0.000
- `p05`  raw=0.0  cal=0.000
- `p06`  raw=1.0  cal=—
- `p07`  raw=1.0  cal=—

**paragraph diagnosis:** Few or no unit deletions move the decision above noise — pipeline holds its decision regardless of which unit is removed.

