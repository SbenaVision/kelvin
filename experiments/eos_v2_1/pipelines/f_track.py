"""f_track — reads the rule, applies every clause correctly.

Score = 20 + 60·(passed/total). Then noise jitter is applied.
"""
from __future__ import annotations

from config import PIPELINE_IDS
from rule_grammar import parse
from schema import Input

from ._noise import jitter


_PIPELINE_ID = PIPELINE_IDS["f_track"]


def _score_from_passed(passed: int, total: int) -> int:
    if total == 0:
        return 50
    return int(round(20 + 60 * (passed / total)))


def f_track(inp: Input, replay_idx: int = 0) -> int:
    clauses = parse(inp.rule_text)
    passed = sum(c.eval_on(inp.case) for c in clauses)
    raw = _score_from_passed(passed, len(clauses))
    return jitter(raw, inp.case.case_id, replay_idx, _PIPELINE_ID)
