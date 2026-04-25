"""Pre-sealed configuration for the EOS v2.2 CERTIFICATION run.

Scope: a small, theorem-aligned certification run against the
V5 theorem (eos_consistency_separation_theorem_V5.pdf,
April 25, 2026). Distinct in scope from v2.1's broader product
(behavioral audit) catalogue.

Per the V5 spec (Assumption 1), every value in this file is fixed
BEFORE evaluation samples are drawn. Editing this file after sealing
invalidates the run.

Wording discipline (per build-plan §7): the run is "theorem-aligned" —
it tests whether the V5 finite-sample assumptions are empirically
supported on a fresh corpus draw. It does NOT prove the V5 theorems
themselves (those are mathematically proved in the PDF).
"""
from __future__ import annotations

# ---------------------------------------------------------------------
# Theorem parameters
# ---------------------------------------------------------------------
EPS: float = 0.10
THETA: float = 0.90               # = 1 − ε; the EOS acceptance threshold
LAMBDA: float = 0.08              # uniform margin: |p_c(f_j) − θ| ≥ λ
DELTA: float = 0.05               # family-wise failure budget

# Catalogue size and family size (sealed)
M: int = 8
A: int = 4                         # number of adversaries (excludes f_track)
A_PLUS_1: int = A + 1              # |F| = 5

# Theorem-required active-sample bounds (computed from the formula,
# rounded up). See seal_manifest.py / theorem_check.py for derivation.
THEOREM2_N_MIN: int = 577          # uniform recovery over family
THEOREM3_N_MIN: int = 451          # separation alone

# Pre-committed minimum active sample size per (pipeline, probe).
N_EFF_MIN: int = 600               # safety margin: Th.2 +23, Th.3 +149

# Per-pair Bonferroni-corrected CP confidence level for reporting.
# α_per_pair = δ / (2 · M · (A + 1)) = 0.05 / 80 = 6.25e-04
ALPHA_PER_PAIR: float = DELTA / (2 * M * A_PLUS_1)

# ---------------------------------------------------------------------
# Relation thresholds (raw — no noise term)
# ---------------------------------------------------------------------
DELTA_DIR: int = 4                 # for R_up, R_down
DELTA_EQ: int = 6                  # for R_eq — chosen so that the maximum
                                    # absolute jitter difference (6, when
                                    # j_t = +3, j_b = -3 or vice versa)
                                    # is contained within the equality
                                    # tolerance. With Δ_eq = 6 and no
                                    # rule effect, R_eq holds with prob
                                    # exactly 1.0 on invariant probes.
                                    # (Certification-hygiene fix.)

# ---------------------------------------------------------------------
# Stochastic adversary
# ---------------------------------------------------------------------
P_ATTACK: float = 0.50             # raised from v2.1's 0.40 to satisfy
                                    # uniform-margin on f_wrongstochastic

# ---------------------------------------------------------------------
# Noise model (carried over from v2.1)
# ---------------------------------------------------------------------
P_NOISE: float = 0.12
NOISE_DELTAS: tuple[int, ...] = (-3, -2, -1, 1, 2, 3)
NOISE_BASE_SEED: int = 1009
SCORE_MIN: int = 0
SCORE_MAX: int = 100

# ---------------------------------------------------------------------
# Decision threshold (unused in raw relations; kept for parity)
# ---------------------------------------------------------------------
DECISION_THRESHOLD: int = 50

# ---------------------------------------------------------------------
# Coupling Γ_{j,c} (pre-specified, fixed before evaluation)
# ---------------------------------------------------------------------
# Independent internal randomness for f_j(x) and f_j(T_c x).
# Seeded deterministically by (case_id, replay_idx, pipeline_id).
BASELINE_REPLAY_IDX: int = 0
TRANSFORM_REPLAY_IDX: int = 1

# ---------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------
CORPUS_SEED: int = 41              # FRESH; disjoint from v2.1 (17, 23, 29)

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
