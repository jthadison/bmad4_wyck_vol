"""
Unit tests for Signal Confidence Scoring Calculator (Story 19.6)

Tests cover:
- Confidence calculation with weighted formula
- Volume score calculation per pattern type
- Grade mapping
- Threshold-based rejection
- Deterministic calculation verification
- Edge cases and boundary conditions

Test Scenarios from Story 19.6:
- High Confidence Spring (95% → A+)
- Marginal SOS (68% → C, auto-reject)
- Threshold configuration
- Determinism verification
"""

import pytest

from src.signal_generator.confidence_calculator import (
    DEFAULT_MIN_THRESHOLD,
    PATTERN_WEIGHT,
    PHASE_WEIGHT,
    VOLUME_WEIGHT,
    ConfidenceCalculator,
    ConfidenceGrade,
    ConfidenceResult,
    calculate_confidence,
    calculate_volume_score,
    get_grade,
)


class TestGetGrade:
    """Tests for grade mapping function."""

    def test_a_plus_grade_90(self):
        """Score of exactly 90 should be A+."""
        assert get_grade(90.0) == ConfidenceGrade.A_PLUS

    def test_a_plus_grade_100(self):
        """Score of 100 should be A+."""
        assert get_grade(100.0) == ConfidenceGrade.A_PLUS

    def test_a_plus_grade_95(self):
        """Score of 95 should be A+."""
        assert get_grade(95.0) == ConfidenceGrade.A_PLUS

    def test_a_grade_80(self):
        """Score of exactly 80 should be A."""
        assert get_grade(80.0) == ConfidenceGrade.A

    def test_a_grade_89(self):
        """Score of 89.99 should be A."""
        assert get_grade(89.99) == ConfidenceGrade.A

    def test_b_grade_70(self):
        """Score of exactly 70 should be B."""
        assert get_grade(70.0) == ConfidenceGrade.B

    def test_b_grade_79(self):
        """Score of 79.99 should be B."""
        assert get_grade(79.99) == ConfidenceGrade.B

    def test_c_grade_60(self):
        """Score of exactly 60 should be C."""
        assert get_grade(60.0) == ConfidenceGrade.C

    def test_c_grade_69(self):
        """Score of 69.99 should be C."""
        assert get_grade(69.99) == ConfidenceGrade.C

    def test_f_grade_59(self):
        """Score of 59.99 should be F."""
        assert get_grade(59.99) == ConfidenceGrade.F

    def test_f_grade_0(self):
        """Score of 0 should be F."""
        assert get_grade(0.0) == ConfidenceGrade.F


class TestCalculateVolumeScoreSpring:
    """Tests for Spring pattern volume score calculation."""

    def test_spring_perfect_volume_0_4(self):
        """Spring with 0.4x volume should score 1.0 (perfect)."""
        assert calculate_volume_score("SPRING", 0.4) == 1.0

    def test_spring_excellent_volume_0_5(self):
        """Spring with 0.5x volume should score 0.9 (excellent)."""
        assert calculate_volume_score("SPRING", 0.5) == 0.9

    def test_spring_good_volume_0_6(self):
        """Spring with 0.6x volume should score 0.75 (good)."""
        assert calculate_volume_score("SPRING", 0.6) == 0.75

    def test_spring_borderline_volume_0_65(self):
        """Spring with 0.65x volume should score 0.6 (borderline)."""
        assert calculate_volume_score("SPRING", 0.65) == 0.6

    def test_spring_violation_0_7(self):
        """Spring with 0.7x volume should score 0.0 (violation)."""
        assert calculate_volume_score("SPRING", 0.7) == 0.0

    def test_spring_violation_high_volume(self):
        """Spring with high volume (1.5x) should score 0.0 (violation)."""
        assert calculate_volume_score("SPRING", 1.5) == 0.0


class TestCalculateVolumeScoreSOS:
    """Tests for SOS breakout pattern volume score calculation."""

    def test_sos_perfect_volume_2_0(self):
        """SOS with 2.0x volume should score 1.0 (perfect)."""
        assert calculate_volume_score("SOS", 2.0) == 1.0

    def test_sos_perfect_volume_3_0(self):
        """SOS with 3.0x volume should score 1.0 (perfect)."""
        assert calculate_volume_score("SOS", 3.0) == 1.0

    def test_sos_excellent_volume_1_8(self):
        """SOS with 1.8x volume should score 0.9 (excellent)."""
        assert calculate_volume_score("SOS", 1.8) == 0.9

    def test_sos_good_volume_1_6(self):
        """SOS with 1.6x volume should score 0.75 (good)."""
        assert calculate_volume_score("SOS", 1.6) == 0.75

    def test_sos_borderline_volume_1_5(self):
        """SOS with 1.5x volume should score 0.6 (borderline)."""
        assert calculate_volume_score("SOS", 1.5) == 0.6

    def test_sos_violation_1_4(self):
        """SOS with 1.4x volume should score 0.0 (violation)."""
        assert calculate_volume_score("SOS", 1.4) == 0.0

    def test_sos_violation_low_volume(self):
        """SOS with low volume (0.5x) should score 0.0 (violation)."""
        assert calculate_volume_score("SOS", 0.5) == 0.0


