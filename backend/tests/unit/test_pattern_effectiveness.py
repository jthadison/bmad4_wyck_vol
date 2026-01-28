"""
Unit tests for Pattern Effectiveness (Story 19.19)

Tests pattern effectiveness models, Wilson score calculation,
and profit factor computation.

Author: Story 19.19
"""

from datetime import date
from decimal import Decimal

import pytest

from src.models.pattern_effectiveness import (
    ConfidenceInterval,
    DateRange,
    PatternEffectiveness,
    PatternEffectivenessResponse,
)
from src.services.pattern_effectiveness_service import (
    calculate_profit_factor,
    wilson_score_interval,
)


class TestWilsonScoreInterval:
    """Test Wilson score confidence interval calculation."""

    def test_wilson_score_typical_case(self):
        """Test Wilson score with typical win rate (52 wins out of 70)."""
        wins = 52
        total = 70

        lower, upper = wilson_score_interval(wins, total)

        # With 52/70 (74.3% win rate), 95% CI should be approximately 62-84%
        assert lower == pytest.approx(63.16, rel=0.02)
        assert upper == pytest.approx(83.29, rel=0.02)

    def test_wilson_score_zero_trades(self):
        """Test Wilson score returns (0, 0) when no trades."""
        lower, upper = wilson_score_interval(0, 0)

        assert lower == 0.0
        assert upper == 0.0

    def test_wilson_score_all_wins(self):
        """Test Wilson score with 100% win rate."""
        wins = 10
        total = 10

        lower, upper = wilson_score_interval(wins, total)

        # Should have narrow CI near 100%
        assert lower > 70.0
        assert upper == pytest.approx(100.0, rel=0.01)

    def test_wilson_score_all_losses(self):
        """Test Wilson score with 0% win rate."""
        wins = 0
        total = 10

        lower, upper = wilson_score_interval(wins, total)

        # Should have narrow CI near 0%
        assert lower == pytest.approx(0.0, rel=0.01)
        assert upper < 30.0

    def test_wilson_score_50_percent(self):
        """Test Wilson score with 50% win rate."""
        wins = 50
        total = 100

        lower, upper = wilson_score_interval(wins, total)

        # 50/100 should have CI roughly 40-60%
        assert lower > 35.0
        assert lower < 50.0
        assert upper > 50.0
        assert upper < 65.0

    def test_wilson_score_small_sample(self):
        """Test Wilson score with small sample (wide CI expected)."""
        wins = 2
        total = 5

        lower, upper = wilson_score_interval(wins, total)

        # Small sample = wide confidence interval
        assert (upper - lower) > 30.0

    def test_wilson_score_large_sample(self):
        """Test Wilson score with large sample (narrow CI expected)."""
        wins = 600
        total = 1000

        lower, upper = wilson_score_interval(wins, total)

        # Large sample = narrow confidence interval
        assert (upper - lower) < 10.0
        assert lower > 55.0
        assert upper < 65.0

    def test_wilson_score_bounds_never_exceed_0_100(self):
        """Test Wilson score bounds are always in [0, 100]."""
        test_cases = [
            (0, 1),
            (1, 1),
            (0, 100),
            (100, 100),
            (1, 2),
            (99, 100),
        ]

        for wins, total in test_cases:
            lower, upper = wilson_score_interval(wins, total)
            assert lower >= 0.0, f"Lower bound < 0 for {wins}/{total}"
            assert upper <= 100.0, f"Upper bound > 100 for {wins}/{total}"
            assert lower <= upper, f"Lower > upper for {wins}/{total}"


