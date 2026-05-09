# envelop — v0.4 prototype diagnosis

**Morning baseline:** seed
**Prototype canonical baseline:** seed
**Replays:** ['seed', 'seed', 'pre-seed', 'seed', 'seed']
**σ_c (noise floor):** 0.4
**Morning labeled-run sensitivity (gate_rule swap):** 1.000

## paragraph-level
- raw sensitivity (all perts):   0.21052631578947367
- raw sensitivity (delete only): 0.42857142857142855
- calibrated (all):              0.0
- calibrated (delete only):      0.04761904761904755

### Per-unit profile (delete-only above-noise)
- `p01`  raw=0.0  cal=0.000
- `p02`  raw=1.0  cal=—
- `p03`  raw=1.0  cal=—
- `p04`  raw=0.0  cal=0.000
- `p05`  raw=0.0  cal=0.000
- `p06`  raw=0.0  cal=0.000
- `p07`  raw=1.0  cal=—

**paragraph diagnosis:** Few or no unit deletions move the decision above noise — pipeline holds its decision regardless of which unit is removed.

