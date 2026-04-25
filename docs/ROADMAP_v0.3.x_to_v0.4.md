# Kelvin Roadmap — completing v0.3.x and shipping v0.4

**Author:** plan drafted 2026-04-25 by Claude
**Status:** proposed — awaiting SBA review
**Scope:** the next ~6–10 weeks of Kelvin work, ending with a tagged v0.4.0 on PyPI

## Where we are

- `main` is at **v0.3.0** (PyPI published 2026-04-24). Three pillars shipped.
- `[Unreleased]` in CHANGELOG is empty.
- Two completed experiments live on the `claude/elegant-dijkstra-ef94ef` worktree:
  - `experiments/eos_v2_1/` — broader product / behavioral-audit catalogue (23 T's, noise-aware relations, K_D=3 stability). PASS, 8/8 criteria.
  - `experiments/eos_v2_2_certification/` — narrow theorem-aligned certification (M=8, raw relations, λ=0.08, n_eff=600). THEOREM-ALIGNED.
- The **EOS Consistency and Catalogue-Relative Separation** paper (Shahar Ben Ami, DRAFT) is committed at `experiments/eos_v2_2_certification/eos_theorem_DRAFT_for_review.pdf` with a 1-page certification brief alongside.

The two open strands are: (1) ship the EOS work as a real Kelvin feature, and (2) close out small lingering items from v0.3 before doing so.

## Two-track plan

```
v0.3.x  (patches; 2–3 weeks)             →  housekeeping + statistical rigor
   v0.3.1   --version + CLI polish
   v0.3.2   bootstrap CIs on σ_c, Inv, Sens
   v0.3.3   applicability + n_eff in core
   v0.3.4   whitepaper §EOS pointer + small bugs

v0.4.0  (minor; 4–6 weeks)               →  EOS as a first-class Kelvin feature
   sealed catalogue file format
   `kelvin eos` subcommand
   CP LCB/UCB + Bonferroni in core
   active-set predicates in perturbation API
   `kelvin eos seal` / `kelvin eos verify`
   signature drift detection (between runs)

PARALLEL  (research, ungated by v0.4)    →  LLM-backed EOS run
   Apply v2.2 sealed catalogue to a real LLM-backed pipeline
   Same theorem alignment + paper appendix
```

---

## v0.3.x patch sequence

Each patch is **byte-compatible** with v0.3.0 on deterministic pipelines. Existing `kelvin.yaml` configs continue to work unchanged.

### v0.3.1 — `--version` flag + CLI polish (1–2 days)

**Why now:** explicitly deferred from v0.3.0; tiny but blocks scriptable pipelines.

- `kelvin --version` prints `kelvin-eval x.y.z`.
- Improved error messages on sealed-config issues (clearer where the violation is).
- `kelvin --help` rewrite: group flags by phase (config / run / report).
- One-line bug fixes from VA-API real-runs (any caught between v0.3.0 ship and now).

**Acceptance:** `kelvin --version` works; `--help` is grouped; CHANGELOG updated; tag-and-ship.

### v0.3.2 — Bootstrap CIs on σ_c, Inv, Sens, K_cal (5–7 days)

**Why now:** top-1 roadmap item from earlier conversations. Statistical rigor is the obvious next quality bump for a numerically-reported tool. Complements (does not break) existing point estimates.

- For each per-case σ_c: 1000-bootstrap 95% CI on the median / mean of pairwise replay distances.
- For Inv, Sens (and Inv_cal, Sens_cal): paired bootstrap CI over cases.
- For K_cal: derived CI via bootstrap on the same draws.
- Reports gain `..._ci_low` / `..._ci_high` fields where the corresponding scalar exists.
- **Pre-committed knob:** `cfg.bootstrap.enabled` (default `true`) and `cfg.bootstrap.n_samples` (default 1000).
- Whitepaper §5.3 updated to report CI bands on the Pillar 1 numbers.

**Acceptance:** all existing point estimates have CI siblings; reports validated against known closed-form CIs on toy cases; runtime overhead < 10% on the 8-case VA corpus.

### v0.3.3 — Applicability + `n_eff` in core (4–6 days)

**Why now:** the EOS work taught us that applicability filtering matters. v0.3 reports raw `N` (corpus size) but doesn't expose `n_eff` per (T, R) pair. EOS's discipline of dropping non-applicable cases instead of treating them as holds is the right default for everything Kelvin does.

- Add `is_applicable(x: Input) → bool` to the perturbation generator API.
- Each generator declares its applicability predicate (already implicit; now explicit).
- Reports include `n_eff_<family>` per family per case.
- Family-level aggregates filter non-applicable cases before computing rates.
- Backwards-compat: families that don't implement `is_applicable` get a default `lambda x: True` (no behavior change).
- Migration note in CHANGELOG for plugin authors.

**Acceptance:** existing v0.3.0 runs produce identical scalar outputs; new `n_eff_*` fields appear in `report.json`; one perturbation family (e.g., `swap_condition`) demonstrably uses applicability filtering.

### v0.3.4 — Whitepaper §EOS pointer + bug-fix flush (2–3 days)

**Why now:** before v0.4 ships EOS as a feature, the whitepaper should at minimum reference the theorem paper and the v2.2 certification run.

- Whitepaper §6 (limitations) gains: "EOS as a separate finite-sample theorem; see `eos_theorem_DRAFT_for_review.pdf`."
- Whitepaper §7 (future work) gains: "v0.4 ships EOS as a first-class subcommand."
- Any bug fixes accumulated since v0.3.0.
- Minor doc polish.

**Acceptance:** doc-only patch; whitepaper rebuilds; no API change.

**End of v0.3.x.** Tag v0.3.4, ship to PyPI, archive the patch branch.

---

## v0.4.0 — EOS as a first-class Kelvin feature (4–6 weeks)

**Theme.** "Empirical Oracle Signatures with finite-sample guarantees."
**Tagline.** Move EOS from `experiments/` into the product surface, with sealing discipline enforced by the tool.

### Concrete deliverables

#### 1. Sealed catalogue file format (`catalogue.yaml`)

```yaml
# kelvin/catalogues/example.yaml
catalogue:
  schema:
    fields:
      revenue_monthly: {role: causal_field}
      team_size:       {role: causal_field}
      risk_score:      {role: causal_field}
      founders:        {role: order_irrelevant_list}
      description:     {role: optional_field}
      rule_text:       {role: rule_text}
  probes:
    - id: 1
      transformation: strengthen_risk_threshold
      relation: R_down
      delta_dir: 4
      active_set: "30 < risk_score <= 40"
    # ... up to M items
  parameters:
    epsilon: 0.10
    delta:   0.05
    lambda:  0.08
    n_eff_min: 600
    bonferroni: true
seal:
  sha256: <auto-computed>
  computed_at: <ISO-8601>
```

The catalogue file IS the seal. Editing invalidates it.

#### 2. `kelvin eos` subcommand

```bash
# Compute and write seal (Commit A equivalent)
kelvin eos seal --catalogue catalogues/my-catalogue.yaml

# Run all pipelines × probes, produce signatures.csv + theorem_check.json
kelvin eos run --catalogue catalogues/my-catalogue.yaml --pipelines pipelines.yaml --output runs/eos-run-2026-04-25/

# Compare two runs for drift
kelvin eos diff runs/eos-run-2026-04-25/ runs/eos-run-2026-05-15/
```

#### 3. CP LCB/UCB + Bonferroni built into core

Move from `experiments/.../cp_lcb.py` to `src/kelvin/stats/cp.py`. Public API:

```python
from kelvin.stats import cp_lcb, cp_ucb, accept_high, accept_low
```

These are the same exact-stdlib implementations from the experiments — they just become first-class library code.

#### 4. Active-set predicates in perturbation API

Already started in v0.3.3. v0.4 makes the predicate signature theorem-ready:

```python
class Probe:
    transformation: Callable[[Input], Input]
    relation: Callable[[Y, Y], bool]   # raw relation, no x dependence
    active_set: Callable[[Input], bool]  # input/rule-semantic
```

#### 5. Sealing discipline tooling

- `kelvin eos seal` computes sha256 over the catalogue + recorded files.
- `kelvin eos verify` re-computes and compares to recorded hash; non-zero exit code on mismatch.
- `kelvin eos run` blocks if seal is invalid (gateable with `--unsafe-no-seal-check` for dev).
- All output artifacts include the seal sha256 in column 1 (matches the experiment convention).

#### 6. Drift detection (`kelvin eos diff`)

Given two `signatures.csv` runs against the same sealed catalogue:
- Per-probe CI overlap analysis.
- Set-difference of accepted (T, R) pairs.
- Output Markdown table flagging movements, regressions, new accepts.

#### 7. Documentation

- New whitepaper section §8 "Empirical Oracle Signatures": references theorem PDF, summarizes v2.2 run, provides usage examples.
- New `docs/eos_tutorial.md` walking through a small example end-to-end.
- `docs/eos_theorem_DRAFT_for_review.pdf` moves to `docs/papers/`.
- README gains a "Two-track positioning" callout: theorem-certified core + behavioral audit engine.

### Out of v0.4 scope (saved for v0.5+)

- **Noise-aware EOS / Theorem 4.** Requires a calibration object with bounded η. Defer.
- **LLM-backed product validation.** Run as research experiment in parallel; not part of the v0.4 ship.
- **Schema-inferred typing.** Lift schema field roles from existing typed schemas (e.g., Pydantic). v0.5.
- **Auto-discovery of T.** Generate transformations from schema annotations. v0.5+.

### v0.4 ship gates

1. ✅ All v0.3.x patches landed and tagged.
2. ✅ EOS subcommand parses sealed catalogues and runs against the existing 5 pipelines.
3. ✅ `signatures.csv` + `theorem_check.json` produced; same format as the experiment.
4. ✅ All v0.3 acceptance tests pass (no regression).
5. ✅ TestPyPI release validated; then PyPI.
6. ✅ Whitepaper §8 + tutorial committed.
7. ✅ `FALLBACKS.md` updated with the v0.4 demote ladder (in case anything needs to be deferred mid-stream).

### v0.4 sequencing (4 phases)

| Phase | Duration | Output |
|---|---|---|
| **A.** Catalogue language | 1 week | `catalogue.yaml` parser, schema validator, sha256 sealer |
| **B.** Core stats + active-set API | 1 week | `kelvin.stats.cp`, finalized `Probe` API, regression tests |
| **C.** `kelvin eos` subcommand | 2 weeks | `seal`, `run`, `verify`, `diff` plus CSV/JSON outputs |
| **D.** Docs + ship | 1 week | whitepaper §8, tutorial, TestPyPI → PyPI |

Each phase ships behind a feature flag (`kelvin eos --experimental` initially), promoted to stable at end of phase D.

---

## Parallel research track — LLM-backed EOS validation

**Goal.** Run the v2.2 sealed catalogue (or a small extension) against a real LLM-backed RAG pipeline to validate that the theorem-alignment holds under genuine model stochasticity (not injected jitter).

**Status.** Sealed catalogue exists; need an LLM target.

**Ungated.** This experiment can run in parallel with v0.4 development; it does NOT gate the v0.4 ship.

**Plan sketch:**

1. Pick an LLM-backed pipeline (e.g., a small RAG over the Envelop venture corpus with rule-text grounding).
2. Implement 5 adversaries against that pipeline: f_track (correct prompt), f_ruleblind (rule text stripped from prompt), f_constant (always returns fixed score), f_wrongstatic (one clause inverted in prompt), f_wrongstochastic (paired clause-drop with p_attack=0.50).
3. Use the v2.2 catalogue as-is or with one small extension for the LLM-specific input schema.
4. Run with K=20 baseline replays + 600 active samples per probe per pipeline.
5. Report theorem-alignment (T2 + T3) with the same wording discipline as v2.2.
6. Add as a paper appendix or as a separate companion paper.

**Cost estimate:** at Haiku-tier prices, ~5 pipelines × 8 probes × 600 × 2 calls ≈ 48k API calls ≈ $50–100. Cheap.

**Wall-clock:** 1–2 weeks once an LLM target is selected.

---

## Out of scope / v0.5+

- **Noise-aware EOS theorem-aligned run.** Theorem 4 requires bounded plug-in error η, which we don't currently have machinery for. v0.5.
- **Schema-inferred T-catalogue.** Auto-generate transformations from typed schema annotations. v0.5+.
- **Symmetry-discovery research track.** Earlier-discussed "auto-discover MRs" thread. v0.6+ research.
- **Rater-validated rhetorical families.** Cut from v0.3 per FALLBACKS.md; not coming back.
- **Public LLM-judge integration.** Out of scope for Kelvin (judge-free is a load-bearing claim).

---

## Summary

The next 6–10 weeks:

1. **v0.3.1 → v0.3.4** (housekeeping + bootstrap CIs + applicability + doc polish). 2–3 weeks.
2. **v0.4.0** (EOS as a first-class Kelvin feature with sealing discipline). 4–6 weeks.
3. **In parallel:** LLM-backed EOS validation experiment for a paper appendix.

Both v0.3.x and v0.4.0 ship under the existing seal-then-adversary discipline. v0.4 makes that discipline a tool feature, not just an experiment convention.

Open questions for SBA before kickoff:
- Confirm the v0.3.x patch order (1 → 2 → 3 → 4)? Bootstrap CIs (v0.3.2) is the only non-trivial one.
- Confirm v0.4 scope (six deliverables above)? Anything to swap or cut?
- LLM-backed run: do you have a target pipeline in mind, or should I propose one?
- TestPyPI for v0.4, or straight to PyPI like v0.3?
