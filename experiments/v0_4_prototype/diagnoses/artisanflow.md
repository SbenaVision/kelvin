# artisanflow — v0.4 prototype diagnosis

**Morning baseline:** seed
**Prototype canonical baseline:** growth
**Replays:** ['growth', 'growth', 'growth', 'growth', 'seed']
**σ_c (noise floor):** 0.4
**Morning labeled-run sensitivity (gate_rule swap):** 1.000

## paragraph-level
- raw sensitivity (all perts):   0.36363636363636365
- raw sensitivity (delete only): 0.2857142857142857
- calibrated (all):              0.0
- calibrated (delete only):      0.0

### Per-unit profile (delete-only above-noise)
- `p01`  raw=0.0  cal=0.000
- `p02`  raw=0.0  cal=0.000
- `p03`  raw=1.0  cal=—
- `p04`  raw=0.0  cal=0.000
- `p05`  raw=0.0  cal=0.000
- `p06`  raw=1.0  cal=—
- `p07`  raw=0.0  cal=0.000

**paragraph diagnosis:** Few or no unit deletions move the decision above noise — pipeline holds its decision regardless of which unit is removed.

## sentence-level
- raw sensitivity (all perts):   0.2909090909090909
- raw sensitivity (delete only): 0.2916666666666667
- calibrated (all):              0.0
- calibrated (delete only):      0.0

### Per-unit profile (delete-only above-noise)
- `s01`  raw=0.0  cal=0.000
- `s02`  raw=0.0  cal=0.000
- `s03`  raw=0.0  cal=0.000
- `s04`  raw=0.0  cal=0.000
- `s05`  raw=1.0  cal=—
- `s06`  raw=1.0  cal=—
- `s07`  raw=1.0  cal=—
- `s08`  raw=1.0  cal=—
- `s09`  raw=1.0  cal=—
- `s10`  raw=0.0  cal=0.000
- `s11`  raw=0.0  cal=0.000
- `s12`  raw=0.0  cal=0.000
- `s13`  raw=1.0  cal=—
- `s14`  raw=0.0  cal=0.000
- `s15`  raw=0.0  cal=0.000
- `s16`  raw=1.0  cal=—
- `s17`  raw=0.0  cal=0.000
- `s18`  raw=0.0  cal=0.000
- `s19`  raw=0.0  cal=0.000
- `s20`  raw=0.0  cal=0.000
- `s21`  raw=0.0  cal=0.000
- `s22`  raw=0.0  cal=0.000
- `s23`  raw=0.0  cal=0.000
- `s24`  raw=0.0  cal=0.000

**sentence diagnosis:** Few or no unit deletions move the decision above noise — pipeline holds its decision regardless of which unit is removed.

