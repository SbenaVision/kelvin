# Kelvin

**An unsupervised correctness signal for RAG pipelines.**

*Is your AI understanding your data, or guessing?*

---

## The problem

Every team shipping production RAG hits the same wall: output variance with no reliable way to measure it. Labeled evaluations are expensive to build and stale the moment a prompt or model changes. LLM-as-judge inherits the judge model's blind spots and is structurally circular.

Existing tools measure whether outputs *look* right. Kelvin measures something stricter: whether outputs *depend on the right things*.

## How it works

Kelvin applies structure-derived metamorphic perturbations to the context a pipeline receives — reordering retrieved units, padding with known-irrelevant units, duplicating or dropping non-essential units, swapping governing units for different valid ones from the same corpus.

Because these transformations are defined over the unit boundaries the corpus already provides, fact-preservation is guaranteed by construction. The facts don't move, so the output shouldn't either.

The core signal is two measurements together:

- **Invariance** — reorder, pad, drop non-essentials. The facts haven't changed; the output shouldn't either. Drift here means the system is responding to presentation, not substance.
- **Sensitivity** — swap a governing unit for a different valid one. A fact has changed; the output should move with it. Insensitivity here means the system isn't reading the facts at all.

### The Kelvin score

Borrowed from the absolute temperature scale: **a Kelvin of zero means the pipeline is perfectly anchored** — invariant where it should be, sensitive where it should be. Higher scores mean more thermal noise.

Kelvin decomposes the score across pipeline stages (retrieval, reranking, generation) so instability can be localized, not only detected.

## Scope

Kelvin targets RAG pipelines whose inputs are discrete, identifiable units: documents in a folder, rows in a database, chunks in a vector store, clauses in a contract, tickets in a queue. Anywhere retrieval returns distinct objects with identity, the structure of that object set provides the metamorphic relations Kelvin needs.

**Out of scope for v1:** perturbations that require rewriting content inside a unit (paraphrasing, synonym swapping). These belong in a later phase once the structural approach is proven.

## Install

```bash
pip install kelvin
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
- `decision_field` — the JSON key your pipeline writes. Must be scalar (str / number / bool / null).
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

- Developers shipping production RAG who want a repeatable correctness signal in CI.
- Teams debugging why a model upgrade or prompt change quietly degraded their pipeline.
- Anyone who has shipped a "working" RAG system and learned in production it wasn't.

## Status

| Component | Status |
|-----------|--------|
| Core perturbations (reorder, pad, swap) | ✅ Done |
| Scorer + stage decomposition | ✅ Done |
| CLI (`kelvin check`) | ✅ Done |
| Terminal / HTML reports | 🔜 PR 3 |
| `kelvin init` wizard | 🔜 Upcoming |
| CI/CD integration | 🔜 Upcoming |

## License

Apache 2.0. See [LICENSE](LICENSE).
