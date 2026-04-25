"""Per-case noise-floor estimation (unchanged from v2).

K=20 baseline replays per case → q_0.95(x) from K(K-1)/2 pairwise
differences (used as a single point estimate; pairs are NOT
independent confidence samples, see v2 plan §7.0).
"""
from __future__ import annotations

from typing import Callable

from config import K_REPLAYS, NOISE_QUANTILE
from schema import Input


PipelineFn = Callable[[Input, int], int]


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n == 1:
        return float(s[0])
    pos = q * (n - 1)
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return s[lo] * (1 - frac) + s[hi] * frac


def baseline_replays(
    f: PipelineFn,
    inputs: list[Input],
    pipeline_id: int,
) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    for inp in inputs:
        out[inp.case.case_id] = [f(inp, replay_idx=k) for k in range(K_REPLAYS)]
    return out


def pairwise_jitter(ys: list[int]) -> list[int]:
    j: list[int] = []
    for i in range(len(ys)):
        for k in range(i + 1, len(ys)):
            j.append(abs(ys[i] - ys[k]))
    return j


def noise_quantile_per_case(replays_by_case: dict[int, list[int]]) -> dict[int, float]:
    return {
        cid: _quantile([float(v) for v in pairwise_jitter(ys)], NOISE_QUANTILE)
        for cid, ys in replays_by_case.items()
    }


def baseline_score_for_pair_eval(
    replays_by_case: dict[int, list[int]],
    case_id: int,
) -> int:
    return replays_by_case[case_id][0]
