"""Discovery loop.

For every (T, R) in the cross-product of catalogues, compute the hold
rate on the corpus. Keep pairs where the empirical hold rate exceeds a
threshold AND the Wilson 95% CI lower bound also exceeds a (lower)
threshold.

Strict relations (R_lt, R_gt) are excluded — they can't be universal
invariants for any T that is the identity on some subset of inputs.
They stay in the catalogue for sensitivity analysis but aren't candidates
for "must hold on all inputs" discovery.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from pipeline import PipelineFn, Venture
from relations import Relation
from transformations import Transform


@dataclass(frozen=True)
class MRCandidate:
    t_name: str
    r_name: str
    axis: str
    hold_count: int
    total: int
    hold_rate: float
    wilson_lower: float


def wilson_lower_bound(successes: int, n: int, z: float = 1.96) -> float:
    """Wilson 95% one-sided lower bound on a binomial proportion."""
    if n == 0:
        return 0.0
    p = successes / n
    denom = 1 + z**2 / n
    centre = p + z**2 / (2 * n)
    spread = z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n)
    return max(0.0, (centre - spread) / denom)


def evaluate_pair(
    f: PipelineFn,
    t: Transform,
    r: Relation,
    corpus: list[Venture],
    seed: int,
) -> MRCandidate:
    rng = random.Random(seed)
    hold = 0
    for x in corpus:
        tx = t.apply(x, rng)
        if r.check(f(x), f(tx)):
            hold += 1
    n = len(corpus)
    return MRCandidate(
        t_name=t.name,
        r_name=r.name,
        axis=t.axis,
        hold_count=hold,
        total=n,
        hold_rate=hold / n if n else 0.0,
        wilson_lower=wilson_lower_bound(hold, n),
    )


def discover(
    f: PipelineFn,
    corpus: list[Venture],
    transforms: list[Transform],
    relations: list[Relation],
    *,
    hold_rate_threshold: float = 0.95,
    wilson_threshold: float = 0.90,
    include_strict: bool = False,
    seed: int = 7,
) -> tuple[list[MRCandidate], list[MRCandidate]]:
    """Return (discovered, all_candidates).

    `discovered` = pairs passing both the empirical hold-rate threshold
    and the Wilson lower-bound threshold.

    `all_candidates` = every (T, R) pair evaluated, for inspection.
    """
    discovered: list[MRCandidate] = []
    all_candidates: list[MRCandidate] = []
    for t in transforms:
        for r in relations:
            if not include_strict and r.name in {"R_lt", "R_gt"}:
                continue
            cand = evaluate_pair(f, t, r, corpus, seed)
            all_candidates.append(cand)
            if (
                cand.hold_rate >= hold_rate_threshold
                and cand.wilson_lower >= wilson_threshold
            ):
                discovered.append(cand)
    return discovered, all_candidates
