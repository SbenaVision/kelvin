#!/usr/bin/env python3
"""Envelop local pipeline — parses `## Gate Rule` then runs computeVVS.

Reads founder intake as Kelvin-style markdown, extracts the goal_frame,
stage_profile, and 7 dimensions from the `## Gate Rule` section, and emits
a verdict in {Go, Reshape, No-Go}. Deterministic, zero-network, zero-cost.

The intake prose outside `## Gate Rule` is retained for human review but
does not influence the verdict — the production engine is a pure function
of the seven VVS scores, goal frame, and stage profile.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Make the local vvs.py importable regardless of where kelvin runs us from.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from vvs import compute  # noqa: E402


DIM_RE = re.compile(r"\b([PMCDLFE])\s*=\s*([1-5])\b")
GOAL_RE = re.compile(r"goal\s*frame\s*:\s*(lifestyle|growth|moonshot)", re.IGNORECASE)
STAGE_RE = re.compile(r"stage\s*profile\s*:\s*(early|growth)", re.IGNORECASE)
SECTION_RE = re.compile(r"^##\s+Gate Rule\s*\n(.*?)(?=\n##\s|\Z)",
                        re.DOTALL | re.MULTILINE | re.IGNORECASE)

CASES_DIR = Path(__file__).resolve().parent.parent / "cases"


def _infer_focal_case_name(input_path: Path) -> str | None:
    """Kelvin writes inputs at <run>/<case>/baseline/input.md or
    <run>/<case>/perturbations/<variant>/input.md. Walk up to find the case dir."""
    parts = input_path.resolve().parts
    for marker in ("baseline", "perturbations"):
        if marker in parts:
            i = parts.index(marker)
            if i > 0:
                return parts[i - 1]
    return None


def _focal_gate_body(case_name: str) -> str | None:
    case_file = CASES_DIR / f"{case_name}.md"
    if not case_file.exists():
        return None
    m = SECTION_RE.search(case_file.read_text(encoding="utf-8"))
    return m.group(1).strip() if m else None


def parse_gate_rule(text: str, input_path: Path | None = None) -> dict | None:
    matches = list(SECTION_RE.finditer(text))
    if not matches:
        return None

    # When the perturbation input contains multiple Gate Rule sections
    # (pad_content injects peers), pick the one whose body matches the
    # focal case's baseline. Fall back to first match when there is no
    # disambiguation context.
    focal_body: str | None = None
    if input_path is not None:
        case_name = _infer_focal_case_name(input_path)
        if case_name:
            focal_body = _focal_gate_body(case_name)

    chosen = None
    if focal_body is not None:
        for m in matches:
            if m.group(1).strip() == focal_body:
                chosen = m
                break
    if chosen is None:
        chosen = matches[0]

    body = chosen.group(1)
    dims = {d: int(v) for d, v in DIM_RE.findall(body)}
    goal = GOAL_RE.search(body)
    stage = STAGE_RE.search(body)
    if len(dims) != 7 or not goal or not stage:
        return None
    return {
        "dimensions": dims,
        "goal_frame": goal.group(1).lower(),
        "stage_profile": stage.group(1).lower(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    input_path = Path(args.input)
    text = input_path.read_text(encoding="utf-8")
    parsed = parse_gate_rule(text, input_path)

    if parsed is None:
        # Gate Rule missing or malformed — emit "No-Go" as a conservative default.
        out = {"verdict": "No-Go", "reason": "gate_rule_missing_or_malformed"}
    else:
        result = compute(parsed["dimensions"], parsed["goal_frame"], parsed["stage_profile"])
        out = {
            "verdict": result["verdict"],
            "score": result["score"],
            "band": result["band"],
            "kill_zone": result["kill_zone"],
        }

    Path(args.output).write_text(json.dumps(out), encoding="utf-8")
    print(f"envelop: verdict={out['verdict']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
