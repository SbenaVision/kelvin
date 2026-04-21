from __future__ import annotations

import json
import shlex
from pathlib import Path

import pytest

from kelvin.check import AbortRun, CheckError, run_check
from kelvin.config import CONFIG_FILENAME, KelvinConfig

# ─── Pipeline fixtures ──────────────────────────────────────────────────────
#
# Each test writes a small Python script to tmp_path that acts as the user's
# pipeline. kelvin.yaml is written to invoke the script.
#
# Scripts:
#   always_approve        → writes {"recommendation": "approve"}
#   always_reject         → writes {"recommendation": "reject"}
#   missing_field         → writes a valid JSON object but no `recommendation`
#   invalid_json          → writes non-JSON to output
#   non_scalar            → writes {"recommendation": [1, 2]}
#   numeric_score         → writes {"score": <count of '##' headers in input>}
#   fails                 → exits 1
#   reacts_to_gate_rule   → "approve" if "A_G1" in input else "reject"

BASE = """\
import argparse, json, sys
ap = argparse.ArgumentParser()
ap.add_argument('--input')
ap.add_argument('--output')
args = ap.parse_args()
"""

SCRIPTS = {
    "always_approve": BASE + "json.dump({'recommendation': 'approve'}, open(args.output, 'w'))\n",
    "always_reject": BASE + "json.dump({'recommendation': 'reject'}, open(args.output, 'w'))\n",
    "missing_field": BASE
    + "json.dump({'other': 'x', 'narrative': 'y'}, open(args.output, 'w'))\n",
    "invalid_json": BASE + "open(args.output, 'w').write('not json {')\n",
    "non_scalar": BASE + "json.dump({'recommendation': [1, 2, 3]}, open(args.output, 'w'))\n",
    "numeric_score": BASE
    + "text = open(args.input).read()\n"
    + "json.dump({'score': text.count('##')}, open(args.output, 'w'))\n",
    "fails": BASE + "sys.exit(1)\n",
    "reacts_to_gate_rule": BASE
    + "text = open(args.input).read()\n"
    + "decision = 'approve' if 'A_G1' in text else 'reject'\n"
    + "json.dump({'recommendation': decision}, open(args.output, 'w'))\n",
}


# ─── Test-env helpers ───────────────────────────────────────────────────────


def _setup_project(
    tmp_path: Path,
    *,
    pipeline: str,
    decision_field: str = "recommendation",
    governing_types: list[str] | None = None,
    seed: int = 0,
    cases: dict[str, str] | None = None,
) -> Path:
    """Create a working directory with kelvin.yaml, pipeline script, and cases.

    Returns the cwd Path to pass to run_check.
    """
    script = tmp_path / "pipe.py"
    script.write_text(SCRIPTS[pipeline], encoding="utf-8")

    cases_dir = tmp_path / "ventures"
    cases_dir.mkdir(exist_ok=True)
    cases = cases or {
        "acme": "## Interview\nCustomer pain point.\n\n## Gate Rule\nA_G1 content.\n",
        "zeta": "## Interview\nDifferent customer.\n\n## Gate Rule\nZ_G1 content.\n",
    }
    for name, content in cases.items():
        (cases_dir / f"{name}.md").write_text(content, encoding="utf-8")

    cfg = KelvinConfig(
        run=f"python3 {shlex.quote(str(script))} --input {{input}} --output {{output}}",
        cases=cases_dir,
        decision_field=decision_field,
        governing_types=governing_types or ["gate_rule"],
        seed=seed,
    )
    cfg.save(tmp_path / CONFIG_FILENAME)
    return tmp_path


def _run(
    cwd: Path,
    *,
    only: str | None = None,
    seed_override: int | None = None,
) -> tuple[list[str], object]:
    """Run check, collecting echo lines."""
    lines: list[str] = []
    try:
        scores = run_check(
            cwd, only=only, seed_override=seed_override, echo=lines.append
        )
        return lines, scores
    except (AbortRun, CheckError) as exc:
        return lines, exc


