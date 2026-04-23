"""Retry loop integration tests — wiring between runner.invoke() and
RetryPolicy. Uses a scriptable fake pipeline that returns a programmable
sequence of exit codes across attempts.

Stereo constraint per the commit-4 plan:
  - Default retry_policy=None must preserve v0.2 behavior (one attempt,
    no retry, no stderr chatter).
  - RETRY_TRANSIENT_DETECTED and RETRY_GIVING_UP messages go to stderr,
    never stdout, so report-writing pipelines that parse stdout stay
    clean.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from kelvin.retry import RetryPolicy, policy_from_codes
from kelvin.runner import invoke


# ─── Scriptable fake pipeline ──────────────────────────────────────────────
#
# The pipeline is a tiny shell script that:
#   1. Reads a sidecar "attempts.state" file to track which attempt this is.
#   2. Consumes the next exit code from a "schedule" env var.
#   3. Writes a valid output JSON on exit-0 attempts; nothing otherwise.
#
# Tests construct the schedule to drive specific retry behaviors.


def _write_fake_pipeline(tmp: Path, schedule: list[int], output_payload: dict) -> Path:
    """Write a fake pipeline script that yields exit codes from `schedule`.

    On a 0-exit attempt, writes `output_payload` as JSON to the output path.
    """
    script = tmp / "fake.py"
    state = tmp / "attempts.state"
    state.write_text("0", encoding="utf-8")
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys, argparse\n"
        "from pathlib import Path\n"
        f"SCHEDULE = {schedule!r}\n"
        f"PAYLOAD = {output_payload!r}\n"
        f"STATE = Path({str(state)!r})\n"
        "attempt = int(STATE.read_text())\n"
        "STATE.write_text(str(attempt + 1))\n"
        "code = SCHEDULE[attempt] if attempt < len(SCHEDULE) else 99\n"
        "ap = argparse.ArgumentParser()\n"
        "ap.add_argument('--input')\n"
        "ap.add_argument('--output')\n"
        "args = ap.parse_args()\n"
        "if code == 0:\n"
        "    Path(args.output).write_text(json.dumps(PAYLOAD))\n"
        "sys.exit(code)\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def _run(script: Path, tmp: Path, **kwargs):
    input_path = tmp / "input.md"
    output_path = tmp / "output.json"
    input_path.write_text("# test\n", encoding="utf-8")
    return invoke(
        f"python3 {script} --input {{input}} --output {{output}}",
        input_path,
        output_path,
        "score",
        **kwargs,
    )


# ─── Default behavior (retry_policy=None) preserves v0.2 semantics ────────


class TestDefaultBehaviorIsV02Compat:
    def test_no_retry_when_policy_is_none(self, tmp_path: Path, capsys) -> None:
        # Pipeline fails with exit 75 — but policy is None so no retry.
        script = _write_fake_pipeline(tmp_path, [75], {"score": 1})
        result = _run(script, tmp_path)
        assert result.ok is False
        assert result.exit_code == 75
        # State file shows only one attempt was made.
        assert (tmp_path / "attempts.state").read_text() == "1"
        # No retry chatter on stdout or stderr.
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "Transient" not in captured.err
        assert "Retry exhausted" not in captured.err

    def test_no_retry_with_default_policy(self, tmp_path: Path, capsys) -> None:
        # Default RetryPolicy() has empty transient codes — equivalent to None.
        script = _write_fake_pipeline(tmp_path, [75], {"score": 1})
        result = _run(script, tmp_path, retry_policy=RetryPolicy())
        assert result.ok is False
        assert (tmp_path / "attempts.state").read_text() == "1"
        captured = capsys.readouterr()
        assert "Transient" not in captured.err


# ─── Retry fires on configured transient codes ────────────────────────────


class TestRetriesOnTransientExit:
    def test_retries_and_succeeds(self, tmp_path: Path, capsys) -> None:
        # Two transient failures, then success.
        script = _write_fake_pipeline(tmp_path, [75, 75, 0], {"score": 42})
        policy = policy_from_codes(
            [75], max_attempts=3, initial_delay_s=0.0, jitter_max_s=0.0
        )
        result = _run(script, tmp_path, retry_policy=policy)
        assert result.ok is True
        assert result.decision_value == 42
        assert (tmp_path / "attempts.state").read_text() == "3"
        # Retry chatter on stderr only.
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err.count("Transient failure") == 2
        assert "Retry exhausted" not in captured.err

    def test_retries_and_exhausts(self, tmp_path: Path, capsys) -> None:
        # All 3 attempts fail with transient code.
        script = _write_fake_pipeline(tmp_path, [75, 75, 75], {"score": 1})
        policy = policy_from_codes(
            [75], max_attempts=3, initial_delay_s=0.0, jitter_max_s=0.0
        )
        result = _run(script, tmp_path, retry_policy=policy)
        assert result.ok is False
        assert result.exit_code == 75
        assert (tmp_path / "attempts.state").read_text() == "3"
        captured = capsys.readouterr()
        # 2 retry-detected messages (after attempt 1 and 2), 1 giving-up.
        assert captured.err.count("Transient failure") == 2
        assert captured.err.count("Retry exhausted") == 1

    def test_no_retry_on_non_transient_code(self, tmp_path: Path, capsys) -> None:
        # Exit 1 is not in the transient list — no retry.
        script = _write_fake_pipeline(tmp_path, [1, 1, 0], {"score": 1})
        policy = policy_from_codes(
            [75], max_attempts=3, initial_delay_s=0.0, jitter_max_s=0.0
        )
        result = _run(script, tmp_path, retry_policy=policy)
        assert result.ok is False
        assert result.exit_code == 1
        assert (tmp_path / "attempts.state").read_text() == "1"
        captured = capsys.readouterr()
        assert "Transient" not in captured.err


# ─── Timeout handling ─────────────────────────────────────────────────────


class TestTimeoutRetryBehavior:
    def _hang_script(self, tmp: Path) -> Path:
        script = tmp / "hang.py"
        state = tmp / "attempts.state"
        state.write_text("0", encoding="utf-8")
        script.write_text(
            "#!/usr/bin/env python3\n"
            "import time, sys\n"
            "from pathlib import Path\n"
            f"STATE = Path({str(state)!r})\n"
            "attempt = int(STATE.read_text())\n"
            "STATE.write_text(str(attempt + 1))\n"
            "time.sleep(10)\n"
            "sys.exit(0)\n",
            encoding="utf-8",
        )
        return script

    def test_no_retry_on_timeout_by_default(self, tmp_path: Path, capsys) -> None:
        script = self._hang_script(tmp_path)
        policy = policy_from_codes(
            [75], max_attempts=3, initial_delay_s=0.0, jitter_max_s=0.0,
            retry_on_timeout=False,
        )
        result = _run(script, tmp_path, timeout_s=1, retry_policy=policy)
        assert result.ok is False
        assert result.exit_code is None  # timeout signal
        assert (tmp_path / "attempts.state").read_text() == "1"

    def test_retry_on_timeout_when_opted_in(self, tmp_path: Path, capsys) -> None:
        script = self._hang_script(tmp_path)
        policy = policy_from_codes(
            [], max_attempts=2, initial_delay_s=0.0, jitter_max_s=0.0,
            retry_on_timeout=True,
        )
        result = _run(script, tmp_path, timeout_s=1, retry_policy=policy)
        assert result.ok is False
        assert result.exit_code is None
        assert (tmp_path / "attempts.state").read_text() == "2"
        captured = capsys.readouterr()
        assert "Transient failure" in captured.err


# ─── Stderr-only retry chatter (gate) ─────────────────────────────────────


class TestRetryMessagesGoToStderrOnly:
    def test_retry_detected_never_on_stdout(self, tmp_path: Path, capsys) -> None:
        script = _write_fake_pipeline(tmp_path, [75, 0], {"score": 1})
        policy = policy_from_codes(
            [75], max_attempts=3, initial_delay_s=0.0, jitter_max_s=0.0
        )
        _run(script, tmp_path, retry_policy=policy)
        captured = capsys.readouterr()
        # stdout must remain pristine — report writers parsing stdout
        # must not see retry chatter.
        assert "Transient" not in captured.out
        assert "Retry exhausted" not in captured.out
        # stderr must contain the expected retry event.
        assert "Transient failure" in captured.err

    def test_giving_up_never_on_stdout(self, tmp_path: Path, capsys) -> None:
        script = _write_fake_pipeline(tmp_path, [75, 75, 75], {"score": 1})
        policy = policy_from_codes(
            [75], max_attempts=3, initial_delay_s=0.0, jitter_max_s=0.0
        )
        _run(script, tmp_path, retry_policy=policy)
        captured = capsys.readouterr()
        assert "Retry exhausted" not in captured.out
        assert "Retry exhausted" in captured.err


# ─── Cache interaction ────────────────────────────────────────────────────


class TestCacheAndRetry:
    def test_cache_stores_only_final_success(self, tmp_path: Path) -> None:
        cache = tmp_path / "cache"
        script = _write_fake_pipeline(tmp_path, [75, 0], {"score": 7})
        policy = policy_from_codes(
            [75], max_attempts=3, initial_delay_s=0.0, jitter_max_s=0.0
        )
        result = _run(script, tmp_path, retry_policy=policy, cache_dir=cache)
        assert result.ok is True
        # Exactly one cache entry — the successful final result.
        entries = list(cache.glob("*.json"))
        assert len(entries) == 1
        entry = json.loads(entries[0].read_text())
        assert entry["result"]["ok"] is True
        assert entry["result"]["decision_value"] == 7

    def test_no_cache_store_when_all_attempts_fail(self, tmp_path: Path) -> None:
        cache = tmp_path / "cache"
        script = _write_fake_pipeline(tmp_path, [75, 75, 75], {"score": 1})
        policy = policy_from_codes(
            [75], max_attempts=3, initial_delay_s=0.0, jitter_max_s=0.0
        )
        result = _run(script, tmp_path, retry_policy=policy, cache_dir=cache)
        assert result.ok is False
        # Cache dir may or may not exist depending on mkdir ordering, but
        # no *.json entries should be present.
        entries = list(cache.glob("*.json")) if cache.exists() else []
        assert entries == []


# ─── Sleep is called between retries ──────────────────────────────────────


class TestBackoffSleep:
    def test_sleep_invoked_between_attempts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import kelvin.runner as runner_mod

        sleeps: list[float] = []
        monkeypatch.setattr(
            runner_mod.time, "sleep", lambda s: sleeps.append(s)
        )
        script = _write_fake_pipeline(tmp_path, [75, 75, 0], {"score": 1})
        policy = policy_from_codes(
            [75],
            max_attempts=3,
            initial_delay_s=0.5,
            backoff_factor=2.0,
            jitter_max_s=0.0,
        )
        _run(script, tmp_path, retry_policy=policy)
        # One sleep before attempt 2 (0.5s), one before attempt 3 (1.0s).
        assert sleeps == [0.5, 1.0]
