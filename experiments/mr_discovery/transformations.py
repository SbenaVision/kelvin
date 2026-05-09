"""Transformation catalogue.

Each transformation carries:
- `name`: unique id, used for logging
- `axis`: which input field/axis it touches (used by the bug-symmetry
  filter to decide whether two Ts act on the same axis)
- `apply(v)`: returns a transformed Venture
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from typing import Callable

from pipeline import Founder, Venture


@dataclass(frozen=True)
class Transform:
    name: str
    axis: str
    apply: Callable[[Venture, random.Random], Venture]


def _clone(v: Venture) -> Venture:
    return copy.deepcopy(v)


# --- founders axis ---

def _permute_founders(v: Venture, rng: random.Random) -> Venture:
    if len(v.founders) < 2:
        return _clone(v)
    w = _clone(v)
    rng.shuffle(w.founders)
    return w


def _rename_founders(v: Venture, rng: random.Random) -> Venture:
    w = _clone(v)
    pool = ["Alice", "Bob", "Carol", "Dan", "Eve", "Frank", "Gina", "Harold"]
    for i, f in enumerate(w.founders):
        f.name = pool[(i + rng.randint(0, 7)) % len(pool)]
    return w


def _bump_founder_experience(v: Venture, rng: random.Random) -> Venture:
    """Non-invariance T on founders axis — increases avg experience."""
    w = _clone(v)
    if w.founders:
        for f in w.founders:
            f.experience_years += 5
    return w


# --- risks axis ---

def _permute_risks(v: Venture, rng: random.Random) -> Venture:
    if len(v.risks) < 2:
        return _clone(v)
    w = _clone(v)
    rng.shuffle(w.risks)
    return w


def _add_risk(v: Venture, rng: random.Random) -> Venture:
    w = _clone(v)
    w.risks.append(f"synthetic_risk_{rng.randint(1000, 9999)}")
    return w


def _drop_risk(v: Venture, rng: random.Random) -> Venture:
    w = _clone(v)
    if w.risks:
        w.risks.pop()
    return w


# --- description axis (the bug-symmetry trap) ---

def _append_description(v: Venture, rng: random.Random) -> Venture:
    w = _clone(v)
    w.description = (w.description or "") + f" appended-{rng.randint(1000, 9999)}"
    return w


def _replace_description(v: Venture, rng: random.Random) -> Venture:
    w = _clone(v)
    w.description = f"wholly different text {rng.randint(1000, 9999)}"
    return w


# --- revenue axis ---

def _scale_revenue_up(v: Venture, rng: random.Random) -> Venture:
    w = _clone(v)
    w.revenue_monthly = max(w.revenue_monthly * 10, 1)
    return w


def _scale_revenue_down(v: Venture, rng: random.Random) -> Venture:
    w = _clone(v)
    w.revenue_monthly = w.revenue_monthly // 10
    return w


# --- team_size axis ---

def _team_plus(v: Venture, rng: random.Random) -> Venture:
    w = _clone(v)
    w.team_size += 1
    return w


def _team_minus(v: Venture, rng: random.Random) -> Venture:
    w = _clone(v)
    w.team_size = max(w.team_size - 1, 1)
    return w


# --- stage axis ---

STAGE_ORDER = ["idea", "building", "first_users"]


def _promote_stage(v: Venture, rng: random.Random) -> Venture:
    w = _clone(v)
    i = STAGE_ORDER.index(w.stage)
    if i < len(STAGE_ORDER) - 1:
        w.stage = STAGE_ORDER[i + 1]
    return w


def _demote_stage(v: Venture, rng: random.Random) -> Venture:
    w = _clone(v)
    i = STAGE_ORDER.index(w.stage)
    if i > 0:
        w.stage = STAGE_ORDER[i - 1]
    return w


CATALOGUE: list[Transform] = [
    Transform("permute_founders",        "founders",    _permute_founders),
    Transform("rename_founders",         "founders",    _rename_founders),
    Transform("bump_founder_experience", "founders",    _bump_founder_experience),
    Transform("permute_risks",           "risks",       _permute_risks),
    Transform("add_risk",                "risks",       _add_risk),
    Transform("drop_risk",               "risks",       _drop_risk),
    Transform("append_description",      "description", _append_description),
    Transform("replace_description",     "description", _replace_description),
    Transform("scale_revenue_up",        "revenue",     _scale_revenue_up),
    Transform("scale_revenue_down",      "revenue",     _scale_revenue_down),
    Transform("team_plus",               "team_size",   _team_plus),
    Transform("team_minus",              "team_size",   _team_minus),
    Transform("promote_stage",           "stage",       _promote_stage),
    Transform("demote_stage",            "stage",       _demote_stage),
]