class TestProfitFactor:
    """Test profit factor calculation."""

    def test_profit_factor_typical_case(self):
        """Test profit factor with typical values."""
        gross_profit = Decimal("5000.00")
        gross_loss = Decimal("2500.00")

        pf = calculate_profit_factor(gross_profit, gross_loss)

        assert pf == pytest.approx(2.0, rel=0.01)

    def test_profit_factor_excellent(self):
        """Test profit factor > 2.0 (excellent)."""
        gross_profit = Decimal("10000.00")
        gross_loss = Decimal("2000.00")

        pf = calculate_profit_factor(gross_profit, gross_loss)

        assert pf == pytest.approx(5.0, rel=0.01)
        assert pf > 2.0  # Excellent

    def test_profit_factor_marginal(self):
        """Test profit factor between 1.0 and 1.5 (marginal)."""
        gross_profit = Decimal("1200.00")
        gross_loss = Decimal("1000.00")

        pf = calculate_profit_factor(gross_profit, gross_loss)

        assert pf == pytest.approx(1.2, rel=0.01)
        assert 1.0 <= pf < 1.5  # Marginal

    def test_profit_factor_unprofitable(self):
        """Test profit factor < 1.0 (unprofitable)."""
        gross_profit = Decimal("500.00")
        gross_loss = Decimal("1000.00")

        pf = calculate_profit_factor(gross_profit, gross_loss)

        assert pf == pytest.approx(0.5, rel=0.01)
        assert pf < 1.0  # Unprofitable

    def test_profit_factor_no_losses(self):
        """Test profit factor is infinity when no losses."""
        gross_profit = Decimal("1000.00")
        gross_loss = Decimal("0.00")

        pf = calculate_profit_factor(gross_profit, gross_loss)

        assert pf == float("inf")

    def test_profit_factor_no_profit_no_loss(self):
        """Test profit factor is 0 when no profit and no loss."""
        gross_profit = Decimal("0.00")
        gross_loss = Decimal("0.00")

        pf = calculate_profit_factor(gross_profit, gross_loss)

        assert pf == 0.0

    def test_profit_factor_no_profit_has_loss(self):
        """Test profit factor is 0 when no profit but has losses."""
        gross_profit = Decimal("0.00")
        gross_loss = Decimal("500.00")

        pf = calculate_profit_factor(gross_profit, gross_loss)

        assert pf == 0.0


class TestPatternEffectivenessModels:
    """Test Pydantic models for pattern effectiveness."""

    def test_confidence_interval_creation(self):
        """Test ConfidenceInterval model creation."""
        ci = ConfidenceInterval(lower=62.5, upper=84.3)

        assert ci.lower == 62.5
        assert ci.upper == 84.3

    def test_confidence_interval_validation_bounds(self):
        """Test ConfidenceInterval validates bounds are 0-100."""
        with pytest.raises(ValueError):
            ConfidenceInterval(lower=-10.0, upper=50.0)

        with pytest.raises(ValueError):
            ConfidenceInterval(lower=50.0, upper=110.0)

    def test_pattern_effectiveness_creation(self):
        """Test PatternEffectiveness model creation."""
        pattern = PatternEffectiveness(
            pattern_type="SPRING",
            signals_generated=100,
            signals_approved=85,
            signals_executed=70,
            signals_closed=60,
            signals_profitable=42,
            win_rate=70.0,
            win_rate_ci=ConfidenceInterval(lower=57.5, upper=80.2),
            avg_r_winners=3.2,
            avg_r_losers=-1.0,
            avg_r_overall=1.5,
            max_r_winner=8.5,
            max_r_loser=-1.0,
            profit_factor=2.4,
            total_pnl=Decimal("15000.00"),
            avg_pnl_per_trade=Decimal("250.00"),
            approval_rate=85.0,
            execution_rate=82.35,
        )

        assert pattern.pattern_type == "SPRING"
        assert pattern.signals_generated == 100
        assert pattern.win_rate == 70.0
        assert pattern.win_rate_ci.lower == 57.5
        assert pattern.profit_factor == 2.4
        assert pattern.total_pnl == Decimal("15000.00")

    def test_pattern_effectiveness_validation_rates(self):
        """Test PatternEffectiveness validates rates are 0-100."""
        with pytest.raises(ValueError):
            PatternEffectiveness(
                pattern_type="SPRING",
                signals_generated=100,
                signals_approved=85,
                signals_executed=70,
                signals_closed=60,
                signals_profitable=42,
                win_rate=150.0,  # Invalid: > 100
                win_rate_ci=ConfidenceInterval(lower=50.0, upper=80.0),
                avg_r_winners=3.2,
                avg_r_losers=-1.0,
                avg_r_overall=1.5,
                max_r_winner=8.5,
                max_r_loser=-1.0,
                profit_factor=2.4,
                total_pnl=Decimal("15000.00"),
                avg_pnl_per_trade=Decimal("250.00"),
                approval_rate=85.0,
                execution_rate=82.35,
            )

    def test_pattern_effectiveness_negative_counts(self):
        """Test PatternEffectiveness validates counts are non-negative."""
        with pytest.raises(ValueError):
            PatternEffectiveness(
                pattern_type="SPRING",
                signals_generated=-1,  # Invalid: negative
                signals_approved=85,
                signals_executed=70,
                signals_closed=60,
                signals_profitable=42,
                win_rate=70.0,
                win_rate_ci=ConfidenceInterval(lower=50.0, upper=80.0),
                avg_r_winners=3.2,
                avg_r_losers=-1.0,
                avg_r_overall=1.5,
                max_r_winner=8.5,
                max_r_loser=-1.0,
                profit_factor=2.4,
                total_pnl=Decimal("15000.00"),
                avg_pnl_per_trade=Decimal("250.00"),
                approval_rate=85.0,
                execution_rate=82.35,
            )

    def test_pattern_effectiveness_response_creation(self):
        """Test PatternEffectivenessResponse model creation."""
        pattern = PatternEffectiveness(
            pattern_type="SPRING",
            signals_generated=100,
            signals_approved=85,
            signals_executed=70,
            signals_closed=60,
            signals_profitable=42,
            win_rate=70.0,
            win_rate_ci=ConfidenceInterval(lower=57.5, upper=80.2),
            avg_r_winners=3.2,
            avg_r_losers=-1.0,
            avg_r_overall=1.5,
            max_r_winner=8.5,
            max_r_loser=-1.0,
            profit_factor=2.4,
            total_pnl=Decimal("15000.00"),
            avg_pnl_per_trade=Decimal("250.00"),
            approval_rate=85.0,
            execution_rate=82.35,
        )

        response = PatternEffectivenessResponse(
            patterns=[pattern],
            date_range=DateRange(
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 27),
            ),
        )

        assert len(response.patterns) == 1
        assert response.patterns[0].pattern_type == "SPRING"
        assert response.date_range.start_date == date(2026, 1, 1)

    def test_pattern_effectiveness_json_serialization(self):
        """Test PatternEffectivenessResponse JSON serialization."""
        pattern = PatternEffectiveness(
            pattern_type="SOS",
            signals_generated=50,
            signals_approved=40,
            signals_executed=35,
            signals_closed=30,
            signals_profitable=18,
            win_rate=60.0,
            win_rate_ci=ConfidenceInterval(lower=42.5, upper=75.3),
            avg_r_winners=2.8,
            avg_r_losers=-1.0,
            avg_r_overall=0.9,
            max_r_winner=6.0,
            max_r_loser=-1.0,
            profit_factor=1.68,
            total_pnl=Decimal("8500.50"),
            avg_pnl_per_trade=Decimal("283.35"),
            approval_rate=80.0,
            execution_rate=87.5,
        )

        response = PatternEffectivenessResponse(
            patterns=[pattern],
            date_range=DateRange(
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 27),
            ),
        )

        json_data = response.model_dump(mode="json")

        assert json_data["patterns"][0]["pattern_type"] == "SOS"
        assert json_data["patterns"][0]["total_pnl"] == "8500.50"
        assert json_data["patterns"][0]["win_rate_ci"]["lower"] == 42.5
        assert json_data["date_range"]["start_date"] == "2026-01-01"


