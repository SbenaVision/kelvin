# Kelvin

**An evidence-tracking diagnostic for structured-decision RAG.**

*Is your pipeline reading the evidence, or reacting to its presentation?*

---

## The problem

Production RAG pipelines fail in two directions, and most evals can't tell them apart:

1. **Presentation-reactive** — reorder the retrieved sections and the decision flips, even though the facts are identical.
2. **Evidence-blind** — swap the governing rule for a different valid one and the decision doesn't move, even though it should.

Labeled evaluations are expensive and go stale the moment a prompt or model changes. LLM-as-judge inherits the judge's blind spots and is structurally circular. Neither catches both failures above reliably.

Kelvin asks something stricter than "does the answer look right?": **does the answer move only when the evidence that should determine it moves?**

## How it works

Kelvin applies metamorphic perturbations to the context a pipeline receives — reordering retrieved units, padding with peer units from other cases, and swapping governing units for same-type units from other cases.

The unit boundaries come from the corpus itself. In v1, the user asserts the unit typing by writing markdown section headers (e.g. `## Gate Rule`, `## Market Evidence`); automatic schema inference is the load-bearing v2 piece. See the [whitepaper](docs/whitepaper.md) for the formal claim and its current limits.

The core signal is two measurements, together:

- **Invariance** — reorder or pad. Decision-relevant content hasn't changed; the output shouldn't either. Drift here means the system is responding to presentation, not substance.
- **Sensitivity** — swap a governing unit for a different valid one. The decision criterion has changed; the output should move with it. Insensitivity here means the system isn't reading the governing evidence at all.

**Why the pair matters.** Invariance alone is trivially gamed by a constant-output pipeline (`return "stay_in_validate"` scores 1.0 on every invariance test while being useless). Sensitivity alone can reward noise-reactivity. Only the pair separates a grounded pipeline from both failure modes. This is the central methodological claim — see whitepaper §3.4.

**A concrete failure the tool caught.** On the Envelop venture-assessment case, Kelvin's reorder perturbations flipped the stage decision from `pre-seed` to `seed` whenever the `## Gate Rule` section was moved to the top of the input — classic retrieval-position bias. The facts were identical across reorderings; only the presentation changed. Exactly what the invariance signal is built to expose.

### The Kelvin score

$$K = (1 - \text{Invariance}) + (1 - \text{Sensitivity})$$

Range **[0, 2]**, lower-is-better. **K = 0** means perfectly anchored: invariant where it should be, sensitive where it should be. Higher = more thermal noise, borrowed from the absolute-temperature analogy.

The CLI reports `K` alongside Invariance and Sensitivity in the terminal summary and in `kelvin/report.json`. Per-stage decomposition (retrieval / reranking / generation) is v2.

## Scope

**Good fit — structured-decision RAG.** Pipelines whose output is a categorical or scalar decision over a small set of values:

- Stage-gate assessors (`idea` / `pre-seed` / `seed` / `growth` / `scale`)
- Resume screening (`advance` / `manual_review` / `reject`)
- Underwriting, routing, triage, grading
- Any decision a human would make from a discrete set after reading typed evidence units

The evidence must arrive as discrete, identifiable units (documents, rows, chunks, clauses, tickets) — that's where the metamorphic relations live.

**Not a fit (v1) — prose-output RAG.** Summarization, open QA, chat. Kelvin scores a designated decision field; free-form rationales are recorded for inspection but ignored by the scorer. Tools like RAGAS and ARES target prose RAG and are complementary to Kelvin, not replaced by it.

**Out of scope entirely for v1:** perturbations that rewrite content inside a unit (paraphrasing, synonym swapping). Deferred to a later phase once the structural approach is proven.

## Install

```bash
pip install kelvin-eval
```

Or from source:

```bash
git clone https://github.com/SbenaVision/kelvin
cd kelvin
pip install -e .
```

## Quickstart

