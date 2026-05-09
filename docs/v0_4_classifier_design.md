# v0.4 — LLM-Assisted Structural Labeling — Design Doc

**Status:** design for review. No code yet for the classifier piece. Some v0.4 components already shipped in commit `164b62f`.

**Decision context:** today's prototype confirmed auto-unitization on stripped prose produces no per-unit signal at reasonable budget (σ_baseline=30-43 on a 200-800 scale; 0/25 paragraphs cleared 2σ). Restoring structure is the load-bearing change. The user's path forward: an LLM acting as a *structural classifier* (not a judge) to infer unit boundaries and types from raw prose, producing labeled artifacts that Kelvin's existing machinery consumes unchanged.

**The classifier never evaluates the pipeline.** It does not score outputs, judge quality, or rate ventures. It reads input prose and assigns each section a type label (e.g., `team`, `market_evidence`, `gate_rule`). That's it.

---

## v0.4 in full — what this design doc covers, and what's already done

v0.4 is a stack of four pieces. The classifier is one of them. The other three are already in code (commit `164b62f`) but worth restating so this doc isn't read as if v0.4 = classifier-only.

### Layer 1 — Drop the `governing_types` requirement ✅ shipped (commit 164b62f)

When `governing_types` is unset/empty, swap and swap_condition iterate every detected unit type with cross-case peers. No user declaration required. Per-unit-type sensitivity profile emerges automatically and reveals which types the pipeline empirically treats as governing.

This was the actual v0.4 breakthrough. Backward-compat preserved: declaring `governing_types: [x, y]` still focuses the swap to those types only.

### Layer 2 — Mechanical perturb-all-units mode ✅ shipped (commit 164b62f)

With Layer 1 in place, all of Kelvin's existing perturbation families (reorder, pad_length, pad_content, swap, swap_condition, the eleven Pillar 3 families) run on every detected unit type without pre-classification. The full battery exercises the full structure of the input.

### Layer 3 — Explicit `signature.json` artifact ✅ shipped (commit 164b62f)

Every `kelvin check` now writes `kelvin/signature.json` — a single named, versioned response-geometry vector bundling raw scores, noise floor, decomposition, mechanical sensitivity, and the per-unit-type sensitivity profile. This is the foundation for v0.5's maturity rubric and v1.0's EOS certification.

Schema versioned at 1; emits unconditionally including dry runs.

### Layer 4 — LLM structural classifier ⏳ this design doc

Today's prototype showed that Layers 1-3 work cleanly when the input has structure (`## Heading` markers in v0.3 cases) and produce noise-dominated output when stripped to raw prose. **The classifier closes that gap.** It reads unlabeled prose and produces labeled markdown that Layers 1-3 consume identically to a hand-labeled file.

Sections A-D below cover Layer 4 specifically. The other three layers are reference points, not new work.

### How the four layers compose

```
Raw prose (any text-like input)
        │
        ▼
[Layer 4]  LLM classifier infers unit boundaries + types
        │
        ▼  cases/{name}.labeled.md (markdown with ## headers inserted)
        │
        ▼
[Existing parser]  Reads ## headers → typed Units
        │
        ▼
[Layer 1]  No governing_types declared → perturb every detected type
        │
        ▼
[Layer 2]  Mechanical perturbations on every unit (reorder, pad, swap, Pillar 3 families)
        │
        ▼
[Existing scorer]  Per-case + per-type + per-pillar aggregation, σ_c calibration
        │
        ▼
[Layer 3]  signature.json emitted (response-geometry vector)
        │
        ▼
[v0.5]  Maturity grade computed from signature.json against published rubric
        │
        ▼
[v1.0]  EOS Σ̂ certification on the maturity grade
```

The classifier (Layer 4) is the only new piece v0.4 needs. Layers 1-3 are already in code; they just become *useful for unlabeled inputs* once Layer 4 exists.

---

## v0.4 mathematical claim

The whole v0.4 design hangs on a bounded-error claim that can be checked
empirically component-by-component. Adopting this as the formal commitment:

$$|K(f, \hat G) - K(f, G_{\text{ref}})| \leq \varepsilon_{\text{label}} + \varepsilon_{\text{sampling}} + \varepsilon_{\text{noise}}$$

Where:

- `K(f, G)` is the Kelvin score of pipeline `f` evaluated under structural
  graph `G` (the unit-boundary + type assignment for the input corpus).
