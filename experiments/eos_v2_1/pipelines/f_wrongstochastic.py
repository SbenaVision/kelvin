"""f_wrongstochastic — reads rule_text correctly, but with probability
P_ATTACK silently ignores the LAST clause.

Attack stochasticity is sampled INDEPENDENTLY per call (baseline and
transformed each draw their own attack flag). Per the v2.1 spec §8,
this means we do not claim hold rate ≈ 1 − p_attack; instead the
adversary classifies as "degraded" with empirical rates reported.
"""
from __future__ import annotations

import random

from config import P_ATTACK, PIPELINE_IDS
from rule_grammar import parse
from schema import Input

from ._noise import jitter


_PIPELINE_ID = PIPELINE_IDS["f_wrongstochastic"]
_ATTACK_BASE_SEED = 0xBEEF


def _score_from_passed(passed: int, total: int) -> int:
    if total == 0:
        return 50
    return int(round(20 + 60 * (passed / total)))


def _attack_fires(case_id: int, replay_idx: int) -> bool:
    rng = random.Random(_ATTACK_BASE_SEED ^ hash((case_id, replay_idx, _PIPELINE_ID)))
    return rng.random() < P_ATTACK


def f_wrongstochastic(inp: Input, replay_idx: int = 0) -> int:
    clauses = parse(inp.rule_text)
    if not clauses:
        raw = 50
    else:
        if _attack_fires(inp.case.case_id, replay_idx):
            evaluated = clauses[:-1] if len(clauses) > 1 else []
        else:
            evaluated = clauses
        if not evaluated:
            raw = 50
        else:
            passed = sum(c.eval_on(inp.case) for c in evaluated)
            raw = _score_from_passed(passed, len(evaluated))
    return jitter(raw, inp.case.case_id, replay_idx, _PIPELINE_ID)
