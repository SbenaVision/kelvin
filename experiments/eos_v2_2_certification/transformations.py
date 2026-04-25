"""Reduced certification catalogue (M = 8 probes).

Each probe is a triple (T, R, A_c) — a transformation, a raw relation,
and an input/rule-semantic active set. Sealed.

Differences from v2.1's broader product catalogue:
  - 8 probes only (not 23).
  - Each probe carries a SINGLE relation (not per-relation rate breakdown).
  - All raw relations: no noise term, no q estimation.
  - Active subsets directly defined and used by the corpus generator
    to draw n_eff samples per probe from D(·|A_c).

The probes are committed BEFORE any v2.2 corpus is generated. Choices
informed by v2.1 prior knowledge only (per user instruction).
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from typing import Callable

from rule_grammar import Clause, parse, render
from schema import Founder, Input


# =====================================================================
# Active-set predicates (input-semantic; pure functions of x)
# =====================================================================

def _A_strengthen_risk(inp: Input) -> bool:
    return 30 < inp.case.risk_score <= 40


def _A_weaken_risk(inp: Input) -> bool:
    return 40 < inp.case.risk_score <= 50


def _A_strengthen_revenue(inp: Input) -> bool:
    return 10000 <= inp.case.revenue_monthly < 20000


def _A_case_team_plus(inp: Input) -> bool:
    return inp.case.team_size == 2


def _A_case_revenue_up(inp: Input) -> bool:
    return 5000 <= inp.case.revenue_monthly < 10000


def _A_case_risk_up(inp: Input) -> bool:
    return 21 <= inp.case.risk_score <= 40


def _A_permute_founders(inp: Input) -> bool:
    return len(inp.case.founders) >= 2


def _A_full_domain(inp: Input) -> bool:
    return True


# =====================================================================
# Transformation implementations
# =====================================================================

def _clone(inp: Input) -> Input:
    return copy.deepcopy(inp)


def _mutate_clause_value(
    clauses: list[Clause], field: str, mutator: Callable[[int], int]
) -> list[Clause]:
    out: list[Clause] = []
    mutated = False
    for c in clauses:
        if not mutated and c.field == field:
            out.append(Clause(c.field, c.op, max(0, mutator(c.value))))
            mutated = True
        else:
            out.append(c)
    return out


def _strengthen_revenue_threshold(inp: Input, rng: random.Random) -> Input:
    new_clauses = _mutate_clause_value(parse(inp.rule_text), "revenue", lambda v: v * 2)
    w = _clone(inp); w.rule_text = render(new_clauses); return w


def _strengthen_risk_threshold(inp: Input, rng: random.Random) -> Input:
    new_clauses = _mutate_clause_value(parse(inp.rule_text), "risk", lambda v: max(0, v - 10))
    w = _clone(inp); w.rule_text = render(new_clauses); return w


def _weaken_risk_threshold(inp: Input, rng: random.Random) -> Input:
    new_clauses = _mutate_clause_value(parse(inp.rule_text), "risk", lambda v: v + 10)
    w = _clone(inp); w.rule_text = render(new_clauses); return w


def _case_team_plus(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp); w.case.team_size += 1; return w


def _case_revenue_up(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp); w.case.revenue_monthly = max(1, w.case.revenue_monthly * 2); return w


def _case_risk_up(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp); w.case.risk_score = min(100, w.case.risk_score + 20); return w


def _permute_founders(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp)
    if len(w.case.founders) >= 2:
        rng.shuffle(w.case.founders)
    return w


def _replace_description(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp)
    w.case.description = f"replaced_{rng.randint(1000, 9999)}"
    return w


# =====================================================================
# Probe dataclass and catalogue
# =====================================================================

@dataclass(frozen=True)
class Probe:
    """A single certification probe = (T, R, A_c).

    Attributes:
        idx                — probe index 1..M (matches the catalogue table)
        name               — short identifier
        axis               — axis label (rule_threshold, rule_clause, case_fact, order, optional)
        relation           — "R_up" | "R_down" | "R_eq"
        expected_direction — "UP" | "DOWN" | "EQ"
        apply              — T(x): Input → Input
        active_subset      — A_c(x): Input → bool
    """
    idx: int
    name: str
    axis: str
    relation: str
    expected_direction: str
    apply: Callable[[Input, random.Random], Input]
    active_subset: Callable[[Input], bool]
    active_subset_description: str


CATALOGUE: list[Probe] = [
    Probe(
        idx=1, name="strengthen_risk_threshold", axis="rule_threshold",
        relation="R_down", expected_direction="DOWN",
        apply=_strengthen_risk_threshold, active_subset=_A_strengthen_risk,
        active_subset_description="30 < risk_score <= 40",
    ),
    Probe(
        idx=2, name="weaken_risk_threshold", axis="rule_threshold",
        relation="R_up", expected_direction="UP",
        apply=_weaken_risk_threshold, active_subset=_A_weaken_risk,
        active_subset_description="40 < risk_score <= 50",
    ),
    Probe(
        idx=3, name="strengthen_revenue_threshold", axis="rule_threshold",
        relation="R_down", expected_direction="DOWN",
        apply=_strengthen_revenue_threshold, active_subset=_A_strengthen_revenue,
        active_subset_description="10000 <= revenue_monthly < 20000",
    ),
    Probe(
        idx=4, name="case_team_plus", axis="case_fact",
        relation="R_up", expected_direction="UP",
        apply=_case_team_plus, active_subset=_A_case_team_plus,
        active_subset_description="team_size == 2",
    ),
    Probe(
        idx=5, name="case_revenue_up", axis="case_fact",
        relation="R_up", expected_direction="UP",
        apply=_case_revenue_up, active_subset=_A_case_revenue_up,
        active_subset_description="5000 <= revenue_monthly < 10000",
    ),
    Probe(
        idx=6, name="case_risk_up", axis="case_fact",
        relation="R_down", expected_direction="DOWN",
        apply=_case_risk_up, active_subset=_A_case_risk_up,
        active_subset_description="21 <= risk_score <= 40",
    ),
    Probe(
        idx=7, name="permute_founders", axis="order",
        relation="R_eq", expected_direction="EQ",
        apply=_permute_founders, active_subset=_A_permute_founders,
        active_subset_description="len(founders) >= 2",
    ),
    Probe(
        idx=8, name="replace_description", axis="optional",
        relation="R_eq", expected_direction="EQ",
        apply=_replace_description, active_subset=_A_full_domain,
        active_subset_description="X (full domain)",
    ),
]


# Sanity assertion
assert len(CATALOGUE) == 8, f"M=8 catalogue requirement violated: {len(CATALOGUE)}"