- `Ĝ` = LLM-classifier-inferred graph (Layer 4 output).
- `G_ref` = human-labeled reference graph (`## Heading`-marked cases).
- `ε_label` = error introduced by the classifier inferring `Ĝ ≠ G_ref`.
- `ε_sampling` = error from finite replay budget at each measurement step.
- `ε_noise` = error from pipeline stochasticity (the per-case σ_c, η at
  the run level).

Each error source is **separately measurable**, and each is targeted by a
different lever in the v0.4 design:

| Error source | Targeted by | How we measure it |
|---|---|---|
| `ε_label` | Classifier validation gates (§B) | Boundary IoU + type accuracy on direct compare; magnitude-error + Spearman on downstream-recovery |
| `ε_sampling` | Replay-budget configuration (existing v0.3 noise_floor.replications, plus per-perturbation N) | Welch SE on each sensitivity estimate; shrinks as 1/√N |
| `ε_noise` | Pillar 1 calibration (existing in v0.3) | η measured per case from baseline replays; calibrated K subtracts it |

The bound is a **triangle-inequality upper bound**, not tight. It buys
the design a clean separation: tightening any one component tightens the
overall bound; shipping decisions can target the component with the
worst headroom rather than guessing.

**Implication for ship-readiness.** v0.4 ships when each component is
bounded by an empirically defensible target. The classifier validation
gates (§B) are the load-bearing ones because `ε_label` is the only
component that's new in v0.4 — `ε_sampling` and `ε_noise` are inherited
from the v0.3 machinery and already measured.

---

## What this doc is about (Layer 4)

The remaining sections (A through D) cover the classifier interface, validation, integration, and timeline. Read everything below as scoped to Layer 4 only — not the full v0.4 stack. The mathematical claim above is what each of those sections is trying to satisfy.

---

## A. LLM-classifier interface

### Model choice

**Recommendation: Claude Haiku 4.5 (current latest Haiku)**, with Gemini 2.5 Flash as the fallback option behind a config flag.

| Criterion | Claude Haiku 4.5 | Gemini 2.5 Flash |
|---|---|---|
| Cost (per 2k-token classification) | ~$0.003 | ~$0.001 |
| Structured-output mode | Tool-use schemas | JSON mode |
| Determinism at temp=0 | Strong | Strong |
| Latency | ~1-3s | ~2-5s |
| Reasoning on ambiguous prose | Better | Adequate |

Both are 100× cheaper than the Envelop full-pipeline call this experiment used. Cost is not the bottleneck. **I'd default to Haiku for stability of structured output** under tool-use; ship Gemini as a configurable provider for users who already have keys for it.

Make the provider/model name a config field so it's swap-able without code changes.

### Prompt shape

Two-part prompt, classification-only:

**System (constant, version-pinned):**
> You are a structural-unit classifier. Your job is to read input prose for a structured-decision pipeline and identify section boundaries and unit types.
>
> You DO NOT:
> - Evaluate the venture, candidate, claim, or content.
> - Score, rate, judge, or assess quality.
> - Comment on whether the content is good, bad, complete, or correct.
> - Add commentary, advice, or interpretation.
>
> You ONLY:
> - Identify where one unit ends and the next begins.
> - Assign each unit a type label from the provided vocabulary.
> - Return character offsets so the boundaries are deterministically reconstructable.
>
> If the prose has no recoverable structure, return an empty units list rather than fabricating boundaries.

**User (per-call):**
> Vocabulary: [team, market_evidence, target_customer, traction_signal, gate_rule, unit_economics, venture_description, ... domain-specific list]
>
> Prose:
> ```
> {prose}
> ```
>
> Return units in JSON form using the schema below.

### Output schema

```json
{
  "units": [
    {
      "index": 0,
      "type": "venture_description",
      "start_char": 0,
      "end_char": 547,
      "raw_excerpt": "First 80 characters of the unit, for human inspection..."
    },
    ...
  ],
  "unrecoverable": false,
  "model": "claude-haiku-4-5-20260301",
  "prompt_version": 1
}
```

- `start_char` / `end_char` are character offsets into the source prose. Kelvin reconstructs the unit deterministically by slicing — the LLM never re-emits the prose.
- `type` must come from the vocabulary; an out-of-vocab type is rejected and the unit is dropped with a warning.
- `unrecoverable: true` is the explicit "no structure here" signal — Kelvin then falls back to paragraph-split or refuses to run on that case (configurable).
- `model` and `prompt_version` are recorded so cached labels can be invalidated when either changes.

