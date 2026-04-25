"""f_constant — fixed score 50.

Even f_constant gets noise jitter applied so its noise floor is
comparable to the other pipelines. The DECISION_THRESHOLD = 50 sits
exactly at the constant score, so jitter can flip the binary decision
either way; that's a real (and intentional) source of R_sign_eq
variance for f_constant.
"""
from __future__ import annotations

from config import PIPELINE_IDS
from schema import Input

from ._noise import jitter


_PIPELINE_ID = PIPELINE_IDS["f_constant"]


def f_constant(inp: Input, replay_idx: int = 0) -> int:
    raw = 50
    return jitter(raw, inp.case.case_id, replay_idx, _PIPELINE_ID)
