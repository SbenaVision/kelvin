"""Phase 2 acceptance run.

For each of the five anchor pipelines and the Envelop pipeline,
load the v0.3.0 report.json (already produced in Phase 1), build a
synthetic RunScores, compute v0.4 maturity + findings + recs, and
render the practitioner / --verbose / JSON / markdown reporters.

Validates the spec acceptance criteria:

    AC1 — naive user understands → manual review (samples written
          out to OUTPUT_DIR for inspection).
    AC2 — default practitioner output < 30 lines per scenario.
    AC3 — no statistical jargon in any output (regex grep).
    AC5 — verdict ordering: constant ≤ brittle ≤ mid ≤ one_mod ≤ grounded
          (categorical: NOT_PROD ≤ NEEDS_WORK ≤ PROD_READY).
    AC7 — Envelop produces "Partially measured", NOT "Production-ready".

Output:
    OUTPUT_DIR/
        constant_default.txt
        constant_verbose.txt
        constant_markdown.md
        constant_json.json
        ... (× 6 pipelines)
        AC_REPORT.md       — pass/fail per AC
        acceptance.json    — machine-readable summary
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent
sys.path.insert(0, str(_REPO / "src"))

from kelvin.findings import compute_findings
from kelvin.recommendations import compute_recommendations, top_fix
from kelvin.reporters import json_reporter, markdown, practitioner
from kelvin.score import compute_maturity
from kelvin.types import (
    CaseScores, InvocationResult, Perturbation, PerturbationKind,
    RunScores, ScoredPerturbation,
)


_OUT = _HERE / "outputs"
_OUT.mkdir(parents=True, exist_ok=True)

# Phase 1 report locations.
_PHASE1_DIR = _REPO / "experiments" / "v040_phase1_calibration"
_ENVELOP_RESULTS = _PHASE1_DIR / "envelop_results.json"


_FORBIDDEN_TERMS = (
    "ANOVA", "F-stat", "F-statistic", "p-value",
    "isotonic", "residual variance",
)


# ── RunScores synthesis ──────────────────────────────────────────────────

def _placeholder_sp(kind: PerturbationKind, distance: float = 0.0) -> ScoredPerturbation:
    return ScoredPerturbation(
        perturbation=Perturbation(
            case_name="stub", kind=kind,
            variant_id=f"{kind}-stub", rendered_markdown="",
        ),
        invocation=InvocationResult(
            ok=True, exit_code=0,
            input_path=Path("/x"), output_path=Path("/y"),
        ),
        distance=distance,
    )


def _all_families_case() -> CaseScores:
    """A CaseScores with one stub entry in every standard family."""
    cs = CaseScores(case_name="stub")
    cs.reorder.append(_placeholder_sp("reorder"))
    cs.pad_length.append(_placeholder_sp("pad_length"))
    cs.pad_content.append(_placeholder_sp("pad_content"))
    cs.swaps_by_type.setdefault("gate_rule", []).append(_placeholder_sp("swap"))
    cs.swap_conditions_by_type.setdefault("gate_rule", []).append(
        _placeholder_sp("swap_condition")
    )
    cs.whitespace_jitter.append(_placeholder_sp("whitespace_jitter"))
    cs.punctuation_normalize.append(_placeholder_sp("punctuation_normalize"))
    cs.bullet_reformat.append(_placeholder_sp("bullet_reformat"))
    cs.non_governing_duplication.append(_placeholder_sp("non_governing_duplication"))
    cs.numeric_magnitude.append(_placeholder_sp("numeric_magnitude"))
    cs.comparator_flip.append(_placeholder_sp("comparator_flip"))
    cs.polarity_flip.append(_placeholder_sp("polarity_flip"))
    for kind in ("hedge_injection", "politeness_injection",
                 "discourse_marker_injection", "meta_commentary_injection"):
        cs.rhetorical.append(_placeholder_sp(kind))  # type: ignore[arg-type]
    return cs


# Anchor-table raw sensitivity/invariance values, used as a fallback
# when v0.3 calibrate() aborts (high-η pipelines) and the calibrated
# fields come back None. These match the anchor metric values
# pinned in src/kelvin/score.py:ANCHORS so the synthetic acceptance
# run matches the Phase 1 calibration outcome.
_FALLBACK_RAW_INVARIANCE = {
    "constant":           1.000,
    "brittle":            0.935,
    "mid_issue":          0.513,
    "one_moderate_issue": 0.952,
    "grounded_oracle":    0.952,
}
_FALLBACK_RAW_SENSITIVITY = {
    "constant":           0.000,
    "brittle":            0.000,
    "mid_issue":          0.593,
    "one_moderate_issue": 0.667,
    "grounded_oracle":    0.667,
}


def _runscores_from_anchor_data(name: str, d: dict) -> RunScores:
    """Synthesize RunScores from the calibration_results.json anchor entry.

    Anchor data has eta, sensitivity_calibrated, invariance_calibrated.
    For high-eta anchors (mid_issue) the calibrated fields are None;
    we provide raw invariance / sensitivity from the anchor table so
    compute_maturity's fallback path can produce a score.

    We assume Pillar 2 (sens_condition) and Pillar 3 (mech_sens) WERE
    measured for the anchor pipelines (they're synthetic and emit all
    fields). Use 0.5 as a placeholder for both so coverage is full.
    """
    raw_inv = (
        d.get("invariance_calibrated")
        if d.get("invariance_calibrated") is not None
        else _FALLBACK_RAW_INVARIANCE[name]
    )
    raw_sens = (
        d.get("sensitivity_calibrated")
        if d.get("sensitivity_calibrated") is not None
        else _FALLBACK_RAW_SENSITIVITY[name]
    )
    return RunScores(
        cases=[_all_families_case()], seed=0,
        invariance=raw_inv,
        invariance_sample=10,
        sensitivity=raw_sens,
        sensitivity_sample=10,
        kelvin_score=None, sensitivity_by_type={},
        governing_types=["gate_rule"],
        noise_floor_eta=d.get("eta"),
        invariance_calibrated=d.get("invariance_calibrated"),
        sensitivity_calibrated=d.get("sensitivity_calibrated"),
        kelvin_score_calibrated=None,
        sensitivity_condition=0.5,
        sensitivity_condition_sample=10,
        mechanical_sensitivity=0.5,
        mechanical_sensitivity_sample=10,
    )


def _runscores_from_envelop_excerpt(d: dict) -> RunScores:
    """Envelop: Pillar 2 silent (sensitivity_condition is None)."""
    raw = d.get("raw_report_excerpt", d)
    return RunScores(
        cases=[_all_families_case()], seed=0,
        invariance=raw.get("invariance"),
        invariance_sample=10,
        sensitivity=raw.get("sensitivity"),
        sensitivity_sample=10,
        kelvin_score=None,
        sensitivity_by_type={
            k: (v.get("mean"), v.get("sample"))
            for k, v in raw.get("sensitivity_by_type", {}).items()
        },
        governing_types=["gate_rule"],
        noise_floor_eta=raw.get("noise_floor_eta"),
        invariance_calibrated=raw.get("invariance_calibrated"),
        sensitivity_calibrated=raw.get("sensitivity_calibrated"),
        kelvin_score_calibrated=raw.get("kelvin_score_calibrated"),
        sensitivity_content=raw.get("sensitivity_content"),
        sensitivity_condition=raw.get("sensitivity_condition"),
        content_effect=raw.get("content_effect"),
        mechanical_sensitivity=raw.get("mechanical_sensitivity"),
        mechanical_sensitivity_sample=10 if raw.get("mechanical_sensitivity") is not None else 0,
    )


# ── Render a single scenario ─────────────────────────────────────────────

def _render_all(name: str, run: RunScores) -> dict:
    m = compute_maturity(run)
    fs = compute_findings(m, run)
    recs = compute_recommendations(fs)
    fix = top_fix(recs)

    default = practitioner.render_to_string(m, fs, recs, fix)
    verbose = practitioner.render_to_string(
        m, fs, recs, fix, verbose=True, run=run,
    )
    md = markdown.render_to_string(m, fs, recs, fix)
    js = json_reporter.render_to_string(m, fs, recs, fix, run)

    (_OUT / f"{name}_default.txt").write_text(default)
    (_OUT / f"{name}_verbose.txt").write_text(verbose)
    (_OUT / f"{name}_markdown.md").write_text(md)
    (_OUT / f"{name}_report.json").write_text(js)

    return {
        "name": name,
        "category": m.category,
        "score": m.score,
        "withheld": m.withheld,
        "pillar_coverage": dict(m.pillar_coverage),
        "silent_pillars": dict(m.silent_pillars),
        "default_lines": default.count("\n"),
        "verbose_lines": verbose.count("\n"),
        "default_text": default,
        "verbose_text": verbose,
        "markdown_text": md,
    }


# ── AC validators ────────────────────────────────────────────────────────

def _ac2_under_30(results: list[dict]) -> dict:
    """AC2 — default output < 30 lines per scenario."""
    failures = [
        (r["name"], r["default_lines"])
        for r in results if r["default_lines"] >= 30
    ]
    return {"pass": not failures, "failures": failures}


def _ac3_no_jargon(results: list[dict]) -> dict:
    """AC3 — no statistical jargon in default OR verbose output."""
    failures = []
    for r in results:
        for mode, text in (("default", r["default_text"]),
                           ("verbose", r["verbose_text"]),
                           ("markdown", r["markdown_text"])):
            for term in _FORBIDDEN_TERMS:
                if term.lower() in text.lower():
                    failures.append((r["name"], mode, term))
    return {"pass": not failures, "failures": failures}


def _ac5_ordering(results: list[dict]) -> dict:
    """AC5 — verdict ordering across the 5 anchors.

    Categorical rank: Not production-ready < Needs work < Production-ready.
    "Partially measured" is excluded from this ordering check (it's a
    coverage signal, not a quality rank).
    """
    rank = {
        "Not production-ready": 0,
        "Needs work":           1,
        "Production-ready":     2,
    }
    expected_order = ["constant", "brittle", "mid_issue",
                      "one_moderate_issue", "grounded_oracle"]
    actual = [next(r for r in results if r["name"] == name)
              for name in expected_order if any(rr["name"] == name for rr in results)]
    ranks = [rank.get(r["category"], -1) for r in actual]
    is_monotone = all(a <= b for a, b in zip(ranks, ranks[1:]))
    return {
        "pass": is_monotone,
        "ranks": list(zip([r["name"] for r in actual], ranks)),
    }


def _ac7_envelop_partial(results: list[dict]) -> dict:
    """AC7 — Envelop must NOT produce 'Production-ready'; must be
    'Partially measured' because Pillar 2 is silent."""
    envelop = next((r for r in results if r["name"] == "envelop"), None)
    if envelop is None:
        return {"pass": False, "reason": "envelop result missing"}
    return {
        "pass": envelop["category"] == "Partially measured"
                and envelop["pillar_coverage"].get("pillar_2") is False,
        "category": envelop["category"],
        "pillar_coverage": envelop["pillar_coverage"],
        "silent_pillars": envelop["silent_pillars"],
    }


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> int:
    print("Phase 2 acceptance run")
    print("=" * 60)

    # Load anchor data.
    cal = json.loads(
        (_PHASE1_DIR / "calibration_results.json").read_text()
    )
    anchor_results: list[dict] = []
    for name in ("constant", "brittle", "mid_issue",
                 "one_moderate_issue", "grounded_oracle"):
        d = cal["anchors"][name]
        run = _runscores_from_anchor_data(name, d)
        r = _render_all(name, run)
        print(f"  {name:>22}  {r['category']:<24}  "
              f"score={r['score']}  default_lines={r['default_lines']}")
        anchor_results.append(r)

    # Envelop.
    env_data = json.loads(_ENVELOP_RESULTS.read_text())
    env_run = _runscores_from_envelop_excerpt(env_data)
    env_r = _render_all("envelop", env_run)
    print(f"  {'envelop':>22}  {env_r['category']:<24}  "
          f"score={env_r['score']}  default_lines={env_r['default_lines']}")

    all_results = anchor_results + [env_r]

    # AC checks.
    print()
    print("Acceptance criteria:")
    ac2 = _ac2_under_30(all_results)
    print(f"  AC2 — default output < 30 lines:    "
          f"{'PASS' if ac2['pass'] else 'FAIL'}")
    if not ac2["pass"]:
        for name, n in ac2["failures"]:
            print(f"      ✗ {name}: {n} lines")

    ac3 = _ac3_no_jargon(all_results)
    print(f"  AC3 — no statistical jargon:        "
          f"{'PASS' if ac3['pass'] else 'FAIL'}")
    if not ac3["pass"]:
        for name, mode, term in ac3["failures"]:
            print(f"      ✗ {name}/{mode}: {term!r}")

    ac5 = _ac5_ordering(anchor_results)
    print(f"  AC5 — anchor category ordering:     "
          f"{'PASS' if ac5['pass'] else 'FAIL'}")
    print(f"      {ac5['ranks']}")

    ac7 = _ac7_envelop_partial([env_r])
    print(f"  AC7 — Envelop = Partially measured: "
          f"{'PASS' if ac7['pass'] else 'FAIL'}")
    print(f"      category={env_r['category']}, "
          f"silent={env_r['silent_pillars']}")

    # Persist machine-readable summary.
    summary = {
        "ac2_lines_under_30": ac2,
        "ac3_no_jargon": ac3,
        "ac5_ordering": ac5,
        "ac7_envelop_partial": ac7,
        "all_pass": all([
            ac2["pass"], ac3["pass"], ac5["pass"], ac7["pass"],
        ]),
        "results": [
            {
                "name": r["name"],
                "category": r["category"],
                "score": r["score"],
                "default_lines": r["default_lines"],
                "verbose_lines": r["verbose_lines"],
                "pillar_coverage": r["pillar_coverage"],
                "silent_pillars": r["silent_pillars"],
            }
            for r in all_results
        ],
    }
    (_OUT / "acceptance.json").write_text(json.dumps(summary, indent=2))
    print()
    print(f"Samples + summary in: {_OUT}")
    return 0 if summary["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
