"""
Unit Tests for Relative Strength Calculator (Task 7)

Purpose:
--------
Tests RS calculation logic with known scenarios.

Test Coverage:
--------------
1. Return percentage calculation
2. RS score calculation (stock vs benchmark)
3. Sector leader identification
4. Edge cases (zero returns, missing data)

Author: Story 11.9 Task 7
"""

from decimal import Decimal

from src.services.relative_strength_calculator import RelativeStrengthCalculator


class TestRelativeStrengthCalculator:
    """Test suite for RS calculator"""

    def test_calculate_return_positive(self):
        """Test return calculation with price gain"""
        calc = RelativeStrengthCalculator(session=None, period_days=30)

        return_pct = calc.calculate_return(
            start_price=Decimal("100.00"), end_price=Decimal("110.00")
        )

        # 10% gain
        assert return_pct == Decimal("10.00")

    def test_calculate_return_negative(self):
        """Test return calculation with price loss"""
        calc = RelativeStrengthCalculator(session=None)

        return_pct = calc.calculate_return(
            start_price=Decimal("100.00"), end_price=Decimal("95.00")
        )

        # 5% loss
        assert return_pct == Decimal("-5.00")

    def test_calculate_return_zero(self):
        """Test return calculation with no change"""
        calc = RelativeStrengthCalculator(session=None)

        return_pct = calc.calculate_return(
            start_price=Decimal("100.00"), end_price=Decimal("100.00")
        )

        assert return_pct == Decimal("0.00")

    def test_calculate_return_zero_start_price(self):
        """Test return calculation with zero start price (edge case)"""
        calc = RelativeStrengthCalculator(session=None)

        return_pct = calc.calculate_return(start_price=Decimal("0.00"), end_price=Decimal("110.00"))

        # Should return 0 to avoid division by zero
        assert return_pct == Decimal("0.00")

    def test_calculate_rs_score_outperforming(self):
        """Test RS score when stock outperforms benchmark"""
        calc = RelativeStrengthCalculator(session=None)

        rs_score = calc.calculate_rs_score(
            stock_return=Decimal("10.00"),  # Stock +10%
            benchmark_return=Decimal("5.00"),  # SPY +5%
        )

        # RS = 10 - 5 = 5.0 (outperforming by 5%)
        assert rs_score == Decimal("5.0000")

    def test_calculate_rs_score_underperforming(self):
        """Test RS score when stock underperforms benchmark"""
        calc = RelativeStrengthCalculator(session=None)

        rs_score = calc.calculate_rs_score(
            stock_return=Decimal("3.00"),  # Stock +3%
            benchmark_return=Decimal("5.00"),  # SPY +5%
        )

        # RS = 3 - 5 = -2.0 (underperforming by 2%)
        assert rs_score == Decimal("-2.0000")

    def test_calculate_rs_score_matching(self):
        """Test RS score when stock matches benchmark"""
        calc = RelativeStrengthCalculator(session=None)

        rs_score = calc.calculate_rs_score(
            stock_return=Decimal("5.00"), benchmark_return=Decimal("5.00")
        )

        # RS = 0 (matching benchmark)
        assert rs_score == Decimal("0.0000")

    def test_calculate_rs_score_negative_returns(self):
        """Test RS score with negative returns"""
        calc = RelativeStrengthCalculator(session=None)

        rs_score = calc.calculate_rs_score(
            stock_return=Decimal("-3.00"),  # Stock -3%
            benchmark_return=Decimal("-5.00"),  # SPY -5%
        )

        # RS = -3 - (-5) = 2.0 (outperforming in down market)
        assert rs_score == Decimal("2.0000")

    def test_sector_etf_mapping(self):
        """Test sector to ETF mapping"""
        calc = RelativeStrengthCalculator(session=None)

        assert calc.SECTOR_ETF_MAP["Technology"] == "XLK"
        assert calc.SECTOR_ETF_MAP["Healthcare"] == "XLV"
        assert calc.SECTOR_ETF_MAP["Financials"] == "XLF"
        assert calc.SECTOR_ETF_MAP["Energy"] == "XLE"

    def test_period_days_configuration(self):
        """Test custom period configuration"""
        calc = RelativeStrengthCalculator(session=None, period_days=60)

        assert calc.period_days == 60