### Type vocabulary — closed by default, configurable

A **closed vocabulary** prevents type-name drift across cases (e.g., "team" vs "company_team" vs "founders" — all the same thing for swap purposes). Kelvin ships defaults per domain:

- `vc_assessment` (default): team, market_evidence, target_customer, traction_signal, gate_rule, unit_economics, venture_description, problem, solution, business_model
- `resume_screening`: education, work_history, skills, certifications, projects
- `medical_report`: presenting_complaint, history, examination, diagnosis, treatment_plan
- `custom`: user provides a list in `kelvin.yaml`

The vocabulary is part of the prompt and is included in the cache key.

### Determinism

| Lever | Setting |
|---|---|
| `temperature` | 0 |
| Structured-output mode | Required (tool-use for Anthropic; JSON mode for Gemini) |
| Model version | Pinned (`claude-haiku-4-5-20260301`, not `claude-haiku-4-5-latest`) |
| Prompt template | Versioned in code; bumping `prompt_version` invalidates cache |
| Vocabulary | Hashed into cache key |

Even with all of these, expect ~1-5% label variation across re-runs at temp=0 on borderline cases. The cache is what makes a Kelvin run reproducible — once labels are computed for a case, they're locked until something changes.

### Caching

Reuse Kelvin's existing on-disk cache pattern. Cache key:

```
sha256( prose_text + model + prompt_version + json.dumps(vocabulary, sorted) )
```

Cache value: the full `units` JSON output above.

Cache location: `kelvin/labels-cache/{key}.json` (separate directory from invocation cache so they can be cleared independently).

Labels also written to a human-visible artifact: `kelvin/labels/{case_name}.json` — same content, plus the mapping back to the source case so a human can spot-check.

---

## B. Validation

The classifier ships only after passing two gates: a **direct-comparison** gate against human-written labels, and a **downstream-recovery** gate confirming that classifier-labeled runs reproduce the per-unit signal of human-labeled runs on the same cases.

### Gate 1 — Direct comparison (necessary but not sufficient)

Run classifier on stripped versions of all 10 cases. Compare against original `## Heading` labels for the 6 human-labeled cases (envelop, artisanflow, freakinggenius, meridian, northpass, rhodium).

| Metric | Definition | Pass threshold |
|---|---|---|
| **Boundary IoU** | Per human unit, find the classifier unit with maximum character-range overlap. IoU = intersection / union. | ≥ 0.8 IoU on ≥ 80% of human units |
| **Type accuracy** | Among matched-boundary units, fraction where classifier type == human type (modulo synonym mapping declared in vocabulary) | ≥ 90% |
| **Coverage** | Fraction of source-prose characters covered by classifier units | ≥ 95% |
| **Stability** | Run classifier 5× per case at temp=0, measure label drift (boundaries + types) | ≥ 95% identical across replays |

### Gate 2 — Downstream recovery (load-bearing)

Direct comparison checks "does the classifier label like a human?" Downstream recovery checks the question that actually matters: **"do classifier-labeled runs produce the same Kelvin output as human-labeled runs?"** Phrased in the math claim's terms: gate 2 estimates `ε_label`.

Protocol:
1. Run morning's full Pillar 1+2+3 experiment on the 6 human-labeled cases — call this **Reference**.
2. Strip headers, run classifier, write classifier-labeled artifacts.
3. Run the same Pillar 1+2+3 experiment on classifier-labeled cases — call this **Classifier**.
4. Run the Reference experiment a *second* independent time — call this **Reference-replicate**. The Reference-vs-Reference-replicate divergence is the irreducible noise floor on every metric below; it sets `ε_sampling + ε_noise`. The Classifier-vs-Reference divergence must not exceed that floor by more than the data-calibrated factor.

#### Two metrics, one rank-based and one magnitude-based

Spearman ρ alone catches rank-flips but is blind to magnitude errors that
preserve ordering — a classifier that scales every sensitivity by 0.5
would score ρ = 1.0 yet produce a wrong K. Adding L∞ (worst-cell error)
and MAE (mean error) catches both axes.

For each case, compute the per-unit-type sensitivity vector. Aggregate
Reference vs Classifier per case, then across cases.

