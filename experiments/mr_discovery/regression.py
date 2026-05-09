"""Regression catch test.

Re-evaluate discovered MRs against a buggy pipeline. For each MR,
compute the violation rate — fraction of inputs where R(f_bug(x),
f_bug(Tx)) fails. An MR whose violation rate is substantially higher on
the buggy pipeline than on the correct one has *caught* the regression.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from discover import MRCandidate
from pipeline import PipelineFn, Venture
from relations import CATALOGUE as R_CATALOGUE
from transformations import CATALOGUE as T_CATALOGUE


T_BY_NAME = {t.name: t for t in T_CATALOGUE}
R_BY_NAME = {r.name: r for r in R_CATALOGUE}


@dataclass(frozen=True)
class RegressionResult:
    t_name: str
    r_name: str
    violations_on_correct: int
    violations_on_buggy: int
    total: int
    violation_rate_correct: float
    violation_rate_buggy: float
    caught: bool


def measure_mr(
    mr: MRCandidate,
    f_correct: PipelineFn,
    f_buggy: PipelineFn,
    corpus: list[Venture],
    seed: int = 11,
) -> RegressionResult:
    t = T_BY_NAME[mr.t_name]
    r = R_BY_NAME[mr.r_name]

    v_correct = 0
    v_buggy = 0
    for x in corpus:
        rng_c = random.Random(seed)
        rng_b = random.Random(seed)
        tx_c = t.apply(x, rng_c)
        tx_b = t.apply(x, rng_b)
        if not r.check(f_correct(x), f_correct(tx_c)):
            v_correct += 1
        if not r.check(f_buggy(x), f_buggy(tx_b)):
            v_buggy += 1
    n = len(corpus)
    rate_c = v_correct / n if n else 0.0
    rate_b = v_buggy / n if n else 0.0
    return RegressionResult(
        t_name=mr.t_name,
        r_name=mr.r_name,
        violations_on_correct=v_correct,
        violations_on_buggy=v_buggy,
        total=n,
        violation_rate_correct=rate_c,
        violation_rate_buggy=rate_b,
        caught=rate_b >= 0.5 and rate_b > rate_c + 0.3,
    )


def run(
    discovered: list[MRCandidate],
    f_correct: PipelineFn,
    f_buggy: PipelineFn,
    corpus: list[Venture],
    seed: int = 11,
) -> list[RegressionResult]:
    return [measure_mr(mr, f_correct, f_buggy, corpus, seed) for mr in discovered]
