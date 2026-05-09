#!/usr/bin/env python3
"""Replicate deletion perturbations on high-σ_c cases to test whether the
per-unit causal map survives noise when each perturbation is sampled multiple times.

Design:
- 4 cases morning labeled as moved: artisanflow, envelop, freakinggenius, meridian
- For each case: 5 additional baseline replays (→ N=10 total) → tighter σ_c
- For each (case, paragraph) deletion in the existing manifest: 4 additional
  replays (→ N=5 total per perturbation)
- Per-(case, paragraph): flip rate over 5 replays; one-sided binomial test
  against null hypothesis flip_rate == σ_c.
- Output: experiments/v0_4_prototype/multi_replay_summary.md
"""

from __future__ import annotations

import csv
import json
import statistics
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parent
HARNESS = "/Users/sb/MyDev/envelopstudio/harness/kelvin_runner.mjs"
DECISION_FIELD = "stage_assessment"
WORKERS = 3
TIMEOUT_S = 180

CASES_TO_REPLICATE = ["artisanflow", "envelop", "freakinggenius", "meridian"]
N_EXTRA_BASELINE = 5      # adds to existing 5 → N=10 total
N_EXTRA_PERTURBATION = 4  # adds to existing 1 → N=5 total

MORNING_BASELINE = {
    "artisanflow": "seed",
    "envelop": "seed",
    "freakinggenius": "pre-seed",
    "meridian": "pre-seed",
}


