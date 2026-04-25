"""f_constant — fixed score 50 then jitter."""
from __future__ import annotations

from config import PIPELINE_IDS
from schema import Input

from ._noise import jitter


_PIPELINE_ID = PIPELINE_IDS["f_constant"]


def f_constant(inp: Input, replay_idx: int = 0) -> int:
    return jitter(50, inp.case.case_id, replay_idx, _PIPELINE_ID)
