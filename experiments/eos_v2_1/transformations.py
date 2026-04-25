"""Transformation catalogue (sealed) — with pre-specified active subsets A_T.

Per v2.1 spec §1: for each sensitivity transformation T, A_T(x) is
defined from rule semantics on the BASELINE input — never from observed
output effects on f(x), f(Tx). The same A_T is used for every pipeline.

Active subset semantics (verified against rule_grammar):

  rule "risk_score <= τ":
    strengthen τ → τ−d   ⇒  A_T = {x : τ−d < risk_score(x) ≤ τ}, expected DOWN
    weaken     τ → τ+d   ⇒  A_T = {x : τ < risk_score(x) ≤ τ+d}, expected UP

  rule "revenue >= τ":
    strengthen τ → τ·k   ⇒  A_T = {x : τ ≤ revenue(x) < τ·k},     expected DOWN
    weaken     τ → τ/k   ⇒  A_T = {x : τ/k ≤ revenue(x) < τ},     expected UP

  rule "team_size >= τ":
    strengthen τ → τ+d   ⇒  A_T = {x : τ ≤ team_size(x) < τ+d},   expected DOWN
    weaken     τ → τ−d   ⇒  A_T = {x : τ−d ≤ team_size(x) < τ},   expected UP

For case-fact transformations (modify x, not the rule), A_T is the set
of cases whose rule-clause membership flips after applying T:

  case_revenue_up: A_T = {x : revenue(x) < 10000 AND 2·revenue(x) ≥ 10000}
                         = {x : 5000 ≤ revenue(x) < 10000}, expected UP
  case_revenue_down (÷2): symmetric, expected DOWN
  case_team_plus  (+1):   A_T = {x : team(x) = 2}, expected UP
  case_team_minus (−1):   A_T = {x : team(x) = 3}, expected DOWN
  case_risk_up   (+20):   A_T = {x : 21 ≤ risk(x) ≤ 40}, expected DOWN
  case_risk_down (−20):   A_T = {x : 41 ≤ risk(x) ≤ 60}, expected UP

For invariance transformations (order, optional, non_rule_fact, identity),
A_T is the full applicable set (filtered only by is_applicable). The
sensitivity_kind attribute drives whether A_T-evaluation runs.

BORDERLINE TRANSFORMATION:

  add_passing_clause: appends "team_size >= 1" — always passes, since
    every case has team_size ≥ 1 by corpus design.

  Predicted score effect on f_track:
    Let p_old = number of original-rule clauses passing for x,
        n_old = original clause count (3 by default rule).
    After T: rule has n_old+1 clauses; new clause always passes.
    score_old = 20 + 60·p_old/n_old
    score_new = 20 + 60·(p_old+1)/(n_old+1)
    effect    = 60·((p_old+1)/(n_old+1) − p_old/n_old)
              = 60·(n_old − p_old) / (n_old·(n_old+1))

    For n_old = 3:
      p_old=0 → +15   (outside divergence zone, effect > q+Δ_dir)
      p_old=1 → +10   (outside zone)
      p_old=2 →  +5   (IN divergence zone [Δ_naive=4, q+Δ_dir≈7))
      p_old=3 →   0   (no flip; outside zone — invariant)

  ACTIVE SUBSET A_T_borderline = {x : exactly 2 of 3 default-rule
    clauses pass for x}. On this subset, the deterministic effect is
    exactly +5 score points.

  --- Divergence-zone math (with empirical-q correction) ---

  Notation: D := jitter₂ − jitter₁ (a single draw under the sealed
  jitter model: P(jitter=0)=0.88, P(jitter=k)=0.02 for k ∈ {-3..-1,1..3}).
  Exact distribution of D, computed from the joint:
      P(D = 0)  = 0.7768
      P(D = ±1) = 0.0368
      P(D = ±2) = 0.0364
      P(D = ±3) = 0.0360
      P(D = ±4) = 0.0012
      P(D = ±5) = 0.0008
      P(D = ±6) = 0.0004

  Naive threshold (Δ_naive = 2, sealed in config):
      Naive R_↑ holds  ⇔  5 + D ≥ 2  ⇔  D ≥ −3
      P(D ≥ −3) = 0.0360 + 0.0364 + 0.0368 + 0.7768
                + 0.0368 + 0.0364 + 0.0360 + 0.0012 + 0.0008 + 0.0004
                = 0.9976
  Naive acceptance is therefore near-certain on A_T_borderline,
  independent of q.

  Omega threshold (q_0.95(x) + Δ_dir, with Δ_dir = 4):
  q_0.95(x) is empirically estimated from K = 20 baseline replays via
  the K(K-1)/2 = 190 pairwise-difference 95th percentile. Under the
  sealed jitter model, q is NOT always 3 — its distribution is
  approximately:

      Pr[k jittered replays] ~ Binomial(K=20, p_noise=0.12)
      Conditional on k:
        k=0  (≈ 7.8% of cases) :  all 190 pairs are 0  ⇒  q = 0
        k=1  (≈ 21.1%)         :  171 zeros + 19 nonzeros in {1,2,3};
                                   q = 95th percentile of the 19,
                                   ≈ 1, 2, or 3 depending on |jitter|
        k=2  (≈ 27.3%)         :  153 zeros + 36 one-jittered + 1
                                   both-jittered; q ≈ 3 typically
        k≥3  (≈ 43.7%)         :  q ≈ 3 typically (could spike higher
                                   only if both-jittered diffs > 3
                                   crowd into the 95th percentile band)

  Per-case omega R^Ω_↑ holds  ⇔  5 + D ≥ q + 4  ⇔  D ≥ q − 1.
      If q = 0 :  P(D ≥ −1) = 0.9252
      If q = 1 :  P(D ≥  0) = 0.8884
      If q = 2 :  P(D ≥  1) = 0.1116
      If q = 3 :  P(D ≥  2) = 0.0748
      If q = 4 :  P(D ≥  3) = 0.0384
      If q ≥ 5 :  P(D ≥ ≥4) ≤ 0.0024

  The empirical-q-weighted rate depends on the realized q distribution
  per draw and per pipeline; the run reports it as a histogram (see
  results.md). Even under a worst-case mix (e.g., 10% of cases get
  q=0, contributing ~0.092 alone) the unconditional omega rate stays
  well below 0.40 — far below the 0.90 acceptance threshold under
  CP_LCB at α = δ/m = 6.494e-04.

  Conditional reference points (cited in results.md):
    (1) If q = 3 (the v2 median observation):
        P(D ≥ 2) = 0.0748
        Expected omega_count ≈ 12 / 164 — rejects.
    (2) Empirical-q calculation (from the actual run's q histogram):
        Reported in results.md as `omega_correct_rate (empirical)`.
    (3) Expected omega-reject still holds: empirical rate is far below
        the 90% acceptance threshold even when q is small.

  This is the engineered c7 signal: naive accepts on f_track over
  A_T_borderline (CP_LCB at α=0.05 ≥ 0.90); omega rejects on the same
  data (CP_LCB at α=6.494e-04 < 0.90).

For the wrong-direction adversary (f_wrongstatic): borderline-T is
NOT specifically about the corrupted clause, so its directional rate
on f_wrongstatic is not pre-specified. It will be reported but isn't
part of c3.
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from typing import Callable

from rule_grammar import Clause, default_rule, parse, render
from schema import Founder, Input


# =====================================================================
# Active-subset predicates (depend on input; computed from rule semantics)
# =====================================================================

def _A_strengthen_revenue(inp: Input) -> bool:
    # rule rev >= τ; strengthen ×2: A = [τ, 2τ).
    for c in parse(inp.rule_text):
        if c.field == "revenue":
            return c.value <= inp.case.revenue_monthly < 2 * c.value
    return False


def _A_weaken_revenue(inp: Input) -> bool:
    # weaken /2: A = [τ/2, τ).
    for c in parse(inp.rule_text):
        if c.field == "revenue":
            return c.value // 2 <= inp.case.revenue_monthly < c.value
    return False


def _A_strengthen_team(inp: Input) -> bool:
    # strengthen +2: A = [τ, τ+2).
    for c in parse(inp.rule_text):
        if c.field == "team_size":
            return c.value <= inp.case.team_size < c.value + 2
    return False


def _A_weaken_team(inp: Input) -> bool:
    # weaken −1: A = [τ−1, τ).
    for c in parse(inp.rule_text):
        if c.field == "team_size":
            return max(0, c.value - 1) <= inp.case.team_size < c.value
    return False


def _A_strengthen_risk(inp: Input) -> bool:
    # rule risk <= τ; strengthen −10: A = (τ−10, τ].
    for c in parse(inp.rule_text):
        if c.field == "risk":
            return c.value - 10 < inp.case.risk_score <= c.value
    return False


def _A_weaken_risk(inp: Input) -> bool:
    # weaken +10: A = (τ, τ+10].
    for c in parse(inp.rule_text):
        if c.field == "risk":
            return c.value < inp.case.risk_score <= c.value + 10
    return False


def _A_case_revenue_up(inp: Input) -> bool:
    # T: rev → 2·rev. Active iff doubling crosses some "rev >= τ" clause.
    for c in parse(inp.rule_text):
        if c.field == "revenue":
            r = inp.case.revenue_monthly
            return r < c.value and 2 * r >= c.value
    return False


def _A_case_revenue_down(inp: Input) -> bool:
    for c in parse(inp.rule_text):
        if c.field == "revenue":
            r = inp.case.revenue_monthly
            return r >= c.value and r // 2 < c.value
    return False


def _A_case_team_plus(inp: Input) -> bool:
    for c in parse(inp.rule_text):
        if c.field == "team_size":
            t = inp.case.team_size
            return t < c.value and t + 1 >= c.value
    return False


def _A_case_team_minus(inp: Input) -> bool:
    for c in parse(inp.rule_text):
        if c.field == "team_size":
            t = inp.case.team_size
            return t >= c.value and max(1, t - 1) < c.value
    return False


def _A_case_risk_up(inp: Input) -> bool:
    for c in parse(inp.rule_text):
        if c.field == "risk":
            r = inp.case.risk_score
            return r <= c.value and min(100, r + 20) > c.value
    return False


def _A_case_risk_down(inp: Input) -> bool:
    for c in parse(inp.rule_text):
        if c.field == "risk":
            r = inp.case.risk_score
            return r > c.value and max(0, r - 20) <= c.value
    return False


def _A_add_strict_clause(inp: Input) -> bool:
    """Active iff:
       (a) the added strict clause "team_size >= 10" FAILS for x
           (i.e., team_size(x) < 10), AND
       (b) at least one EXISTING clause passes for x.

    Rationale: if no existing clause passes, score was already 20
    and adding a failing clause keeps it at the floor (no genuine
    "down" perturbation observable). Restricting to (b) ensures the
    added clause has a measurable downward effect on score.
    """
    if inp.case.team_size >= 10:
        return False  # added clause passes — no perturbation
    existing = parse(inp.rule_text)
    return any(c.eval_on(inp.case) for c in existing)


def _A_remove_last_clause(inp: Input) -> bool:
    """Active iff:
       (a) the removed last clause FAILS for x
           (i.e., removing it benefits x; if it was passing, removal
           reduces the passed/total ratio and the predicted UP direction
           does not necessarily hold), AND
       (b) at least one REMAINING clause passes for x.

    Rationale: if no remaining clause passes, score is dominated by
    score floor and the "up" effect is degenerate.
    """
    clauses = parse(inp.rule_text)
    if len(clauses) < 2:
        return False
    last = clauses[-1]
    if last.eval_on(inp.case):
        return False  # removed clause was passing — removal would reduce ratio
    remaining = clauses[:-1]
    return any(c.eval_on(inp.case) for c in remaining)


def _A_borderline_add_passing(inp: Input) -> bool:
    """Active iff exactly 2 of 3 (or n−1 of n in general) clauses pass.

    This is the input-semantic definition of the divergence-zone subset
    for the borderline transformation. On this subset, score effect
    is deterministically +60·(n − p_old)/(n·(n+1)) = +5 for n=3, p_old=2.
    """
    clauses = parse(inp.rule_text)
    if not clauses:
        return False
    p = sum(c.eval_on(inp.case) for c in clauses)
    n = len(clauses)
    return p == n - 1   # exactly one clause failing


# =====================================================================
# Transform dataclass + helpers
# =====================================================================

@dataclass(frozen=True)
class Transform:
    name: str
    axis: str
    apply: Callable[[Input, random.Random], Input]
    is_applicable: Callable[[Input], bool]
    sensitivity_kind: str             # "directional" | "invariance"
    expected_direction: str           # "UP" | "DOWN" | "EQ"
    active_subset: Callable[[Input], bool] | None
    is_identity: bool = False
    is_borderline: bool = False


def _clone(inp: Input) -> Input:
    return copy.deepcopy(inp)


def _always(inp: Input) -> bool:
    return True


# =====================================================================
# Identity (sanity)
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
# Rule threshold (sensitivity / directional)
# =====================================================================

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


def _make_threshold_apply(field: str, mutator: Callable[[int], int]) -> Callable:
    def _apply(inp: Input, rng: random.Random) -> Input:
        new_clauses = _mutate_clause_value(parse(inp.rule_text), field, mutator)
        w = _clone(inp)
        w.rule_text = render(new_clauses)
        return w
    return _apply


def _has_field(field: str) -> Callable[[Input], bool]:
    def _ok(inp: Input) -> bool:
        return any(c.field == field for c in parse(inp.rule_text))
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
# Borderline T (engineered for c7 divergence zone)
# =====================================================================

def _add_passing_clause(inp: Input, rng: random.Random) -> Input:
    """Append 'team_size >= 1' — always passes for our corpus.

    Effect on score = 60·(n_old − p_old)/(n_old·(n_old+1))
    For default 3-clause rule and p_old=2: effect = +5 (in divergence zone).
    """
    clauses = parse(inp.rule_text)
    clauses.append(Clause("team_size", ">=", 1))
    w = _clone(inp)
    w.rule_text = render(clauses)
    return w


# =====================================================================
# Case fact (sensitivity / directional)
# =====================================================================

def _case_revenue_up(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp); w.case.revenue_monthly = max(1, w.case.revenue_monthly * 2); return w


def _case_revenue_down(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp); w.case.revenue_monthly = w.case.revenue_monthly // 2; return w


def _case_team_plus(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp); w.case.team_size += 1; return w


def _case_team_minus(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp); w.case.team_size = max(1, w.case.team_size - 1); return w


def _case_risk_up(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp); w.case.risk_score = min(100, w.case.risk_score + 20); return w


def _case_risk_down(inp: Input, rng: random.Random) -> Input:
    w = _clone(inp); w.case.risk_score = max(0, w.case.risk_score - 20); return w


# =====================================================================
# CATALOGUE
# =====================================================================

def _inv(name: str, axis: str, apply, applicable=_always) -> Transform:
    return Transform(
        name=name, axis=axis, apply=apply, is_applicable=applicable,
        sensitivity_kind="invariance", expected_direction="EQ",
        active_subset=None,
    )


def _dir(
    name: str, axis: str, apply, applicable, direction: str, A: Callable[[Input], bool],
) -> Transform:
    return Transform(
        name=name, axis=axis, apply=apply, is_applicable=applicable,
        sensitivity_kind="directional", expected_direction=direction,
        active_subset=A,
    )


CATALOGUE: list[Transform] = [
    # --- Identity (sanity; classified as invariance) ---
    Transform(
        name="identity", axis="identity", apply=_identity, is_applicable=_always,
        sensitivity_kind="invariance", expected_direction="EQ",
        active_subset=None, is_identity=True,
    ),

    # --- Order ---
    _inv("permute_founders", "order", _permute_founders, _founders_perm_applicable),
    _inv("permute_risks",    "order", _permute_risks,    _risks_perm_applicable),

    # --- Optional ---
    _inv("replace_description", "optional", _replace_description),
    _inv("blank_description",   "optional", _blank_description),

    # --- Non-rule fact ---
    _inv("add_risk_item",           "non_rule_fact", _add_risk_item),
    _inv("drop_risk_item",          "non_rule_fact", _drop_risk_item, _drop_risk_applicable),
    _inv("bump_founder_experience", "non_rule_fact", _bump_founder_experience),

    # --- Rule threshold (directional) ---
    _dir("strengthen_revenue_threshold", "rule_threshold",
         _make_threshold_apply("revenue", lambda v: v * 2),
         _has_field("revenue"), "DOWN", _A_strengthen_revenue),
    _dir("weaken_revenue_threshold", "rule_threshold",
         _make_threshold_apply("revenue", lambda v: v // 2),
         _has_field("revenue"), "UP", _A_weaken_revenue),
    _dir("strengthen_team_threshold", "rule_threshold",
         _make_threshold_apply("team_size", lambda v: v + 2),
         _has_field("team_size"), "DOWN", _A_strengthen_team),
    _dir("weaken_team_threshold", "rule_threshold",
         _make_threshold_apply("team_size", lambda v: max(0, v - 1)),
         _has_field("team_size"), "UP", _A_weaken_team),
    _dir("strengthen_risk_threshold", "rule_threshold",
         _make_threshold_apply("risk", lambda v: max(0, v - 10)),
         _has_field("risk"), "DOWN", _A_strengthen_risk),
    _dir("weaken_risk_threshold", "rule_threshold",
         _make_threshold_apply("risk", lambda v: v + 10),     # 40 → 50 per v2.1 spec
         _has_field("risk"), "UP", _A_weaken_risk),

    # --- Rule clause (directional) ---
    _dir("add_strict_clause",  "rule_clause", _add_strict_clause,  _always,
         "DOWN", _A_add_strict_clause),
    _dir("remove_last_clause", "rule_clause", _remove_last_clause, _remove_last_applicable,
         "UP",   _A_remove_last_clause),

    # --- BORDERLINE T (directional, engineered for c7 divergence zone) ---
    Transform(
        name="add_passing_clause", axis="rule_clause",
        apply=_add_passing_clause, is_applicable=_always,
        sensitivity_kind="directional", expected_direction="UP",
        active_subset=_A_borderline_add_passing,
        is_borderline=True,
    ),

    # --- Case fact (directional) ---
    _dir("case_revenue_up",   "case_fact", _case_revenue_up,   _always, "UP",   _A_case_revenue_up),
    _dir("case_revenue_down", "case_fact", _case_revenue_down, _always, "DOWN", _A_case_revenue_down),
    _dir("case_team_plus",    "case_fact", _case_team_plus,    _always, "UP",   _A_case_team_plus),
    _dir("case_team_minus",   "case_fact", _case_team_minus,   _always, "DOWN", _A_case_team_minus),
    _dir("case_risk_up",      "case_fact", _case_risk_up,      _always, "DOWN", _A_case_risk_up),
    _dir("case_risk_down",    "case_fact", _case_risk_down,    _always, "UP",   _A_case_risk_down),
]
