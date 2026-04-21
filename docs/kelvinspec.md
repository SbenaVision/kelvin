# Kelvin

**An unsupervised correctness signal for RAG pipelines.**

Your pipeline should stay calm when nothing important changes, and react when something important does. Kelvin measures both.

---

## The idea in one paragraph

RAG pipelines read corpora of discrete, typed units — interviews, clauses, rules, records. That structure lets us define metamorphic relations: reordering units shouldn't change the answer, swapping a governing unit should. Kelvin runs these perturbations and measures the result. No labels. No judge model.

The stronger version of this idea uses a full schema to derive typed units and validity constraints automatically. **In v1, types come from user-declared markdown section headers** — a lightweight convention that approximates the schema story. Good enough to produce a real signal, honest enough not to oversell.

---

## What Kelvin measures

Kelvin produces two **diagnostic signals** — not truth metrics. They tell you where to look, not whether your pipeline is correct.

**Invariance** — does the pipeline stay stable when irrelevant things change?
Reorder units, pad with unrelated ones from other cases. The facts are identical; the output should be too. Drift means the pipeline is reacting to presentation, not substance.

**Sensitivity** — does the pipeline react when relevant things change?
Swap a governing unit for a different valid one drawn from another case. The facts changed; the output should too. Flatness means the pipeline isn't reading that evidence at all.

Either signal alone is a trap. A pipeline that always says "unclear" is perfectly invariant and useless. A pipeline that flips on every breeze is sensitive and unusable. Understanding requires both.

---

## How a developer uses it

```
$ pip install kelvin
$ kelvin init     # 30-second interactive setup
$ kelvin check    # run perturbations, print report
```

**`kelvin init`** asks four things and writes `kelvin.yaml`:
1. Shell command to invoke your pipeline (with `{input}` and `{output}` placeholders)
2. Where your cases live
3. Name of the decision field in your pipeline's output JSON
4. Which unit types are governing (used for swap perturbations)

`init` stays offline — it does not invoke the pipeline. For governing-types selection, `init` scans the cases directory to autodetect unit types and presents them as a multi-select checklist. If the directory doesn't exist or is empty, `init` creates it and falls back to free-text (the user edits `kelvin.yaml` later once cases exist).

**`kelvin check`** runs end-to-end:
1. Parse each case into typed units.
2. Run the baseline for the first case. Validate the decision field is present in the output; if not, abort the run with a clear error naming the expected and actual fields. No perturbations generated yet — fail fast before spending compute.
3. Run remaining baselines. If any baseline fails (non-zero exit, missing output file, unparseable JSON, or missing decision field), skip that case entirely with a distinct error. Baseline failures are reported separately from perturbation failures.
4. Generate perturbations per case.
5. Invoke the pipeline once per perturbation via the shell command.
6. Score outputs by comparing the decision field to baseline.
7. Print a terminal report. Write a self-contained HTML report.

If every case's baseline fails, `check` exits non-zero.

**Flags:**
- `--only <case>` — run on a single case.
- `--seed <int>` — override the seed from `kelvin.yaml`.

Everything visible on disk. No hosted service.

---

## Input contract

**One markdown file per case.** `ventures/acme.md`, `ventures/zeta.md`. The filename (without `.md`) is the case name.

**`## Section` headers declare typed units.** Each header starts a new unit; the header text becomes the unit type, normalized (lowercased, whitespace → underscore). Content before the first header is treated as untyped preamble and never perturbed; it stays pinned at the top of the case for all perturbation kinds.

```markdown
Preamble text. Optional. Never perturbed. Always pinned at top.

## Interview
First customer interview content...

## Interview
Second customer interview content...

## Gate Rule
Stage-gate criterion content...

## Budget Assumption
Budget figures and reasoning...
```

Two `## Interview` headers produce two units of type `interview`. The same normalization applies to `## interview`, `## INTERVIEW`, and `## Interview ` — all collapse to `interview`. Use consistent header text for units of the same type.

---

## Pipeline contract

Kelvin invokes a shell command once per baseline and once per perturbation:

```yaml
run: python -m envelop.assess --input {input} --output {output}
```

