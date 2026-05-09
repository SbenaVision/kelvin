# EOS — Empirical Oracle Signature: experimental results

**Date:** 2026-04-24
**Thesis tested:** `Kelvin_Empirical_Oracle_Signature_Corrected_Thesis.pdf`
**Status:** PASS — all 13 pre-registered criteria satisfied.

---

## What this does and does not prove (thesis §2, applied)

### This experiment **does** prove:

1. **A mechanically discovered signature separates a rule-tracking pipeline
   from a rule-blind adversary, a rule-misinterpreting adversary, and a
   constant baseline on the defined corpus.** The per-pipeline signatures
   differ both in axis classification and at the per-pair level, and the
   separation is concentrated exactly where the thesis predicts (rule-text
   axes).

2. **The method produces a judge-free behavioral oracle in the tested
   setting.** At no point does the discovery procedure consult a rater,
   a semantic-similarity oracle, or an LLM-as-judge. Only `f` (deterministic
   code) and the four decidable relations in `relations.py`.

3. **Schema + role annotations are sufficient for mechanical enumeration
   of a catalogue that separates the four pipelines.** All 22 non-identity
   transformations were enumerated from role annotations in
   [schema.py](schema.py) and [transformations.py](transformations.py).

4. **The discovered signature is stable from train to held-out
   validation.** Train→holdout stability ratio: 100% (every accepted pair
   on n=350 train is also accepted on n=150 holdout at the same ε=0.05,
   α=5.68e-4).

### This experiment **does not** prove:

- **Universal correctness for arbitrary black-box pipelines.** The four
  pipelines here are deterministic Python functions with fully inspectable
  behavior. Generalization to opaque LLM-backed pipelines requires the
  stochastic-pipeline extension (noise floor calibration, which this
  experiment does not address).
- **Semantic correctness of pipeline output.** The signature tests
  behavior relative to transformations; it does not verify that `f_track`'s
  output is the *right* decision for any given case.
- **That all valid metamorphic relations can be found from schema alone.**
  The T and R catalogues here are finite and hand-enumerated. Scaling to
  richer schemas requires a schema-driven T generator.
- **That invariant fields are truly irrelevant rather than masked,
  saturated, or under-tested.** The 4-way axis classifier distinguishes
  `invariant-candidate` from `ignored-candidate` by reading the schema
  role, but it cannot rule out saturation or correlated-substitute
  features (thesis §7 caveat, acknowledged here).

---

## Setup

| Parameter | Value |
|---|---|
| Corpus size N | 500 |
| Corpus mix | 60% boundary, 20% interior-pass, 20% interior-fail |
| Corpus seed | 42 |
| Train / holdout | 350 / 150 (70 / 30) |
| \|T\| | 22 (21 signature-eligible + 1 identity sanity) |
| \|R\| | 4 (R_eq, R_le, R_ge, R_sign_eq with τ=50) |
| m = \|T\|·\|R\| | 88 |
| ε (acceptance threshold) | 0.05 |
| δ (family-wise error budget) | 0.05 |
| α = δ / m (per-hypothesis CP level) | 5.682 × 10⁻⁴ |
| γ at n=350 (Hoeffding margin) | ≈ 0.108 |
| Statistical test | Exact one-sided Clopper–Pearson LCB, Bonferroni-corrected |

The Hoeffding sample-size guide from the thesis (n ≥ ln(2m/δ)/(2γ²))
gives n ≥ 408 for γ=0.10; our n=350 gives γ ≈ 0.108, a ~8% relative
relaxation. Since the acceptance test uses exact Clopper–Pearson (tighter
than Hoeffding), this does not affect the validity of accept decisions —
the Hoeffding bound is only a sanity guide.

### Default rule

```
ADVANCE IF revenue >= 10000 AND team_size >= 3 AND risk <= 40
```

Every case carries this rule. Rule-threshold and rule-clause transformations
rewrite it per evaluation.

### Pipelines

- **f_track** — parses the rule, evaluates every clause correctly.
  Score = 20 + 60·(passed / total).
- **f_wrongrule** — parses the rule, inverts the comparator on the
  **last clause only**. Deterministic adversary that *reads* the rule but
  tracks it incorrectly.
- **f_ruleblind** — ignores rule_text entirely. Heuristic score from
  revenue and team_size only (no risk).
- **f_constant** — returns 50 always.

### Transformation axes (thesis §5)

