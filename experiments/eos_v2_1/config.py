"""Pre-sealed configuration for the EOS v2.1 experiment.

Refinements over v2:

- Sensitivity transformations are evaluated on PRE-SPECIFIED active
  subsets A_T derived from rule semantics (not observed effects).
- For each sensitivity T, we report directional rates
  (correct, wrong, no_effect) over A_T with two-sided CP confidence
  bounds (LCB for high-rate claims; UCB for low-rate claims).
- Global invariance R^Ω_eq is unchanged: evaluated over the full
  applicable distribution.
- A pre-committed BORDERLINE sensitivity T is added so the
  load-bearing (c7) check has a designed signal in the divergence zone
  Δ_naive ≤ signed_effect < q_0.95(x) + Δ_dir.

ALL numeric parameters that govern the experiment live here. This file
is part of the sealed catalogue (sha256 in SEAL.txt). Editing this file
after sealing invalidates the run.
"""
from __future__ import annotations

# ---------------------------------------------------------------------
# Statistical parameters
# ---------------------------------------------------------------------
EPS: float = 0.10                 # high-rate threshold for "rate ≥ 1−ε"
EPS_LOW: float = 0.10             # symmetric low-rate threshold for "rate ≤ ε"
DELTA: float = 0.05               # family-wise error budget (Bonferroni)
DELTA_EQ: int = 5                 # invariance margin (R^Ω_eq)
DELTA_DIR: int = 4                # directional margin (R^Ω_↑/↓ AND naive directional)

# ---------------------------------------------------------------------
# Corpus parameters
# ---------------------------------------------------------------------
N_PER_DRAW: int = 500
K_D: int = 3
BOUNDARY_FRACTION: float = 0.65
INTERIOR_PASS_FRACTION: float = 0.175
INTERIOR_FAIL_FRACTION: float = 0.175
CORPUS_SEEDS: tuple[int, ...] = (17, 23, 29)
TRAIN_FRAC: float = 1.0           # use full draw; stability comes from K_D draws

# Two distinct n_eff floors per the v2.1 spec:
N_EFF_MIN_GLOBAL: int = 150       # for global invariance over full corpus
N_EFF_MIN_ACTIVE: int = 30        # for directional sensitivity over A_T
                                  # Pairs below either floor → unresolved.
                                  # Note: at α=5.7e-4 and 1−ε=0.90, even
                                  # n_eff=71 with k=n is needed to pass
                                  # acceptance, so n_eff_active in [30, 70]
                                  # will likely produce "low-power" pairs
                                  # that resolve to "unresolved"; this is
                                  # a documented limitation.

# ---------------------------------------------------------------------
# Noise model
# ---------------------------------------------------------------------
P_NOISE: float = 0.12
NOISE_DELTAS: tuple[int, ...] = (-3, -2, -1, 1, 2, 3)
NOISE_BASE_SEED: int = 1009
SCORE_MIN: int = 0
SCORE_MAX: int = 100

# ---------------------------------------------------------------------
# Noise-floor estimation
# ---------------------------------------------------------------------
K_REPLAYS: int = 20
NOISE_QUANTILE: float = 0.95

# ---------------------------------------------------------------------
# Stochastic adversary
# ---------------------------------------------------------------------
P_ATTACK: float = 0.40
ACTIVE_BOUNDARY_RISK_LO: int = 25
ACTIVE_BOUNDARY_RISK_HI: int = 55

# ---------------------------------------------------------------------
# Decision threshold for R_sign_eq
# ---------------------------------------------------------------------
DECISION_THRESHOLD: int = 50

# ---------------------------------------------------------------------
# Stability target
# ---------------------------------------------------------------------
JACCARD_TARGET: float = 0.80

# ---------------------------------------------------------------------
# Pipeline ids
# ---------------------------------------------------------------------
PIPELINE_IDS: dict[str, int] = {
    "f_track":           1,
    "f_ruleblind":       2,
    "f_constant":        3,
    "f_wrongstatic":     4,
    "f_wrongstochastic": 5,
}

# ---------------------------------------------------------------------
# Naive directional acceptance (diagnostic only — load-bearing test)
# ---------------------------------------------------------------------
# Naive directional uses Δ_naive < Δ_dir with NO noise term.
# Δ_naive = 3 (one less than Δ_dir = 4) so the borderline T's effect
# of +5 lands cleanly above the naive threshold even with adverse
# jitter, while staying below the omega threshold q + Δ_dir ≈ 7.
#
# Naive uses raw α=δ=0.05 (no Bonferroni) per the load-bearing
# comparison convention.
#
# Divergence-zone width = (q + Δ_dir) − Δ_naive ≈ 4 score points.
DELTA_NAIVE: int = 3
