# Changelog

All notable changes to Kelvin are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html). Entries under a released version should not be edited after the version is tagged.

## [Unreleased]

Nothing queued beyond v0.2.0 at this time. v0.3 scope is tracked in the [pinned roadmap issue](https://github.com/SbenaVision/kelvin/issues/1).

## [0.2.0] — 2026-04-22

**Theme.** "The paired signal is empirically demonstrated, and the positioning matches the implementation." The central methodological claim (§3.4: invariance × sensitivity separates evidence-tracking from evidence-blind pipelines) now ships as a reproducible empirical artifact rather than an analytical promise. The marketing and whitepaper language no longer runs ahead of the tool.

### Headline empirical result

Table 3 (6 cases × 60 perturbations each, seed = 0), reproducible in under ten seconds via `cd experiments/tier3 && ./run.sh`:

| Pipeline | Invariance | Sensitivity | Kelvin score `K` |
|---|---|---|---|
| Grounded (rule-based stand-in) | 0.85 | 0.67 | **0.48** |
| Degenerate (constant output) | 1.00 | 0.00 | **1.00** |

The degenerate pipeline lands at `K = 1.00` exactly, matching the §3.4 analytical prediction pinned in `TestKelvinScore.test_constant_output_pipeline`. ΔK = 0.52 separates the two pipelines on a shared perturbation suite. See `docs/whitepaper.md` §5.3 and `experiments/tier3/README.md` for scope and limitations (the grounded column is a rule-based stand-in, not an LLM-backed pipeline).

### Added

- **Kelvin score `K = (1 − Invariance) + (1 − Sensitivity)`.** Range `[0, 2]`, lower = more anchored. Emitted as `RunScores.kelvin_score`, as `"kelvin_score"` in `report.json`, and as a dedicated block in the terminal reporter between Sensitivity and the diagnostic line. `K` is `None` when either component is `None` (no default substitution). Property-test pinned in `tests/test_scorer.py::TestKelvinScore`. ([#2](https://github.com/SbenaVision/kelvin/pull/2))
- **`PadLengthGenerator` and the `pad_length` perturbation kind.** Inserts 2–4 neutral `## Reference Note` filler sections drawn from a fixed, decision-neutral bank at random positions per variant. Runs even in single-case corpora — closes a gap where the old `pad` silently dropped out with no peers available. Probes presentation-length robustness as a distinct invariance property. ([#3](https://github.com/SbenaVision/kelvin/pull/3))
- **Footgun warnings (Tier 4).** ([#3](https://github.com/SbenaVision/kelvin/pull/3))
  - Governing-type validation at Phase 1: unknown declared types raise `CheckError` listing the discovered types and a "did you forget to normalize?" hint. Previously silent zero-swap runs.
  - Type-discovery echo: one-line `Discovered types across N case(s): gate_rule×4, interview×4, …` printed before Phase 1 so `## Gate Rule` → `gate_rule` normalization is visible immediately.
  - Single-case escalation: a `⚠` banner at run start, a `single_case_run: bool` structural flag in `RunScores` and `report.json`, and an escalated banner at the top of the terminal report box.
  - Cost/time preamble after baselines: `Running ~N perturbations across M case(s) (est. ~X min at baseline speed). Ctrl-C to abort.` Lets users bail before burning compute on expensive pipelines.
- **Opt-in on-disk invocation cache.** New `cache_dir` field in `kelvin.yaml` (absent = disabled). Key = `sha256(run_template + rendered_markdown + decision_field)` with null-byte delimiters; value = serialized `InvocationResult` under a `schema_version: 1` envelope. Cache hits skip the pipeline subprocess entirely and materialize `output.json` from the cached parsed output. Failed invocations are never cached. Safe to wipe (`rm -rf <cache_dir>`) at any time. ([#5](https://github.com/SbenaVision/kelvin/pull/5))
- **Grounded-vs-degenerate empirical experiment.** New `experiments/tier3/` directory: `pipelines/grounded.py` (deterministic rule-based stand-in), `pipelines/degenerate.py` (constant output), matched `kelvin.yaml` configs, `run.sh` runner, `build_table.py` that derives Table 3 from the actual run reports, and `README.md` documenting scope and how to add a live-Envelop column on demand. ([#4](https://github.com/SbenaVision/kelvin/pull/4))
- **Case corpus scaled from n=2 to n=6.** Four new realistic venture cases spanning the decision space: `artisanflow.md` (growth), `meridian.md` (pre-seed), `northpass.md` (idea), `rhodium.md` (scale). Existing `envelop.md` and `freakinggenius.md` retained. ([#4](https://github.com/SbenaVision/kelvin/pull/4))
- **Exponential-backoff retry in the Envelop harness.** `harness/kelvin_runner.mjs` now retries on transient 5xx (500/502/503/504) with a 500 ms jittered base and 3 attempts. Addresses the 2-of-14 transient failures reported in the original Kelvin pilot — traced to upstream Supabase/LLM infrastructure, not Kelvin bugs. ([#4](https://github.com/SbenaVision/kelvin/pull/4))
- **`CONTRIBUTING.md`** with a pointer to the pinned v0.2 roadmap issue, asking external contributors to coordinate on in-flight scope before opening PRs. ([#2](https://github.com/SbenaVision/kelvin/pull/2))
- **Whitepaper §3.3 subsection "Content leakage in raw swap: type-matched is not counterfactual-controlled."** Names the most attackable methodological limit with a worked example, forecasts the `swap_condition` mitigation, and frames raw swap sensitivity as an *upper bound* on rule-tracking behavior rather than a calibrated magnitude. ([#2](https://github.com/SbenaVision/kelvin/pull/2))

### Changed

- **Positioning.** Retagline from "An unsupervised correctness signal for RAG pipelines" to "An evidence-tracking diagnostic for structured-decision RAG." README now leads with the two failure modes (presentation-reactive / evidence-blind) and the pairing argument from §3.4. Scope narrowed: explicit fit for stage-gate / screening / underwriting / routing / grading; explicit non-fit for prose RAG (RAGAS/ARES framed as complementary, not competitive). `pyproject.toml` description aligned with the new tagline. ([#2](https://github.com/SbenaVision/kelvin/pull/2))
- **Whitepaper narrowed to match the v1 implementation.** Abstract, §1, and §3.1 no longer imply schema-derived typing; the structural-oracle argument is explicitly framed as reducing to the user's assertion about which headers identify governing units in v1, with automatic schema inference named as the load-bearing v2 piece. ([#2](https://github.com/SbenaVision/kelvin/pull/2))
- **Whitepaper §3.2 rewritten** to describe the shipped `pad_length` / `pad_content` split rather than the earlier single `pad` operator that conflated presentation-length robustness with distractor-content robustness. §6 and §7 updated in lockstep. ([#3](https://github.com/SbenaVision/kelvin/pull/3))
- **Whitepaper §5.3 rewritten** around the empirical Table 3. Pilot (n=2) results retained for historical reference; the paired-signal claim now has an executable empirical anchor. Conclusion and abstract updated to cite the empirical result rather than hedging as pilot-scale. ([#4](https://github.com/SbenaVision/kelvin/pull/4))
- **`PadGenerator` renamed to `PadContentGenerator`.** `kind` field `"pad"` → `"pad_content"`; variant IDs `pad-NN` → `pad_content-NN`. ([#3](https://github.com/SbenaVision/kelvin/pull/3))
- **`CaseScores.pad` split into `pad_length` + `pad_content` fields.** `invariance_distances` combines reorder + pad_length + pad_content. ([#3](https://github.com/SbenaVision/kelvin/pull/3))
- **`PerturbationKind` literal** changed from `"reorder" | "pad" | "swap"` to `"reorder" | "pad_length" | "pad_content" | "swap"`. ([#3](https://github.com/SbenaVision/kelvin/pull/3))
- **Terminal invariance-drift diagnostic** now ranks across all three invariance buckets (reorder / pad_length / pad_content) and names the kind with the highest drift rate in its message, so "Output drifts on pad_length" vs "on pad_content" are distinguishable in the one-liner. ([#3](https://github.com/SbenaVision/kelvin/pull/3))
- **README status table** reorganized around v0.2 / v0.3 / v2 lanes. All v0.2-scoped items now marked ✅ Done except `swap_condition`, which was explicitly deferred.

### Removed

- **`PadGenerator` class name.** Replaced by `PadContentGenerator`; no alias. ([#3](https://github.com/SbenaVision/kelvin/pull/3))
- **`"pad"` perturbation kind.** Superseded by `"pad_length"` and `"pad_content"`; no alias. External report.json consumers that matched on `kind == "pad"` will need to match on both new kinds. ([#3](https://github.com/SbenaVision/kelvin/pull/3))
- **"An unsupervised correctness signal for RAG pipelines" tagline** from README, `pyproject.toml` description, and whitepaper abstract. ([#2](https://github.com/SbenaVision/kelvin/pull/2))

### Fixed

- **Pre-existing flaky determinism test.** `test_same_seed_same_output` asserted perturbation `notes` equality *by index*, but perturbation order in the report is driven by `concurrent.futures.as_completed()`, which is non-deterministic. With more perturbations per case after the pad split, this surfaced as intermittent red. Fix compares `{variant_id: notes}` dicts so the test checks content determinism — which is what "same seed same output" actually means — rather than completion order. ([#3](https://github.com/SbenaVision/kelvin/pull/3))

### Deferred

- **Rule-condition swap (`swap_condition`)** — moved from v0.2 to **v0.3**. Clause parsing on real gate-rule text is non-trivial; a first-approximation implementation risks producing awkward swaps that would weaken rather than strengthen the sensitivity signal. Raw swap remains as the v0.2 sensitivity operator with the content-leakage limitation named explicitly in whitepaper §3.3 and §6. See [#1](https://github.com/SbenaVision/kelvin/issues/1) for current v0.3 scope.
- **Automatic schema-inferred typing** — remains **v2**, the load-bearing direction for the full structural-oracle claim made in whitepaper §2–§3.
- **HTML / markdown reporters** — upcoming. Terminal reporter shipped in v0.2.
- **`kelvin init` wizard** — upcoming.
- **Stage decomposition** (retrieval / reranking / generation attribution) — remains v2.

### Upgrade notes from v0.1

- **Python API consumers:** `PadGenerator` → `PadContentGenerator`. `CaseScores.pad` → iterate both `CaseScores.pad_length` and `CaseScores.pad_content`.
- **`report.json` consumers:** perturbations with `"kind": "pad"` no longer exist. Match on `"pad_length"` and `"pad_content"` separately, or iterate over all kinds if you do not care about the split.
- **`kelvin.yaml`:** existing configs continue to work unchanged. To opt into caching, add `cache_dir: .kelvin-cache` (or any path).
- **Terminal output:** a new `Kelvin score` row appears between Sensitivity and the diagnostic line whenever both Invariance and Sensitivity are defined.

## [0.1.0] — 2026-04 (initial pilot)

Initial alpha. Core perturbations (reorder, pad, swap), Invariance and Sensitivity scoring on a designated scalar decision field, `kelvin check` CLI, terminal reporter, and the Envelop venture-assessment harness. Pilot run against the live Envelop edge function on two cases (envelop, freakinggenius) surfaced the canonical reorder position-bias failure retained as the concrete demo in whitepaper §5.
