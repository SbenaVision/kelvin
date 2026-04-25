"""EOS v2.2 certification adversary pipelines (Commit B).

Implemented after Commit A re-seal (sha256 in SEAL.txt). Five pipelines.

f_wrongstochastic uses PAIRED attack semantics: the attack flag
depends on case_id ONLY (not replay_idx), so the baseline call and
the transformed call see the SAME attack outcome on the same case.

Jitter is INDEPENDENT across baseline and transformed (replay_idx
distinguishes the seeds).
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
