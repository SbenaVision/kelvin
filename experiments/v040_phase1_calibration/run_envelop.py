"""Run Kelvin v0.4 against the Envelop local pipeline.

Real-world test of whether the maturity score is actionable on a
production-flavored deterministic pipeline. Envelop's local
implementation lives in a parallel worktree
(`.claude/worktrees/competent-bose-7a0d7d/experiments/envelop_local/`)
— we point Kelvin at that pipeline + its 8-case corpus and read the
resulting metrics.

Output: reports envelop_results.json + prints maturity, sub-scores,
top weakest axes, and a plain-language interpretation.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent
sys.path.insert(0, str(_REPO / "src"))

from kelvin.score import compute_maturity
from kelvin.taxonomy import Axis
from kelvin.types import (
    CaseScores, InvocationResult, Perturbation,
    PerturbationKind, RunScores, ScoredPerturbation,
)


VENV_PYTHON = "/Users/sb/MyDev/Kelvin/.venv/bin/python"
ENVELOP_ROOT = Path("/Users/sb/MyDev/Kelvin/.claude/worktrees/competent-bose-7a0d7d/experiments/envelop_local")


KELVIN_YAML = f"""\
run: {VENV_PYTHON} {ENVELOP_ROOT}/pipelines/envelop.py --input {{input}} --output {{output}}
cases: {ENVELOP_ROOT}/cases
decision_field: verdict
governing_types: [gate_rule]
seed: 0
noise_floor:
  enabled: true
  n_replays: 30
counterfactual_swap:
  enabled: true
intra_slot:
  enabled: true
  enabled_families:
    - whitespace_jitter
    - punctuation_normalize
    - bullet_reformat
    - non_governing_duplication
    - numeric_magnitude
    - comparator_flip
    - polarity_flip
    - hedge_injection
    - politeness_injection
    - discourse_marker_injection
    - meta_commentary_injection
