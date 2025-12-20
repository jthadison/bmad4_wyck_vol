"""
Unit tests for Position Manager (Story 12.1 Task 4).

Tests position tracking, cash management, and P&L calculations.
"""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.position_manager import PositionManager
from src.models.backtest import BacktestOrder
from src.models.ohlcv import OHLCVBar


@pytest.fixture
def position_manager():
    """Fixture for PositionManager with $100k starting capital."""
    return PositionManager(Decimal("100000"))


@pytest.fixture
def filled_buy_order():
    """Fixture for a filled BUY order."""
    return BacktestOrder(
        order_id=uuid4(),
        symbol="AAPL",
        order_type="MARKET",
        side="BUY",
        quantity=100,
        limit_price=None,
        created_bar_timestamp=datetime(2024, 1, 10, 9, 30),
        filled_bar_timestamp=datetime(2024, 1, 11, 9, 30),
        status="FILLED",
        fill_price=Decimal("150.03"),  # $150 + 0.02% slippage
        commission=Decimal("0.50"),
        slippage=Decimal("0.03"),
    )


@pytest.fixture
def filled_sell_order():
    """Fixture for a filled SELL order."""
    return BacktestOrder(
        order_id=uuid4(),
        symbol="AAPL",
        order_type="MARKET",
        side="SELL",
        quantity=100,
        limit_price=None,
        created_bar_timestamp=datetime(2024, 1, 15, 9, 30),
        filled_bar_timestamp=datetime(2024, 1, 16, 9, 30),
        status="FILLED",
        fill_price=Decimal("155.47"),  # $155.50 - 0.02% slippage
        commission=Decimal("0.50"),
        slippage=Decimal("0.03"),
    )


@pytest.fixture
def current_bar():
    """Fixture for current price bar."""
    return OHLCVBar(
        symbol="AAPL",
        timeframe="1d",
        open=Decimal("151.00"),
        high=Decimal("153.00"),
        low=Decimal("150.00"),
        close=Decimal("152.00"),
        volume=50000,
        spread=Decimal("3.00"),
        timestamp=datetime(2024, 1, 12, 9, 30),
    )


class TestPositionManagerInitialization:
    """Test PositionManager initialization."""

    def test_initialization_with_valid_capital(self):
        """Test initialization with valid starting capital."""
        pm = PositionManager(Decimal("100000"))

        assert pm.initial_capital == Decimal("100000")
        assert pm.cash == Decimal("100000")
        assert pm.positions == {}
        assert pm.closed_trades == []

    def test_initialization_with_zero_capital(self):
        """Test initialization fails with zero capital."""
        with pytest.raises(ValueError, match="Initial capital must be greater than zero"):
            PositionManager(Decimal("0"))

    def test_initialization_with_negative_capital(self):
        """Test initialization fails with negative capital."""
        with pytest.raises(ValueError, match="Initial capital must be greater than zero"):
            PositionManager(Decimal("-1000"))


