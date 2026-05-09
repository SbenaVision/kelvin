#!/usr/bin/env python3
"""
Throwaway: run the v0.4 perturbation-response experiment on classifier-labeled
markdown for the 4 cases (himom, stagehand, readyrounds, narma).

Reads labeled_cases/{case}.md (output of classify.py — labeled markdown with
`## Type` headers), parses sections as units, sends labeled markdown to the
Envelop full-pipeline harness, deletes each section (header + body) and
re-runs to measure per-unit response.

Same protocol as run_opportunity.py:
  - 10 baseline replays per case
  - 5 deletion replays per unit
  - Per-unit metrics: deletion_mean, delta_vs_baseline, z, above-noise (|Δ| > 2σ_baseline)

Outputs:
  - opportunity_labeled_baseline_replays.csv
  - opportunity_labeled_perturbation_manifest.csv
  - opportunity_labeled_per_unit.csv
  - opportunity_labeled_summary.md
"""
from __future__ import annotations

import csv
import json
import re
import statistics
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LABELED_DIR = ROOT / "labeled_cases"
HARNESS = "/Users/sb/MyDev/envelopstudio/harness/kelvin_runner.mjs"
DECISION_FIELD = "opportunity_score"
WORKERS = 3
TIMEOUT_S = 300
N_BASELINE = 10
N_DELETION_REPLAYS = 5
TARGET_CASES = ["himom", "stagehand", "readyrounds", "narma"]
MAX_ATTEMPTS = 2
RETRY_DELAY_S = 5.0

_HEADER_RE = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)


def parse_labeled(text: str) -> list[tuple[str, str]]:
    """Returns [(unit_id, raw_section_text_with_header), ...]."""
    matches = list(_HEADER_RE.finditer(text))
    if not matches:
        return [("u01", text.strip())]
    units = []
    for i, m in enumerate(matches):
        body_start = m.start()  # include the header line
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section = text[body_start:body_end].rstrip()
        units.append((f"u{i + 1:02d}", section))
    return units


def render_units(units: list[tuple[str, str]]) -> str:
    return "\n\n".join(u[1] for u in units) + "\n"


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
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = _invoke_once(text, work_dir, label)
        if result is not None:
            return result
        if attempt < MAX_ATTEMPTS:
            time.sleep(RETRY_DELAY_S)
    return None


def stdev(xs):
    return statistics.stdev(xs) if len(xs) >= 2 else 0.0


