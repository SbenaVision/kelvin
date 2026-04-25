"""Tests for kelvin.isotonic — pure-Python PAV + linear interpolation."""

from __future__ import annotations

import pytest

from kelvin.isotonic import IsotonicCalibration, fit_monotone


# =====================================================================
# Construction
# =====================================================================

def test_fit_empty_raises():
    with pytest.raises(ValueError, match="empty"):
        fit_monotone([], [])


def test_fit_mismatched_lengths_raises():
    with pytest.raises(ValueError, match="length mismatch"):
        fit_monotone([0.0, 1.0], [0.0])


def test_fit_single_anchor_returns_constant_function():
    cal = fit_monotone([0.5], [0.7])
    assert cal(0.0) == pytest.approx(0.7)
    assert cal(0.5) == pytest.approx(0.7)
    assert cal(1.0) == pytest.approx(0.7)


# =====================================================================
# Monotonicity
# =====================================================================

def test_already_monotone_input_is_preserved():
    """Non-decreasing input should round-trip through PAV unchanged."""
    cal = fit_monotone([0.0, 0.25, 0.5, 0.75, 1.0],
                       [0.0, 0.20, 0.40, 0.60, 1.0])
    # Anchor points hit exactly.
    for x, y_target in zip(cal.xs, [0.0, 0.20, 0.40, 0.60, 1.0]):
        assert cal(x) == pytest.approx(y_target)


def test_pav_pools_violations_into_monotone_fit():
    """Input with one downward kink: PAV should pool the violators
    into a single block average."""
    cal = fit_monotone([0.0, 1.0, 2.0, 3.0],
                       [0.0, 0.7, 0.5, 1.0])
    # Original ys at x=1 and x=2: 0.7, 0.5 — violation. Pool to mean = 0.6.
    assert cal(1.0) == pytest.approx(0.6)
    assert cal(2.0) == pytest.approx(0.6)
    # Endpoints unchanged.
    assert cal(0.0) == pytest.approx(0.0)
    assert cal(3.0) == pytest.approx(1.0)


def test_decreasing_fit_inverts_monotonicity():
    """`decreasing=True` should produce non-increasing output."""
    cal = fit_monotone([0.0, 0.1, 0.2, 0.3], [1.0, 1.0, 0.5, 0.0],
                       decreasing=True)
    ys = [cal(x) for x in [0.0, 0.1, 0.2, 0.3]]
    # Monotone non-increasing.
    for a, b in zip(ys, ys[1:]):
        assert a >= b - 1e-9, f"violated: {ys}"


def test_decreasing_fit_pools_correctly():
    """Decreasing fit on a non-monotone input pools violators."""
    cal = fit_monotone([0.0, 0.1, 0.2, 0.3], [1.0, 0.4, 0.6, 0.0],
                       decreasing=True)
    # 0.4 vs 0.6 violates non-increasing → pool to mean = 0.5.
    assert cal(0.1) == pytest.approx(0.5)
    assert cal(0.2) == pytest.approx(0.5)


# =====================================================================
# Interpolation + clamping
# =====================================================================

def test_linear_interpolation_between_anchors():
    cal = fit_monotone([0.0, 1.0], [0.0, 1.0])
    # Halfway → 0.5.
    assert cal(0.5) == pytest.approx(0.5)
    # Quarter → 0.25.
    assert cal(0.25) == pytest.approx(0.25)


def test_clamps_below_smallest_anchor():
    cal = fit_monotone([0.5, 1.0], [0.3, 1.0])
    assert cal(0.0) == pytest.approx(0.3)
    assert cal(-100.0) == pytest.approx(0.3)


def test_clamps_above_largest_anchor():
    cal = fit_monotone([0.0, 0.5], [0.0, 0.7])
    assert cal(1.0) == pytest.approx(0.7)
    assert cal(100.0) == pytest.approx(0.7)


# =====================================================================
# Integration: Phase 1 anchors
# =====================================================================

def test_phase1_drift_anchors_fit_consistently():
    """The four drift anchors with η=0 should pool to the mean of their
    sub-scores; the mid_issue anchor at η=0.20 sits at 0.333.

    With the v0.4.0 anchor table, all η=0 pipelines have sub-score=1.0,
    so pooling is trivial (mean = 1.0). The η=0.20 mid_issue anchor is
    distinct.
    """
    # Mirrors score.ANCHORS for drift.
    xs = [0.0, 0.0, 0.20, 0.0, 0.0]
    ys = [1.0, 1.0, 0.333, 1.0, 1.0]
    cal = fit_monotone(xs, ys, decreasing=True)
    # At η=0: should be 1.0 (the four-anchor cluster).
    assert cal(0.0) == pytest.approx(1.0, abs=0.01)
    # At η=0.20: should be 0.333 ± numerical wiggle.
    assert cal(0.20) == pytest.approx(0.333, abs=0.05)
    # Above 0.20: clamped to 0.333.
    assert cal(0.5) == pytest.approx(0.333, abs=0.05)
