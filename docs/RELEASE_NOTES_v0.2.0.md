# Kelvin v0.2.0 — the paired signal is empirically demonstrated

**This release moves Kelvin's central methodological claim from an analytical prediction to a reproducible empirical artifact, and brings the marketing and whitepaper language in line with what the tool actually measures.**

## Headline result

Grounded vs. degenerate on the same six-case suite, 60 perturbations each, seed = 0 — reproducible in under ten seconds with `cd experiments/tier3 && ./run.sh`:

| Pipeline | Invariance | Sensitivity | Kelvin score `K` |
|---|---|---|---|
| Grounded (rule-based stand-in) | 0.85 | 0.67 | **0.48** |
| Degenerate (constant output) | 1.00 | 0.00 | **1.00** |

**ΔK = 0.52.** The degenerate pipeline lands at `K = 1.00` exactly, matching the whitepaper §3.4 analytical prediction pinned in the test suite. Invariance alone would barely distinguish the two pipelines (0.15 apart); sensitivity alone needs governing-unit declarations to be meaningful. The paired scalar surfaces the separation in a single number — the methodological claim is no longer just argued in §3.4, it is executed in `experiments/tier3/`.

## What's new

- **Kelvin score `K = (1 − Invariance) + (1 − Sensitivity)`** — emitted in the terminal report, `kelvin/report.json`, and the Python API. Range `[0, 2]`, lower = more anchored. `None` when either component is undefined (no default substitution).
- **Pad split:** the old `pad` kind is replaced by two distinct probes — `pad_length` (length-matched neutral filler; runs in single-case corpora) and `pad_content` (peer-case units; requires peers). Aggregate invariance no longer conflates presentation-length robustness with distractor-content robustness.
- **Footgun warnings:** governing-type validation at Phase 1 (unknown types abort with a clear message), type-discovery echo so `## Gate Rule` → `gate_rule` normalization is visible, single-case escalation (banner + structural `single_case_run` flag), cost/time preamble so you can `Ctrl-C` before burning compute.
- **Opt-in on-disk invocation cache.** Add `cache_dir: .kelvin-cache` to `kelvin.yaml`. Key = `sha256(run_template + rendered_markdown + decision_field)`; hits skip the pipeline subprocess entirely. Failed invocations are never cached. Intended for paid pilots against expensive pipelines.
- **Grounded-vs-degenerate experiment** under `experiments/tier3/` with scaled 6-case corpus and reproducible Table 3.
- **Envelop harness retry** — exponential backoff on transient 5xx (the 2-of-14 pilot failures traced to upstream infrastructure noise, not Kelvin bugs).

## Positioning changes

- **New tagline:** "An evidence-tracking diagnostic for structured-decision RAG" (was "An unsupervised correctness signal for RAG pipelines").
- **Scope narrowed** on the README and in the whitepaper: explicit fit for stage-gate / screening / underwriting / routing / grading pipelines; explicit non-fit for prose-output RAG (RAGAS/ARES framed as complementary).
- **Whitepaper §3.3** gains a named limitation subsection: "Content leakage in raw swap — type-matched is not counterfactual-controlled." Raw swap sensitivity is explicitly framed as an upper bound on rule-tracking behavior in v1.
- **Whitepaper §5.3** rewritten around the empirical Table 3. No more TODO markers.
- **Whitepaper §2–§3** narrowed so the structural-oracle argument reduces transparently to user-asserted typing in v1; automatic schema inference is named as the load-bearing v2 piece.

## Breaking changes

- `PadGenerator` → `PadContentGenerator`. No alias.
- Perturbation `kind` field: `"pad"` → `"pad_length"` or `"pad_content"`. External report.json consumers that match on `kind == "pad"` need to match on both new kinds.
- `CaseScores.pad` → `CaseScores.pad_length` + `CaseScores.pad_content`.

See `CHANGELOG.md` "Upgrade notes" section for the full migration checklist. Scope is small; v0.1 was an alpha with no production consumers to protect.

## Deferred to v0.3

- **Rule-condition swap (`swap_condition`)** — originally scoped for v0.2 and moved to v0.3 after design review. Clause parsing on real gate-rule text is non-trivial and a first-approximation implementation risks producing awkward swaps that would *weaken* the sensitivity signal rather than strengthen it. Raw swap remains as the v0.2 sensitivity operator with the content-leakage limitation named explicitly. Current v0.3 scope is tracked in [#1](https://github.com/SbenaVision/kelvin/issues/1).

## Install / upgrade

```bash
pip install --upgrade kelvin-eval==0.2.0
```

## Thanks

This release responds directly to external review pointing out the gap between the whitepaper's paired-signal claim and the pre-empirical state of the v0.1 implementation. The goal across v0.2 was to close that gap honestly — shipping the empirical artifact, narrowing the claims to what the tool actually measures, and deferring rather than half-shipping anything that would have weakened the signal.
