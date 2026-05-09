"""Typed schema with role annotations per thesis §3.

The input X = Input(case, rule_text). Each Case field carries a role
annotation; rule_text is itself the `rule_text` role. The role drives
the 4-way axis classification in `axis_classifier.py`.

Roles used by this experiment:
- causal_field:         the pipeline SHOULD read this (rule-referenced).
- order_irrelevant_list: a list field whose order SHOULD NOT matter.
- optional_field:        the pipeline SHOULD NOT need this for correctness.
- rule_text:             the governing rule string.
- threshold_field:       a numeric value WITHIN rule_text.
- rule_clause:           a logical clause WITHIN rule_text.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Role(str, Enum):
    CAUSAL_FIELD = "causal_field"
    ORDER_IRRELEVANT_LIST = "order_irrelevant_list"
    OPTIONAL_FIELD = "optional_field"
    RULE_TEXT = "rule_text"


# Per-field schema role annotations.
# For this experiment, the rule grammar references revenue, team_size,
# and risk. So those are CAUSAL_FIELD. All others are OPTIONAL relative
# to the rule, or ORDER_IRRELEVANT for list-typed fields.
FIELD_ROLES: dict[str, Role] = {
    "revenue_monthly": Role.CAUSAL_FIELD,
    "team_size":       Role.CAUSAL_FIELD,
    "risk_score":      Role.CAUSAL_FIELD,
    "stage":           Role.OPTIONAL_FIELD,
    "founders":        Role.ORDER_IRRELEVANT_LIST,
    "risks":           Role.ORDER_IRRELEVANT_LIST,
    "description":     Role.OPTIONAL_FIELD,
    "rule_text":       Role.RULE_TEXT,
}


@dataclass
class Founder:
    name: str
    experience_years: int


@dataclass
class Case:
    revenue_monthly: int
    team_size: int
    risk_score: int              # 0 (best) .. 100 (worst)
    stage: str
    founders: list[Founder]
    risks: list[str]
    description: str = ""


@dataclass
class Input:
    case: Case
    rule_text: str


# Decision threshold on scalar output. Used by R_sign_eq and by
# "derived binary decision" reporting. Scores in [20, 80] by design;
# 50 sits mid-range.
DECISION_THRESHOLD: int = 50


# --- Axis taxonomy ------------------------------------------------------
# Each transformation is assigned to exactly one axis. Axes have
# a "causal_status" declared by the schema, which drives the 4-way
# classifier per thesis §7.
#
#   causal_status = "non_causal": schema says axis SHOULD NOT affect output
#   causal_status = "rule_bearing": schema says axis SHOULD affect output
#                                   *when* the pipeline tracks the rule
#   causal_status = "causal":       schema says axis SHOULD affect output
#                                   regardless of rule-reading strategy
#                                   (e.g., revenue affects f_ruleblind too)

class AxisStatus(str, Enum):
    NON_CAUSAL = "non_causal"
    RULE_BEARING = "rule_bearing"
    CAUSAL = "causal"


AXIS_STATUS: dict[str, AxisStatus] = {
    "order":           AxisStatus.NON_CAUSAL,
    "optional":        AxisStatus.NON_CAUSAL,
    "rule_threshold":  AxisStatus.RULE_BEARING,
    "rule_clause":     AxisStatus.RULE_BEARING,
    "case_fact":       AxisStatus.CAUSAL,
    "non_rule_fact":   AxisStatus.NON_CAUSAL,   # case fields NOT in rule
    "identity":        AxisStatus.NON_CAUSAL,   # sanity axis
}
