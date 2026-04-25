# Phase 2 scope additions (locked before Phase 2 starts)

Phase 2 is the practitioner reporter / findings / recommendations /
CLI work. The base scope was defined in
`docs/V0.4.0_BUILD_PLAN.md` (commit `9b605fa`).

This document captures **additions made to Phase 2 scope after
Phase 1 finished**, so the Phase 2 prompt doesn't need to re-derive
them.

## Addition: silent-pillar handling

### What triggered this addition

The Phase 1 Envelop run (commit `e20cabb`) produced maturity 10/10 /
Production-ready, BUT Pillar 2 silently failed to fire (Envelop's
gate_rule format doesn't match Kelvin's expected pattern). This is
exactly the false-positive verdict the v0.4 surface is supposed to
catch — a clean score on a pipeline that wasn't fully measured.

### Phase 2 reporter requirements

These are MANDATORY in Phase 2, not deferred:

1. **Verdict can NEVER be "Production-ready" when a standard pillar
   is silent.**
   - "Standard pillar" = Pillar 1 (noise floor / drift), Pillar 2
     (counterfactual swap), Pillar 3 (invariance + mechanical
     sensitivity).
   - "Silent" = the pillar's primary metric is `None` because no
     contributing perturbations fired (format mismatch, missing axis
     data, disabled family in `kelvin.yaml`, etc.).
   - When any standard pillar is silent, the top-line verdict
     becomes a distinct state: **"Partially measured"** (working
     name; final wording in Phase 2 reporter design).
   - This applies regardless of how clean the measured axes look.

2. **The default reporter output must surface which pillar was
   silent and why.**
   - Format mismatch (gate_rule doesn't match `swap_condition`
     pattern) → "Pillar 2: gate_rule format not recognized; install
     a custom grammar or restructure the rule."
   - Family disabled in config → "Pillar 3 family X disabled in
     `kelvin.yaml`; enable for full coverage."
   - No contributing perturbations (e.g., insufficient
     `state_phrase` matches in the corpus) → "Pillar 2: no
     swap_condition perturbations fired; the corpus may need more
     paired cases."

3. **Numeric score is flagged or withheld on partial coverage.**
   - In `--verbose`, when any standard pillar is silent: either
     prefix the numeric with a banner ("Partial coverage — pillar X
     silent; numeric is not directly comparable to pipelines with
     full coverage"), or withhold it entirely.
   - Do NOT compute a top-line number on partial coverage and present
     it as if it were complete.

### Why this is Phase 2, not v0.5

This is the user-facing **symptom containment**. The actual fix to
Pillar 2's format coverage (generalizing `swap_condition`) is a
v0.5 backlog item (B-3 promoted to high priority). But while B-3 is
pending, ANY user pipeline with a non-canonical gate_rule format
will hit the same Envelop trap: silently-skipped pillar producing a
falsely-clean score. The Phase 2 reporter must close that gap from
day one.

### Implementation surface

- New field on `MaturityScore`: `pillar_coverage: dict[str, bool]`
  with keys "pillar_1" / "pillar_2" / "pillar_3" → True if measured,
  False if silent.
- `compute_maturity` populates `pillar_coverage` from the same fields
  it already reads:
  - Pillar 1 silent iff `noise_floor_eta` is `None` (and run had
    `noise_floor.enabled: true`).
  - Pillar 2 silent iff `sensitivity_condition` is `None` AND
    `swap_condition` is enabled.
  - Pillar 3 silent iff `mechanical_sensitivity` is `None` AND
    `intra_slot.enabled: true`.
- Verdict resolution: if any of these is `False`, verdict becomes
  "Partially measured" regardless of numeric.

### Test requirements

- `tests/test_score.py::test_silent_pillar_2_blocks_production_ready`
  — synthetic RunScores with `sensitivity_condition=None` produces
  verdict "Partially measured" even when other axes are clean.
- `tests/test_score.py::test_silent_pillar_1_blocks_production_ready`
  — same for missing noise floor.
- `tests/test_reporters_practitioner.py::test_partial_coverage_banner`
  — golden-file the practitioner output in this state.

### Cross-reference

- v0.5 backlog: B-3 (Pillar 2 swap_condition format coverage).
- Phase 1 deliverable: `experiments/v040_phase1_calibration/ENVELOP_INTERPRETATION.md`.

---

This addition is locked in. The Phase 2 prompt should reference this
file rather than re-derive the requirements.