| Metric | What it captures |
|---|---|
| **Spearman ρ** between Reference and Classifier sensitivity vectors | Rank preservation — does the classifier order types the same way? |
| **L∞ norm** of `(vec_cls − vec_ref)` | Worst-cell magnitude error — the largest single per-type sensitivity miss |
| **MAE** of `(vec_cls − vec_ref)` | Average magnitude error across all types |
| **σ_c divergence**: `|σ_c_ref − σ_c_cls|` (absolute, on the 0-1 sensitivity scale) | Noise floor preservation |
| **Run-level K divergence**: `|K_ref − K_cls|` | The headline `ε_label` quantity in the math claim |

#### Threshold calibration — set on data, not guessed

Pre-stating "ρ ≥ 0.8" was wrong: rank-only, threshold not calibrated.
The right protocol:

1. Run Reference and Reference-replicate experiments on all 6 cases.
2. Compute the four metrics above on Reference-vs-Reference-replicate.
   Call these the **noise-floor distributions**: `D_ρ`, `D_L∞`, `D_MAE`, `D_σ`, `D_K`.
3. Threshold each metric at **noise-floor 95th percentile × 1.5** as the gate
   — i.e., the classifier's metric on Classifier-vs-Reference must not
   exceed the worst case observed in Reference-vs-Reference-replicate by
   more than 50%. The 1.5× factor is conservative; we accept up to half
   again as much error as pipeline stochasticity alone produces.

