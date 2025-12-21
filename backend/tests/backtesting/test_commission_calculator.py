"""
Unit Tests for Commission Calculator (Story 12.5 Task 15.1).

Tests all commission calculation methods, edge cases, and validation.

Author: Story 12.5 Task 15
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.commission_calculator import CommissionCalculator
from src.models.backtest import BacktestOrder, CommissionConfig


class TestCommissionCalculator:
    """Unit tests for CommissionCalculator."""

    @pytest.fixture
    def calculator(self):
        """Create CommissionCalculator instance."""
        return CommissionCalculator()

    @pytest.fixture
    def sample_order(self):
        """Create sample BacktestOrder."""
        return BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=1000,
            created_bar_timestamp=datetime.now(UTC),
            fill_price=Decimal("150.00"),
            status="FILLED",
        )

    # Subtask 15.1.1: Test per-share commission calculation
    def test_per_share_commission_basic(self, calculator, sample_order):
        """Test basic per-share commission calculation."""
        config = CommissionConfig(
            commission_type="PER_SHARE",
            commission_per_share=Decimal("0.005"),
            min_commission=Decimal("1.00"),
        )

        commission, breakdown = calculator.calculate_commission(sample_order, config)

        # 1000 shares * $0.005 = $5.00
        assert commission == Decimal("5.00")
        assert breakdown.base_commission == Decimal("5.00")
        assert breakdown.applied_commission == Decimal("5.00")
        assert breakdown.commission_type == "PER_SHARE"

    # Subtask 15.1.2: Test per-share commission with minimum cap
    def test_per_share_commission_min_cap(self, calculator):
        """Test per-share commission with minimum cap applied."""
        # Small order that triggers min commission
        small_order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=100,  # 100 shares
            created_bar_timestamp=datetime.now(UTC),
            fill_price=Decimal("50.00"),
            status="FILLED",
        )

        config = CommissionConfig(
            commission_type="PER_SHARE",
            commission_per_share=Decimal("0.005"),
            min_commission=Decimal("1.00"),
        )

        commission, breakdown = calculator.calculate_commission(small_order, config)

        # 100 shares * $0.005 = $0.50, but min is $1.00
        assert commission == Decimal("1.00")
        assert breakdown.base_commission == Decimal("0.50")
        assert breakdown.applied_commission == Decimal("1.00")

    # Subtask 15.1.3: Test per-share commission with maximum cap
    def test_per_share_commission_max_cap(self, calculator):
        """Test per-share commission with maximum cap applied."""
        # Large order that triggers max commission
        large_order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=50000,  # 50,000 shares
            created_bar_timestamp=datetime.now(UTC),
            fill_price=Decimal("100.00"),
            status="FILLED",
        )

        config = CommissionConfig(
            commission_type="PER_SHARE",
            commission_per_share=Decimal("0.005"),
            min_commission=Decimal("1.00"),
            max_commission=Decimal("100.00"),
        )

        commission, breakdown = calculator.calculate_commission(large_order, config)

        # 50,000 shares * $0.005 = $250, but max is $100
        assert commission == Decimal("100.00")
        assert breakdown.base_commission == Decimal("250.00")
        assert breakdown.applied_commission == Decimal("100.00")

    # Subtask 15.1.4: Test percentage-based commission
    def test_percentage_commission_basic(self, calculator, sample_order):
        """Test basic percentage-based commission calculation."""
        config = CommissionConfig(
            commission_type="PERCENTAGE",
            commission_percentage=Decimal("0.001"),  # 0.1%
            min_commission=Decimal("0"),
        )

        commission, breakdown = calculator.calculate_commission(sample_order, config)

        # 1000 shares * $150 = $150,000 order value
        # $150,000 * 0.001 = $150 commission
        assert commission == Decimal("150.00")
        assert breakdown.commission_type == "PERCENTAGE"

    # Subtask 15.1.5: Test fixed commission
    def test_fixed_commission(self, calculator, sample_order):
        """Test fixed commission calculation."""
        config = CommissionConfig(
            commission_type="FIXED",
            fixed_commission_per_trade=Decimal("10.00"),
            min_commission=Decimal("0"),
        )

        commission, breakdown = calculator.calculate_commission(sample_order, config)

        assert commission == Decimal("10.00")
        assert breakdown.commission_type == "FIXED"

    # Subtask 15.1.6: Test zero commission (Robinhood-style)
    def test_zero_commission(self, calculator, sample_order):
        """Test zero commission (commission-free broker)."""
        config = CommissionConfig(
            commission_type="FIXED",
            fixed_commission_per_trade=Decimal("0"),
            min_commission=Decimal("0"),
        )

        commission, breakdown = calculator.calculate_commission(sample_order, config)

        assert commission == Decimal("0")
        assert breakdown.applied_commission == Decimal("0")

    # Subtask 15.1.7: Test commission breakdown structure
    def test_commission_breakdown_structure(self, calculator, sample_order):
        """Test commission breakdown contains all required fields."""
        config = CommissionConfig(
            commission_type="PER_SHARE",
            commission_per_share=Decimal("0.005"),
            broker_name="Interactive Brokers Retail",
        )

        commission, breakdown = calculator.calculate_commission(sample_order, config)

        assert breakdown.order_id == sample_order.order_id
        assert breakdown.shares == sample_order.quantity
        assert breakdown.base_commission > Decimal("0")
        assert breakdown.applied_commission == commission
        assert breakdown.commission_type == "PER_SHARE"
        assert breakdown.broker_name == "Interactive Brokers Retail"

    # Subtask 15.1.8: Test edge case - zero shares (should not happen but handle gracefully)
    def test_zero_shares_edge_case(self, calculator):
        """Test edge case with zero shares."""
        zero_order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=1,  # Changed from 0 to 1 - Pydantic requires quantity > 0
            created_bar_timestamp=datetime.now(UTC),
            fill_price=Decimal("100.00"),
            status="FILLED",
        )

        config = CommissionConfig(
            commission_type="PER_SHARE",
            commission_per_share=Decimal("0.005"),
            min_commission=Decimal("1.00"),
        )

        commission, breakdown = calculator.calculate_commission(zero_order, config)

        # Base commission for 1 share is $0.005 (quantized to $0.01), but min cap of $1.00 applies
        assert commission == Decimal("1.00")
        assert breakdown.base_commission == Decimal("0.01")  # Quantized to 2 decimals

    # Subtask 15.1.9: Test Interactive Brokers realistic example
    def test_interactive_brokers_realistic(self, calculator):
        """Test realistic Interactive Brokers commission scenario."""
        # Typical IB retail order: 500 shares of AAPL at $180
        order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=500,
            created_bar_timestamp=datetime.now(UTC),
            fill_price=Decimal("180.00"),
            status="FILLED",
        )

        config = CommissionConfig(
            commission_type="PER_SHARE",
            commission_per_share=Decimal("0.005"),
            min_commission=Decimal("1.00"),
            broker_name="Interactive Brokers Retail",
        )

        commission, breakdown = calculator.calculate_commission(order, config)

        # 500 shares * $0.005 = $2.50
        assert commission == Decimal("2.50")
        assert breakdown.broker_name == "Interactive Brokers Retail"
