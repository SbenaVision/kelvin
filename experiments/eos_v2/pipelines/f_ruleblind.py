"""f_ruleblind — ignores rule_text entirely.

Heuristic from case fields: revenue + team. Risk_score is NOT used —
this matches the deterministic v1 design. The pipeline responds to
case-fact transforms on revenue/team but is silent on risk and on all
rule-text transforms.
"""
from __future__ import annotations

from config import PIPELINE_IDS
from schema import Input

from ._noise import jitter


_PIPELINE_ID = PIPELINE_IDS["f_ruleblind"]


def f_ruleblind(inp: Input, replay_idx: int = 0) -> int:
    c = inp.case
    rev_bonus = min(40, c.revenue_monthly // 500)
    team_bonus = min(20, c.team_size * 3)
    raw = max(20, min(80, 20 + rev_bonus + team_bonus))
    return jitter(raw, inp.case.case_id, replay_idx, _PIPELINE_ID)
