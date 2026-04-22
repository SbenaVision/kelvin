from __future__ import annotations

import pytest

from kelvin.scorer import (
    DecisionFieldTypeError,
    DefaultScorer,
    aggregate,
    validate_scalar,
)
from kelvin.types import (
    CaseScores,
    InvocationResult,
    Perturbation,
    ScoredPerturbation,
)


class TestDistance:
    def setup_method(self) -> None:
        self.s = DefaultScorer()

    def test_equal_strings_zero(self) -> None:
        assert self.s.distance("approve", "approve") == 0.0

    def test_different_strings_one(self) -> None:
        assert self.s.distance("approve", "reject") == 1.0

    def test_strings_are_case_sensitive(self) -> None:
        assert self.s.distance("Approve", "approve") == 1.0

    def test_strings_are_whitespace_sensitive(self) -> None:
        assert self.s.distance("approve", "approve ") == 1.0

    def test_numeric_equal_zero(self) -> None:
        assert self.s.distance(5, 5) == 0.0

    def test_numeric_proportional_small_values(self) -> None:
        # |0.2 - 0.4| / max(0.2, 0.4, 1.0) = 0.2 / 1.0 = 0.2
        assert self.s.distance(0.2, 0.4) == pytest.approx(0.2)

    def test_numeric_proportional_large_values(self) -> None:
        # |10 - 20| / max(10, 20, 1) = 10 / 20 = 0.5
        assert self.s.distance(10, 20) == pytest.approx(0.5)

    def test_numeric_caps_at_one_for_huge_difference(self) -> None:
        # |0 - 1000| / max(0, 1000, 1) = 1.0
        assert self.s.distance(0, 1000) == 1.0

    def test_numeric_sign_matters_only_via_absolute_difference(self) -> None:
        # |-5 - 5| / max(5, 5, 1) = 10 / 5 = 2 → capped at 1.0
        assert self.s.distance(-5, 5) == 1.0

    def test_int_and_float_comparable(self) -> None:
        assert self.s.distance(1, 1.0) == 0.0

    def test_bool_equality(self) -> None:
        # bool falls under exact equality branch, not numeric.
        assert self.s.distance(True, True) == 0.0
        assert self.s.distance(True, False) == 1.0

    def test_none_equality(self) -> None:
        assert self.s.distance(None, None) == 0.0
        assert self.s.distance(None, "approve") == 1.0

    def test_mixed_types_treated_as_different(self) -> None:
        assert self.s.distance("1", 1) == 1.0

    def test_list_raises(self) -> None:
        with pytest.raises(DecisionFieldTypeError):
            self.s.distance([1, 2], [1, 2])

    def test_dict_raises(self) -> None:
        with pytest.raises(DecisionFieldTypeError):
            self.s.distance({"x": 1}, {"x": 1})


class TestValidateScalar:
    def test_accepts_string(self) -> None:
        validate_scalar("approve", "rec")

    def test_accepts_number(self) -> None:
        validate_scalar(0.5, "rec")

    def test_accepts_bool(self) -> None:
        validate_scalar(True, "rec")

    def test_accepts_none(self) -> None:
        validate_scalar(None, "rec")

    def test_rejects_list(self) -> None:
        with pytest.raises(DecisionFieldTypeError, match="scalar"):
            validate_scalar([1, 2], "rec")

    def test_rejects_dict(self) -> None:
        with pytest.raises(DecisionFieldTypeError, match="scalar"):
            validate_scalar({"a": 1}, "rec")


def _sp(kind: str, distance: float | None, variant_id: str = "v", notes=None) -> ScoredPerturbation:
    from pathlib import Path

    return ScoredPerturbation(
        perturbation=Perturbation(
            case_name="case",
            kind=kind,
            variant_id=variant_id,
            rendered_markdown="",
            notes=notes or {},
        ),
        invocation=InvocationResult(
            ok=distance is not None,
            exit_code=0,
            input_path=Path("in"),
            output_path=Path("out"),
        ),
        distance=distance,
    )


