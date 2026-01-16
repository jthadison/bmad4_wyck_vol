"""
Unit Tests for Cost Models (Story 18.9.4)

Tests for pluggable cost model implementations including ZeroCostModel
(zero-cost) and RealisticCostModel (per-share commission + spread-based slippage).

Author: Story 18.9.4
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.engine.cost_model import (
    RealisticCostModel,
    ZeroCostModel,
)
from src.models.backtest import BacktestOrder
from src.models.ohlcv import OHLCVBar


class TestZeroCostModel:
    """Tests for ZeroCostModel (zero-cost model)."""

    @pytest.fixture
    def cost_model(self):
        """Create ZeroCostModel instance."""
        return ZeroCostModel()

    @pytest.fixture
    def sample_order(self):
        """Create a sample order."""
        return BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=100,
            status="PENDING",
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        )

    @pytest.fixture
    def sample_bar(self):
        """Create a sample bar."""
        return OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("150.00"),
            high=Decimal("152.00"),
            low=Decimal("149.00"),
            close=Decimal("151.00"),
            volume=1000000,
            spread=Decimal("3.00"),
        )

    def test_zero_commission(self, cost_model, sample_order):
        """AC1: ZeroCostModel returns zero commission."""
        commission = cost_model.calculate_commission(sample_order)
        assert commission == Decimal("0")

    def test_zero_slippage(self, cost_model, sample_order, sample_bar):
        """AC1: ZeroCostModel returns zero slippage."""
        slippage = cost_model.calculate_slippage(sample_order, sample_bar)
        assert slippage == Decimal("0")

    def test_zero_slippage_sell_order(self, cost_model, sample_bar):
        """AC1: ZeroCostModel returns zero slippage for sell orders."""
        sell_order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="SELL",
            quantity=100,
            status="PENDING",
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        )
        slippage = cost_model.calculate_slippage(sell_order, sample_bar)
        assert slippage == Decimal("0")


class TestRealisticCostModel:
    """Tests for RealisticCostModel with per-share commission and slippage."""

    @pytest.fixture
    def cost_model(self):
        """Create RealisticCostModel with default parameters."""
        return RealisticCostModel()

    @pytest.fixture
    def custom_cost_model(self):
        """Create RealisticCostModel with custom parameters."""
        return RealisticCostModel(
            commission_per_share=Decimal("0.01"),  # $0.01 per share
            slippage_pct=Decimal("0.001"),  # 0.1%
        )

    @pytest.fixture
    def sample_order(self):
        """Create a sample order."""
        return BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=100,
            status="PENDING",
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        )

    @pytest.fixture
    def sample_bar(self):
        """Create a sample bar with known spread."""
        return OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("150.00"),
            high=Decimal("155.00"),  # high - low = $5 spread
            low=Decimal("150.00"),
            close=Decimal("152.00"),
            volume=1000000,
            spread=Decimal("5.00"),
        )

    def test_default_values(self, cost_model):
        """AC2: RealisticCostModel has sensible defaults."""
        assert cost_model.commission_per_share == Decimal("0.005")  # $0.005 per share (IB-like)
        assert cost_model.minimum_commission == Decimal("1.00")  # $1.00 minimum
        assert cost_model.slippage_pct == Decimal("0.0005")  # 0.05%

    def test_commission_calculation_above_minimum(self, cost_model):
        """AC2: Commission is per-share when above minimum."""
        # 500 shares * $0.005 per share = $2.50 > $1.00 minimum
        large_order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=500,
            status="PENDING",
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        )
        commission = cost_model.calculate_commission(large_order)
        expected = Decimal("500") * Decimal("0.005")  # $2.50
        assert commission == expected

    def test_commission_calculation_at_minimum(self, cost_model, sample_order):
        """AC2: Commission uses minimum when per-share is below it."""
        # 100 shares * $0.005 per share = $0.50 < $1.00 minimum
        commission = cost_model.calculate_commission(sample_order)
        assert commission == Decimal("1.00")  # Minimum kicks in

    def test_custom_commission_rate(self, custom_cost_model):
        """AC2: Custom per-share commission is applied correctly."""
        order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=100,
            status="PENDING",
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        )
        # 100 shares * $0.01 per share = $1.00
        commission = custom_cost_model.calculate_commission(order)
        assert commission == Decimal("1.00")

    def test_slippage_buy_order(self, cost_model, sample_order, sample_bar):
        """AC2: Slippage is positive for BUY orders (pay more)."""
        # Spread = $155 - $150 = $5
        # Slippage = $5 * 0.0005 = $0.0025
        slippage = cost_model.calculate_slippage(sample_order, sample_bar)
        expected = Decimal("5.00") * Decimal("0.0005")
        assert slippage == expected
        assert slippage > 0

    def test_slippage_sell_order(self, cost_model, sample_bar):
        """AC2: Slippage is negative for SELL orders (receive less)."""
        sell_order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="SELL",
            quantity=100,
            status="PENDING",
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        )
        # Spread = $5
        # Slippage = -$5 * 0.0005 = -$0.0025
        slippage = cost_model.calculate_slippage(sell_order, sample_bar)
        expected = -Decimal("5.00") * Decimal("0.0005")
        assert slippage == expected
        assert slippage < 0

    def test_custom_slippage_rate(self, custom_cost_model, sample_bar):
        """AC2: Custom slippage percentage is applied correctly."""
        order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=100,
            status="PENDING",
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        )
        # Spread = $5
        # Slippage = $5 * 0.001 = $0.005
        slippage = custom_cost_model.calculate_slippage(order, sample_bar)
        expected = Decimal("5.00") * Decimal("0.001")
        assert slippage == expected

    def test_slippage_zero_spread_bar(self, cost_model):
        """Slippage is zero when bar has no spread (high == low, doji bar)."""
        zero_spread_bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("150.00"),
            high=Decimal("150.00"),  # high == low
            low=Decimal("150.00"),
            close=Decimal("150.00"),
            volume=1000000,
            spread=Decimal("0.00"),
        )
        buy_order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=100,
            status="PENDING",
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        )
        slippage = cost_model.calculate_slippage(buy_order, zero_spread_bar)
        assert slippage == Decimal("0")

    def test_invalid_negative_commission(self):
        """Negative commission per share raises ValueError."""
        with pytest.raises(ValueError, match="Commission per share cannot be negative"):
            RealisticCostModel(commission_per_share=Decimal("-0.001"))

    def test_invalid_negative_minimum_commission(self):
        """Negative minimum commission raises ValueError."""
        with pytest.raises(ValueError, match="Minimum commission cannot be negative"):
            RealisticCostModel(minimum_commission=Decimal("-1.00"))

    def test_invalid_slippage_percentage_too_high(self):
        """Slippage percentage > 100% raises ValueError."""
        with pytest.raises(ValueError, match="Slippage percentage must be in"):
            RealisticCostModel(slippage_pct=Decimal("1.5"))

    def test_invalid_slippage_percentage_negative(self):
        """Negative slippage percentage raises ValueError."""
        with pytest.raises(ValueError, match="Slippage percentage must be in"):
            RealisticCostModel(slippage_pct=Decimal("-0.001"))

    def test_property_accessors(self, custom_cost_model):
        """Property accessors return correct values."""
        assert custom_cost_model.commission_per_share == Decimal("0.01")
        assert custom_cost_model.minimum_commission == Decimal("1.00")  # default
        assert custom_cost_model.slippage_pct == Decimal("0.001")

    def test_custom_minimum_commission(self):
        """Custom minimum commission is applied correctly."""
        cost_model = RealisticCostModel(
            commission_per_share=Decimal("0.005"),
            minimum_commission=Decimal("2.00"),  # $2.00 minimum
        )
        order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=100,
            status="PENDING",
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        )
        # 100 * $0.005 = $0.50 < $2.00 minimum
        commission = cost_model.calculate_commission(order)
        assert commission == Decimal("2.00")


class TestCostModelProtocolCompliance:
    """Tests verifying cost models implement CostModel protocol."""

    @pytest.fixture
    def sample_order(self):
        """Create a sample order."""
        return BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=100,
            status="PENDING",
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        )

    @pytest.fixture
    def sample_bar(self):
        """Create a sample bar."""
        return OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("150.00"),
            high=Decimal("152.00"),
            low=Decimal("149.00"),
            close=Decimal("151.00"),
            volume=1000000,
            spread=Decimal("3.00"),
        )

    def test_zero_cost_model_has_required_methods(self, sample_order, sample_bar):
        """ZeroCostModel has all required CostModel methods."""
        model = ZeroCostModel()

        # Should have calculate_commission method
        assert hasattr(model, "calculate_commission")
        assert callable(model.calculate_commission)

        # Should have calculate_slippage method
        assert hasattr(model, "calculate_slippage")
        assert callable(model.calculate_slippage)

        # Methods should return Decimal
        assert isinstance(model.calculate_commission(sample_order), Decimal)
        assert isinstance(model.calculate_slippage(sample_order, sample_bar), Decimal)

    def test_realistic_cost_model_has_required_methods(self, sample_order, sample_bar):
        """RealisticCostModel has all required CostModel methods."""
        model = RealisticCostModel()

        # Should have calculate_commission method
        assert hasattr(model, "calculate_commission")
        assert callable(model.calculate_commission)

        # Should have calculate_slippage method
        assert hasattr(model, "calculate_slippage")
        assert callable(model.calculate_slippage)

        # Methods should return Decimal
        assert isinstance(model.calculate_commission(sample_order), Decimal)
        assert isinstance(model.calculate_slippage(sample_order, sample_bar), Decimal)
