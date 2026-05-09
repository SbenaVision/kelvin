"""Toy venture-assessment scorer with known ground-truth MRs.

The pipeline is transparent by design: we can enumerate which (T, R)
pairs *should* hold. That lets us measure the discovery procedure's
precision and recall.

Built-in bug-symmetry trap: `description` is present in the schema but
never read by score(). Any T on description yields R=eq trivially —
the discriminator must flag this.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


STAGE_WEIGHT = {"idea": 10, "building": 20, "first_users": 30}
STAGE_ORDER = ["idea", "building", "first_users"]


@dataclass
class Founder:
    name: str
    experience_years: int


@dataclass
class Venture:
    stage: str
    revenue_monthly: int
    team_size: int
    founders: list[Founder]
    risks: list[str]
    description: str = ""


def _revenue_tier(revenue: int) -> int:
    if revenue <= 0:
        return 0
    if revenue < 1_000:
        return 10
    if revenue < 10_000:
        return 20
    return 30


def _team_bonus(team_size: int) -> int:
    return min(team_size, 10)


def _founder_experience(founders: list[Founder]) -> int:
    if not founders:
        return 0
    avg = sum(f.experience_years for f in founders) / len(founders)
    return min(int(avg), 20)


def _risk_penalty(risks: list[str]) -> int:
    return -min(3 * len(risks), 15)


def score(v: Venture) -> int:
    """Correct pipeline. Note: `description` is deliberately unused."""
    return (
        STAGE_WEIGHT[v.stage]
        + _revenue_tier(v.revenue_monthly)
        + _team_bonus(v.team_size)
        + _founder_experience(v.founders)
        + _risk_penalty(v.risks)
    )


def score_buggy(v: Venture) -> int:
    """Buggy pipeline: stage weights flipped (idea=30, first_users=10)."""
    bugged_weight = {"idea": 30, "building": 20, "first_users": 10}
    return (
        bugged_weight[v.stage]
        + _revenue_tier(v.revenue_monthly)
        + _team_bonus(v.team_size)
        + _founder_experience(v.founders)
        + _risk_penalty(v.risks)
    )


PipelineFn = Callable[[Venture], int]
