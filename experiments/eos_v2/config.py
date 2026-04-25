"""Pre-sealed configuration for the EOS v2 experiment.

ALL numeric parameters that govern the experiment live here. This file
is part of the sealed catalogue (sha256 in SEAL.txt). Editing this file
after sealing invalidates the run.

References:
- EOS_LLM_Backed_Experiment_Math_Plan_UPDATED.md §15 (final sealed run)
- experiments/eos/results.md (deterministic v1 PoC)
"""
from __future__ import annotations

# ---------------------------------------------------------------------
# Statistical parameters (thesis §4, plan §8)
# ---------------------------------------------------------------------
EPS: float = 0.10                 # acceptance threshold: accept iff p_L >= 1 - EPS
DELTA: float = 0.05               # family-wise error budget for Bonferroni
DELTA_EQ: int = 5                 # score-point margin for invariance R^Ω_eq
DELTA_DIR: int = 4                # score-point margin for directional R^Ω_↑/↓

# ---------------------------------------------------------------------
# Corpus parameters (plan §15)
# ---------------------------------------------------------------------
N_PER_DRAW: int = 300
K_D: int = 3                      # number of independent corpus draws
BOUNDARY_FRACTION: float = 0.65
INTERIOR_PASS_FRACTION: float = 0.175
INTERIOR_FAIL_FRACTION: float = 0.175
CORPUS_SEEDS: tuple[int, ...] = (17, 23, 29)  # K_D distinct primes; deterministic
N_EFF_MIN: int = 150              # per draw; pairs below → unresolved
TRAIN_FRAC: float = 1.0           # use full draw; stability comes from K_D draws

# ---------------------------------------------------------------------
# Noise model (plan §15, applied via pipelines/_noise.py)
# ---------------------------------------------------------------------
P_NOISE: float = 0.12
NOISE_DELTAS: tuple[int, ...] = (-3, -2, -1, 1, 2, 3)
NOISE_BASE_SEED: int = 1009       # seeds Random(NOISE_BASE_SEED ^ hash((case_id, replay_idx, pipeline_id)))
SCORE_MIN: int = 0
SCORE_MAX: int = 100

# ---------------------------------------------------------------------
# Noise-floor estimation (plan §7)
# ---------------------------------------------------------------------
K_REPLAYS: int = 20               # baseline replays per case for q_0.95 estimation
NOISE_QUANTILE: float = 0.95

# ---------------------------------------------------------------------
# Stochastic adversary (plan §11 criterion 4)
# ---------------------------------------------------------------------
P_ATTACK: float = 0.40            # f_wrongstochastic per-call attack rate (top of band)
ACTIVE_BOUNDARY_RISK_LO: int = 25
ACTIVE_BOUNDARY_RISK_HI: int = 55

# ---------------------------------------------------------------------
# Decision threshold for R_sign_eq (binary derived decision)
# ---------------------------------------------------------------------
DECISION_THRESHOLD: int = 50

# ---------------------------------------------------------------------
# Stability target (plan §15)
# ---------------------------------------------------------------------
JACCARD_TARGET: float = 0.80

# ---------------------------------------------------------------------
# Pipeline ids (used to seed pipeline-specific replay RNGs)
# ---------------------------------------------------------------------
PIPELINE_IDS: dict[str, int] = {
    "f_track":           1,
    "f_ruleblind":       2,
    "f_constant":        3,
    "f_wrongstatic":     4,
    "f_wrongstochastic": 5,
}