class TestAggregate:
    def test_empty_cases_has_null_scores(self) -> None:
        rs = aggregate([], seed=0, governing_types=["gate_rule"])
        assert rs.invariance is None
        assert rs.sensitivity is None
        assert rs.invariance_sample == 0
        assert rs.sensitivity_sample == 0

    def test_invariance_is_one_minus_mean(self) -> None:
        c = CaseScores(
            case_name="a",
            reorder=[_sp("reorder", 0.0), _sp("reorder", 0.0)],
            pad=[_sp("pad", 0.2)],
        )
        rs = aggregate([c], seed=0, governing_types=[])
        # mean distance = (0+0+0.2)/3 = 0.0667; invariance = 1 - 0.0667 = 0.933
        assert rs.invariance == pytest.approx(1 - 0.2 / 3)
        assert rs.invariance_sample == 3

    def test_sensitivity_is_mean_swap_distance(self) -> None:
        c = CaseScores(
            case_name="a",
            swaps_by_type={"gate_rule": [_sp("swap", 1.0), _sp("swap", 1.0), _sp("swap", 0.0)]},
        )
        rs = aggregate([c], seed=0, governing_types=["gate_rule"])
        assert rs.sensitivity == pytest.approx(2 / 3)
        assert rs.sensitivity_sample == 3

    def test_failed_perturbations_dont_contribute(self) -> None:
        # None distances are excluded from both numerator and sample count.
        c = CaseScores(
            case_name="a",
            reorder=[_sp("reorder", 0.0), _sp("reorder", None)],
            pad=[_sp("pad", 0.5)],
        )
        rs = aggregate([c], seed=0, governing_types=[])
        assert rs.invariance == pytest.approx(1 - 0.25)  # (0 + 0.5) / 2 = 0.25
        assert rs.invariance_sample == 2

    def test_per_type_breakdown(self) -> None:
        c = CaseScores(
            case_name="a",
            swaps_by_type={
                "gate_rule": [_sp("swap", 0.0), _sp("swap", 0.0)],
                "policy_clause": [_sp("swap", 1.0), _sp("swap", 1.0)],
            },
        )
        rs = aggregate([c], seed=0, governing_types=["gate_rule", "policy_clause"])
        assert rs.sensitivity_by_type["gate_rule"] == (0.0, 2)
        assert rs.sensitivity_by_type["policy_clause"] == (1.0, 2)
        # Overall: (0+0+1+1)/4 = 0.5
        assert rs.sensitivity == pytest.approx(0.5)
        assert rs.sensitivity_sample == 4

    def test_uniform_mean_not_case_weighted(self) -> None:
        # Case A has 1 swap at distance 0, case B has 3 swaps at distance 1.
        # A uniform mean weights by perturbation: (0+1+1+1)/4 = 0.75.
        a = CaseScores(
            case_name="a",
            swaps_by_type={"gate_rule": [_sp("swap", 0.0)]},
        )
        b = CaseScores(
            case_name="b",
            swaps_by_type={"gate_rule": [_sp("swap", 1.0), _sp("swap", 1.0), _sp("swap", 1.0)]},
        )
        rs = aggregate([a, b], seed=0, governing_types=["gate_rule"])
        assert rs.sensitivity == pytest.approx(0.75)

    def test_warnings_and_caps_collected_from_cases(self) -> None:
        c = CaseScores(case_name="a", warnings=["w1"], caps=["c1"])
        rs = aggregate([c], seed=0, governing_types=[], run_warnings=["r1"], run_caps=["rc1"])
        assert "w1" in rs.warnings
        assert "r1" in rs.warnings
        assert "c1" in rs.caps
        assert "rc1" in rs.caps


class TestKelvinScore:
    """K = (1 - Invariance) + (1 - Sensitivity), range [0, 2], lower = anchored."""

    def test_formula_matches_residuals(self) -> None:
        # reorder distance 0.2 → invariance = 0.8 → residual 0.2
        # swap distance 0.3 → sensitivity = 0.3 → residual 0.7
        # K = 0.9
        c = CaseScores(
            case_name="a",
            reorder=[_sp("reorder", 0.2)],
            swaps_by_type={"gate_rule": [_sp("swap", 0.3)]},
        )
        rs = aggregate([c], seed=0, governing_types=["gate_rule"])
        assert rs.invariance == pytest.approx(0.8)
        assert rs.sensitivity == pytest.approx(0.3)
        assert rs.kelvin_score == pytest.approx((1 - 0.8) + (1 - 0.3))
        assert rs.kelvin_score == pytest.approx(0.9)

    def test_zero_when_perfectly_anchored(self) -> None:
        # invariance 1.0 (no drift) + sensitivity 1.0 (every swap moves output) → K = 0
        c = CaseScores(
            case_name="a",
            reorder=[_sp("reorder", 0.0)],
            swaps_by_type={"gate_rule": [_sp("swap", 1.0)]},
        )
        rs = aggregate([c], seed=0, governing_types=["gate_rule"])
        assert rs.kelvin_score == pytest.approx(0.0)

    def test_two_when_worst_case(self) -> None:
        # invariance 0.0 (drifts every reorder) + sensitivity 0.0 (ignores swaps) → K = 2
        c = CaseScores(
            case_name="a",
            reorder=[_sp("reorder", 1.0)],
            swaps_by_type={"gate_rule": [_sp("swap", 0.0)]},
        )
        rs = aggregate([c], seed=0, governing_types=["gate_rule"])
        assert rs.kelvin_score == pytest.approx(2.0)

    def test_constant_output_pipeline(self) -> None:
        # Constant-output degeneracy: invariance 1.0, sensitivity 0.0 → K = 1.0.
        # Sanity check the §3.4 prediction: a pipeline that always returns the
        # same answer is distinguishable only because K sits at 1.0, not 0.0.
        c = CaseScores(
            case_name="a",
            reorder=[_sp("reorder", 0.0), _sp("reorder", 0.0)],
            pad=[_sp("pad", 0.0)],
            swaps_by_type={"gate_rule": [_sp("swap", 0.0), _sp("swap", 0.0)]},
        )
        rs = aggregate([c], seed=0, governing_types=["gate_rule"])
        assert rs.invariance == pytest.approx(1.0)
        assert rs.sensitivity == pytest.approx(0.0)
        assert rs.kelvin_score == pytest.approx(1.0)

    def test_none_when_invariance_missing(self) -> None:
        c = CaseScores(
            case_name="a",
            swaps_by_type={"gate_rule": [_sp("swap", 0.5)]},
        )
        rs = aggregate([c], seed=0, governing_types=["gate_rule"])
        assert rs.invariance is None
        assert rs.kelvin_score is None

    def test_none_when_sensitivity_missing(self) -> None:
        c = CaseScores(
            case_name="a",
            reorder=[_sp("reorder", 0.5)],
        )
        rs = aggregate([c], seed=0, governing_types=[])
        assert rs.sensitivity is None
        assert rs.kelvin_score is None

    def test_none_when_no_cases(self) -> None:
        rs = aggregate([], seed=0, governing_types=["gate_rule"])
        assert rs.kelvin_score is None
