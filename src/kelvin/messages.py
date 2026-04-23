"""User-facing message catalog.

Every error raise and user-visible warning in Kelvin routes through a
`MessageTemplate` here. Each entry has three fields: `what` happened,
`why` it matters, and `how_to_fix` it. This guarantees consistent tone
and gives users enough context to act without re-reading docs.

Commit 1 of 0.2.1 ships the scaffolding plus ten representative entries
covering config, runner, check, and retry paths. Remaining call sites
migrate incrementally in later commits; the set of entries expands as
we migrate, locked by a snapshot test that enumerates the entry IDs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ─── Message ID constants ─────────────────────────────────────────────────
# String IDs are the stable API — tests and structured logs reference these.
# Using module-level constants rather than an enum keeps catalog extension
# trivial while still giving static analyzers a chance to catch typos.

CONFIG_FILE_NOT_FOUND = "config.file_not_found"
CONFIG_YAML_PARSE_ERROR = "config.yaml_parse_error"
CONFIG_NOT_MAPPING = "config.not_mapping"
CONFIG_MISSING_KEYS = "config.missing_keys"
CONFIG_RUN_INVALID = "config.run_invalid"
CONFIG_RUN_MISSING_PLACEHOLDERS = "config.run_missing_placeholders"
CONFIG_CASES_INVALID = "config.cases_invalid"
CONFIG_DECISION_FIELD_INVALID = "config.decision_field_invalid"
CONFIG_GOVERNING_TYPES_INVALID = "config.governing_types_invalid"
CONFIG_SEED_INVALID = "config.seed_invalid"
CONFIG_CACHE_DIR_INVALID = "config.cache_dir_invalid"
CONFIG_TIMEOUT_INVALID = "config.timeout_invalid"
CONFIG_UNKNOWN_GOVERNING_TYPE = "config.unknown_governing_type"
CONFIG_NOISE_FLOOR_NOT_MAPPING = "config.noise_floor_not_mapping"
CONFIG_NOISE_FLOOR_ENABLED_INVALID = "config.noise_floor_enabled_invalid"
CONFIG_NOISE_FLOOR_REPLICATIONS_INVALID = "config.noise_floor_replications_invalid"
CONFIG_COUNTERFACTUAL_SWAP_NOT_MAPPING = "config.counterfactual_swap_not_mapping"
CONFIG_COUNTERFACTUAL_SWAP_ENABLED_INVALID = "config.counterfactual_swap_enabled_invalid"
CONFIG_INTRA_SLOT_NOT_MAPPING = "config.intra_slot_not_mapping"
CONFIG_INTRA_SLOT_ENABLED_INVALID = "config.intra_slot_enabled_invalid"
CONFIG_INTRA_SLOT_FAMILIES_INVALID = "config.intra_slot_families_invalid"
CONFIG_INTRA_SLOT_MARKERS_INVALID = "config.intra_slot_markers_invalid"
CONFIG_INTRA_SLOT_WHITELIST_INVALID = "config.intra_slot_whitelist_invalid"

RUNNER_TIMEOUT = "runner.timeout"
RUNNER_EXIT_NONZERO = "runner.exit_nonzero"
RUNNER_OUTPUT_MISSING = "runner.output_missing"
RUNNER_OUTPUT_UNREADABLE = "runner.output_unreadable"
RUNNER_OUTPUT_NOT_JSON = "runner.output_not_json"
RUNNER_OUTPUT_NOT_MAPPING = "runner.output_not_mapping"
RUNNER_DECISION_FIELD_MISSING = "runner.decision_field_missing"

CHECK_NO_CASES = "check.no_cases"
CHECK_UNKNOWN_CASE = "check.unknown_case"
CHECK_ALL_BASELINES_FAILED = "check.all_baselines_failed"
CHECK_USER_ABORTED = "check.user_aborted"

SCORER_NON_SCALAR_DECISION = "scorer.non_scalar_decision"
SCORER_NON_SCALAR_DECISION_FIELD = "scorer.non_scalar_decision_field"

CONFIG_RETRY_POLICY_NOT_MAPPING = "config.retry_policy_not_mapping"
CONFIG_RETRY_POLICY_MAX_ATTEMPTS_INVALID = "config.retry_policy_max_attempts_invalid"
CONFIG_RETRY_POLICY_INITIAL_DELAY_INVALID = "config.retry_policy_initial_delay_invalid"
CONFIG_RETRY_POLICY_BACKOFF_FACTOR_INVALID = "config.retry_policy_backoff_factor_invalid"
CONFIG_RETRY_POLICY_JITTER_MAX_INVALID = "config.retry_policy_jitter_max_invalid"
CONFIG_RETRY_POLICY_TRANSIENT_CODES_INVALID = "config.retry_policy_transient_codes_invalid"
CONFIG_RETRY_POLICY_RETRY_ON_TIMEOUT_INVALID = "config.retry_policy_retry_on_timeout_invalid"

RETRY_TRANSIENT_DETECTED = "retry.transient_detected"
RETRY_GIVING_UP = "retry.giving_up"

DRY_RUN_SKIPPED_INVOCATION = "dry_run.skipped_invocation"


@dataclass(frozen=True)
class MessageTemplate:
    """A parameterized user-facing message with what/why/how-to-fix.

    Params are substituted via `str.format(**params)`. A missing param
    raises `KeyError` — intentional, so template bugs surface in tests
    rather than at the user's terminal.
    """

    id: str
    what: str
    why: str
    how_to_fix: str

    def format(self, **params: Any) -> FormattedMessage:
        return FormattedMessage(
            id=self.id,
            what=self.what.format(**params),
            why=self.why.format(**params),
            how_to_fix=self.how_to_fix.format(**params),
            params=dict(params),
        )


@dataclass(frozen=True)
class FormattedMessage:
    """A rendered message ready for terminal display or structured logs."""

    id: str
    what: str
    why: str
    how_to_fix: str
    params: dict[str, Any]

    def as_text(self) -> str:
        return f"{self.what}\n  {self.why}\n  Fix: {self.how_to_fix}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.id,
            "what": self.what,
            "why": self.why,
            "how_to_fix": self.how_to_fix,
            "params": dict(self.params),
        }


CATALOG: dict[str, MessageTemplate] = {
    CONFIG_FILE_NOT_FOUND: MessageTemplate(
        id=CONFIG_FILE_NOT_FOUND,
        what="Config file {path} not found.",
        why=(
            "Kelvin needs a kelvin.yaml in the current directory (or the "
            "--config path) to know what pipeline to invoke and which cases "
            "to use."
        ),
        how_to_fix=(
            "Run `kelvin init` in the directory where you want to run, or "
            "pass --config <path> to an existing kelvin.yaml."
        ),
    ),

    CONFIG_YAML_PARSE_ERROR: MessageTemplate(
        id=CONFIG_YAML_PARSE_ERROR,
        what="Config file {path} is not valid YAML: {detail}",
        why=(
            "A malformed config can't be safely interpreted — Kelvin stops "
            "before running to avoid acting on ambiguous settings."
        ),
        how_to_fix=(
            "Fix the YAML syntax at the location indicated above. Common "
            "causes: unquoted colons, mixed indentation, tabs instead of "
            "spaces."
        ),
    ),

    CONFIG_NOT_MAPPING: MessageTemplate(
        id=CONFIG_NOT_MAPPING,
        what="Config file {path} is not a YAML mapping at the top level.",
        why=(
            "Kelvin expects a mapping (key: value pairs) at the root of "
            "kelvin.yaml. A list or scalar at the top level cannot be "
            "interpreted as a config."
        ),
        how_to_fix=(
            "Wrap the file's contents in a top-level mapping — the first "
            "line should be a key like `run:`, not `-` or a bare value."
        ),
    ),

    CONFIG_MISSING_KEYS: MessageTemplate(
        id=CONFIG_MISSING_KEYS,
        what="Config file {path} is missing required keys: {missing}.",
        why=(
            "These keys define the pipeline contract and are not "
            "inferrable — Kelvin won't guess."
        ),
        how_to_fix=(
            "Add each missing key to {path}. See `kelvin init` or "
            "docs/kelvinspec.md for an example with every required key."
        ),
    ),

    CONFIG_RUN_INVALID: MessageTemplate(
        id=CONFIG_RUN_INVALID,
        what="Config `run:` must be a non-empty string shell-command template.",
        why=(
            "`run:` is the command Kelvin invokes for every baseline and "
            "every perturbation. An empty or non-string value would leave "
            "nothing to execute."
        ),
        how_to_fix=(
            "Set `run:` to a shell-command string with {{input}} and "
            "{{output}} placeholders. Example: "
            "`run: python my_pipeline.py {{input}} {{output}}`"
        ),
    ),

    CONFIG_RUN_MISSING_PLACEHOLDERS: MessageTemplate(
        id=CONFIG_RUN_MISSING_PLACEHOLDERS,
        what="Config `run:` template is missing required placeholders.",
        why=(
            "Kelvin writes perturbed input files to disk and reads JSON "
            "output files from disk; the pipeline command needs to know "
            "where both are. Without {{input}} and {{output}} placeholders "
            "Kelvin can't substitute the paths at invocation time."
        ),
        how_to_fix=(
            "Edit the `run:` line to include both placeholders. Example: "
            "`run: python my_pipeline.py {{input}} {{output}}`"
        ),
    ),

    CONFIG_CASES_INVALID: MessageTemplate(
        id=CONFIG_CASES_INVALID,
        what="Config `cases:` must be a non-empty path string.",
        why=(
            "`cases:` names the directory Kelvin scans for `*.md` case "
            "files. An empty or non-string value has no meaning."
        ),
        how_to_fix=(
            "Set `cases:` to a directory path (relative to the config "
            "file's location, or absolute). Example: `cases: ./cases`"
        ),
    ),

    CONFIG_DECISION_FIELD_INVALID: MessageTemplate(
        id=CONFIG_DECISION_FIELD_INVALID,
        what="Config `decision_field:` must be a non-empty string.",
        why=(
            "`decision_field:` names the JSON key Kelvin reads from the "
            "pipeline output to score. An empty or non-string value would "
            "make scoring ambiguous."
        ),
        how_to_fix=(
            "Set `decision_field:` to the name of the scalar field your "
            "pipeline emits. Example: `decision_field: score`"
        ),
    ),

    CONFIG_GOVERNING_TYPES_INVALID: MessageTemplate(
        id=CONFIG_GOVERNING_TYPES_INVALID,
        what="Config `governing_types:` must be a list of strings.",
        why=(
            "`governing_types:` declares which section types drive swap "
            "perturbations. It must be a list (possibly empty) of "
            "normalized type names."
        ),
        how_to_fix=(
            "Set `governing_types:` to a YAML list. Example: "
            "`governing_types: [gate_rule]` or `governing_types: []` to "
            "skip swap perturbations entirely."
        ),
    ),

    CONFIG_SEED_INVALID: MessageTemplate(
        id=CONFIG_SEED_INVALID,
        what="Config `seed:` must be an integer.",
        why=(
            "`seed:` is the root RNG seed for all perturbation generators. "
            "Non-integer values break determinism and reproducibility."
        ),
        how_to_fix=(
            "Set `seed:` to an integer (any value; 0 is a reasonable "
            "default). Example: `seed: 42`"
        ),
    ),

    CONFIG_CACHE_DIR_INVALID: MessageTemplate(
        id=CONFIG_CACHE_DIR_INVALID,
        what="Config `cache_dir:` must be a non-empty string path, or omitted to disable caching.",
        why=(
            "The on-disk invocation cache needs a directory path to write "
            "into. An empty string or wrong type leaves Kelvin with "
            "nowhere to store entries."
        ),
        how_to_fix=(
            "Either remove `cache_dir:` to disable the cache, or set it "
            "to a directory path. Example: `cache_dir: ./kelvin_cache`"
        ),
    ),

    CONFIG_TIMEOUT_INVALID: MessageTemplate(
        id=CONFIG_TIMEOUT_INVALID,
        what="Config `timeout_s: {value}` is not a positive integer.",
        why=(
            "Subprocess timeout must be a positive integer number of "
            "seconds. Zero or negative values would cause Kelvin to abort "
            "every invocation immediately; non-integers are rejected to "
            "avoid ambiguity about fractional-second semantics across "
            "platforms."
        ),
        how_to_fix=(
            "Set `timeout_s:` to a positive integer in seconds. Default is "
            "150. For LLM-backed pipelines that take 30-60s, 150 is usually "
            "enough; for slower pipelines, raise it."
        ),
    ),

    CONFIG_UNKNOWN_GOVERNING_TYPE: MessageTemplate(
        id=CONFIG_UNKNOWN_GOVERNING_TYPE,
        what=(
            "Declared governing_types not found in any case: {unknown}. "
            "Discovered types: {discovered}."
        ),
        why=(
            "A governing_type that doesn't appear in any case file means "
            "`swap` silently generates nothing for that type — the user "
            "would get a run with no sensitivity signal and no indication "
            "why. Kelvin fails fast instead."
        ),
        how_to_fix=(
            "Check for header-normalization surprises: `## Gate Rule` "
            "becomes `gate_rule`, not `Gate Rule` or `GateRule`. Either "
            "rename the header in the case files, or update "
            "`governing_types:` in the config to match the normalized form."
        ),
    ),

    RUNNER_TIMEOUT: MessageTemplate(
        id=RUNNER_TIMEOUT,
        what="Pipeline timed out after {timeout_s}s.",
        why=(
            "The subprocess ran longer than the configured `timeout_s` and "
            "was killed. This usually means either the pipeline is slower "
            "than expected for this input, or it deadlocked waiting on a "
            "resource."
        ),
        how_to_fix=(
            "If the pipeline is legitimately slow on some inputs (e.g. "
            "LLM-backed), raise `timeout_s:` in kelvin.yaml. If the "
            "timeout is indicative of a hang, inspect stderr_tail in the "
            "report for the failing perturbation."
        ),
    ),

    RUNNER_EXIT_NONZERO: MessageTemplate(
        id=RUNNER_EXIT_NONZERO,
        what="Pipeline failed with non-zero exit code {exit_code}.",
        why=(
            "The subprocess returned a non-zero exit code, which Kelvin "
            "interprets as failure. This could be a genuine pipeline error, "
            "a transient upstream issue, or a bug in the pipeline wrapper."
        ),
        how_to_fix=(
            "Inspect the stderr tail recorded on the perturbation in "
            "report.json. Common causes: auth errors, rate limiting, "
            "missing env vars, unhandled exceptions in the wrapper."
        ),
    ),

    RUNNER_OUTPUT_MISSING: MessageTemplate(
        id=RUNNER_OUTPUT_MISSING,
        what="Pipeline output file not created.",
        why=(
            "The subprocess exited successfully (exit code 0) but did not "
            "write the expected output file. Kelvin cannot score without "
            "the output."
        ),
        how_to_fix=(
            "Verify the pipeline actually writes to the path given via the "
            "{{output}} placeholder in `run:`. A common bug is writing to "
            "stdout instead of the output file path."
        ),
    ),

    RUNNER_OUTPUT_UNREADABLE: MessageTemplate(
        id=RUNNER_OUTPUT_UNREADABLE,
        what="Pipeline output file is unreadable: {detail}",
        why=(
            "The output file exists on disk but cannot be opened as UTF-8 "
            "text — this usually means a filesystem permissions issue or a "
            "pipeline that wrote binary data."
        ),
        how_to_fix=(
            "Check file permissions on the output path. Ensure the "
            "pipeline writes UTF-8-encoded JSON text, not binary."
        ),
    ),

    RUNNER_OUTPUT_NOT_JSON: MessageTemplate(
        id=RUNNER_OUTPUT_NOT_JSON,
        what="Pipeline output is not valid JSON: {detail}",
        why=(
            "Kelvin reads the pipeline's output file as JSON to extract "
            "the decision field. Non-JSON output can't be compared and "
            "would produce meaningless distances."
        ),
        how_to_fix=(
            "Check the pipeline's stderr for errors that may have "
            "corrupted the output file. Ensure the pipeline writes valid "
            "JSON — e.g., `json.dump(result, f)` rather than printing a "
            "Python repr."
        ),
    ),

    RUNNER_OUTPUT_NOT_MAPPING: MessageTemplate(
        id=RUNNER_OUTPUT_NOT_MAPPING,
        what=(
            "Pipeline output JSON must be a mapping at the top level; "
            "got {actual_type}."
        ),
        why=(
            "Kelvin reads a decision field by key from the top-level "
            "object. A JSON array, number, or string at the root has no "
            "keys to look up."
        ),
        how_to_fix=(
            "Change the pipeline to wrap its result in an object. Example: "
            "`json.dump({{\"score\": value}}, f)` rather than `json.dump"
            "(value, f)`."
        ),
    ),

    RUNNER_DECISION_FIELD_MISSING: MessageTemplate(
        id=RUNNER_DECISION_FIELD_MISSING,
        what=(
            "Decision field {field!r} missing from pipeline output. "
            "Actual keys: {actual}."
        ),
        why=(
            "The pipeline returned a valid JSON object but none of the "
            "keys match the declared decision field — Kelvin has nothing "
            "to score. This is almost always a config/pipeline mismatch."
        ),
        how_to_fix=(
            "Either update `decision_field:` in kelvin.yaml to match what "
            "the pipeline emits, or change the pipeline to emit the "
            "declared field. If the decision is nested (e.g. "
            "`report.score`), extract it in a wrapper script before "
            "writing the output JSON."
        ),
    ),

    CONFIG_NOISE_FLOOR_NOT_MAPPING: MessageTemplate(
        id=CONFIG_NOISE_FLOOR_NOT_MAPPING,
        what="Config `noise_floor:` must be a mapping.",
        why=(
            "`noise_floor:` is a block config with nested keys like "
            "`enabled:` and `replications:`. A scalar or list at that "
            "position can't carry the required fields."
        ),
        how_to_fix=(
            "Use a nested mapping. Example:\n"
            "  noise_floor:\n"
            "    enabled: true\n"
            "    replications: 10"
        ),
    ),

    CONFIG_NOISE_FLOOR_ENABLED_INVALID: MessageTemplate(
        id=CONFIG_NOISE_FLOOR_ENABLED_INVALID,
        what="Config `noise_floor.enabled` must be a boolean.",
        why=(
            "YAML accepts unquoted strings like `yes`/`no` in some places, "
            "but Kelvin requires an unambiguous `true` or `false` for "
            "feature flags so there's no parser-dependent behavior."
        ),
        how_to_fix=(
            "Set `noise_floor.enabled: true` or `noise_floor.enabled: "
            "false`."
        ),
    ),

    CONFIG_NOISE_FLOOR_REPLICATIONS_INVALID: MessageTemplate(
        id=CONFIG_NOISE_FLOOR_REPLICATIONS_INVALID,
        what="Config `noise_floor.replications` must be an integer >= 2.",
        why=(
            "Noise-floor calibration computes per-case stochasticity from "
            "pairwise distances across replays. At least 2 replays are "
            "needed to form a single pair; fewer would produce no noise "
            "estimate."
        ),
        how_to_fix=(
            "Set `noise_floor.replications:` to an integer >= 2. Default "
            "is 10. For expensive pipelines, 5 is a reasonable floor."
        ),
    ),

    CONFIG_COUNTERFACTUAL_SWAP_NOT_MAPPING: MessageTemplate(
        id=CONFIG_COUNTERFACTUAL_SWAP_NOT_MAPPING,
        what="Config `counterfactual_swap:` must be a mapping.",
        why=(
            "`counterfactual_swap:` is a block config with at least an "
            "`enabled:` key. A scalar or list at that position can't "
            "carry the required fields."
        ),
        how_to_fix=(
            "Use a nested mapping. Example:\n"
            "  counterfactual_swap:\n"
            "    enabled: true"
        ),
    ),

    CONFIG_COUNTERFACTUAL_SWAP_ENABLED_INVALID: MessageTemplate(
        id=CONFIG_COUNTERFACTUAL_SWAP_ENABLED_INVALID,
        what="Config `counterfactual_swap.enabled` must be a boolean.",
        why=(
            "Feature flags must be unambiguous `true`/`false` so there's "
            "no parser-dependent behavior."
        ),
        how_to_fix=(
            "Set `counterfactual_swap.enabled: true` or "
            "`counterfactual_swap.enabled: false`."
        ),
    ),

    CONFIG_INTRA_SLOT_NOT_MAPPING: MessageTemplate(
        id=CONFIG_INTRA_SLOT_NOT_MAPPING,
        what="Config `intra_slot:` must be a mapping.",
        why=(
            "`intra_slot:` is a block config with nested keys like "
            "`enabled:`, `enabled_families:`, and "
            "`governing_sentence_markers:`. A scalar or list at that "
            "position can't carry the required fields."
        ),
        how_to_fix=(
            "Use a nested mapping. Example:\n"
            "  intra_slot:\n"
            "    enabled: true\n"
            "    enabled_families: [numeric_magnitude]"
        ),
    ),

    CONFIG_INTRA_SLOT_ENABLED_INVALID: MessageTemplate(
        id=CONFIG_INTRA_SLOT_ENABLED_INVALID,
        what="Config `intra_slot.enabled` must be a boolean.",
        why=(
            "The top-level intra-slot kill switch must be unambiguous "
            "`true`/`false`. Keeping this strict makes the "
            "v0.2-behavior-on-upgrade guarantee trivially verifiable."
        ),
        how_to_fix=(
            "Set `intra_slot.enabled: true` or `intra_slot.enabled: false`."
        ),
    ),

    CONFIG_INTRA_SLOT_FAMILIES_INVALID: MessageTemplate(
        id=CONFIG_INTRA_SLOT_FAMILIES_INVALID,
        what="Config `intra_slot.enabled_families` must be a list of strings.",
        why=(
            "Each entry names a perturbation family to run. Non-string "
            "values can't match a known family name."
        ),
        how_to_fix=(
            "Set `intra_slot.enabled_families:` to a YAML list of strings. "
            "Example: `enabled_families: [numeric_magnitude, "
            "irrelevant_paragraph_injection]`"
        ),
    ),

    CONFIG_INTRA_SLOT_MARKERS_INVALID: MessageTemplate(
        id=CONFIG_INTRA_SLOT_MARKERS_INVALID,
        what="Config `intra_slot.governing_sentence_markers` must be a mapping.",
        why=(
            "`governing_sentence_markers:` is an optional per-case "
            "override of the default heuristic (sentences in "
            "`governing_types` sections = governing). It must be a "
            "mapping from case names to marker specs."
        ),
        how_to_fix=(
            "Either omit the key to use the default heuristic, or supply "
            "a mapping. Example:\n"
            "  governing_sentence_markers:\n"
            "    envelop: [2, 3]"
        ),
    ),

    CONFIG_INTRA_SLOT_WHITELIST_INVALID: MessageTemplate(
        id=CONFIG_INTRA_SLOT_WHITELIST_INVALID,
        what="Config `intra_slot.filler_stripping_whitelist` must be a list of strings.",
        why=(
            "The whitelist names filler words eligible for stripping "
            "(opt-in). Only string tokens can match against case text."
        ),
        how_to_fix=(
            "Set it to a YAML list of strings or omit the key entirely. "
            "Example: `filler_stripping_whitelist: [basically, just, "
            "honestly]`"
        ),
    ),

    CHECK_NO_CASES: MessageTemplate(
        id=CHECK_NO_CASES,
        what="No cases found in {cases_dir}.",
        why=(
            "Kelvin needs at least one `*.md` case file in the configured "
            "`cases:` directory. With zero cases there's nothing to run a "
            "baseline against, let alone perturb."
        ),
        how_to_fix=(
            "Add one or more `*.md` files to {cases_dir}, or update the "
            "`cases:` path in kelvin.yaml to point at an existing "
            "directory that contains case files."
        ),
    ),

    CHECK_UNKNOWN_CASE: MessageTemplate(
        id=CHECK_UNKNOWN_CASE,
        what="--only {only!r}: no such case. Available: {available}.",
        why=(
            "The --only flag filters to a single case by name (filename "
            "stem, not full path). The requested name doesn't match any "
            "discovered case file."
        ),
        how_to_fix=(
            "Pick one of the available case names listed above. Case names "
            "come from the filename stem — e.g., `cases/envelop.md` is "
            "case `envelop`."
        ),
    ),

    CHECK_USER_ABORTED: MessageTemplate(
        id=CHECK_USER_ABORTED,
        what="Run aborted at forecast prompt.",
        why=(
            "The user answered no (or anything other than y/yes) at the "
            "--confirm prompt after Phase 1. Partial reports for "
            "completed baselines were still written."
        ),
        how_to_fix=(
            "Re-run without --confirm to skip the prompt, or with --yes "
            "to auto-accept. The on-disk cache preserves successful "
            "baselines so re-runs are cheap."
        ),
    ),

    CHECK_ALL_BASELINES_FAILED: MessageTemplate(
        id=CHECK_ALL_BASELINES_FAILED,
        what="All baselines failed — no case produced a usable decision.",
        why=(
            "Kelvin aborts when every case's baseline invocation fails, "
            "because perturbation results would have no reference to "
            "compare against. This usually indicates a pipeline-level "
            "problem (bad auth, wrong endpoint, schema mismatch) rather "
            "than a case-specific one."
        ),
        how_to_fix=(
            "Inspect the per-case report.json files under kelvin/ for the "
            "baseline error messages. Fix the pipeline, then re-run. The "
            "cache will skip any successful calls from prior runs."
        ),
    ),

    SCORER_NON_SCALAR_DECISION: MessageTemplate(
        id=SCORER_NON_SCALAR_DECISION,
        what=(
            "Decision field value must be scalar (str, number, bool, "
            "null); got {actual_type}."
        ),
        why=(
            "Kelvin's v1 scorer operates on scalar decision fields only. "
            "List or dict values have no well-defined distance and would "
            "produce meaningless sensitivity/invariance scores."
        ),
        how_to_fix=(
            "Change the pipeline to emit a scalar for the decision field. "
            "If the decision is naturally structured, extract a scalar "
            "summary in a wrapper (e.g., the primary category label)."
        ),
    ),

    SCORER_NON_SCALAR_DECISION_FIELD: MessageTemplate(
        id=SCORER_NON_SCALAR_DECISION_FIELD,
        what=(
            "Decision field {field_name!r} must be scalar (str, number, "
            "bool, null); got {actual_type}."
        ),
        why=(
            "Preflight check on the first successful baseline failed — "
            "before Kelvin burns compute on perturbations, it verifies "
            "the declared decision field is scalar."
        ),
        how_to_fix=(
            "Either change the pipeline to emit {field_name!r} as a "
            "scalar, or point `decision_field:` at a different key that "
            "is scalar. Nested values can be flattened in a wrapper."
        ),
    ),

    CONFIG_RETRY_POLICY_NOT_MAPPING: MessageTemplate(
        id=CONFIG_RETRY_POLICY_NOT_MAPPING,
        what="Config `retry_policy:` must be a mapping.",
        why=(
            "`retry_policy:` is a block config with nested keys like "
            "`max_attempts:` and `transient_exit_codes:`. A scalar or "
            "list at that position can't carry the required fields."
        ),
        how_to_fix=(
            "Use a nested mapping. Example:\n"
            "  retry_policy:\n"
            "    max_attempts: 3\n"
            "    transient_exit_codes: [75]"
        ),
    ),

    CONFIG_RETRY_POLICY_MAX_ATTEMPTS_INVALID: MessageTemplate(
        id=CONFIG_RETRY_POLICY_MAX_ATTEMPTS_INVALID,
        what="Config `retry_policy.max_attempts` must be an integer >= 1.",
        why=(
            "The attempt count is 1-indexed and must permit at least the "
            "first try. Values < 1 would skip invocation entirely."
        ),
        how_to_fix=(
            "Set `retry_policy.max_attempts:` to a positive integer. "
            "Default is 3 (1 initial + 2 retries)."
        ),
    ),

    CONFIG_RETRY_POLICY_INITIAL_DELAY_INVALID: MessageTemplate(
        id=CONFIG_RETRY_POLICY_INITIAL_DELAY_INVALID,
        what="Config `retry_policy.initial_delay_s` must be a non-negative number.",
        why=(
            "Backoff delay cannot be negative. Zero is permitted (retry "
            "immediately) but discouraged for real upstreams."
        ),
        how_to_fix=(
            "Set `retry_policy.initial_delay_s:` to a number >= 0. "
            "Default is 1.0."
        ),
    ),

    CONFIG_RETRY_POLICY_BACKOFF_FACTOR_INVALID: MessageTemplate(
        id=CONFIG_RETRY_POLICY_BACKOFF_FACTOR_INVALID,
        what="Config `retry_policy.backoff_factor` must be a number >= 1.0.",
        why=(
            "Backoff factor multiplies the delay between attempts. "
            "Values < 1.0 would shrink the delay over time, which defeats "
            "the purpose of exponential backoff."
        ),
        how_to_fix=(
            "Set `retry_policy.backoff_factor:` to a number >= 1.0. "
            "Default is 2.0 (delay doubles each attempt)."
        ),
    ),

    CONFIG_RETRY_POLICY_JITTER_MAX_INVALID: MessageTemplate(
        id=CONFIG_RETRY_POLICY_JITTER_MAX_INVALID,
        what="Config `retry_policy.jitter_max_s` must be a non-negative number.",
        why=(
            "Jitter randomizes the delay between attempts to avoid "
            "thundering-herd retries. Negative values are meaningless; "
            "zero disables jitter."
        ),
        how_to_fix=(
            "Set `retry_policy.jitter_max_s:` to a number >= 0. Default "
            "is 0.3."
        ),
    ),

    CONFIG_RETRY_POLICY_TRANSIENT_CODES_INVALID: MessageTemplate(
        id=CONFIG_RETRY_POLICY_TRANSIENT_CODES_INVALID,
        what="Config `retry_policy.transient_exit_codes` must be a list of integers.",
        why=(
            "Exit codes are compared as integers against the subprocess "
            "return code. Non-integer entries can't match."
        ),
        how_to_fix=(
            "Set `retry_policy.transient_exit_codes:` to a YAML list of "
            "integers. Example: `transient_exit_codes: [75]` (EX_TEMPFAIL "
            "by convention)."
        ),
    ),

    CONFIG_RETRY_POLICY_RETRY_ON_TIMEOUT_INVALID: MessageTemplate(
        id=CONFIG_RETRY_POLICY_RETRY_ON_TIMEOUT_INVALID,
        what="Config `retry_policy.retry_on_timeout` must be a boolean.",
        why=(
            "Must be unambiguous `true`/`false`. Retrying on timeout is "
            "off by default because a timed-out pipeline often re-times-"
            "out; opt in explicitly if you know the upstream is "
            "slow-to-settle."
        ),
        how_to_fix=(
            "Set `retry_policy.retry_on_timeout: true` or `false`."
        ),
    ),

    RETRY_TRANSIENT_DETECTED: MessageTemplate(
        id=RETRY_TRANSIENT_DETECTED,
        what=(
            "Transient failure on attempt {attempt}/{max_attempts} for "
            "{context}; backing off {delay_s:.1f}s."
        ),
        why=(
            "Exit code {exit_code} is configured as a transient failure "
            "indicator. Kelvin will retry before giving up."
        ),
        how_to_fix=(
            "If this fires frequently, the upstream service may be "
            "unhealthy — inspect stderr tail. To disable retry, clear "
            "`retry_policy.transient_exit_codes:` in kelvin.yaml."
        ),
    ),

    DRY_RUN_SKIPPED_INVOCATION: MessageTemplate(
        id=DRY_RUN_SKIPPED_INVOCATION,
        what="dry-run: skipped invocation for {context}.",
        why=(
            "--dry-run generates perturbation inputs and writes reports "
            "without calling the pipeline. No subprocess is spawned and no "
            "output JSON is produced for this variant."
        ),
        how_to_fix=(
            "To actually invoke the pipeline, re-run without --dry-run. "
            "The generated inputs under kelvin/ can be inspected or fed "
            "to a different tool."
        ),
    ),

    RETRY_GIVING_UP: MessageTemplate(
        id=RETRY_GIVING_UP,
        what="Retry exhausted for {context} after {attempts} attempts.",
        why=(
            "The pipeline failed with a transient indicator on every "
            "attempt up to the configured max. Kelvin records the "
            "perturbation as failed and continues with the run."
        ),
        how_to_fix=(
            "The perturbation is logged in report.json with stderr_tail. "
            "Either raise `retry_policy.max_attempts:` (if upstream is "
            "genuinely slow to recover) or investigate the underlying "
            "failure."
        ),
    ),
}


class UnknownMessageIdError(KeyError):
    """Raised when `catalog()` is asked for an ID not in CATALOG."""


def catalog(message_id: str, **params: Any) -> FormattedMessage:
    """Look up and format a catalog message.

    Raises `UnknownMessageIdError` on unknown ID (a test-time bug, not a
    user-facing condition). Raises `KeyError` on missing format param
    (also a test-time bug — template params are part of the contract).
    """
    template = CATALOG.get(message_id)
    if template is None:
        raise UnknownMessageIdError(
            f"Unknown catalog message id: {message_id!r}. "
            f"Known ids: {sorted(CATALOG.keys())}"
        )
    return template.format(**params)
