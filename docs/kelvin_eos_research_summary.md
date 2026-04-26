# Kelvin — Reviewer Overview

*A self-contained briefing for someone who has not read the code, the whitepaper, or any prior context. Version current as of v0.3.0 (April 24, 2026).*

---

## 1. What Kelvin is

**Bottom line.** Kelvin is a measurement tool that asks one question of an AI pipeline: *does the pipeline's answer change only when the parts of the input that should determine the answer change?* It produces a numeric score from 0 to 2, where lower means the pipeline is better anchored to its evidence. It does this without any human-labeled "correct" answers, without a second AI model acting as a judge, and without modifying the pipeline being tested.

**The problem it tries to solve.** Most evaluations of retrieval-augmented generation (RAG) pipelines — systems that look up information from a corpus and use a language model to produce a structured decision — fall into two camps. The first camp uses labeled test sets: a human writes the right answer for each case, and the pipeline's accuracy is measured against the labels. This is expensive, the labels go stale every time the prompt or model changes, and the labels themselves can be wrong. The second camp uses an LLM-as-judge: a second language model rates whether the answer looks correct. This is cheaper but inherits whatever biases the judge model has, and the judge can be wrong in correlated ways with the system being judged. Kelvin sits outside both camps. It produces a *diagnostic* — not a measure of whether an answer is true, but a measure of whether the pipeline is reading the evidence that should determine the answer.

**The core method.** Kelvin treats a corpus as a list of typed units (a unit is a section of text with a declared role, such as "this paragraph is the gate rule," "this paragraph is the team description"). It then makes two kinds of changes to the input. **Invariance perturbations** rearrange or pad the corpus in ways that leave the decision-relevant content unchanged — for example, reordering sections, or adding sections from a different case. The output is expected to stay the same. **Sensitivity perturbations** replace a *governing unit* — a section that carries the rule the decision is supposed to follow — with a different one. The output is expected to change. A pipeline that scores well on both axes is reading its evidence; one that scores well on only one is either ignoring evidence (high invariance, low sensitivity — the trivial case is a pipeline that always returns the same answer) or reacting to surface presentation (low invariance, high sensitivity). The pair is the central idea: neither axis alone separates a grounded pipeline from a degenerate one.

**Where Kelvin sits in a three-layer architecture.** What ships today (v0.3.0) is a measurement layer **scoped to typed-markdown corpora with user-declared `governing_types`** — a response-geometry vector built from invariance, sensitivity, noise floor, decomposition, and per-family scores. The next release (v0.4) is the actual breakthrough: it expands the measurement layer's input domain so that any pipeline taking text-like input and emitting a structured decision can be graded, with no pre-declared typing required and the per-type sensitivity profile *itself* revealing which input types the pipeline treats as governing. A **maturity grade** (v0.5) turns the resulting vector into an ordinal verdict against a published rubric ("this pipeline is at Maturity 3 / 5: stable but content-leaky — fix the rule-tracking before promoting"). An **EOS certification layer** (v1.0) attaches finite-sample statistical guarantees to the grade for audiences that need defensible published claims. §8 lays out the layering and roadmap in full. The order is deliberate: each layer requires the one below it to be useful, and the broadest input domain belongs at the bottom of the stack.

---

## 2. Current version (v0.3.0)

**Release.** Shipped April 24, 2026. PyPI package `kelvin-eval`. Install with:

```bash
pip install kelvin-eval
```

The CLI command is `kelvin check`. The current code lives at `github.com/SbenaVision/kelvin`.

### The three pillars

v0.3.0 ships three additions to the v0.2 measurement framework. All three are opt-in via configuration flags, so a v0.2 setup keeps producing identical output until the user enables them.

**Pillar 1 — Noise-floor calibration (`K_cal`).** Language-model pipelines have inherent randomness: re-running the same input may produce different decisions even with no perturbation. Pillar 1 quantifies this by replaying each baseline several times and computing per-pipeline stochasticity `η` (the average decision instability across replays). Invariance and sensitivity scores are then normalized: a Kelvin score that beats the noise floor is real evidence; one that doesn't is reported as `None` rather than a false signal. A degenerate constant-output pipeline preserves the analytical prediction `K_cal = 1.000` exactly.

