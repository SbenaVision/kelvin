"""Deterministic rule grammar.

Rule syntax (strict):
    ADVANCE IF <clause> [ AND <clause> ]*
    clause := <field> <op> <int>
    field  ∈ {revenue, team_size, risk}
    op     ∈ {>=, <=, >, <, ==}

Fields map to Case attributes:
    revenue    → case.revenue_monthly
    team_size  → case.team_size
    risk       → case.risk_score

The parser is deterministic: the same string always yields the same
clause list in the same order. Parsing failures raise ValueError
(the pipelines expect well-formed rule text; malformed rules are a
bug, not a domain condition).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from schema import Case


FIELD_MAP: dict[str, str] = {
    "revenue":   "revenue_monthly",
    "team_size": "team_size",
    "risk":      "risk_score",
}

VALID_FIELDS = tuple(FIELD_MAP.keys())
VALID_OPS = (">=", "<=", ">", "<", "==")


@dataclass(frozen=True)
class Clause:
    field: str     # rule-language field name (e.g., "revenue")
    op: str
    value: int

    def render(self) -> str:
        return f"{self.field} {self.op} {self.value}"

    def eval_on(self, case: Case) -> bool:
        attr = FIELD_MAP[self.field]
        x = getattr(case, attr)
        if self.op == ">=": return x >= self.value
        if self.op == "<=": return x <= self.value
        if self.op == ">":  return x > self.value
        if self.op == "<":  return x < self.value
        if self.op == "==": return x == self.value
        raise ValueError(f"unknown op: {self.op}")


_HEADER = "ADVANCE IF "
# Ordering of alternation in op group is longest-first to avoid
# "<" matching before "<=".
_CLAUSE_RE = re.compile(
    r"^\s*(revenue|team_size|risk)\s*(>=|<=|==|>|<)\s*(-?\d+)\s*$"
)


def parse(rule_text: str) -> list[Clause]:
    if not rule_text.startswith(_HEADER):
        raise ValueError(f"rule must start with '{_HEADER}': {rule_text!r}")
    body = rule_text[len(_HEADER):].strip()
    if body.endswith("."):
        body = body[:-1].rstrip()
    if not body:
        return []
    parts = [p.strip() for p in body.split(" AND ")]
    clauses: list[Clause] = []
    for p in parts:
        m = _CLAUSE_RE.match(p)
        if not m:
            raise ValueError(f"malformed clause: {p!r}")
        field, op, val = m.group(1), m.group(2), int(m.group(3))
        clauses.append(Clause(field=field, op=op, value=val))
    return clauses


def render(clauses: list[Clause]) -> str:
    if not clauses:
        return _HEADER.rstrip()
    return _HEADER + " AND ".join(c.render() for c in clauses)


def default_rule() -> str:
    """The single rule used across the entire corpus."""
    return "ADVANCE IF revenue >= 10000 AND team_size >= 3 AND risk <= 40"
