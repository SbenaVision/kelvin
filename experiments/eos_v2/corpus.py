"""Boundary-aware synthetic corpus generator.

K_D draws of N=300 each, with deterministic seeds from
config.CORPUS_SEEDS. 65% boundary, 17.5% interior-pass, 17.5%
interior-fail per draw.

Active-boundary subset (used for f_wrongstochastic detection):
  cases with risk_score ∈ [ACTIVE_BOUNDARY_RISK_LO,
  ACTIVE_BOUNDARY_RISK_HI] — the targeted clause is decision-revealing.
"""
from __future__ import annotations

import random

from config import (
    ACTIVE_BOUNDARY_RISK_HI,
    ACTIVE_BOUNDARY_RISK_LO,
    BOUNDARY_FRACTION,
    CORPUS_SEEDS,
    INTERIOR_FAIL_FRACTION,
    INTERIOR_PASS_FRACTION,
    K_D,
    N_PER_DRAW,
)
from rule_grammar import default_rule
from schema import Case, Founder, Input


_RISK_POOL = [
    "market_risk", "regulatory_risk", "technical_risk", "funding_risk",
    "team_risk", "competition_risk", "scaling_risk", "legal_risk",
]
_NAME_POOL = [
    "Alex", "Blake", "Casey", "Drew", "Emery", "Finley",
    "Gray", "Harper", "Indigo", "Jules", "Kai", "Lane",
]
_STAGES = ["idea", "building", "first_users"]


def _sample_founders(rng: random.Random) -> list[Founder]:
    n = rng.randint(1, 4)
    return [Founder(rng.choice(_NAME_POOL), rng.randint(0, 25)) for _ in range(n)]


def _sample_risks(rng: random.Random) -> list[str]:
    n = rng.randint(0, 5)
    return rng.sample(_RISK_POOL, k=min(n, len(_RISK_POOL)))


def _sample_description(rng: random.Random) -> str:
    return rng.choice([
        "", "short desc",
        "a longer description of the venture's approach",
        "detailed narrative about product, market, and execution plans",
    ])


def _boundary_case(rng: random.Random) -> Case:
    revenue = rng.choice([
        rng.randint(5_000, 9_999),
        rng.randint(10_000, 19_999),
        rng.randint(20_000, 30_000),
    ])
    team = rng.choice([1, 2, 3, 4, 5])
    risk = rng.randint(25, 55)
    return Case(
        revenue_monthly=revenue, team_size=team, risk_score=risk,
        stage=rng.choice(_STAGES),
        founders=_sample_founders(rng), risks=_sample_risks(rng),
        description=_sample_description(rng),
    )


def _interior_passing_case(rng: random.Random) -> Case:
    return Case(
        revenue_monthly=rng.randint(80_000, 150_000),
        team_size=rng.randint(8, 15),
        risk_score=rng.randint(0, 10),
        stage=rng.choice(_STAGES),
        founders=_sample_founders(rng), risks=_sample_risks(rng),
        description=_sample_description(rng),
    )


def _interior_failing_case(rng: random.Random) -> Case:
    return Case(
        revenue_monthly=rng.randint(0, 1_000),
        team_size=1,
        risk_score=rng.randint(80, 100),
        stage=rng.choice(_STAGES),
        founders=_sample_founders(rng), risks=_sample_risks(rng),
        description=_sample_description(rng),
    )


def generate_draw(seed: int, draw_idx: int) -> list[Input]:
    rng = random.Random(seed)
    rule = default_rule()
    n_b = int(round(N_PER_DRAW * BOUNDARY_FRACTION))
    n_p = int(round(N_PER_DRAW * INTERIOR_PASS_FRACTION))
    n_f = N_PER_DRAW - n_b - n_p

    cases: list[Case] = []
    cases.extend(_boundary_case(rng) for _ in range(n_b))
    cases.extend(_interior_passing_case(rng) for _ in range(n_p))
    cases.extend(_interior_failing_case(rng) for _ in range(n_f))
    rng.shuffle(cases)

    # case_id encodes draw and within-draw index, used for replay RNG seeding.
    inputs: list[Input] = []
    for i, c in enumerate(cases):
        c.case_id = draw_idx * 1_000_000 + i
        inputs.append(Input(case=c, rule_text=rule))
    return inputs


def generate_all_draws() -> list[list[Input]]:
    """Returns K_D draws, each a list of N_PER_DRAW Inputs."""
    assert len(CORPUS_SEEDS) == K_D
    return [generate_draw(seed, idx) for idx, seed in enumerate(CORPUS_SEEDS)]


def is_active_boundary(inp: Input) -> bool:
    return ACTIVE_BOUNDARY_RISK_LO <= inp.case.risk_score <= ACTIVE_BOUNDARY_RISK_HI
