"""Invoke the user's pipeline as a shell command.

Failure handling is identical for the four failure modes listed in the spec:
  - non-zero exit code
  - output file not created
  - output file is not valid JSON (or not a JSON object)
  - output JSON is missing the declared decision field

The runner returns an `InvocationResult` in every case; it never raises for
pipeline-side failures. Callers (baseline vs perturbation path) decide what to
do with the failure.
"""

from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

from kelvin.types import InvocationResult

_STDERR_TAIL_LINES = 20


def invoke(
    run_template: str,
    input_path: Path,
    output_path: Path,
    decision_field: str,
    *,
    timeout_s: float | None = None,
) -> InvocationResult:
    """Invoke the pipeline once. Returns an `InvocationResult`."""
    command = run_template.format(
        input=shlex.quote(str(input_path)),
        output=shlex.quote(str(output_path)),
    )

    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return InvocationResult(
            ok=False,
            exit_code=None,
            input_path=input_path,
            output_path=output_path,
            error=f"pipeline timed out after {timeout_s}s",
        )

    stderr_tail = _tail(proc.stderr)

    if proc.returncode != 0:
        return InvocationResult(
            ok=False,
            exit_code=proc.returncode,
            input_path=input_path,
            output_path=output_path,
            error=f"non-zero exit ({proc.returncode})",
            stderr_tail=stderr_tail,
        )

    if not output_path.exists():
        return InvocationResult(
            ok=False,
            exit_code=proc.returncode,
            input_path=input_path,
            output_path=output_path,
            error="output file not created",
            stderr_tail=stderr_tail,
        )

    try:
        raw = output_path.read_text(encoding="utf-8")
    except OSError as exc:
        return InvocationResult(
            ok=False,
            exit_code=proc.returncode,
            input_path=input_path,
            output_path=output_path,
            error=f"output file unreadable: {exc}",
            stderr_tail=stderr_tail,
        )

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return InvocationResult(
            ok=False,
            exit_code=proc.returncode,
            input_path=input_path,
            output_path=output_path,
            error=f"output is not valid JSON: {exc.msg} at line {exc.lineno}",
            stderr_tail=stderr_tail,
        )

    if not isinstance(parsed, dict):
        return InvocationResult(
            ok=False,
            exit_code=proc.returncode,
            input_path=input_path,
            output_path=output_path,
            error=(
                f"output JSON must be a mapping at the top level; "
                f"got {type(parsed).__name__}"
            ),
            stderr_tail=stderr_tail,
        )

    if decision_field not in parsed:
        actual = sorted(parsed.keys())
        return InvocationResult(
            ok=False,
            exit_code=proc.returncode,
            input_path=input_path,
            output_path=output_path,
            parsed_output=parsed,
            error=(
                f"decision field '{decision_field}' missing from output; "
                f"actual keys: {actual}"
            ),
            stderr_tail=stderr_tail,
        )

    return InvocationResult(
        ok=True,
        exit_code=proc.returncode,
        input_path=input_path,
        output_path=output_path,
        parsed_output=parsed,
        decision_value=parsed[decision_field],
    )


def _tail(text: str | None) -> str | None:
    if not text:
        return None
    lines = text.splitlines()
    if not lines:
        return None
    return "\n".join(lines[-_STDERR_TAIL_LINES:])
