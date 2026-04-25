"""Tests for kelvin.taxonomy — axis enum and family constants."""

from __future__ import annotations

import typing

from kelvin.taxonomy import (
    Axis,
    FAMILY_AXIS,
    STANDARD_SCORE_FAMILIES,
    family_axis,
)
from kelvin.types import PerturbationKind


def test_axis_enum_has_four_members():
    """Spec: drift, sensitivity, equivalence, wrong-direction."""
    members = {a.value for a in Axis}
    assert members == {"drift", "sensitivity", "equivalence", "wrong_direction"}


def test_standard_score_families_matches_v0_3_perturbation_kinds():
    """STANDARD_SCORE_FAMILIES must enumerate exactly the v0.3.0
    PerturbationKind literal — re-running calibration with a smaller
    or larger set requires updating both in lockstep."""
    kinds = set(typing.get_args(PerturbationKind))
    assert STANDARD_SCORE_FAMILIES == kinds, (
        "STANDARD_SCORE_FAMILIES drifted from PerturbationKind. "
        "Update both together."
    )


def test_family_axis_returns_expected_axis_for_known_families():
    assert family_axis("reorder") is Axis.EQUIVALENCE
    assert family_axis("whitespace_jitter") is Axis.EQUIVALENCE
    assert family_axis("hedge_injection") is Axis.EQUIVALENCE
    assert family_axis("swap") is Axis.SENSITIVITY
    assert family_axis("swap_condition") is Axis.SENSITIVITY
    assert family_axis("numeric_magnitude") is Axis.SENSITIVITY
    assert family_axis("comparator_flip") is Axis.SENSITIVITY
    assert family_axis("polarity_flip") is Axis.SENSITIVITY


def test_family_axis_unknown_returns_none():
    assert family_axis("not_a_real_family") is None


def test_family_axis_covers_every_standard_family():
    """Every family in STANDARD_SCORE_FAMILIES has a declared axis."""
    missing = [f for f in STANDARD_SCORE_FAMILIES if family_axis(f) is None]
    assert not missing, (
        f"Families without an axis assignment: {missing}. "
        "Add them to FAMILY_AXIS or remove them from STANDARD_SCORE_FAMILIES."
    )


def test_family_axis_only_assigns_drift_or_sensitivity_or_equivalence():
    """DRIFT and WRONG_DIRECTION are cross-cutting; no FAMILY produces
    them directly. Only SENSITIVITY and EQUIVALENCE should appear in
    FAMILY_AXIS values."""
    seen = set(FAMILY_AXIS.values())
    forbidden = seen & {Axis.DRIFT, Axis.WRONG_DIRECTION}
    assert not forbidden, (
        f"FAMILY_AXIS should not include {forbidden}; those axes are "
        "cross-cutting and not produced by any single family."
    )
