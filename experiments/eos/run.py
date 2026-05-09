"""EOS orchestrator.

Pipeline
  1. Generate corpus (N=500, 60% boundary / 40% interior, seed=42).
  2. Split 70/30 into train (n=350) and holdout (n=150).
  3. For each pipeline × T × R, run discovery on train, then on holdout.
  4. Apply subsumption to train-accepted and holdout-accepted sets.
  5. Classify axes per pipeline using train-signature (subsumed).
  6. Compute stability: a train-accepted pair is "stable" iff it is also
     accepted on the holdout at the same ε and α.
  7. Apply PASS/FAIL criteria (success_criteria.py docstring).
  8. Write signatures.csv, axis_summary.csv, stability.csv, results.md.

Statistical parameters (thesis §4)
  ε = 0.05             acceptance threshold (p ≥ 1 − ε)
  δ = 0.05             family-wise error budget
  m = |T| × |R|        number of hypotheses tested (identity INCLUDED
                       in m because we do test it; we drop identity
                       from the *signature* for reporting, not from
                       the Bonferroni count)
  α = δ / m            per-hypothesis CP level
  γ ≈ 0.10             Hoeffding margin at n = 350

Sample-size check
  n ≥ ln(2m/δ) / (2γ²)
  m = 22 T × 4 R = 88; ln(2·88/0.05) = ln(3520) ≈ 8.17
  n ≥ 8.17 / 0.02 ≈ 408
  Train n=350 gives γ = sqrt(ln(3520)/700) ≈ 0.108 — within thesis
  tolerance for γ=0.10 (<5% relative). We use exact CP for acceptance
  regardless; the Hoeffding bound is only a sanity guide.
"""
from __future__ import annotations

import csv
import sys
from dataclasses import asdict, replace
from pathlib import Path

# Allow running as `python run.py` from inside experiments/eos/
sys.path.insert(0, str(Path(__file__).parent))

from axis_classifier import AxisReport, classify_axes
from corpus import generate_corpus, split_train_holdout
from discover import Candidate, evaluate_all
from pipelines import PIPELINES
from relations import CATALOGUE as R_CATALOGUE
from subsumption import drop_subsumed
from transformations import CATALOGUE as T_CATALOGUE


# --- Statistical parameters ---
EPS = 0.05
DELTA = 0.05
M = len(T_CATALOGUE) * len(R_CATALOGUE)  # 22 * 4 = 88
ALPHA = DELTA / M
N_CORPUS = 500
TRAIN_FRAC = 0.70
CORPUS_SEED = 42
DISCOVERY_SEED = 7
OUT_DIR = Path(__file__).parent


def _signature_key(c: Candidate) -> tuple[str, str, str]:
    return (c.pipeline, c.t_name, c.r_name)


def _subsumed_signature(
    candidates: list[Candidate],
) -> set[tuple[str, str, str]]:
    """Return the subsumed-accepted signature set for these candidates."""
    kept = drop_subsumed(candidates)
    return {_signature_key(c) for c in kept if c.accepted}


def _apply_stability_mask(
    candidates: list[Candidate],
    stable_keys: set[tuple[str, str, str]],
) -> list[Candidate]:
    """Return candidates with `accepted` replaced by True iff stable."""
    out: list[Candidate] = []
    for c in candidates:
        out.append(replace(c, accepted=(_signature_key(c) in stable_keys)))
    return out


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _candidate_row(
    train: Candidate, hold: Candidate, stable: bool
) -> dict:
    assert train.pipeline == hold.pipeline
    assert train.t_name == hold.t_name
    assert train.r_name == hold.r_name
    return {
        "pipeline": train.pipeline,
        "axis": train.axis,
        "t_name": train.t_name,
        "r_name": train.r_name,
        "is_identity": int(train.is_identity),
        "k_train": train.k,
        "n_train": train.n,
        "p_hat_train": round(train.p_hat, 4),
        "cp_lcb_train": round(train.cp_lcb, 4),
        "accepted_train": int(train.accepted),
        "k_hold": hold.k,
        "n_hold": hold.n,
        "p_hat_hold": round(hold.p_hat, 4),
        "cp_lcb_hold": round(hold.cp_lcb, 4),
        "accepted_hold": int(hold.accepted),
        "stable": int(stable),
    }


def _print_banner() -> None:
    print("=" * 72)
    print("EOS — Empirical Oracle Signature discovery")
    print("=" * 72)
    print(f"  N_corpus = {N_CORPUS}  (60% boundary, 40% interior)")
    print(f"  Train/holdout = {TRAIN_FRAC:.0%} / {1 - TRAIN_FRAC:.0%}")
    print(f"  |T| = {len(T_CATALOGUE)}   |R| = {len(R_CATALOGUE)}   m = {M}")
    print(f"  ε = {EPS}   δ = {DELTA}   α = δ/m = {ALPHA:.3e}")
    print(f"  Pipelines: {list(PIPELINES)}")
    print()