class TestCalculateVolumeScoreLPS:
    """Tests for LPS retest pattern volume score calculation."""

    def test_lps_perfect_volume_0_8(self):
        """LPS with 0.8x volume should score 1.0 (perfect - in ideal range)."""
        assert calculate_volume_score("LPS", 0.8) == 1.0

    def test_lps_perfect_volume_1_0(self):
        """LPS with 1.0x volume should score 1.0 (perfect)."""
        assert calculate_volume_score("LPS", 1.0) == 1.0

    def test_lps_good_volume_0_5(self):
        """LPS with 0.5x volume should score 0.85."""
        assert calculate_volume_score("LPS", 0.5) == 0.85

    def test_lps_acceptable_volume_0_4(self):
        """LPS with 0.4x volume should score 0.7."""
        assert calculate_volume_score("LPS", 0.4) == 0.7


class TestCalculateVolumeScoreUTAD:
    """Tests for UTAD pattern volume score calculation.

    UTAD requires HIGH volume to confirm supply overwhelming demand.
    This is the correct Wyckoff interpretation (distribution trap).
    """

    def test_utad_excellent_volume_2_5(self):
        """UTAD with 2.5x volume should score 1.0 (excellent distribution signal)."""
        assert calculate_volume_score("UTAD", 2.5) == 1.0

    def test_utad_very_strong_volume_2_0(self):
        """UTAD with 2.0x volume should score 0.9 (very strong)."""
        assert calculate_volume_score("UTAD", 2.0) == 0.9

    def test_utad_strong_volume_1_5(self):
        """UTAD with 1.5x volume should score 0.8 (strong)."""
        assert calculate_volume_score("UTAD", 1.5) == 0.8

    def test_utad_acceptable_volume_1_2(self):
        """UTAD with 1.2x volume should score 0.7 (meets validator minimum)."""
        assert calculate_volume_score("UTAD", 1.2) == 0.7

    def test_utad_violation_low_volume(self):
        """UTAD with low volume (< 1.2x) should score 0.0 (violation)."""
        assert calculate_volume_score("UTAD", 0.7) == 0.0
        assert calculate_volume_score("UTAD", 1.0) == 0.0
        assert calculate_volume_score("UTAD", 1.1) == 0.0


class TestCalculateVolumeScoreSC:
    """Tests for Selling Climax pattern volume score calculation."""

    def test_sc_perfect_volume_3_0(self):
        """SC with 3.0x volume should score 1.0 (perfect)."""
        assert calculate_volume_score("SC", 3.0) == 1.0

    def test_sc_excellent_volume_2_5(self):
        """SC with 2.5x volume should score 0.9."""
        assert calculate_volume_score("SC", 2.5) == 0.9

    def test_sc_good_volume_2_0(self):
        """SC with 2.0x volume should score 0.75."""
        assert calculate_volume_score("SC", 2.0) == 0.75

    def test_sc_weak_volume_1_0(self):
        """SC with 1.0x volume should score 0.3 (weak)."""
        assert calculate_volume_score("SC", 1.0) == 0.3


class TestCalculateVolumeScoreAR:
    """Tests for Automatic Rally pattern volume score calculation."""

    def test_ar_perfect_volume_1_5(self):
        """AR with 1.5x volume should score 1.0 (in ideal range)."""
        assert calculate_volume_score("AR", 1.5) == 1.0

    def test_ar_good_volume_1_0(self):
        """AR with 1.0x volume should score 0.85."""
        assert calculate_volume_score("AR", 1.0) == 0.85


