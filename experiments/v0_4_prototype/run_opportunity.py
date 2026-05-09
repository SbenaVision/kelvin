#!/usr/bin/env python3
"""
v0.4 prototype on himom / stagehand / readyrounds / narma using the scalar
opportunity_score (200-800) from the full Envelop pipeline.

Pipeline: harness_full_pipeline_prose action (Pass 1 → Stage 2 → reasoning memo
→ Stage 3 → deriveOpportunityScore). Requires the edge function to be deployed
with the new action; harness/kelvin_runner.mjs is updated to extract it.

Per case:
- Strip ## headers; auto-unitize on paragraph boundaries.
- 10 baseline replays.
- 5 deletion replays per paragraph.
- Per-unit metrics: mean_score, delta_vs_baseline, above-noise indicator
  (|delta| > 2 * baseline_sigma_c).

Outputs:
- stripped_cases/{case}.txt
- opportunity_baseline_replays.csv
- opportunity_perturbation_manifest.csv
- opportunity_per_unit.csv
- diagnoses_opportunity/{case}.md
- opportunity_summary.md
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KELVIN_ROOT = ROOT.parent.parent
CASES_DIR = KELVIN_ROOT / "cases"
HARNESS = "/Users/sb/MyDev/envelopstudio/harness/kelvin_runner.mjs"
DECISION_FIELD = "opportunity_score"
WORKERS = 3
TIMEOUT_S = 300  # full pipeline takes longer
N_BASELINE = 10
N_DELETION_REPLAYS = 5
TARGET_CASES = ["himom", "stagehand", "readyrounds", "narma"]

_HEADER_RE = re.compile(r"^##[ \t]+.+?[ \t]*$", re.MULTILINE)
_BLANK_RE = re.compile(r"\n{3,}")


def strip_headers(text: str) -> str:
    text = _HEADER_RE.sub("", text)
    text = _BLANK_RE.sub("\n\n", text)
    return text.strip()


def unitize_paragraphs(text: str) -> list[tuple[str, str]]:
    paras = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
    return [(f"p{i + 1:02d}", p) for i, p in enumerate(paras)]


def render(units: list[tuple[str, str]]) -> str:
    return "\n\n".join(u[1] for u in units)


# Soft-retry on transient failure. The Envelop full-pipeline endpoint
# occasionally queues/rate-limits under parallel load. One re-attempt
# with a short delay clears most of these without doubling the budget
# on a truly broken endpoint.
MAX_ATTEMPTS = 2
RETRY_DELAY_S = 5.0


def _invoke_once(text: str, work_dir: Path, label: str) -> float | None:
    work_dir.mkdir(parents=True, exist_ok=True)
    input_path = work_dir / "input.md"
    output_path = work_dir / "output.json"
    input_path.write_text(text, encoding="utf-8")
    try:
        r = subprocess.run(
            ["node", HARNESS, "--full-pipeline",
             "--input", str(input_path), "--output", str(output_path),
             "--variant", label],
            capture_output=True, timeout=TIMEOUT_S, check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    if r.returncode != 0:
        return None
    try:
        data = json.loads(output_path.read_text(encoding="utf-8"))
        v = data.get(DECISION_FIELD)
        return float(v) if isinstance(v, (int, float)) else None
    except Exception:
        return None


def invoke(text: str, work_dir: Path, label: str) -> float | None:
    """Call the full-pipeline harness with one transient retry."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = _invoke_once(text, work_dir, label)
        if result is not None:
            return result
        if attempt < MAX_ATTEMPTS:
            time.sleep(RETRY_DELAY_S)
    return None


