"""Boundary-aware synthetic corpus generator.

Per the thesis §6, the rule-threshold sensitivity test is vacuous if no
case sits near the decision boundary: strengthening a threshold would
leave every case's decision unchanged.

We generate a mix:
  60% boundary cases — parameters close to rule thresholds so that
    multiplicative changes (×2 revenue, +2 team, ±10 risk) realistically
    flip the passing count.
  40% interior cases — split evenly between "clearly passing" and
    "clearly failing" configurations, used to verify that monotone
    relations DO hold non-vacuously and to exercise R_sign_eq.

All cases share the same rule (`rule_grammar.default_rule`). Per-case
rule variation is produced by the rule-threshold and rule-clause
transformations at evaluation time.
"""
from __future__ import annotations

import random

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
    return [
        Founder(
            name=rng.choice(_NAME_POOL),
            experience_years=rng.randint(0, 25),
        )
        for _ in range(n)
    ]


def _sample_risks(rng: random.Random) -> list[str]:
    n = rng.randint(0, 5)
    return rng.sample(_RISK_POOL, k=min(n, len(_RISK_POOL)))


def _sample_description(rng: random.Random) -> str:
    return rng.choice([
        "",
        "short desc",
        "a longer description of the venture's approach",
        "detailed narrative about product, market, and execution plans",
    ])


def _boundary_case(rng: random.Random) -> Case:
    # Rule thresholds: revenue≥10000, team_size≥3, risk≤40.
    # "Boundary" = near at least one of the thresholds such that a
    # ×2 / ±2 / ±10 perturbation can flip its clause.
    revenue = rng.choice([
        rng.randint(5_000, 9_999),    # just below rev threshold
        rng.randint(10_000, 19_999),  # just above (but ×2 still passes, /2 drops)
        rng.randint(20_000, 30_000),  # comfortably above but still in reach
    ])
    team = rng.choice([1, 2, 3, 4, 5])
    risk = rng.randint(25, 55)
    return Case(
        revenue_monthly=revenue,
        team_size=team,
        risk_score=risk,
        stage=rng.choice(_STAGES),
        founders=_sample_founders(rng),
        risks=_sample_risks(rng),
        description=_sample_description(rng),
    )


def _interior_passing_case(rng: random.Random) -> Case:
    return Case(
        revenue_monthly=rng.randint(80_000, 150_000),
        team_size=rng.randint(8, 15),
        risk_score=rng.randint(0, 10),
        stage=rng.choice(_STAGES),
        founders=_sample_founders(rng),
        risks=_sample_risks(rng),
        description=_sample_description(rng),
    )


def _interior_failing_case(rng: random.Random) -> Case:
    return Case(
        revenue_monthly=rng.randint(0, 1_000),
        team_size=1,
        risk_score=rng.randint(80, 100),
        stage=rng.choice(_STAGES),
        founders=_sample_founders(rng),
        risks=_sample_risks(rng),
        description=_sample_description(rng),
    )


def generate_corpus(n: int, seed: int = 42) -> list[Input]:
    """Return n Inputs with the default rule attached.

    Mix: 60% boundary, 20% interior-passing, 20% interior-failing.
    Deterministic given `seed`.
    """
    rng = random.Random(seed)
    rule = default_rule()
    n_boundary = int(round(n * 0.60))
    n_pass = int(round(n * 0.20))
    n_fail = n - n_boundary - n_pass

    cases: list[Case] = []
    cases.extend(_boundary_case(rng) for _ in range(n_boundary))
    cases.extend(_interior_passing_case(rng) for _ in range(n_pass))
    cases.extend(_interior_failing_case(rng) for _ in range(n_fail))

    # Stable order derived from the deterministic seed.
    rng.shuffle(cases)
    return [Input(case=c, rule_text=rule) for c in cases]


def split_train_holdout(
    corpus: list[Input], train_frac: float = 0.70
) -> tuple[list[Input], list[Input]]:
    """Deterministic split; first train_frac as train, rest as holdout."""
    k = int(round(len(corpus) * train_frac))
    return corpus[:k], corpus[k:]
