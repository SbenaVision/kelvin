"""EOS v2.2 certification orchestrator (post-seal, Commit C).

Pipeline:
  1. Verify SEAL.txt hash.
  2. Print theorem-required sample-size bounds.
  3. For each probe c: generate the per-probe corpus pool (n_eff = 600
     direct-sampled from D(·|A_c)).
  4. For each (pipeline j, probe c): run discover.evaluate_probe →
     ProbeEstimate(p_hat, CP_LCB, CP_UCB, n_eff, margin_supported).
  5. Apply success_criteria.check_t2_alignment, check_t3_alignment.
  6. Write CSVs (signatures, theorem_check) and results.md.

Single corpus draw per probe (the V5 theorem requires no resampling
for the certification claim itself; multi-draw stability is a v2.1
product property).

No noise-floor estimation, no replay loop — raw relations only.
"""
from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    ALPHA_PER_PAIR, DELTA, EPS, LAMBDA, M, N_EFF_MIN, THETA,
)
from corpus import generate_probe_pool
from discover import ProbeEstimate, evaluate_probe
from pipelines import PIPELINES
from seal_manifest import compute_seal
from success_criteria import check_t2_alignment, check_t3_alignment
from theorem_check import compute_bounds, format_report
from transformations import CATALOGUE


HERE = Path(__file__).parent
ADVERSARIES = ["f_ruleblind", "f_constant", "f_wrongstatic", "f_wrongstochastic"]


def _verify_seal() -> str:
    seal_path = HERE / "SEAL.txt"
    if not seal_path.exists():
        raise RuntimeError("SEAL.txt missing")
    sealed_lines = seal_path.read_text().splitlines()
    sealed_digest = next(
        (line.split(" = ", 1)[1] for line in sealed_lines if line.startswith("seal_sha256")),
        None,
    )
    current_digest, _ = compute_seal(HERE)
    if sealed_digest != current_digest:
        raise RuntimeError(
            f"SEAL VIOLATED: sealed={sealed_digest} current={current_digest}"
        )
    return current_digest


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    print("=" * 78)
    print("EOS v2.2 — Theorem-aligned certification run")
    print("=" * 78)
    seal_hash = _verify_seal()
    print(f"  SEAL ok. seal_sha256 = {seal_hash}")
    print()

    bounds = compute_bounds()
    print(format_report(bounds))

    print()
    estimates: list[ProbeEstimate] = []
    for probe in CATALOGUE:
        inputs = generate_probe_pool(probe.idx)
        print(f"  -- Probe #{probe.idx} {probe.name:32s} (n_eff = {len(inputs)}) --")
        for pname, f in PIPELINES.items():
            est = evaluate_probe(
                pname, f, probe, inputs,
                theta=THETA, lam=LAMBDA, alpha=ALPHA_PER_PAIR,
            )
            estimates.append(est)
            band = "INSIDE BAND" if not est.margin_condition_supported else "outside band"
            print(
                f"    {pname:18s}: p̂={est.p_hat:.4f} "
                f"CP=[{est.cp_lcb:.4f}, {est.cp_ucb:.4f}] "
                f"|p̂−θ|={est.margin_from_theta:.3f}  [{band}]"
            )
    print()

    # Theorem alignment checks
    t2_aligned, t2_violators = check_t2_alignment(estimates)
    t3_aligned, t3_sep_per_adv = check_t3_alignment(estimates, ADVERSARIES)

    print(f"-- Theorem-2 alignment: {'PASS' if t2_aligned else 'FAIL'} --")
    if t2_violators:
        print(f"   {len(t2_violators)} (pipeline, probe) pair(s) inside boundary band:")
        for v in t2_violators:
            print(f"     {v.pipeline}/{v.probe_name}  p̂={v.p_hat:.4f}  CP=[{v.cp_lcb:.4f},{v.cp_ucb:.4f}]")
    else:
        print("   All (pipeline, probe) CP intervals lie outside boundary band (θ-λ, θ+λ)")
    print()

    print(f"-- Theorem-3 alignment: {'PASS' if t3_aligned else 'FAIL'} --")
    print(f"   Separating probe per adversary:")
    for adv, probe_name in t3_sep_per_adv.items():
        marker = "✓" if probe_name else "✗"
        print(f"     {marker} {adv:18s} ↔ {probe_name or 'NO SEPARATING PROBE'}")
    print()

    overall = t2_aligned and t3_aligned
    print("OVERALL: " + ("THEOREM-ALIGNED" if overall else "NOT ALIGNED"))

    # ---- Write artifacts ----
    sig_rows: list[dict] = []
    for est in estimates:
        sig_rows.append({
            "seal_sha256": seal_hash,
            "probe_idx": est.probe_idx,
            "probe_name": est.probe_name,
            "relation": est.relation,
            "expected_direction": est.expected_direction,
            "pipeline": est.pipeline,
            "k": est.k,
            "n_eff": est.n_eff,
            "p_hat": round(est.p_hat, 6),
            "cp_lcb": round(est.cp_lcb, 6),
            "cp_ucb": round(est.cp_ucb, 6),
            "margin_from_theta": round(est.margin_from_theta, 6),
            "n_min_required": est.n_min_required,
            "margin_condition_supported": int(est.margin_condition_supported),
        })
    _write_csv(HERE / "signatures.csv", sig_rows)

    # theorem_check.json — sealed bounds + alignment results
    theorem_record = {
        "seal_sha256": seal_hash,
        "bounds": {
            "M": bounds.M,
            "A": bounds.A,
            "family_size": bounds.family_size,
            "epsilon": bounds.epsilon,
            "theta": bounds.theta,
            "lambda": bounds.lam,
            "delta": bounds.delta,
            "theorem2_n_min": bounds.theorem2_n_min,
            "theorem3_n_min": bounds.theorem3_n_min,
            "n_eff_min_committed": bounds.n_eff_min_committed,
            "alpha_per_pair": ALPHA_PER_PAIR,
        },
        "t2_aligned": t2_aligned,
        "t2_violators": [
            {"pipeline": v.pipeline, "probe": v.probe_name,
             "p_hat": v.p_hat, "cp_lcb": v.cp_lcb, "cp_ucb": v.cp_ucb}
            for v in t2_violators
        ],
        "t3_aligned": t3_aligned,
        "t3_separating_probe_per_adversary": t3_sep_per_adv,
    }
    (HERE / "theorem_check.json").write_text(json.dumps(theorem_record, indent=2))

    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
