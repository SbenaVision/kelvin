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

import contextlib
import hashlib
import json
import shlex
import subprocess
from pathlib import Path

from kelvin.types import InvocationResult

_STDERR_TAIL_LINES = 20
_CACHE_SCHEMA_VERSION = 1


def invoke(
    run_template: str,
    input_path: Path,
    output_path: Path,
    decision_field: str,
    *,
    timeout_s: float | None = None,
    cache_dir: Path | None = None,
) -> InvocationResult:
    """Invoke the pipeline once. Returns an `InvocationResult`.

    If `cache_dir` is set, successful invocations are cached on disk keyed by
    `sha256(run_template + rendered_markdown + decision_field)`. A cache hit
    skips the subprocess and materializes `output_path` from the cached
    parsed output so downstream inspection (diffs, reports) still works.
    Failures are never cached — transient upstream errors should be allowed
    to retry freely on the next run.
    """
    # Cache lookup. Computed once and reused for the cache-store at the end.
    cache_key: str | None = None
    if cache_dir is not None:
        try:
            rendered = input_path.read_text(encoding="utf-8")
        except OSError:
            rendered = None
        if rendered is not None:
            cache_key = _cache_key(run_template, rendered, decision_field)
            cached = _cache_lookup(cache_dir, cache_key, input_path, output_path)
            if cached is not None:
                return cached

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

    result = InvocationResult(
        ok=True,
        exit_code=proc.returncode,
        input_path=input_path,
        output_path=output_path,
        parsed_output=parsed,
        decision_value=parsed[decision_field],
    )

    if cache_dir is not None and cache_key is not None:
        # Don't fail the run because the cache is read-only or full.
        with contextlib.suppress(OSError):
            _cache_store(cache_dir, cache_key, result)

    return result


def _tail(text: str | None) -> str | None:
    if not text:
        return None
    lines = text.splitlines()
    if not lines:
        return None
    return "\n".join(lines[-_STDERR_TAIL_LINES:])


# ─── On-disk invocation cache ──────────────────────────────────────────────


def _cache_key(run_template: str, rendered_markdown: str, decision_field: str) -> str:
    """Stable sha256 over the three inputs that identify a pipeline invocation.

    Null delimiters prevent concatenation collisions — `("ab", "c")` and
    `("a", "bc")` hash to different keys.
    """
    h = hashlib.sha256()
    h.update(run_template.encode("utf-8"))
    h.update(b"\x00")
    h.update(rendered_markdown.encode("utf-8"))
    h.update(b"\x00")
    h.update(decision_field.encode("utf-8"))
    return h.hexdigest()


def _cache_lookup(
    cache_dir: Path,
    key: str,
    input_path: Path,
    output_path: Path,
) -> InvocationResult | None:
    """Return a reconstructed `InvocationResult` on hit, `None` on miss.

    On hit, materializes `output_path` from the cached parsed output so
    downstream code and user inspection (`diff`, `jq`) see the same file
    as a fresh run would produce. A corrupt or partial cache entry is
    treated as a miss.
    """
    path = cache_dir / f"{key}.json"
    if not path.exists():
        return None
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(entry, dict) or entry.get("schema_version") != _CACHE_SCHEMA_VERSION:
        return None
    res = entry.get("result")
    if not isinstance(res, dict) or not res.get("ok"):
        return None
    parsed = res.get("parsed_output")
    if not isinstance(parsed, dict):
        return None
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
    except OSError:
        return None
    return InvocationResult(
        ok=True,
        exit_code=res.get("exit_code", 0),
        input_path=input_path,
        output_path=output_path,
        parsed_output=parsed,
        decision_value=res.get("decision_value"),
    )


def _cache_store(cache_dir: Path, key: str, result: InvocationResult) -> None:
    """Write a successful invocation to the cache. Overwrites any prior entry."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "schema_version": _CACHE_SCHEMA_VERSION,
        "key": key,
        "result": {
            "ok": result.ok,
            "exit_code": result.exit_code,
            "parsed_output": result.parsed_output,
            "decision_value": result.decision_value,
            "error": result.error,
            "stderr_tail": result.stderr_tail,
        },
    }
    (cache_dir / f"{key}.json").write_text(
        json.dumps(entry, indent=2), encoding="utf-8"
    )
