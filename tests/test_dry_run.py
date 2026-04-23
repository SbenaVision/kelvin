"""Tests for --dry-run mode.

Dry-run generates perturbation inputs and writes reports without
invoking the pipeline. The pipeline must never be spawned; output JSON
files must not appear. Reports must explicitly mark the run as dry.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

import kelvin.check as check_mod
from kelvin.check import run_check
from kelvin.event_log import EventLogger


CASE_CONTENT = """\
## Idea
An idea.

## Customer
A customer.

## Money
$10/month.

## Alternative
None.
"""

CASE2_CONTENT = """\
## Idea
Second idea.

## Customer
Another customer.

## Money
$20/month.

## Alternative
Doing it manually.
"""


def _setup(tmp: Path) -> None:
    """Build a minimal corpus + config. The `run:` command would be
    catastrophically wrong (points at a missing script) — dry-run must
    never exec it, which is itself a dry-run smoke test."""
    cases = tmp / "cases"
    cases.mkdir()
    (cases / "one.md").write_text(CASE_CONTENT, encoding="utf-8")
    (cases / "two.md").write_text(CASE2_CONTENT, encoding="utf-8")
    (tmp / "kelvin.yaml").write_text(
        "run: /does/not/exist/pipeline --input {input} --output {output}\n"
        f"cases: {cases}\n"
        "decision_field: score\n"
        "governing_types: []\n"
        "seed: 0\n",
        encoding="utf-8",
    )


class TestDryRunProducesInputs:
    def test_perturbation_input_files_are_written(self, tmp_path: Path) -> None:
        _setup(tmp_path)
        run_check(tmp_path, dry_run=True, logger=EventLogger())
        # Each case has at least reorder-01 / reorder-02 / reorder-03 input.md.
        for case in ("one", "two"):
            pert_dir = tmp_path / "kelvin" / case / "perturbations"
            assert pert_dir.exists()
            # At minimum reorder variants.
            assert any(pert_dir.glob("reorder-*/input.md"))

    def test_baseline_input_is_written(self, tmp_path: Path) -> None:
        _setup(tmp_path)
        run_check(tmp_path, dry_run=True, logger=EventLogger())
        for case in ("one", "two"):
            baseline_input = tmp_path / "kelvin" / case / "baseline" / "input.md"
            assert baseline_input.exists()
            assert "## Idea" in baseline_input.read_text(encoding="utf-8")


class TestInvokeNeverCalled:
    def test_invoke_not_called_in_dry_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _setup(tmp_path)
        calls: list[tuple] = []

        def trap(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("invoke() called during dry-run")

        monkeypatch.setattr(check_mod, "invoke", trap)
        run_check(tmp_path, dry_run=True, logger=EventLogger())
        assert calls == []


class TestNoOutputJsonWritten:
    def test_no_output_json_files_exist(self, tmp_path: Path) -> None:
        _setup(tmp_path)
        run_check(tmp_path, dry_run=True, logger=EventLogger())
        # No variant produces output.json in dry mode.
        variant_outputs = list(
            (tmp_path / "kelvin").glob("*/perturbations/*/output.json")
        )
        assert variant_outputs == []
        # Baseline output.json also absent.
        baseline_outputs = list((tmp_path / "kelvin").glob("*/baseline/output.json"))
        assert baseline_outputs == []


class TestReportDryRunMarker:
    def test_run_report_has_dry_run_true(self, tmp_path: Path) -> None:
        _setup(tmp_path)
        run_check(tmp_path, dry_run=True, logger=EventLogger())
        report = json.loads(
            (tmp_path / "kelvin" / "report.json").read_text(encoding="utf-8")
        )
        assert report["dry_run"] is True

    def test_per_case_report_has_dry_run_true(self, tmp_path: Path) -> None:
        _setup(tmp_path)
        run_check(tmp_path, dry_run=True, logger=EventLogger())
        for case in ("one", "two"):
            case_report = json.loads(
                (tmp_path / "kelvin" / case / "report.json").read_text(
                    encoding="utf-8"
                )
            )
            assert case_report["dry_run"] is True

    def test_non_dry_run_omits_dry_run_key_from_run_report(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _setup(tmp_path)
        # Replace the broken pipeline with an always-succeeds fake so the
        # non-dry path can complete.
        pipeline = tmp_path / "pipe.py"
        pipeline.write_text(
            "import json, sys, argparse\n"
            "ap = argparse.ArgumentParser(); ap.add_argument('--input')\n"
            "ap.add_argument('--output'); args = ap.parse_args()\n"
            "json.dump({'score': 1}, open(args.output, 'w'))\n",
            encoding="utf-8",
        )
        (tmp_path / "kelvin.yaml").write_text(
            f"run: python3 {pipeline} --input {{input}} --output {{output}}\n"
            f"cases: {tmp_path / 'cases'}\n"
            "decision_field: score\n"
            "governing_types: []\n"
            "seed: 0\n",
            encoding="utf-8",
        )
        run_check(tmp_path, logger=EventLogger())
        report = json.loads(
            (tmp_path / "kelvin" / "report.json").read_text(encoding="utf-8")
        )
        assert "dry_run" not in report

    def test_non_dry_run_omits_dry_run_key_from_case_report(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _setup(tmp_path)
        pipeline = tmp_path / "pipe.py"
        pipeline.write_text(
            "import json, sys, argparse\n"
            "ap = argparse.ArgumentParser(); ap.add_argument('--input')\n"
            "ap.add_argument('--output'); args = ap.parse_args()\n"
            "json.dump({'score': 1}, open(args.output, 'w'))\n",
            encoding="utf-8",
        )
        (tmp_path / "kelvin.yaml").write_text(
            f"run: python3 {pipeline} --input {{input}} --output {{output}}\n"
            f"cases: {tmp_path / 'cases'}\n"
            "decision_field: score\n"
            "governing_types: []\n"
            "seed: 0\n",
            encoding="utf-8",
        )
        run_check(tmp_path, logger=EventLogger())
        case_report = json.loads(
            (tmp_path / "kelvin" / "one" / "report.json").read_text(
                encoding="utf-8"
            )
        )
        assert "dry_run" not in case_report


class TestConfirmBypassedInDryRun:
    def test_confirm_prompt_not_shown_when_dry_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _setup(tmp_path)
        called: list[str] = []

        def trap_input(prompt: str) -> str:
            called.append(prompt)
            return "y"

        # Also force TTY to be true so the only thing that could bypass
        # the prompt is the dry_run flag.
        monkeypatch.setattr(check_mod.sys.stdin, "isatty", lambda: True)
        # Patch the _accept_forecast input_fn via module-level input.
        monkeypatch.setattr("builtins.input", trap_input)

        run_check(
            tmp_path,
            dry_run=True,
            confirm_before_phase2=True,
            logger=EventLogger(),
        )
        assert called == []


class TestDryRunEventEmitted:
    def test_dry_run_skipped_invocation_events_fire(
        self, tmp_path: Path
    ) -> None:
        _setup(tmp_path)
        out = io.StringIO()
        err = io.StringIO()
        logger = EventLogger(fmt="json", stdout=out, stderr=err)
        run_check(tmp_path, dry_run=True, logger=logger)

        events = [
            json.loads(line) for line in out.getvalue().splitlines() if line
        ]
        skipped = [
            e for e in events if e["event"] == "dry_run_skipped_invocation"
        ]
        # At minimum one baseline + several perturbations per case.
        assert len(skipped) >= 2  # 2 baselines (one per case), no further
        # Baseline events present for each case.
        baseline_cases = {
            e["case"] for e in skipped if e.get("kind") == "baseline"
        }
        assert baseline_cases == {"one", "two"}
        # At least one perturbation-kind event.
        pert_kinds = {
            e.get("kind") for e in skipped if e.get("variant_id") is not None
        }
        assert pert_kinds  # non-empty


class TestDryRunScoresAreNull:
    def test_invariance_sensitivity_kelvin_are_null(
        self, tmp_path: Path
    ) -> None:
        _setup(tmp_path)
        run_check(tmp_path, dry_run=True, logger=EventLogger())
        report = json.loads(
            (tmp_path / "kelvin" / "report.json").read_text(encoding="utf-8")
        )
        assert report["invariance"] is None
        assert report["sensitivity"] is None
        assert report["kelvin_score"] is None