def stdev(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    return statistics.stdev(xs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=",".join(TARGET_CASES))
    parser.add_argument("--workers", type=int, default=WORKERS)
    parser.add_argument("--smoke", action="store_true",
                        help="exactly 1 baseline + 1 deletion-of-p01 per case "
                             "(8 total calls for 4 cases — verifies harness wiring only)")
    args = parser.parse_args()
    case_names = [c.strip() for c in args.cases.split(",")]

    n_baseline = 1 if args.smoke else N_BASELINE
    n_deletion = 1 if args.smoke else N_DELETION_REPLAYS
    smoke_only_first_unit = args.smoke

    # 1. Strip + unitize
    stripped_dir = ROOT / "stripped_cases"
    stripped_dir.mkdir(parents=True, exist_ok=True)
    cases: dict[str, str] = {}
    units_by_case: dict[str, list[tuple[str, str]]] = {}
    for name in case_names:
        md_path = CASES_DIR / f"{name}.md"
        text = md_path.read_text(encoding="utf-8")
        stripped = strip_headers(text)
        (stripped_dir / f"{name}.txt").write_text(stripped + "\n", encoding="utf-8")
        cases[name] = stripped
        units_by_case[name] = unitize_paragraphs(stripped)

    print("=" * 70)
    print(f"Cases: {case_names}")
    for n in case_names:
        print(f"  {n}: {len(units_by_case[n])} paragraphs")
    total_perts = sum(len(u) * n_deletion for u in units_by_case.values())
    total_baselines = len(case_names) * n_baseline
    n_calls = total_baselines + total_perts
    print(f"Estimated calls: {n_calls} ({total_baselines} baselines + {total_perts} deletions)")
    print(f"Budget @ ~90s/call sequential: ~{n_calls * 90 / 60:.0f} min;")
    print(f"  with {args.workers} workers: ~{n_calls * 90 / 60 / args.workers:.0f} min")
    print("=" * 70)

    # 2. Phase 1 — baselines
    print(f"\n=== Phase 1: {n_baseline} baselines per case ===")
    baseline_replays: dict[str, list[float | None]] = {n: [] for n in case_names}
    csv_baselines = ROOT / "opportunity_baseline_replays.csv"
    t0 = time.monotonic()
    work_b = []
    for name in case_names:
        for r in range(n_baseline):
            wd = ROOT / "runs_opportunity" / name / "baseline" / f"r{r:02d}"
            work_b.append((name, r, wd))

    with open(csv_baselines, "w", newline="") as f, \
         ThreadPoolExecutor(max_workers=args.workers) as ex:
        w = csv.writer(f)
        w.writerow(["case", "replay_index", "opportunity_score"])
        futs = {ex.submit(invoke, cases[name], wd, f"{name}-baseline-r{r}"): (name, r)
                for name, r, wd in work_b}
        completed = 0
        for fut in as_completed(futs):
            name, r = futs[fut]
            score = fut.result()
            baseline_replays[name].append(score)
            w.writerow([name, r, score if score is not None else ""])
            f.flush()
            completed += 1
            if completed % 5 == 0 or completed == len(work_b):
                print(f"  [{completed}/{len(work_b)}] {(time.monotonic() - t0) / 60:.1f} min")

    print("\n  Baseline replay summary:")
    baseline_stats: dict[str, dict[str, float]] = {}
    for name in case_names:
        valid = [v for v in baseline_replays[name] if v is not None]
        if valid:
            mean = statistics.mean(valid)
            sigma = stdev(valid)
            baseline_stats[name] = {"mean": mean, "sigma": sigma, "n": len(valid)}
            print(f"    {name:14s}  mean={mean:6.1f}  σ={sigma:5.1f}  N={len(valid)}/{n_baseline}")
        else:
            baseline_stats[name] = {"mean": float("nan"), "sigma": float("nan"), "n": 0}
            print(f"    {name:14s}  ALL FAILED")

    # 3. Phase 2 — deletion perturbations
    print(f"\n=== Phase 2: deletion perturbations ({n_deletion} replays per unit) ===")
    csv_perts = ROOT / "opportunity_perturbation_manifest.csv"
    work_p = []
    for name in case_names:
        units = units_by_case[name]
        if len(units) < 2:
            continue
        # Smoke mode: only test deletion of the first paragraph (p01) per case.
        # Full mode: test deletion of every paragraph.
        unit_indices = [0] if smoke_only_first_unit else range(len(units))
        for i in unit_indices:
            uid, _ = units[i]
            new_units = [u for j, u in enumerate(units) if j != i]
            rendered = render(new_units)
            for r in range(n_deletion):
                wd = ROOT / "runs_opportunity" / name / "perturbations" / f"delete-{uid}" / f"r{r:02d}"
                work_p.append((name, uid, r, wd, rendered))

    t0 = time.monotonic()
    pert_replays: dict[tuple[str, str], list[float | None]] = {}
    with open(csv_perts, "w", newline="") as f, \
         ThreadPoolExecutor(max_workers=args.workers) as ex:
        w = csv.writer(f)
        w.writerow(["case", "unit_id", "replay_index", "kind", "opportunity_score"])
        futs = {ex.submit(invoke, rendered, wd, f"{name}-del-{uid}-r{r}"):
                (name, uid, r) for name, uid, r, wd, rendered in work_p}
        completed = 0
        for fut in as_completed(futs):
            name, uid, r = futs[fut]
            score = fut.result()
            pert_replays.setdefault((name, uid), []).append(score)
            w.writerow([name, uid, r, "delete", score if score is not None else ""])
            f.flush()
            completed += 1
            if completed % 10 == 0 or completed == len(work_p):
                print(f"  [{completed}/{len(work_p)}] {(time.monotonic() - t0) / 60:.1f} min")

    # 4. Aggregate per-unit
    csv_unit = ROOT / "opportunity_per_unit.csv"
    per_unit_rows = []
    with open(csv_unit, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case", "unit_id", "n_replays", "deletion_mean", "deletion_sigma",
                    "baseline_mean", "baseline_sigma", "delta", "z_score",
                    "above_noise_2sigma"])
        for (case, uid), replays in sorted(pert_replays.items()):
            valid = [v for v in replays if v is not None]
            if not valid or case not in baseline_stats:
                continue
            del_mean = statistics.mean(valid)
            del_sigma = stdev(valid)
            base = baseline_stats[case]
            delta = del_mean - base["mean"]
            # Standard error of the difference of means (Welch-style)
            se = ((base["sigma"] ** 2 / max(base["n"], 1)) +
                  (del_sigma ** 2 / max(len(valid), 1))) ** 0.5
            z = delta / se if se > 0 else (float("inf") if abs(delta) > 0 else 0.0)
            above_noise = abs(delta) > 2 * base["sigma"] if base["sigma"] > 0 else abs(delta) > 0
            row = {
                "case": case, "unit_id": uid, "n_replays": len(valid),
                "deletion_mean": del_mean, "deletion_sigma": del_sigma,
                "baseline_mean": base["mean"], "baseline_sigma": base["sigma"],
                "delta": delta, "z_score": z, "above_noise_2sigma": above_noise,
            }
            per_unit_rows.append(row)
            w.writerow([case, uid, len(valid), f"{del_mean:.1f}", f"{del_sigma:.1f}",
                        f"{base['mean']:.1f}", f"{base['sigma']:.1f}",
                        f"{delta:+.1f}", f"{z:.2f}",
                        "Y" if above_noise else "n"])

    # 5. Per-case diagnosis markdown
    diag_dir = ROOT / "diagnoses_opportunity"
    diag_dir.mkdir(parents=True, exist_ok=True)
    for case in case_names:
        write_case_diagnosis(case, baseline_stats[case], baseline_replays[case],
                              units_by_case[case], per_unit_rows, diag_dir)

    # 6. Summary
    write_summary(case_names, baseline_stats, per_unit_rows)

    print(f"\n✓ Artifacts in {ROOT}/")


