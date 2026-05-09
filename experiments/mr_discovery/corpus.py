"""Synthetic corpus generator for ventures.

Inputs are sampled from the schema's valid range. The sampler is
intentionally diverse so that transformations have something to bite
into (non-empty lists, multiple founders, varying stage/revenue).
"""
from __future__ import annotations

import random

from pipeline import Founder, Venture


STAGES = ["idea", "building", "first_users"]
RISK_POOL = [
    "market_risk", "regulatory_risk", "technical_risk", "funding_risk",
    "team_risk", "competition_risk", "scaling_risk", "legal_risk",
]
NAME_POOL = [
    "Alex", "Blake", "Casey", "Drew", "Emery", "Finley",
    "Gray", "Harper", "Indigo", "Jules",
]


def sample_venture(rng: random.Random) -> Venture:
    stage = rng.choice(STAGES)
    # Bias toward a range where mutations can actually move the score.
    revenue = rng.choice([0, 500, 2_500, 5_000, 12_000, 30_000])
    team_size = rng.randint(1, 8)
    n_founders = rng.randint(1, 4)
    founders = [
        Founder(
            name=rng.choice(NAME_POOL),
            experience_years=rng.randint(0, 25),
        )
        for _ in range(n_founders)
    ]
    n_risks = rng.randint(0, 5)
    risks = rng.sample(RISK_POOL, k=min(n_risks, len(RISK_POOL)))
    description = rng.choice([
        "", "short desc", "a longer description of the venture's approach",
        "detailed narrative about product, market, and execution plans",
    ])
    return Venture(
        stage=stage,
        revenue_monthly=revenue,
        team_size=team_size,
        founders=founders,
        risks=risks,
        description=description,
    )


def generate_corpus(n: int, seed: int = 42) -> list[Venture]:
    rng = random.Random(seed)
    return [sample_venture(rng) for _ in range(n)]