def main():
    cases = {}
    units_by_case = {}
    for name in TARGET_CASES:
        path = LABELED_DIR / f"{name}.md"
        if not path.exists():
            print(f"  MISSING: {path}")
            continue
        text = path.read_text(encoding="utf-8")
        cases[name] = text
        units_by_case[name] = parse_labeled(text)

    print("=" * 70)
    print(f"Cases: {list(cases.keys())}")
    for n, units in units_by_case.items():
        print(f"  {n}: {len(units)} units")
        for uid, sec in units:
            head = sec.split("\n", 1)[0]
            print(f"    {uid}  {head}")
    total_calls = len(cases) * N_BASELINE + sum(len(u) for u in units_by_case.values()) * N_DELETION_REPLAYS
    print(f"Total calls: {total_calls}  est. ~{total_calls * 30 / 60 / WORKERS:.0f} min")
    print("=" * 70)

    # Phase 1 — baselines
    print("\n=== Phase 1: baselines ===")
    baseline_replays = {n: [] for n in cases}
    work_b = []
    for name in cases:
        for r in range(N_BASELINE):
            wd = ROOT / "runs_labeled" / name / "baseline" / f"r{r:02d}"
            work_b.append((name, r, wd))

    csv_baselines = ROOT / "opportunity_labeled_baseline_replays.csv"
    t0 = time.monotonic()
    with open(csv_baselines, "w", newline="") as f, ThreadPoolExecutor(max_workers=WORKERS) as ex:
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

    baseline_stats = {}
    for name in cases:
        valid = [v for v in baseline_replays[name] if v is not None]
        if valid:
            baseline_stats[name] = {"mean": statistics.mean(valid), "sigma": stdev(valid), "n": len(valid)}
        else:
            baseline_stats[name] = {"mean": float("nan"), "sigma": float("nan"), "n": 0}
        b = baseline_stats[name]
        print(f"  {name}: mean={b['mean']:.1f} σ={b['sigma']:.1f} N={b['n']}/{N_BASELINE}")

    # Phase 2 — deletions
    print("\n=== Phase 2: deletions ===")
    work_p = []
    for name in cases:
        units = units_by_case[name]
        if len(units) < 2:
            continue
        for i, (uid, _) in enumerate(units):
            new_units = [u for j, u in enumerate(units) if j != i]
            rendered = render_units(new_units)
            for r in range(N_DELETION_REPLAYS):
                wd = ROOT / "runs_labeled" / name / "perturbations" / f"delete-{uid}" / f"r{r:02d}"
                work_p.append((name, uid, r, wd, rendered))

    pert_replays = {}
    csv_perts = ROOT / "opportunity_labeled_perturbation_manifest.csv"
    t0 = time.monotonic()
    with open(csv_perts, "w", newline="") as f, ThreadPoolExecutor(max_workers=WORKERS) as ex:
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

    # Aggregate
    csv_unit = ROOT / "opportunity_labeled_per_unit.csv"
    rows_per_case = {n: [] for n in cases}
    with open(csv_unit, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case", "unit_id", "n_replays", "deletion_mean", "deletion_sigma",
                    "baseline_mean", "baseline_sigma", "delta", "z_score", "above_noise_2sigma"])
        for (case, uid), replays in sorted(pert_replays.items()):
            valid = [v for v in replays if v is not None]
            if not valid or case not in baseline_stats:
                continue
            del_mean = statistics.mean(valid)
            del_sigma = stdev(valid)
            base = baseline_stats[case]
            delta = del_mean - base["mean"]
            se = ((base["sigma"] ** 2 / max(base["n"], 1)) +
                  (del_sigma ** 2 / max(len(valid), 1))) ** 0.5
            z = delta / se if se > 0 else (float("inf") if abs(delta) > 0 else 0.0)
            above = abs(delta) > 2 * base["sigma"] if base["sigma"] > 0 else abs(delta) > 0
            row = {"case": case, "unit_id": uid, "delta": delta, "z": z, "above": above,
                   "del_mean": del_mean, "del_sigma": del_sigma, "n_replays": len(valid),
                   "base_mean": base["mean"], "base_sigma": base["sigma"]}
            rows_per_case[case].append(row)
            w.writerow([case, uid, len(valid), f"{del_mean:.1f}", f"{del_sigma:.1f}",
                        f"{base['mean']:.1f}", f"{base['sigma']:.1f}",
                        f"{delta:+.1f}", f"{z:.2f}",
                        "Y" if above else "n"])

    # Summary
    lines = ["# v0.4 throwaway — labeled-classifier perturbation-response", "",
             f"_Generated {time.strftime('%Y-%m-%d %H:%M:%S')}_", "",
             "## Per-case overview", "",
             "| Case | N units | Baseline mean | σ | 2σ threshold | N above-noise |",
             "|---|---:|---:|---:|---:|---:|"]
    for case in cases:
        b = baseline_stats[case]
        rows = rows_per_case[case]
        n_above = sum(1 for r in rows if r["above"])
        n_units = len(rows)
        lines.append(f"| {case} | {n_units} | {b['mean']:.1f} | {b['sigma']:.1f} | "
                     f"{2 * b['sigma']:.1f} | **{n_above}** |")
    lines.append("")

    n_cases_with_above = sum(1 for case in cases if any(r["above"] for r in rows_per_case[case]))
    lines.append("## Pass criterion")
    lines.append("")
    lines.append(f"Today's stripped-prose run: **0 of 4** cases with ≥ 1 above-noise unit.")
    lines.append(f"Throwaway pass criterion: **≥ 2 of 4** cases with ≥ 1 above-noise unit.")
    lines.append(f"Throwaway result: **{n_cases_with_above} of 4** cases with ≥ 1 above-noise unit.")
    if n_cases_with_above >= 2:
        lines.append("")
        lines.append("**PASS** — labeled inputs unblock per-unit signal that stripped prose did not.")
    elif n_cases_with_above == 1:
        lines.append("")
        lines.append("**AMBIGUOUS** — one case improved; SBA decision required.")
    else:
        lines.append("")
        lines.append("**FAIL** — labeled inputs do not unblock above-noise per-unit signal.")
    lines.append("")

    lines.append("## Per-unit details")
    lines.append("")
    for case in cases:
        rows = rows_per_case[case]
        if not rows:
            continue
        lines.append(f"### {case}  (σ_baseline = {baseline_stats[case]['sigma']:.1f}, "
                     f"baseline mean = {baseline_stats[case]['mean']:.1f})")
        lines.append("")
        lines.append("| Unit | Type | n | deletion_mean | Δ | z | above-noise? |")
        lines.append("|---|---|---:|---:|---:|---:|:-:|")
        for r in sorted(rows, key=lambda r: -abs(r["delta"])):
            uid = r["unit_id"]
            # Look up the type by parsing labeled markdown again for this unit
            unit_text = next((sec for u, sec in units_by_case[case] if u == uid), "")
            type_name = ""
            m = _HEADER_RE.search(unit_text)
            if m:
                type_name = m.group(1)
            ar = "**Y**" if r["above"] else "n"
            lines.append(f"| {uid} | {type_name} | {r['n_replays']} | {r['del_mean']:.1f} | "
                         f"{r['delta']:+.1f} | {r['z']:.2f} | {ar} |")
        lines.append("")

    out = ROOT / "opportunity_labeled_summary.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n✓ Summary at {out}")
    print(f"\nCases with ≥1 above-noise unit: {n_cases_with_above}/4 (pass=≥2)")


if __name__ == "__main__":
    main()