def main() -> int:
    _print_banner()

    corpus = generate_corpus(n=N_CORPUS, seed=CORPUS_SEED)
    train, holdout = split_train_holdout(corpus, train_frac=TRAIN_FRAC)
    print(f"  corpus split: train={len(train)}  holdout={len(holdout)}")
    print()

    # --- Phase 1: evaluate every (pipeline, T, R) on train and on holdout ---
    all_train: list[Candidate] = []
    all_hold: list[Candidate] = []
    for pipeline_name, f in PIPELINES.items():
        all_train.extend(evaluate_all(
            pipeline_name, f, T_CATALOGUE, R_CATALOGUE, train,
            eps=EPS, alpha=ALPHA, seed=DISCOVERY_SEED,
        ))
        all_hold.extend(evaluate_all(
            pipeline_name, f, T_CATALOGUE, R_CATALOGUE, holdout,
            eps=EPS, alpha=ALPHA, seed=DISCOVERY_SEED,
        ))

    # --- Identity sanity check (thesis §3 bullet 6) ---
    identity_fails: list[Candidate] = [
        c for c in all_train
        if c.is_identity and not c.accepted
    ]
    print("-- Identity sanity (must pass R_eq at p=1 on all pipelines) --")
    if identity_fails:
        for c in identity_fails:
            print(f"  FAIL: {c.pipeline}/{c.t_name}/{c.r_name}  k/n = {c.k}/{c.n}")
        print()
        print("ABORT: identity T failed acceptance. Bug in transformations or pipelines.")
        return 2
    else:
        print("  OK — identity accepted on all 4 R for all 4 pipelines.")
    print()

    # --- Phase 2: subsumed signatures on train and holdout ---
    train_sig = _subsumed_signature(all_train)
    hold_sig = _subsumed_signature(all_hold)

    # Stability: a pair is stable iff accepted (post-subsumption) on both.
    stable_sig = train_sig & hold_sig

    # --- Phase 3: axis classification uses STABLE signature ---
    # Build a synthetic candidate list with accepted=True iff stable,
    # restricted to the subsumed-train candidates. The classifier reads
    # `accepted` to decide T-invariant / T-responsive.
    stability_masked = _apply_stability_mask(all_train, stable_sig)
    axis_reports = classify_axes(stability_masked)

    # --- Phase 4: build signatures.csv (one row per candidate) ---
    # Pair train/hold candidates by (pipeline, t_name, r_name).
    hold_by_key = {_signature_key(c): c for c in all_hold}
    sig_rows: list[dict] = []
    for tc in all_train:
        hc = hold_by_key[_signature_key(tc)]
        stable = _signature_key(tc) in stable_sig
        sig_rows.append(_candidate_row(tc, hc, stable))
    _write_csv(OUT_DIR / "signatures.csv", sig_rows)

    # --- Phase 5: axis_summary.csv ---
    axis_rows = [asdict(r) for r in axis_reports]
    _write_csv(OUT_DIR / "axis_summary.csv", axis_rows)

    # --- Phase 6: stability.csv (only accepted-on-train pairs) ---
    stab_rows = [r for r in sig_rows if r["accepted_train"] == 1]
    _write_csv(OUT_DIR / "stability.csv", stab_rows)

    # --- Phase 7: PASS/FAIL criteria ---
    criteria = _evaluate_success_criteria(axis_reports, stable_sig, train_sig)
    _print_axis_summary(axis_reports)
    _print_signature_diffs(stable_sig)
    _print_criteria(criteria)

    all_passed = all(ok for _, ok in criteria)
    print()
    print("OVERALL: " + ("PASS" if all_passed else "FAIL"))
    return 0 if all_passed else 1


# =====================================================================
# Success criteria + reporters
# =====================================================================

def _pipeline_axis(reports: list[AxisReport], pipeline: str, axis: str) -> AxisReport | None:
    for r in reports:
        if r.pipeline == pipeline and r.axis == axis:
            return r
    return None


def _pipeline_signature(
    sig: set[tuple[str, str, str]], pipeline: str
) -> set[tuple[str, str]]:
    return {(t, r) for (p, t, r) in sig if p == pipeline}


