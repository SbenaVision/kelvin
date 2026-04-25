"""EOS v2.1 adversary pipelines.

Implemented AFTER the catalogue was sealed. seal_sha256 above (see SEAL.txt).
All pipelines have signature

    f(inp: Input, replay_idx: int) -> int

returning a score in [0, 100]. Determinism is per-call: same
(inp, replay_idx, pipeline_id) tuple always yields the same score.
"""
from __future__ import annotations

from typing import Callable

from .f_constant import f_constant
from .f_ruleblind import f_ruleblind
from .f_track import f_track
from .f_wrongstatic import f_wrongstatic
from .f_wrongstochastic import f_wrongstochastic


PIPELINES: dict[str, Callable] = {
    "f_track":           f_track,
    "f_ruleblind":       f_ruleblind,
    "f_constant":        f_constant,
    "f_wrongstatic":     f_wrongstatic,
    "f_wrongstochastic": f_wrongstochastic,
}
