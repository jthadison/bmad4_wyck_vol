"""
Unit tests for SpringConfidenceScorer

Tests all scoring methods individually to ensure testability and correctness.
Each scoring method is tested with boundary values and representative cases.

Story 18.8.2: Spring Confidence Scorer Extraction
AC5: 95%+ test coverage
AC6: Scores match original implementation
"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.pattern_engine.detectors.spring.confidence_scorer import (
    ScoreResult,
    SpringConfidenceScorer,
)


# ================================================================
# Shared Fixtures
# ================================================================


@pytest.fixture
def scorer():
    """Create scorer instance for all tests."""
    return SpringConfidenceScorer()


@pytest.fixture
def mock_spring():
    """Create mock Spring with ideal values."""
    spring = MagicMock()
    spring.volume_ratio = Decimal("0.35")  # EXCELLENT: 30 pts
    spring.penetration_pct = Decimal("0.015")  # IDEAL: 35 pts
    spring.recovery_bars = 2  # STRONG: 20 pts
    return spring


@pytest.fixture
def mock_creek():
    """Create mock Creek with excellent strength."""
    creek = MagicMock()
    creek.strength_score = 85  # EXCELLENT: 10 pts bonus
    return creek


class TestScoreResult:
    """Tests for ScoreResult dataclass."""

    def test_score_result_creation(self):
        """Test ScoreResult can be created with required fields."""
        result = ScoreResult(points=35, quality="IDEAL", max_points=40)

        assert result.points == 35
        assert result.quality == "IDEAL"
        assert result.max_points == 40


class TestSpringConfidenceScorer:
    """Tests for SpringConfidenceScorer class."""

    # ================================================================
    # Volume Scoring Tests (_score_volume)
    # ================================================================

    class TestScoreVolume:
        """Tests for _score_volume method."""

        def test_exceptional_volume_under_0_3(self, scorer):
            """Volume < 0.3x earns 40 points (EXCEPTIONAL)."""
            result = scorer._score_volume(Decimal("0.25"))
            assert result.points == 40
            assert result.quality == "EXCEPTIONAL"
            assert result.max_points == 40

        def test_excellent_volume_0_3_to_0_4(self, scorer):
            """Volume 0.3x-0.4x earns 30 points (EXCELLENT)."""
            result = scorer._score_volume(Decimal("0.35"))
            assert result.points == 30
            assert result.quality == "EXCELLENT"

        def test_ideal_volume_0_4_to_0_5(self, scorer):
            """Volume 0.4x-0.5x earns 20 points (IDEAL)."""
            result = scorer._score_volume(Decimal("0.45"))
            assert result.points == 20
            assert result.quality == "IDEAL"

        def test_acceptable_volume_0_5_to_0_6(self, scorer):
            """Volume 0.5x-0.6x earns 10 points (ACCEPTABLE)."""
            result = scorer._score_volume(Decimal("0.55"))
            assert result.points == 10
            assert result.quality == "ACCEPTABLE"

        def test_marginal_volume_0_6_and_above(self, scorer):
            """Volume >= 0.6x earns 5 points (MARGINAL)."""
            result = scorer._score_volume(Decimal("0.65"))
            assert result.points == 5
            assert result.quality == "MARGINAL"

        def test_volume_boundary_at_0_3(self, scorer):
            """Boundary: 0.3x exactly is EXCELLENT, not EXCEPTIONAL."""
            result = scorer._score_volume(Decimal("0.3"))
            assert result.points == 30
            assert result.quality == "EXCELLENT"

        def test_volume_boundary_at_0_4(self, scorer):
            """Boundary: 0.4x exactly is IDEAL, not EXCELLENT."""
            result = scorer._score_volume(Decimal("0.4"))
            assert result.points == 20
            assert result.quality == "IDEAL"

    # ================================================================
    # Penetration Scoring Tests (_score_penetration)
    # ================================================================

    class TestScorePenetration:
        """Tests for _score_penetration method."""

        def test_ideal_penetration_1_to_2_percent(self, scorer):
            """Penetration 1-2% earns 35 points (IDEAL)."""
            result = scorer._score_penetration(Decimal("0.015"))
            assert result.points == 35
            assert result.quality == "IDEAL"
            assert result.max_points == 35

        def test_good_penetration_2_to_3_percent(self, scorer):
            """Penetration 2-3% earns 25 points (GOOD)."""
            result = scorer._score_penetration(Decimal("0.025"))
            assert result.points == 25
            assert result.quality == "GOOD"

        def test_acceptable_penetration_3_to_4_percent(self, scorer):
            """Penetration 3-4% earns 15 points (ACCEPTABLE)."""
            result = scorer._score_penetration(Decimal("0.035"))
            assert result.points == 15
            assert result.quality == "ACCEPTABLE"

        def test_deep_penetration_4_to_5_percent(self, scorer):
            """Penetration 4-5% earns 5 points (DEEP)."""
            result = scorer._score_penetration(Decimal("0.045"))
            assert result.points == 5
            assert result.quality == "DEEP"

        def test_penetration_below_1_percent_is_shallow(self, scorer):
            """Penetration < 1% is SHALLOW (valid but less convincing shakeout)."""
            result = scorer._score_penetration(Decimal("0.005"))
            assert result.points == 20
            assert result.quality == "SHALLOW"

        def test_penetration_boundary_at_1_percent(self, scorer):
            """Boundary: 1% exactly is IDEAL."""
            result = scorer._score_penetration(Decimal("0.01"))
            assert result.points == 35
            assert result.quality == "IDEAL"

        def test_penetration_boundary_at_2_percent(self, scorer):
            """Boundary: 2% exactly is GOOD, not IDEAL."""
            result = scorer._score_penetration(Decimal("0.02"))
            assert result.points == 25
            assert result.quality == "GOOD"

    # ================================================================
    # Recovery Scoring Tests (_score_recovery)
    # ================================================================

    class TestScoreRecovery:
        """Tests for _score_recovery method."""

        def test_immediate_recovery_1_bar(self, scorer):
            """Recovery in 1 bar earns 25 points (IMMEDIATE)."""
            result = scorer._score_recovery(1)
            assert result.points == 25
            assert result.quality == "IMMEDIATE"
            assert result.max_points == 25

        def test_strong_recovery_2_bars(self, scorer):
            """Recovery in 2 bars earns 20 points (STRONG)."""
            result = scorer._score_recovery(2)
            assert result.points == 20
            assert result.quality == "STRONG"

        def test_good_recovery_3_bars(self, scorer):
            """Recovery in 3 bars earns 15 points (GOOD)."""
            result = scorer._score_recovery(3)
            assert result.points == 15
            assert result.quality == "GOOD"

        def test_slow_recovery_4_bars(self, scorer):
            """Recovery in 4 bars earns 10 points (SLOW)."""
            result = scorer._score_recovery(4)
            assert result.points == 10
            assert result.quality == "SLOW"

        def test_slow_recovery_5_bars(self, scorer):
            """Recovery in 5+ bars earns 10 points (SLOW)."""
            result = scorer._score_recovery(5)
            assert result.points == 10
            assert result.quality == "SLOW"

    # ================================================================
    # Follow-Through / Test Confirmation Tests (_score_follow_through)
    # ================================================================

    class TestScoreFollowThrough:
        """Tests for _score_follow_through method."""

        def test_test_present_earns_20_points(self, scorer):
            """Test confirmation present earns 20 points."""
            result = scorer._score_follow_through(has_test=True)
            assert result.points == 20
            assert result.quality == "PRESENT"
            assert result.max_points == 20

        def test_no_test_earns_0_points(self, scorer):
            """No test confirmation earns 0 points."""
            result = scorer._score_follow_through(has_test=False)
            assert result.points == 0
            assert result.quality == "NONE"

    # ================================================================
    # Creek Strength Scoring Tests (_score_creek_strength)
    # ================================================================

    class TestScoreCreekStrength:
        """Tests for _score_creek_strength method."""

        def test_excellent_creek_80_plus(self, scorer):
            """Creek strength >= 80 earns 10 points (EXCELLENT)."""
            result = scorer._score_creek_strength(85)
            assert result.points == 10
            assert result.quality == "EXCELLENT"
            assert result.max_points == 10

        def test_strong_creek_70_to_79(self, scorer):
            """Creek strength 70-79 earns 7 points (STRONG)."""
            result = scorer._score_creek_strength(75)
            assert result.points == 7
            assert result.quality == "STRONG"

        def test_moderate_creek_60_to_69(self, scorer):
            """Creek strength 60-69 earns 5 points (MODERATE)."""
            result = scorer._score_creek_strength(65)
            assert result.points == 5
            assert result.quality == "MODERATE"

        def test_weak_creek_below_60(self, scorer):
            """Creek strength < 60 earns 0 points (WEAK)."""
            result = scorer._score_creek_strength(55)
            assert result.points == 0
            assert result.quality == "WEAK"

        def test_creek_boundary_at_80(self, scorer):
            """Boundary: 80 exactly is EXCELLENT."""
            result = scorer._score_creek_strength(80)
            assert result.points == 10
            assert result.quality == "EXCELLENT"

        def test_creek_boundary_at_70(self, scorer):
            """Boundary: 70 exactly is STRONG."""
            result = scorer._score_creek_strength(70)
            assert result.points == 7
            assert result.quality == "STRONG"

    # ================================================================
    # Volume Trend Scoring Tests (_score_volume_trend)
    # ================================================================

    class TestScoreVolumeTrend:
        """Tests for _score_volume_trend method."""

        def test_insufficient_data_less_than_2_tests(self, scorer):
            """Less than 2 previous tests returns 0 points."""
            test1 = MagicMock()
            test1.volume_ratio = Decimal("0.5")

            result = scorer._score_volume_trend(Decimal("0.4"), [test1])
            assert result.points == 0
            assert result.quality == "INSUFFICIENT_DATA"

        def test_declining_volume_trend_earns_10_points(self, scorer):
            """20%+ volume decrease from tests earns 10 points."""
            test1 = MagicMock()
            test1.volume_ratio = Decimal("0.6")
            test2 = MagicMock()
            test2.volume_ratio = Decimal("0.6")

            # Spring volume 0.4 is 33% less than avg 0.6 (>20% decline)
            result = scorer._score_volume_trend(Decimal("0.4"), [test1, test2])
            assert result.points == 10
            assert result.quality == "DECLINING"

        def test_stable_volume_trend_earns_5_points(self, scorer):
            """Stable volume (±20%) earns 5 points."""
            test1 = MagicMock()
            test1.volume_ratio = Decimal("0.5")
            test2 = MagicMock()
            test2.volume_ratio = Decimal("0.5")

            # Spring volume 0.45 is 10% less than avg 0.5 (within ±20%)
            result = scorer._score_volume_trend(Decimal("0.45"), [test1, test2])
            assert result.points == 5
            assert result.quality == "STABLE"

        def test_rising_volume_trend_earns_0_points(self, scorer):
            """Rising volume (>20% increase) earns 0 points."""
            test1 = MagicMock()
            test1.volume_ratio = Decimal("0.4")
            test2 = MagicMock()
            test2.volume_ratio = Decimal("0.4")

            # Spring volume 0.6 is 50% more than avg 0.4 (>20% increase)
            result = scorer._score_volume_trend(Decimal("0.6"), [test1, test2])
            assert result.points == 0
            assert result.quality == "RISING"

        def test_empty_tests_list(self, scorer):
            """Empty tests list returns insufficient data."""
            result = scorer._score_volume_trend(Decimal("0.4"), [])
            assert result.points == 0
            assert result.quality == "INSUFFICIENT_DATA"

        def test_zero_volume_ratio_in_tests(self, scorer):
            """Zero volume ratios in tests returns INVALID_DATA."""
            test1 = MagicMock()
            test1.volume_ratio = Decimal("0")
            test2 = MagicMock()
            test2.volume_ratio = Decimal("0")

            result = scorer._score_volume_trend(Decimal("0.4"), [test1, test2])
            assert result.points == 0
            assert result.quality == "INVALID_DATA"

        def test_negative_volume_ratio_in_tests(self, scorer):
            """Negative volume ratios in tests returns INVALID_DATA."""
            test1 = MagicMock()
            test1.volume_ratio = Decimal("-0.5")
            test2 = MagicMock()
            test2.volume_ratio = Decimal("-0.3")

            result = scorer._score_volume_trend(Decimal("0.4"), [test1, test2])
            assert result.points == 0
            assert result.quality == "INVALID_DATA"

    # ================================================================
    # Quality Tier Tests (_determine_quality_tier)
    # ================================================================

    class TestDetermineQualityTier:
        """Tests for _determine_quality_tier method."""

        def test_excellent_tier_90_plus(self, scorer):
            """Score >= 90 is EXCELLENT."""
            assert scorer._determine_quality_tier(95) == "EXCELLENT"
            assert scorer._determine_quality_tier(90) == "EXCELLENT"

        def test_good_tier_80_to_89(self, scorer):
            """Score 80-89 is GOOD."""
            assert scorer._determine_quality_tier(85) == "GOOD"
            assert scorer._determine_quality_tier(80) == "GOOD"

        def test_acceptable_tier_70_to_79(self, scorer):
            """Score 70-79 is ACCEPTABLE."""
            assert scorer._determine_quality_tier(75) == "ACCEPTABLE"
            assert scorer._determine_quality_tier(70) == "ACCEPTABLE"

        def test_rejected_tier_below_70(self, scorer):
            """Score < 70 is REJECTED."""
            assert scorer._determine_quality_tier(65) == "REJECTED"
            assert scorer._determine_quality_tier(50) == "REJECTED"

    # ================================================================
    # Calculate Method Tests
    # ================================================================

    class TestCalculate:
        """Tests for calculate method (integration of all scoring)."""

        def test_calculate_with_ideal_spring(self, scorer, mock_spring, mock_creek):
            """Test calculate with ideal spring values."""
            test = MagicMock()
            test.volume_ratio = Decimal("0.5")

            result = scorer.calculate(mock_spring, mock_creek, [test])

            assert "total_score" in result
            assert "component_scores" in result
            assert "quality_tier" in result
            assert result["total_score"] <= 100

        def test_calculate_raises_for_none_spring(self, scorer, mock_creek):
            """Calculate raises ValueError if spring is None."""
            with pytest.raises(ValueError, match="Spring required"):
                scorer.calculate(None, mock_creek, [])

        def test_calculate_raises_for_none_creek(self, scorer, mock_spring):
            """Calculate raises ValueError if creek is None."""
            with pytest.raises(ValueError, match="Creek level required"):
                scorer.calculate(mock_spring, None, [])

        def test_calculate_handles_none_previous_tests(self, scorer, mock_spring, mock_creek):
            """Calculate handles None previous_tests gracefully."""
            result = scorer.calculate(mock_spring, mock_creek, None)
            assert result["component_scores"]["test_confirmation"] == 0
            assert result["component_scores"]["volume_trend_bonus"] == 0

        def test_calculate_caps_at_100(self, scorer, mock_creek):
            """Calculate caps total score at 100."""
            # Create spring with maximum scores
            spring = MagicMock()
            spring.volume_ratio = Decimal("0.25")  # EXCEPTIONAL: 40 pts
            spring.penetration_pct = Decimal("0.015")  # IDEAL: 35 pts
            spring.recovery_bars = 1  # IMMEDIATE: 25 pts

            # With test (20 pts) + creek bonus (10 pts) + trend bonus (10 pts)
            # = 140 pts raw, should cap at 100
            test1 = MagicMock()
            test1.volume_ratio = Decimal("0.6")
            test2 = MagicMock()
            test2.volume_ratio = Decimal("0.6")

            result = scorer.calculate(spring, mock_creek, [test1, test2])

            assert result["total_score"] == 100
            assert result["component_scores"]["raw_total"] > 100

        def test_calculate_component_scores_structure(self, scorer, mock_spring, mock_creek):
            """Calculate returns properly structured component scores."""
            result = scorer.calculate(mock_spring, mock_creek, [])

            expected_keys = [
                "volume_quality",
                "penetration_depth",
                "recovery_speed",
                "test_confirmation",
                "creek_strength_bonus",
                "volume_trend_bonus",
                "raw_total",
            ]

            for key in expected_keys:
                assert key in result["component_scores"]

        def test_calculate_excellent_quality_tier(self, scorer, mock_creek):
            """Calculate returns EXCELLENT for score >= 90."""
            spring = MagicMock()
            spring.volume_ratio = Decimal("0.25")  # 40 pts
            spring.penetration_pct = Decimal("0.015")  # 35 pts
            spring.recovery_bars = 1  # 25 pts

            test1 = MagicMock()
            test1.volume_ratio = Decimal("0.5")
            test2 = MagicMock()
            test2.volume_ratio = Decimal("0.5")

            result = scorer.calculate(spring, mock_creek, [test1, test2])
            assert result["quality_tier"] == "EXCELLENT"

        def test_calculate_rejected_quality_tier(self, scorer, mock_creek):
            """Calculate returns REJECTED for score < 70."""
            spring = MagicMock()
            spring.volume_ratio = Decimal("0.65")  # 5 pts (MARGINAL)
            spring.penetration_pct = Decimal("0.045")  # 5 pts (DEEP)
            spring.recovery_bars = 5  # 10 pts (SLOW)

            # No tests = 0 pts for confirmation and trend
            # Creek bonus = 10 pts
            # Total = 5 + 5 + 10 + 0 + 10 + 0 = 30 pts

            result = scorer.calculate(spring, mock_creek, [])
            assert result["quality_tier"] == "REJECTED"
            assert result["total_score"] < 70
