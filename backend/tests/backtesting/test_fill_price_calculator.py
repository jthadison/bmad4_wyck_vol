"""
Unit Tests for Fill Price Calculator (Story 12.5 Task 15.3).

Tests market order and limit order fill price calculation.

Author: Story 12.5 Task 15
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.fill_price_calculator import FillPriceCalculator
from src.models.backtest import BacktestConfig, BacktestOrder, SlippageConfig
from src.models.ohlcv import OHLCVBar


class TestFillPriceCalculator:
    """Unit tests for FillPriceCalculator."""

    @pytest.fixture
    def calculator(self):
        """Create FillPriceCalculator instance."""
        return FillPriceCalculator()

    @pytest.fixture
    def backtest_config(self):
        """Create BacktestConfig with slippage config."""
        from datetime import date

        return BacktestConfig(
            symbol="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            slippage_config=SlippageConfig(
                slippage_model="LIQUIDITY_BASED",
                high_liquidity_threshold=Decimal("1000000"),
                high_liquidity_slippage_pct=Decimal("0.0002"),  # 0.02%
                low_liquidity_slippage_pct=Decimal("0.0005"),  # 0.05%
                market_impact_enabled=True,
            ),
        )

    @pytest.fixture
    def high_liquidity_bars(self):
        """Create high liquidity historical bars."""
        bars = []
        for i in range(20):
            bar = OHLCVBar(
                symbol="AAPL",
                timeframe="5m",
                timestamp=datetime.now(UTC),
                open=Decimal("100.00"),
                high=Decimal("101.00"),
                low=Decimal("99.00"),
                close=Decimal("100.00"),
                volume=100000,  # High volume
                spread=Decimal("2.00"),
            )
            bars.append(bar)
        return bars

    # Subtask 15.3.1: Test market order fill at next bar open + slippage
    def test_market_order_fill_buy(self, calculator, backtest_config, high_liquidity_bars):
        """Test market BUY order fills at next bar open + slippage."""
        order = BacktestOrder(
            symbol="AAPL",
            created_bar_timestamp=datetime.now(UTC),
            status="PENDING",
            order_id=uuid4(),
            order_type="MARKET",
            side="BUY",
            quantity=1000,
        )

        next_bar = OHLCVBar(
            symbol="AAPL",
            timeframe="5m",
            timestamp=datetime.now(UTC),
            open=Decimal("100.00"),  # Base fill price
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=100000,
            spread=Decimal("2.00"),
        )

        fill_price = calculator.calculate_fill_price(
            order, next_bar, high_liquidity_bars, backtest_config
        )

        # BUY: Fill at open + slippage
        # $100 * (1 + 0.0002) = $100.02
        assert fill_price is not None
        assert fill_price > Decimal("100.00")  # Slippage increases price
        assert fill_price <= Decimal("100.10")  # Reasonable slippage

    # Subtask 15.3.2: Test market SELL order slippage direction
    def test_market_order_fill_sell(self, calculator, backtest_config, high_liquidity_bars):
        """Test market SELL order fills at next bar open - slippage."""
        order = BacktestOrder(
            symbol="AAPL",
            created_bar_timestamp=datetime.now(UTC),
            status="PENDING",
            order_id=uuid4(),
            order_type="MARKET",
            side="SELL",
            quantity=1000,
        )

        next_bar = OHLCVBar(
            symbol="AAPL",
            timeframe="5m",
            timestamp=datetime.now(UTC),
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=100000,
            spread=Decimal("2.00"),
        )

        fill_price = calculator.calculate_fill_price(
            order, next_bar, high_liquidity_bars, backtest_config
        )

        # SELL: Fill at open - slippage
        # $100 * (1 - 0.0002) = $99.98
        assert fill_price is not None
        assert fill_price < Decimal("100.00")  # Slippage decreases price
        assert fill_price >= Decimal("99.90")  # Reasonable slippage

    # Subtask 15.3.3: Test BUY limit order triggered (conservative fill at high)
    def test_buy_limit_order_triggered(self, calculator, backtest_config, high_liquidity_bars):
        """Test BUY limit order triggered and filled at limit price."""
        order = BacktestOrder(
            symbol="AAPL",
            created_bar_timestamp=datetime.now(UTC),
            status="PENDING",
            order_id=uuid4(),
            order_type="LIMIT",
            side="BUY",
            quantity=1000,
            limit_price=Decimal("100.00"),
        )

        next_bar = OHLCVBar(
            symbol="AAPL",
            timeframe="5m",
            timestamp=datetime.now(UTC),
            open=Decimal("100.50"),
            high=Decimal("101.00"),
            low=Decimal("99.50"),  # Touches limit price
            close=Decimal("100.20"),
            volume=100000,
            spread=Decimal("2.00"),
        )

        fill_price = calculator.calculate_fill_price(
            order, next_bar, high_liquidity_bars, backtest_config
        )

        # BUY limit triggered (low <= limit)
        # Fill at limit price
        assert fill_price == Decimal("100.00")

    # Subtask 15.3.4: Test BUY limit order NOT triggered
    def test_buy_limit_order_not_triggered(self, calculator, backtest_config, high_liquidity_bars):
        """Test BUY limit order not triggered (price never reaches limit)."""
        order = BacktestOrder(
            symbol="AAPL",
            created_bar_timestamp=datetime.now(UTC),
            status="PENDING",
            order_id=uuid4(),
            order_type="LIMIT",
            side="BUY",
            quantity=1000,
            limit_price=Decimal("99.00"),
        )

        next_bar = OHLCVBar(
            symbol="AAPL",
            timeframe="5m",
            timestamp=datetime.now(UTC),
            open=Decimal("100.50"),
            high=Decimal("101.00"),
            low=Decimal("99.50"),  # Low > limit price
            close=Decimal("100.20"),
            volume=100000,
            spread=Decimal("2.00"),
        )

        fill_price = calculator.calculate_fill_price(
            order, next_bar, high_liquidity_bars, backtest_config
        )

        # Not triggered
        assert fill_price is None

    # Subtask 15.3.5: Test SELL limit order triggered (conservative fill at low)
    def test_sell_limit_order_triggered(self, calculator, backtest_config, high_liquidity_bars):
        """Test SELL limit order triggered and filled at limit price."""
        order = BacktestOrder(
            symbol="AAPL",
            created_bar_timestamp=datetime.now(UTC),
            status="PENDING",
            order_id=uuid4(),
            order_type="LIMIT",
            side="SELL",
            quantity=1000,
            limit_price=Decimal("100.00"),
        )

        next_bar = OHLCVBar(
            symbol="AAPL",
            timeframe="5m",
            timestamp=datetime.now(UTC),
            open=Decimal("99.50"),
            high=Decimal("100.50"),  # Touches limit price
            low=Decimal("99.00"),
            close=Decimal("100.20"),
            volume=100000,
            spread=Decimal("2.00"),
        )

        fill_price = calculator.calculate_fill_price(
            order, next_bar, high_liquidity_bars, backtest_config
        )

        # SELL limit triggered (high >= limit)
        # Fill at limit price
        assert fill_price == Decimal("100.00")

    # Subtask 15.3.6: Test SELL limit order NOT triggered
    def test_sell_limit_order_not_triggered(self, calculator, backtest_config, high_liquidity_bars):
        """Test SELL limit order not triggered (price never reaches limit)."""
        order = BacktestOrder(
            symbol="AAPL",
            created_bar_timestamp=datetime.now(UTC),
            status="PENDING",
            order_id=uuid4(),
            order_type="LIMIT",
            side="SELL",
            quantity=1000,
            limit_price=Decimal("101.00"),
        )

        next_bar = OHLCVBar(
            symbol="AAPL",
            timeframe="5m",
            timestamp=datetime.now(UTC),
            open=Decimal("99.50"),
            high=Decimal("100.50"),  # High < limit price
            low=Decimal("99.00"),
            close=Decimal("100.20"),
            volume=100000,
            spread=Decimal("2.00"),
        )

        fill_price = calculator.calculate_fill_price(
            order, next_bar, high_liquidity_bars, backtest_config
        )

        # Not triggered
        assert fill_price is None

    # Subtask 15.3.7: Test limit order at exact limit price boundary
    def test_buy_limit_order_exact_boundary(self, calculator, backtest_config, high_liquidity_bars):
        """Test BUY limit order when low exactly equals limit price."""
        order = BacktestOrder(
            symbol="AAPL",
            created_bar_timestamp=datetime.now(UTC),
            status="PENDING",
            order_id=uuid4(),
            order_type="LIMIT",
            side="BUY",
            quantity=1000,
            limit_price=Decimal("100.00"),
        )

        next_bar = OHLCVBar(
            symbol="AAPL",
            timeframe="5m",
            timestamp=datetime.now(UTC),
            open=Decimal("100.50"),
            high=Decimal("101.00"),
            low=Decimal("100.00"),  # Exactly at limit
            close=Decimal("100.20"),
            volume=100000,
            spread=Decimal("2.00"),
        )

        fill_price = calculator.calculate_fill_price(
            order, next_bar, high_liquidity_bars, backtest_config
        )

        # Should trigger (low <= limit), fill at limit price
        assert fill_price == Decimal("100.00")

    # Subtask 15.3.8: Test missing limit price
    def test_limit_order_missing_limit_price(
        self, calculator, backtest_config, high_liquidity_bars
    ):
        """Test limit order with missing limit_price field."""
        order = BacktestOrder(
            symbol="AAPL",
            created_bar_timestamp=datetime.now(UTC),
            status="PENDING",
            order_id=uuid4(),
            order_type="LIMIT",
            side="BUY",
            quantity=1000,
            limit_price=None,  # Missing!
        )

        next_bar = OHLCVBar(
            symbol="AAPL",
            timeframe="5m",
            timestamp=datetime.now(UTC),
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.00"),
            volume=100000,
            spread=Decimal("2.00"),
        )

        fill_price = calculator.calculate_fill_price(
            order, next_bar, high_liquidity_bars, backtest_config
        )

        # Should return None (error case)
        assert fill_price is None

    # Subtask 15.3.9: Test unknown order type validation
    def test_unknown_order_type(self, calculator, backtest_config, high_liquidity_bars):
        """Test that Pydantic validates order_type literal values."""
        from pydantic_core import ValidationError

        # Pydantic should prevent creation of orders with invalid order_type
        with pytest.raises(ValidationError) as exc_info:
            order = BacktestOrder(
                symbol="AAPL",
                created_bar_timestamp=datetime.now(UTC),
                status="PENDING",
                order_id=uuid4(),
                order_type="STOP_LIMIT",  # Not supported
                side="BUY",
                quantity=1000,
            )

        # Verify the validation error is for order_type
        assert "order_type" in str(exc_info.value)

    # Subtask 15.3.10: Test realistic scenario (market order with slippage breakdown)
    def test_realistic_market_order_with_breakdown(
        self, calculator, backtest_config, high_liquidity_bars
    ):
        """Test realistic market order and verify slippage breakdown is stored."""
        order = BacktestOrder(
            symbol="AAPL",
            created_bar_timestamp=datetime.now(UTC),
            status="PENDING",
            order_id=uuid4(),
            order_type="MARKET",
            side="BUY",
            quantity=1000,
        )

        next_bar = OHLCVBar(
            symbol="AAPL",
            timeframe="5m",
            timestamp=datetime.now(UTC),
            open=Decimal("150.00"),
            high=Decimal("151.00"),
            low=Decimal("149.00"),
            close=Decimal("150.50"),
            volume=50000,
            spread=Decimal("2.00"),
        )

        fill_price = calculator.calculate_fill_price(
            order, next_bar, high_liquidity_bars, backtest_config
        )

        # Verify slippage breakdown was stored in order
        assert order.slippage_breakdown is not None
        assert order.slippage_breakdown.order_id == order.order_id
        assert order.slippage_breakdown.total_slippage_pct > Decimal("0")
        assert order.slippage is not None
        assert order.slippage > Decimal("0")