- `{input}` — path to a markdown file Kelvin writes before the call.
- `{output}` — path where the pipeline must write a JSON file before exiting.
- Output JSON must contain the decision field named in `kelvin.yaml`.

**Failure handling:** A pipeline invocation counts as failed if any of the following happen:
- Non-zero exit code.
- Output file not created.
- Output file is not valid JSON.
- Output JSON is missing the declared decision field.

For **perturbations**, failures are logged and the run continues; failed perturbations don't contribute to the score. For **baselines**, failures are a hard stop for that case — no perturbations are attempted.

Language-agnostic. Framework-agnostic. Works for any pipeline invocable as a command.

---

## `kelvin.yaml` example

```yaml
run: python -m envelop.assess --input {input} --output {output}
cases: ./ventures
decision_field: recommendation
governing_types: [gate_rule]
seed: 0
```

Five keys. Written by `kelvin init`. Edit by hand if needed.

**The seed** governs Kelvin's perturbation choices — which units to reorder, which to pad with, which governing units to swap. It does not govern the user's pipeline. A non-deterministic pipeline (e.g., an LLM with temperature > 0) will produce different outputs across seeded Kelvin runs; that's expected behavior, not a Kelvin bug.

---

## Perturbations (v1)

Three kinds. Target counts per case, capped by data availability.

**Reorder.** Shuffle the unit order within the case. Preamble stays first. 3 variants per case, deterministic by seed. If a case has fewer than 2 units, reorder is skipped for that case with a warning.

**Pad.** Insert 2–4 units drawn from *other cases in the same run* (never from the case being perturbed) into the current case. Units are sampled regardless of type and placed at random positions. 3 variants per case. If the peer pool has fewer than 2 units total, pad is skipped with a warning; if fewer than 4, the per-variant insert count caps at what's available.

**Swap.** Replace one unit of a governing type with a unit of the same type drawn from another case (without replacement from the peer pool). Target: **3 swaps per governing type per case**. If a case has fewer than 3 units of a governing type, run as many swaps as units exist. If the peer pool has no same-type units, skip swaps for that type with a warning. Type match is the only validity check in v1 — a deliberately crude approximation. A future version infers governing types and enforces semantic validity.

**Visibility of caps and skips:** Every cap (reduced sample) and every skip (perturbation not run) appears in the terminal report and HTML report. Silent capping is forbidden — the user must always see the effective sample size their scores are computed on.

**Edge cases:**
- Only one case in the run → pad and swap are skipped (no peers to draw from). Only reorder runs. Warning shown.
- Case has no units of a governing type → swap skipped for that case. Warning shown.

---

## On-disk layout

After a run, `./kelvin/` contains:

```
kelvin/
  <case-name>/
    baseline/
      input.md                  # the unperturbed case
      output.json               # the baseline pipeline output
    perturbations/
      reorder-01/               input.md  output.json
      reorder-02/               input.md  output.json
      reorder-03/               input.md  output.json
      pad-01/                   input.md  output.json
      ...
      swap-gate_rule-01/        input.md  output.json
      swap-gate_rule-02/        input.md  output.json
      swap-gate_rule-03/        input.md  output.json
      swap-policy_clause-01/    input.md  output.json
      ...
    report.md                   # per-case human-readable diagnosis
    report.json                 # per-case machine-readable scores
  report.html                   # cross-case summary, self-contained
  report.json                   # cross-case machine-readable scores
```

Every step inspectable with `cat`, `diff`, `grep`, `git`. Nothing magic. The init wizard offers to add `kelvin/` to `.gitignore`.

---

## The report

The terminal output is the product. It must fit in one screenshot and communicate what was checked, whether the pipeline is behaving, and where to look if not.

