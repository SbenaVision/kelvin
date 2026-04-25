"""f_wrongstochastic — reads rule_text correctly, but with probability
P_ATTACK silently ignores the LAST clause.

Detection signal: on the last-clause axis (default: risk), the
correct-direction R^Ω is satisfied only on the (1 − P_ATTACK) fraction
of cases where the attack does not fire. Hold rate ≈ 1 − P_ATTACK · β
(plan §11 criterion 4). This makes the noise-aware acceptance fail at
ε = 0.10 when the effective failure mass exceeds ε + γ.

Determinism: the attack-fire decision for case c at replay r is
seeded by Random(P_ATTACK_BASE_SEED ^ hash((case_id, replay_idx,
pipeline_id))) so the same triple always produces the same fire/no-fire
decision. This separates attack stochasticity from score-jitter
stochasticity, which uses the shared _noise.jitter seed.
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
            # Skip the last clause entirely.
            evaluated = clauses[:-1] if len(clauses) > 1 else []
        else:
            evaluated = clauses
        if not evaluated:
            raw = 50
        else:
            passed = sum(c.eval_on(inp.case) for c in evaluated)
            raw = _score_from_passed(passed, len(evaluated))
    return jitter(raw, inp.case.case_id, replay_idx, _PIPELINE_ID)
