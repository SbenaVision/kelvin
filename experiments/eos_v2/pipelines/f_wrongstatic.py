"""f_wrongstatic — reads rule_text but inverts the comparator on the LAST clause.

Deterministic adversary: same input → same raw score (before noise).
Detection signal: on the last-clause axis (default: risk), strengthening
the rule produces score INCREASE (R^Ω_↑ accepted) instead of decrease
(R^Ω_↓ on f_track). Wrong-direction monotone signature.
"""
from __future__ import annotations

from config import PIPELINE_IDS
from rule_grammar import Clause, parse
from schema import Input

from ._noise import jitter


_PIPELINE_ID = PIPELINE_IDS["f_wrongstatic"]


def _invert_op(op: str) -> str:
    return {">=": "<", "<=": ">", ">": "<=", "<": ">=", "==": "=="}[op]


def _score_from_passed(passed: int, total: int) -> int:
    if total == 0:
        return 50
    return int(round(20 + 60 * (passed / total)))


def f_wrongstatic(inp: Input, replay_idx: int = 0) -> int:
    clauses = parse(inp.rule_text)
    if not clauses:
        raw = 50
    else:
        tweaked: list[Clause] = list(clauses[:-1])
        last = clauses[-1]
        tweaked.append(Clause(last.field, _invert_op(last.op), last.value))
        passed = sum(c.eval_on(inp.case) for c in tweaked)
        raw = _score_from_passed(passed, len(tweaked))
    return jitter(raw, inp.case.case_id, replay_idx, _PIPELINE_ID)