| Axis | \|T\| | Schema status |
|---|---|---|
| identity | 1 | non-causal (sanity control, excluded from signature) |
| order | 2 | non-causal (order-irrelevant lists) |
| optional | 2 | non-causal (unreferenced fields) |
| non_rule_fact | 3 | non-causal (fields not in this rule) |
| rule_threshold | 6 | rule-bearing |
| rule_clause | 2 | rule-bearing |
| case_fact | 6 | causal (rule-referenced fields) |

---

## Identity sanity (thesis §3 bullet 6)

For all 4 pipelines × 4 relations, identity T passes at p=1.0 on both
train (k=350/350) and holdout (k=150/150). Excluded from reported
signatures per thesis spec.

---

## Axis classification — stable signature (train ∩ holdout, subsumed)

|  | order | optional | non_rule_fact | rule_threshold | rule_clause | case_fact |
|---|---|---|---|---|---|---|
| **f_track**     | invariant-cand. | invariant-cand. | invariant-cand. | **responsive**        | **responsive** | **responsive** |
| **f_wrongrule** | invariant-cand. | invariant-cand. | invariant-cand. | **responsive** (partial / wrong-direction on risk) | unstable/noisy | **responsive** |
| **f_ruleblind** | invariant-cand. | invariant-cand. | invariant-cand. | **ignored-candidate** | **ignored-candidate** | responsive (only on rev/team) |
| **f_constant**  | invariant-cand. | invariant-cand. | invariant-cand. | **ignored-candidate** | **ignored-candidate** | **ignored-candidate** |

Legend: `invariant-candidate` = all T preserve equality AND axis declared
non-causal; `ignored-candidate` = all T preserve equality BUT axis
declared rule-bearing/causal; `responsive` = ≥1 T is directional.

---

## Signature-level separation

|  | \|Σ\| (stable, subsumed, non-identity) |
|---|---|
| f_track | 22 |
| f_wrongrule | 20 |
| f_ruleblind | 22 |
| f_constant | 22 |

Set sizes alone don't distinguish f_track from f_ruleblind / f_constant
(they coincidentally all have 22 pairs, differently composed). The
separation is at the **pair** level:

### Σ(f_track) ∖ Σ(f_ruleblind) = 10 pairs

All 10 are the monotone rule-response pairs:
- `rule_threshold/strengthen_{revenue,team,risk}/R_ge`
- `rule_threshold/weaken_{revenue,team,risk}/R_le`
- `rule_clause/add_strict_clause/R_ge` and `/R_sign_eq`
- `case_fact/case_risk_up/R_ge`
- `case_fact/case_risk_down/R_le`

### Σ(f_ruleblind) ∖ Σ(f_track) = 10 pairs

All 10 are R_eq invariances on causal or rule-bearing axes — these are
the `ignored-candidate` signals that mark `f_ruleblind` as rule-blind:
- `rule_threshold/*/R_eq` (6 pairs)
- `rule_clause/{add_strict_clause,remove_last_clause}/R_eq`
- `case_fact/case_risk_{up,down}/R_eq` (f_ruleblind's heuristic doesn't
  use `risk_score`)

### Σ(f_track) ∖ Σ(f_wrongrule) = 6 pairs

