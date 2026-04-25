"""Shared score-jitter for ALL five pipelines.

Per sealed config: with probability P_NOISE per call, perturb the score
by an integer drawn uniformly from NOISE_DELTAS, clipped to
[SCORE_MIN, SCORE_MAX]. Noise distribution is structurally identical
across pipelines, parameterized only by case_id × replay_idx ×
pipeline_id (so f_track replay 0 does NOT share its jitter draw with
f_ruleblind replay 0).
"""
from __future__ import annotations

import random

from config import (
    NOISE_BASE_SEED,
    NOISE_DELTAS,
    P_NOISE,
    SCORE_MAX,
    SCORE_MIN,
)


def _seed(case_id: int, replay_idx: int, pipeline_id: int) -> int:
    return NOISE_BASE_SEED ^ hash((case_id, replay_idx, pipeline_id))


def jitter(score: int, case_id: int, replay_idx: int, pipeline_id: int) -> int:
    rng = random.Random(_seed(case_id, replay_idx, pipeline_id))
    if rng.random() < P_NOISE:
        return max(SCORE_MIN, min(SCORE_MAX, score + rng.choice(NOISE_DELTAS)))
    return score