**1. Write a `kelvin.yaml` in your working directory:**

```yaml
run: python -m your_pipeline --input {input} --output {output}
cases: ./cases
decision_field: recommendation
governing_types: [gate_rule]
seed: 0
```

- `run` — shell command to invoke your pipeline. Must contain `{input}` and `{output}`.
- `cases` — folder of `*.md` case files. One file per case. Sections start with `## Heading` — each heading becomes a typed unit.
- `decision_field` — the JSON key your pipeline writes. **Must be a top-level key** in the output (no dotted paths — `factsheet.delivery_model` is not supported). If your pipeline produces nested output, flatten it in a thin adapter harness before Kelvin sees it. The value must resolve to a scalar (str / number / bool / null).
- `governing_types` — unit types used for swap perturbations. Normalize to lowercase+underscores (e.g. `Gate Rule` → `gate_rule`).

**2. Write a case file (`cases/acme.md`):**

```markdown
## Gate Rule
Revenue must exceed $10k MRR before Series A.

## Market Evidence
TAM estimated at $2B based on 2024 industry report.

## Customer Signal
Three enterprise pilots confirmed willingness to pay $500/mo.
```

**3. Run:**

```bash
kelvin check
```

Optional flags: `--only <case_name>` to run a single case, `--seed 42` to override the seed.

**4. Inspect results:**

```bash
jq '.invariance, .sensitivity, .sensitivity_by_type' kelvin/report.json
diff kelvin/acme/baseline/output.json kelvin/acme/perturbations/swap-gate_rule-01/output.json
```

Everything lands under `./kelvin/`:

| Path | Contents |
|------|----------|
| `kelvin/report.json` | Cross-case scores: invariance, sensitivity, sensitivity_by_type, warnings |
| `kelvin/<case>/report.json` | Per-case: baseline decision, every perturbation's distance and notes |
| `kelvin/<case>/baseline/` | Unperturbed input + output |
| `kelvin/<case>/perturbations/<variant>/` | Each perturbation's input + output |

**Exit codes:** `0` success · `1` config or cases-dir problem · `2` decision field missing or every baseline failed.

## Who it's for

- Teams shipping stage-gate, screening, triage, routing, or grading pipelines that need a repeatable evidence-tracking signal in CI.
- Engineers debugging why a model upgrade or prompt change quietly shifted a decision distribution.
- Anyone who has seen a production RAG "work" on spot-checks and later found it was reacting to retrieval position rather than content.

## Status

| Component | Status |
|-----------|--------|
| Core perturbations (`reorder`, `pad`, `swap`) | ✅ Done |
| Scorer — Invariance + Sensitivity | ✅ Done |
| CLI (`kelvin check`) | ✅ Done |
| Terminal reporter | ✅ Done |
| Kelvin score `K` (formalized, emitted) | ✅ Done |
| Grounded-vs-degenerate empirical table (Table 3) | ✅ Done |
| Corpus scaled to n=6 realistic cases | ✅ Done |
| Envelop harness — exponential backoff on transient 5xx | ✅ Done |
| Pad split (`pad_length` / `pad_content`) | ✅ Done |
| Footgun warnings (governing-type validation, type discovery, single-case banner, cost preamble) | ✅ Done |
| On-disk invocation cache | 🔜 v0.2 |
| Rule-condition swap (`swap_condition`) | 🔜 v0.3 — design in progress |
| HTML / markdown reporters | 🔜 Upcoming |
| `kelvin init` wizard | 🔜 Upcoming |
| CI/CD integration | 🔜 Upcoming |
| Automatic schema inference | 🔜 v2 (load-bearing) |
| Stage decomposition (retrieval / reranking / generation) | 🔜 v2 |

## Research

The formal treatment of Kelvin's paired metamorphic diagnostics is in [docs/whitepaper.md](docs/whitepaper.md).


## License

Apache 2.0. See [LICENSE](LICENSE).
