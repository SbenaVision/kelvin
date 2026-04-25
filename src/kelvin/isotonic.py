"""Pure-Python isotonic regression utility for v0.4.0 score calibration.

Implements the Pool Adjacent Violators (PAV) algorithm for fitting a
monotone non-decreasing step function through a small set of (x, y)
anchor points, plus linear interpolation/extrapolation for evaluation
at new x values.

We deliberately avoid scikit-learn / numpy as runtime dependencies:

- Kelvin's existing dep set is light (typer, rich, pyyaml, jinja2);
  pulling in scikit-learn (~50 MB) or numpy (~30 MB) for what is
  essentially a 5-anchor lookup table would be a poor trade.
- Anchor sets are tiny (≤ 10 points). PAV is O(n²) worst case but
  trivially fast at this scale.
- Pure-Python keeps the core importable on minimal install footprints.

API summary:

    fit_monotone(xs, ys, *, decreasing=False) -> IsotonicCalibration
    cal = fit_monotone([0.0, 0.2, 1.0], [0.0, 0.4, 1.0])
    cal(0.1)  -> 0.2 (linear interp between (0.0, 0.0) and (0.2, 0.4))

Behavior at boundaries:

- Below the smallest anchor x: returns y of the smallest anchor (clamp).
- Above the largest anchor x: returns y of the largest anchor (clamp).
- Between anchors: linear interpolation.

Clamping is the safer default for a maturity-score calibration: an
unfamiliar new pipeline whose metric falls outside the calibration
range should NOT receive an extrapolated sub-score that exceeds the
calibration's known anchors. The maturity-score user sees a value
inside the established calibration envelope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class IsotonicCalibration:
    """Fitted monotone calibration. Callable: f(x) -> y.

    Attributes:
        xs: anchor x values, sorted ascending.
        ys: fitted y values, monotone non-decreasing in xs (or non-
            increasing if `decreasing=True` was used at fit time).
        decreasing: whether the calibration is monotone non-increasing.
    """

    xs: tuple[float, ...]
    ys: tuple[float, ...]
    decreasing: bool

    def __call__(self, x: float) -> float:
        return self.evaluate(x)

    def evaluate(self, x: float) -> float:
        """Evaluate the calibrated function at x.

        Linear interpolation between anchors; clamps to anchor extrema
        outside the anchor range.
        """
        xs, ys = self.xs, self.ys
        n = len(xs)
        if n == 0:
            raise ValueError("empty calibration")
        if n == 1:
            return ys[0]
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        # Binary search for the segment containing x. Linear scan is
        # fine for n ≤ 10; we use bisect for correctness/clarity.
        from bisect import bisect_right
        i = bisect_right(xs, x)
        # Now xs[i-1] < x ≤ xs[i] (since x is strictly inside).
        x_lo, x_hi = xs[i - 1], xs[i]
        y_lo, y_hi = ys[i - 1], ys[i]
        if x_hi == x_lo:
            return y_lo
        t = (x - x_lo) / (x_hi - x_lo)
        return y_lo + t * (y_hi - y_lo)


def _pav_increasing(ys: list[float]) -> list[float]:
    """Pool-Adjacent-Violators for non-decreasing fit.

    Input order is x-sorted; output is the in-place pooled means.
    """
    n = len(ys)
    if n == 0:
        return []
    # Each block: (sum, count). After pooling, fitted value = sum / count.
    blocks: list[tuple[float, int]] = [(y, 1) for y in ys]
    i = 0
    while i < len(blocks) - 1:
        s_i, c_i = blocks[i]
        s_j, c_j = blocks[i + 1]
        if s_i / c_i > s_j / c_j:
            # Violation: pool blocks i and i+1.
            blocks[i] = (s_i + s_j, c_i + c_j)
            del blocks[i + 1]
            if i > 0:
                i -= 1  # re-check previous block for new violation
        else:
            i += 1
    fitted: list[float] = []
    for s, c in blocks:
        avg = s / c
        fitted.extend([avg] * c)
    return fitted


def fit_monotone(
    xs: Sequence[float],
    ys: Sequence[float],
    *,
    decreasing: bool = False,
) -> IsotonicCalibration:
    """Fit a monotone calibration through (x, y) anchor points.

    Args:
        xs: anchor x values (need not be sorted).
        ys: anchor y values (need not be sorted; matched to xs by index).
        decreasing: if True, fit a monotone NON-INCREASING function.
            Default False fits non-decreasing.

    Returns:
        IsotonicCalibration with anchor xs/ys sorted ascending.

    Raises:
        ValueError: if inputs are empty or have mismatched lengths.
    """
    if len(xs) != len(ys):
        raise ValueError(f"xs/ys length mismatch: {len(xs)} vs {len(ys)}")
    if len(xs) == 0:
        raise ValueError("empty anchor set")

    # Sort by x ascending, breaking ties by y to keep output deterministic.
    pairs = sorted(zip(xs, ys), key=lambda p: (p[0], p[1]))
    sorted_xs = [p[0] for p in pairs]
    sorted_ys = [p[1] for p in pairs]

    if decreasing:
        # Fit non-decreasing on negated ys, then negate back.
        fitted_neg = _pav_increasing([-y for y in sorted_ys])
        fitted = [-y for y in fitted_neg]
    else:
        fitted = _pav_increasing(sorted_ys)

    return IsotonicCalibration(
        xs=tuple(sorted_xs),
        ys=tuple(fitted),
        decreasing=decreasing,
    )
