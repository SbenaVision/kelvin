"""Discovery loop with applicability filtering + per-case noise threshold.

For each pipeline f, each transformation T, each noise-aware relation R^Ω:

  z_i = 1{ R^Ω(y_baseline_i, y_perturbed_i, q_i) holds }

where:
  y_baseline_i = first baseline replay of x_i (deterministic pick)
  y_perturbed_i = single fresh evaluation of f(T(x_i))
  q_i = q_0.95^noise(x_i)  estimated from K baseline replays

Cases where T is not applicable to x_i are DROPPED for that (T, R) pair
(per plan §8.1). We report n_eff(T, R) per pair.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from cp_lcb import accept_cp, cp_lcb
from relations import NaiveRelation, NoiseAwareRelation
from schema import Input
from transformations import Transform


PipelineFnReplay = Callable[[Input, int], int]   # used for replays
PipelineFnTransform = Callable[[Input, int], int]   # used for f(Tx); separate replay_idx


@dataclass(frozen=True)
class CandidateOmega:
    """Noise-aware (T, R^Ω) candidate — counts toward Bonferroni m."""
    pipeline: str
    t_name: str
    axis: str
    is_identity: bool
    r_name: str
    k: int
    n_eff: int
    n_raw: int
    p_hat: float
    cp_lcb_value: float
    accepted: bool        # final decision (after n_eff floor)
    skipped_low_neff: bool


@dataclass(frozen=True)
class CandidateNaive:
    """Naive diagnostic — NOT in Bonferroni m, NOT in signature."""
    pipeline: str
    t_name: str
    axis: str
    r_name: str
    k: int
    n_eff: int
    p_hat: float
    cp_lcb_value: float
    accepted_alpha_raw: bool   # acceptance at α = δ (no Bonferroni)


def _evaluate_pair_omega(
    f_baseline: PipelineFnReplay,
    f_transform: PipelineFnTransform,
    inputs: list[Input],
    baseline_first_score: dict[int, int],
    q_per_case: dict[int, float],
    t: Transform,
    r: NoiseAwareRelation,
    transform_replay_idx: int,
) -> tuple[int, int]:
    rng = random.Random(0xA1A1)
    k = 0
    n_eff = 0
    for inp in inputs:
        if not t.is_applicable(inp):
            continue
        n_eff += 1
        y1 = baseline_first_score[inp.case.case_id]
        tx = t.apply(inp, rng)
        y2 = f_transform(tx, transform_replay_idx)
        q = q_per_case[inp.case.case_id]
        if r.check(y1, y2, q):
            k += 1
    return k, n_eff


def _evaluate_pair_naive(
    f_baseline: PipelineFnReplay,
    f_transform: PipelineFnTransform,
    inputs: list[Input],
    baseline_first_score: dict[int, int],
    t: Transform,
    r: NaiveRelation,
    transform_replay_idx: int,
) -> tuple[int, int]:
    rng = random.Random(0xA1A1)
    k = 0
    n_eff = 0
    for inp in inputs:
        if not t.is_applicable(inp):
            continue
        n_eff += 1
        y1 = baseline_first_score[inp.case.case_id]
        tx = t.apply(inp, rng)
        y2 = f_transform(tx, transform_replay_idx)
        if r.check(y1, y2):
            k += 1
    return k, n_eff


def discover_omega(
    pipeline_name: str,
    f: PipelineFnReplay,
    transforms: list[Transform],
    relations: list[NoiseAwareRelation],
    inputs: list[Input],
    baseline_first_score: dict[int, int],
    q_per_case: dict[int, float],
    *,
    eps: float,
    alpha: float,
    n_eff_min: int,
    transform_replay_idx: int,
) -> list[CandidateOmega]:
    out: list[CandidateOmega] = []
    for t in transforms:
        for r in relations:
            k, n_eff = _evaluate_pair_omega(
                f, f, inputs, baseline_first_score, q_per_case,
                t, r, transform_replay_idx,
            )
            n_raw = len(inputs)
            p_hat = k / n_eff if n_eff > 0 else 0.0
            skipped = n_eff < n_eff_min
            if skipped:
                accepted = False
                lb = 0.0
            else:
                accepted = accept_cp(k, n_eff, eps, alpha)
                lb = cp_lcb(k, n_eff, alpha)
            out.append(CandidateOmega(
                pipeline=pipeline_name, t_name=t.name, axis=t.axis,
                is_identity=t.is_identity, r_name=r.name,
                k=k, n_eff=n_eff, n_raw=n_raw,
                p_hat=p_hat, cp_lcb_value=lb,
                accepted=accepted, skipped_low_neff=skipped,
            ))
    return out


def discover_naive(
    pipeline_name: str,
    f: PipelineFnReplay,
    transforms: list[Transform],
    relations: list[NaiveRelation],
    inputs: list[Input],
    baseline_first_score: dict[int, int],
    *,
    delta: float,
    transform_replay_idx: int,
) -> list[CandidateNaive]:
    """Diagnostic only. Acceptance uses raw α=δ (no Bonferroni) so the
    naive set isn't artificially harder than the noise-aware one for
    the load-bearing comparison."""
    out: list[CandidateNaive] = []
    for t in transforms:
        for r in relations:
            k, n_eff = _evaluate_pair_naive(
                f, f, inputs, baseline_first_score,
                t, r, transform_replay_idx,
            )
            p_hat = k / n_eff if n_eff > 0 else 0.0
            accepted = accept_cp(k, n_eff, eps=0.10, alpha=delta) if n_eff > 0 else False
            lb = cp_lcb(k, n_eff, delta) if n_eff > 0 else 0.0
            out.append(CandidateNaive(
                pipeline=pipeline_name, t_name=t.name, axis=t.axis,
                r_name=r.name, k=k, n_eff=n_eff,
                p_hat=p_hat, cp_lcb_value=lb,
                accepted_alpha_raw=accepted,
            ))
    return out
