# Semantic Perturbations — Design (separate from boundary classifier)

**Status:** design only. No code. Companion to `docs/v0_4_classifier_design.md`.

**Problem.** Today's perturbations are *mechanical* — delete a unit, reorder, flip a number, swap a comparator. They probe presence/absence and surface form. They cannot probe **intensity** or **meaning preservation**. A pipeline that grades the same regardless of "500 paying customers" vs "50 interested prospects" looks identical to mechanical perturbations even though it's failing to weight evidence appropriately.

**Goal.** A second perturbation family that probes intensity gradients per unit type. A mature pipeline produces a monotonic, proportional response across the gradient. An immature pipeline produces a flat or jagged response.

**Tension with positional tagging.** v0.4's boundary classifier was just locked in as **positional tags only** (p1, p2, ...) — no semantic vocabulary. Semantic perturbations require knowing the *type* of each unit (traction vs team vs gate_rule), because intensity gradients are type-specific. This means semantic perturbations require a **second** preprocessing layer: a semantic typer that overlays type metadata onto the positional tags. The two layers are independent — boundary classification works without typing; typing requires boundaries to attach to. The composition is clean: `unit = (positional_tag, semantic_type?, content)`. The `semantic_type` is `None` if typing is not enabled.

---

## 1. Taxonomy — per-type intensity gradients

The intensity axis is **−2 (strong-weaken) → −1 → 0 (neutralize) → +1 → +2 (strong-strengthen)**, with an optional separate **contradict** perturbation outside the axis. Five points on the axis is the working design — fewer collapses signal, more is expensive.

The gradient definition is type-specific. Below: each type, the dimension(s) the gradient operates on, and concrete examples.

### `traction`

**Gradient dimension:** evidence quality × magnitude of demand.

| Intensity | Form |
|---|---|
| +2 strong-strengthen | "5000 paying customers, $50M ARR, net-negative churn" |
| +1 mild-strengthen | "1500 paying customers, $5M ARR, healthy retention" |
| 0 neutralize | "early traction with paying customers" (qualitative, no magnitude) |
| −1 mild-weaken | "200 interested prospects, 5 LOIs" |
| −2 strong-weaken | "no customers yet, building waitlist" |
| Contradict | "we tried selling and customers refused at every price point" |

### `team`

**Gradient dimension:** experience × commitment × completeness.

| Intensity | Form |
|---|---|
| +2 | "Three founders full-time. CEO sold last company for $200M, CTO ex-FAANG principal, COO scaled prior co to $50M ARR." |
| +1 | "Two founders full-time. Both ex-senior at relevant scale-ups." |
| 0 | "Small team currently building" (no detail on stage or commitment) |
| −1 | "Two founders part-time, exploring full-time commitment" |
| −2 | "One founder, first-time, evening/weekend work" |
| Contradict | "Founder is actively interviewing for full-time roles elsewhere" |

### `market_evidence`

**Gradient dimension:** measurement granularity × size × evidence specificity.

| Intensity | Form |
|---|---|
| +2 | "Bottom-up SOM of $400M, 8000 named accounts at avg $50K ACV; survey of 200 prospects gave 73% buying intent" |
| +1 | "$2B TAM cited; SAM derived from industry report; specific niche identified" |
| 0 | "Large market for this category" (no figure, no source) |
| −1 | "Niche segment of unknown size; market education needed" |
| −2 | "No market data; assuming demand exists based on founder intuition" |
| Contradict | "Customers explicitly said they would not buy this" |

### `gate_rule` (rule-shaped governing units)

Two distinct semantic perturbations because gate rules are compositional:

**(a) Condition severity gradient** (rule itself):
| Intensity | Form |
|---|---|
| +2 | "Requires 100 paying customers, 3 reference accounts, $5M ARR" |
| +1 | "Requires 30 paying customers, 1 reference account, $1M ARR" |
| 0 | "Requires demonstrated market traction" |
| −1 | "Requires 5 paying pilots" |
| −2 | "Requires 1 letter of interest" |

