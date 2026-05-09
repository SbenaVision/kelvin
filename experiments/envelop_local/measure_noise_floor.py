#!/usr/bin/env python3
"""Manual noise-floor replication — Pillar 1 η measurement.

Kelvin 0.2.1 accepts the `noise_floor:` config block but does not yet feed
it into scoring (Pillar 1 K_cal is held for v0.3.0 per CHANGELOG). This
script performs the same operation outside Kelvin so we can quote η today.

For each case, invoke the pipeline N=10 times on the unperturbed baseline
input. Record every verdict. η is the fraction of replications whose
verdict differs from the case's modal verdict, averaged across cases.

  K_cal = max(0, K_raw - η)

For a fully deterministic pipeline η = 0 and K_cal = K_raw. The point of
the measurement is to detect stochasticity that would otherwise contaminate
the Invariance signal (a pipeline that disagrees with itself on unchanged
inputs has a noise floor you must back out before claiming the Invariance
drift is evidence of presentation-reactivity).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


def run_once(cmd: list[str], input_path: Path, tmp_out: Path) -> str:
    """Run the pipeline once and return the verdict string."""
    full = [c.replace("{input}", str(input_path)).replace("{output}", str(tmp_out)) for c in cmd]
    subprocess.run(full, check=True, capture_output=True, text=True)
    return json.loads(tmp_out.read_text())["verdict"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pipeline", required=True, help="Pipeline script, e.g. pipelines/envelop.py")
    ap.add_argument("--cases", default="cases", help="Cases directory")
    ap.add_argument("--n", type=int, default=10, help="Replications per case")
    ap.add_argument("--out", default="results/noise_floor.json")
    args = ap.parse_args()

    cases_dir = Path(args.cases)
    case_files = sorted(cases_dir.glob("*.md"))
    if not case_files:
        print(f"No cases in {cases_dir}", file=sys.stderr)
        return 1

    cmd = ["python3", args.pipeline, "--input", "{input}", "--output", "{output}"]
    tmp_out = Path("/tmp/noise_floor_probe.json")

    per_case = {}
    total_replications = 0
    total_drift = 0

    for case_file in case_files:
        verdicts = []
        for _ in range(args.n):
            verdicts.append(run_once(cmd, case_file, tmp_out))
        counts = Counter(verdicts)
        modal, modal_n = counts.most_common(1)[0]
        drift = args.n - modal_n
        per_case[case_file.stem] = {
            "n": args.n,
            "verdicts": verdicts,
            "modal": modal,
            "modal_n": modal_n,
            "drift_n": drift,
            "drift_rate": drift / args.n,
        }
        total_replications += args.n
        total_drift += drift

    eta = total_drift / total_replications
    out = {
        "pipeline": args.pipeline,
        "n_cases": len(case_files),
        "replications_per_case": args.n,
        "total_replications": total_replications,
        "total_drift": total_drift,
        "eta": eta,
        "per_case": per_case,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    print(f"η (noise floor) = {eta:.4f} over {total_replications} replications")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
