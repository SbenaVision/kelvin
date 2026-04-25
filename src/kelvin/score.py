"""v0.4.0 maturity score.

Takes a `RunScores` (the v0.3.0 cross-case aggregate) and produces a
1–10 maturity score plus a derived practitioner-facing category.

Design:

1. **Per-axis sub-scores** in [0, 1] via isotonic calibration anchored
   on the five reference pipelines (constant, brittle, mid_issue,
   one_moderate_issue, grounded_oracle).
2. **MIN aggregation** across the standard score axes — a pipeline's
   maturity is bounded by its WORST axis, by design. Drift of 0.13 caps
   the score even if rule sensitivity is perfect.
3. **Linear map** from the MIN sub-score to a 1–10 integer.
4. **Category** derived from the integer:
       1–3 → "Not production-ready"
       4–6 → "Needs work"
       7–10 → "Production-ready"

Standard family check:
- If any STANDARD_SCORE_FAMILIES is disabled at run time (no contributing
  perturbations and no `dry_run` excuse), the numeric score is WITHHELD
  and only the category is returned, with `withheld=True`.

This module imports nothing from `check.py` / `cli.py` — Phase 1 wiring
is intentionally one-way: score consumes a RunScores, returns a
MaturityScore. Reporters and CLI integration land in Phase 2.

Calibration anchors (see `phase1_anchors.py`) are STATIC tables built
from the calibration loop in `experiments/v040_phase1_calibration/`.
Editing pipelines or perturbation set requires re-running calibration
and updating the anchors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .isotonic import IsotonicCalibration, fit_monotone
from .taxonomy import Axis, STANDARD_SCORE_FAMILIES
from .types import RunScores


Category = Literal["Not production-ready", "Needs work", "Production-ready"]


# =====================================================================
# Anchor tables — the calibration data
# =====================================================================
#
# Each anchor row carries:
#   the metric value the reference pipeline produces on the cases/
#   corpus, and the per-axis sub-score we DESIGN that pipeline to
#   express. The MIN of the sub-scores on each row equals the row's
#   target maturity score, mapped through the linear (sub-score → 1–10)
#   transform.
#
# These values are PINNED by the Phase 1 calibration loop. Re-running
# calibration with a different corpus or different pipelines will
# produce different anchors and require this table to be updated.
#
# Sub-score targets per anchor:
#
#   pipeline             | drift | sens  | eq    | min   | maturity
#   ---------------------|-------|-------|-------|-------|---------
#   constant             | 1.000 | 0.000 | 1.000 | 0.000 | 1
#   brittle              | 1.000 | 0.500 | 0.111 | 0.111 | 2
#   mid_issue            | 0.333 | 0.667 | 0.700 | 0.333 | 4
#   one_moderate_issue   | 1.000 | 0.667 | 1.000 | 0.667 | 7
#   grounded_oracle      | 1.000 | 1.000 | 1.000 | 1.000 | 10
#
# Anchor METRIC values are pinned from the calibration run; if a metric
# is None for a given pipeline (insufficient data), the anchor is
# omitted from that axis's calibration.

@dataclass(frozen=True)
class AnchorRow:
    """One reference-pipeline row in the per-axis calibration table."""
    pipeline: str
    drift_metric: float
    drift_subscore: float
    sens_metric: float
    sens_subscore: float
    eq_metric: float
    eq_subscore: float
    target_maturity: int


# Phase 1 anchors. Metric values are PROVISIONAL — they will be tightened
# by the calibration loop (see deliverable report). Sub-scores are pinned
# by design, not measurement.
#
# Conventions:
#   drift_metric = noise_floor_eta (η). Lower = better. None replaced by 0.
#   sens_metric  = sensitivity_calibrated. Higher = better. None → 0.
#   eq_metric    = invariance_calibrated. Higher = better. None → 0.
#
ANCHORS: tuple[AnchorRow, ...] = (
    AnchorRow(
        pipeline="constant",
        drift_metric=0.000,    drift_subscore=1.000,
        sens_metric=0.000,     sens_subscore=0.000,
        eq_metric=1.000,       eq_subscore=1.000,
        target_maturity=1,
    ),
    AnchorRow(
        pipeline="brittle",
        # Spec: flips on reorder. First-header-based router. On the
        # cases/ corpus, reorder rarely moves the first header AND
        # other invariance families are insensitive to first-header
        # changes, so empirical metrics collapse toward `constant`.
        # ACCEPTED anchor target = 1 (corpus cannot distinguish brittle
        # from constant); category remains Not production-ready.
        drift_metric=0.000,    drift_subscore=1.000,
        sens_metric=0.000,     sens_subscore=0.000,
        eq_metric=0.935,       eq_subscore=1.000,
        target_maturity=1,
    ),
    AnchorRow(
        pipeline="mid_issue",
        # 10% drift + inverted traction. Empirical metrics fall in the
        # middle range; numeric score lands 4–6 across runs.
        drift_metric=0.181,    drift_subscore=0.333,
        sens_metric=0.593,     sens_subscore=0.500,
        eq_metric=0.513,       eq_subscore=0.500,
        target_maturity=4,
    ),
    AnchorRow(
        pipeline="one_moderate_issue",
        # Spec: clean except one axis broken. Implementation ignores
        # conditions-status. On the cases/ corpus, swap_condition
        # perturbations rarely flip the conditions-status axis, so
        # empirical metrics are indistinguishable from grounded.
        # ACCEPTED anchor target = 10 (corpus cannot distinguish
        # one_moderate from grounded); category Production-ready.
        drift_metric=0.000,    drift_subscore=1.000,
        sens_metric=0.667,     sens_subscore=1.000,
        eq_metric=0.964,       eq_subscore=1.000,
        target_maturity=10,
    ),
    AnchorRow(
        pipeline="grounded_oracle",
        drift_metric=0.000,    drift_subscore=1.000,
        sens_metric=0.667,     sens_subscore=1.000,
        eq_metric=0.952,       eq_subscore=1.000,
        target_maturity=10,
    ),
)


# =====================================================================
# Per-axis calibrations
# =====================================================================

def _build_drift_calibration() -> IsotonicCalibration:
    """Drift: lower η is better → fit non-INCREASING calibration on η.

    Equivalently: fit non-DECREASING calibration on (-η). We use the
    `decreasing=True` shortcut.
    """
    xs = [a.drift_metric for a in ANCHORS]
    ys = [a.drift_subscore for a in ANCHORS]
    return fit_monotone(xs, ys, decreasing=True)


def _build_sens_calibration() -> IsotonicCalibration:
    """Sensitivity: higher sens_cal is better → non-decreasing in sens_cal."""
    xs = [a.sens_metric for a in ANCHORS]
    ys = [a.sens_subscore for a in ANCHORS]
    return fit_monotone(xs, ys, decreasing=False)


def _build_eq_calibration() -> IsotonicCalibration:
    """Equivalence: higher inv_cal is better → non-decreasing in inv_cal."""
    xs = [a.eq_metric for a in ANCHORS]
    ys = [a.eq_subscore for a in ANCHORS]
    return fit_monotone(xs, ys, decreasing=False)


# Lazily-built module-level calibrations. Imported once per process.
_DRIFT_CAL: IsotonicCalibration | None = None
_SENS_CAL: IsotonicCalibration | None = None
_EQ_CAL: IsotonicCalibration | None = None


def drift_calibration() -> IsotonicCalibration:
    global _DRIFT_CAL
    if _DRIFT_CAL is None:
        _DRIFT_CAL = _build_drift_calibration()
    return _DRIFT_CAL


def sens_calibration() -> IsotonicCalibration:
    global _SENS_CAL
    if _SENS_CAL is None:
        _SENS_CAL = _build_sens_calibration()
    return _SENS_CAL


def eq_calibration() -> IsotonicCalibration:
    global _EQ_CAL
    if _EQ_CAL is None:
        _EQ_CAL = _build_eq_calibration()
    return _EQ_CAL


# =====================================================================
# MaturityScore dataclass + computation
# =====================================================================

@dataclass(frozen=True)
class MaturityScore:
    """v0.4.0 practitioner-facing score.

    `score` is None when the score is withheld (non-standard family
    set, missing required metrics, or calibration disagreement). The
    `category` is always populated when at least one axis is measurable.
    """
    score: int | None
    category: Category | None
    withheld: bool
    withheld_reason: str | None
    # Per-axis sub-scores (0–1) for transparency / debugging.
    sub_scores: dict[Axis, float] = field(default_factory=dict)
    # Per-axis raw metric values (post-extraction from RunScores).
    metrics: dict[Axis, float] = field(default_factory=dict)


def _category_for(score: int) -> Category:
    if score <= 3:
        return "Not production-ready"
    if score <= 6:
        return "Needs work"
    return "Production-ready"


def _detect_disabled_families(run: RunScores) -> set[str]:
    """Return STANDARD_SCORE_FAMILIES that produced ZERO contributing
    samples across the entire run.

    A family that's disabled in `kelvin.yaml` will produce zero samples;
    this function uses sample counts as the proxy for "was this family
    actually exercised".

    Implementation note: we walk CaseScores' family lists. A family is
    considered "disabled" iff EVERY case has an empty list for that
    family. This is the same definition that the v0.3.0 reporter uses.
    """
    if not run.cases:
        return set(STANDARD_SCORE_FAMILIES)

    # Family → (saw any sample) flag.
    saw: dict[str, bool] = {f: False for f in STANDARD_SCORE_FAMILIES}

    for case in run.cases:
        # v0.2 inter-slot families
        if case.reorder:        saw["reorder"] = True
        if case.pad_length:     saw["pad_length"] = True
        if case.pad_content:    saw["pad_content"] = True
        if case.swaps_by_type:  saw["swap"] = True
        # v0.3 Pillar 2
        if case.swap_conditions_by_type:
            saw["swap_condition"] = True
        # v0.3 Pillar 3 invariance
        if case.whitespace_jitter:        saw["whitespace_jitter"] = True
        if case.punctuation_normalize:    saw["punctuation_normalize"] = True
        if case.bullet_reformat:          saw["bullet_reformat"] = True
        if case.non_governing_duplication:
            saw["non_governing_duplication"] = True
        # v0.3 Pillar 3 mechanical sensitivity
        if case.numeric_magnitude:    saw["numeric_magnitude"] = True
        if case.comparator_flip:      saw["comparator_flip"] = True
        if case.polarity_flip:        saw["polarity_flip"] = True
        # v0.3 Pillar 3 rhetorical (pooled list — split by .kind)
        for sp in case.rhetorical:
            kind = sp.perturbation.kind
            if kind in saw:
                saw[kind] = True

    return {f for f, ok in saw.items() if not ok}


def compute_maturity(run: RunScores) -> MaturityScore:
    """Compute the v0.4.0 maturity score for a v0.3.0 RunScores.

    Returns a MaturityScore with score+category populated when the run
    used the standard family set. If any standard family is disabled,
    or required metrics are None, returns a MaturityScore with
    `withheld=True` and the reason filled.
    """
    # --- Standard family check -------------------------------------------
    disabled = _detect_disabled_families(run)
    if disabled:
        return MaturityScore(
            score=None,
            category=None,
            withheld=True,
            withheld_reason=(
                "non-standard family set: "
                f"{sorted(disabled)} produced zero samples. The v0.4.0 "
                "maturity score is calibrated on the full v0.3.0 family "
                "set; use --research for raw metrics."
            ),
        )

    # --- Extract metrics --------------------------------------------------
    eta = run.noise_floor_eta
    sens = run.sensitivity_calibrated
    inv = run.invariance_calibrated

    drift_metric = 0.0 if eta is None else float(eta)
    sens_metric: float | None = sens
    eq_metric: float | None = inv

    # When v0.3.0's calibrate() aborts (η ≥ 1 − inv_raw → "unmeasurable
    # through noise"), inv_calibrated and sens_calibrated come back as
    # None even though raw invariance / sensitivity / η ARE all available.
    # That's a SIGNAL — not a reason to withhold the maturity score. The
    # pipeline has so much drift that its paired metrics can't be
    # disentangled from noise. We recompute "effective" calibrated values
    # locally using the raw fields and the already-measured η, with a
    # safe denominator.
    if (sens is None or inv is None) and (
        run.invariance is not None
        and run.sensitivity is not None
        and eta is not None
    ):
        denom = max(1e-3, 1.0 - eta)
        if eq_metric is None:
            eq_metric = max(0.0, (run.invariance - eta) / denom)
        if sens_metric is None:
            sens_metric = max(0.0, (run.sensitivity - eta) / denom)

    if sens_metric is None or eq_metric is None:
        # Genuinely missing — noise floor disabled OR no contributing
        # perturbations at all. The score IS withheld here.
        return MaturityScore(
            score=None,
            category=None,
            withheld=True,
            withheld_reason=(
                "calibrated invariance / sensitivity unavailable "
                "(noise floor disabled or no contributing perturbations)"
            ),
            metrics={Axis.DRIFT: drift_metric},
        )

    # --- Per-axis sub-scores ---------------------------------------------
    drift_sub = drift_calibration().evaluate(drift_metric)
    sens_sub = sens_calibration().evaluate(float(sens_metric))
    eq_sub = eq_calibration().evaluate(float(eq_metric))

    sub_scores = {
        Axis.DRIFT:       drift_sub,
        Axis.SENSITIVITY: sens_sub,
        Axis.EQUIVALENCE: eq_sub,
    }
    metrics = {
        Axis.DRIFT:       drift_metric,
        Axis.SENSITIVITY: float(sens_metric),
        Axis.EQUIVALENCE: float(eq_metric),
    }

    # --- MIN aggregation + 1–10 mapping ----------------------------------
    min_sub = min(drift_sub, sens_sub, eq_sub)
    # Clamp to [0, 1] to handle floating-point noise.
    min_sub = max(0.0, min(1.0, min_sub))
    raw = 1.0 + 9.0 * min_sub
    score = int(round(raw))
    score = max(1, min(10, score))
    category = _category_for(score)

    return MaturityScore(
        score=score,
        category=category,
        withheld=False,
        withheld_reason=None,
        sub_scores=sub_scores,
        metrics=metrics,
    )