def invoke(input_path, output_path, label):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(
            ["node", HARNESS, "--input", str(input_path), "--output", str(output_path), "--variant", label],
            capture_output=True, timeout=TIMEOUT_S, check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    if r.returncode != 0:
        return None
    try:
        return json.loads(output_path.read_text(encoding="utf-8")).get(DECISION_FIELD)
    except Exception:
        return None


def main():
    # 1. Extra baseline replays
    print("=== Phase A: extra baseline replays ===")
    extra_baselines: dict[str, list[str | None]] = {}
    work_a = []
    for case in CASES_TO_REPLICATE:
        case_dir = ROOT / "runs" / case / "baseline"
        for r in range(N_EXTRA_BASELINE):
            extra_idx = 5 + r  # original used r00..r04
            wd = case_dir / f"r{extra_idx:02d}"
            wd.mkdir(parents=True, exist_ok=True)
            # Copy the existing input.md from r00 (deterministic input — same prose)
            src_input = case_dir / "r00" / "input.md"
            dst_input = wd / "input.md"
            dst_input.write_text(src_input.read_text(encoding="utf-8"), encoding="utf-8")
            work_a.append((case, extra_idx, dst_input, wd / "output.json"))

    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(invoke, ip, op, f"{c}-baseline-r{idx}"): (c, idx)
                for c, idx, ip, op in work_a}
        for fut in as_completed(futs):
            c, idx = futs[fut]
            extra_baselines.setdefault(c, []).append(fut.result())
    print(f"  Phase A: {time.monotonic() - t0:.0f}s")

    # 2. Extra deletion-perturbation replays — only for paragraph-level deletes
    rows = list(csv.DictReader(open(ROOT / "perturbation_manifest.csv")))
    delete_rows = [r for r in rows
                   if r["case"] in CASES_TO_REPLICATE
                   and r["unitizer"] == "paragraph"
                   and r["kind"] == "delete"]
    print(f"\n=== Phase B: extra deletion replays ({len(delete_rows)} variants × {N_EXTRA_PERTURBATION} replays) ===")

    work_b = []
    for r in delete_rows:
        case = r["case"]
        variant_id = r["variant_id"]
        var_dir = ROOT / "runs" / case / "perturbations" / variant_id
        src_input = var_dir / "input.md"
        if not src_input.exists():
            print(f"  WARN: no input.md for {case}/{variant_id}")
            continue
        for k in range(N_EXTRA_PERTURBATION):
            extra_idx = 1 + k  # original was implicit r0
            wd = var_dir / f"r{extra_idx:02d}"
            wd.mkdir(parents=True, exist_ok=True)
            dst_input = wd / "input.md"
            dst_input.write_text(src_input.read_text(encoding="utf-8"), encoding="utf-8")
            work_b.append((case, variant_id, r["unit_id"], extra_idx, dst_input, wd / "output.json"))

    extra_perts: dict[tuple[str, str], list[str | None]] = {}
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(invoke, ip, op, f"{c}-{vid}-r{idx}"): (c, vid)
                for c, vid, _, idx, ip, op in work_b}
        done = 0
        for fut in as_completed(futs):
            c, vid = futs[fut]
            extra_perts.setdefault((c, vid), []).append(fut.result())
            done += 1
            if done % 20 == 0:
                print(f"    [{done}/{len(work_b)}] {time.monotonic() - t0:.0f}s elapsed")
    print(f"  Phase B: {time.monotonic() - t0:.0f}s")

    # 3. Aggregate
    # Original baseline replays
    orig_baselines: dict[str, list[str | None]] = {}
    for r in csv.DictReader(open(ROOT / "baseline_replays.csv")):
        orig_baselines.setdefault(r["case"], []).append(r["decision"] or None)

    print("\n=== Aggregation ===")
    summary_lines = ["# Multi-replay test — does the per-unit causal map survive noise?", ""]
    summary_lines.append(f"_Generated {time.strftime('%Y-%m-%d %H:%M:%S')}_  ")
    summary_lines.append(f"4 cases × ~7 paragraphs × 5 replays each = {len(work_b)} extra perturbation calls")
    summary_lines.append(f"4 cases × 5 extra baseline replays = {len(work_a)} extra baseline calls")
    summary_lines.append("")
    summary_lines.append("## Per-case noise floor (N=10 replays)")
    summary_lines.append("")
    summary_lines.append("| Case | morning_baseline | replays (N=10) | σ_c (10 replays) | σ_c (orig 5 replays) |")
    summary_lines.append("|---|---|---|---:|---:|")

    sigmas_10 = {}
    for case in CASES_TO_REPLICATE:
        all_replays = (orig_baselines.get(case, []) or []) + (extra_baselines.get(case, []) or [])
        valid = [d for d in all_replays if d]
        # pairwise distance
        if len(valid) >= 2:
            pairs = sum(1 for i in range(len(valid)) for j in range(i+1,len(valid)) if valid[i] != valid[j])
            total = len(valid)*(len(valid)-1)//2
            sigma = pairs/total
        else:
            sigma = None
        sigmas_10[case] = sigma
        # original σ_c (5 replays)
        v5 = [d for d in (orig_baselines.get(case) or []) if d]
        if len(v5) >= 2:
            pairs5 = sum(1 for i in range(len(v5)) for j in range(i+1,len(v5)) if v5[i] != v5[j])
            sigma5 = pairs5 / (len(v5)*(len(v5)-1)//2)
        else:
            sigma5 = None
        replays_str = str(all_replays).replace("'", "")
        summary_lines.append(f"| {case} | {MORNING_BASELINE[case]} | `{replays_str[:80]}` | {sigma:.3f} | {sigma5:.3f} |")
    summary_lines.append("")

    # 4. Per-(case, paragraph) replicated flip rate vs σ_c
    summary_lines.append("## Per-paragraph flip rates (N=5 replays) vs σ_c")
    summary_lines.append("")
    summary_lines.append("Decision rule: paragraph deletion is **above-noise** if a one-sided binomial test ")
    summary_lines.append("(H₀: flip_rate ≤ σ_c) gives p < 0.05.")
    summary_lines.append("")

    morning_flag_count = 0
    surviving_count = 0
    new_count = 0
    by_case_above_noise = {}

    for case in CASES_TO_REPLICATE:
        sigma = sigmas_10[case] or 0.0
        baseline_canonical = MORNING_BASELINE[case]
        # Filter delete rows for this case
        case_dels = [r for r in delete_rows if r["case"] == case]
        case_dels.sort(key=lambda r: r["unit_id"])

        summary_lines.append(f"### {case}  (σ_c={sigma:.3f}, canonical baseline = {baseline_canonical})")
        summary_lines.append("")
        summary_lines.append("| Unit | Replay decisions (N=5) | flip_rate | binomial p (vs σ_c) | above-noise? | morning probe? |")
        summary_lines.append("|---|---|---:|---:|:-:|:-:|")

        case_above = []
        for r in case_dels:
            uid = r["unit_id"]
            vid = r["variant_id"]
            # Combine: original 1 + extras
            extras = extra_perts.get((case, vid), [])
            replays = [r["decision"] or None] + extras
            # Compare each replay to canonical baseline
            flips = sum(1 for d in replays if d is not None and d != baseline_canonical)
            n_valid = sum(1 for d in replays if d is not None)
            flip_rate = flips / n_valid if n_valid else None
            # Binomial test: is flips out of n_valid > σ_c?
            if n_valid >= 1 and sigma is not None and 0 < sigma < 1:
                test = binomtest(flips, n_valid, p=sigma, alternative="greater")
                p = test.pvalue
            elif sigma == 0 and flips > 0:
                # σ_c=0 so any flip is above noise
                p = 0.0
            else:
                p = None
            above = (p is not None and p < 0.05)
            morning_flag = (r["distance"] == "1.0")
            if morning_flag:
                morning_flag_count += 1
                if above:
                    surviving_count += 1
            else:
                if above:
                    new_count += 1
            case_above.append((uid, above))
            replays_str = str([r if r else "—" for r in replays]).replace("'", "")
            ar = "**Y**" if above else "n"
            mf = "Y" if morning_flag else "n"
            p_s = f"{p:.3f}" if p is not None else "—"
            summary_lines.append(f"| {uid} | `{replays_str[:60]}` | {flip_rate:.2f} | {p_s} | {ar} | {mf} |")
        summary_lines.append("")
        by_case_above_noise[case] = case_above

    summary_lines.append("## Summary counts")
    summary_lines.append("")
    summary_lines.append(f"- Morning's prototype (single-replay) flagged paragraphs: {morning_flag_count}")
    summary_lines.append(f"- Of those, surviving 5-replay binomial test (p<0.05 vs σ_c): **{surviving_count}**")
    summary_lines.append(f"- New paragraphs revealed as above-noise after replication: {new_count}")
    summary_lines.append("")

    # 5. Honest read placeholder
    summary_lines.append("## Honest read")
    summary_lines.append("")
    summary_lines.append("_Auto-generated; will be edited after inspection._")

    out = ROOT / "multi_replay_summary.md"
    out.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(f"\n✓ Written {out}")
    print(f"\nCounts: {morning_flag_count} morning-flagged, {surviving_count} surviving, {new_count} new above-noise")


if __name__ == "__main__":
    main()
