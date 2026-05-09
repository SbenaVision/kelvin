"""End-to-end orchestrator.

Runs discovery, applies the bug-symmetry filter, computes precision /
recall / bug-rejection rates, then runs the regression catch test
against the buggy pipeline. Prints a plain-text report and writes a
machine-readable JSON record for reproducibility.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running as `python run.py` from inside experiments/mr_discovery/
sys.path.insert(0, str(Path(__file__).parent))

from bug_filter import filter_bug_symmetries
from corpus import generate_corpus
from discover import discover
from ground_truth import GROUND_TRUTH, bug_symmetry_mrs, valid_mrs
from pipeline import score, score_buggy
from regression import run as run_regression
from relations import CATALOGUE as R_CATALOGUE
from subsumption import drop_subsumed
from transformations import CATALOGUE as T_CATALOGUE


def main(n: int = 200, seed: int = 42) -> int:
    corpus = generate_corpus(n=n, seed=seed)

    # Phase 1: discovery
    discovered_raw, all_candidates = discover(
        f=score,
        corpus=corpus,
        transforms=T_CATALOGUE,
        relations=R_CATALOGUE,
    )

    # Phase 2: subsumption — drop R' if a stronger R on the same T is also discovered
    discovered = drop_subsumed(discovered_raw)

    # Phase 3: bug-symmetry filter
    filtered = filter_bug_symmetries(discovered, all_candidates)

    # Phase 3: evaluate against ground truth
    discovered_set = {(c.t_name, c.r_name) for c in discovered}
    kept_set = {(c.t_name, c.r_name) for c in filtered.kept}
    gt_valid = set(valid_mrs())
    gt_bugs = set(bug_symmetry_mrs())

    true_positives = kept_set & gt_valid
    false_positives = kept_set - gt_valid
    false_negatives = gt_valid - kept_set
    bugs_caught_pre_filter = discovered_set & gt_bugs
    bugs_caught_post_filter = kept_set & gt_bugs

    precision = len(true_positives) / max(len(kept_set), 1)
    recall = len(true_positives) / max(len(gt_valid), 1)
    bug_rejection = 1.0 - (len(bugs_caught_post_filter) / max(len(gt_bugs), 1))

    # Phase 4: regression catch
    regression_results = run_regression(
        discovered=filtered.kept,
        f_correct=score,
        f_buggy=score_buggy,
        corpus=corpus,
    )
    any_caught = any(rr.caught for rr in regression_results)

    # --- Report ---
    print("=" * 72)
    print("MR DISCOVERY — RESULTS")
    print("=" * 72)
    print(f"corpus size: {len(corpus)}")
    print(f"|T catalogue|: {len(T_CATALOGUE)}   |R catalogue|: {len(R_CATALOGUE)}")
    print()
    print("-- All candidates --")
    for c in sorted(all_candidates, key=lambda c: (-c.hold_rate, c.t_name, c.r_name)):
        marker = "  " if c.hold_rate < 0.95 else "✓ "
        print(
            f"  {marker}{c.t_name:30s} {c.r_name:5s}  "
            f"hold={c.hold_rate:.3f}  wilson_lb={c.wilson_lower:.3f}"
        )
    print()
    print(f"-- Discovered raw (pre-subsumption): {len(discovered_raw)} --")
    print(f"-- Discovered after subsumption (pre-bug-filter): {len(discovered)} --")
    for c in discovered:
        print(f"  ({c.t_name}, {c.r_name}) on axis '{c.axis}'")
    print()
    print(f"-- Bug-symmetry filter: kept={len(filtered.kept)} rejected={len(filtered.rejected)} --")
    for c in filtered.rejected:
        reason = filtered.reason_by_name[(c.t_name, c.r_name)]
        print(f"  REJECT ({c.t_name}, {c.r_name}): {reason}")
    for c in filtered.kept:
        reason = filtered.reason_by_name[(c.t_name, c.r_name)]
        print(f"  KEEP   ({c.t_name}, {c.r_name}): {reason}")
    print()
    print("-- Metrics vs. ground truth --")
    print(f"  precision:              {precision:.3f}  ({len(true_positives)}/{len(kept_set)})")
    print(f"  recall:                 {recall:.3f}  ({len(true_positives)}/{len(gt_valid)})")
    print(f"  bug-symmetry rejection: {bug_rejection:.3f}  "
          f"({len(gt_bugs) - len(bugs_caught_post_filter)}/{len(gt_bugs)})")
    if false_positives:
        print(f"  FALSE POSITIVES: {sorted(false_positives)}")
    if false_negatives:
        print(f"  FALSE NEGATIVES: {sorted(false_negatives)}")
    print()
    print("-- Regression catch test (injected bug: stage weights flipped) --")
    for rr in regression_results:
        flag = "CAUGHT" if rr.caught else "      "
        print(
            f"  {flag}  ({rr.t_name}, {rr.r_name}): "
            f"vio_correct={rr.violation_rate_correct:.3f}  "
            f"vio_buggy={rr.violation_rate_buggy:.3f}"
        )
    print()
    print(f"  regression caught by at least one MR: {any_caught}")
    print()
    print("-- Success criteria (pre-registered in README) --")
    criteria = [
        ("recall ≥ 0.80",              recall >= 0.80),
        ("precision ≥ 0.80",           precision >= 0.80),
        ("bug-symmetry rejection = 1", bug_rejection >= 0.999),
        ("regression caught",          any_caught),
    ]
    for label, ok in criteria:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {label}")
    all_passed = all(ok for _, ok in criteria)
    print()
    print("OVERALL: " + ("PROOF OF CONCEPT PASSES" if all_passed else "PROOF FAILED"))

    # --- JSON record ---
    record = {
        "corpus_size": len(corpus),
        "seed": seed,
        "ground_truth": [list(t) for t in GROUND_TRUTH],
        "all_candidates": [
            {
                "t": c.t_name, "r": c.r_name, "axis": c.axis,
                "hold_count": c.hold_count, "total": c.total,
                "hold_rate": c.hold_rate, "wilson_lower": c.wilson_lower,
            }
            for c in all_candidates
        ],
        "discovered_raw": [[c.t_name, c.r_name] for c in discovered_raw],
        "discovered_post_subsumption": [[c.t_name, c.r_name] for c in discovered],
        "kept_post_filter": [[c.t_name, c.r_name] for c in filtered.kept],
        "rejected_post_filter": [[c.t_name, c.r_name] for c in filtered.rejected],
        "metrics": {
            "precision": precision,
            "recall": recall,
            "bug_rejection_rate": bug_rejection,
        },
        "regression": [
            {
                "t": rr.t_name, "r": rr.r_name,
                "violation_rate_correct": rr.violation_rate_correct,
                "violation_rate_buggy": rr.violation_rate_buggy,
                "caught": rr.caught,
            }
            for rr in regression_results
        ],
        "criteria": {label: ok for label, ok in criteria},
        "all_passed": all_passed,
    }
    out_path = Path(__file__).parent / "results.json"
    out_path.write_text(json.dumps(record, indent=2))
    print(f"\nwrote {out_path}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
