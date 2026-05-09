"""Four pipelines for the EOS experiment.

All four have signature f: Input → int, with score ∈ [20, 80]. The
decision threshold (DECISION_THRESHOLD = 50) turns score into a binary
decision for R_sign_eq evaluation.

- f_track:     reads rule text AND case. Score = 20 + 60 * (passed / total).
- f_ruleblind: reads case only, IGNORES rule_text. Heuristic based on
               revenue and team_size.
- f_constant:  returns a fixed score (50), ignoring everything.
- f_wrongrule: reads rule text but INVERTS the comparator on the last
               clause (consistent adversary — not stochastic). This is
               a sharper adversary than f_ruleblind: it reads the rule
               but tracks it *incorrectly*.

The pipelines are deterministic — no RNG use. They also do not raise
on malformed rules in f_ruleblind / f_constant (they simply ignore it).
f_track and f_wrongrule will raise if the rule fails to parse; that
indicates a transformation bug, which is a test failure, not a domain
condition.
"""
from __future__ import annotations

from rule_grammar import Clause, parse
from schema import DECISION_THRESHOLD, Input


def _score_from_passed(passed: int, total: int) -> int:
    if total == 0:
        return 50  # no rule → neutral
    return int(round(20 + 60 * (passed / total)))


def f_track(inp: Input) -> int:
    """Reads the rule; evaluates every clause correctly."""
    clauses = parse(inp.rule_text)
    passed = sum(c.eval_on(inp.case) for c in clauses)
    return _score_from_passed(passed, len(clauses))


def _invert_op(op: str) -> str:
    return {">=": "<", "<=": ">", ">": "<=", "<": ">=", "==": "=="}[op]


def f_wrongrule(inp: Input) -> int:
    """Reads the rule but inverts the comparator on the last clause.

    Deterministic adversary: same input → same output. Differentiates
    from f_ruleblind because it *does* respond to rule-text changes,
    but in partially-wrong ways. Differentiates from f_track because
    the last-clause comparator is flipped.
    """
    clauses = parse(inp.rule_text)
    if not clauses:
        return 50
    tweaked: list[Clause] = list(clauses[:-1])
    last = clauses[-1]
    tweaked.append(Clause(field=last.field, op=_invert_op(last.op), value=last.value))
    passed = sum(c.eval_on(inp.case) for c in tweaked)
    return _score_from_passed(passed, len(tweaked))


def f_ruleblind(inp: Input) -> int:
    """Ignores the rule; responds to case facts via a fixed heuristic.

    Heuristic: score = clamp(20 + rev_bonus + team_bonus, 20, 80)
      rev_bonus  = min(40, revenue_monthly // 500)     # caps at revenue=20000
      team_bonus = min(20, team_size * 3)               # caps at team=6+
    Risk is NOT used — so this pipeline is blind to the risk clause too.
    """
    c = inp.case
    rev_bonus = min(40, c.revenue_monthly // 500)
    team_bonus = min(20, c.team_size * 3)
    return max(20, min(80, 20 + rev_bonus + team_bonus))


def f_constant(inp: Input) -> int:
    return 50


PIPELINES: dict[str, callable] = {
    "f_track":     f_track,
    "f_wrongrule": f_wrongrule,
    "f_ruleblind": f_ruleblind,
    "f_constant":  f_constant,
}