```
┌─ Kelvin Report ──────────────────────────────────────────┐
│                                                           │
│   Invariance    0.82                                      │
│   (18 perturbations across 6 cases)                       │
│   Does your pipeline stay calm when nothing              │
│   important changes?                                      │
│   ████████░░   mostly — good                              │
│                                                           │
│   Sensitivity   0.31                                      │
│   (9 swaps across 3 governing types)                      │
│   Does your pipeline react when something                │
│   important changes?                                      │
│   ███░░░░░░░   barely — concerning                        │
│                                                           │
│   ⚠  Gate rules are being ignored.                       │
│      Swapping the governing gate_rule for a              │
│      different valid one didn't change the               │
│      recommendation in 4 of 5 cases.                     │
│                                                           │
│   Diagnostic signals — not truth metrics.                │
│   → kelvin/report.html for per-case drill-down           │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

Sample counts on both scores are mandatory. Users over-interpret small-sample scores otherwise — "Sensitivity 0.0" from 2 swaps means something very different than from 30.

The HTML report is a single static file. It includes:
- Per-case drill-down with input/output diffs.
- A **per-type sensitivity table** — the cross-type average hides which governing type is driving the signal; seeing `gate_rule 0.15` vs `policy_clause 0.67` is the insight users act on.
- A stability heatmap by unit type.
- A methodology section at the bottom: what each perturbation does, how distance is computed, what "diagnostic signal, not truth metric" means, and what the seed controls and doesn't.

Open in any browser. Commit to a PR.

---

## Scoring

Scoring is a **diagnostic signal**, not a metric. The spec phrasing is deliberate: "indicator," "diagnostic," never "accuracy" or "correctness."

**Distance function** operates on the declared decision field only. Other fields (prose, narrative) are shown in the report for context but don't affect scores.

- Enum or string field: `distance = 0 if equal else 1`. Equality is **exact match** — case-sensitive, whitespace-sensitive. Users who want normalization can apply it in their pipeline output.
- Numeric field: `distance = min(1, |a − b| / max(|a|, |b|, 1))`.
- Arrays, nested objects: unsupported in v1 — `kelvin check` fails fast on the first baseline with a clear error if the decision field is non-scalar.

**Aggregation:**
- `Invariance = 1 − mean(distance(baseline, perturbed))` over reorder + pad perturbations.
- `Sensitivity = mean(distance(baseline, perturbed))` over swap perturbations.
- Overall sensitivity is a uniform mean across all swaps regardless of governing type. Per-type sensitivity is computed separately and surfaced in the HTML report (see reports section).

Scoring is a pluggable function — implementers structure the code so a better scorer can replace the default without touching the runner.

---

## Execution

**Serial.** One perturbation at a time. v1 does not parallelize; the user controls cost with `--only <case>` during iteration. Parallel execution is a v2 concern.

**No caching.** Every run re-invokes the pipeline for every baseline and perturbation. v2 may add content-hash caching. v1 stays simple.

**Working directory.** `kelvin check` runs from the current directory. `./kelvin/` is written there. `kelvin.yaml` is read from there.

---

## Scope

**In (v1):**
- Markdown-with-headers case format (one file per case).
- Three perturbation kinds: reorder, pad, swap.
- Shell-command pipeline invocation.
- Serial execution, no caching.
- Terminal report + self-contained HTML report with per-type sensitivity breakdown.
- Structured-field scoring (enum, string, numeric).
- Deterministic by seed, CLI flag override.

**Out (v2 and beyond):**
- Stage decomposition (retrieval vs. generation vs. reranking).
- Semantic-equivalence scoring via LLM judge.
- Parallelism and caching.
- Perturbation packs for specific verticals.
- Framework-native adapters (LangChain, LlamaIndex).
- Dashboards, history, alerts — anything continuous or hosted.
- Schema-inferred unit types and validity constraints.

---

## Principles

1. **The corpus is the oracle.** No labels, no judge model, no circular reasoning.
2. **Two numbers, never one.** Invariance and sensitivity, always together.
3. **Diagnostic, not definitive.** Signals point; humans decide.
4. **Everything on disk.** If Kelvin breaks, `cat` and `diff` debug it.
5. **The report is the product.** Optimize for the screenshot, not the feature list.
6. **Never cap silently.** The user must always see the effective sample size.
7. **Minimal surface.** One command, one config file, one optional override. Every flag earns its place.

---

## License

Apache 2.0.

---

## The name

Kelvin is the absolute temperature scale. A Kelvin of zero would mean perfectly anchored — invariant where it should be, sensitive where it should be. Higher scores mean more thermal noise: the pipeline is reading presentation, not substance.