class TestFunnelMetricsCalculations:
    """Test funnel metrics calculations."""

    def test_approval_rate_calculation(self):
        """Test approval rate: approved / generated * 100."""
        generated = 100
        approved = 85

        approval_rate = (approved / generated * 100) if generated > 0 else 0.0

        assert approval_rate == 85.0

    def test_execution_rate_calculation(self):
        """Test execution rate: executed / approved * 100."""
        approved = 85
        executed = 70

        execution_rate = (executed / approved * 100) if approved > 0 else 0.0

        assert execution_rate == pytest.approx(82.35, rel=0.01)

    def test_approval_rate_zero_generated(self):
        """Test approval rate is 0 when no signals generated."""
        generated = 0
        approved = 0

        approval_rate = (approved / generated * 100) if generated > 0 else 0.0

        assert approval_rate == 0.0

    def test_execution_rate_zero_approved(self):
        """Test execution rate is 0 when no signals approved."""
        approved = 0
        executed = 0

        execution_rate = (executed / approved * 100) if approved > 0 else 0.0

        assert execution_rate == 0.0


class TestRMultipleCalculations:
    """Test R-multiple related calculations."""

    def test_average_r_multiple_winners(self):
        """Test average R-multiple for winning trades."""
        r_multiples = [2.5, 3.0, 4.2, 1.8, 2.0]
        avg_r = sum(r_multiples) / len(r_multiples)

        assert avg_r == pytest.approx(2.7, rel=0.01)

    def test_average_r_multiple_losers(self):
        """Test average R-multiple for losing trades (should be negative)."""
        r_multiples = [-1.0, -1.0, -0.8, -1.0, -0.5]
        avg_r = sum(r_multiples) / len(r_multiples)

        assert avg_r == pytest.approx(-0.86, rel=0.01)
        assert avg_r < 0  # Should be negative for losers

    def test_overall_r_multiple_calculation(self):
        """Test overall R-multiple (all trades combined)."""
        winners = [2.5, 3.0, 4.2]
        losers = [-1.0, -1.0, -0.8]
        all_r = winners + losers
        avg_r = sum(all_r) / len(all_r)

        assert avg_r == pytest.approx(1.15, rel=0.01)
        assert avg_r > 0  # Should be positive overall (profitable)
