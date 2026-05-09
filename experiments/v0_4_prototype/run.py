#!/usr/bin/env python3
"""
v0.4 prototype — auto-unitize + perturb-all-units against the live Envelop pipeline.

Throwaway test of the v0.4 thesis: given unlabeled venture descriptions
(no `## Heading` markup, no governing_types declared), can Kelvin auto-
unitize, perturb every unit, and recover what we learned from this morning's
labeled run?

Decision field: stage_assessment (same as morning).
Pipeline: Envelop harness_pass1_prose via /Users/sb/MyDev/envelopstudio/harness/kelvin_runner.mjs
Unitizers: paragraph-split AND sentence-split.
Primary perturbation: deletion (remove unit, re-render).
Secondary: numeric_magnitude, comparator_flip, polarity_flip (where they fire).
Presentation invariance: whitespace_jitter, punctuation_normalize.
Noise floor: 5 baseline replays per case; per-unit sensitivity is calibrated
as max(0, (raw - eta) / (1 - eta)).

Usage:
  python3 experiments/v0_4_prototype/run.py             # full run (10 cases × 2 unitizers)
  python3 experiments/v0_4_prototype/run.py --smoke     # 1 case for verification
  python3 experiments/v0_4_prototype/run.py --cases envelop,rhodium
  python3 experiments/v0_4_prototype/run.py --skip-pipeline  # generate artifacts from existing CSV
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── Config ────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent
KELVIN_ROOT = ROOT.parent.parent
CASES_DIR = KELVIN_ROOT / "cases"
HARNESS = "/Users/sb/MyDev/envelopstudio/harness/kelvin_runner.mjs"
DECISION_FIELD = "stage_assessment"
N_REPLAYS = 5
SEED = 0
WORKERS = 3
TIMEOUT_S = 180

# Morning's labeled-run sensitivity values (the comparison baseline).
# Source: this morning's live Envelop run, kelvin/<case>/report.json scores.
# Three cases (himom, narma, stagehand) had no gate_rule sections so produced
# no morning sensitivity — they are not in the comparison.
MORNING_SENSITIVITY: dict[str, float] = {
    "artisanflow": 1.0,
    "envelop": 1.0,
    "freakinggenius": 1.0,
    "meridian": 1.0,
    "northpass": 0.0,
    "readyrounds": 0.0,
    "rhodium": 0.0,
}
MORNING_BASELINE: dict[str, str] = {
    "artisanflow": "seed",
    "envelop": "seed",
    "freakinggenius": "pre-seed",
    "meridian": "pre-seed",
    "northpass": "idea",
    "readyrounds": "idea",
    "rhodium": "growth",
    "himom": "idea",
    "narma": "idea",
    "stagehand": "idea",
}

# ── Header stripping ───────────────────────────────────────────────────────

_HEADER_RE = re.compile(r"^##[ \t]+.+?[ \t]*$", re.MULTILINE)
_BLANK_RE = re.compile(r"\n{3,}")


def strip_headers(text: str) -> str:
    """Remove `## Heading` lines, keep content. Collapse blank-line runs."""
    text = _HEADER_RE.sub("", text)
    text = _BLANK_RE.sub("\n\n", text)
    return text.strip()


# ── Unitizers ──────────────────────────────────────────────────────────────


def unitize_paragraphs(text: str) -> list[tuple[str, str]]:
    """Split on `\n\n+`. Returns [(unit_id, content), ...]."""
    paras = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
    return [(f"p{i + 1:02d}", p) for i, p in enumerate(paras)]


def unitize_sentences(text: str) -> list[tuple[str, str]]:
    """Naive sentence split. Collapses whitespace first."""
    flat = re.sub(r"\s+", " ", text).strip()
    sents = re.split(r"(?<=[.!?])\s+(?=[A-Z])", flat)
    return [(f"s{i + 1:02d}", s.strip()) for i, s in enumerate(sents) if s.strip()]


UNITIZERS: dict[str, Any] = {
    "paragraph": unitize_paragraphs,
    "sentence": unitize_sentences,
}


# ── Perturbations ──────────────────────────────────────────────────────────

NUMERIC_MULT = 10
COMPARATOR_PAIRS = [
    (">=", "<="), ("<=", ">="), (">", "<"), ("<", ">"),
    ("≥", "≤"), ("≤", "≥"),
    ("exceeds", "falls below"), ("above", "below"),
    ("more than", "less than"), ("at least", "at most"),
    ("greater than", "less than"),
]
POLARITY_PAIRS = [
    ("must not", "must"), ("must", "must not"),
    ("should not", "should"), ("should", "should not"),
    ("all conditions are met", "no conditions are met"),
    ("none of these conditions are currently met", "all of these conditions are currently met"),
    ("none of these conditions are met", "all of these conditions are met"),
]


def perturb_delete(units: list[tuple[str, str]], i: int) -> list[tuple[str, str]] | None:
    if len(units) < 2:
        return None
    return [u for j, u in enumerate(units) if j != i]


def _apply_to_unit(units, i, transform_fn):
    new_content = transform_fn(units[i][1])
    if new_content is None or new_content == units[i][1]:
        return None
    return [(units[j][0], new_content if j == i else units[j][1]) for j in range(len(units))]


def _multiply_numeric_in(content: str) -> str | None:
    def _repl(m):
        s = m.group()
        s_clean = s.replace(",", "")
        try:
            v = float(s_clean) * NUMERIC_MULT
            if "." in s_clean:
                return f"{v:g}"
            return str(int(v))
        except ValueError:
            return s
    new = re.sub(r"\b\d+(?:[.,]\d+)?\b", _repl, content)
    return new if new != content else None


def perturb_numeric_magnitude(units, i):
    return _apply_to_unit(units, i, _multiply_numeric_in)


def _flip_first_match(content: str, pairs: list[tuple[str, str]]) -> str | None:
    """Replace the first regex-matched occurrence of any pair-source with its target."""
    best: tuple[int, str, str] | None = None  # (start, src, dst)
    for src, dst in pairs:
        # Word-bounded for word patterns; literal for symbols
        if any(c.isalpha() for c in src):
            pat = r"\b" + re.escape(src) + r"\b"
        else:
            pat = re.escape(src)
        m = re.search(pat, content, flags=re.IGNORECASE)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), m.group(), dst)
    if best is None:
        return None
    start, matched, dst = best
    return content[:start] + dst + content[start + len(matched):]


def perturb_comparator_flip(units, i):
    return _apply_to_unit(units, i, lambda c: _flip_first_match(c, COMPARATOR_PAIRS))


def perturb_polarity_flip(units, i):
    return _apply_to_unit(units, i, lambda c: _flip_first_match(c, POLARITY_PAIRS))


def perturb_whitespace_jitter(units, i):
    rng = random.Random(SEED + i + 1)
    content = units[i][1]
    words = content.split(" ")
    if len(words) < 4:
        return None
    pos = rng.randint(1, len(words) - 1)
    new_content = " ".join(words[:pos] + [words[pos] + " "] + words[pos + 1:])
    return [(units[j][0], new_content if j == i else units[j][1]) for j in range(len(units))]


def perturb_punctuation_normalize(units, i):
    content = units[i][1]
    # Try to replace straight punctuation with smart equivalents
    replacements = [
        ('"', '\u201c'),  # straight to left smart
        ("'", "\u2019"),
        (" - ", " \u2014 "),  # hyphen to em-dash
    ]
    new_content = content
    for src, dst in replacements:
        new_content = new_content.replace(src, dst, 1)
    if new_content == content:
        return None
    return [(units[j][0], new_content if j == i else units[j][1]) for j in range(len(units))]


PERTURBATIONS = [
    ("delete", perturb_delete),
    ("numeric_magnitude", perturb_numeric_magnitude),
    ("comparator_flip", perturb_comparator_flip),
    ("polarity_flip", perturb_polarity_flip),
    ("whitespace_jitter", perturb_whitespace_jitter),
    ("punctuation_normalize", perturb_punctuation_normalize),
]

# ── Pipeline call ──────────────────────────────────────────────────────────


def render(units: list[tuple[str, str]]) -> str:
    """Re-render units back to plain text with paragraph breaks."""
    return "\n\n".join(u[1] for u in units)


def invoke_pipeline(text: str, work_dir: Path, label: str) -> str | None:
    """Write text to input.md, call harness, parse decision_value. None on failure."""
    work_dir.mkdir(parents=True, exist_ok=True)
    input_path = work_dir / "input.md"
    output_path = work_dir / "output.json"
    input_path.write_text(text, encoding="utf-8")
    try:
        result = subprocess.run(
            ["node", HARNESS, "--input", str(input_path), "--output", str(output_path),
             "--variant", label],
            capture_output=True, timeout=TIMEOUT_S, check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    if result.returncode != 0:
        return None
    try:
        data = json.loads(output_path.read_text(encoding="utf-8"))
        return data.get(DECISION_FIELD)
    except Exception:
        return None


# ── Distance + sensitivity ─────────────────────────────────────────────────


def categorical_distance(a, b) -> float | None:
    if a is None or b is None:
        return None
    return 0.0 if a == b else 1.0


def calibrated(raw: float | None, eta: float | None) -> float | None:
    """Pillar-1 calibration: max(0, (raw - eta) / (1 - eta)). None if eta >= 1-raw."""
    if raw is None or eta is None:
        return raw
    if eta <= 0:
        return raw
    if eta >= 1.0 - raw:
        return None
    return max(0.0, (raw - eta) / (1.0 - eta))


# ── Main ───────────────────────────────────────────────────────────────────


@dataclass
class CaseRun:
    name: str
    stripped_text: str
    replays: list[str | None] = field(default_factory=list)
    sigma_c: float | None = None
    canonical_baseline: str | None = None


@dataclass
class PerturbationRow:
    case: str
    unitizer: str
    unit_id: str
    kind: str
    variant_id: str
    baseline: str | None
    decision: str | None
    distance: float | None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="run on 1 case (envelop) only")
    parser.add_argument("--cases", default=None, help="comma-separated case names")
    parser.add_argument("--skip-pipeline", action="store_true", help="skip live calls; use existing CSV")
    parser.add_argument("--unitizers", default="paragraph,sentence")
    parser.add_argument("--workers", type=int, default=WORKERS)
    args = parser.parse_args()

    # 1. Load + strip cases
    stripped_dir = ROOT / "stripped_cases"
    stripped_dir.mkdir(parents=True, exist_ok=True)

    case_names = [p.stem for p in sorted(CASES_DIR.glob("*.md"))]
    if args.smoke:
        case_names = ["envelop"]
    elif args.cases:
        case_names = [c.strip() for c in args.cases.split(",")]

    runs: dict[str, CaseRun] = {}
    for name in case_names:
        md = CASES_DIR / f"{name}.md"
        text = md.read_text(encoding="utf-8")
        stripped = strip_headers(text)
        (stripped_dir / f"{name}.txt").write_text(stripped + "\n", encoding="utf-8")
        runs[name] = CaseRun(name=name, stripped_text=stripped)

    unitizers_to_run = [u.strip() for u in args.unitizers.split(",")]

    # Pre-compute unit counts and budget
    print("=" * 70)
    print(f"Cases: {len(runs)}  Unitizers: {unitizers_to_run}  Replays: {N_REPLAYS}")
    total_perts = 0
    for unitizer_name in unitizers_to_run:
        for run in runs.values():
            units = UNITIZERS[unitizer_name](run.stripped_text)
            for i in range(len(units)):
                for kind, fn in PERTURBATIONS:
                    if fn(units, i) is not None:
                        total_perts += 1
    n_calls = len(runs) * N_REPLAYS + total_perts
    print(f"Estimated calls: {n_calls} ({len(runs) * N_REPLAYS} baselines + {total_perts} perturbations)")
    print(f"Budget @ ~30s/call sequential: ~{n_calls * 30 / 60:.0f} min; with {args.workers} workers: ~{n_calls * 30 / 60 / args.workers:.0f} min")
    print("=" * 70)

    csv_results = ROOT / "perturbation_manifest.csv"
    csv_baselines = ROOT / "baseline_replays.csv"

    if not args.skip_pipeline:
        # 2. Phase 1 — baselines + replays. Parallel within case.
        print(f"\n=== Phase 1: baselines + {N_REPLAYS} replays per case ===")
        t0 = time.monotonic()
        with open(csv_baselines, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["case", "replay_index", "decision"])
            for name, run in runs.items():
                # Parallel replays
                with ThreadPoolExecutor(max_workers=args.workers) as ex:
                    futs = {
                        ex.submit(
                            invoke_pipeline,
                            run.stripped_text,
                            ROOT / "runs" / name / "baseline" / f"r{r:02d}",
                            f"{name}-baseline-r{r}",
                        ): r
                        for r in range(N_REPLAYS)
                    }
                    by_idx: dict[int, str | None] = {}
                    for fut in as_completed(futs):
                        r = futs[fut]
                        by_idx[r] = fut.result()
                    run.replays = [by_idx[r] for r in range(N_REPLAYS)]
                for r, dec in enumerate(run.replays):
                    w.writerow([name, r, dec])
                f.flush()
                print(f"  {name}: {run.replays}")
        print(f"  Phase 1 elapsed: {(time.monotonic() - t0) / 60:.1f} min")

        # 3. Compute σ_c per case + canonical baseline
        for run in runs.values():
            valid = [r for r in run.replays if r is not None]
            run.canonical_baseline = valid[0] if valid else None
            if len(valid) < 2:
                run.sigma_c = None
                continue
            pairs = []
            for i in range(len(valid)):
                for j in range(i + 1, len(valid)):
                    pairs.append(categorical_distance(valid[i], valid[j]))
            run.sigma_c = sum(pairs) / len(pairs)
        print("\n  σ_c per case:")
        for n, r in runs.items():
            print(f"    {n:18s}  σ_c={r.sigma_c}  baseline={r.canonical_baseline}")

        # 4. Phase 2 — perturbations
        print(f"\n=== Phase 2: perturbations ({total_perts} variants) ===")
        with open(csv_results, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["case", "unitizer", "unit_id", "kind", "variant_id",
                        "baseline", "decision", "distance"])
            t0 = time.monotonic()
            done = 0

            # Build work list across all (case × unitizer × unit × kind) cells
            work: list[tuple[str, str, str, str, str, str]] = []  # case, unitizer, uid, kind, variant_id, rendered
            for unitizer_name in unitizers_to_run:
                fn = UNITIZERS[unitizer_name]
                for name, run in runs.items():
                    if run.canonical_baseline is None:
                        continue
                    units = fn(run.stripped_text)
                    for i, (uid, _) in enumerate(units):
                        for kind, pfn in PERTURBATIONS:
                            new_units = pfn(units, i)
                            if new_units is None:
                                continue
                            variant_id = f"{unitizer_name}-{uid}-{kind}"
                            work.append((name, unitizer_name, uid, kind, variant_id, render(new_units)))

            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                futs = {}
                for name, uniti, uid, kind, vid, rendered in work:
                    wd = ROOT / "runs" / name / "perturbations" / vid
                    futs[ex.submit(invoke_pipeline, rendered, wd, f"{name}-{vid}")] = (
                        name, uniti, uid, kind, vid
                    )
                for fut in as_completed(futs):
                    name, uniti, uid, kind, vid = futs[fut]
                    decision = fut.result()
                    base = runs[name].canonical_baseline
                    d = categorical_distance(base, decision)
                    w.writerow([name, uniti, uid, kind, vid, base, decision, d])
                    f.flush()
                    done += 1
                    if done % 25 == 0:
                        elapsed = (time.monotonic() - t0) / 60
                        print(f"    [{done}/{len(work)}] {elapsed:.1f} min elapsed")

            print(f"  Phase 2 elapsed: {(time.monotonic() - t0) / 60:.1f} min")

    else:
        # Reload from CSV
        if csv_baselines.exists():
            with open(csv_baselines) as f:
                for row in csv.DictReader(f):
                    runs[row["case"]].replays.append(row["decision"] if row["decision"] else None)
            for run in runs.values():
                valid = [r for r in run.replays if r]
                run.canonical_baseline = valid[0] if valid else None
                if len(valid) >= 2:
                    pairs = [categorical_distance(valid[i], valid[j])
                             for i in range(len(valid)) for j in range(i + 1, len(valid))]
                    run.sigma_c = sum(pairs) / len(pairs)

    # 5. Aggregate per-unit sensitivity
    print("\n=== Aggregating per-unit sensitivity ===")
    # Read manifest, compute per-unit raw + calibrated
    perturbation_rows: list[PerturbationRow] = []
    if csv_results.exists():
        with open(csv_results) as f:
            for r in csv.DictReader(f):
                d = r["distance"]
                perturbation_rows.append(PerturbationRow(
                    case=r["case"], unitizer=r["unitizer"], unit_id=r["unit_id"],
                    kind=r["kind"], variant_id=r["variant_id"],
                    baseline=r["baseline"] or None, decision=r["decision"] or None,
                    distance=float(d) if d not in ("", "None") else None,
                ))

    per_unit: dict[tuple[str, str, str], list[float]] = {}
    for row in perturbation_rows:
        if row.distance is None:
            continue
        per_unit.setdefault((row.case, row.unitizer, row.unit_id), []).append(row.distance)

    # Write per_unit_sensitivity.csv
    csv_unit = ROOT / "per_unit_sensitivity.csv"
    with open(csv_unit, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case", "unitizer", "unit_id", "n_perturbations", "raw_sensitivity",
                    "sigma_c", "calibrated_sensitivity"])
        for (case, uniti, uid), dists in sorted(per_unit.items()):
            raw = sum(dists) / len(dists)
            sc = runs[case].sigma_c if case in runs else None
            cal = calibrated(raw, sc)
            w.writerow([case, uniti, uid, len(dists), f"{raw:.4f}",
                        sc, "" if cal is None else f"{cal:.4f}"])

    # 6. Per-case aggregate sensitivity (mean over all units, mean over deletion-only)
    per_case_sens: dict[tuple[str, str], dict[str, float | None]] = {}
    for unitizer_name in unitizers_to_run:
        for case in runs:
            unit_keys = [k for k in per_unit if k[0] == case and k[1] == unitizer_name]
            if not unit_keys:
                continue
            all_dists = [d for k in unit_keys for d in per_unit[k]]
            del_dists = [r.distance for r in perturbation_rows
                         if r.case == case and r.unitizer == unitizer_name
                         and r.kind == "delete" and r.distance is not None]
            raw_all = sum(all_dists) / len(all_dists) if all_dists else None
            raw_del = sum(del_dists) / len(del_dists) if del_dists else None
            sc = runs[case].sigma_c
            per_case_sens[(case, unitizer_name)] = {
                "raw_all": raw_all,
                "raw_delete_only": raw_del,
                "calibrated_all": calibrated(raw_all, sc) if raw_all is not None else None,
                "calibrated_delete": calibrated(raw_del, sc) if raw_del is not None else None,
                "sigma_c": sc,
            }

    # 7. Per-case diagnosis markdown
    diag_dir = ROOT / "diagnoses"
    diag_dir.mkdir(parents=True, exist_ok=True)
    for case in runs:
        write_case_diagnosis(case, runs[case], per_unit, per_case_sens, perturbation_rows, diag_dir)

    # 8. Summary with Spearman + Mann-Whitney
    write_summary(runs, perturbation_rows, per_case_sens, unitizers_to_run)

    print(f"\n✓ Artifacts in {ROOT}/")


def write_case_diagnosis(case, run, per_unit, per_case_sens, perturbation_rows, out_dir):
    lines = [f"# {case} — v0.4 prototype diagnosis", ""]
    lines.append(f"**Morning baseline:** {MORNING_BASELINE.get(case, '?')}")
    lines.append(f"**Prototype canonical baseline:** {run.canonical_baseline}")
    lines.append(f"**Replays:** {run.replays}")
    lines.append(f"**σ_c (noise floor):** {run.sigma_c}")
    morning_sens = MORNING_SENSITIVITY.get(case)
    if morning_sens is not None:
        lines.append(f"**Morning labeled-run sensitivity (gate_rule swap):** {morning_sens:.3f}")
    else:
        lines.append("**Morning labeled-run sensitivity:** n/a (no gate_rule section)")
    lines.append("")
    for unitizer in ("paragraph", "sentence"):
        agg = per_case_sens.get((case, unitizer))
        if agg is None:
            continue
        lines.append(f"## {unitizer}-level")
        lines.append(f"- raw sensitivity (all perts):   {agg['raw_all']}")
        lines.append(f"- raw sensitivity (delete only): {agg['raw_delete_only']}")
        lines.append(f"- calibrated (all):              {agg['calibrated_all']}")
        lines.append(f"- calibrated (delete only):      {agg['calibrated_delete']}")
        lines.append("")
        lines.append("### Per-unit profile (delete-only above-noise)")
        unit_keys = [k for k in per_unit if k[0] == case and k[1] == unitizer]
        rows_for_unit = []
        for (_, _, uid) in sorted(unit_keys):
            del_dists = [r.distance for r in perturbation_rows
                         if r.case == case and r.unitizer == unitizer
                         and r.unit_id == uid and r.kind == "delete" and r.distance is not None]
            raw_del = sum(del_dists) / len(del_dists) if del_dists else None
            cal = calibrated(raw_del, run.sigma_c) if raw_del is not None else None
            rows_for_unit.append((uid, raw_del, cal))
        rows_for_unit.sort(key=lambda x: -(x[2] or 0))
        for uid, raw, cal in rows_for_unit:
            cal_s = f"{cal:.3f}" if cal is not None else "—"
            lines.append(f"- `{uid}`  raw={raw}  cal={cal_s}")
        lines.append("")
        # Plain-language one-liner
        if agg["calibrated_delete"] is not None and agg["calibrated_delete"] >= 0.5:
            verdict = "Multiple unit deletions move the decision above the noise floor — Envelop is responsive to the corpus content."
        elif agg["calibrated_delete"] is not None and agg["calibrated_delete"] >= 0.2:
            verdict = "Some unit deletions move the decision above noise; others do not — pipeline reads parts of the corpus selectively."
        else:
            verdict = "Few or no unit deletions move the decision above noise — pipeline holds its decision regardless of which unit is removed."
        lines.append(f"**{unitizer} diagnosis:** {verdict}")
        if rows_for_unit:
            top = [r for r in rows_for_unit if r[2] is not None and r[2] > 0]
            if top:
                ids = ", ".join(f"`{u}`" for u, _, _ in top[:3])
                lines.append(f"**Highest above-noise causal effect on stage_assessment:** {ids}")
        lines.append("")
    (out_dir / f"{case}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary(runs, perturbation_rows, per_case_sens, unitizers):
    lines = ["# v0.4 prototype — summary", "",
             f"_Generated {time.strftime('%Y-%m-%d %H:%M:%S')}_", ""]

    # Per-case sensitivity table
    lines.append("## Per-case sensitivity (calibrated, delete-only)")
    lines.append("")
    lines.append("| Case | Morning Sens | σ_c | Para-cal-del | Sent-cal-del |")
    lines.append("|---|---:|---:|---:|---:|")
    for case in sorted(runs):
        ms = MORNING_SENSITIVITY.get(case)
        ms_s = f"{ms:.3f}" if ms is not None else "—"
        sc = runs[case].sigma_c
        sc_s = f"{sc:.3f}" if sc is not None else "—"
        p = per_case_sens.get((case, "paragraph"), {}).get("calibrated_delete")
        s = per_case_sens.get((case, "sentence"), {}).get("calibrated_delete")
        p_s = f"{p:.3f}" if p is not None else "—"
        s_s = f"{s:.3f}" if s is not None else "—"
        lines.append(f"| {case} | {ms_s} | {sc_s} | {p_s} | {s_s} |")
    lines.append("")

    # Spearman + Mann-Whitney for each unitizer
    try:
        from scipy.stats import spearmanr, mannwhitneyu
        sciok = True
    except ImportError:
        sciok = False

    for unitizer in unitizers:
        lines.append(f"## Comparison vs morning's labeled run — {unitizer}-level")
        lines.append("")
        # Rank correlation: only on the 7 cases where morning has a value
        pairs_v = []
        pairs_m = []
        for case, ms in MORNING_SENSITIVITY.items():
            v = per_case_sens.get((case, unitizer), {}).get("calibrated_delete")
            if v is None:
                continue
            pairs_v.append(v)
            pairs_m.append(ms)
        lines.append(f"- N comparable cases: {len(pairs_v)}")
        if sciok and len(pairs_v) >= 3:
            rho, p = spearmanr(pairs_v, pairs_m)
            lines.append(f"- Spearman ρ: {rho:.3f}  (p={p:.3f})")
            # Mann-Whitney: split morning into "moved" (sens=1) vs "stuck" (sens=0)
            moved = [v for v, m in zip(pairs_v, pairs_m) if m == 1.0]
            stuck = [v for v, m in zip(pairs_v, pairs_m) if m == 0.0]
            if moved and stuck:
                u, p_mw = mannwhitneyu(moved, stuck, alternative="greater")
                lines.append(f"- Mann-Whitney U (moved > stuck, one-sided): U={u:.1f}, p={p_mw:.3f}")
                lines.append(f"- Median(moved) = {statistics.median(moved):.3f}; "
                             f"median(stuck) = {statistics.median(stuck):.3f}")
                lines.append(f"- Moved cases: {moved}")
                lines.append(f"- Stuck cases: {stuck}")
        lines.append("")

    # Cross-unitizer correlation
    if sciok and "paragraph" in unitizers and "sentence" in unitizers:
        lines.append("## Cross-unitizer agreement")
        lines.append("")
        from scipy.stats import spearmanr
        cross_p, cross_s = [], []
        for case in runs:
            p = per_case_sens.get((case, "paragraph"), {}).get("calibrated_delete")
            s = per_case_sens.get((case, "sentence"), {}).get("calibrated_delete")
            if p is not None and s is not None:
                cross_p.append(p)
                cross_s.append(s)
        if len(cross_p) >= 3:
            rho, pval = spearmanr(cross_p, cross_s)
            lines.append(f"Per-case calibrated-delete sensitivity, paragraph vs sentence:")
            lines.append(f"- Spearman ρ: {rho:.3f}  (p={pval:.3f})  N={len(cross_p)}")
            lines.append("")

    # Honest read placeholder
    lines.append("## Honest read")
    lines.append("")
    lines.append("_To be written by hand after inspecting the per-case diagnoses._")

    (ROOT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
