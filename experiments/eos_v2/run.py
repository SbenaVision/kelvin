"""EOS v2 orchestrator.

Pipeline:
  1. Verify SEAL.txt hash matches sealed-catalogue files.
  2. Generate K_D independent corpus draws.
  3. Per pipeline: K=20 baseline replays per case → q_0.95 noise floor per case.
  4. For each (T, R^Ω): evaluate per-case Bernoulli z_i with applicability filter,
     run CP+Bonferroni acceptance.
  5. For each (T, R_naive): same but α = δ (no Bonferroni). Diagnostic only.
  6. Subsumption (no-op for current R^Ω) on accepted set per draw.
  7. Stability: pairwise Jaccard + triple intersection of f_track signatures.
  8. Axis classification per pipeline per draw.
  9. Active-boundary subset eval for f_wrongstochastic on rule-threshold axis.
 10. Apply 8 §11 success criteria.
 11. Write CSVs + results.md.
"""
from __future__ import annotations

import csv
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from axis_classifier import AxisReport, classify_axes
from config import (
    DELTA, EPS, K_D, K_REPLAYS, N_EFF_MIN, N_PER_DRAW, PIPELINE_IDS,
)
from corpus import generate_all_draws, is_active_boundary
from discover import (
    CandidateNaive, CandidateOmega, discover_naive, discover_omega,
)
from noise_floor import (
    baseline_replays, baseline_score_for_pair_eval, noise_quantile_per_case,
)
from pipelines import PIPELINES
from relations import NAIVE as R_NAIVE, NOISE_AWARE as R_OMEGA
from schema import Input
from seal_manifest import compute_seal
from subsumption import drop_subsumed
from success_criteria import evaluate as evaluate_criteria
from transformations import CATALOGUE as T_CATALOGUE


M = len(T_CATALOGUE) * len(R_OMEGA)
ALPHA = DELTA / M
TRANSFORM_REPLAY_IDX = K_REPLAYS  # use a fresh replay index for f(Tx)
HERE = Path(__file__).parent


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
            f"SEAL VIOLATED: sealed={sealed_digest} current={current_digest}\n"
            "  → A file in the sealed catalogue has been modified after sealing."
        )
    return current_digest


def _signature_keys(cs: list[CandidateOmega]) -> set[tuple[str, str, str]]:
    return {(c.pipeline, c.t_name, c.r_name) for c in cs if c.accepted and not c.is_identity}


