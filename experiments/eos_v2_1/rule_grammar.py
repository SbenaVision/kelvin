"""Deterministic rule grammar.

Rule syntax (strict):
    ADVANCE IF <clause> [ AND <clause> ]*
    clause := <field> <op> <int>
    field  ∈ {revenue, team_size, risk}
    op     ∈ {>=, <=, >, <, ==}

Grammar is identical to experiments/eos/rule_grammar.py — kept here as
a sealed copy to keep the v2 catalogue self-contained.
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
    field: str
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
        clauses.append(Clause(field=m.group(1), op=m.group(2), value=int(m.group(3))))
    return clauses


def render(clauses: list[Clause]) -> str:
    if not clauses:
        return _HEADER.rstrip()
    return _HEADER + " AND ".join(c.render() for c in clauses)


def default_rule() -> str:
    return "ADVANCE IF revenue >= 10000 AND team_size >= 3 AND risk <= 40"
