"""Discovery loop with Bonferroni-corrected Clopper–Pearson acceptance.

Thesis §4 statistical rule:

    For each candidate (T, R), observe n Bernoulli trials
        z_i = 1 if R(f(x_i), f(Tx_i)) else 0
    Accept iff the one-sided CP lower bound at confidence 1 − α is
    at least 1 − ε, where α = δ / m (family-wise Bonferroni
    correction) and m = |T| × |R|.

This module computes every (T, R) candidate's k/n on a given corpus
and returns both the accepted set and full candidate records.

For acceptance we use the equivalent single-tail test (see
`cp_lcb.accept_cp`), which is exact and faster than the bisection.
For reporting we also return the actual CP lower bound via
`cp_lcb.cp_lcb`.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from cp_lcb import accept_cp, cp_lcb
from relations import Relation
from schema import Input
from transformations import Transform


PipelineFn = Callable[[Input], int]


@dataclass(frozen=True)
class Candidate:
    pipeline: str
    t_name: str
    r_name: str
    axis: str
    is_identity: bool
    k: int
    n: int
    p_hat: float
    cp_lcb: float
    accepted: bool


def _evaluate_pair(
    f: PipelineFn,
    t: Transform,
    r: Relation,
    corpus: list[Input],
    seed: int,
) -> tuple[int, int]:
    rng = random.Random(seed)
    hold = 0
    for x in corpus:
        tx = t.apply(x, rng)
        if r.check(f(x), f(tx)):
            hold += 1
    return hold, len(corpus)


def evaluate_all(
    pipeline_name: str,
    f: PipelineFn,
    transforms: list[Transform],
    relations: list[Relation],
    corpus: list[Input],
    *,
    eps: float,
    alpha: float,
    seed: int,
) -> list[Candidate]:
    out: list[Candidate] = []
    for t in transforms:
        for r in relations:
            k, n = _evaluate_pair(f, t, r, corpus, seed)
            p_hat = k / n if n else 0.0
            accepted = accept_cp(k, n, eps, alpha)
            lb = cp_lcb(k, n, alpha)
            out.append(Candidate(
                pipeline=pipeline_name,
                t_name=t.name,
                r_name=r.name,
                axis=t.axis,
                is_identity=t.is_identity,
                k=k, n=n, p_hat=p_hat, cp_lcb=lb,
                accepted=accepted,
            ))
    return out