class TestOpenPosition:
    """Test opening positions from BUY orders."""

    def test_open_new_position(self, position_manager, filled_buy_order):
        """Test opening a new position from filled BUY order."""
        position = position_manager.open_position(filled_buy_order)

        # Check position created
        assert position.symbol == "AAPL"
        assert position.side == "LONG"
        assert position.quantity == 100
        assert position.average_entry_price == Decimal("150.03")
        assert position.current_price == Decimal("150.03")
        assert position.total_commission == Decimal("0.50")
        assert position.unrealized_pnl == Decimal("0")

        # Check cash deducted
        # Cost: (100 * $150.03) + $0.50 = $15,003.50
        expected_cash = Decimal("100000") - Decimal("15003.50")
        assert position_manager.cash == expected_cash

        # Check position tracked
        assert position_manager.has_position("AAPL")
        assert position_manager.get_position("AAPL") == position

    def test_open_position_adds_to_existing(self, position_manager, filled_buy_order):
        """Test adding to existing position (average up)."""
        # First buy: 100 shares @ $150.03
        position_manager.open_position(filled_buy_order)

        # Second buy: 50 shares @ $152.00
        second_buy = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=50,
            limit_price=None,
            created_bar_timestamp=datetime(2024, 1, 12, 9, 30),
            filled_bar_timestamp=datetime(2024, 1, 13, 9, 30),
            status="FILLED",
            fill_price=Decimal("152.00"),
            commission=Decimal("0.25"),
            slippage=Decimal("0.03"),
        )
        position = position_manager.open_position(second_buy)

        # Check position quantity increased
        assert position.quantity == 150

        # Check average entry price
        # First: 100 * $150.03 = $15,003
        # Second: 50 * $152.00 = $7,600
        # Average: ($15,003 + $7,600) / 150 = $150.6867
        expected_avg = (Decimal("15003") + Decimal("7600")) / Decimal("150")
        assert position.average_entry_price == expected_avg

        # Check total commission
        assert position.total_commission == Decimal("0.75")  # $0.50 + $0.25

    def test_open_position_insufficient_cash(self, position_manager):
        """Test opening position fails with insufficient cash."""
        # Try to buy $150k worth of stock with $100k cash
        large_order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=1000,
            limit_price=None,
            created_bar_timestamp=datetime(2024, 1, 10, 9, 30),
            filled_bar_timestamp=datetime(2024, 1, 11, 9, 30),
            status="FILLED",
            fill_price=Decimal("150.00"),
            commission=Decimal("5.00"),
            slippage=Decimal("0.30"),
        )

        with pytest.raises(ValueError, match="Insufficient cash"):
            position_manager.open_position(large_order)

    def test_open_position_requires_filled_order(self, position_manager):
        """Test opening position fails with non-filled order."""
        pending_order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=100,
            limit_price=None,
            created_bar_timestamp=datetime(2024, 1, 10, 9, 30),
            filled_bar_timestamp=None,
            status="PENDING",
            fill_price=None,
            commission=Decimal("0"),
            slippage=Decimal("0"),
        )

        with pytest.raises(ValueError, match="Cannot open position from non-filled order"):
            position_manager.open_position(pending_order)

    def test_open_position_requires_buy_order(self, position_manager):
        """Test opening position fails with SELL order."""
        sell_order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="SELL",
            quantity=100,
            limit_price=None,
            created_bar_timestamp=datetime(2024, 1, 10, 9, 30),
            filled_bar_timestamp=datetime(2024, 1, 11, 9, 30),
            status="FILLED",
            fill_price=Decimal("150.00"),
            commission=Decimal("0.50"),
            slippage=Decimal("0.03"),
        )

        with pytest.raises(ValueError, match="Cannot open position from SELL order"):
            position_manager.open_position(sell_order)