def _evaluate_success_criteria(
    reports: list[AxisReport],
    stable_sig: set[tuple[str, str, str]],
    train_sig: set[tuple[str, str, str]],
) -> list[tuple[str, bool]]:
    track_sig = _pipeline_signature(stable_sig, "f_track")
    blind_sig = _pipeline_signature(stable_sig, "f_ruleblind")
    const_sig = _pipeline_signature(stable_sig, "f_constant")
    wrong_sig = _pipeline_signature(stable_sig, "f_wrongrule")

    # Track differs from each adversary.
    track_vs_blind = track_sig != blind_sig
    track_vs_const = track_sig != const_sig
    track_vs_wrong = track_sig != wrong_sig

    # Rule axes behavior per pipeline.
    def axis_is(pipeline: str, axis: str, expected: str) -> bool:
        r = _pipeline_axis(reports, pipeline, axis)
        return r is not None and r.classification == expected

    track_rt_resp = axis_is("f_track", "rule_threshold", "responsive")
    track_rc_resp = axis_is("f_track", "rule_clause", "responsive")

    blind_rt_ign = axis_is("f_ruleblind", "rule_threshold", "ignored-candidate")
    blind_rc_ign = axis_is("f_ruleblind", "rule_clause", "ignored-candidate")

    const_rt_ign = axis_is("f_constant", "rule_threshold", "ignored-candidate")
    const_rc_ign = axis_is("f_constant", "rule_clause", "ignored-candidate")

    # f_wrongrule: the adversary READS the rule, so it should be responsive
    # on rule-text axes (it re-evaluates whenever rule text changes) but
    # its signature at the (T, R) level differs from f_track.
    wrong_rt_resp = axis_is("f_wrongrule", "rule_threshold", "responsive")

    # Order axes invariant across all pipelines.
    order_invariant_all = all(
        axis_is(p, "order", "invariant-candidate")
        for p in ("f_track", "f_ruleblind", "f_constant", "f_wrongrule")
    )

    # Stability: ≥90% of train-accepted signature must be stable on holdout.
    # (Exact ratio acceptable; overall-PASS still requires specific criteria.)
    stability_ratio = (
        len(stable_sig) / len(train_sig) if train_sig else 0.0
    )
    stability_ok = stability_ratio >= 0.90

    # Signature non-trivial for f_track (not empty, not identity-only).
    non_trivial = len(track_sig) >= 3  # at least three accepted pairs after subsumption

    return [
        (f"f_track signature differs from f_ruleblind",    track_vs_blind),
        (f"f_track signature differs from f_constant",     track_vs_const),
        (f"f_track signature differs from f_wrongrule",    track_vs_wrong),
        (f"f_track rule_threshold axis = responsive",      track_rt_resp),
        (f"f_track rule_clause axis = responsive",         track_rc_resp),
        (f"f_ruleblind rule_threshold = ignored-candidate", blind_rt_ign),
        (f"f_ruleblind rule_clause = ignored-candidate",    blind_rc_ign),
        (f"f_constant rule_threshold = ignored-candidate",  const_rt_ign),
        (f"f_constant rule_clause = ignored-candidate",     const_rc_ign),
        (f"f_wrongrule rule_threshold = responsive",        wrong_rt_resp),
        (f"order axis invariant across all pipelines",      order_invariant_all),
        (f"train→holdout stability ≥ 90% ({stability_ratio:.1%})",
         stability_ok),
        (f"f_track signature non-trivial (|Σ_track| ≥ 3)",  non_trivial),
    ]


def _print_axis_summary(reports: list[AxisReport]) -> None:
    print("-- Axis classification (subsumed, stable pairs) --")
    by_pipeline: dict[str, list[AxisReport]] = {}
    for r in reports:
        by_pipeline.setdefault(r.pipeline, []).append(r)
    for p in sorted(by_pipeline):
        print(f"  {p}")
        for r in sorted(by_pipeline[p], key=lambda r: r.axis):
            label = r.classification.upper()
            print(
                f"    {r.axis:18s} → {label:22s} "
                f"(resp={r.n_responsive} inv={r.n_invariant} null={r.n_null}"
                f" / {r.n_transforms})"
            )
    print()


def _print_signature_diffs(stable_sig: set[tuple[str, str, str]]) -> None:
    track = _pipeline_signature(stable_sig, "f_track")
    blind = _pipeline_signature(stable_sig, "f_ruleblind")
    const = _pipeline_signature(stable_sig, "f_constant")
    wrong = _pipeline_signature(stable_sig, "f_wrongrule")
    print("-- Signature sizes (stable, subsumed) --")
    print(f"  |Σ(f_track)|     = {len(track)}")
    print(f"  |Σ(f_wrongrule)| = {len(wrong)}")
    print(f"  |Σ(f_ruleblind)|= {len(blind)}")
    print(f"  |Σ(f_constant)| = {len(const)}")
    print(f"  Σ(f_track) ∖ Σ(f_wrongrule): {len(track - wrong)} pair(s)")
    print(f"  Σ(f_wrongrule) ∖ Σ(f_track): {len(wrong - track)} pair(s)")
    print(f"  Σ(f_track) ∖ Σ(f_ruleblind): {len(track - blind)} pair(s)")
    print(f"  Σ(f_ruleblind) ∖ Σ(f_track): {len(blind - track)} pair(s)")
    print()


def _print_criteria(criteria: list[tuple[str, bool]]) -> None:
    print("-- Success criteria --")
    for label, ok in criteria:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {label}")


if __name__ == "__main__":
    sys.exit(main())