**Pillar 2 — Counterfactual-controlled swap decomposition.** The v0.2 swap operator replaced an entire governing unit (e.g., a whole gate rule) with a peer's. This conflated two effects: the *rule effect* (decision moves because the criteria changed) and the *content effect* (decision moves because surface tokens like dollar amounts or company names changed). Pillar 2 introduces `swap_condition`, which edits *only* the condition clause of a gate rule while preserving the focal case's state phrase (e.g., "All conditions are met") and surrounding facts. Aggregate raw swap sensitivity is then decomposed: `Sens(swap_content) = Rule_Effect + Content_Effect + ε`. A pipeline that genuinely tracks the rule will show high `Sens(swap_condition)`; a pipeline that reacts only to surface tokens will show high `Content_Effect`.

**Pillar 3 — Eleven rule-based perturbation families.** Eleven new generators that probe behaviors the v0.2 four-family suite missed. Originally planned as rater-validated rhetorical probes, the design was reframed mid-release to families whose invariants hold *by construction* — a reviewer can verify the structural rule rather than trusting a labeling study.

### Full perturbation family list (16 generators)

**v0.2 inter-slot families** (operate at the section level)

1. **`reorder`** — permute the order of units in the case without changing their content. Tests presentation-position invariance.
2. **`pad_length`** — insert 2–4 neutral `## Reference Note` filler sections from a fixed decision-neutral bank. Tests length invariance independent of content.
3. **`pad_content`** — insert typed units sampled from peer cases in the same run. Tests robustness to distractor evidence about other entities.
4. **`swap`** — replace one unit of a declared governing type with a same-type unit from a peer case. Raw v0.2 sensitivity probe; carries both rule effect and content effect.

**Pillar 2 family** (counterfactual-controlled sensitivity)

5. **`swap_condition`** — edit only the condition clause of a gate-rule unit (e.g., the `requires: ...` list), keeping state phrase and other content from the focal case. Isolates rule effect from content effect.

**Pillar 3 presentation-layer invariance** (orthographic / structural changes)

6. **`whitespace_jitter`** — randomize spacing inside non-governing sections; tokens preserved.
7. **`punctuation_normalize`** — swap orthographically-equivalent punctuation (e.g., en-dash → em-dash, smart quotes → straight).
8. **`bullet_reformat`** — convert between bulleted and inline-numbered list forms; content preserved.
9. **`non_governing_duplication`** — duplicate an existing sentence within a non-governing section. Decision should not change.

**Pillar 3 rhetorical invariance** (rule-based, structural constraints)

10. **`hedge_injection`** — insert hedges ("perhaps", "appears to") around non-governing prose; never touches numeric tokens or governing sections.
11. **`politeness_injection`** — soften imperative verbs in non-governing prose ("review" → "please review").
12. **`discourse_marker_injection`** — prepend discourse markers ("Specifically,", "Importantly,") to non-governing sentences.
13. **`meta_commentary_injection`** — add a meta-clause ("As noted above") to non-governing prose.

**Pillar 3 mechanical sensitivity** (decision should move; closed hand-validated lists)

14. **`numeric_magnitude`** — multiply numeric tokens in governing sections by 2×, 5×, 10×, or 100×. Tests whether the model reads quantities.
15. **`comparator_flip`** — swap a comparator inside the governing section (≥ ↔ ≤, > ↔ <, etc.) from a closed pair list.
16. **`polarity_flip`** — replace a word with its antonym from a closed pair list (`exceeds` ↔ `falls below`, `must` ↔ `must not`).

### Decision-field scoring

Kelvin scores a single designated decision field per pipeline output — a top-level JSON key the pipeline must emit. The value must resolve to a scalar (string, number, boolean, or null). Free-form text rationales in the same output are recorded for inspection but not scored.

- **Categorical decisions** (e.g., `stage_assessment ∈ {idea, pre-seed, seed, growth, scale}`) use a 0/1 distance: same value → 0, different → 1.
- **Scalar decisions** (e.g., a risk score between 0 and 100) use a normalized absolute difference: `d(a, b) = min(1, |a - b| / max(|a|, |b|, 1))`.

Distances are averaged over each perturbation class to produce **Invariance** ∈ [0, 1] (1 = perfectly stable) and **Sensitivity** ∈ [0, 1] (1 = always moves under sensitivity probes). The Kelvin score is `K = (1 − Invariance) + (1 − Sensitivity)`, range [0, 2], lower = better.

---

## 3. Input requirements

**Bottom line.** Kelvin reads a folder of markdown case files plus one YAML config. The pipeline being tested is invoked as a shell command — Kelvin doesn't need to import any of the pipeline's code.

*The requirements below describe v0.3.0. v0.4 (§8) removes the markdown-only and `governing_types` requirements via auto-unitization across input formats and a perturb-all-units mode; until then, the constraints in this section apply.*

