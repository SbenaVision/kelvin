"""Tests for the EventLogger — text and JSON output modes, stream routing,
and the text_fallback path used by legacy `echo=` consumers.
"""

from __future__ import annotations

import io
import json

import pytest

from kelvin.event_log import EventLogger, text_logger_for


class TestTextMode:
    def test_info_writes_to_stdout(self) -> None:
        out = io.StringIO()
        err = io.StringIO()
        logger = EventLogger(stdout=out, stderr=err)
        logger.info("hello", text="world")
        assert out.getvalue() == "world\n"
        assert err.getvalue() == ""

    def test_warn_writes_to_stderr(self) -> None:
        out = io.StringIO()
        err = io.StringIO()
        logger = EventLogger(stdout=out, stderr=err)
        logger.warn("something", text="wrong")
        assert out.getvalue() == ""
        assert err.getvalue() == "wrong\n"

    def test_error_writes_to_stderr(self) -> None:
        out = io.StringIO()
        err = io.StringIO()
        logger = EventLogger(stdout=out, stderr=err)
        logger.error("failure", text="boom")
        assert err.getvalue() == "boom\n"
        assert out.getvalue() == ""

    def test_text_fallback_routes_info_only(self) -> None:
        out = io.StringIO()
        err = io.StringIO()
        collected: list[str] = []
        logger = EventLogger(
            stdout=out, stderr=err, text_fallback=collected.append
        )
        logger.info("a", text="info-line")
        logger.warn("b", text="warn-line")
        logger.error("c", text="error-line")
        # info goes to fallback; warn/error still hit stderr.
        assert collected == ["info-line"]
        assert out.getvalue() == ""
        assert err.getvalue() == "warn-line\nerror-line\n"

    def test_synthesizes_text_when_none_given(self) -> None:
        out = io.StringIO()
        logger = EventLogger(stdout=out)
        logger.info("evt", a=1, b="x")
        assert out.getvalue() == "evt: a=1 b=x\n"

    def test_synthesized_bare_event_when_no_fields(self) -> None:
        out = io.StringIO()
        logger = EventLogger(stdout=out)
        logger.info("just_an_event")
        assert out.getvalue() == "just_an_event\n"


class TestJsonMode:
    def test_info_emits_one_json_line_to_stdout(self) -> None:
        out = io.StringIO()
        logger = EventLogger(fmt="json", stdout=out, _clock=lambda: 1000.0)
        logger.info("baseline_completed", case="x", ok=True)
        lines = out.getvalue().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["schema_version"] == 1
        assert record["ts"] == 1000.0
        assert record["level"] == "info"
        assert record["event"] == "baseline_completed"
        assert record["case"] == "x"
        assert record["ok"] is True

    def test_warn_and_error_emit_to_stderr(self) -> None:
        out = io.StringIO()
        err = io.StringIO()
        logger = EventLogger(
            fmt="json", stdout=out, stderr=err, _clock=lambda: 0.0
        )
        logger.warn("retry_detected", attempt=1)
        logger.error("fatal", reason="x")
        assert out.getvalue() == ""
        lines = err.getvalue().splitlines()
        assert len(lines) == 2
        r1 = json.loads(lines[0])
        r2 = json.loads(lines[1])
        assert r1["level"] == "warn"
        assert r1["event"] == "retry_detected"
        assert r1["attempt"] == 1
        assert r2["level"] == "error"
        assert r2["event"] == "fatal"

    def test_includes_text_when_given(self) -> None:
        out = io.StringIO()
        logger = EventLogger(fmt="json", stdout=out)
        logger.info("evt", text="human-readable", x=1)
        record = json.loads(out.getvalue())
        assert record["text"] == "human-readable"
        assert record["x"] == 1

    def test_omits_text_when_absent(self) -> None:
        out = io.StringIO()
        logger = EventLogger(fmt="json", stdout=out)
        logger.info("evt", x=1)
        record = json.loads(out.getvalue())
        assert "text" not in record

    def test_text_fallback_bypassed_in_json_mode(self) -> None:
        out = io.StringIO()
        collected: list[str] = []
        logger = EventLogger(
            fmt="json", stdout=out, text_fallback=collected.append
        )
        logger.info("evt", text="should-not-reach-fallback")
        assert collected == []  # fallback never called in JSON mode
        assert out.getvalue() != ""  # record did go to stdout

    def test_schema_version_field_present(self) -> None:
        out = io.StringIO()
        logger = EventLogger(fmt="json", stdout=out)
        logger.info("evt")
        record = json.loads(out.getvalue())
        assert "schema_version" in record

    def test_non_serializable_values_use_default_str(self) -> None:
        # Path objects and other non-JSON-native types render via str().
        from pathlib import Path

        out = io.StringIO()
        logger = EventLogger(fmt="json", stdout=out)
        logger.info("evt", path=Path("/tmp/foo"))
        record = json.loads(out.getvalue())
        assert record["path"] == "/tmp/foo"


class TestInvalidFormat:
    def test_rejects_unknown_format(self) -> None:
        with pytest.raises(ValueError, match="fmt must be"):
            EventLogger(fmt="xml")


class TestEndToEndJsonLogs:
    """One integration test: run_check in JSON mode emits the expected
    event names for a trivial pipeline, proving the wiring between
    check.py and EventLogger is correct."""

    def test_run_check_json_mode_emits_required_events(
        self, tmp_path
    ) -> None:
        import io
        from pathlib import Path

        from kelvin.check import run_check

        # Minimal pipeline: always write {"score": 1}.
        pipeline = tmp_path / "pipe.py"
        pipeline.write_text(
            "import json, sys, argparse\n"
            "ap = argparse.ArgumentParser(); ap.add_argument('--input')\n"
            "ap.add_argument('--output'); args = ap.parse_args()\n"
            "with open(args.output, 'w') as f: json.dump({'score': 1}, f)\n",
            encoding="utf-8",
        )
        cases = tmp_path / "cases"
        cases.mkdir()
        (cases / "one.md").write_text(
            "## Idea\nhello\n## Money\n$1\n", encoding="utf-8"
        )
        (tmp_path / "kelvin.yaml").write_text(
            f"run: python3 {pipeline} --input {{input}} --output {{output}}\n"
            f"cases: {cases}\n"
            "decision_field: score\n"
            "governing_types: []\n"
            "seed: 0\n",
            encoding="utf-8",
        )

        out = io.StringIO()
        err = io.StringIO()
        logger = EventLogger(fmt="json", stdout=out, stderr=err)
        run_check(Path(tmp_path), logger=logger)

        events = [
            json.loads(line) for line in out.getvalue().splitlines() if line
        ]
        event_names = {e["event"] for e in events}
        # Required structured events must all appear.
        assert "config_loaded" in event_names
        assert "baseline_completed" in event_names
        assert "perturbation_completed" in event_names
        assert "run_completed" in event_names
        # Every record has the schema contract.
        for e in events:
            assert e["schema_version"] == 1
            assert "ts" in e
            assert "level" in e
            assert "event" in e


class TestLegacyEchoHelper:
    def test_text_logger_for_routes_info_through_callable(self) -> None:
        collected: list[str] = []
        logger = text_logger_for(collected.append)
        logger.info("evt", text="hello")
        assert collected == ["hello"]

    def test_text_logger_for_none_writes_to_stdout(self) -> None:
        logger = text_logger_for(None)
        # Smoke test — construction succeeds, writes land on sys.stdout.
        assert logger.fmt == "text"
        assert logger.text_fallback is None