class TestConfidenceCalculatorInit:
    """Tests for ConfidenceCalculator initialization."""

    def test_default_threshold(self):
        """Default threshold should be 70.0."""
        calculator = ConfidenceCalculator()
        assert calculator.min_threshold == 70.0

    def test_custom_threshold(self):
        """Custom threshold should be set correctly."""
        calculator = ConfidenceCalculator(min_threshold=75.0)
        assert calculator.min_threshold == 75.0

    def test_invalid_threshold_negative(self):
        """Negative threshold should raise ValueError."""
        with pytest.raises(ValueError, match="min_threshold must be 0-100"):
            ConfidenceCalculator(min_threshold=-10.0)

    def test_invalid_threshold_over_100(self):
        """Threshold over 100 should raise ValueError."""
        with pytest.raises(ValueError, match="min_threshold must be 0-100"):
            ConfidenceCalculator(min_threshold=150.0)


class TestConfidenceCalculatorCalculate:
    """Tests for ConfidenceCalculator.calculate() method."""

    def test_high_confidence_spring_scenario(self):
        """
        Scenario 1 from Story 19.6: High Confidence Spring.

        Given: pattern_quality=0.95, phase_strength=0.90, volume_ratio=0.4x
        Expected: score ~95%, grade A+, approved
        """
        calculator = ConfidenceCalculator()
        result = calculator.calculate(
            pattern_quality=0.95,
            phase_strength=0.90,
            pattern_type="SPRING",
            volume_ratio=0.4,
        )

        # Volume score for Spring at 0.4x = 1.0
        # Expected: 0.95*0.4 + 0.90*0.3 + 1.0*0.3 = 0.38 + 0.27 + 0.30 = 0.95 = 95%
        assert result.confidence_score == 95.0
        assert result.grade == ConfidenceGrade.A_PLUS
        assert result.meets_threshold is True
        assert result.rejection_reason is None

    def test_marginal_sos_scenario(self):
        """
        Scenario 2 from Story 19.6: Marginal SOS.

        Given: pattern_quality=0.70, phase_strength=0.65, volume_ratio=1.6x
        Expected: score ~70.5%, grade B, approved (just above 70%)
        """
        calculator = ConfidenceCalculator()
        result = calculator.calculate(
            pattern_quality=0.70,
            phase_strength=0.65,
            pattern_type="SOS",
            volume_ratio=1.6,
        )

        # Volume score for SOS at 1.6x = 0.75
        # Expected: 0.70*0.4 + 0.65*0.3 + 0.75*0.3 = 0.28 + 0.195 + 0.225 = 0.70 = 70%
        assert result.confidence_score == 70.0
        assert result.grade == ConfidenceGrade.B
        assert result.meets_threshold is True

    def test_rejected_signal_below_threshold(self):
        """Signal below 70% threshold should be rejected."""
        calculator = ConfidenceCalculator(min_threshold=70.0)
        result = calculator.calculate(
            pattern_quality=0.60,
            phase_strength=0.50,
            pattern_type="SOS",
            volume_ratio=1.4,  # Violation = 0.0 volume score
        )

        # Expected: 0.60*0.4 + 0.50*0.3 + 0.0*0.3 = 0.24 + 0.15 + 0.0 = 0.39 = 39%
        assert result.confidence_score == 39.0
        assert result.grade == ConfidenceGrade.F
        assert result.meets_threshold is False
        assert "Below minimum confidence threshold" in result.rejection_reason

    def test_custom_threshold_rejection(self):
        """
        Scenario 3 from Story 19.6: Threshold Configuration.

        Given: threshold=75%, signal=72%
        Expected: rejected with reason
        """
        calculator = ConfidenceCalculator(min_threshold=75.0)
        result = calculator.calculate(
            pattern_quality=0.72,
            phase_strength=0.70,
            pattern_type="SPRING",
            volume_ratio=0.5,  # Volume score = 0.9
        )

        # Expected: 0.72*0.4 + 0.70*0.3 + 0.9*0.3 = 0.288 + 0.21 + 0.27 = 0.768 = 76.8%
        # This actually passes 75% threshold
        # Let's adjust for a case that fails
        result2 = calculator.calculate(
            pattern_quality=0.65,
            phase_strength=0.65,
            pattern_type="SPRING",
            volume_ratio=0.5,  # Volume score = 0.9
        )

        # Expected: 0.65*0.4 + 0.65*0.3 + 0.9*0.3 = 0.26 + 0.195 + 0.27 = 0.725 = 72.5%
        assert result2.confidence_score == 72.5
        assert result2.meets_threshold is False
        assert "72.5% < 75.0%" in result2.rejection_reason

    def test_invalid_pattern_quality_negative(self):
        """Negative pattern_quality should raise ValueError."""
        calculator = ConfidenceCalculator()
        with pytest.raises(ValueError, match="pattern_quality must be 0.0-1.0"):
            calculator.calculate(
                pattern_quality=-0.1,
                phase_strength=0.80,
                pattern_type="SPRING",
                volume_ratio=0.4,
            )

    def test_invalid_pattern_quality_over_1(self):
        """pattern_quality over 1.0 should raise ValueError."""
        calculator = ConfidenceCalculator()
        with pytest.raises(ValueError, match="pattern_quality must be 0.0-1.0"):
            calculator.calculate(
                pattern_quality=1.5,
                phase_strength=0.80,
                pattern_type="SPRING",
                volume_ratio=0.4,
            )

    def test_invalid_phase_strength(self):
        """Invalid phase_strength should raise ValueError."""
        calculator = ConfidenceCalculator()
        with pytest.raises(ValueError, match="phase_strength must be 0.0-1.0"):
            calculator.calculate(
                pattern_quality=0.90,
                phase_strength=1.5,
                pattern_type="SPRING",
                volume_ratio=0.4,
            )

    def test_invalid_volume_ratio_negative(self):
        """Negative volume_ratio should raise ValueError."""
        calculator = ConfidenceCalculator()
        with pytest.raises(ValueError, match="volume_ratio must be non-negative"):
            calculator.calculate(
                pattern_quality=0.90,
                phase_strength=0.80,
                pattern_type="SPRING",
                volume_ratio=-0.5,
            )