class TestClosePosition:
    """Test closing positions from SELL orders."""

    def test_close_full_position(self, position_manager, filled_buy_order, filled_sell_order):
        """Test closing entire position."""
        # Open position
        position_manager.open_position(filled_buy_order)
        initial_cash = position_manager.cash

        # Close position
        trade = position_manager.close_position(filled_sell_order)

        # Check trade record
        assert trade.symbol == "AAPL"
        assert trade.side == "LONG"
        assert trade.quantity == 100
        assert trade.entry_price == Decimal("150.03")
        assert trade.exit_price == Decimal("155.47")

        # Check realized P&L
        # Entry cost: (100 * $150.03) + $0.50 = $15,003.50
        # Exit proceeds: (100 * $155.47) - $0.50 = $15,546.50
        # P&L: $15,546.50 - $15,003.50 = $543.00
        expected_pnl = Decimal("543.00")
        assert trade.realized_pnl == expected_pnl

        # Check cash credited
        exit_proceeds = (Decimal("100") * Decimal("155.47")) - Decimal("0.50")
        expected_cash = initial_cash + exit_proceeds
        assert position_manager.cash == expected_cash

        # Check position removed
        assert not position_manager.has_position("AAPL")
        assert position_manager.get_position("AAPL") is None

        # Check trade in history
        assert len(position_manager.closed_trades) == 1
        assert position_manager.closed_trades[0] == trade

    def test_close_partial_position(self, position_manager, filled_buy_order):
        """Test closing part of a position."""
        # Open position: 100 shares
        position_manager.open_position(filled_buy_order)

        # Close partial: 50 shares
        partial_sell = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="SELL",
            quantity=50,
            limit_price=None,
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30),
            filled_bar_timestamp=datetime(2024, 1, 16, 9, 30),
            status="FILLED",
            fill_price=Decimal("155.47"),
            commission=Decimal("0.25"),
            slippage=Decimal("0.03"),
        )

        trade = position_manager.close_position(partial_sell)

        # Check trade quantity
        assert trade.quantity == 50

        # Check position reduced
        position = position_manager.get_position("AAPL")
        assert position is not None
        assert position.quantity == 50

        # Check commission allocated proportionally
        # Entry commission: $0.50 for 100 shares
        # Allocated to 50 shares: $0.25
        # Exit commission: $0.25
        # Total trade commission: $0.50
        assert trade.commission == Decimal("0.50")

    def test_close_position_no_open_position(self, position_manager, filled_sell_order):
        """Test closing position fails when no position exists."""
        with pytest.raises(ValueError, match="No open position for symbol"):
            position_manager.close_position(filled_sell_order)

    def test_close_position_insufficient_quantity(
        self, position_manager, filled_buy_order, filled_sell_order
    ):
        """Test closing position fails with insufficient quantity."""
        # Open position: 100 shares
        position_manager.open_position(filled_buy_order)

        # Try to close 200 shares
        large_sell = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="SELL",
            quantity=200,
            limit_price=None,
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30),
            filled_bar_timestamp=datetime(2024, 1, 16, 9, 30),
            status="FILLED",
            fill_price=Decimal("155.47"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.03"),
        )

        with pytest.raises(ValueError, match="Insufficient position quantity"):
            position_manager.close_position(large_sell)

    def test_close_position_requires_filled_order(self, position_manager, filled_buy_order):
        """Test closing position fails with non-filled order."""
        position_manager.open_position(filled_buy_order)

        pending_sell = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="SELL",
            quantity=100,
            limit_price=None,
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30),
            filled_bar_timestamp=None,
            status="PENDING",
            fill_price=None,
            commission=Decimal("0"),
            slippage=Decimal("0"),
        )

        with pytest.raises(ValueError, match="Cannot close position from non-filled order"):
            position_manager.close_position(pending_sell)

    def test_close_position_requires_sell_order(self, position_manager, filled_buy_order):
        """Test closing position fails with BUY order."""
        position_manager.open_position(filled_buy_order)

        with pytest.raises(ValueError, match="Cannot close position from BUY order"):
            position_manager.close_position(filled_buy_order)


