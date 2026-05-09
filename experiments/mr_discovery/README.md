# MR Discovery — Breakthrough-Formulation Proof Experiment

## Claim under test

For a pipeline `f: X → Y` with typed input schema, we can **automatically
discover metamorphic relations** — pairs `(T, R)` where `T` is an input
transformation and `R` is a decidable output relation such that
`R(f(x), f(Tx))` holds — without a human judge or ground-truth labels.

## Why this would be a breakthrough

A metamorphic relation in the classical MT literature is exactly the pair
`(T, R)`. Today Kelvin ships hand-authored `(T, R)` pairs per family
(Pillar 1 invariance = R=equality; mechanical sensitivity = R=monotone).
If we can *discover* the pair empirically from a schema, we no longer need
to hand-author families per pipeline. The oracle becomes `R` itself, which
is mechanically decidable — no judge, no labels.

## Why this experiment can actually *prove* it

Running discovery on a real opaque pipeline tells you nothing, because you
don't know which MRs *should* hold. You can't measure precision or recall.

This experiment uses a **transparent toy pipeline with a known rule set**,
so the ground-truth MR set is derivable by inspection. Then we run the
discovery procedure and measure:

- **Recall**: fraction of ground-truth MRs recovered.
- **Precision**: fraction of discovered MRs that are genuine (not
  bug-symmetries or statistical accidents).
- **Bug-symmetry rejection rate**: the pipeline *deliberately ignores* one
  input field (`description`). Any T on that field yields R=equality
  trivially — that is an ignore-the-input bug, not a conservation law. The
  discriminator must flag it.
- **Regression catch rate**: inject a known bug into the pipeline; measure
  how often the discovered MRs fire on the buggy pipeline vs. the correct
  one.

## The pipeline (f)

A rule-based scorer for venture-assessment-like inputs. Schema:

```
{
  "stage":           enum {idea, building, first_users},
  "revenue_monthly": int ≥ 0,
  "team_size":       int ≥ 1,
  "founders":        list of {name: str, experience_years: int},
  "risks":           list of str,
  "description":     str,     # DELIBERATELY IGNORED — bug-symmetry trap
}
```

Score computation (see `pipeline.py` for exact rules):
- stage weight + revenue tier + team size bonus + avg founder experience
  − risks penalty.
- `description` enters the function signature but is never read — this is
  the built-in bug-symmetry trap.

## The candidate T catalogue (`transformations.py`)

Schema-derived transformations:
- `T_permute(<list_field>)`        — permute rows of a list field
- `T_rename(<entity.str_field>)`   — substitute semantically-equivalent strings
- `T_append(description, ...)`     — extend a string field
- `T_scale(<numeric_field>, k)`    — multiply a numeric field by k
- `T_delta(<numeric_field>, d)`    — add d to a numeric field
- `T_promote(stage)`               — advance stage to next ordinal value
- `T_demote(stage)`                — regress stage to previous ordinal value
- `T_add_item(<list_field>)`       — append a synthetic item
- `T_drop_item(<list_field>)`      — drop last item

## The candidate R catalogue (`relations.py`)

Decidable output relations:
- `R_eq`:        y1 == y2
- `R_le`:        y1 ≤ y2  (monotone-up)
- `R_ge`:        y1 ≥ y2  (monotone-down)
- `R_abs_le(δ)`: |y1 − y2| ≤ δ  (bounded)
- `R_sign_eq(τ)`: sign(y1 − τ) == sign(y2 − τ)  (decision-preserving)

## The discovery procedure

1. Generate corpus `X` of N=200 synthetic inputs.
2. For each `(T, R)` in the cross-product of catalogues: compute
   `hold_rate = |{x ∈ X : R(f(x), f(Tx))}| / N`.
3. Keep pairs with `hold_rate ≥ 0.95` and lower-bound Wilson 95% CI ≥ 0.90.
4. **Bug-symmetry filter**: for each kept `(T, R_eq)`, check that some
   other transformation `T'` on the *same input axis* violates `R_eq` on
   the same corpus. If no such `T'` exists in the candidate set → the axis
   is ignored by f; reject.

## The regression catch test

1. Define `f_bug`: same pipeline but with `stage` weight function
   incorrectly flipped (`idea=30, first_users=10`).
2. Re-run discovered MRs against `f_bug`.
3. Count: for each MR, fraction of inputs where `R(f_bug(x), f_bug(Tx))`
   is violated.
4. Success criterion: ≥1 of the stage-related MRs detects the bug at
   ≥50% firing rate.

## Success criteria (pre-registered)

- **Recall ≥ 0.80** against the ground-truth MR set.
- **Precision ≥ 0.80** (after bug-symmetry filter).
- **Bug-symmetry rejection**: `(T=T_append, description, R_eq)` is
  discovered *before* filter, rejected *after* filter.
- **Regression catch**: injected bug detected by at least one discovered
  MR with ≥50% firing rate.

All four must hold for the experiment to prove the claim.

## Files

- `pipeline.py` — toy pipeline + buggy variant
- `transformations.py` — T catalogue
- `relations.py` — R catalogue
- `corpus.py` — synthetic input generator
- `ground_truth.py` — enumerated ground-truth MRs (for recall/precision)
- `discover.py` — discovery loop
- `bug_filter.py` — bug-symmetry discriminator
- `regression.py` — regression catch test
- `run.py` — orchestrator
- `results.md` — populated after run