"""


def _stub_runscores_from_report(report: dict) -> RunScores:
    """Same construction as run_calibration.py — the score function
    only needs metric values and a non-empty family list per case."""
    placeholder_inv = InvocationResult(
        ok=True, exit_code=0,
        input_path=Path("/x"), output_path=Path("/y"),
    )

    def _sp(kind: PerturbationKind) -> ScoredPerturbation:
        return ScoredPerturbation(
            perturbation=Perturbation(
                case_name="stub", kind=kind,
                variant_id=f"{kind}-stub", rendered_markdown="",
            ),
            invocation=placeholder_inv, distance=0.0,
        )

    cs = CaseScores(case_name="stub")
    cs.reorder.append(_sp("reorder"))
    cs.pad_length.append(_sp("pad_length"))
    cs.pad_content.append(_sp("pad_content"))
    cs.swaps_by_type.setdefault("gate_rule", []).append(_sp("swap"))
    cs.swap_conditions_by_type.setdefault("gate_rule", []).append(_sp("swap_condition"))
    cs.whitespace_jitter.append(_sp("whitespace_jitter"))
    cs.punctuation_normalize.append(_sp("punctuation_normalize"))
    cs.bullet_reformat.append(_sp("bullet_reformat"))
    cs.non_governing_duplication.append(_sp("non_governing_duplication"))
    cs.numeric_magnitude.append(_sp("numeric_magnitude"))
    cs.comparator_flip.append(_sp("comparator_flip"))
    cs.polarity_flip.append(_sp("polarity_flip"))
    for kind in ("hedge_injection", "politeness_injection",
                 "discourse_marker_injection", "meta_commentary_injection"):
        cs.rhetorical.append(_sp(kind))  # type: ignore[arg-type]

    return RunScores(
        cases=[cs], seed=report.get("seed", 0),
        invariance=report.get("invariance"),
        invariance_sample=report.get("invariance_sample", 0),
        sensitivity=report.get("sensitivity"),
        sensitivity_sample=report.get("sensitivity_sample", 0),
        kelvin_score=report.get("kelvin_score"),
        sensitivity_by_type=report.get("sensitivity_by_type", {}),
        governing_types=report.get("governing_types", []),
        single_case_run=report.get("single_case_run", False),
        noise_floor_eta=report.get("noise_floor_eta"),
        invariance_calibrated=report.get("invariance_calibrated"),
        sensitivity_calibrated=report.get("sensitivity_calibrated"),
        kelvin_score_calibrated=report.get("kelvin_score_calibrated"),
        sensitivity_content=report.get("sensitivity_content"),
        sensitivity_content_sample=report.get("sensitivity_content_sample", 0),
        sensitivity_condition=report.get("sensitivity_condition"),
        sensitivity_condition_sample=report.get("sensitivity_condition_sample", 0),
        content_effect=report.get("content_effect"),
        mechanical_sensitivity=report.get("mechanical_sensitivity"),
        mechanical_sensitivity_sample=report.get("mechanical_sensitivity_sample", 0),
    )


def main() -> int:
    workdir = _HERE / "_envelop_workdir"
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    (workdir / "kelvin.yaml").write_text(KELVIN_YAML)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(_REPO / "src") + os.pathsep + env.get("PYTHONPATH", "")

    print("=" * 72)
    print("Kelvin v0.4 against Envelop local pipeline")
    print("=" * 72)
    print(f"  Pipeline: {ENVELOP_ROOT}/pipelines/envelop.py")
    print(f"  Corpus:   {ENVELOP_ROOT}/cases (8 cases)")
    print(f"  K_REPLAYS: 30")
    print()
    print("Running kelvin check...")
    proc = subprocess.run(
        [VENV_PYTHON, "-m", "kelvin", "check"],
        cwd=str(workdir), env=env, capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        print("FAILED")
        print("STDOUT (tail):", proc.stdout[-1000:])
        print("STDERR (tail):", proc.stderr[-1000:])
        return 1

    report = json.loads((workdir / "kelvin" / "report.json").read_text())
    runs = _stub_runscores_from_report(report)
    m = compute_maturity(runs)

    # ─── Per-axis breakdown ─────────────────────────────────────────────
    print()
    print(f"Maturity: {m.score} / 10  ({m.category})")
    if m.withheld:
        print(f"  WITHHELD: {m.withheld_reason}")
    print()
    print("Per-axis raw metrics:")
    print(f"  drift η:           {report.get('noise_floor_eta'):.4f}")
    print(f"  sensitivity_cal:   {report.get('sensitivity_calibrated')}")
    print(f"  invariance_cal:    {report.get('invariance_calibrated')}")
    print()
    print("Per-axis sub-scores (0–1):")
    for axis, sub in m.sub_scores.items():
        print(f"  {axis.value:13s}: {sub:.3f}")
    print()
    print("Per-family raw distance (when available, lower = more invariant/sensitive):")
    print(f"  invariance (overall): {report.get('invariance')}")
    print(f"  sensitivity (overall): {report.get('sensitivity')}")
    print(f"  sensitivity_by_type: {report.get('sensitivity_by_type')}")
    print(f"  mechanical_sensitivity: {report.get('mechanical_sensitivity')}")
    print(f"  sensitivity_content: {report.get('sensitivity_content')}")
    print(f"  sensitivity_condition: {report.get('sensitivity_condition')}")
    print(f"  content_effect: {report.get('content_effect')}")
    print()

    # ─── Top weakest axes ──────────────────────────────────────────────
    if m.sub_scores:
        sorted_axes = sorted(m.sub_scores.items(), key=lambda kv: kv[1])
        print("Top weakest axes (lowest sub-scores first):")
        for axis, sub in sorted_axes[:3]:
            print(f"  {axis.value}: sub-score {sub:.3f}")
    print()

    # ─── Persist ───────────────────────────────────────────────────────
    out = {
        "maturity_score": m.score,
        "category": m.category,
        "withheld": m.withheld,
        "withheld_reason": m.withheld_reason,
        "sub_scores": {a.value: s for a, s in m.sub_scores.items()},
        "metrics": {a.value: v for a, v in m.metrics.items()},
        "raw_report_excerpt": {
            "noise_floor_eta": report.get("noise_floor_eta"),
            "invariance_calibrated": report.get("invariance_calibrated"),
            "sensitivity_calibrated": report.get("sensitivity_calibrated"),
            "kelvin_score_calibrated": report.get("kelvin_score_calibrated"),
            "invariance": report.get("invariance"),
            "sensitivity": report.get("sensitivity"),
            "sensitivity_by_type": report.get("sensitivity_by_type"),
            "mechanical_sensitivity": report.get("mechanical_sensitivity"),
            "sensitivity_content": report.get("sensitivity_content"),
            "sensitivity_condition": report.get("sensitivity_condition"),
            "content_effect": report.get("content_effect"),
        },
    }
    (_HERE / "envelop_results.json").write_text(json.dumps(out, indent=2))
    print(f"wrote {_HERE / 'envelop_results.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
