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
CONFIG_MISSING_KEYS = "config.missing_keys"
CONFIG_RUN_MISSING_PLACEHOLDERS = "config.run_missing_placeholders"
CONFIG_TIMEOUT_INVALID = "config.timeout_invalid"
CONFIG_UNKNOWN_GOVERNING_TYPE = "config.unknown_governing_type"

RUNNER_TIMEOUT = "runner.timeout"
RUNNER_OUTPUT_NOT_JSON = "runner.output_not_json"
RUNNER_DECISION_FIELD_MISSING = "runner.decision_field_missing"

RETRY_TRANSIENT_DETECTED = "retry.transient_detected"
RETRY_GIVING_UP = "retry.giving_up"


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