### Case file format

One `.md` file per case. Each `## Heading` becomes a typed unit; the heading is normalized to lowercase-snake-case to derive the unit's `type` (e.g., `## Gate Rule` → type `gate_rule`). Content between headings is the unit's body. Example:

```markdown
## Venture Description
The company sells AI-powered task management for enterprise teams.

## Team
Three co-founders, all full-time, two with prior exits.

## Gate Rule
Advance from Validate to Build requires: founder committed capital, evidence
of demand, and first ventures actively using the platform. All conditions
are met.
```

Section count is flexible. Sections are unit-typed by their headings; types may repeat (a case with three `## Interview` sections produces three units of type `interview`). A unit type used as the governing type for sensitivity probes must appear in at least two cases for swap to fire.

### `kelvin.yaml` configuration schema

| Field | Required | Type | Purpose |
|---|---|---|---|
| `run` | yes | string | Shell template, must contain `{input}` and `{output}` placeholders |
| `cases` | yes | path | Directory of `.md` case files |
| `decision_field` | yes | string | Top-level JSON key the pipeline must emit (no dotted paths) |
| `governing_types` | yes | list[str] | Unit types eligible as swap targets (normalized) |
| `seed` | no | int | Deterministic seed for perturbation generation; default 0 |
| `cache_dir` | no | path | If set, opt-in on-disk invocation cache keyed by input hash |
| `timeout_s` | no | int | Per-invocation subprocess timeout in seconds; default 150 |
| `noise_floor.enabled` | no | bool | Pillar 1 toggle |
| `noise_floor.replications` | no | int | Number of baseline replays for σ_c estimation; default 10 |
| `counterfactual_swap.enabled` | no | bool | Pillar 2 toggle (`swap_condition`) |
| `intra_slot.enabled` | no | bool | Pillar 3 toggle |
| `intra_slot.enabled_families` | no | list[str] | Subset of the 11 Pillar 3 families to activate |
| `retry_policy.transient_exit_codes` | no | list[int] | Exit codes that trigger retry with exponential backoff |
| `retry_policy.max_attempts` | no | int | Default 1 (no retry) |

### Pipeline interface contract

Kelvin invokes the pipeline as a subprocess once per baseline, replay, and perturbation. The contract:

1. Kelvin writes a `.md` file to disk and substitutes its absolute path for `{input}` in the `run` template.
2. Kelvin substitutes a target `.json` path for `{output}`.
3. The pipeline reads `{input}`, does its work, writes a JSON object to `{output}`, and exits 0 on success.
4. Kelvin loads the JSON and reads the value at the configured `decision_field` key. Non-zero exit, missing field, or non-scalar value is treated as a failure for that invocation; the case is dropped from aggregation if every replay fails.

This design intentionally avoids framework lock-in. Any pipeline written in any language with any RAG framework satisfies the contract as long as it can be invoked from a shell.

### Governing types

Declared in the top-level `governing_types: [type_a, type_b]` list in `kelvin.yaml`. Only these types are eligible for swap and `swap_condition` perturbations. A case that lacks a unit of any declared governing type silently skips swap perturbations for itself; its other units remain eligible as swap peers for cases that do have one.

---

## 4. Output

### Per-case report (`kelvin/<case>/report.json`)

Each case produces a JSON file with:

- `case` — case name
- `baseline` — `{ ok, decision_value, decision_field, error }` for the unperturbed run
- `perturbations` — list of every variant for this case, each with `variant_id`, `kind`, `notes` (peer source, position, etc.), `invocation` (output decision value), `distance` (0/1 or scalar), `input_path`, `output_path`
- `scores` — `{ invariance, invariance_sample, sensitivity, sensitivity_sample, sensitivity_by_type, sigma_c }`
- `warnings` — non-fatal cap entries (e.g., "no peers found for type X")
- `caps` — explicit notice when a generator produced fewer variants than its target count

### Run-level report (`kelvin/report.json`)

Aggregate scores across all cases:

