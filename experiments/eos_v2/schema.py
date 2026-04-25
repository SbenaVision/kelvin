"""Typed schema with role annotations.

This is the Envelop-LIKE local structured-decision schema used for the
EOS v2 experiment. It is NOT the production Envelop system. The
parallel: same domain (venture-style structured decisions with a
governing rule over numeric facts), same role taxonomy, but the
pipeline is local Python, not an LLM-backed remote service.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    CAUSAL_FIELD = "causal_field"
    ORDER_IRRELEVANT_LIST = "order_irrelevant_list"
    OPTIONAL_FIELD = "optional_field"
    RULE_TEXT = "rule_text"


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
    risk_score: int                 # 0 (best) .. 100 (worst)
    stage: str
    founders: list[Founder]
    risks: list[str]
    description: str = ""
    case_id: int = -1               # used to seed per-case replay RNGs


@dataclass
class Input:
    case: Case
    rule_text: str


# --- Axis taxonomy ------------------------------------------------------
class AxisStatus(str, Enum):
    NON_CAUSAL = "non_causal"
    RULE_BEARING = "rule_bearing"
    CAUSAL = "causal"


AXIS_STATUS: dict[str, AxisStatus] = {
    "order":           AxisStatus.NON_CAUSAL,
    "optional":        AxisStatus.NON_CAUSAL,
    "non_rule_fact":   AxisStatus.NON_CAUSAL,
    "rule_threshold":  AxisStatus.RULE_BEARING,
    "rule_clause":     AxisStatus.RULE_BEARING,
    "case_fact":       AxisStatus.CAUSAL,
    "identity":        AxisStatus.NON_CAUSAL,   # sanity axis
}
