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
import random
import shlex
import subprocess
import sys
import time
from pathlib import Path

from kelvin.event_log import EventLogger
from kelvin.messages import (
    RETRY_GIVING_UP,
    RETRY_TRANSIENT_DETECTED,
    RUNNER_DECISION_FIELD_MISSING,
    RUNNER_EXIT_NONZERO,
    RUNNER_OUTPUT_MISSING,
    RUNNER_OUTPUT_NOT_JSON,
    RUNNER_OUTPUT_NOT_MAPPING,
    RUNNER_OUTPUT_UNREADABLE,
    RUNNER_TIMEOUT,
    catalog,
)
from kelvin.retry import DEFAULT as DEFAULT_RETRY_POLICY
from kelvin.retry import RetryPolicy
from kelvin.types import InvocationResult

_STDERR_TAIL_LINES = 20
# Cache entry schema version. Pinned at 1 for v0.2 compatibility; bump when
# a v0.3 pillar extends the cached payload (e.g. noise-floor replays, family
# identifiers). Bumping invalidates all prior entries cleanly (miss, not
# crash) — reader in `_cache_lookup` rejects mismatched versions.
_CACHE_SCHEMA_VERSION = 1


def invoke(
    run_template: str,
    input_path: Path,
    output_path: Path,
    decision_field: str,
    *,
    timeout_s: float | None = None,
    cache_dir: Path | None = None,
    retry_policy: RetryPolicy | None = None,
    rng: random.Random | None = None,
    logger: EventLogger | None = None,
) -> InvocationResult:
    """Invoke the pipeline once. Returns an `InvocationResult`.

    If `cache_dir` is set, successful invocations are cached on disk keyed by
    `sha256(run_template + rendered_markdown + decision_field)`. A cache hit
    skips the subprocess and materializes `output_path` from the cached
    parsed output so downstream inspection (diffs, reports) still works.
    Failures are never cached — transient upstream errors should be allowed
    to retry freely on the next run.

    If `retry_policy` is set (or implied via a non-empty
    `transient_exit_codes` / `retry_on_timeout`), transient failures are
    retried with exponential backoff + jitter. The default policy
    (`RetryPolicy()`) performs no retries — v0.2-byte-compat behavior.
    Retry progress messages go to stderr so stdout stays parseable.
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

    policy = retry_policy if retry_policy is not None else DEFAULT_RETRY_POLICY
    context = str(input_path)

    was_retry = False
    result: InvocationResult | None = None
    for attempt in range(1, policy.max_attempts + 1):
        result = _attempt_once(
            run_template,
            input_path,
            output_path,
            decision_field,
            timeout_s=timeout_s,
        )

        if result.ok:
            break

        timed_out = result.exit_code is None
        if policy.should_retry(
            attempt=attempt,
            exit_code=result.exit_code,
            timed_out=timed_out,
        ):
            was_retry = True
            next_delay = policy.delay_for(attempt + 1, rng=rng)
            _emit_retry_detected(
                attempt=attempt,
                max_attempts=policy.max_attempts,
                delay_s=next_delay,
                exit_code=result.exit_code if result.exit_code is not None else -1,
                context=context,
                logger=logger,
            )
            time.sleep(next_delay)
            continue

        # No retry — either permanent failure or attempts exhausted.
        if was_retry:
            _emit_giving_up(attempts=attempt, context=context, logger=logger)
        break

    assert result is not None  # loop always runs at least once
    if result.ok and cache_dir is not None and cache_key is not None:
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


# ─── Single-attempt body ──────────────────────────────────────────────────


def _attempt_once(
    run_template: str,
    input_path: Path,
    output_path: Path,
    decision_field: str,
    *,
    timeout_s: float | None,
) -> InvocationResult:
    """Run the pipeline exactly once. The retry loop in `invoke()` calls this."""
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
            error=catalog(RUNNER_TIMEOUT, timeout_s=timeout_s).what,
        )

    stderr_tail = _tail(proc.stderr)

    if proc.returncode != 0:
        return InvocationResult(
            ok=False,
            exit_code=proc.returncode,
            input_path=input_path,
            output_path=output_path,
            error=catalog(RUNNER_EXIT_NONZERO, exit_code=proc.returncode).what,
            stderr_tail=stderr_tail,
        )

    if not output_path.exists():
        return InvocationResult(
            ok=False,
            exit_code=proc.returncode,
            input_path=input_path,
            output_path=output_path,
            error=catalog(RUNNER_OUTPUT_MISSING).what,
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
            error=catalog(RUNNER_OUTPUT_UNREADABLE, detail=exc).what,
            stderr_tail=stderr_tail,
        )

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        detail = f"{exc.msg} at line {exc.lineno}"
        return InvocationResult(
            ok=False,
            exit_code=proc.returncode,
            input_path=input_path,
            output_path=output_path,
            error=catalog(RUNNER_OUTPUT_NOT_JSON, detail=detail).what,
            stderr_tail=stderr_tail,
        )

    if not isinstance(parsed, dict):
        return InvocationResult(
            ok=False,
            exit_code=proc.returncode,
            input_path=input_path,
            output_path=output_path,
            error=catalog(
                RUNNER_OUTPUT_NOT_MAPPING, actual_type=type(parsed).__name__
            ).what,
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
            error=catalog(
                RUNNER_DECISION_FIELD_MISSING, field=decision_field, actual=actual
            ).what,
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


# ─── Retry event emission ─────────────────────────────────────────────────
# Retry progress messages go to stderr only so stdout stays parseable for
# report writers. Each message is a single line (the catalog entry's `what`
# field); full why/how-to-fix rendering is available via catalog lookup.


def _emit_retry_detected(
    *,
    attempt: int,
    max_attempts: int,
    delay_s: float,
    exit_code: int,
    context: str,
    logger: EventLogger | None,
) -> None:
    msg = catalog(
        RETRY_TRANSIENT_DETECTED,
        attempt=attempt,
        max_attempts=max_attempts,
        delay_s=delay_s,
        exit_code=exit_code,
        context=context,
    )
    if logger is not None:
        logger.warn(
            "retry_detected",
            text=msg.what,
            attempt=attempt,
            max_attempts=max_attempts,
            delay_s=delay_s,
            exit_code=exit_code,
            context=context,
        )
    else:
        # v0.2-compat fallback: direct stderr print (no logger attached).
        print(msg.what, file=sys.stderr)


def _emit_giving_up(
    *, attempts: int, context: str, logger: EventLogger | None
) -> None:
    msg = catalog(RETRY_GIVING_UP, attempts=attempts, context=context)
    if logger is not None:
        logger.warn(
            "retry_giving_up",
            text=msg.what,
            attempts=attempts,
            context=context,
        )
    else:
        print(msg.what, file=sys.stderr)


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