- **`invariance`** — mean invariance distance across all invariance-class perturbations, subtracted from 1.
- **`sensitivity`** — mean sensitivity distance across all sensitivity-class perturbations.
- **`kelvin_score`** — `(1 − invariance) + (1 − sensitivity)`.
- **`eta`**, **`invariance_cal`**, **`sensitivity_cal`**, **`kelvin_score_cal`** — Pillar 1 calibrated values, present only when `noise_floor.enabled: true`.
- **`sensitivity_content`**, **`sensitivity_condition`**, **`content_effect`**, **`rule_effect`** — Pillar 2 decomposition, present only when `counterfactual_swap.enabled: true` and the corpus produces clean swap_condition samples.
- **`mechanical_sensitivity`** — Pillar 3 mechanical-axis sensitivity (numeric_magnitude + comparator_flip + polarity_flip).
- **`sensitivity_by_type`** — sensitivity broken down per governing type, useful when multiple governing types are configured.
- **Sample counts** — every score is paired with its underlying sample count so the reviewer can judge statistical weight.
- **`warnings`** / **`caps`** — surfaced from per-case reports.

### Per-family sensitivity breakdown

Mechanical sensitivity is reported as a single aggregate plus per-family breakdown: each of `numeric_magnitude`, `comparator_flip`, `polarity_flip` produces its own mean distance. This lets a reviewer see whether a pipeline is, say, sensitive to numeric magnitude but blind to comparator flips.

### Pillar 2 decomposition output

When the corpus has gate-rule-shaped governing units with parseable condition clauses and matching state phrases, Pillar 2 produces:

```
Sens(swap_content)   — raw v0.2 sensitivity (rule + content effect combined)
Sens(swap_condition) — rule-effect-only sensitivity (state phrase preserved)
Content_Effect       — Sens(swap_content) − Sens(swap_condition)
```

A pipeline that genuinely reads its rule will have `Sens(swap_condition) ≈ Sens(swap_content)`, indicating low content leakage. A pipeline that reacts to surface tokens will have `Sens(swap_condition) ≈ 0` and most of the raw signal flowing through `Content_Effect`.

A terminal report with bar-chart visualizations and a one-line diagnostic is produced after each run; an HTML report is written to `kelvin/report.html` for sharing.

---

## 5. Architecture

**Bottom line.** Kelvin has four cooperating components that pass plain Python dataclasses between them. The artifacts of each step are written to disk so a developer can inspect them with `diff`, `grep`, and version control.

- **Parser** (`src/kelvin/parser.py`) — reads each case file, splits on `## Heading` lines, normalizes headings to types, and produces a `Case` object containing a list of `Unit(type, content, raw_header, index)`.

- **Perturbation generators** (`src/kelvin/perturbations/`) — one module per family. Each implements a `PerturbationGenerator` protocol with a single method: `generate(case, peer_cases, *, seed, governing_types) -> PerturbationBatch`. A batch contains a list of `Perturbation` records, each carrying the rendered markdown for the perturbed input plus structured `notes` describing what was changed. Generators are pure: same seed and same input cases produce bit-identical perturbations.

- **Runner** (`src/kelvin/runner.py`) — invokes the pipeline subprocess for each baseline, replay, and perturbation. Materializes the input markdown to disk under `kelvin/<case>/<phase>/<variant>/input.md`, substitutes paths into the `run` template, captures stdout/stderr, parses the output JSON, extracts the decision field, and produces an `InvocationResult`. Optional retry policy fires on configured transient exit codes with exponential backoff and jitter; retries are logged to stderr only so stdout stays parseable.

- **Scorer** (`src/kelvin/scorer.py`) — computes per-case invariance / sensitivity / sigma_c, aggregates to run-level, applies Pillar 1 calibration when configured, and applies Pillar 2 decomposition when swap_condition samples are present. The scorer is a `Protocol` so a v2 semantic scorer can drop in without changing the runner.

### How a single perturbation is generated and scored

1. Parser produces `Case` objects from the markdown files in `cases/`.
2. The check entry-point invokes each generator once per case, passing the focal `case`, the list of `peer_cases` (everything else), the seed, and the configured `governing_types`. Each generator returns a list of `Perturbation` records.
3. Phase 1: the runner invokes the pipeline once per baseline, plus N times per case for Pillar 1 noise-floor replays.
4. Phase 2: the runner invokes the pipeline once per perturbation. A thread pool parallelizes invocations within configured concurrency limits.
5. The scorer reads each invocation's decision value, computes per-perturbation distance from the baseline decision, aggregates into per-case scores, and aggregates across cases into run-level scores.

### Caching, retry, parallelism

- **Caching**: opt-in via `cache_dir`. Key is `sha256(run_template + rendered_markdown + decision_field)`. Hits skip the subprocess entirely. Failed invocations are never cached. Safe to delete at any time.
- **Retry**: opt-in via `retry_policy`. Exponential backoff with jitter on configured `transient_exit_codes`. Exhausted retries surface as a normal failure; the case is correctly excluded from aggregation if every replay fails.
- **Parallelism**: a small thread pool runs perturbation invocations in parallel within a single case. Cases are processed serially.

