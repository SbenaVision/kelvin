"""Opt-in retry policy for the core runner.

Convention: pipelines that opt into core-runner retry signal transient
failures with a distinguishable exit code (e.g., 75 = EX_TEMPFAIL).
Permanent failures return any other non-zero code and are not retried.
Invalid-response-format failures are never retried — the wrapper should
surface them clearly and the run continues with that variant marked
failed.

Retry-in-wrapper remains the preferred location for API-aware retry (see
harness/kelvin_runner.mjs for the reference pattern): wrappers have
context the runner does not (HTTP status codes, rate-limit headers,
auth errors). This module lifts the pattern into the core runner for
pipelines that don't want to maintain their own retry wrapper.

Defaults produce zero retries — v0.2 byte-compatible. Retry activates
only when `transient_exit_codes` is non-empty or `retry_on_timeout`
is True.
"""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_delay_s: float = 1.0
    backoff_factor: float = 2.0
    jitter_max_s: float = 0.3
    transient_exit_codes: frozenset[int] = field(default_factory=frozenset)
    retry_on_timeout: bool = False

    def delay_for(self, attempt: int, rng: random.Random | None = None) -> float:
        """Compute backoff delay *before* `attempt`.

        `attempt` is 1-indexed. Delay before attempt 1 is 0 (first try,
        no backoff yet). Delay before attempt 2 is `initial_delay_s +
        jitter`. Subsequent attempts multiply by `backoff_factor`.
        """
        if attempt < 2:
            return 0.0
        base = self.initial_delay_s * (self.backoff_factor ** (attempt - 2))
        if self.jitter_max_s > 0:
            r = rng if rng is not None else random
            base += r.random() * self.jitter_max_s
        return base

    def is_transient_exit(self, exit_code: int | None) -> bool:
        return exit_code is not None and exit_code in self.transient_exit_codes

    def should_retry(
        self,
        *,
        attempt: int,
        exit_code: int | None = None,
        timed_out: bool = False,
    ) -> bool:
        """Would this failure be retried on the *next* attempt?

        Returns False once `attempt >= max_attempts` regardless of other
        conditions — the policy's job is to decide whether to schedule
        one more try, not to decide whether the current failure is
        transient in isolation.
        """
        if attempt >= self.max_attempts:
            return False
        if timed_out:
            return self.retry_on_timeout
        return self.is_transient_exit(exit_code)


def policy_from_codes(
    codes: Iterable[int],
    *,
    max_attempts: int = 3,
    initial_delay_s: float = 1.0,
    backoff_factor: float = 2.0,
    jitter_max_s: float = 0.3,
    retry_on_timeout: bool = False,
) -> RetryPolicy:
    """Convenience constructor — pass any iterable of exit codes."""
    return RetryPolicy(
        max_attempts=max_attempts,
        initial_delay_s=initial_delay_s,
        backoff_factor=backoff_factor,
        jitter_max_s=jitter_max_s,
        transient_exit_codes=frozenset(codes),
        retry_on_timeout=retry_on_timeout,
    )


# Zero-retry default — safe for v0.2 byte-compat.
DEFAULT = RetryPolicy()