class TestConfidenceCalculatorFromScores:
    """Tests for ConfidenceCalculator.calculate_from_scores() method."""

    def test_from_scores_basic(self):
        """Basic test with pre-calculated volume score."""
        calculator = ConfidenceCalculator()
        result = calculator.calculate_from_scores(
            pattern_quality=0.90,
            phase_strength=0.85,
            volume_score=0.80,
        )

        # Expected: 0.90*0.4 + 0.85*0.3 + 0.80*0.3 = 0.36 + 0.255 + 0.24 = 0.855 = 85.5%
        assert result.confidence_score == 85.5
        assert result.grade == ConfidenceGrade.A

    def test_from_scores_invalid_volume_score(self):
        """Invalid volume_score should raise ValueError."""
        calculator = ConfidenceCalculator()
        with pytest.raises(ValueError, match="volume_score must be 0.0-1.0"):
            calculator.calculate_from_scores(
                pattern_quality=0.90,
                phase_strength=0.85,
                volume_score=1.5,
            )


class TestCalculateConfidenceFunction:
    """Tests for the convenience calculate_confidence() function."""

    def test_convenience_function(self):
        """Test the convenience function works correctly."""
        result = calculate_confidence(
            pattern_quality=0.95,
            phase_strength=0.90,
            volume_score=1.0,
        )

        # Expected: 0.95*0.4 + 0.90*0.3 + 1.0*0.3 = 0.38 + 0.27 + 0.30 = 0.95 = 95%
        assert result.confidence_score == 95.0
        assert result.grade == ConfidenceGrade.A_PLUS

    def test_convenience_function_custom_threshold(self):
        """Test convenience function with custom threshold."""
        result = calculate_confidence(
            pattern_quality=0.70,
            phase_strength=0.70,
            volume_score=0.70,
            min_threshold=75.0,
        )

        # Expected: 0.70*0.4 + 0.70*0.3 + 0.70*0.3 = 0.28 + 0.21 + 0.21 = 0.70 = 70%
        assert result.confidence_score == 70.0
        assert result.meets_threshold is False


class TestDeterminism:
    """
    Scenario 4 from Story 19.6: Deterministic Calculation.

    Given the same input parameters, confidence should be identical each time.
    """

    def test_deterministic_calculation(self):
        """Same inputs should always produce identical results."""
        calculator = ConfidenceCalculator()

        results = []
        for _ in range(100):
            result = calculator.calculate(
                pattern_quality=0.85,
                phase_strength=0.80,
                pattern_type="SPRING",
                volume_ratio=0.45,
            )
            results.append(result.confidence_score)

        # All results should be identical
        assert all(r == results[0] for r in results)
        assert len(set(results)) == 1  # Only one unique value

    def test_deterministic_from_scores(self):
        """Same inputs to calculate_from_scores should produce identical results."""
        calculator = ConfidenceCalculator()

        results = []
        for _ in range(100):
            result = calculator.calculate_from_scores(
                pattern_quality=0.85,
                phase_strength=0.80,
                volume_score=0.75,
            )
            results.append(result.confidence_score)

        assert all(r == results[0] for r in results)