def _run_one_draw(draw_idx: int, draw: list[Input]) -> tuple[
    list[CandidateOmega],
    list[CandidateNaive],
    dict[str, dict[int, float]],
    dict[str, dict[int, list[int]]],
]:
    """Return (omega_candidates, naive_candidates, q_per_case_per_pipeline, replays_per_pipeline) for one draw."""
    print(f"  -- Draw {draw_idx}  (N={len(draw)}) --")
    all_omega: list[CandidateOmega] = []
    all_naive: list[CandidateNaive] = []
    q_per_pipeline: dict[str, dict[int, float]] = {}
    replays_per_pipeline: dict[str, dict[int, list[int]]] = {}

    for pname, f in PIPELINES.items():
        # Phase 1: K_REPLAYS baseline replays for noise floor.
        replays = baseline_replays(f, draw, PIPELINE_IDS[pname])
        q_per_case = noise_quantile_per_case(replays)
        baseline_first = {cid: ys[0] for cid, ys in replays.items()}
        replays_per_pipeline[pname] = replays
        q_per_pipeline[pname] = q_per_case

        median_q = sorted(q_per_case.values())[len(q_per_case) // 2]
        print(f"    {pname}: median q_0.95 = {median_q:.2f}")

        # Phase 2: noise-aware discovery (PRIMARY).
        omega = discover_omega(
            pname, f, T_CATALOGUE, R_OMEGA, draw,
            baseline_first, q_per_case,
            eps=EPS, alpha=ALPHA, n_eff_min=N_EFF_MIN,
            transform_replay_idx=TRANSFORM_REPLAY_IDX,
        )
        all_omega.extend(omega)

        # Phase 3: naive discovery (DIAGNOSTIC ONLY).
        naive = discover_naive(
            pname, f, T_CATALOGUE, R_NAIVE, draw,
            baseline_first, delta=DELTA,
            transform_replay_idx=TRANSFORM_REPLAY_IDX,
        )
        all_naive.extend(naive)
    return all_omega, all_naive, q_per_pipeline, replays_per_pipeline


def _check_load_bearing(
    omega_candidates: list[CandidateOmega],
    naive_candidates: list[CandidateNaive],
) -> tuple[bool, list[tuple[str, str, str, str]]]:
    """Find pairs where naive accepted but omega rejected.

    Pair the two by (pipeline, t_name, dir): naive R_up_naive vs omega
    R_up_omega, etc. R_eq pair: naive R_eq_naive vs omega R_eq_omega.
    """
    omega_by_key = {(c.pipeline, c.t_name, c.r_name): c for c in omega_candidates}
    naive_by_key = {(c.pipeline, c.t_name, c.r_name): c for c in naive_candidates}

    NAIVE_TO_OMEGA = {
        "R_eq_naive":   "R_eq_omega",
        "R_up_naive":   "R_up_omega",
        "R_down_naive": "R_down_omega",
    }

    fired: list[tuple[str, str, str, str]] = []
    for (p, t, naive_r), nc in naive_by_key.items():
        if naive_r not in NAIVE_TO_OMEGA:
            continue
        omega_r = NAIVE_TO_OMEGA[naive_r]
        oc = omega_by_key.get((p, t, omega_r))
        if oc is None:
            continue
        if nc.accepted_alpha_raw and not oc.accepted:
            fired.append((p, t, naive_r, omega_r))
    return bool(fired), fired


def _active_boundary_recheck(
    draw_idx: int, draw: list[Input],
) -> dict[str, list[CandidateOmega]]:
    """For f_wrongstochastic on rule-threshold + case_fact axes,
    re-run discovery on the active-boundary subset.

    Reported separately; not part of the primary signature comparison.
    """
    sub = [inp for inp in draw if is_active_boundary(inp)]
    if len(sub) < N_EFF_MIN // 2:
        return {}
    print(f"    active-boundary subset: n={len(sub)}")
    out: dict[str, list[CandidateOmega]] = {}
    pname = "f_wrongstochastic"
    f = PIPELINES[pname]
    replays = baseline_replays(f, sub, PIPELINE_IDS[pname])
    q_per_case = noise_quantile_per_case(replays)
    baseline_first = {cid: ys[0] for cid, ys in replays.items()}
    omega = discover_omega(
        pname, f, T_CATALOGUE, R_OMEGA, sub,
        baseline_first, q_per_case,
        eps=EPS, alpha=ALPHA, n_eff_min=max(50, len(sub) // 3),
        transform_replay_idx=TRANSFORM_REPLAY_IDX,
    )
    out[pname] = omega
    return out


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _omega_row(c: CandidateOmega, draw_idx: int, seal_hash: str, in_signature: bool) -> dict:
    return {
        "seal_sha256": seal_hash,
        "draw": draw_idx,
        "pipeline": c.pipeline,
        "axis": c.axis,
        "t_name": c.t_name,
        "is_identity": int(c.is_identity),
        "r_name": c.r_name,
        "k": c.k,
        "n_eff": c.n_eff,
        "n_raw": c.n_raw,
        "p_hat": round(c.p_hat, 4),
        "cp_lcb": round(c.cp_lcb_value, 4),
        "accepted": int(c.accepted),
        "skipped_low_neff": int(c.skipped_low_neff),
        "in_signature": int(in_signature),
    }


def main() -> int:
    print("=" * 72)
    print("EOS v2 — Empirical Oracle Signature, sealed-catalogue run")
    print("=" * 72)
    seal_hash = _verify_seal()
    print(f"  SEAL ok. seal_sha256 = {seal_hash}")
    print(f"  K_D={K_D}  N_per_draw={N_PER_DRAW}  K_replays={K_REPLAYS}")
    print(f"  |T|={len(T_CATALOGUE)}  |R^Ω|={len(R_OMEGA)}  m={M}  α=δ/m={ALPHA:.3e}")
    print(f"  ε={EPS}  Δ_eq=5  Δ_dir=4  n_eff_min={N_EFF_MIN}")
    print()

    draws = generate_all_draws()
    print(f"  Generated {len(draws)} draws.")
    print()

    omega_per_draw: list[list[CandidateOmega]] = []
    naive_per_draw: list[list[CandidateNaive]] = []
    reports_per_draw: list[list[AxisReport]] = []
    sig_per_draw: list[set[tuple[str, str, str]]] = []
    active_boundary_per_draw: list[dict[str, list[CandidateOmega]]] = []

    for di, draw in enumerate(draws):
        omega, naive, _q, _reps = _run_one_draw(di, draw)

        # Subsumption (no-op here but preserved).
        omega_subsumed = drop_subsumed(omega)

        # Build signature: accepted, non-identity, post-subsumption.
        sig = _signature_keys(omega_subsumed)

        # Axis classification on subsumed omega set.
        # Pass the FULL omega set (all evaluations) so the classifier
        # can see which T's were skipped for low n_eff. drop_subsumed
        # only keeps accepted candidates, but classification needs to
        # know about non-accepted T's as well.
        for_classifier = []
        accepted_keys = {(c.pipeline, c.t_name, c.r_name) for c in omega_subsumed}
        for c in omega:
            if c.accepted and (c.pipeline, c.t_name, c.r_name) not in accepted_keys:
                # was subsumed: re-mark as not accepted for classifier
                from dataclasses import replace
                for_classifier.append(replace(c, accepted=False))
            else:
                for_classifier.append(c)
        reports = classify_axes(for_classifier)

        omega_per_draw.append(omega)
        naive_per_draw.append(naive)
        reports_per_draw.append(reports)
        sig_per_draw.append(sig)

        # Active-boundary re-check for f_wrongstochastic.
        ab = _active_boundary_recheck(di, draw)
        active_boundary_per_draw.append(ab)

    # Load-bearing check: pool over all draws.
    pooled_omega = [c for od in omega_per_draw for c in od]
    pooled_naive = [c for nd in naive_per_draw for c in nd]
    load_bearing_fired, load_bearing_pairs = _check_load_bearing(pooled_omega, pooled_naive)
    print(f"-- Load-bearing check --")
    print(f"  naive accepted but R^Ω rejected: {len(load_bearing_pairs)} pair(s)")
    if load_bearing_pairs[:8]:
        for (p, t, nr, omr) in load_bearing_pairs[:8]:
            print(f"    {p:18s} / {t:30s} / {nr} → {omr}")
    print()

    # Stability: pairwise Jaccard for f_track.
    track_sigs = [{(t, r) for (p, t, r) in s if p == "f_track"} for s in sig_per_draw]
    pairwise_jaccards: list[tuple[int, int, float]] = []
    for i in range(K_D):
        for j in range(i + 1, K_D):
            a, b = track_sigs[i], track_sigs[j]
            jac = len(a & b) / len(a | b) if (a or b) else 1.0
            pairwise_jaccards.append((i, j, jac))
    triple = set.intersection(*track_sigs) if K_D >= 2 else set()
    print(f"-- Stability --")
    for i, j, jac in pairwise_jaccards:
        print(f"  Jaccard(Σ_track[{i}], Σ_track[{j}]) = {jac:.3f}")
    print(f"  triple intersection |Σ_1 ∩ Σ_2 ∩ Σ_3| = {len(triple)}")
    print(f"  union size avg = {sum(len(s) for s in track_sigs) / K_D:.1f}")
    print()

    # Success criteria.
    criteria = evaluate_criteria(reports_per_draw, sig_per_draw, load_bearing_fired)
    print("-- Success criteria --")
    for name, ok, detail in criteria:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}")
        print(f"         {detail}")
    all_pass = all(ok for _, ok, _ in criteria)
    print()
    print("OVERALL: " + ("PASS" if all_pass else "FAIL"))

    # --- Write artifacts ---
    sig_keys_per_draw = [_signature_keys(drop_subsumed(od)) for od in omega_per_draw]
    sig_rows: list[dict] = []
    for di, omega in enumerate(omega_per_draw):
        sig = sig_keys_per_draw[di]
        for c in omega:
            in_sig = (c.pipeline, c.t_name, c.r_name) in sig
            sig_rows.append(_omega_row(c, di, seal_hash, in_sig))
    _write_csv(HERE / "signatures.csv", sig_rows)

    # axis_summary
    axis_rows: list[dict] = []
    for di, reports in enumerate(reports_per_draw):
        for r in reports:
            row = {"seal_sha256": seal_hash, "draw": di}
            row.update(asdict(r))
            axis_rows.append(row)
    _write_csv(HERE / "axis_summary.csv", axis_rows)

    # stability
    stab_rows: list[dict] = [{
        "seal_sha256": seal_hash,
        "draw_i": i,
        "draw_j": j,
        "jaccard": round(jac, 4),
        "track_sig_size_i": len(track_sigs[i]),
        "track_sig_size_j": len(track_sigs[j]),
    } for (i, j, jac) in pairwise_jaccards]
    stab_rows.append({
        "seal_sha256": seal_hash,
        "draw_i": "triple",
        "draw_j": "triple",
        "jaccard": round(len(triple) / len(set.union(*track_sigs)) if track_sigs and set.union(*track_sigs) else 0.0, 4),
        "track_sig_size_i": len(triple),
        "track_sig_size_j": len(set.union(*track_sigs)),
    })
    _write_csv(HERE / "stability.csv", stab_rows)

    # Active-boundary signatures (only one pipeline, possibly multiple draws).
    ab_rows: list[dict] = []
    for di, ab in enumerate(active_boundary_per_draw):
        for pname, omega in ab.items():
            sig_keys = _signature_keys(drop_subsumed(omega))
            for c in omega:
                in_sig = (c.pipeline, c.t_name, c.r_name) in sig_keys
                ab_rows.append(_omega_row(c, di, seal_hash, in_sig))
    _write_csv(HERE / "signatures_active_boundary.csv", ab_rows)

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