# ─── Happy paths ────────────────────────────────────────────────────────────


class TestHappyPath:
    def test_invariance_is_one_when_pipeline_ignores_input(self, tmp_path: Path) -> None:
        cwd = _setup_project(tmp_path, pipeline="always_approve")
        _, scores = _run(cwd)
        assert scores.invariance == 1.0
        assert scores.sensitivity == 0.0  # swap also unchanged → no sensitivity
        assert scores.invariance_sample > 0
        # report files on disk
        assert (cwd / "kelvin" / "report.json").exists()
        assert (cwd / "kelvin" / "acme" / "report.json").exists()
        assert (cwd / "kelvin" / "zeta" / "report.json").exists()
        # baseline inputs/outputs exist
        assert (cwd / "kelvin" / "acme" / "baseline" / "input.md").exists()
        assert (cwd / "kelvin" / "acme" / "baseline" / "output.json").exists()

    def test_sensitivity_is_nonzero_when_pipeline_reads_governing_content(
        self, tmp_path: Path
    ) -> None:
        # A case with "A_G1" in its gate_rule → baseline says approve.
        # Swap replaces A_G1 with a peer gate_rule (not containing "A_G1") → reject.
        cwd = _setup_project(
            tmp_path,
            pipeline="reacts_to_gate_rule",
            cases={
                "acme": "## Interview\nx.\n\n## Gate Rule\nA_G1 content.\n",
                "zeta": "## Interview\ny.\n\n## Gate Rule\nZ_G1 content.\n",
            },
        )
        _, scores = _run(cwd)
        # Baseline for acme: "approve" (A_G1 present). Swap removes A_G1 → "reject".
        # Baseline for zeta: "reject" (no A_G1). Swap inserts A_G1 → "approve".
        # Both flips = sensitivity 1.0.
        assert scores.sensitivity == 1.0
        assert scores.sensitivity_sample == 2  # 1 swap each, capped

    def test_numeric_decision_field(self, tmp_path: Path) -> None:
        cwd = _setup_project(
            tmp_path,
            pipeline="numeric_score",
            decision_field="score",
            governing_types=[],
        )
        _, scores = _run(cwd)
        # Reorder and pad both change the count of '##' (pad adds, reorder doesn't).
        # Reorder → same header count → distance 0.
        # Pad → extra headers → distance > 0 but bounded.
        assert scores.invariance is not None

    def test_report_json_shape(self, tmp_path: Path) -> None:
        cwd = _setup_project(tmp_path, pipeline="always_approve")
        _run(cwd)
        run_report = json.loads((cwd / "kelvin" / "report.json").read_text())
        assert run_report["seed"] == 0
        assert run_report["decision_field"] == "recommendation"
        assert "acme" in run_report["cases"]["run"]
        assert "zeta" in run_report["cases"]["run"]
        case_report = json.loads((cwd / "kelvin" / "acme" / "report.json").read_text())
        assert case_report["case"] == "acme"
        assert case_report["baseline"]["ok"] is True
        assert case_report["baseline"]["decision_value"] == "approve"


# ─── Flags ──────────────────────────────────────────────────────────────────