---

## 6. Key design decisions and limitations

**Why structural typing is required.** Kelvin's whole argument depends on classifying each unit as either *should-not-affect-the-decision* (invariance peers and pads) or *should-govern-the-decision* (swap targets). In v1 the typing comes from user-declared section headers — the user asserts, by writing `## Gate Rule`, that this section is the rule. This is a significant simplification: the structural-oracle argument in whitepaper §3 only fully holds when types are derived from a corpus schema rather than asserted by the human writing the cases. Schema-inferred typing is the explicitly load-bearing direction for v2.

**What Kelvin cannot do (true by design, not by version).**

- **Score free-form text.** Kelvin reads a single scalar decision field. It does not score the rationale, the explanation, or any prose output. Tools like RAGAS and ARES are aimed at prose RAG and are complementary, not replaced. (Richer-Y scoring is v2 territory; see §8.)
- **Reverse-engineer or synthesize a rule.** Kelvin measures whether a pipeline empirically treats specific unit types as governing — after v0.4 the per-type sensitivity profile shows *which* types the pipeline reads. It does not infer the *content* of the rule the pipeline is following, propose one, or determine which unit *should* be governing in a normative sense (that's a corpus-design choice the user makes).
- **Score rhetorical correctness.** Pillar 3's rhetorical families test whether the pipeline is invariant under hedge / politeness / discourse-marker injection. They do not measure whether the pipeline's *own* rhetoric is good.

**What Kelvin does not yet ship (but is planned, not foreclosed).** Today's measurement layer is **scoped to typed-markdown corpora with user-declared `governing_types`** — a real adoption blocker for any pipeline outside that shape. v0.4 closes this with auto-unitization across input formats (markdown / plain text / JSON / HTML), drops the `governing_types` declaration, and adds a perturb-all-units mode so Kelvin can grade a pipeline without the builder telling Kelvin what matters. The response-geometry vector is also currently emitted as ~20+ scalars scattered across `report.json` rather than as one named artifact. A **maturity grade** as a first-class output does not exist yet. **EOS certification** is drafted but not integrated. These are the next three releases (§8), not architectural impossibilities — and v0.4 is the one that actually broadens the audience.

**Known issues observed in real runs.**

- **Pillar 2 is corpus-specific.** `swap_condition` requires the governing unit to have a parseable structure (typically a "X requires: A, B, C" template) and peers with matching state phrases ("All conditions are met"). When the corpus uses prose gate rules without that structure, swap_condition silently produces zero perturbations. This was observed cleanly in the live Envelop run: 7 cases had populated gate rules but only 5 produced swap_condition variants because two had idiosyncratic state phrases or completely different formats.
- **The swap probe only fires on cases with explicit governing-type sections.** Cases without a declared governing-type section participate in invariance probes (reorder, pad, Pillar 3 invariance families) and contribute as peers, but produce no swap or swap_condition variants for themselves. This is by design — Kelvin cannot probe rule-tracking on a case that has no rule — but it means a corpus split between "has a gate rule" and "doesn't" will produce sensitivity scores derived from a sub-population only.
- **Pipeline determinism collapses Pillar 1 to a no-op.** Pipelines configured with deterministic decoding (temperature=0, structured output schemas) produce σ_c = 0 across replays, making `K_cal = K_raw` exactly. Pillar 1's value emerges only with sampled / non-deterministic pipelines.
- **Content leakage in raw `swap` is real.** Pre-Pillar-2, raw swap sensitivity was an upper bound on rule-tracking. The grounded rule-based reference pipeline showed 100% content leakage (`Sens(swap_condition) = 0`); a live LLM-backed pipeline showed ~58% rule effect / ~42% content effect. The decomposition is necessary, not theoretical.

---

## 7. Whitepaper positioning

**Bottom line.** The formal claim of the framework is in `docs/whitepaper.md` §3. The narrow version is one paragraph long and is reproduced verbatim in the §1 abstract: Kelvin uses typed corpus units to derive paired metamorphic diagnostics — invariance under irrelevant perturbations and sensitivity under governing-unit substitution — providing an evidence-tracking signal of whether a pipeline's outputs move with the evidence that should govern them rather than with its presentation.

**Relation to metamorphic testing.** Metamorphic testing was developed for settings where individual ground-truth answers are expensive or impossible to specify. Instead of comparing one execution against a label, it specifies relations between multiple executions under transformations of the input. Kelvin inherits this framing directly. The novelty is in *where the relations come from*: not from program semantics or mathematical identities (the classic metamorphic-testing source), but from the structural typing of a corpus.

**Relation to behavioral testing in NLP.** CheckList-style behavioral testing (Ribeiro et al., 2020) treats invariance under linguistic perturbations as a first-class capability test. Kelvin shares the philosophy but perturbs the *organization of evidence units inside a RAG corpus* rather than the linguistic form of individual examples.

**Relation to judge-based evaluation.** RAGAS, ARES, and LLM-as-judge frameworks ask "does this answer look right to a model?" Kelvin asks "does this answer move only when the evidence that should determine it moves?" The methods are answering different questions and are complementary, not competing. Judge-based metrics summarize answer quality; Kelvin probes evidence-tracking under controlled perturbations.

**The empirical anchor.** Whitepaper §5.3 shows that on a six-case corpus run with the same perturbation suite, a deterministic rule-based "grounded" pipeline scores K = 0.48 and a constant-output "degenerate" scores K = 1.00 exactly — matching the analytical prediction in §3.4 that a degenerate pipeline lands at K = 1. The paired signal separates them; neither axis alone does.

---

## 8. Roadmap — measurement first, certification second

**Bottom line.** Three layers, in order: estimate the geometry, grade against a rubric, certify the grade with finite-sample guarantees. **v0.4 is the breakthrough release** — not because it formalizes the geometry vector (that's small follow-on work), but because it removes the actual adoption blocker: today's requirement that the user pre-declare typed markdown sections and `governing_types`. After v0.4, Kelvin grades any pipeline that takes text-like input and emits a structured decision, without the builder telling Kelvin what matters. v0.5 builds the rubric on top of that broader baseline. v1.0 adds EOS certification. v2 is the deeper-semantic upgrade. Two prior orderings were wrong: K → EOS → maturity (front-loaded the math); v0.4 → signature.json without dropping the typing requirement (improved reporting before removing the actual blocker).

### Layer 1 — Response-geometry vector (the measurement)

Today (v0.3.0), the vector is computed for typed-markdown corpora with declared `governing_types`: ~20+ scalars covering invariance, sensitivity, noise floor (η, Inv_cal, Sens_cal, K_cal), Pillar 2 decomposition (Sens_content, Sens_condition, Content_Effect, Rule_Effect), per-family means across the eleven Pillar 3 generators, and per-type sensitivity. The vector is implicit — assembled from `report.json` by hand.

Two changes are needed to make Layer 1 useful as a *general* measurement layer rather than a structured-decision-RAG-with-typed-corpus tool. Both ship in **v0.4**:

1. **Expand the input domain.** Drop the markdown-only requirement. Drop the `governing_types` declaration. Auto-unitize the input. Perturb every detected unit type. Emit a per-unit-type sensitivity profile so the user can read which types the pipeline treats as governing rather than declare it in advance. *This is the breakthrough.*

2. **Make the vector explicit.** Bundle the per-type profile and pillar scalars into a single named, versioned `signature.json` artifact. *Small follow-on work that becomes more valuable once the vector covers a broader class of pipelines.*

### Layer 2 — Maturity grade (the rubric)

A grade is a function from response-geometry-vector → ordinal class, defined by a rubric. Each grade names a region of the vector space with concrete criteria:

| Grade | Region in vector space (illustrative) |
|---|---|
| **1 — Constant** | Inv ≈ 1, Sens ≈ 0. Pipeline always returns the same answer; trivially invariant, no evidence tracking. |
| **2 — Reactive** | Inv low, Sens variable. Output moves under any input change; not anchored. |
| **3 — Stable but content-leaky** | Inv high, Sens_content high, Sens_condition low. Pipeline reacts to surface tokens, not the rule itself. |
| **4 — Rule-tracking** | Inv high, Sens_condition ≈ Sens_content; mechanical-sensitivity families (numeric_magnitude, comparator_flip, polarity_flip) all > 0. |
| **5 — Mature** | Grade 4 plus η below an action threshold (deterministic enough for reliable production); Pillar 3 invariance probes all > 0.9; no per-type sensitivity gaps. |

Computing the grade is straightforward arithmetic on the vector. Producing a remediation tip ("Sens_condition below 0.3 — pipeline is reading surface tokens, not the rule clause") follows from each grade's failure conditions. This is the layer that makes Kelvin a product rather than a research artifact: a non-statistician reads one number and a remediation list. The illustrative grades above are placeholders to anchor the shape; the shipped rubric will name calibrated thresholds derived from reference signatures.

### Layer 3 — EOS certification (the guarantee)

Once a maturity grade exists, the natural follow-up is *how confident are we in the grade?* That's where the **Empirical Oracle Signature** framework — currently drafted at `experiments/eos_v2_2_certification/eos_theorem_DRAFT_for_review.pdf` (companion brief at `experiments/eos_v2_2_certification/CERTIFICATION_BRIEF.md`) — becomes the right tool.

EOS defines a behavioral signature `Σ̂(f)` for a pipeline `f` as a vector of decision-probabilities under a sealed, pre-specified catalogue of probes (M = 8 in the v2.2 instance), computed by sampling N = 600 trials per (pipeline, probe) pair under explicit stochastic-coupling adversaries with active-set conditioning so the probe meaningfully exercises the pipeline. The accompanying V5 theorem provides finite-sample conditions under which two pipelines with distinct signatures can be **separated** with confidence ≥ 1 − δ at a Bonferroni-corrected α-per-pair, even against paired adversaries that try to mimic a tracking pipeline. The v2.2 certification run is one empirical instance of the theorem's setup: five reference pipelines (`f_track`, `f_ruleblind`, `f_constant`, `f_wrongstatic`, `f_wrongstochastic`) tested on the M = 8 sealed catalogue, with all parameters and probe specifications committed to git *before* any pipeline-run results were generated. The result: `Σ̂(f_track) ≠ Σ̂(f_j)` for every adversary, margin ≥ λ = 0.08 in both directions.

In the layered model, EOS is the apparatus that lets a team make a published, defensible claim: *"we are ≥ 1 − δ confident that this pipeline meets Maturity 4 on the sealed catalogue."* Without the rubric in Layer 2, EOS is a separation theorem in search of a proposition to certify; with the rubric in place, EOS becomes the rigor upgrade for teams that need to attach finite-sample confidence to their grade — auditors, regulators, paper reviewers, vendor-certification programs.

**Important scope limits** carried over from the draft: EOS does not prove pipelines are *correct* in any semantic sense — only that their behavioral signatures are distinguishable on the sealed catalogue. It does not detect failure modes outside the catalogue. The v2.2 run uses synthetic rule-based reference pipelines, not LLM-backed ones; LLM-backed validity requires a separate sealed run under the same discipline.

### Why this order

**Estimation precedes inference precedes inferential confidence.** The vector is the estimator. The grade is the inferential claim built from the estimator. EOS is the standard-error apparatus on the inferential claim. Each layer requires the one below it to add value: a certification with no graded claim has nothing to certify; a grade with no underlying vector has nothing to compute from.

**Each release ships a user-visible deliverable.** v0.4 broadens the input domain so the measurement layer applies to any pipeline. v0.5 turns it into a grade. v1.0 makes the grade certifiable. The K → EOS → maturity order would have shipped the V5 theorem before shipping the readable output. The signature.json-without-broader-input order would have improved reporting before removing the actual blocker. Both errors front-loaded the wrong thing.

**Maturity is intrinsic; signatures are catalogue-relative.** A grade against the perturbation-suite rubric is a property of the pipeline. An EOS Σ̂ is defined relative to a sealed catalogue. The intrinsic property should ship first; the catalogue-relative certification should ship later for the audiences that need it.

**The breadth of the input domain belongs at the bottom.** The rubric's value is gated by what input domain the measurement layer supports. A rubric over typed-markdown corpora with declared governing types helps a niche audience. A rubric over auto-unitized signatures helps anyone with a black-box pipeline. Layer 1 must be broad before Layer 2 ships, or Layer 2 inherits Layer 1's adoption ceiling.

### Corrected roadmap

| Stage | Status | Deliverable | What it gives the user |
|---|---|---|---|
| **v0.3.0** | shipped 2026-04-24 | `report.json` with all pillar scalars; geometry computed for typed-markdown corpora with declared `governing_types` | Geometry exists for projects that have typed their corpus and declared governing types |
| **v0.4 — drop the typing requirement (THE BREAKTHROUGH)** | not yet scoped | (a) **Auto-unitization across input formats**: markdown headers (kept as a fast path), plain text (paragraph or sentence split), JSON (key-level units), HTML (DOM block split). (b) **Drop the `governing_types` declaration**: Kelvin perturbs every unit type that has ≥2 peers and emits a per-unit-type sensitivity profile. The profile *itself* shows which types the pipeline empirically treats as governing. (c) **Mechanical perturb-all-units mode** runs the full battery without pre-classification. (d) Explicit `signature.json` artifact bundling everything as a versioned vector. | Kelvin grades any pipeline that takes text-like input and emits a structured decision, without the builder telling Kelvin what matters. The release that turns Kelvin from a structured-decision-RAG tool into a general black-box-pipeline diagnostic. |
| **v0.5 — the rubric** | not yet scoped | Maturity rubric over the v0.4 signature space; CLI prints a grade ("Maturity 3 / 5: stable but content-leaky") with per-grade remediation tips; reference vectors for the canonical shapes (constant, ruleblind, content-leaky, rule-tracking, mature) shipped with the package | Teams get a single readable verdict for any pipeline and a concrete remediation plan derived from the per-type profile |
| **v1.0 — the certification** | EOS draft exists; integration not started | EOS Σ̂ wired into the runner; `kelvin certify` command; sealed catalogue shipped; finite-sample CIs at 1 − δ confidence on grade claims; reference adversaries from the v2.2 certification run packaged as a verifiable benchmark | Teams can publish defensible claims with statistical guarantees; reviewers, auditors, regulators have proper inferential machinery |
| **v2 — deeper-semantic work** | named in whitepaper §6–7 | Schema-inferred *categorical* typing (e.g., "this unit is a gate rule" vs "this is a team description") on top of v0.4's structural unitization; semantic-output scorer (free-form text Y); stage decomposition (retrieval / reranking / generation attribution) | Categorical type discovery on auto-unitized inputs; richer Y; per-stage attribution |

### v0.4 vs v2 — disambiguating the typing work

The earlier framing (and the whitepaper's "schema-inferred typing is v2") conflated two different typing concerns. **v0.4's auto-unitization is structural**: it detects that units exist by splitting input on natural boundaries — headers, paragraphs, JSON keys, DOM blocks. It does not assign semantic categories; units may be called `unit-1, unit-2, ...` or grouped by trivial structural type, and the per-type sensitivity profile reads units as *what they are positionally*. **v2's schema-inferred typing is semantic**: it infers categorical labels for each unit from a corpus schema or learned classifier, so the type names become human-meaningful (`gate_rule`, `market_evidence`).

v0.4 is enough to remove the adoption blocker and produce a per-unit-type sensitivity profile. v2 makes the type labels human-meaningful and enables claims like *"this pipeline reads gate_rule but ignores team."* v0.4 is the breakthrough; v2 is the depth upgrade.

### Why v0.4 is smaller engineering than it looks

Auto-perturb-all-types is mostly removing the `governing_types` filter from the swap generator and updating aggregation to emit per-type profiles — twenty-line changes in a couple of files. Auto-unitize for markdown is free: sections are already units. MVP unit detectors for plain text (paragraph-split) and JSON (top-level keys) are tens of lines each. The expensive work — semantic chunkers, learned unit detectors, NLP-based categorical typing — stays in v2. v0.4 is "remove the artificial restriction the v1 simplification introduced," not "solve unit detection in the general case."

### Why this strengthens the structural-oracle argument

The whitepaper's v1 simplification was *"let the user assert which headers identify governing units,"* which made the user's assertion a load-bearing premise. v0.4 removes the assertion: Kelvin measures decision-change rate per detected unit type, and the type with the highest rate is what the pipeline empirically treats as governing. This is more rigorous than the v1 setup, not less. The structural-oracle argument now rests on the empirical sensitivity profile rather than on the user's a-priori typing.

### How EOS's positioning has shifted in this document

EOS is no longer described as "the bridge to geometry," nor as the next user-visible release. Layer 1's response-geometry vector *is* the geometry, and v0.4 expands its applicability to any pipeline. EOS is the **certification layer** that attaches finite-sample confidence to the maturity grade once the rubric exists. The V5 theorem and v2.2 certification run remain valid and useful in this framing; they answer *"with what confidence can we claim two graded pipelines are behaviorally distinct?"* rather than the conflated *"what is the geometry?"* The draft itself does not need restructuring — only the surrounding sequencing does.

---

*Document version: 2026-04-26 (revision 3 — v0.4 reframed as the breakthrough release that drops the typed-markdown / `governing_types` requirement; signature.json reframed as small follow-on work, not the headline). Self-contained reviewer briefing for Kelvin v0.3.0 with corrected roadmap.*
