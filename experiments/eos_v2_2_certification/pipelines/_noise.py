"""Shared score-jitter for ALL five pipelines.

Per the V5 theorem coupling Γ_{j,c} (sealed): jitter is INDEPENDENT
across baseline (replay_idx = 0) and transformed (replay_idx = 1)
calls. The seed depends on (case_id, replay_idx, pipeline_id) so
different replays draw different jitter values.

This module is shared by all 5 pipelines so noise is structurally
identical; only `pipeline_id` distinguishes draws.
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