class TestFlags:
    def test_only_restricts_which_case_is_scored(self, tmp_path: Path) -> None:
        cwd = _setup_project(tmp_path, pipeline="always_approve")
        _, scores = _run(cwd, only="acme")
        names = [c.case_name for c in scores.cases]
        assert names == ["acme"]
        # zeta still available in the peer pool (swap/pad should draw from it);
        # that means acme's perturbations still run.
        assert any(c.baseline_ok for c in scores.cases)

    def test_only_with_unknown_case_raises_check_error(self, tmp_path: Path) -> None:
        cwd = _setup_project(tmp_path, pipeline="always_approve")
        _, outcome = _run(cwd, only="nonexistent")
        assert isinstance(outcome, CheckError)
        assert "nonexistent" in str(outcome)

    def test_seed_override_produces_different_perturbations(self, tmp_path: Path) -> None:
        cwd = _setup_project(tmp_path, pipeline="always_approve", seed=0)
        _run(cwd)  # seed 0
        a_order = json.loads(
            (cwd / "kelvin" / "acme" / "report.json").read_text()
        )["perturbations"]
        _run(cwd, seed_override=999)  # rerun with overridden seed
        b_order = json.loads(
            (cwd / "kelvin" / "acme" / "report.json").read_text()
        )["perturbations"]
        # At least one perturbation's notes (orderings, peer choices) should differ.
        assert a_order != b_order


# ─── Failure handling ───────────────────────────────────────────────────────


class TestFailureHandling:
    def test_missing_decision_field_aborts_whole_run(self, tmp_path: Path) -> None:
        cwd = _setup_project(tmp_path, pipeline="missing_field")
        _, outcome = _run(cwd)
        assert isinstance(outcome, AbortRun)
        assert "recommendation" in str(outcome)

    def test_non_scalar_decision_aborts(self, tmp_path: Path) -> None:
        cwd = _setup_project(tmp_path, pipeline="non_scalar")
        _, outcome = _run(cwd)
        assert isinstance(outcome, AbortRun)
        assert "scalar" in str(outcome)

    def test_baseline_failure_skips_case_and_continues(self, tmp_path: Path) -> None:
        # Pipeline that fails only on "broken", succeeds elsewhere.
        script = tmp_path / "pipe.py"
        script.write_text(
            BASE
            + "import os\n"
            + "if 'broken' in args.input:\n"
            + "    sys.exit(1)\n"
            + "json.dump({'recommendation': 'approve'}, open(args.output, 'w'))\n",
            encoding="utf-8",
        )
        cases_dir = tmp_path / "ventures"
        cases_dir.mkdir()
        (cases_dir / "broken.md").write_text(
            "## Interview\nx.\n\n## Gate Rule\nG.\n", encoding="utf-8"
        )
        (cases_dir / "good.md").write_text(
            "## Interview\ny.\n\n## Gate Rule\nG2.\n", encoding="utf-8"
        )
        cfg = KelvinConfig(
            run=f"python3 {shlex.quote(str(script))} --input {{input}} --output {{output}}",
            cases=cases_dir,
            decision_field="recommendation",
            governing_types=["gate_rule"],
            seed=0,
        )
        cfg.save(tmp_path / CONFIG_FILENAME)

        lines, scores = _run(tmp_path)
        broken = next(c for c in scores.cases if c.case_name == "broken")
        good = next(c for c in scores.cases if c.case_name == "good")
        assert broken.baseline_ok is False
        assert good.baseline_ok is True
        # Distinct error message for baseline failure
        assert any("Baseline failed for broken" in line for line in lines)
        # run_report.json records it separately
        rr = json.loads((tmp_path / "kelvin" / "report.json").read_text())
        assert any(b["case"] == "broken" for b in rr["cases"]["baseline_failed"])
        assert "good" in rr["cases"]["baseline_ok"]

    def test_all_baselines_fail_raises_abort(self, tmp_path: Path) -> None:
        cwd = _setup_project(tmp_path, pipeline="fails")
        _, outcome = _run(cwd)
        assert isinstance(outcome, AbortRun)
        # run_report still written
        rr = json.loads((tmp_path / "kelvin" / "report.json").read_text())
        assert rr["cases"]["baseline_ok"] == []

    def test_perturbation_failures_are_logged_and_run_continues(
        self, tmp_path: Path
    ) -> None:
        # Pipeline that passes baseline but fails on any perturbation.
        # Detect a perturbation input by a marker only present in baselines.
        # Baselines and perturbations are both rendered via render_case, so their
        # formatting is identical — we distinguish by content: perturbations
        # contain either a pad or swap insert that changes the text.
        #
        # Simpler approach: always_approve baseline succeeds, pipeline succeeds
        # on every perturbation too → no perturbation failures. Already tested.
        #
        # Here, use a pipeline that fails on inputs containing 'peer' (which
        # pad inserts bring in from peer case names).
        script = tmp_path / "pipe.py"
        script.write_text(
            BASE
            + "text = open(args.input).read()\n"
            + "if 'peer' in text.lower():\n"
            + "    sys.exit(2)\n"
            + "json.dump({'recommendation': 'approve'}, open(args.output, 'w'))\n",
            encoding="utf-8",
        )
        cases_dir = tmp_path / "ventures"
        cases_dir.mkdir()
        (cases_dir / "acme.md").write_text(
            "## Interview\nAcme interview.\n\n## Gate Rule\nAG1.\n", encoding="utf-8"
        )
        # Use a case name containing "peer" so that when pad inserts a unit
        # whose header mentions the source case, the input will have 'peer'
        # only in padded variants. Actually the rendered markdown only contains
        # unit header + content, not case name. So we inject "peer" in the
        # peer case's unit content directly.
        (cases_dir / "zeta.md").write_text(
            "## Interview\npeer content here.\n\n## Gate Rule\npeer rule.\n",
            encoding="utf-8",
        )
        cfg = KelvinConfig(
            run=f"python3 {shlex.quote(str(script))} --input {{input}} --output {{output}}",
            cases=cases_dir,
            decision_field="recommendation",
            governing_types=["gate_rule"],
            seed=0,
        )
        cfg.save(tmp_path / CONFIG_FILENAME)
        _lines, scores = _run(tmp_path)
        # Acme baseline: no 'peer' → ok.
        acme = next(c for c in scores.cases if c.case_name == "acme")
        assert acme.baseline_ok is True
        # Pad variants for acme include peer units → fail.
        pad_failures = [sp for sp in acme.pad if sp.distance is None]
        assert len(pad_failures) > 0
        # Run still completes (scores calculated on succeeding perturbations).
        assert scores.invariance is not None or scores.invariance_sample == 0