**(b) State-meeting gradient** (the assertion that conditions are/aren't met):
| Intensity | Form |
|---|---|
| +2 | "All conditions are met with significant headroom" |
| +1 | "All conditions are met at the threshold" |
| 0 | "Some conditions are met; others in progress" |
| −1 | "Most conditions are not yet met" |
| −2 | "None of these conditions are currently met" |

(b) is essentially the corpus's existing baseline variation — most v0.3 cases differ exactly along (b). Including it in the perturbation suite tests pipeline sensitivity to this axis explicitly.

### `unit_economics`

**Gradient dimension:** margin × CAC/LTV ratio × runway.

| Intensity | Form |
|---|---|
| +2 | "75% gross margin, LTV/CAC 4.5×, 36-month runway, profitable today" |
| +1 | "55% gross margin, LTV/CAC 2.0×, 18-month runway" |
| 0 | "Standard SaaS economics in line with the category" |
| −1 | "30% gross margin, LTV/CAC near 1, 9-month runway" |
| −2 | "Negative gross margin, no path to LTV/CAC > 1, 3-month runway" |

### `venture_description` and `target_customer`

These types are **less amenable to intensity gradients** than the others — they're definitional rather than evidence-bearing. Mechanical perturbations (paraphrase, rhetorical injection) cover them. Semantic perturbations on these types are deferred or skipped.

### `problem` and `solution`

| Intensity | Form |
|---|---|
| +2 | "Problem affects 80M people; current solutions cost $X and fail Y% of the time" |
| 0 | "Problem in this category" |
| −2 | "Edge-case problem affecting niche population" |

Lower-priority: these get useful gradients but the type is more often paraphrased than scaled.

### `business_model`

**Gradient dimension:** clarity × validation.

| +2 | Validated pricing tiers, customer-paid pilots converting at known rate |
| 0 | Stated pricing, no conversion data |
| −2 | "Monetization to be determined" |

### Type coverage summary

| Type | Gradient quality | Priority for v0.5+ |
|---|---|---|
| `traction` | Strong (clear axis) | High |
| `team` | Strong | High |
| `market_evidence` | Strong | High |
| `gate_rule` | Strong (two axes) | High |
| `unit_economics` | Strong | High |
| `problem` | Moderate | Medium |
| `solution` | Moderate | Medium |
| `business_model` | Moderate | Medium |
| `venture_description` | Weak (definitional) | Skip |
| `target_customer` | Weak (definitional) | Skip |

A v0.5+ release ships gradients for the **High** types and skips the others — semantic perturbations don't try to cover everything.

---

## 2. LLM-prompting approach

Three architecture options, picking one:

### Option A — Per-perturbation prompt (one LLM call per intensity point per unit)

Pro: simple prompt, type-agnostic.
Con: 5 LLM calls per typed unit. ~70 typed units × 5 = 350 LLM calls per corpus. Slow + expensive.

### Option B — Batch prompt (one LLM call per typed unit, generates all 5 intensities) ✅ recommended

One call yields the full intensity ladder. Output is structured JSON with 5 variants.

**Prompt sketch:**

```
SYSTEM:
You are generating intensity-graded perturbations of a {TYPE} unit for a
measurement framework. Your job is to produce 5 variants of the input unit
spanning strong-strengthen → strong-weaken on the type-appropriate gradient.

You DO NOT:
- Evaluate, score, or judge the input.
- Add commentary, advice, or interpretation.
- Change the venture's identity (company name, founder names, product
  category remain the same).

You ONLY:
- Produce 5 perturbed variants at intensities +2, +1, 0, -1, -2.
- Preserve facts not directly affected by the gradient. If the original
  mentions specific people, places, dates not on the gradient axis, keep
  them verbatim.

Gradient definition for {TYPE}:
  +2 = {TYPE-specific strong-strengthen guidance}
  +1 = {TYPE-specific mild-strengthen guidance}
   0 = {TYPE-specific neutralize guidance}
  -1 = {TYPE-specific mild-weaken guidance}
  -2 = {TYPE-specific strong-weaken guidance}

USER:
Original {TYPE} unit:
"""
{CONTENT}
"""

Generate the 5 variants. Each variant must:
- Read as natural prose at the same length scale as the original (±50%).
- Differ from the original only along the gradient axis.
- Be internally consistent (numbers, claims, timeframe).
- Use the submit_variants tool to return all 5.
```

**Tool schema:**
```json
{
  "name": "submit_variants",
  "input_schema": {
    "variants": [
      {"intensity": 2, "content": "..."},
      {"intensity": 1, "content": "..."},
      {"intensity": 0, "content": "..."},
      {"intensity": -1, "content": "..."},
      {"intensity": -2, "content": "..."}
    ]
  }
}
```

Per-call cost at Haiku rates: ~$0.005 per typed unit (input+output ~3k tokens). For 70 typed units = $0.35 per corpus. Negligible.

### Option C — Template-driven per-type prompts

A separate prompt per type, hand-engineered. Pro: best output quality. Con: prompt-management nightmare, ties to a closed type vocabulary (which conflicts with the user's stated direction).

**Going with Option B.** Type-specific gradient guidance is parametrized into one generic prompt; new types added by extending the parameter table, not the prompt template.

### Validation requirement (load-bearing)

Generated variants must pass two checks before being used as perturbations:

1. **Fact-preservation check.** Named entities (company name, founder names) must be preserved verbatim. A regex/NER pass before accepting the variant.
2. **Magnitude check.** For `traction`, `unit_economics`, `market_evidence`, the variant's numerics must be on the right side of the original. If +2 traction is supposed to have *higher* customer count than original but the LLM wrote a *lower* one, reject and retry.
3. **Length check.** Variant length within ±50% of original — no compression or expansion that introduces noise of its own.

If 2/3 retries fail validation, the variant is dropped (not used) and a `caps` warning recorded — semantic-perturbation samples for that intensity point on that unit are missing, scoring degrades gracefully.

---

## 3. Belongs in v0.4 or v0.5+? — **v0.5+, definitely not v0.4**

Reasons:

**Methodological reason.** v0.4's premise is that mechanical perturbations + structural cues are *sufficient* for the per-unit perturbation-response map. The throwaway running now tests this with positional tags. If it passes, the simplest design wins. Adding semantic perturbations to v0.4 muddles that test — we wouldn't know whether positional tags or semantic perturbations were the unblocking factor.

**Engineering reason.** Semantic perturbations are a substantial workstream (taxonomy, prompt engineering, validation, integration) — roughly the same scale as v0.4 production. Bundling them into v0.4 stretches the 2.5-week target to 5+ weeks and creates a monolithic release.

**Sequencing logic.**

| Release | What | What's tested |
|---|---|---|
| **v0.4** (in design now) | Positional unitization → mechanical perturbations | "Are content-free unit markers + mechanical perturbations enough to recover per-unit signal?" |
| **v0.4.x** (if v0.4 throws ambiguity) | Level 2 (statement-level) unitization | "Does finer-grained boundaries help?" |
| **v0.5** (maturity rubric) | Rubric over response geometry | "Can we grade pipelines from existing measurements?" |
| **v0.6** (semantic perturbations) | Type overlay + intensity-graded perturbations | "Does intensity-response add to the maturity grade?" |
| **v1.0** (EOS certification) | Catalogue-relative finite-sample guarantees | "Can we publish defensible claims?" |

Semantic perturbations sit in **v0.6** in this ordering: built on top of an already-grading system (v0.5), valuable when the rubric needs more axes to discriminate maturity, not earlier.

**One nuance.** v0.5's maturity rubric might *itself* show that mechanical-only perturbations don't separate maturity well at the upper end (i.e., grade 4 vs grade 5 ventures can't be distinguished by mechanical sensitivity alone). If so, semantic perturbations become urgent — promoted from v0.6 to v0.5.x. The decision waits on v0.5 data.

---

## 4. Cost and complexity

### Engineering complexity

| Component | Days |
|---|---:|
| Semantic typer (LLM classifier that overlays types onto positional tags) | 2 |
| Semantic perturber (LLM call + JSON parse + per-type gradient table) | 3 |
| Validation pipeline (fact-preservation, magnitude monotonicity, length) | 3 |
| Per-type gradient-table tuning (8 high-priority types × ~1 day each, but most can copy a generic template) | 4 |
| Integration into Kelvin's runner (new perturbation kinds, scorer extensions for intensity-response curves) | 3 |
| Validation suite (cross-replay stability of generated variants, pipeline monotonicity tests on a known-good reference) | 3 |
| Documentation + examples | 1 |
| Buffer | 3 |
| **Total** | **~22 days ≈ 4-5 calendar weeks** |

This is roughly the same scale as v0.4 production. Treating it as a separate release (v0.6) preserves the option to ship it later or not at all if v0.5's rubric proves sufficient.

### Run-time cost

For a 10-case corpus, ~7 typed units per case = 70 typed units:

| Cost component | Per-corpus cost |
|---|---|
| Semantic typer LLM calls (1 per unit, batched possible) | ~70 calls × $0.003 = ~$0.20 |
| Semantic perturber LLM calls (Option B: 1 per typed unit, returns 5 variants) | ~70 calls × $0.005 = ~$0.35 |
| Pipeline calls (5 intensities × N replays × 70 units) | dominant cost |

At N=5 replays per perturbation: 5 × 5 × 70 = 1,750 pipeline calls per corpus.
At today's Envelop full-pipeline cost (~$0.05/call): ~$90 per corpus.

This is **~10× the v0.4 production run cost**. Semantic perturbations are the expensive layer of the stack — you'd run them on critical corpora, not every commit.

### Run-time wall-clock

At ~30s per pipeline call with 3 workers: 1,750 × 30 / 3 ≈ 4.8 hours wall-clock per corpus. Worth budgeting for overnight runs in CI rather than developer-loop testing.

### Where the cost goes

- **80% pipeline calls** (perturbed inputs sent to the pipeline being graded)
- **15% validation pipeline** (ensuring generated variants pass quality gates)
- **5% LLM perturbation generation** (the cheap part)

Optimization levers if cost matters: reduce intensity points (5 → 3), reduce replays per intensity (5 → 3), reduce typed-unit coverage (top 3 types only).

---

## Summary — the four asks, answered

| # | Ask | Answer |
|---|---|---|
| 1 | Taxonomy of semantic perturbations per type | 8 unit types with ranked gradient quality; high-priority (traction, team, market, gate_rule, unit_economics) get full 5-point intensity ladders; medium-priority (problem, solution, business_model) get gradients but lower priority; weak-priority (venture_description, target_customer) skipped — definitional, not evidence-bearing. |
| 2 | LLM prompting approach | **Option B (batch prompt)**: one LLM call per typed unit, returns 5 variants spanning intensity −2 to +2 via structured tool-use output. Generic prompt parameterized by type-specific gradient guidance. Fact-preservation + magnitude-monotonicity + length validation gates before variants are used as perturbations. |
| 3 | v0.4 or v0.5+? | **v0.6**, in the sequencing v0.4 → v0.4.x (if needed) → v0.5 (maturity rubric) → v0.6 (semantic perturbations) → v1.0 (EOS). Could promote to v0.5.x if v0.5's rubric demonstrates mechanical-only perturbations can't separate the upper grades — decision waits on v0.5 data. |
| 4 | Cost & complexity | **~4-5 calendar weeks engineering** (22 working days; same scale as v0.4 production). **~$90 per 10-case corpus run-time**, dominated by pipeline calls (1,750 per run); ~5 hours wall-clock with 3 workers. ~10× the v0.4 cost — built for critical-corpus runs, not every developer commit. |

## Decisions — locked (April 26, 2026)

All four resolved by SBA. Doc updated to reflect.

### 1. v0.4 reserves the schema fields

**Decision:** v0.4's `signature.json` reserves keys for semantic-response data, populated as `null` until v0.6 ships. Cheap now (a few null fields), expensive later (schema migration if added retroactively).

**Reserved keys** (v0.4 emits these as `null`; v0.6 populates):
```json
{
  "semantic_response": {
    "by_type": null,                  // {type → {intensity → {mean, sample}}}
    "monotonicity_score": null,       // per type, fraction of monotonic responses
    "contradict_response": null       // {type → {mean, sample}}
  }
}
```

To carry into the v0.4 production build (the `signature.json` writer in `check.py`).

### 2. Gradient table review deferred to v0.5 data

**Decision:** Park gradient-per-type tuning until v0.5 ships and produces data on which axes the maturity rubric actually needs. The structure (intensity ladders + contradict) is sound; the specific examples per type need a venture-assessment domain expert and shouldn't be guessed pre-v0.5.

For v0.6 planning purposes the doc's tables stand as a sketch. They will be replaced before any v0.6 build begins.

### 3. Contradict is a separate perturbation

**Decision:** Contradict lives outside the −2 to +2 intensity axis. A mature pipeline should respond *differently* to "weak version" (intensity −2) vs "claim that contradicts the original" — these are not points on the same axis.

**Cost adjustment:** 6 perturbations per typed unit instead of 5 (intensity ladder × 5 + contradict × 1). Per-corpus pipeline calls: 6 × 5 replays × 70 typed units = **2,100** (up from 1,750). Per-corpus cost: ~**$105** (up from ~$90). Wall-clock: ~5.8 hours with 3 workers. Engineering: +0.5 day to handle contradict as its own perturbation kind in the runner. Increase is within the v0.6 budget.

### 4. Separate LLM calls for typer and perturber

**Decision:** The semantic typer (positional unit → type label) and the semantic perturber (typed unit → 5 intensity variants + 1 contradict) are separate LLM calls. Different tasks, different failure modes; coupling them means a typer error cascades into a perturber error and the cause is hard to localize.

**Cost adjustment:** adds the typer's ~70 calls × $0.005 ≈ **$0.35 per corpus** — negligible compared to pipeline-call cost. **Engineering:** ~+1 day for typer scaffolding (own client, own validation gate). Still within v0.6 budget.

**Architectural implication:** the v0.6 preprocessing stack has three composable layers, each independently testable:
- Boundary classifier (positional tags) — v0.4 ✓
- Semantic typer (overlays types onto positional tags) — v0.6, separate LLM call
- Semantic perturber (generates intensity-graded variants per typed unit) — v0.6, separate LLM call

A failure at any layer surfaces at that layer; no cross-layer cascading.

---

## Updated cost & complexity (after decisions 3 + 4)

| Component | Days |
|---|---:|
| Semantic typer (separate LLM call, type assignment, validation) | 3 |
| Semantic perturber (LLM call, JSON parse, per-type gradient table) | 3 |
| Validation pipelines (per layer: type stability, fact-preservation, magnitude monotonicity, length, contradict-vs-axis distinction) | 4 |
| Per-type gradient-table tuning (deferred per decision 2; placeholder budget) | 4 |
| Integration into Kelvin's runner (intensity-response perturbation kinds, contradict as separate kind, scorer extensions) | 3.5 |
| Validation suite (cross-replay stability, monotonicity tests, contradict-vs-axis discrimination check) | 3 |
| Documentation + examples | 1 |
| Buffer | 3 |
| **Total** | **~24.5 days ≈ 5 calendar weeks** |

| Run-time | Per-corpus |
|---|---|
| Typer LLM calls | ~$0.35 |
| Perturber LLM calls | ~$0.35 |
| Pipeline calls (6 perturbations × 5 replays × 70 typed units) | ~$105 (Envelop full-pipeline rates) |
| **Total** | **~$106 per 10-case corpus, ~5.8 hours wall-clock with 3 workers** |

---

*Design version 2, 2026-04-26. Decisions locked. Parked until v0.6 — do not start building. Throwaway results pending.*
