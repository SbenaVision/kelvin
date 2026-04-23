# Changelog

All notable changes to Kelvin are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html). Entries under a released version should not be edited after the version is tagged.

## [Unreleased]

Nothing queued beyond v0.2.1 at this time. v0.3 scope is tracked in the [pinned roadmap issue](https://github.com/SbenaVision/kelvin/issues/1); `FALLBACKS.md` pins the paper tier ladder in advance so thresholds aren't relaxed mid-stream.

## [0.2.1] — 2026-04-23

**Theme.** "UX polish with zero methodology drift." This release adds opt-in diagnostic, observability, and reliability surfaces — a central `MessageCatalog` for what/why/how-to-fix error rendering, a core-runner retry policy, structured JSON logs, a pre-Phase-2 forecast prompt, and a `--dry-run` mode for materializing perturbation inputs without calling the pipeline. **Zero changes** to the scorer math, aggregation rules, perturbation generators, or the paired-signal claim in §3.4. Every new feature is off by default; `kelvin check` with a v0.2.0 `kelvin.yaml` and no new flags produces byte-for-byte identical output to v0.2.0 on deterministic pipelines (verified by a regression harness snapshotted from v0.2.0 reports). Methodology work — Pillar 1 noise-calibrated `K_cal`, Pillar 2 `swap_condition` + decomposition, Pillar 3 validated intra-slot probes — is deliberately held for v0.3.0, which ships alongside the paper revision.

### Added

- **`src/kelvin/messages.py` — centralized message catalog.** Every `raise ConfigError(…)`, every `raise CheckError(…)`, every `raise AbortRun(…)`, every `raise DecisionFieldTypeError(…)`, and every `InvocationResult.error` string now sources from a `MessageTemplate` carrying three fields: `what` happened, `why` it matters, `how_to_fix` it. Exception classes gained a `formatted_message: FormattedMessage | None` attribute so structured log consumers can render all three fields downstream. Back-compat preserved: raising with a plain string still works for external callers. 46 entries in commit 7; snapshot-locked by `tests/test_messages.py::TestCatalogSnapshot` so adding or removing an entry requires an explicit snapshot edit in the same commit. (commits 1, 2, 3, 5, 6)
- **`src/kelvin/retry.py` — opt-in retry policy for the core runner.** New `RetryPolicy` dataclass with fields `max_attempts`, `initial_delay_s`, `backoff_factor`, `jitter_max_s`, `transient_exit_codes`, `retry_on_timeout`. `invoke()` gained a `retry_policy` kwarg; configured via a new `retry_policy:` block in `kelvin.yaml` with six validated fields. Transient failures (exit codes in the configured list) retry with exponential backoff + jitter; retry progress messages emit to **stderr only** so stdout stays parseable for report writers downstream. Convention: pipelines opt in by signalling transients with a distinguishable exit code (e.g., 75 = `EX_TEMPFAIL`). Retry-in-wrapper remains the preferred location for API-aware retry (see `harness/kelvin_runner.mjs`); this is the simpler option for pipelines that don't want to maintain their own wrapper. Default policy is zero-retry — `RetryPolicy()` with empty `transient_exit_codes` — so v0.2 behavior is byte-for-byte preserved. (commits 1, 4)
- **`src/kelvin/event_log.py` — structured event logger.** New `EventLogger` class with two output modes:
  - `text` mode (default): human-readable lines matching v0.2 output; `text_fallback` callable preserves legacy `echo=list.append` / `echo=typer.echo` patterns without refactor.
  - `json` mode: one JSON record per line with `{schema_version: 1, ts, level, event, [text], …fields}`. Info-level events to stdout; warn/error to stderr.

  Eight structured events wired through `run_check` and `invoke()`: `config_loaded`, `types_discovered`, `cache_path`, `single_case_run`, `cost_preamble`, `baseline_completed`, `perturbation_completed`, `run_completed`, `retry_detected`, `retry_giving_up`, `dry_run_skipped_invocation`. (commits 5, 6)
- **`--confirm` + `--yes` forecast dialog.** New CLI flags on `kelvin check`. When `--confirm` is set, Kelvin prompts `Proceed? [y/N]` after Phase 1 (baselines + cost preamble) and before Phase 2 (perturbations) — the compute-burn gate. Two independent prompt bypasses: `--yes` (explicit auto-accept) **or** `sys.stdin.isatty() == False` (CI safety — no interactive input available). User rejection writes partial per-case reports for completed baselines and raises `AbortRun(CHECK_USER_ABORTED)`. Default off: no prompt, no behavior change from v0.2. (commit 5)
- **`--log-format text|json` CLI flag.** Selects the output format for progress/status events from `run_check` and retry events from `invoke()`. Text is the default and matches v0.2 output exactly. JSON emits one record per line with a stable schema versioned at 1. (commit 5)
- **`--dry-run` CLI flag.** Generate perturbation inputs and write reports without invoking the pipeline. Both phases write `input.md` files under `kelvin/<case>/…/` but skip the subprocess entirely — no output JSON is produced, no cache entries are written, no side effects beyond the generated inputs and reports. Run-level and per-case `report.json` gain a top-level `"dry_run": true` marker emitted **only when set** (non-dry runs produce identical bytes to v0.2). `--dry-run` bypasses the `--confirm` prompt — no spend means nothing to confirm. `dry_run_skipped_invocation` event fires once per skipped baseline and once per skipped perturbation variant for log-based auditing. (commit 6)
- **`timeout_s` config field.** New top-level `timeout_s:` key in `kelvin.yaml` (default 150). Replaces the hardcoded 60s subprocess timeout in v0.2 which was effectively a bug for LLM-backed pipelines. v0.2 yaml files without the field get the new default; users who want the old behavior can set `timeout_s: 60` explicitly. (Phase A)
- **`FALLBACKS.md` at repo root.** Pre-registered paper tier ladder for v0.3.0: four tiers (full scope → Pillar 1 alone) with explicit threshold-discipline policy ("what we will not do"). Not edited mid-stream; exists to prevent threshold relaxation after results arrive. (commit 1)
- **`schema_version` field in `report.json`.** Pinned at 1 in 0.2.1 for the v0.2-equivalent report shape. Bumps in v0.3.0 when pillar data arrives. Additive only — omission is still legal per the Keep-a-Changelog additive-keys rule. (Phase A)

### Changed

- **Version-mismatch fix.** v0.2.0 shipped with `pyproject.toml` at `0.2.0` and `src/kelvin/__init__.py` at `0.1.0`. Both now set to `0.2.1`. Module docstring also updated to the current positioning ("An evidence-tracking diagnostic for structured-decision RAG.").
- **Subprocess timeout default: 60s → 150s.** Users on LLM-backed pipelines no longer need to patch the source. Still configurable per-project via `timeout_s:` in `kelvin.yaml`. Deterministic pipelines (the regression-harness constant and brittle benchmarks) finish in milliseconds — timeout change is unobservable at the score level. (Phase A)
- **Error messages across the tool now render as three-field structures** (what / why / how-to-fix) via `str(error)` on raised exceptions and through the catalog's `FormattedMessage.as_text()` helper. Existing pytest `match=` assertions in the suite continue to pass because every catalog `what` field preserves the keyword substrings consumers were grepping for. Terminal runner errors (`InvocationResult.error`) still render as single-line strings (catalog `what` only) to keep progress output clean — full what/why/how-to-fix is available via the structured log path or catalog lookup. (commits 2, 3)

### Backward compatibility

- **v0.2.0 `kelvin.yaml` loads unchanged.** Every new config block (`noise_floor`, `counterfactual_swap`, `intra_slot`, `retry_policy`) is optional with off/safe defaults. Tested in `tests/test_config.py::TestV03BackwardCompat::test_v02_yaml_loads_with_new_flags_off`.
- **Default behavior preserves v0.2 byte-for-byte.** All new features are opt-in: `--confirm`, `--yes`, `--log-format`, `--dry-run`, and the `retry_policy` / `noise_floor` / `counterfactual_swap` / `intra_slot` config blocks all default to inactive. A `kelvin check` invocation with a v0.2.0 yaml and no new CLI flags produces identical `report.json` content to v0.2.0.
- **Regression harness verifies this claim.** `regression.py` runs the current code against the `constant` (K=1.000) and `brittle` (K=1.055) benchmarks and diffs every key/value in `report.json` against v0.2.0 baseline snapshots. The only additive key in v0.2.1 non-dry reports is `schema_version: 1` (new; additive by Keep-a-Changelog rule). Gate fires before every commit in this release; never tripped.
- **Python API back-compat.** `run_check(echo=print)` remains a valid call shape. When only `echo` is passed (not `logger`), `run_check` constructs a text-mode `EventLogger` with the echo callable as its `text_fallback` — all info events still route through `echo`, so `echo=lines.append` patterns in tests continue to work.
- **`report.json` consumers.** Existing keys and their types are unchanged. Two new keys are additive and **emitted only when true**: `"dry_run": true` at run-level and per-case when `--dry-run` is active. Consumers that don't handle the key simply ignore it.

### Schema impact

- `report.json` top-level: `"dry_run": true` added, **emitted only when `--dry-run` is set**. Absent from non-dry reports, which remain byte-identical to v0.2.0.
- `report.json` per-case: same pattern. `"dry_run": true` only in dry-run reports.
- `schema_version`: pinned at `1` (v0.2-equivalent shape). Bumped in v0.3.0 when pillar data arrives.
- `InvocationResult` dataclass and its serialization inside each perturbation's `invocation` block: **unchanged**.
- Cache entry format (`_CACHE_SCHEMA_VERSION` in `runner.py`): pinned at `1`. No new cache fields in 0.2.1; commit 5's earlier preview of adding `formatted_error` to `InvocationResult` was deferred — JSON logs carry the structured error data on-stream instead, no cache schema churn.
- JSON log record schema (new): pinned at `1`. Distinct from `report.json` schema.

### What is NOT in 0.2.1

Deliberately deferred to **v0.3.0** (methods paper release):

- **Pillar 1 — Noise-floor calibration (`K_cal`).** Replay baselines N times, compute per-pipeline stochasticity `η`, report noise-normalized `K_cal`.
- **Pillar 2 — Counterfactual-controlled sensitivity (`swap_condition`) with decomposition theorem.** Edit only the condition clause of a governing rule; separate `Rule_Effect` from `Content_Effect` analytically + empirically.
- **Pillar 3 — Validated intra-slot probes.** Sentence-level perturbations within a section (numeric magnitude curve, comparator flip, polarity flip, bank invariance, rhetorical families) with human-labeling validation (α ≥ 0.8, meaning-preservation ≥ 90%).
- **Scorer math changes.** `DefaultScorer.distance` unchanged. Aggregation rules unchanged.
- **Perturbation generator changes.** `reorder`, `pad_length`, `pad_content`, `swap` behavior unchanged. No new generators.
- **Paper revision.** Whitepaper stays at its v0.2.0 text; the v0.3.0 paper revision lands alongside the methodology pillars.

0.2.1 is pure scaffolding and UX polish. Every downstream methodology piece inherits cleanly from this release.

### Fixed

- **`pyproject.toml` / `src/kelvin/__init__.py` version mismatch** (from v0.2.0): both now read `0.2.1`.
- **Subprocess timeout hardcoded to 60s** (from v0.2.0): now configurable via `timeout_s:` in `kelvin.yaml`, default 150.
- **Closed the Copilot-flagged scorer test gap** from the v0.2.0 review: added `pad_length` invariance-pool test, zero-baseline numeric edge cases, empty-type sensitivity. (Phase A)

### Upgrade notes from v0.2.0

- **No action required.** `pip install -U kelvin-eval` and existing runs continue to work unchanged.
- **To opt into retry on flaky pipelines**, add to `kelvin.yaml`:
  ```yaml
  retry_policy:
    transient_exit_codes: [75]   # EX_TEMPFAIL by convention
  ```
- **To opt into structured JSON logs**, run `kelvin check --log-format json`. One record per line with `{schema_version, ts, level, event, …fields}`.
- **To add a budget-burn gate before Phase 2**, run `kelvin check --confirm`. CI pipelines should pair with `--yes` or rely on non-TTY auto-accept.
- **To inspect perturbation inputs without calling the pipeline**, run `kelvin check --dry-run`. Generates every `input.md` and writes reports marked `"dry_run": true`.
- **External tools reading `report.json`** should tolerate the new optional `schema_version: 1` key (always present) and the optional `dry_run: true` key (only in dry-run reports).

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