# ─── Warnings / caps ────────────────────────────────────────────────────────


class TestWarningsAndCaps:
    def test_single_case_warns_no_peers(self, tmp_path: Path) -> None:
        cwd = _setup_project(
            tmp_path,
            pipeline="always_approve",
            cases={"acme": "## Interview\nA.\n\n## Gate Rule\nG.\n"},
        )
        _, scores = _run(cwd)
        assert any("Only one case" in w for w in scores.warnings)

    def test_missing_cases_dir_raises_check_error(self, tmp_path: Path) -> None:
        cwd = _setup_project(tmp_path, pipeline="always_approve")
        # Wipe the cases directory to simulate missing.
        import shutil

        shutil.rmtree(cwd / "ventures")
        _, outcome = _run(cwd)
        assert isinstance(outcome, CheckError)


# ─── Determinism ────────────────────────────────────────────────────────────


class TestDeterminism:
    def test_same_seed_same_output(self, tmp_path: Path) -> None:
        cwd = _setup_project(tmp_path, pipeline="always_approve", seed=13)
        _run(cwd)
        first = json.loads((cwd / "kelvin" / "acme" / "report.json").read_text())
        # Wipe and rerun with identical config.
        import shutil

        shutil.rmtree(cwd / "kelvin")
        _run(cwd)
        second = json.loads((cwd / "kelvin" / "acme" / "report.json").read_text())
        # Perturbation notes should be identical.
        assert [p["notes"] for p in first["perturbations"]] == [
            p["notes"] for p in second["perturbations"]
        ]


@pytest.fixture(autouse=True)
def _ensure_cwd_restored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests pass cwd explicitly to run_check; this fixture just keeps the
    real cwd untouched in case a test ever chdir's."""
    monkeypatch.chdir(tmp_path)
