"""f_wrongstochastic — reads rule_text correctly, but with probability
P_ATTACK silently DROPS THE LAST CLAUSE.

PAIRED attack semantics (v2.2 certification design):
  attack_fires(case_id, pipeline_id) ~ Bernoulli(P_ATTACK)
  — depends ONLY on case_id (and the pipeline id), NOT on replay_idx.
  → Same attack flag for the baseline call (replay_idx=0) and the
    transformed call (replay_idx=1) on the SAME case.

For the default rule "ADVANCE IF revenue >= X AND team_size >= Y AND
risk <= Z", the last clause is the risk clause. So when the attack
fires, the adversary skips the risk clause specifically for that
case (and applies the same skip to both the baseline x evaluation
and the transformed Tx evaluation).

Jitter remains INDEPENDENT across baseline and transformed calls
(via the replay_idx-dependent seed in `_noise.py`).

Analytical pre-prediction (probes #1, #2, #6 with P_ATTACK = 0.50):
  - Attack does not fire (prob 0.5):
        rule effect → R holds with probability ≈ 1.0
  - Attack fires (prob 0.5):
        signed_effect = 0 (both calls drop last clause symmetrically)
        → R holds only via jitter, prob ≈ P(|jitter_diff| > Δ_dir) ≈ 0.0024
  - Marginal: p_c ≈ 0.5012

Pre-registered in v2.2/results.md before any v2.2 evaluation.
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


def _attack_fires(case_id: int) -> bool:
    """PAIRED attack flag: depends on case_id only, NOT on replay_idx.

    Same case_id → same attack outcome regardless of which call (baseline
    or transformed). This is the v2.2 certification semantics — distinct
    from v2.1 where the attack flag was independent per call.
    """
    rng = random.Random(_ATTACK_BASE_SEED ^ hash((case_id, _PIPELINE_ID)))
    return rng.random() < P_ATTACK


def f_wrongstochastic(inp: Input, replay_idx: int = 0) -> int:
    clauses = parse(inp.rule_text)
    if not clauses:
        raw = 50
    else:
        if _attack_fires(inp.case.case_id):
            evaluated = clauses[:-1] if len(clauses) > 1 else []
        else:
            evaluated = clauses
        if not evaluated:
            raw = 50
        else:
            passed = sum(c.eval_on(inp.case) for c in evaluated)
            raw = _score_from_passed(passed, len(evaluated))
    return jitter(raw, inp.case.case_id, replay_idx, _PIPELINE_ID)
