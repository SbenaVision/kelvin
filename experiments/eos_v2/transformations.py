"""Transformation catalogue (sealed).

Same axes as eos v1 plus an explicit `is_applicable` predicate so that
non-applicable cases are dropped from per-pair statistics rather than
silently counted as holds.

All transformations satisfy the noise-transfer assumption (plan §7.1):
they are prompt-structure / length preserving — none changes the rule
text by more than one clause or perturbs the case schema shape.
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
    is_applicable: Callable[[Input], bool]
    is_identity: bool = False


def _clone(inp: Input) -> Input:
    return copy.deepcopy(inp)


def _always(inp: Input) -> bool:
    return True


# =====================================================================
# Identity
# =====================================================================

def _identity(inp: Input, rng: random.Random) -> Input:
    return _clone(inp)


# =====================================================================
# Order
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


def _founders_perm_applicable(inp: Input) -> bool:
    return len(inp.case.founders) >= 2


def _risks_perm_applicable(inp: Input) -> bool:
    return len(inp.case.risks) >= 2


# =====================================================================
# Optional
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
# Non-rule fact
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


def _drop_risk_applicable(inp: Input) -> bool:
    return len(inp.case.risks) >= 1


def _bump_founder_experience(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp)
    for f in w.case.founders:
        f.experience_years += 5
    return w


# =====================================================================
# Rule threshold
# =====================================================================

def _mutate_clause_value(
    clauses: list[Clause], field: str, mutator: Callable[[int], int]
) -> tuple[list[Clause], bool]:
    out: list[Clause] = []
    mutated = False
    for c in clauses:
        if not mutated and c.field == field:
            out.append(Clause(c.field, c.op, max(0, mutator(c.value))))
            mutated = True
        else:
            out.append(c)
    return out, mutated


def _has_clause_with_field(rule_text: str, field: str) -> bool:
    return any(c.field == field for c in parse(rule_text))


def _make_threshold_t(field: str, mutator: Callable[[int], int]) -> Callable:
    def _apply(inp: Input, rng: random.Random) -> Input:
        clauses = parse(inp.rule_text)
        new_clauses, _ = _mutate_clause_value(clauses, field, mutator)
        w = _clone(inp)
        w.rule_text = render(new_clauses)
        return w
    return _apply


def _make_threshold_applicable(field: str) -> Callable[[Input], bool]:
    def _ok(inp: Input) -> bool:
        return _has_clause_with_field(inp.rule_text, field)
    return _ok


# =====================================================================
# Rule clause
# =====================================================================

def _add_strict_clause(inp: Input, rng: random.Random) -> Input:
    clauses = parse(inp.rule_text)
    clauses.append(Clause("team_size", ">=", 10))
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


def _remove_last_applicable(inp: Input) -> bool:
    return len(parse(inp.rule_text)) >= 2


# =====================================================================
# Case fact (rule-referenced)
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
    Transform("identity", "identity", _identity, _always, is_identity=True),

    Transform("permute_founders", "order", _permute_founders, _founders_perm_applicable),
    Transform("permute_risks",    "order", _permute_risks,    _risks_perm_applicable),

    Transform("replace_description", "optional", _replace_description, _always),
    Transform("blank_description",   "optional", _blank_description,   _always),

    Transform("add_risk_item",           "non_rule_fact", _add_risk_item,           _always),
    Transform("drop_risk_item",          "non_rule_fact", _drop_risk_item,          _drop_risk_applicable),
    Transform("bump_founder_experience", "non_rule_fact", _bump_founder_experience, _always),

    Transform("strengthen_revenue_threshold",
              "rule_threshold",
              _make_threshold_t("revenue", lambda v: v * 2),
              _make_threshold_applicable("revenue")),
    Transform("weaken_revenue_threshold",
              "rule_threshold",
              _make_threshold_t("revenue", lambda v: v // 2),
              _make_threshold_applicable("revenue")),
    Transform("strengthen_team_threshold",
              "rule_threshold",
              _make_threshold_t("team_size", lambda v: v + 2),
              _make_threshold_applicable("team_size")),
    Transform("weaken_team_threshold",
              "rule_threshold",
              _make_threshold_t("team_size", lambda v: max(0, v - 1)),
              _make_threshold_applicable("team_size")),
    Transform("strengthen_risk_threshold",
              "rule_threshold",
              _make_threshold_t("risk", lambda v: max(0, v - 10)),
              _make_threshold_applicable("risk")),
    Transform("weaken_risk_threshold",
              "rule_threshold",
              _make_threshold_t("risk", lambda v: v + 20),
              _make_threshold_applicable("risk")),

    Transform("add_strict_clause",  "rule_clause", _add_strict_clause,  _always),
    Transform("remove_last_clause", "rule_clause", _remove_last_clause, _remove_last_applicable),

    Transform("case_revenue_up",   "case_fact", _case_revenue_up,   _always),
    Transform("case_revenue_down", "case_fact", _case_revenue_down, _always),
    Transform("case_team_plus",    "case_fact", _case_team_plus,    _always),
    Transform("case_team_minus",   "case_fact", _case_team_minus,   _always),
    Transform("case_risk_up",      "case_fact", _case_risk_up,      _always),
    Transform("case_risk_down",    "case_fact", _case_risk_down,    _always),
]


# Map T name → predicted direction on f_track for the directional relation.
# Used by the axis classifier to decide responsive-CORRECT vs responsive-WRONG.
# UP   means R^Ω_↑ predicted (score non-decrease).
# DOWN means R^Ω_↓ predicted (score non-increase).
# EQ   means R^Ω_eq predicted (invariance).
# NONE means no clean prediction.
PREDICTED_DIRECTION: dict[str, str] = {
    "identity": "EQ",

    "permute_founders": "EQ",
    "permute_risks":    "EQ",

    "replace_description": "EQ",
    "blank_description":   "EQ",

    "add_risk_item":           "EQ",
    "drop_risk_item":          "EQ",
    "bump_founder_experience": "EQ",

    "strengthen_revenue_threshold": "DOWN",
    "weaken_revenue_threshold":     "UP",
    "strengthen_team_threshold":    "DOWN",
    "weaken_team_threshold":        "UP",
    "strengthen_risk_threshold":    "DOWN",
    "weaken_risk_threshold":        "UP",

    "add_strict_clause":  "DOWN",
    "remove_last_clause": "NONE",  # ratio-scoring breaks monotonicity

    "case_revenue_up":   "UP",
    "case_revenue_down": "DOWN",
    "case_team_plus":    "UP",
    "case_team_minus":   "DOWN",
    "case_risk_up":      "DOWN",   # higher risk → score down (rule-bearing)
    "case_risk_down":    "UP",
}
