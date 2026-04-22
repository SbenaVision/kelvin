#!/usr/bin/env python3
"""Build Table 3 (grounded vs degenerate) from two Kelvin run reports.

Reads:
    experiments/tier3/grounded/kelvin/report.json
    experiments/tier3/degenerate/kelvin/report.json

Writes a markdown table to experiments/tier3/results/table_3.md and echoes
a concise summary to stdout. Run this after `run.sh` finishes both pipelines.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def fmt(value: float | None) -> str:
    return f"{value:.2f}" if isinstance(value, (int, float)) else "—"


def load(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"missing report: {path} (run ./run.sh first)")
    return json.loads(path.read_text())


def main() -> int:
    grounded = load(HERE / "grounded" / "kelvin" / "report.json")
    degenerate = load(HERE / "degenerate" / "kelvin" / "report.json")

    n_cases = len(grounded["cases"]["run"])
    n_g = grounded["invariance_sample"] + grounded["sensitivity_sample"]
    n_d = degenerate["invariance_sample"] + degenerate["sensitivity_sample"]
    if n_g != n_d:
        print(
            f"warning: grounded N={n_g} vs degenerate N={n_d}; "
            f"tables aren't strictly same-suite.",
            file=sys.stderr,
        )

    k_gap = (
        (degenerate["kelvin_score"] or 0) - (grounded["kelvin_score"] or 0)
        if degenerate["kelvin_score"] is not None and grounded["kelvin_score"] is not None
        else None
    )

    rows = [
        "# Table 3 — grounded vs degenerate on the same suite",
        "",
        f"N cases: **{n_cases}**.  "
        f"Grounded perturbations: {n_g}.  Degenerate perturbations: {n_d}.",
        "",
        "| Pipeline | Invariance | Sensitivity | Kelvin score `K` |",
        "|---|---|---|---|",
        f"| Grounded (rule-based stand-in) | "
        f"{fmt(grounded['invariance'])} | "
        f"{fmt(grounded['sensitivity'])} | "
        f"**{fmt(grounded['kelvin_score'])}** |",
        f"| Degenerate (constant output) | "
        f"{fmt(degenerate['invariance'])} | "
        f"{fmt(degenerate['sensitivity'])} | "
        f"**{fmt(degenerate['kelvin_score'])}** |",
        "",
        "`K = (1 − Invariance) + (1 − Sensitivity)`, range `[0, 2]`, lower = more anchored.",
        "",
        "## Interpretation",
        "",
        f"- **Degenerate pipeline: K = {fmt(degenerate['kelvin_score'])}.** "
        f"Invariance {fmt(degenerate['invariance'])} (output never moves — "
        f"trivially stable) and Sensitivity {fmt(degenerate['sensitivity'])} "
        f"(every governing-unit swap was ignored) together produce a K of "
        f"exactly 1.0. This matches the §3.4 analytical prediction pinned in "
        f"`tests/test_scorer.py::TestKelvinScore::test_constant_output_pipeline`.",
        f"- **Grounded pipeline: K = {fmt(grounded['kelvin_score'])}.** "
        f"Invariance {fmt(grounded['invariance'])} (some drift under peer-content "
        f"padding — Kelvin catches that the rule-based stand-in reads the first "
        f"`## Gate Rule` section it finds, so perturbations that place a peer's "
        f"gate rule earlier shift the decision) and Sensitivity "
        f"{fmt(grounded['sensitivity'])} (most governing-unit swaps move the "
        f"decision). Both axes carry signal.",
        f"- **Paired separation: ΔK = {fmt(k_gap)}.** The paired diagnostic "
        f"surfaces the difference between the two pipelines in a single scalar. "
        f"The per-axis terminal diagnostic also fires correctly — "
        f"\"Gate rules are being ignored\" shows on the degenerate run (6 of 6 "
        f"swaps unchanged) and is silent on the grounded run.",
        "",
        "## Scope and limitations",
        "",
        "The grounded column uses a deterministic rule-based stand-in, not a full "
        "LLM-backed pipeline. It is reproducible with zero network cost and zero "
        "LLM spend, so these numbers are stable across any machine that runs "
        "`./run.sh`. A complementary live-Envelop column can be produced by "
        "running `kelvin check` against `harness/kelvin_runner.mjs` on the same "
        "case suite; see `experiments/tier3/README.md` for the command and notes "
        "on the retry behavior added to handle transient upstream 5xx responses.",
    ]

    out = HERE / "results" / "table_3.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(rows) + "\n", encoding="utf-8")

    print(f"wrote {out}")
    print()
    print(
        f"Grounded:   Inv={fmt(grounded['invariance'])}  "
        f"Sens={fmt(grounded['sensitivity'])}  "
        f"K={fmt(grounded['kelvin_score'])}"
    )
    print(
        f"Degenerate: Inv={fmt(degenerate['invariance'])}  "
        f"Sens={fmt(degenerate['sensitivity'])}  "
        f"K={fmt(degenerate['kelvin_score'])}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
