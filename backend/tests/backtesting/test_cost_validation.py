"""
Unit Tests for Cost Validator (Story 12.5).

Tests validation of transaction costs and R-multiple degradation.

Author: Story 12.5 QA - Unit Testing
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.cost_validation import CostValidator
from src.models.backtest import (
    BacktestConfig,
    BacktestCostSummary,
    BacktestMetrics,
    BacktestResult,
)


class TestCostValidator:
    """Unit tests for CostValidator."""

    @pytest.fixture
    def validator(self):
        """Create CostValidator instance."""
        return CostValidator()

    @pytest.fixture
    def realistic_cost_summary(self):
        """Create realistic cost summary for testing."""
        return BacktestCostSummary(
            total_trades=10,
            total_commission_paid=Decimal("50.00"),
            total_slippage_cost=Decimal("30.00"),
            total_transaction_costs=Decimal("80.00"),
            avg_commission_per_trade=Decimal("5.00"),
            avg_slippage_per_trade=Decimal("3.00"),
            avg_transaction_cost_per_trade=Decimal("8.00"),
            cost_as_pct_of_total_pnl=Decimal("5.0"),
            gross_avg_r_multiple=Decimal("2.5"),
            net_avg_r_multiple=Decimal("2.2"),
            r_multiple_degradation=Decimal("0.3"),
        )

    # Test 1: Validate realistic R-multiple degradation (3-20%)
    def test_validate_realistic_r_multiple_degradation(self, validator, realistic_cost_summary):
        """Test validation of realistic R-multiple degradation."""
        is_valid, warnings = validator.validate_r_multiple_degradation(realistic_cost_summary)

        # 12% degradation (0.3R / 2.5R) should be valid
        assert is_valid is True
        assert len(warnings) == 0

    # Test 2: Warn on zero R-multiple degradation
    def test_warn_on_zero_degradation(self, validator):
        """Test warning when R-multiple degradation is zero."""
        cost_summary = BacktestCostSummary(
            total_trades=10,
            total_commission_paid=Decimal("0"),
            total_slippage_cost=Decimal("0"),
            total_transaction_costs=Decimal("0"),
            avg_commission_per_trade=Decimal("0"),
            avg_slippage_per_trade=Decimal("0"),
            avg_transaction_cost_per_trade=Decimal("0"),
            cost_as_pct_of_total_pnl=Decimal("0"),
            gross_avg_r_multiple=Decimal("2.5"),
            net_avg_r_multiple=Decimal("2.5"),  # Same as gross
            r_multiple_degradation=Decimal("0"),  # Zero degradation
        )

        is_valid, warnings = validator.validate_r_multiple_degradation(cost_summary)

        # Should be invalid (error, not warning)
        assert is_valid is False
        assert len(warnings) > 0
        assert "0%" in warnings[0] and "transaction costs not applied" in warnings[0].lower()

    # Test 3: Warn on unrealistically low degradation (<3%)
    def test_warn_on_low_degradation(self, validator):
        """Test warning when degradation is unrealistically low."""
        cost_summary = BacktestCostSummary(
            total_trades=10,
            total_commission_paid=Decimal("10.00"),
            total_slippage_cost=Decimal("5.00"),
            total_transaction_costs=Decimal("15.00"),
            avg_commission_per_trade=Decimal("1.00"),
            avg_slippage_per_trade=Decimal("0.50"),
            avg_transaction_cost_per_trade=Decimal("1.50"),
            cost_as_pct_of_total_pnl=Decimal("1.0"),
            gross_avg_r_multiple=Decimal("2.5"),
            net_avg_r_multiple=Decimal("2.48"),  # 0.02R degradation = 0.8%
            r_multiple_degradation=Decimal("0.02"),
        )

        is_valid, warnings = validator.validate_r_multiple_degradation(cost_summary)

        # Should generate warning for suspiciously low degradation
        assert is_valid is True  # Still valid, just a warning
        assert len(warnings) > 0
        assert "unusually low" in warnings[0].lower()

    # Test 4: Warn on unrealistically high degradation (>20%)
    def test_warn_on_high_degradation(self, validator):
        """Test warning when degradation is unrealistically high."""
        cost_summary = BacktestCostSummary(
            total_trades=10,
            total_commission_paid=Decimal("500.00"),
            total_slippage_cost=Decimal("300.00"),
            total_transaction_costs=Decimal("800.00"),
            avg_commission_per_trade=Decimal("50.00"),
            avg_slippage_per_trade=Decimal("30.00"),
            avg_transaction_cost_per_trade=Decimal("80.00"),
            cost_as_pct_of_total_pnl=Decimal("40.0"),
            gross_avg_r_multiple=Decimal("2.5"),
            net_avg_r_multiple=Decimal("1.75"),  # 0.75R degradation = 30%
            r_multiple_degradation=Decimal("0.75"),
        )

        is_valid, warnings = validator.validate_r_multiple_degradation(cost_summary)

        # Should generate warning for excessively high degradation
        assert is_valid is True  # Still valid, just a warning
        assert len(warnings) > 0
        assert "unusually high" in warnings[0].lower()

    # Test 5: Validate realistic commission costs
    def test_validate_realistic_commission_costs(self, validator, realistic_cost_summary):
        """Test validation of realistic commission costs."""
        is_valid, warnings = validator.validate_commission_costs(realistic_cost_summary)

        # $5 average commission is realistic for IB retail
        assert is_valid is True
        assert len(warnings) == 0

    # Test 6: Accept zero commission (zero-commission brokers exist)
    def test_accept_zero_commission(self, validator):
        """Test that zero commission is accepted (zero-commission brokers exist)."""
        cost_summary = BacktestCostSummary(
            total_trades=10,
            total_commission_paid=Decimal("0"),
            total_slippage_cost=Decimal("30.00"),
            total_transaction_costs=Decimal("30.00"),
            avg_commission_per_trade=Decimal("0"),
            avg_slippage_per_trade=Decimal("3.00"),
            avg_transaction_cost_per_trade=Decimal("3.00"),
            cost_as_pct_of_total_pnl=Decimal("2.0"),
            gross_avg_r_multiple=Decimal("2.5"),
            net_avg_r_multiple=Decimal("2.4"),
            r_multiple_degradation=Decimal("0.1"),
        )

        is_valid, warnings = validator.validate_commission_costs(cost_summary)

        # Zero commission is valid (Robinhood, TD Ameritrade, etc.)
        assert is_valid is True
        assert len(warnings) == 0

    # Test 7: Warn on unusually high commission
    def test_warn_on_high_commission(self, validator):
        """Test warning on unusually high commission costs."""
        cost_summary = BacktestCostSummary(
            total_trades=10,
            total_commission_paid=Decimal("600.00"),
            total_slippage_cost=Decimal("30.00"),
            total_transaction_costs=Decimal("630.00"),
            avg_commission_per_trade=Decimal("60.00"),  # $60 per trade is unusually high
            avg_slippage_per_trade=Decimal("3.00"),
            avg_transaction_cost_per_trade=Decimal("63.00"),
            cost_as_pct_of_total_pnl=Decimal("40.0"),
            gross_avg_r_multiple=Decimal("2.5"),
            net_avg_r_multiple=Decimal("1.8"),
            r_multiple_degradation=Decimal("0.7"),
        )

        is_valid, warnings = validator.validate_commission_costs(cost_summary)

        # Should warn about unusually high commission
        assert is_valid is True  # Still valid, just a warning
        assert len(warnings) > 0
        assert "unusually high" in warnings[0].lower()

    # Test 8: Validate realistic slippage costs
    def test_validate_realistic_slippage_costs(self, validator, realistic_cost_summary):
        """Test validation of realistic slippage costs."""
        is_valid, warnings = validator.validate_slippage_costs(realistic_cost_summary)

        # $3 average slippage is realistic
        assert is_valid is True
        assert len(warnings) == 0

    # Test 9: Accept zero slippage (limit orders)
    def test_accept_zero_slippage(self, validator):
        """Test that zero slippage is acceptable (limit orders)."""
        cost_summary = BacktestCostSummary(
            total_trades=10,
            total_commission_paid=Decimal("50.00"),
            total_slippage_cost=Decimal("0"),  # Zero slippage (limit orders)
            total_transaction_costs=Decimal("50.00"),
            avg_commission_per_trade=Decimal("5.00"),
            avg_slippage_per_trade=Decimal("0"),
            avg_transaction_cost_per_trade=Decimal("5.00"),
            cost_as_pct_of_total_pnl=Decimal("3.0"),
            gross_avg_r_multiple=Decimal("2.5"),
            net_avg_r_multiple=Decimal("2.4"),
            r_multiple_degradation=Decimal("0.1"),
        )

        is_valid, warnings = validator.validate_slippage_costs(cost_summary)

        # Zero slippage is valid (limit orders)
        assert is_valid is True

    # Test 10: Warn on unusually high slippage
    def test_warn_on_high_slippage(self, validator):
        """Test warning on unusually high slippage costs."""
        cost_summary = BacktestCostSummary(
            total_trades=10,
            total_commission_paid=Decimal("50.00"),
            total_slippage_cost=Decimal("1200.00"),  # $120 per trade average
            total_transaction_costs=Decimal("1250.00"),
            avg_commission_per_trade=Decimal("5.00"),
            avg_slippage_per_trade=Decimal("120.00"),  # Unusually high
            avg_transaction_cost_per_trade=Decimal("125.00"),
            cost_as_pct_of_total_pnl=Decimal("60.0"),
            gross_avg_r_multiple=Decimal("2.5"),
            net_avg_r_multiple=Decimal("1.5"),
            r_multiple_degradation=Decimal("1.0"),
        )

        is_valid, warnings = validator.validate_slippage_costs(cost_summary)

        # Should warn about unusually high slippage
        assert len(warnings) > 0
        assert "unusually high" in warnings[0].lower() or "liquidity issues" in warnings[0].lower()

    # Test 11: Validate balanced cost distribution
    def test_validate_balanced_cost_distribution(self, validator, realistic_cost_summary):
        """Test validation of balanced commission/slippage distribution."""
        is_valid, warnings = validator.validate_cost_distribution(realistic_cost_summary)

        # $50 commission / $30 slippage = 1.67 ratio is reasonable
        assert is_valid is True
        assert len(warnings) == 0

    # Test 12: Warn on commission-dominated costs
    def test_warn_on_commission_dominated_costs(self, validator):
        """Test warning when commissions dominate costs excessively."""
        cost_summary = BacktestCostSummary(
            total_trades=10,
            total_commission_paid=Decimal("500.00"),
            total_slippage_cost=Decimal("10.00"),  # Very low slippage
            total_transaction_costs=Decimal("510.00"),
            avg_commission_per_trade=Decimal("50.00"),
            avg_slippage_per_trade=Decimal("1.00"),
            avg_transaction_cost_per_trade=Decimal("51.00"),
            cost_as_pct_of_total_pnl=Decimal("30.0"),
            gross_avg_r_multiple=Decimal("2.5"),
            net_avg_r_multiple=Decimal("2.0"),
            r_multiple_degradation=Decimal("0.5"),
        )

        is_valid, warnings = validator.validate_cost_distribution(cost_summary)

        # Should warn about commission dominating costs
        assert len(warnings) > 0

    # Test 13: Test AC10 compliance validation (2.5R → 2.2R)
    def test_ac10_compliance_validation(self, validator, realistic_cost_summary):
        """Test AC10 compliance validation (2.5R → 2.2R target)."""
        is_valid, warnings = validator.validate_ac10_compliance(realistic_cost_summary)

        # Should validate AC10 target (2.5R → 2.2R = 12% degradation)
        assert is_valid is True

    # Test 14: Full backtest validation with all checks
    def test_full_backtest_validation(self, validator):
        """Test full backtest validation with all checks."""
        backtest_result = BacktestResult(
            backtest_run_id=uuid4(),
            symbol="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            config=BacktestConfig(
                symbol="AAPL",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
            ),
            trades=[],
            metrics=BacktestMetrics(),
            cost_summary=BacktestCostSummary(
                total_trades=10,
                total_commission_paid=Decimal("50.00"),
                total_slippage_cost=Decimal("30.00"),
                total_transaction_costs=Decimal("80.00"),
                avg_commission_per_trade=Decimal("5.00"),
                avg_slippage_per_trade=Decimal("3.00"),
                avg_transaction_cost_per_trade=Decimal("8.00"),
                cost_as_pct_of_total_pnl=Decimal("5.0"),
                gross_avg_r_multiple=Decimal("2.5"),
                net_avg_r_multiple=Decimal("2.2"),
                r_multiple_degradation=Decimal("0.3"),
            ),
        )

        validation_report = validator.validate_full_backtest(backtest_result)

        # Verify report structure
        assert "is_valid" in validation_report
        assert "errors" in validation_report
        assert "warnings" in validation_report
        assert "recommendations" in validation_report
        assert "cost_summary" in validation_report

        # Should be valid with realistic costs
        assert validation_report["is_valid"] is True
        assert len(validation_report["errors"]) == 0

    # Test 15: Full validation with missing cost summary
    def test_full_validation_missing_cost_summary(self, validator):
        """Test full validation when cost summary is missing."""
        backtest_result = BacktestResult(
            backtest_run_id=uuid4(),
            symbol="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            config=BacktestConfig(
                symbol="AAPL",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
            ),
            trades=[],
            metrics=BacktestMetrics(),
            cost_summary=None,  # Missing cost summary
        )

        validation_report = validator.validate_full_backtest(backtest_result)

        # Should not be valid
        assert validation_report["is_valid"] is False
        assert len(validation_report["errors"]) > 0
        assert "No cost summary available" in validation_report["errors"][0]