class TestPortfolioCalculations:
    """Test portfolio value and P&L calculations."""

    def test_calculate_portfolio_value_cash_only(self, position_manager, current_bar):
        """Test portfolio value with no positions."""
        portfolio_value = position_manager.calculate_portfolio_value(current_bar)
        assert portfolio_value == Decimal("100000")

    def test_calculate_portfolio_value_with_position(
        self, position_manager, filled_buy_order, current_bar
    ):
        """Test portfolio value with open position."""
        # Open position: 100 shares @ $150.03
        # Cash spent: $15,003.50
        position_manager.open_position(filled_buy_order)

        # Calculate value with current price $152.00
        portfolio_value = position_manager.calculate_portfolio_value(current_bar)

        # Cash: $100,000 - $15,003.50 = $84,996.50
        # Position: 100 * $152.00 = $15,200.00
        # Total: $100,196.50
        expected_value = Decimal("84996.50") + Decimal("15200.00")
        assert portfolio_value == expected_value

    def test_calculate_unrealized_pnl_no_positions(self, position_manager, current_bar):
        """Test unrealized P&L with no positions."""
        unrealized = position_manager.calculate_unrealized_pnl(current_bar)
        assert unrealized == Decimal("0")

    def test_calculate_unrealized_pnl_with_profit(
        self, position_manager, filled_buy_order, current_bar
    ):
        """Test unrealized P&L with profitable position."""
        # Open position: 100 shares @ $150.03
        position_manager.open_position(filled_buy_order)

        # Calculate unrealized P&L with current price $152.00
        unrealized = position_manager.calculate_unrealized_pnl(current_bar)

        # Unrealized: (152.00 - 150.03) * 100 = $197.00
        expected_unrealized = (Decimal("152.00") - Decimal("150.03")) * Decimal("100")
        assert unrealized == expected_unrealized

        # Check position updated
        position = position_manager.get_position("AAPL")
        assert position.unrealized_pnl == expected_unrealized
        assert position.current_price == Decimal("152.00")

    def test_calculate_unrealized_pnl_with_loss(self, position_manager, filled_buy_order):
        """Test unrealized P&L with losing position."""
        # Open position: 100 shares @ $150.03
        position_manager.open_position(filled_buy_order)

        # Price dropped to $148.00
        losing_bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            open=Decimal("149.00"),
            high=Decimal("150.00"),
            low=Decimal("147.00"),
            close=Decimal("148.00"),
            volume=60000,
            spread=Decimal("3.00"),
            timestamp=datetime(2024, 1, 12, 9, 30),
        )

        unrealized = position_manager.calculate_unrealized_pnl(losing_bar)

        # Unrealized: (148.00 - 150.03) * 100 = -$203.00
        expected_unrealized = (Decimal("148.00") - Decimal("150.03")) * Decimal("100")
        assert unrealized == expected_unrealized
        assert unrealized < Decimal("0")  # Loss


class TestRealizedPnL:
    """Test realized P&L calculations."""

    def test_get_realized_pnl_no_trades(self, position_manager):
        """Test realized P&L with no closed trades."""
        realized = position_manager.get_realized_pnl()
        assert realized == Decimal("0")

    def test_get_realized_pnl_single_trade(
        self, position_manager, filled_buy_order, filled_sell_order
    ):
        """Test realized P&L with one closed trade."""
        # Execute round-trip trade
        position_manager.open_position(filled_buy_order)
        trade = position_manager.close_position(filled_sell_order)

        realized = position_manager.get_realized_pnl()
        assert realized == trade.realized_pnl
        assert realized == Decimal("543.00")

    def test_get_realized_pnl_multiple_trades(self, position_manager):
        """Test realized P&L with multiple trades."""
        # Trade 1: Profit
        buy1 = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=100,
            limit_price=None,
            created_bar_timestamp=datetime(2024, 1, 10, 9, 30),
            filled_bar_timestamp=datetime(2024, 1, 11, 9, 30),
            status="FILLED",
            fill_price=Decimal("150.00"),
            commission=Decimal("0.50"),
            slippage=Decimal("0.03"),
        )
        sell1 = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="SELL",
            quantity=100,
            limit_price=None,
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30),
            filled_bar_timestamp=datetime(2024, 1, 16, 9, 30),
            status="FILLED",
            fill_price=Decimal("155.00"),
            commission=Decimal("0.50"),
            slippage=Decimal("0.03"),
        )

        # Trade 2: Loss
        buy2 = BacktestOrder(
            order_id=uuid4(),
            symbol="MSFT",
            order_type="MARKET",
            side="BUY",
            quantity=50,
            limit_price=None,
            created_bar_timestamp=datetime(2024, 1, 20, 9, 30),
            filled_bar_timestamp=datetime(2024, 1, 21, 9, 30),
            status="FILLED",
            fill_price=Decimal("300.00"),
            commission=Decimal("0.25"),
            slippage=Decimal("0.06"),
        )
        sell2 = BacktestOrder(
            order_id=uuid4(),
            symbol="MSFT",
            order_type="MARKET",
            side="SELL",
            quantity=50,
            limit_price=None,
            created_bar_timestamp=datetime(2024, 1, 25, 9, 30),
            filled_bar_timestamp=datetime(2024, 1, 26, 9, 30),
            status="FILLED",
            fill_price=Decimal("295.00"),
            commission=Decimal("0.25"),
            slippage=Decimal("0.06"),
        )

        # Execute trades
        position_manager.open_position(buy1)
        trade1 = position_manager.close_position(sell1)

        position_manager.open_position(buy2)
        trade2 = position_manager.close_position(sell2)

        # Total realized P&L
        realized = position_manager.get_realized_pnl()
        expected = trade1.realized_pnl + trade2.realized_pnl
        assert realized == expected


