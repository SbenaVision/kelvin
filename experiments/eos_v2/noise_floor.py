"""Per-case noise-floor estimation.

Plan §7: for each baseline x, run K replays, collect pairwise jitter
J_x = {|y_i - y_j| : i<j}, define q_0.95^noise(x) = 95th percentile of
J_x. Pairwise differences are NOT independent confidence samples;
they're a resampling device for a single point estimate.
"""
from __future__ import annotations

from typing import Callable

from config import K_REPLAYS, NOISE_QUANTILE, PIPELINE_IDS
from schema import Input


PipelineFn = Callable[[Input, int], int]   # f(x, replay_idx) → score


def _quantile(values: list[float], q: float) -> float:
    """Linear-interpolated quantile (numpy-equivalent at default `linear`)."""
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
    """Return {case_id: [y_1, ..., y_K]} for K = K_REPLAYS."""
    out: dict[int, list[int]] = {}
    for inp in inputs:
        ys = [f(inp, replay_idx=k) for k in range(K_REPLAYS)]
        out[inp.case.case_id] = ys
    return out


def pairwise_jitter(ys: list[int]) -> list[int]:
    j: list[int] = []
    for i in range(len(ys)):
        for k in range(i + 1, len(ys)):
            j.append(abs(ys[i] - ys[k]))
    return j


def noise_quantile_per_case(
    replays_by_case: dict[int, list[int]]
) -> dict[int, float]:
    """q_0.95^noise(x) per case from the K(K-1)/2 pairwise differences."""
    return {
        cid: _quantile([float(v) for v in pairwise_jitter(ys)], NOISE_QUANTILE)
        for cid, ys in replays_by_case.items()
    }


def baseline_score_for_pair_eval(
    replays_by_case: dict[int, list[int]],
    case_id: int,
) -> int:
    """Pick a single baseline score y(x) for use in R(f(x), f(Tx)) tests.

    Use the FIRST replay deterministically. This is the y_1 the
    relation evaluates against; the noise floor q is estimated from the
    full set of K replays (not just y_1), so the threshold reflects the
    true jitter even though only y_1 is compared.
    """
    return replays_by_case[case_id][0]