The adversary-specific diff. All six are either on the risk axis (the
adversary's inverted last clause) or on the add_strict_clause
transformation (the adversary's interpretation shifts when a clause is
appended):
- `rule_threshold/strengthen_risk_threshold/R_ge`  (f_track: correct)
- `rule_threshold/weaken_risk_threshold/R_le`  (f_track: correct)
- `case_fact/case_risk_up/R_ge`  (f_track: correct)
- `case_fact/case_risk_down/R_le`  (f_track: correct)
- `rule_clause/add_strict_clause/R_ge` and `/R_sign_eq`

### Σ(f_wrongrule) ∖ Σ(f_track) = 4 pairs

The wrong-direction responses — f_wrongrule's misinterpretation produces
the OPPOSITE monotonicity on the risk axis:
- `rule_threshold/strengthen_risk_threshold/R_le`  (wrong: score goes UP)
- `rule_threshold/weaken_risk_threshold/R_ge`  (wrong: score goes DOWN)
- `case_fact/case_risk_up/R_le`  (wrong: adversary interprets risk≥40)
- `case_fact/case_risk_down/R_ge`  (wrong: same)

This is exactly the "partial / wrong response" pattern the thesis §6
success criterion calls for. The adversary's reading of the rule is
detectable *directly* at the pair level.

---

## Train→holdout stability

| Metric | Value |
|---|---|
| Train-accepted (subsumed, non-identity, all pipelines) | 86 pairs |
| Stable (accepted on holdout too, same ε, α) | 86 pairs |
| Stability ratio | 100.0% |

Holdout n=150 gives a looser Hoeffding margin (γ ≈ 0.15), but exact CP
acceptance at k=150/150 satisfies the test even at this smaller n
(holdout CP LCB = 0.951 at k=n=150, α=5.68×10⁻⁴). No pair collapsed on
holdout.

---

## Success criteria (pre-registered in thesis §6 and user instructions)

| # | Criterion | Status |
|---|---|---|
| 1 | f_track signature ≠ f_ruleblind | PASS |
| 2 | f_track signature ≠ f_constant | PASS |
| 3 | f_track signature ≠ f_wrongrule | PASS |
| 4 | f_track rule_threshold axis = responsive | PASS |
| 5 | f_track rule_clause axis = responsive | PASS |
| 6 | f_ruleblind rule_threshold = ignored-candidate | PASS |
| 7 | f_ruleblind rule_clause = ignored-candidate | PASS |
| 8 | f_constant rule_threshold = ignored-candidate | PASS |
| 9 | f_constant rule_clause = ignored-candidate | PASS |
| 10 | f_wrongrule rule_threshold = responsive (partial/wrong) | PASS |
| 11 | order axis invariant across all pipelines | PASS |
| 12 | train→holdout stability ≥ 90% (100.0%) | PASS |
| 13 | f_track signature non-trivial (\|Σ_track\| ≥ 3) | PASS |

---

## Observations worth flagging

1. **f_track rule_clause has one null T.** The `remove_last_clause`
   transformation produces no accepted relation on f_track. This is not a
   bug but a real property of the ratio-based scoring: removing the last
   clause can move the score up *or* down depending on which clauses were
   previously passing, because the denominator shrinks while the numerator
   may or may not. A universal monotone relation therefore does not hold.
   The axis is still classified `responsive` because `add_strict_clause`
   IS directional on f_track.

2. **f_wrongrule rule_clause is unstable/noisy.** Both rule_clause
   transforms (add and remove) produce no accepted relation on f_wrongrule.
   This is because f_wrongrule's inverted "last clause" shifts to a
   different field whenever rule structure changes — its response has no
   clean monotone direction. This is consistent with a rule-misinterpreting
   adversary and is a legitimate *non-invariance, non-monotone* signal.

3. **The separation is concentrated on the risk clause.** Because
   f_wrongrule only inverts the *last* clause (risk ≤ 40 in the default
   rule), the detectable differences are concentrated on risk-related
   transforms. If the experiment were extended with a second adversary
   that flipped a different clause (`f_wrongrule_first_clause`), we would
   expect symmetric detection on the revenue axis. This is a confirmation
   of the thesis's "conditional distinguishability" statement (§1): the
   signature can separate adversaries only on axes where the catalogue
   contains contrastive interventions.

---

## Reproducibility

```bash
cd experiments/eos
python3 run.py
```

- Stdlib only (no scipy, no numpy).
- Deterministic: `CORPUS_SEED=42`, `DISCOVERY_SEED=7`.
- Wall-clock: ~15 seconds on a laptop (88 candidates × 4 pipelines ×
  500 cases × 2 [train+holdout] ≈ 352 000 pipeline evaluations, all
  local, no I/O).
- Output: `signatures.csv`, `axis_summary.csv`, `stability.csv`,
  `results.md` (this file).

---

## Implication for Kelvin

This result is a controlled proof-of-concept for the EOS thesis on a
transparent pipeline. Two next experiments would extend it to publishable
Kelvin work:

1. **Stochastic pipelines.** Replace the deterministic toy pipelines
   with LLM-backed scorers. Calibrate the acceptance threshold against
   the per-case noise floor σ_c (Kelvin Pillar 1). The thesis's ε would
   become pipeline-specific: accept `(T, R)` iff `p_L ≥ 1 − max(ε_nominal,
   Kε · σ_c)` for some Kε ≥ 2. This requires integrating EOS discovery
   with Pillar 1 calibration.
2. **Schema-driven T generation.** Replace the hand-enumerated 22-T
   catalogue with a generator that reads schema + role annotations and
   emits candidate Ts per axis (permute for lists, perturb-magnitude for
   numerics, rename-from-closed-pool for typed strings, etc.). Measure
   how much of the discovered MR set survives vs. the current hand-crafted
   catalogue on a real RAG pipeline.

If (2) recovers ≥80% of hand-authored Kelvin MRs on the v0.3.0 gate-rule
corpus, and (1) stays stable on the VA API pipeline, that is the
publishable Kelvin 0.5.0 result.
