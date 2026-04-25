"""Direct sampling from D(·|A_c) per probe (sealed).

For each probe c, we generate exactly N_EFF_MIN active samples by
drawing the constrained field from its A_c-restricted marginal and
all other fields from the unconstrained schema marginals.

This is the cleanest interpretation of the V5 theorem's
X_i^{(j,c)} ~ D(· | A_c) IID requirement: per-probe pools, fixed
sample count, deterministic from CORPUS_SEED.

Per-pipeline corpus pools share the SAME inputs across pipelines
(this is allowed; the theorem requires only per-(j,c) row independence
and IID within (j,c)). Different probes get DIFFERENT input pools
(necessary because A_c subsets are mutually different).

Default rule applied uniformly:
    "ADVANCE IF revenue >= 10000 AND team_size >= 3 AND risk <= 40"
"""
from __future__ import annotations

import random

from config import CORPUS_SEED, N_EFF_MIN
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


def _sample_founders(rng: random.Random, min_count: int = 1) -> list[Founder]:
    n = rng.randint(max(min_count, 1), 4)
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


def _make_case(
    rng: random.Random,
    case_id: int,
    revenue: int,
    team: int,
    risk: int,
    founders_min: int = 1,
) -> Case:
    return Case(
        revenue_monthly=revenue,
        team_size=team,
        risk_score=risk,
        stage=rng.choice(_STAGES),
        founders=_sample_founders(rng, min_count=founders_min),
        risks=_sample_risks(rng),
        description=_sample_description(rng),
        case_id=case_id,
    )


def _draw_unconstrained(rng: random.Random) -> tuple[int, int, int]:
    """Schema-marginal draw for (revenue, team, risk) when not constrained."""
    revenue = rng.choice([
        rng.randint(0, 5_000),
        rng.randint(5_000, 30_000),
        rng.randint(30_000, 80_000),
        rng.randint(80_000, 150_000),
    ])
    team = rng.randint(1, 12)
    risk = rng.randint(0, 100)
    return revenue, team, risk


def _make_probe_pool(probe_idx: int, sampler) -> list[Input]:
    """Generate N_EFF_MIN cases for one probe.

    Each probe gets its own deterministic seed = CORPUS_SEED ^ probe_idx
    so pools are independent across probes but reproducible.
    """
    rng = random.Random(CORPUS_SEED ^ probe_idx)
    rule = default_rule()
    inputs: list[Input] = []
    for i in range(N_EFF_MIN):
        case_id = probe_idx * 1_000_000 + i
        c = sampler(rng, case_id)
        inputs.append(Input(case=c, rule_text=rule))
    return inputs


# =====================================================================
# Per-probe samplers — each draws directly from D(·|A_c)
# =====================================================================

def _sampler_strengthen_risk(rng: random.Random, case_id: int) -> Case:
    """A_c = {31..40}"""
    revenue, team, _ = _draw_unconstrained(rng)
    risk = rng.randint(31, 40)
    return _make_case(rng, case_id, revenue, team, risk)


def _sampler_weaken_risk(rng: random.Random, case_id: int) -> Case:
    """A_c = {41..50}"""
    revenue, team, _ = _draw_unconstrained(rng)
    risk = rng.randint(41, 50)
    return _make_case(rng, case_id, revenue, team, risk)


def _sampler_strengthen_revenue(rng: random.Random, case_id: int) -> Case:
    """A_c = [10000, 20000)"""
    _, team, risk = _draw_unconstrained(rng)
    revenue = rng.randint(10000, 19999)
    return _make_case(rng, case_id, revenue, team, risk)


def _sampler_case_team_plus(rng: random.Random, case_id: int) -> Case:
    """A_c = {team == 2}"""
    revenue, _, risk = _draw_unconstrained(rng)
    team = 2
    return _make_case(rng, case_id, revenue, team, risk)


def _sampler_case_revenue_up(rng: random.Random, case_id: int) -> Case:
    """A_c = [5000, 10000)"""
    _, team, risk = _draw_unconstrained(rng)
    revenue = rng.randint(5000, 9999)
    return _make_case(rng, case_id, revenue, team, risk)


def _sampler_case_risk_up(rng: random.Random, case_id: int) -> Case:
    """A_c = {21..40}"""
    revenue, team, _ = _draw_unconstrained(rng)
    risk = rng.randint(21, 40)
    return _make_case(rng, case_id, revenue, team, risk)


def _sampler_permute_founders(rng: random.Random, case_id: int) -> Case:
    """A_c = {len(founders) >= 2}"""
    revenue, team, risk = _draw_unconstrained(rng)
    return _make_case(rng, case_id, revenue, team, risk, founders_min=2)


def _sampler_full_domain(rng: random.Random, case_id: int) -> Case:
    """A_c = X"""
    revenue, team, risk = _draw_unconstrained(rng)
    return _make_case(rng, case_id, revenue, team, risk)


PROBE_SAMPLERS: dict[int, callable] = {
    1: _sampler_strengthen_risk,
    2: _sampler_weaken_risk,
    3: _sampler_strengthen_revenue,
    4: _sampler_case_team_plus,
    5: _sampler_case_revenue_up,
    6: _sampler_case_risk_up,
    7: _sampler_permute_founders,
    8: _sampler_full_domain,
}


def generate_probe_pool(probe_idx: int) -> list[Input]:
    sampler = PROBE_SAMPLERS[probe_idx]
    return _make_probe_pool(probe_idx, sampler)
