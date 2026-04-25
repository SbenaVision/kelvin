"""EOS v2.1 orchestrator (post-seal, Commit C).

Pipeline:
  1. Verify SEAL.txt hash matches sealed-catalogue files.
  2. Generate K_D independent corpus draws.
  3. Per pipeline: K=20 baseline replays per case → q_0.95 noise floor per case.
  4. Discover global invariance (R^Ω over full corpus, INVARIANCE Ts).
  5. Discover directional sensitivity rates (correct/wrong/no_effect)
     on pre-specified A_T (DIRECTIONAL Ts).
  6. Subsumption (no-op) on accepted invariance set.
  7. Stability: pairwise Jaccard + triple intersection of f_track signatures.
  8. Axis classification per pipeline per draw.
  9. Apply 8 §11 success criteria.
 10. Write CSVs + results.md (results.md by hand after run).

Reports the empirical q distribution per (pipeline, draw) so c7
rationale is grounded in actual measurements.
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from axis_classifier import AxisReport, classify_axes
from config import (
    DELTA, DELTA_NAIVE, DELTA_DIR, DELTA_EQ, EPS, K_D, K_REPLAYS,
    N_EFF_MIN_GLOBAL, N_EFF_MIN_ACTIVE, N_PER_DRAW, PIPELINE_IDS,
)
from corpus import generate_all_draws
from discover import (
    DirectionalRates, GlobalInvarianceCandidate,
    discover_directional_rates, discover_global_invariance,
)
from noise_floor import (
    baseline_replays, baseline_score_for_pair_eval, noise_quantile_per_case,
)
from pipelines import PIPELINES
from relations import NOISE_AWARE as R_OMEGA
from schema import Input
from seal_manifest import compute_seal
from subsumption import drop_subsumed
from success_criteria import evaluate as evaluate_criteria
from transformations import CATALOGUE as T_CATALOGUE


# Bonferroni m: counts only NON-DIAGNOSTIC hypotheses
# (R^Ω invariance + directional rate tests). Naive directional is
# diagnostic only, NOT part of m.
N_INVARIANCE_T = sum(1 for t in T_CATALOGUE if t.sensitivity_kind == "invariance")
N_DIRECTIONAL_T = sum(1 for t in T_CATALOGUE if t.sensitivity_kind == "directional")
M_GLOBAL = N_INVARIANCE_T * len(R_OMEGA)
M_DIRECTIONAL = N_DIRECTIONAL_T * 3
M_TOTAL = M_GLOBAL + M_DIRECTIONAL
ALPHA_OMEGA = DELTA / M_TOTAL
ALPHA_NAIVE = DELTA  # diagnostic only — no Bonferroni

TRANSFORM_REPLAY_IDX = K_REPLAYS  # use a fresh replay index for f(Tx)
HERE = Path(__file__).parent


# =====================================================================
# Seal verification
# =====================================================================

def _verify_seal() -> str:
    seal_path = HERE / "SEAL.txt"
    if not seal_path.exists():
        raise RuntimeError("SEAL.txt missing — run seal_manifest.py first")
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


# =====================================================================
# Empirical q distribution
# =====================================================================

def _q_bucket(q: float) -> int:
    if q < 0.5: return 0
    if q < 1.5: return 1
    if q < 2.5: return 2
    if q < 3.5: return 3
    if q < 4.5: return 4
    if q < 5.5: return 5
    return 6


def _q_histogram(q_per_case: dict[int, float]) -> dict[int, int]:
    h: Counter = Counter()
    for q in q_per_case.values():
        h[_q_bucket(q)] += 1
    return dict(h)


# =====================================================================
# Per-draw run
# =====================================================================

def _run_one_draw(
    draw_idx: int, draw: list[Input],
) -> dict:
    print(f"  -- Draw {draw_idx}  (N = {len(draw)}) --")
    inv_all: list[GlobalInvarianceCandidate] = []
    rates_all: list[DirectionalRates] = []
    q_hists: dict[str, dict[int, int]] = {}
    q_per_pipeline: dict[str, dict[int, float]] = {}

    for pname, f in PIPELINES.items():
        replays = baseline_replays(f, draw, PIPELINE_IDS[pname])
        q_per_case = noise_quantile_per_case(replays)
        q_per_pipeline[pname] = q_per_case
        q_hists[pname] = _q_histogram(q_per_case)
        baseline_first = {cid: ys[0] for cid, ys in replays.items()}

        n_active_share = q_hists[pname]
        median_q = sorted(q_per_case.values())[len(q_per_case) // 2]
        print(
            f"    {pname:18s}  median q_0.95 = {median_q:.2f}   "
            f"hist = {sorted(n_active_share.items())}"
        )

        # (A) Global invariance
        inv = discover_global_invariance(
            pname, f, T_CATALOGUE, R_OMEGA, draw,
            baseline_first, q_per_case,
            eps=EPS, alpha=ALPHA_OMEGA, n_eff_min=N_EFF_MIN_GLOBAL,
            transform_replay_idx=TRANSFORM_REPLAY_IDX,
        )
        inv_all.extend(inv)

        # (B) Directional rates on A_T
        rates = discover_directional_rates(
            pname, f, T_CATALOGUE, draw,
            baseline_first, q_per_case,
            eps=EPS,
            alpha_omega=ALPHA_OMEGA,
            alpha_naive=ALPHA_NAIVE,
            delta_dir=DELTA_DIR,
            delta_naive=DELTA_NAIVE,
            n_eff_active_min=N_EFF_MIN_ACTIVE,
            transform_replay_idx=TRANSFORM_REPLAY_IDX,
        )
        rates_all.extend(rates)

    return {
        "invariance": inv_all,
        "rates": rates_all,
        "q_histograms": q_hists,
    }


# =====================================================================
# CSV writers
# =====================================================================

def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


# =====================================================================
# Main
# =====================================================================

def main() -> int:
    print("=" * 78)
    print("EOS v2.1 — Empirical Oracle Signature, sealed-catalogue run")
    print("=" * 78)
    seal_hash = _verify_seal()
    print(f"  SEAL ok. seal_sha256 = {seal_hash}")
    print(f"  K_D={K_D}  N_per_draw={N_PER_DRAW}  K_replays={K_REPLAYS}")
    print(f"  |T_inv|={N_INVARIANCE_T}  |T_dir|={N_DIRECTIONAL_T}  |R^Ω|={len(R_OMEGA)}")
    print(f"  m_total = {M_TOTAL}  (m_global={M_GLOBAL} + m_directional={M_DIRECTIONAL})")
    print(f"  α_omega = δ/m = {ALPHA_OMEGA:.3e}   α_naive (diagnostic) = {ALPHA_NAIVE}")
    print(f"  ε={EPS}  Δ_eq={DELTA_EQ}  Δ_dir={DELTA_DIR}  Δ_naive={DELTA_NAIVE}")
    print(f"  n_eff_min_global={N_EFF_MIN_GLOBAL}  n_eff_min_active={N_EFF_MIN_ACTIVE}")
    print()

    draws = generate_all_draws()
    print(f"  Generated {len(draws)} draws.")
    print()

    inv_per_draw: list[list[GlobalInvarianceCandidate]] = []
    rates_per_draw: list[list[DirectionalRates]] = []
    q_per_draw: list[dict[str, dict[int, int]]] = []
    reports_per_draw: list[list[AxisReport]] = []

    for di, draw in enumerate(draws):
        out = _run_one_draw(di, draw)
        inv_per_draw.append(out["invariance"])
        rates_per_draw.append(out["rates"])
        q_per_draw.append(out["q_histograms"])

        # Subsumption (no-op for current R^Ω) and axis classification.
        inv_subsumed = drop_subsumed(out["invariance"])
        accepted_keys = {
            (c.pipeline, c.t_name, c.r_name) for c in inv_subsumed
        }

        # Apply the subsumption mask to the candidate list given to the
        # axis classifier.
        from dataclasses import replace
        masked_inv = [
            c if c.is_identity or (c.pipeline, c.t_name, c.r_name) in accepted_keys
              or not c.accepted
            else replace(c, accepted=False)
            for c in out["invariance"]
        ]
        reports = classify_axes(masked_inv, out["rates"], EPS)
        reports_per_draw.append(reports)

    # =================================================================
    # Stability + criteria
    # =================================================================
    criteria = evaluate_criteria(reports_per_draw, inv_per_draw, rates_per_draw)
    print()
    print("-- Success criteria --")
    for name, ok, detail in criteria:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}")
        print(f"         {detail}")

    all_pass = all(ok for _, ok, _ in criteria)
    print()
    print("OVERALL: " + ("PASS" if all_pass else "FAIL"))

    # =================================================================
    # Write artifacts
    # =================================================================

    # signatures.csv — invariance + directional rows
    sig_rows: list[dict] = []
    for di in range(K_D):
        for c in inv_per_draw[di]:
            sig_rows.append({
                "seal_sha256": seal_hash, "draw": di, "kind": "invariance",
                "pipeline": c.pipeline, "axis": c.axis, "t_name": c.t_name,
                "is_identity": int(c.is_identity), "r_name": c.r_name,
                "k": c.k, "n_eff": c.n_eff, "n_raw": c.n_raw,
                "p_hat": round(c.p_hat, 4), "cp_lcb": round(c.cp_lcb_value, 4),
                "accepted": int(c.accepted),
                "skipped_low_neff": int(c.skipped_low_neff),
            })
        for r in rates_per_draw[di]:
            sig_rows.append({
                "seal_sha256": seal_hash, "draw": di, "kind": "directional",
                "pipeline": r.pipeline, "axis": r.axis, "t_name": r.t_name,
                "is_identity": 0,
                "r_name": "directional_rates",
                "k": r.correct_count, "n_eff": r.n_eff_active,
                "n_raw": N_PER_DRAW,
                "p_hat": round(r.correct_rate, 4),
                "cp_lcb": round(r.correct_lcb, 4),
                "accepted": int(r.correct_high_accepted),
                "skipped_low_neff": int(r.n_active_below_floor),
            })
    _write_csv(HERE / "signatures.csv", sig_rows)

    # directional_rates.csv — per-T per-pipeline per-draw rate breakdown
    rate_rows: list[dict] = []
    for di in range(K_D):
        for r in rates_per_draw[di]:
            rate_rows.append({
                "seal_sha256": seal_hash, "draw": di,
                "pipeline": r.pipeline, "axis": r.axis, "t_name": r.t_name,
                "is_borderline": int(r.is_borderline),
                "expected_direction": r.expected_direction,
                "n_eff_active": r.n_eff_active,
                "below_floor": int(r.n_active_below_floor),
                "correct_count": r.correct_count,
                "wrong_count": r.wrong_count,
                "no_effect_count": r.no_effect_count,
                "correct_rate": round(r.correct_rate, 4),
                "wrong_rate": round(r.wrong_rate, 4),
                "no_effect_rate": round(r.no_effect_rate, 4),
                "correct_lcb": round(r.correct_lcb, 4),
                "wrong_ucb": round(r.wrong_ucb, 4),
                "no_effect_lcb": round(r.no_effect_lcb, 4),
                "correct_high_accepted": int(r.correct_high_accepted),
                "wrong_low_accepted": int(r.wrong_low_accepted),
                "naive_correct_count": r.naive_correct_count,
                "naive_correct_rate": round(r.naive_correct_rate, 4),
                "naive_correct_high_accepted": int(r.naive_correct_high_accepted),
            })
    _write_csv(HERE / "directional_rates.csv", rate_rows)

    # axis_summary.csv
    axis_rows: list[dict] = []
    for di, reports in enumerate(reports_per_draw):
        for r in reports:
            row = {"seal_sha256": seal_hash, "draw": di}
            row.update(asdict(r))
            axis_rows.append(row)
    _write_csv(HERE / "axis_summary.csv", axis_rows)

    # q_histogram.csv — empirical q_0.95 distribution per (pipeline, draw)
    q_rows: list[dict] = []
    for di, hists in enumerate(q_per_draw):
        for pname, hist in hists.items():
            row = {"seal_sha256": seal_hash, "draw": di, "pipeline": pname}
            for bucket in range(7):
                row[f"q_{bucket}"] = hist.get(bucket, 0)
            row["total"] = sum(hist.values())
            q_rows.append(row)
    _write_csv(HERE / "q_histogram.csv", q_rows)

    # stability.csv — pairwise Jaccard for f_track
    track_sigs = []
    for di in range(K_D):
        keys = set()
        for c in inv_per_draw[di]:
            if c.is_identity or not c.accepted:
                continue
            if c.pipeline == "f_track":
                keys.add((c.t_name, c.r_name))
        for r in rates_per_draw[di]:
            if r.pipeline != "f_track":
                continue
            if r.n_active_below_floor:
                continue
            if r.correct_high_accepted and r.wrong_low_accepted:
                keys.add((r.t_name, "correct"))
            elif r.wrong_rate >= 1 - EPS and r.correct_rate <= EPS:
                keys.add((r.t_name, "wrong"))
            elif r.no_effect_rate >= 1 - EPS:
                keys.add((r.t_name, "no_effect"))
        track_sigs.append(keys)

    stab_rows: list[dict] = []
    for i in range(K_D):
        for j in range(i + 1, K_D):
            a, b = track_sigs[i], track_sigs[j]
            jac = len(a & b) / len(a | b) if (a or b) else 1.0
            stab_rows.append({
                "seal_sha256": seal_hash, "i": i, "j": j,
                "jaccard": round(jac, 4),
                "size_i": len(a), "size_j": len(b),
                "intersection_size": len(a & b),
            })
    triple = set.intersection(*track_sigs) if K_D >= 2 else set()
    union = set.union(*track_sigs) if track_sigs else set()
    stab_rows.append({
        "seal_sha256": seal_hash, "i": "triple", "j": "triple",
        "jaccard": round(len(triple) / len(union) if union else 0.0, 4),
        "size_i": len(triple), "size_j": len(union),
        "intersection_size": len(triple),
    })
    _write_csv(HERE / "stability.csv", stab_rows)

    # criteria.csv
    crit_rows = [
        {
            "seal_sha256": seal_hash, "criterion": name,
            "passed": int(ok), "detail": detail,
        }
        for name, ok, detail in criteria
    ]
    _write_csv(HERE / "criteria.csv", crit_rows)

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