def write_case_diagnosis(case, base_stats, base_replays, units, per_unit_rows, out_dir):
    lines = [f"# {case} — v0.4 prototype diagnosis (opportunity_score)", ""]
    lines.append(f"**Field:** opportunity_score (200-800 scale, derived from VVS dimensions P, M, C)")
    lines.append("")
    lines.append("## Baseline")
    lines.append(f"- Replays (N={base_stats['n']}): {base_replays}")
    lines.append(f"- mean = {base_stats['mean']:.1f}")
    lines.append(f"- σ = {base_stats['sigma']:.1f}")
    lines.append("")
    lines.append("## Per-paragraph deletion impact")
    lines.append("")
    lines.append("| Unit | n | deletion_mean | delta vs baseline | z | above-noise (|Δ|>2σ)? |")
    lines.append("|---|---:|---:|---:|---:|:-:|")
    case_rows = sorted([r for r in per_unit_rows if r["case"] == case],
                       key=lambda r: -abs(r["delta"]))
    for r in case_rows:
        ar = "**Y**" if r["above_noise_2sigma"] else "n"
        lines.append(f"| `{r['unit_id']}` | {r['n_replays']} | {r['deletion_mean']:.1f} | "
                     f"{r['delta']:+.1f} | {r['z_score']:.2f} | {ar} |")
    lines.append("")

    above = [r for r in case_rows if r["above_noise_2sigma"]]
    if not above:
        verdict = (f"**Diagnosis:** No paragraph deletion moves opportunity_score by more than "
                   f"2σ ({base_stats['sigma']:.1f} × 2 = {2 * base_stats['sigma']:.1f}). "
                   f"The pipeline holds its score against unit removal at this sample size — "
                   f"either no single unit drives the score, or the noise floor exceeds any "
                   f"individual unit's contribution.")
    else:
        ids = ", ".join(f"`{r['unit_id']}` (Δ={r['delta']:+.1f})" for r in above[:3])
        verdict = (f"**Diagnosis:** {len(above)} of {len(case_rows)} paragraph deletions "
                   f"shift opportunity_score above the 2σ noise floor "
                   f"(σ_baseline = {base_stats['sigma']:.1f}). "
                   f"Strongest above-noise drivers: {ids}.")
    lines.append(verdict)
    lines.append("")

    # Show paragraph text for top-3 above-noise units
    if above:
        lines.append("### Driver paragraphs (top 3 by |delta|)")
        lines.append("")
        unit_text = {uid: txt for uid, txt in units}
        for r in above[:3]:
            uid = r["unit_id"]
            txt = unit_text.get(uid, "?")
            preview = txt if len(txt) <= 240 else txt[:240] + "..."
            lines.append(f"**`{uid}` (delta {r['delta']:+.1f}):**")
            lines.append(f"> {preview}")
            lines.append("")

    (out_dir / f"{case}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary(case_names, baseline_stats, per_unit_rows):
    lines = ["# v0.4 prototype on opportunity_score — summary", "",
             f"_Generated {time.strftime('%Y-%m-%d %H:%M:%S')}_", ""]

    lines.append("## Per-case overview")
    lines.append("")
    lines.append("| Case | Baseline mean | σ | N units | N above-noise |")
    lines.append("|---|---:|---:|---:|---:|")
    for case in case_names:
        b = baseline_stats[case]
        case_rows = [r for r in per_unit_rows if r["case"] == case]
        n_above = sum(1 for r in case_rows if r["above_noise_2sigma"])
        lines.append(f"| {case} | {b['mean']:.1f} | {b['sigma']:.1f} | "
                     f"{len(case_rows)} | {n_above} |")
    lines.append("")

    # Compare patterns across cases
    lines.append("## Cross-case comparison")
    lines.append("")
    lines.append("| Case | Strongest driver (unit_id, Δ) | 2nd (unit_id, Δ) |")
    lines.append("|---|---|---|")
    for case in case_names:
        case_rows = sorted([r for r in per_unit_rows if r["case"] == case],
                           key=lambda r: -abs(r["delta"]))
        first = f"`{case_rows[0]['unit_id']}` ({case_rows[0]['delta']:+.1f})" if case_rows else "—"
        second = f"`{case_rows[1]['unit_id']}` ({case_rows[1]['delta']:+.1f})" if len(case_rows) > 1 else "—"
        lines.append(f"| {case} | {first} | {second} |")
    lines.append("")

    # Honest read placeholder
    lines.append("## Honest read")
    lines.append("")
    lines.append("_To be written after inspection of per-case diagnoses._")

    (ROOT / "opportunity_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