class TestRealisticScenarios:
    """Test realistic trading scenarios."""

    def test_full_backtest_workflow(self, position_manager):
        """Test complete backtest workflow with multiple positions."""
        # Starting capital
        assert position_manager.cash == Decimal("100000")

        # Day 1: Buy AAPL
        buy_aapl = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=100,
            limit_price=None,
            created_bar_timestamp=datetime(2024, 1, 10, 9, 30),
            filled_bar_timestamp=datetime(2024, 1, 11, 9, 30),
            status="FILLED",
            fill_price=Decimal("150.03"),
            commission=Decimal("0.50"),
            slippage=Decimal("0.03"),
        )
        position_manager.open_position(buy_aapl)

        # Check state
        assert position_manager.has_position("AAPL")
        assert position_manager.cash == Decimal("84996.50")

        # Day 5: Buy MSFT
        buy_msft = BacktestOrder(
            order_id=uuid4(),
            symbol="MSFT",
            order_type="MARKET",
            side="BUY",
            quantity=50,
            limit_price=None,
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30),
            filled_bar_timestamp=datetime(2024, 1, 16, 9, 30),
            status="FILLED",
            fill_price=Decimal("300.06"),
            commission=Decimal("0.25"),
            slippage=Decimal("0.06"),
        )
        position_manager.open_position(buy_msft)

        # Check state
        assert position_manager.has_position("MSFT")
        assert position_manager.get_pending_count() == 2

        # Day 10: Calculate portfolio value
        aapl_bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            open=Decimal("152.00"),
            high=Decimal("153.00"),
            low=Decimal("151.00"),
            close=Decimal("152.50"),
            volume=50000,
            spread=Decimal("2.00"),
            timestamp=datetime(2024, 1, 20, 9, 30),
        )
        portfolio_value = position_manager.calculate_portfolio_value(aapl_bar)

        # Cash after 2 buys: ~$69,993.25
        # AAPL: 100 * $152.50 = $15,250
        # MSFT: 50 * $300.06 = $15,003 (not updated yet)
        # Total: ~$100,246.25 (profit)
        assert portfolio_value > Decimal("100000")

        # Day 15: Sell AAPL
        sell_aapl = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="SELL",
            quantity=100,
            limit_price=None,
            created_bar_timestamp=datetime(2024, 1, 25, 9, 30),
            filled_bar_timestamp=datetime(2024, 1, 26, 9, 30),
            status="FILLED",
            fill_price=Decimal("155.47"),
            commission=Decimal("0.50"),
            slippage=Decimal("0.03"),
        )
        trade = position_manager.close_position(sell_aapl)

        # Check trade
        assert trade.realized_pnl == Decimal("543.00")
        assert not position_manager.has_position("AAPL")
        assert position_manager.has_position("MSFT")

        # Check final P&L
        realized_pnl = position_manager.get_realized_pnl()
        assert realized_pnl == Decimal("543.00")
