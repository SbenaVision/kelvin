from __future__ import annotations

import random

import pytest

from kelvin.retry import DEFAULT, RetryPolicy, policy_from_codes


class TestDefaultPolicy:
    def test_default_has_empty_transient_codes(self) -> None:
        assert DEFAULT.transient_exit_codes == frozenset()

    def test_default_does_not_retry_on_timeout(self) -> None:
        assert DEFAULT.retry_on_timeout is False

    def test_default_never_retries_any_failure(self) -> None:
        # With no configured transient codes and timeout-retry off, every
        # failure should return should_retry=False regardless of attempt.
        assert DEFAULT.should_retry(attempt=1, exit_code=1) is False
        assert DEFAULT.should_retry(attempt=1, exit_code=75) is False
        assert DEFAULT.should_retry(attempt=1, timed_out=True) is False

    def test_default_max_attempts_is_three(self) -> None:
        assert DEFAULT.max_attempts == 3

    def test_default_backoff_parameters(self) -> None:
        assert DEFAULT.initial_delay_s == 1.0
        assert DEFAULT.backoff_factor == 2.0
        assert DEFAULT.jitter_max_s == 0.3


class TestShouldRetry:
    def test_retries_on_configured_transient_code(self) -> None:
        policy = policy_from_codes([75])
        assert policy.should_retry(attempt=1, exit_code=75) is True

    def test_does_not_retry_non_transient_code(self) -> None:
        policy = policy_from_codes([75])
        assert policy.should_retry(attempt=1, exit_code=1) is False

    def test_does_not_retry_exit_code_none_by_default(self) -> None:
        policy = policy_from_codes([75])
        assert policy.should_retry(attempt=1, exit_code=None) is False

    def test_does_not_retry_after_max_attempts(self) -> None:
        policy = policy_from_codes([75], max_attempts=3)
        # attempt=3 means we've already tried 3 times — no retry.
        assert policy.should_retry(attempt=3, exit_code=75) is False

    def test_retries_up_to_but_not_past_max(self) -> None:
        policy = policy_from_codes([75], max_attempts=3)
        assert policy.should_retry(attempt=1, exit_code=75) is True
        assert policy.should_retry(attempt=2, exit_code=75) is True
        assert policy.should_retry(attempt=3, exit_code=75) is False

    def test_does_not_retry_on_timeout_unless_opted_in(self) -> None:
        policy = policy_from_codes([])
        assert policy.should_retry(attempt=1, timed_out=True) is False

    def test_retries_on_timeout_when_opted_in(self) -> None:
        policy = policy_from_codes([], retry_on_timeout=True)
        assert policy.should_retry(attempt=1, timed_out=True) is True

    def test_timeout_retry_respects_max_attempts(self) -> None:
        policy = policy_from_codes(
            [], retry_on_timeout=True, max_attempts=2
        )
        assert policy.should_retry(attempt=1, timed_out=True) is True
        assert policy.should_retry(attempt=2, timed_out=True) is False

    def test_timeout_precedence_over_exit_code(self) -> None:
        # If the subprocess both timed out AND reports a transient exit,
        # timeout semantics apply (no retry by default).
        policy = policy_from_codes([75], retry_on_timeout=False)
        assert (
            policy.should_retry(attempt=1, exit_code=75, timed_out=True)
            is False
        )


class TestDelay:
    def test_no_delay_before_first_attempt(self) -> None:
        policy = RetryPolicy(initial_delay_s=1.0, backoff_factor=2.0, jitter_max_s=0.0)
        assert policy.delay_for(1) == 0.0

    def test_delay_grows_exponentially_without_jitter(self) -> None:
        policy = RetryPolicy(
            initial_delay_s=1.0, backoff_factor=2.0, jitter_max_s=0.0
        )
        # attempt 2: 1.0 * 2^0 = 1.0
        # attempt 3: 1.0 * 2^1 = 2.0
        # attempt 4: 1.0 * 2^2 = 4.0
        assert policy.delay_for(2) == 1.0
        assert policy.delay_for(3) == 2.0
        assert policy.delay_for(4) == 4.0

    def test_delay_custom_initial_and_factor(self) -> None:
        policy = RetryPolicy(
            initial_delay_s=0.5, backoff_factor=3.0, jitter_max_s=0.0
        )
        assert policy.delay_for(2) == 0.5
        assert policy.delay_for(3) == 1.5
        assert policy.delay_for(4) == 4.5

    def test_jitter_is_bounded(self) -> None:
        policy = RetryPolicy(
            initial_delay_s=1.0, backoff_factor=2.0, jitter_max_s=0.3
        )
        # Run 200 trials, all delays for attempt=2 should fall in [1.0, 1.3].
        rng = random.Random(0)
        observed = [policy.delay_for(2, rng=rng) for _ in range(200)]
        assert all(1.0 <= d < 1.3 for d in observed)
        # And jitter actually varies — not stuck at the floor.
        assert min(observed) < max(observed)

    def test_jitter_deterministic_with_seeded_rng(self) -> None:
        policy = RetryPolicy(
            initial_delay_s=1.0, backoff_factor=2.0, jitter_max_s=0.5
        )
        rng_a = random.Random(42)
        rng_b = random.Random(42)
        sequence_a = [policy.delay_for(i, rng=rng_a) for i in range(2, 6)]
        sequence_b = [policy.delay_for(i, rng=rng_b) for i in range(2, 6)]
        assert sequence_a == sequence_b


class TestClassifyTransient:
    def test_is_transient_exit_matches_configured_codes(self) -> None:
        policy = policy_from_codes([75, 111])
        assert policy.is_transient_exit(75) is True
        assert policy.is_transient_exit(111) is True
        assert policy.is_transient_exit(1) is False

    def test_is_transient_exit_none_returns_false(self) -> None:
        policy = policy_from_codes([75])
        assert policy.is_transient_exit(None) is False


class TestImmutability:
    def test_policy_is_frozen(self) -> None:
        policy = RetryPolicy()
        with pytest.raises((AttributeError, Exception)):
            policy.max_attempts = 99  # type: ignore[misc]

    def test_transient_codes_is_frozenset(self) -> None:
        policy = policy_from_codes([75, 111])
        assert isinstance(policy.transient_exit_codes, frozenset)


class TestPolicyFromCodes:
    def test_accepts_list(self) -> None:
        p = policy_from_codes([75])
        assert 75 in p.transient_exit_codes

    def test_accepts_tuple(self) -> None:
        p = policy_from_codes((75, 111))
        assert p.transient_exit_codes == frozenset({75, 111})

    def test_accepts_set(self) -> None:
        p = policy_from_codes({75})
        assert p.transient_exit_codes == frozenset({75})

    def test_accepts_generator(self) -> None:
        p = policy_from_codes(code for code in [75, 111])
        assert p.transient_exit_codes == frozenset({75, 111})

    def test_deduplicates(self) -> None:
        p = policy_from_codes([75, 75, 75])
        assert p.transient_exit_codes == frozenset({75})