class TestWeightConstants:
    """Tests to verify weight constants match Story 19.6 specification."""

    def test_pattern_weight(self):
        """Pattern weight should be 40%."""
        assert PATTERN_WEIGHT == 0.40

    def test_phase_weight(self):
        """Phase weight should be 30%."""
        assert PHASE_WEIGHT == 0.30

    def test_volume_weight(self):
        """Volume weight should be 30%."""
        assert VOLUME_WEIGHT == 0.30

    def test_weights_sum_to_one(self):
        """Weights should sum to 1.0."""
        assert PATTERN_WEIGHT + PHASE_WEIGHT + VOLUME_WEIGHT == 1.0

    def test_default_threshold(self):
        """Default threshold should be 70%."""
        assert DEFAULT_MIN_THRESHOLD == 70.0


class TestConfidenceResult:
    """Tests for ConfidenceResult model."""

    def test_result_fields(self):
        """Result should have all required fields."""
        result = ConfidenceResult(
            confidence_score=85.0,
            grade=ConfidenceGrade.A,
            pattern_quality_score=90.0,
            phase_strength_score=80.0,
            volume_score=75.0,
            meets_threshold=True,
            threshold=70.0,
        )

        assert result.confidence_score == 85.0
        assert result.grade == ConfidenceGrade.A
        assert result.pattern_quality_score == 90.0
        assert result.phase_strength_score == 80.0
        assert result.volume_score == 75.0
        assert result.meets_threshold is True
        assert result.threshold == 70.0

    def test_rejection_reason_when_below_threshold(self):
        """rejection_reason should return message when below threshold."""
        result = ConfidenceResult(
            confidence_score=65.0,
            grade=ConfidenceGrade.C,
            pattern_quality_score=70.0,
            phase_strength_score=60.0,
            volume_score=50.0,
            meets_threshold=False,
            threshold=70.0,
        )

        assert result.rejection_reason is not None
        assert "65.0% < 70.0%" in result.rejection_reason

    def test_rejection_reason_when_above_threshold(self):
        """rejection_reason should be None when above threshold."""
        result = ConfidenceResult(
            confidence_score=85.0,
            grade=ConfidenceGrade.A,
            pattern_quality_score=90.0,
            phase_strength_score=80.0,
            volume_score=75.0,
            meets_threshold=True,
            threshold=70.0,
        )

        assert result.rejection_reason is None


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_inputs(self):
        """All zero inputs should produce 0% confidence."""
        calculator = ConfidenceCalculator()
        result = calculator.calculate_from_scores(
            pattern_quality=0.0,
            phase_strength=0.0,
            volume_score=0.0,
        )

        assert result.confidence_score == 0.0
        assert result.grade == ConfidenceGrade.F
        assert result.meets_threshold is False

    def test_perfect_inputs(self):
        """All perfect inputs should produce 100% confidence."""
        calculator = ConfidenceCalculator()
        result = calculator.calculate_from_scores(
            pattern_quality=1.0,
            phase_strength=1.0,
            volume_score=1.0,
        )

        assert result.confidence_score == 100.0
        assert result.grade == ConfidenceGrade.A_PLUS
        assert result.meets_threshold is True

    def test_boundary_at_exact_threshold(self):
        """Score exactly at threshold should pass."""
        calculator = ConfidenceCalculator(min_threshold=70.0)
        result = calculator.calculate_from_scores(
            pattern_quality=0.70,
            phase_strength=0.70,
            volume_score=0.70,
        )

        assert result.confidence_score == 70.0
        assert result.meets_threshold is True

    def test_zero_threshold(self):
        """Zero threshold should approve all signals."""
        calculator = ConfidenceCalculator(min_threshold=0.0)
        result = calculator.calculate_from_scores(
            pattern_quality=0.10,
            phase_strength=0.10,
            volume_score=0.10,
        )

        assert result.meets_threshold is True

    def test_100_threshold(self):
        """100% threshold should only approve perfect scores."""
        calculator = ConfidenceCalculator(min_threshold=100.0)

        # Not quite perfect
        result1 = calculator.calculate_from_scores(
            pattern_quality=0.99,
            phase_strength=0.99,
            volume_score=0.99,
        )
        assert result1.meets_threshold is False

        # Perfect
        result2 = calculator.calculate_from_scores(
            pattern_quality=1.0,
            phase_strength=1.0,
            volume_score=1.0,
        )
        assert result2.meets_threshold is True

    def test_unknown_pattern_type_gets_neutral_volume(self):
        """Unknown pattern type should get neutral (0.5) volume score."""
        # This tests the else branch in calculate_volume_score
        score = calculate_volume_score("UNKNOWN", 1.0)
        assert score == 0.5
