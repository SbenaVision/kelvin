"""Shell invocation of the user's pipeline. Implemented in PR 2."""

from __future__ import annotations

from pathlib import Path

from kelvin.types import InvocationResult


def invoke(
    run_template: str,
    input_path: Path,
    output_path: Path,
    decision_field: str,
    *,
    timeout_s: float | None = None,
) -> InvocationResult:
    """Invoke the user's pipeline. Returns an `InvocationResult`.

    Failure modes treated identically (ok=False):
      - non-zero exit code
      - missing output file
      - unparseable JSON
      - missing decision field in parsed JSON
    """
    raise NotImplementedError("runner arrives in PR 2")
