"""
Unit tests for Order Simulator (Story 12.1 Task 3).

Tests market order fills, limit order fills, and realistic order execution.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

import pytest

from src.backtesting.order_simulator import OrderSimulator
from src.models.ohlcv import OHLCVBar


@pytest.fixture
def simulator():
    """Fixture for OrderSimulator instance."""
    return OrderSimulator()


@pytest.fixture
def bar_n():
    """Fixture for bar N (order submission bar)."""
    return OHLCVBar(
        symbol="AAPL",
        timeframe="1d",
        open=Decimal("150.00"),
        high=Decimal("152.00"),
        low=Decimal("149.00"),
        close=Decimal("151.00"),
        volume=50000,
        spread=Decimal("3.00"),
        timestamp=datetime(2024, 1, 10, 9, 30),
    )


@pytest.fixture
def bar_n_plus_1():
    """Fixture for bar N+1 (order fill bar)."""
    return OHLCVBar(
        symbol="AAPL",
        timeframe="1d",
        open=Decimal("151.50"),  # Next bar opens higher
        high=Decimal("153.00"),
        low=Decimal("150.50"),
        close=Decimal("152.50"),
        volume=48000,
        spread=Decimal("2.50"),
        timestamp=datetime(2024, 1, 11, 9, 30),
    )


class TestOrderSubmission:
    """Test order submission."""

    def test_submit_market_buy_order(self, simulator, bar_n):
        """Test submitting a market buy order."""
        order = simulator.submit_order(
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=100,
            current_bar=bar_n,
        )

        assert isinstance(order.order_id, UUID)
        assert order.symbol == "AAPL"
        assert order.order_type == "MARKET"
        assert order.side == "BUY"
        assert order.quantity == 100
        assert order.created_bar_timestamp == bar_n.timestamp
        assert order.status == "PENDING"
        assert order.fill_price is None
        assert order.filled_bar_timestamp is None
        assert simulator.get_pending_count() == 1

    def test_submit_market_sell_order(self, simulator, bar_n):
        """Test submitting a market sell order."""
        order = simulator.submit_order(
            symbol="AAPL",
            order_type="MARKET",
            side="SELL",
            quantity=200,
            current_bar=bar_n,
        )

        assert order.order_type == "MARKET"
        assert order.side == "SELL"
        assert order.quantity == 200
        assert order.status == "PENDING"

    def test_submit_limit_buy_order(self, simulator, bar_n):
        """Test submitting a limit buy order."""
        order = simulator.submit_order(
            symbol="AAPL",
            order_type="LIMIT",
            side="BUY",
            quantity=100,
            current_bar=bar_n,
            limit_price=Decimal("149.00"),
        )

        assert order.order_type == "LIMIT"
        assert order.limit_price == Decimal("149.00")
        assert order.status == "PENDING"

    def test_multiple_pending_orders(self, simulator, bar_n):
        """Test multiple pending orders."""
        order1 = simulator.submit_order("AAPL", "MARKET", "BUY", 100, bar_n)
        order2 = simulator.submit_order("AAPL", "MARKET", "SELL", 50, bar_n)
        order3 = simulator.submit_order("AAPL", "LIMIT", "BUY", 200, bar_n, Decimal("148.00"))

        assert simulator.get_pending_count() == 3
        assert order1 in simulator.pending_orders
        assert order2 in simulator.pending_orders
        assert order3 in simulator.pending_orders


class TestMarketOrderFills:
    """Test market order fills at next bar open."""

    def test_fill_market_buy_order(self, simulator, bar_n, bar_n_plus_1):
        """Test filling a market buy order at next bar open."""
        # Submit order on bar N
        order = simulator.submit_order("AAPL", "MARKET", "BUY", 100, bar_n)

        # Fill on bar N+1
        avg_volume = Decimal("2000000")  # Liquid
        filled = simulator.fill_pending_orders(bar_n_plus_1, avg_volume)

        assert len(filled) == 1
        assert filled[0].order_id == order.order_id
        assert filled[0].status == "FILLED"
        assert filled[0].filled_bar_timestamp == bar_n_plus_1.timestamp

        # Fill price = bar N+1 open + slippage
        # Slippage for liquid stock: 0.02% of $151.50 = $0.0303
        # Buy order increases price: $151.50 + $0.0303 = $151.5303
        assert filled[0].fill_price == Decimal("151.5303")
        assert filled[0].slippage == Decimal("0.0303")

        # Commission: 100 * $0.005 = $0.50
        assert filled[0].commission == Decimal("0.50")

        # No longer pending
        assert simulator.get_pending_count() == 0

    def test_fill_market_sell_order(self, simulator, bar_n, bar_n_plus_1):
        """Test filling a market sell order at next bar open."""
        # Submit sell order
        order = simulator.submit_order("AAPL", "MARKET", "SELL", 100, bar_n)

        # Fill on next bar
        avg_volume = Decimal("2000000")
        filled = simulator.fill_pending_orders(bar_n_plus_1, avg_volume)

        assert len(filled) == 1
        assert filled[0].status == "FILLED"

        # Sell order decreases price: $151.50 - $0.0303 = $151.4697
        assert filled[0].fill_price == Decimal("151.4697")
        assert filled[0].slippage == Decimal("0.0303")

    def test_fill_with_market_impact(self, simulator, bar_n, bar_n_plus_1):
        """Test fill with market impact from large order."""
        # Large order: 10,000 shares when bar volume is 48,000
        # Order is ~21% of bar volume
        # Excess: 11% / 10% = 2 increments of market impact
        order = simulator.submit_order("AAPL", "MARKET", "BUY", 10000, bar_n)

        avg_volume = Decimal("2000000")  # Liquid
        filled = simulator.fill_pending_orders(bar_n_plus_1, avg_volume)

        # Base slippage: 0.02%
        # Market impact: 2 * 0.01% = 0.02%
        # Total: 0.04% of $151.50 = $0.0606
        assert filled[0].slippage == Decimal("0.0606")
        assert filled[0].fill_price == Decimal("151.5606")

    def test_fill_illiquid_stock(self, simulator, bar_n):
        """Test fill on illiquid stock with higher slippage."""
        # Create illiquid bar
        illiquid_bar = OHLCVBar(
            symbol="TINY",
            timeframe="1d",
            open=Decimal("25.00"),
            high=Decimal("25.50"),
            low=Decimal("24.50"),
            close=Decimal("25.20"),
            volume=1000,
            spread=Decimal("1.00"),
            timestamp=datetime(2024, 1, 11, 9, 30),
        )

        order = simulator.submit_order("TINY", "MARKET", "BUY", 100, bar_n)

        # Illiquid: avg_volume < $1M
        avg_volume = Decimal("100000")
        filled = simulator.fill_pending_orders(illiquid_bar, avg_volume)

        # Illiquid slippage: 0.05% of $25.00 = $0.0125
        assert filled[0].slippage == Decimal("0.0125")
        assert filled[0].fill_price == Decimal("25.0125")

    def test_fill_multiple_orders(self, simulator, bar_n, bar_n_plus_1):
        """Test filling multiple pending orders."""
        order1 = simulator.submit_order("AAPL", "MARKET", "BUY", 100, bar_n)
        order2 = simulator.submit_order("AAPL", "MARKET", "SELL", 50, bar_n)

        avg_volume = Decimal("2000000")
        filled = simulator.fill_pending_orders(bar_n_plus_1, avg_volume)

        assert len(filled) == 2
        assert simulator.get_pending_count() == 0

        # Both filled at bar N+1 open
        assert all(o.filled_bar_timestamp == bar_n_plus_1.timestamp for o in filled)

    def test_custom_commission_rate(self, simulator, bar_n, bar_n_plus_1):
        """Test custom commission rate."""
        order = simulator.submit_order("AAPL", "MARKET", "BUY", 100, bar_n)

        # Custom commission: $0.01/share
        avg_volume = Decimal("2000000")
        filled = simulator.fill_pending_orders(
            bar_n_plus_1, avg_volume, commission_per_share=Decimal("0.01")
        )

        # 100 shares * $0.01 = $1.00
        assert filled[0].commission == Decimal("1.00")


class TestLimitOrderFills:
    """Test limit order fills when price reaches limit."""

    def test_limit_buy_order_filled(self, simulator, bar_n):
        """Test limit buy order filled when price drops to limit."""
        # Submit limit buy at $150.00
        order = simulator.submit_order(
            "AAPL", "LIMIT", "BUY", 100, bar_n, limit_price=Decimal("150.00")
        )

        # Next bar touches limit (low = $150.50 doesn't fill)
        bar_too_high = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            open=Decimal("151.00"),
            high=Decimal("152.00"),
            low=Decimal("150.50"),  # Doesn't reach $150.00
            close=Decimal("151.50"),
            volume=50000,
            spread=Decimal("1.50"),
            timestamp=datetime(2024, 1, 11, 9, 30),
        )

        filled = simulator.fill_pending_orders(bar_too_high, Decimal("2000000"))
        assert len(filled) == 0  # Not filled
        assert simulator.get_pending_count() == 1

        # Next bar reaches limit (low = $149.50)
        bar_reached = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            open=Decimal("150.50"),
            high=Decimal("151.00"),
            low=Decimal("149.50"),  # Reaches $150.00
            close=Decimal("150.00"),
            volume=50000,
            spread=Decimal("1.50"),
            timestamp=datetime(2024, 1, 12, 9, 30),
        )

        filled = simulator.fill_pending_orders(bar_reached, Decimal("2000000"))
        assert len(filled) == 1
        assert filled[0].status == "FILLED"
        assert filled[0].fill_price == Decimal("150.00")  # Filled at limit price
        assert filled[0].slippage == Decimal("0")  # No slippage on limit orders
        assert simulator.get_pending_count() == 0

    def test_limit_sell_order_filled(self, simulator, bar_n):
        """Test limit sell order filled when price rises to limit."""
        # Submit limit sell at $152.00
        order = simulator.submit_order(
            "AAPL", "LIMIT", "SELL", 100, bar_n, limit_price=Decimal("152.00")
        )

        # Bar reaches limit (high = $152.50)
        bar_reached = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            open=Decimal("151.00"),
            high=Decimal("152.50"),  # Reaches $152.00
            low=Decimal("150.50"),
            close=Decimal("151.50"),
            volume=50000,
            spread=Decimal("2.00"),
            timestamp=datetime(2024, 1, 11, 9, 30),
        )

        filled = simulator.fill_pending_orders(bar_reached, Decimal("2000000"))
        assert len(filled) == 1
        assert filled[0].fill_price == Decimal("152.00")  # Filled at limit
        assert filled[0].slippage == Decimal("0")

    def test_limit_buy_not_filled(self, simulator, bar_n):
        """Test limit buy not filled when price stays above limit."""
        order = simulator.submit_order(
            "AAPL", "LIMIT", "BUY", 100, bar_n, limit_price=Decimal("148.00")
        )

        # Price never drops to $148.00
        bar_above = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            open=Decimal("150.00"),
            high=Decimal("151.00"),
            low=Decimal("149.00"),  # Low is $149.00, limit is $148.00
            close=Decimal("150.50"),
            volume=50000,
            spread=Decimal("2.00"),
            timestamp=datetime(2024, 1, 11, 9, 30),
        )

        filled = simulator.fill_pending_orders(bar_above, Decimal("2000000"))
        assert len(filled) == 0
        assert simulator.get_pending_count() == 1  # Still pending


class TestOrderCancellation:
    """Test order cancellation."""

    def test_cancel_pending_orders(self, simulator, bar_n):
        """Test cancelling all pending orders."""
        order1 = simulator.submit_order("AAPL", "MARKET", "BUY", 100, bar_n)
        order2 = simulator.submit_order("AAPL", "LIMIT", "BUY", 50, bar_n, Decimal("148.00"))

        assert simulator.get_pending_count() == 2

        cancelled = simulator.cancel_pending_orders()

        assert len(cancelled) == 2
        assert all(o.status == "REJECTED" for o in cancelled)
        assert simulator.get_pending_count() == 0

    def test_cancel_empty_queue(self, simulator):
        """Test cancelling when no pending orders."""
        cancelled = simulator.cancel_pending_orders()
        assert len(cancelled) == 0


class TestRealisticScenarios:
    """Test realistic trading scenarios."""

    def test_round_trip_trade_simulation(self, simulator):
        """Test complete round-trip trade: entry → exit."""
        # Day 1: Submit entry order
        entry_bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            open=Decimal("150.00"),
            high=Decimal("152.00"),
            low=Decimal("149.00"),
            close=Decimal("151.00"),
            volume=50000,
            spread=Decimal("3.00"),
            timestamp=datetime(2024, 1, 10, 9, 30),
        )
        entry_order = simulator.submit_order("AAPL", "MARKET", "BUY", 100, entry_bar)

        # Day 2: Fill entry
        fill_entry_bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            open=Decimal("151.00"),
            high=Decimal("153.00"),
            low=Decimal("150.00"),
            close=Decimal("152.00"),
            volume=50000,
            spread=Decimal("3.00"),
            timestamp=datetime(2024, 1, 11, 9, 30),
        )
        filled_entry = simulator.fill_pending_orders(fill_entry_bar, Decimal("2000000"))

        assert len(filled_entry) == 1
        entry_fill_price = filled_entry[0].fill_price
        entry_commission = filled_entry[0].commission

        # Day 5: Price moved up, submit exit order
        exit_signal_bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            open=Decimal("155.00"),
            high=Decimal("156.00"),
            low=Decimal("154.00"),
            close=Decimal("155.50"),
            volume=48000,
            spread=Decimal("2.00"),
            timestamp=datetime(2024, 1, 15, 9, 30),
        )
        exit_order = simulator.submit_order("AAPL", "MARKET", "SELL", 100, exit_signal_bar)

        # Day 6: Fill exit
        fill_exit_bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            open=Decimal("155.50"),
            high=Decimal("157.00"),
            low=Decimal("154.50"),
            close=Decimal("156.00"),
            volume=48000,
            spread=Decimal("2.50"),
            timestamp=datetime(2024, 1, 16, 9, 30),
        )
        filled_exit = simulator.fill_pending_orders(fill_exit_bar, Decimal("2000000"))

        assert len(filled_exit) == 1
        exit_fill_price = filled_exit[0].fill_price
        exit_commission = filled_exit[0].commission

        # Calculate P&L
        entry_cost = (entry_fill_price * Decimal("100")) + entry_commission
        exit_proceeds = (exit_fill_price * Decimal("100")) - exit_commission
        pnl = exit_proceeds - entry_cost

        # Entry: $151.00 + 0.02% slippage = $151.0302, + $0.50 commission
        # Exit: $155.50 - 0.02% slippage = $155.4689, - $0.50 commission
        # P&L should be positive
        assert pnl > Decimal("0")
        assert entry_fill_price < exit_fill_price  # Profitable trade
