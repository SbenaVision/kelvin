"""Compute SEAL.txt sha256 over the v2.1 sealed catalogue.

The sealed list is FROZEN by this module.

v2.1 additions over v2:
  - Active subset predicates A_T live in transformations.py
  - cp_lcb.py adds cp_ucb / accept_low for low-rate claims
  - relations.py drops naive equality (load-bearing test is directional only)
  - discover.py is restructured: global invariance + directional rates
  - axis_classifier.py uses 5-way rate-based classification
  - success_criteria.py rewrites c3 (directional rates) and c7 (load-bearing
    via naive vs omega directional on the borderline T's A_T)
  - config.py gains N_EFF_MIN_GLOBAL / N_EFF_MIN_ACTIVE / DELTA_NAIVE
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path


SEALED_FILES: list[str] = [
    "config.py",
    "schema.py",
    "rule_grammar.py",
    "corpus.py",
    "transformations.py",
    "relations.py",
    "noise_floor.py",
    "cp_lcb.py",
    "discover.py",
    "subsumption.py",
    "axis_classifier.py",
    "success_criteria.py",
    "seal_manifest.py",
]


def compute_seal(here: Path | None = None) -> tuple[str, list[tuple[str, str]]]:
    here = here or Path(__file__).parent
    h = hashlib.sha256()
    per_file: list[tuple[str, str]] = []
    for fname in SEALED_FILES:
        path = here / fname
        data = path.read_bytes()
        per_file.append((fname, hashlib.sha256(data).hexdigest()))
        h.update(fname.encode("utf-8"))
        h.update(b"\0")
        h.update(data)
        h.update(b"\0")
    return h.hexdigest(), per_file


def write_seal(here: Path | None = None) -> str:
    here = here or Path(__file__).parent
    digest, per_file = compute_seal(here)
    seal_path = here / "SEAL.txt"
    lines = [
        "# EOS v2.1 sealed-catalogue manifest",
        "# Files in seal order; rewriting any file invalidates the seal.",
        "",
        f"seal_sha256 = {digest}",
        "",
    ]
    for fname, fhash in per_file:
        lines.append(f"{fname}  {fhash}")
    seal_path.write_text("\n".join(lines) + "\n")
    return digest


if __name__ == "__main__":
    digest = write_seal()
    print(f"SEAL written. seal_sha256 = {digest}")
    sys.exit(0)
