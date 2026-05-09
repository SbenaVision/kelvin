"""Transformation catalogue.

Each transformation carries:
- name:  unique id, used for logging and signature tables.
- axis:  which of the thesis axes it belongs to (drives classification).
- apply: deterministic function Input → Input. Transformations must be
         validity-preserving (T(x) ∈ X) per thesis §3.

The catalogue is hand-enumerated from schema role annotations, per
thesis §5 procedure step 1. In a production Kelvin, the catalogue
would be generated from the schema; here we enumerate directly for
clarity and to match the thesis's axis taxonomy precisely.

Identity T is INCLUDED in the catalogue for sanity control, but will
be excluded from discovered signatures (see run.py).
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from typing import Callable

from rule_grammar import Clause, parse, render
from schema import Founder, Input


@dataclass(frozen=True)
class Transform:
    name: str
    axis: str
    apply: Callable[[Input, random.Random], Input]
    is_identity: bool = False


def _clone(inp: Input) -> Input:
    return copy.deepcopy(inp)


# =====================================================================
# Axis: identity (sanity control; excluded from signatures)
# =====================================================================

def _identity(inp: Input, rng: random.Random) -> Input:
    return _clone(inp)


# =====================================================================
# Axis: order (order-irrelevant lists)
# =====================================================================

def _permute_founders(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp)
    if len(w.case.founders) >= 2:
        rng.shuffle(w.case.founders)
    return w


def _permute_risks(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp)
    if len(w.case.risks) >= 2:
        rng.shuffle(w.case.risks)
    return w


# =====================================================================
# Axis: optional (schema-declared non-causal)
# =====================================================================

def _replace_description(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp)
    w.case.description = f"replaced_{rng.randint(1000, 9999)}"
    return w


def _blank_description(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp)
    w.case.description = ""
    return w


# =====================================================================
# Axis: non_rule_fact (case fields NOT referenced by rule)
# =====================================================================

def _add_risk_item(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp)
    w.case.risks.append(f"synth_risk_{rng.randint(1000, 9999)}")
    return w


def _drop_risk_item(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp)
    if w.case.risks:
        w.case.risks.pop()
    return w


def _bump_founder_experience(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp)
    for f in w.case.founders:
        f.experience_years += 5
    return w


# =====================================================================
# Axis: rule_threshold (modify numeric value inside rule_text)
# =====================================================================

def _mutate_clause_value(
    clauses: list[Clause], field: str, mutator: Callable[[int], int]
) -> list[Clause]:
    out: list[Clause] = []
    mutated = False
    for c in clauses:
        if not mutated and c.field == field:
            out.append(Clause(field=c.field, op=c.op, value=max(0, mutator(c.value))))
            mutated = True
        else:
            out.append(c)
    return out


def _strengthen_revenue_threshold(inp: Input, rng: random.Random) -> Input:
    # revenue >= N  →  revenue >= 2*N (stricter; fewer cases pass)
    clauses = parse(inp.rule_text)
    new_clauses = _mutate_clause_value(clauses, "revenue", lambda v: v * 2)
    w = _clone(inp)
    w.rule_text = render(new_clauses)
    return w


def _weaken_revenue_threshold(inp: Input, rng: random.Random) -> Input:
    clauses = parse(inp.rule_text)
    new_clauses = _mutate_clause_value(clauses, "revenue", lambda v: v // 2)
    w = _clone(inp)
    w.rule_text = render(new_clauses)
    return w


def _strengthen_team_threshold(inp: Input, rng: random.Random) -> Input:
    # team_size >= N → team_size >= N+2 (stricter)
    clauses = parse(inp.rule_text)
    new_clauses = _mutate_clause_value(clauses, "team_size", lambda v: v + 2)
    w = _clone(inp)
    w.rule_text = render(new_clauses)
    return w


def _weaken_team_threshold(inp: Input, rng: random.Random) -> Input:
    clauses = parse(inp.rule_text)
    new_clauses = _mutate_clause_value(clauses, "team_size", lambda v: max(0, v - 1))
    w = _clone(inp)
    w.rule_text = render(new_clauses)
    return w


def _strengthen_risk_threshold(inp: Input, rng: random.Random) -> Input:
    # risk <= N → risk <= N-10 (stricter; fewer low-risk cases pass)
    clauses = parse(inp.rule_text)
    new_clauses = _mutate_clause_value(clauses, "risk", lambda v: max(0, v - 10))
    w = _clone(inp)
    w.rule_text = render(new_clauses)
    return w


def _weaken_risk_threshold(inp: Input, rng: random.Random) -> Input:
    clauses = parse(inp.rule_text)
    new_clauses = _mutate_clause_value(clauses, "risk", lambda v: v + 20)
    w = _clone(inp)
    w.rule_text = render(new_clauses)
    return w


# =====================================================================
# Axis: rule_clause (add / remove a whole clause)
# =====================================================================

def _add_strict_clause(inp: Input, rng: random.Random) -> Input:
    # Append a strict team_size clause that fails for small teams.
    clauses = parse(inp.rule_text)
    clauses.append(Clause(field="team_size", op=">=", value=10))
    w = _clone(inp)
    w.rule_text = render(clauses)
    return w


def _remove_last_clause(inp: Input, rng: random.Random) -> Input:
    clauses = parse(inp.rule_text)
    if len(clauses) > 1:
        clauses = clauses[:-1]
    w = _clone(inp)
    w.rule_text = render(clauses)
    return w


# =====================================================================
# Axis: case_fact (rule-referenced case fields)
# =====================================================================

def _case_revenue_up(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp)
    w.case.revenue_monthly = max(1, w.case.revenue_monthly * 2)
    return w


def _case_revenue_down(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp)
    w.case.revenue_monthly = w.case.revenue_monthly // 2
    return w


def _case_team_plus(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp)
    w.case.team_size += 1
    return w


def _case_team_minus(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp)
    w.case.team_size = max(1, w.case.team_size - 1)
    return w


def _case_risk_up(inp: Input, rng: random.Random) -> Input:
    # risk_score up = WORSE
    w = _clone(inp)
    w.case.risk_score = min(100, w.case.risk_score + 20)
    return w


def _case_risk_down(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp)
    w.case.risk_score = max(0, w.case.risk_score - 20)
    return w


# =====================================================================
# Catalogue
# =====================================================================

CATALOGUE: list[Transform] = [
    # Identity (sanity; excluded from signatures)
    Transform("identity",                     "identity",        _identity, is_identity=True),

    # Order
    Transform("permute_founders",             "order",           _permute_founders),
    Transform("permute_risks",                "order",           _permute_risks),

    # Optional
    Transform("replace_description",          "optional",        _replace_description),
    Transform("blank_description",            "optional",        _blank_description),

    # Non-rule fact (risks list, founder experience — fields not in rule)
    Transform("add_risk_item",                "non_rule_fact",   _add_risk_item),
    Transform("drop_risk_item",               "non_rule_fact",   _drop_risk_item),
    Transform("bump_founder_experience",      "non_rule_fact",   _bump_founder_experience),

    # Rule threshold
    Transform("strengthen_revenue_threshold", "rule_threshold",  _strengthen_revenue_threshold),
    Transform("weaken_revenue_threshold",     "rule_threshold",  _weaken_revenue_threshold),
    Transform("strengthen_team_threshold",    "rule_threshold",  _strengthen_team_threshold),
    Transform("weaken_team_threshold",        "rule_threshold",  _weaken_team_threshold),
    Transform("strengthen_risk_threshold",    "rule_threshold",  _strengthen_risk_threshold),
    Transform("weaken_risk_threshold",        "rule_threshold",  _weaken_risk_threshold),

    # Rule clause
    Transform("add_strict_clause",            "rule_clause",     _add_strict_clause),
    Transform("remove_last_clause",           "rule_clause",     _remove_last_clause),

    # Case fact (rule-referenced fields)
    Transform("case_revenue_up",              "case_fact",       _case_revenue_up),
    Transform("case_revenue_down",            "case_fact",       _case_revenue_down),
    Transform("case_team_plus",               "case_fact",       _case_team_plus),
    Transform("case_team_minus",              "case_fact",       _case_team_minus),
    Transform("case_risk_up",                 "case_fact",       _case_risk_up),
    Transform("case_risk_down",               "case_fact",       _case_risk_down),
]