| Metric | Gate threshold |
|---|---|
| Spearman ρ | `≥ percentile_5(D_ρ) − 0.5 × |percentile_5(D_ρ)|` (i.e., classifier rho can drop by up to 50% of the noise-floor's 5th-percentile rho) |
| L∞ | `≤ 1.5 × percentile_95(D_L∞)` |
| MAE | `≤ 1.5 × percentile_95(D_MAE)` |
| σ_c divergence | `≤ 1.5 × percentile_95(D_σ)` |
| Run-level K | `≤ 1.5 × percentile_95(D_K)` |

The exact numbers fall out of step 1-2; we don't pre-commit to a
specific Spearman threshold like "0.8". We commit to the **principle**
that classifier-induced error is bounded relative to noise-floor error.

#### What we don't ship

If any of the five gates fails, the classifier ships labels that look right to a human but wrong to Kelvin. We don't ship — the v0.4 mathematical claim's `ε_label` term exceeds what we can defend.

### What we do with the 4 unlabeled cases

For himom, stagehand, readyrounds, narma there's no human label to compare against, so direct comparison doesn't apply. Use them for:
- **Vocabulary stress-test** — does the classifier produce reasonable type assignments on cases the gate vocabulary may not perfectly cover (e.g., `stagehand` is a developer-tool pitch with no `gate_rule`)?
- **`unrecoverable: true` signal test** — does the classifier correctly mark sections that don't match any vocabulary type?
- **Cross-corpus stability** — run classifier on these 4 cases 5× each, confirm ≥ 95% stability (matches gate 1's stability metric).

---

## C. Integration into Kelvin

**Recommendation: separate `kelvin label` preprocessing step, with optional auto-invocation from `kelvin check` when configured.**

### Why preprocessing, not inline

- **Inspectability.** Labeled artifacts at `cases/{name}.labeled.md` are human-readable markdown. The user can spot-check or hand-edit before running `kelvin check`.
- **Separation of concerns.** Classifier logic stays in one module; the runner doesn't gain an LLM dependency in its hot path.
- **Cache lifecycle.** Labels invalidate on different triggers than invocation results — different cache directories, independently clearable.
- **Failure isolation.** If the classifier fails, `kelvin label` errors out with a useful message. `kelvin check` is unaffected because labels already exist on disk from a previous run.

### Concrete shape

**New CLI subcommand:**

```bash
kelvin label                    # classify all unlabeled cases in cases_dir
kelvin label --case envelop     # one case
kelvin label --force            # bypass cache
kelvin label --vocabulary vc_assessment   # override default
```

**Output:**
- `cases/{name}.labeled.md` — markdown with `## Heading` markers inserted. Same format as today's hand-labeled cases. Existing parser handles unchanged.
- `kelvin/labels/{name}.json` — full classifier output (offsets, model, prompt_version) for traceability.

**New `kelvin.yaml` block:**

```yaml
unitizer:
  mode: markdown        # markdown (default) | llm | auto
  vocabulary: vc_assessment
  llm:
    provider: anthropic
    model: claude-haiku-4-5-20260301
    prompt_version: 1
```

- `mode: markdown` → today's behavior. Reads `## Heading` directly.
- `mode: llm` → require `*.labeled.md` to exist for every case (run `kelvin label` first).
- `mode: auto` → for any case without `*.labeled.md`, invoke the classifier inline before parsing.

`auto` is the user-friendly mode; `llm` is the strict CI/audit mode where label generation is a separate explicit step.

### Where labeled output lands

```
cases/
├── envelop.md                  # original, human or LLM-labeled — input to kelvin
├── envelop.labeled.md          # generated by `kelvin label` (if classifier ran)
├── himom.md                    # raw prose
└── himom.labeled.md            # generated

kelvin/
├── labels/
│   ├── envelop.json            # classifier metadata for envelop
│   └── himom.json
├── labels-cache/
│   └── {sha256}.json           # de-duplicated by content+model+prompt+vocab
└── ... (existing report.json, runs/, etc.)
```

### File naming and parsing

Keep `parse_case` simple: it reads `*.md` files. The convention `*.labeled.md` is just the canonical name for classifier output, but `parse_case` doesn't care about the suffix — it parses headers wherever it finds them. This means a hand-labeled file named `cases/envelop.md` and a classifier-output file named `cases/envelop.labeled.md` are interchangeable to Kelvin.

`load_cases` needs one small change: prefer `*.labeled.md` over `*.md` when both exist for the same stem. (Or have the user delete the raw `.md` after labeling — simpler but less audit-friendly.)

---

## D. Cost and timeline

### Engineering breakdown

| Component | Days |
|---|---:|
| LLM classifier client (Anthropic-only, structured output, retry, cache) | 2 |
| Prompt template + vocabulary in kelvin.yaml + validation | 1 |
| `kelvin label` CLI subcommand + config plumbing (`unitizer:` block, `auto`/`llm` modes) | 2 |
| Validation suite — gate 1 (boundary IoU, type accuracy, stability) | 1 |
| Validation suite — gate 2 (Reference-vs-Reference-replicate calibration + 5-metric downstream gate) | 2.5 |
| Documentation: README updates, new spec section, examples for the 4 stub cases | 1 |
| Buffer for surprises (prompt iteration if gate 2 fails on first try) | 2 |
| **Total** | **11.5 working days ≈ 2.5 calendar weeks** |

(Anthropic-only and YAML-only-vocabulary trims the original 12-day plan
by 0.5 days. Gemini provider and the shipped vocabulary registry are
deferred to v0.4.x.)

### Pushback on the 1-2 week target

I'd push back on **1 week** as too tight. The non-negotiable items are the two validation gates. Cutting either one risks shipping a classifier that produces "good-looking but downstream-wrong" labels — which would be invisible until users start running Kelvin and getting unexpected results. The downstream-recovery gate is the load-bearing safety net.

**2 weeks is achievable** if:
- We accept Anthropic-only as v0.4 (Gemini provider deferred to v0.4.x). Saves ~1 day on provider abstraction.
- We accept `auto` mode only (skip the strict-`llm` mode that requires explicit `kelvin label` first). Saves ~0.5 day on CLI plumbing.
- We accept that prompt iteration is in-budget (2 days of buffer assumes one round of revision if gate 2 misses).

**3 weeks is the realistic median** if we want both providers, both modes, and a comfortable buffer for prompt iteration. I'd recommend planning for 3 weeks and shipping in 2 if everything goes smoothly.

### Run-time cost

Classifier is one call per case, cached. Claude Haiku at ~$0.003 per 2k-token case × ~10 cases per typical run = **$0.03 per `kelvin label` run, cached on subsequent runs**. Negligible. The cost story is not where the worry is.

The worry is **prompt regression**. If we bump `prompt_version`, every cached label invalidates and the classifier re-runs across every case. For a 100-case corpus, that's ~$0.30 — still negligible — but the validation gates need to re-pass before the new prompt is considered shipped. That's the discipline that needs to live in the validation suite.

---

## Open questions — RESOLVED, then SUPERSEDED

The five original open questions resolved earlier (closed vocabulary, Haiku default, calibrated gate, separate `kelvin label`, vocabulary in `kelvin.yaml`) have been **partially superseded** by five new clarifications. Both layers captured here for traceability — the new clarifications take precedence where they conflict.

### Superseding clarifications (April 26, 2026)

#### 1. Provider-agnostic from day one — supersedes "Provider default: Haiku"

The classifier accepts a `provider` parameter (`anthropic`, `openai`, `google`, ...) and a corresponding API key from env. The throwaway defaults to Anthropic because that's what's configured locally; **production must allow any provider without code changes**. The provider-abstraction interface ships in v0.4 from day one — Anthropic is the first concrete implementation, Gemini and OpenAI follow immediately as additional implementations of the same interface.

Implementation: a `Classifier` protocol with one method (`classify(prose) → units`); concrete classes per provider (`AnthropicClassifier`, `OpenAIClassifier`, `GoogleClassifier`). Selection via `unitizer.llm.provider:` in `kelvin.yaml`.

#### 2. Optional preprocessing, not core — supersedes any framing of classifier as required

Kelvin **remains a local library**. The classifier is **optional preprocessing** that saves the user ~30 minutes of manual markdown labeling per corpus. The **v0.3 path (user writes `## headers` manually) remains fully supported** — both paths produce the same input format for Kelvin's runner. The classifier is a convenience, not a requirement. Users who don't want any LLM in their pipeline use `unitizer.mode: markdown` (the default) and never touch the classifier.

#### 3. User-provided API key — never stored, never logged, never transmitted

Kelvin ships with **no credentials**. The user provides their own API key via environment variable (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, etc.). Kelvin reads the key from the environment, passes it directly to the chosen provider's client, and **never stores it on disk, logs it, prints it, includes it in cache keys, or transmits it anywhere except to the provider's API**. Documentation must make this contract explicit in the README and the new classifier spec.

#### 4. Arbitrary positional tags, not semantic vocabulary — supersedes "closed vocabulary with `unknown`/`unrecoverable` fallback"

The classifier produces structural boundaries with **positional tags only**: `p1`, `p2`, `p3`, ... at paragraph level. **No semantic vocabulary** (no `team`, `market_evidence`, `gate_rule`). Kelvin does not need semantic meaning — only consistent boundaries. This simplifies the classifier prompt entirely (no vocabulary management, no per-domain registry, no `unknown` fallback) and removes the v0.3.0 cross-case matching dependency for swap perturbations (see cascade below).

#### 5. Single-level granularity in v0.4 — supersedes any multi-granularity discussion

**Level 1 (paragraphs) only** in v0.4. Split on natural paragraph breaks. Tag as `p1, p2, p3, …`. If the throwaway passes, **ship Level 1**. If the throwaway fails, add Level 2 (statements) and retry **before** committing to the production build. **Defer Level 2-3 (sentences, clauses) to v0.4.x** — they're real follow-ons but not v0.4-blocking.

### Cascading effect of clarification #4 (positional tags drop semantic typing)

Two v0.3 perturbation families depend on semantic type-matching across cases. They are dropped from v0.4:

| Family | Status in v0.4 | Reason |
|---|---|---|
| `swap` (cross-case unit swap) | **Dropped** | Requires "same type" peers across cases; positional tags can't define type-match across cases of different unit counts |
| `swap_condition` (Pillar 2) | **Dropped** | Same — needs typed peers; rule-shaped structural parsing also doesn't fit positional tags |
| `delete` (primary content perturbation) | **Kept** | Type-agnostic; works on any unit identifier |
| `reorder` | **Kept** | Type-agnostic |
| `pad_length` | **Kept** | Inserts neutral filler; type-agnostic |
| `pad_content` | **Kept** | Inserts arbitrary peer units; doesn't need type matching |
| Pillar 3 mechanical (numeric / comparator / polarity) | **Kept** | Operates on tokens within units, not on types |
| Pillar 3 presentation (whitespace / punctuation / bullet / duplicate) | **Kept** | Within-unit; type-agnostic |

**Net effect:** deletion + Pillar 3 carry the v0.4 sensitivity load. Cross-case swap was already structurally confounded with content leakage (per Pillar 2's own raison d'être); dropping it tightens the methodology rather than weakens it.

### Original five open questions — what they collapse to

| Original Q | Original answer | Now |
|---|---|---|
| 1. Vocabulary | Closed + `unknown` fallback | **Moot** — no vocabulary; positional tags only (clarification #4) |
| 2. Provider default | Haiku | **Now**: provider-agnostic interface; Anthropic is first concrete implementation, throwaway default (clarification #1) |
| 3. Gate threshold | Spearman ρ + magnitude-error, calibrated on data | **Unchanged** — calibration protocol still applies, but compares boundary IoU rather than type-and-boundary agreement |
| 4. Subcommand | Separate `kelvin label` | **Unchanged** |
| 5. Vocabulary location | `kelvin.yaml` first | **Moot** — no vocabulary (clarification #4) |

---

---

## Throwaway-first protocol — go/no-go gate before production build

Before committing the 11.5 days, ship a 2-3 day throwaway that tests the
load-bearing question: *does an LLM classifier produce labels that
recover above-noise per-unit perturbation-response signal on inputs
where stripped-prose v0.4 failed today?*

If the throwaway answers no, the production build is on a method that
doesn't work. Stop and report.

### Throwaway scope (deliberately minimal — superseded by April 26 clarifications)

**In scope:**
- **Provider-abstraction interface in place** (`Classifier` protocol with one method); Anthropic concrete implementation as the throwaway default. API key from `ANTHROPIC_API_KEY` env var.
- **Paragraph-level granularity (Level 1) only.** Split on natural paragraph breaks (`\n\n+`); the LLM is not actually needed for Level 1 — this is deterministic text munging — but the abstraction is wired so Level 2 (statements) can plug in without re-architecting.
- **Positional tags only** (`p1`, `p2`, `p3`, …). No semantic vocabulary, no closed-list, no `unknown` fallback. The unit identifier carries no meaning.
- 4 cases that failed today: himom, stagehand, readyrounds, narma.
- Output: 4 labeled markdown files at `experiments/v0_4_prototype/labeled_cases/{case}.md`, each with `## p1`, `## p2`, … headers around the original paragraphs.
- Re-run today's `run_opportunity.py` (via a thin wrapper) against the labeled inputs at the same N=10 baselines + N=5 deletions per unit.
- **No `swap` or `swap_condition` perturbations** (they need semantic types — see cascade above). Deletion is the primary perturbation; reorder + pad + Pillar 3 families are available but secondary for the throwaway.

**Explicitly out of scope:**
- ❌ No caching layer (yet — production gets one)
- ❌ No additional providers beyond Anthropic interface stub (Gemini/OpenAI implementations come in production)
- ❌ No `kelvin.yaml` integration
- ❌ No `kelvin label` subcommand
- ❌ No validation gates (gates are for the production build; throwaway tests only the perturbation-response question)
- ❌ No `kelvin/labels-cache/` or `kelvin/labels/{name}.json` artifacts — just labeled markdown
- ❌ No back-compat with v0.3
- ❌ No tests
- ❌ No semantic vocabulary, no domain registry
- ❌ No Level 2 (statements) — added only if Level 1 fails

**What the throwaway is actually testing.**
Today's morning experiment sent stripped paragraphs to the pipeline *without* any header markers — σ_baseline was 30-43 on a 200-800 scale and 0/4 cases produced above-noise per-unit deltas. The throwaway sends the same paragraphs to the pipeline *with* `## p1`, `## p2`, … headers. **The test is whether positional headers — without semantic content — restore enough structural cue to reduce σ_baseline below the per-unit deletion delta.** If yes, even content-free unit markers help. If no, paragraph-level v0.4 is dead and Level 2 is required (or v0.4 ships only as case-level σ_baseline grading).

### Pass criterion

Compare classifier-labeled run against today's stripped-prose run on the same 4 cases:

| Case | Today's stripped-prose result | Throwaway pass criterion |
|---|---|---|
| himom, narma | 0/6 paragraphs above-noise (|Δ| > 2σ); mixed-sign z's, all small | ≥ 1 unit above-noise OR coherent shape with median |z| > 1 |
| stagehand | 0/6 paragraphs above-noise; coherent all-negative z-stripe | ≥ 1 unit above-noise (the all-negative pattern should sharpen with proper typing) |
| readyrounds | 0/7 paragraphs above-noise; mostly flat with one moderate dip at p03 | ≥ 1 unit above-noise (p03's dip should sharpen) |

**Aggregate pass:** at least 2 of the 4 cases produce ≥ 1 above-noise unit. Today's run had 0/4 cases meeting that bar. The throwaway is asking whether classifier labels *unblock* the per-unit signal — not whether every case produces it.

If 0 of 4 cases improve, the method doesn't work and the production build is wasted effort.

### Throwaway timeline

| Day | Work |
|---|---|
| 1 | Write the classifier client (~50 lines: Anthropic SDK, prompt, parse, char-offset reconstruction); generate the 4 labeled markdown files; eyeball the labels for sanity |
| 2 | Run `run_opportunity.py` against labeled inputs (~60 min wall-clock at full Envelop pipeline costs); aggregate per-unit profile; compare against today's stripped-prose result |
| 3 | Buffer (one round of prompt iteration if labels look wrong, or analysis writeup if labels look right) |

Total: 2-3 days. Cost: ~$10-20 in Envelop tokens for the per-unit run, ~$0.10 for classifier calls. Negligible.

### Outcomes

- **Throwaway passes (≥ 2 of 4 cases gain above-noise units):** I commit to the 2.5-week production build with the five resolved questions above. No further design discussion needed unless the math claim's `ε_label` calibration surfaces something unexpected.

- **Throwaway fails (0 or 1 of 4 cases gain above-noise units):** stop and report. Don't start the production build. Possible failure causes — (a) the classifier produces labels but Kelvin still doesn't see signal because the perturbation primitive (deletion) is structurally confounded as we noted in the morning's analysis, (b) the noise floor on these cases is structurally too high for any unit-level test to clear, (c) the classifier produces unstable labels that re-introduce the noise we hoped to remove. Each failure mode points to a different next experiment.

- **Throwaway ambiguous (exactly 1 of 4 cases gains an above-noise unit):** report and hold; do not commit. The user decides whether that's enough signal to bet 11.5 days on or whether to do a second throwaway with a different perturbation primitive.

### Show-before-build

The throwaway code (~50 lines of classifier + a thin re-run script) plus
its output (4 labeled markdown files + a 1-page comparison report) is
the next deliverable. **No production build starts until you see the
throwaway result and explicitly approve.**

---

---

## The "local library / your provider / your key" contract

Required text for the README and any user-facing doc. The classifier sits behind this contract and never violates it.

> **Kelvin is a local library. The classifier is optional.**
>
> Kelvin runs entirely on your machine. It reads case files, generates perturbations, invokes your pipeline as a shell command, and aggregates results — all locally. Nothing leaves your machine unless you opt into the LLM-assisted classifier (`unitizer.mode: llm` or `auto`), and even then only the input prose you authorize for classification is sent to the provider you chose.
>
> **Your provider, your key.**
>
> Kelvin ships with no credentials. If you enable the classifier, you provide your own API key via environment variable (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, etc.). Kelvin reads the key from the environment, passes it directly to the provider you chose, and never:
> - Stores the key on disk
> - Logs the key (not even in debug mode)
> - Includes the key in cache keys, error messages, telemetry, or any artifact
> - Transmits the key anywhere except to the provider's API
>
> If you don't want any LLM in your evaluation pipeline, write your case files with `## headers` manually (the v0.3 path) and use `unitizer.mode: markdown`. The classifier is a 30-minute-saving convenience, not a requirement.

The contract is enforced by code structure: the API-key value is read into a local variable in the classifier client, passed directly to the provider's SDK, and never assigned to any persistent field, written to any file, or included in any log call. A test in the production validation suite asserts this — `grep` the artifact directory for the first 8 chars of any common API-key prefix (`sk-ant-`, `sk-`, `AIza`) after a classifier run; zero matches required.

---

## What this v0.4 actually delivers — restated cleanly

**Input:** unlabeled prose for any structured-decision pipeline.
**Output:** the same per-unit perturbation-response map the v0.3 methodology already produces — labels are no longer the user's burden. *(Honest framing: deletion shows the pipeline responds to a unit's removal; it does not prove the unit is semantically important. "Perturbation-response" is the operational claim; "causal" is a stronger inference Kelvin does not make.)*
**Method:** an LLM classifier (not a judge) infers unit boundaries and types as a preprocessing step. Existing Kelvin perturbation machinery runs unchanged on the labeled output.
**Failure mode it does not cover:** prose with no recoverable structure at all. The classifier returns `unrecoverable: true` and Kelvin refuses to run (or falls back to per-case σ_baseline grading from today's prototype as a degraded mode).
**What it preserves:** label-free workflow, governing-types-free configuration, per-case + per-unit + per-type sensitivity, Pillar 1/2/3 machinery, the response-geometry vector → maturity grade roadmap.

The methodology doesn't change. What changes is **who provides the structural typing** — moves from human (v0.3) to LLM classifier (v0.4) — and whether the LLM ever sees the pipeline's outputs (it doesn't; it only reads inputs).
