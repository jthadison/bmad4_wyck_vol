"""
Unit tests for BrokerRouter (Story 23.7, 23.11).

Tests symbol classification, order routing logic, and risk gate integration.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.brokers.broker_router import BrokerRouter, classify_symbol
from src.models.order import (
    ExecutionReport,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
)
from src.risk_management.execution_risk_gate import PortfolioState


class TestClassifySymbol:
    """Test symbol classification logic."""

    @pytest.mark.parametrize(
        "symbol",
        ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD", "XAUUSD"],
    )
    def test_forex_symbols(self, symbol: str):
        """Test that known forex pairs are classified as forex."""
        assert classify_symbol(symbol) == "forex"

    @pytest.mark.parametrize(
        "symbol",
        ["EUR/USD", "GBP/USD", "USD/JPY"],
    )
    def test_forex_symbols_with_slash(self, symbol: str):
        """Test that forex pairs with slashes are classified correctly."""
        assert classify_symbol(symbol) == "forex"

    @pytest.mark.parametrize(
        "symbol",
        ["eurusd", "Eurusd", "EurUsd"],
    )
    def test_forex_symbols_case_insensitive(self, symbol: str):
        """Test that classification is case-insensitive."""
        assert classify_symbol(symbol) == "forex"

    @pytest.mark.parametrize(
        "symbol",
        ["AAPL", "MSFT", "TSLA", "GOOGL", "SPY", "QQQ", "AMZN"],
    )
    def test_stock_symbols(self, symbol: str):
        """Test that stock tickers are classified as stock."""
        assert classify_symbol(symbol) == "stock"

    def test_unknown_symbol_defaults_to_stock(self):
        """Test that unknown symbols default to stock classification."""
        assert classify_symbol("UNKNOWN123") == "stock"

    def test_empty_string_defaults_to_stock(self):
        """Test that empty string is classified as stock (no crash)."""
        assert classify_symbol("") == "stock"


class TestBrokerRouter:
    """Test BrokerRouter order routing."""

    @pytest.fixture
    def mock_mt5(self):
        """Create mock MT5 adapter."""
        adapter = MagicMock()
        adapter.platform_name = "MetaTrader5"
        adapter.is_connected.return_value = True
        adapter.place_order = AsyncMock(
            return_value=ExecutionReport(
                order_id="00000000-0000-0000-0000-000000000001",
                platform_order_id="MT5-12345",
                platform="MetaTrader5",
                status=OrderStatus.FILLED,
                filled_quantity=Decimal("1.0"),
                remaining_quantity=Decimal("0"),
            )
        )
        return adapter

    @pytest.fixture
    def mock_alpaca(self):
        """Create mock Alpaca adapter."""
        adapter = MagicMock()
        adapter.platform_name = "Alpaca"
        adapter.is_connected.return_value = True
        adapter.place_order = AsyncMock(
            return_value=ExecutionReport(
                order_id="00000000-0000-0000-0000-000000000002",
                platform_order_id="ALP-67890",
                platform="Alpaca",
                status=OrderStatus.SUBMITTED,
                filled_quantity=Decimal("0"),
                remaining_quantity=Decimal("100"),
            )
        )
        return adapter

    @pytest.fixture
    def router_both(self, mock_mt5, mock_alpaca):
        """Create router with both adapters configured."""
        return BrokerRouter(mt5_adapter=mock_mt5, alpaca_adapter=mock_alpaca)

    @pytest.fixture
    def router_mt5_only(self, mock_mt5):
        """Create router with only MT5 adapter."""
        return BrokerRouter(mt5_adapter=mock_mt5)

    @pytest.fixture
    def router_alpaca_only(self, mock_alpaca):
        """Create router with only Alpaca adapter."""
        return BrokerRouter(alpaca_adapter=mock_alpaca)

    @pytest.fixture
    def router_none(self):
        """Create router with no adapters."""
        return BrokerRouter()

    @pytest.fixture
    def safe_portfolio(self):
        """Portfolio state within all risk limits."""
        return PortfolioState(
            account_equity=Decimal("100000"),
            current_heat_pct=Decimal("3.0"),
        )

    @pytest.fixture
    def safe_risk_pct(self):
        """Trade risk percentage within limits."""
        return Decimal("1.0")

    def test_get_adapter_forex_returns_mt5(self, router_both, mock_mt5):
        """Test forex symbol returns MT5 adapter."""
        adapter = router_both.get_adapter("EURUSD")
        assert adapter is mock_mt5

    def test_get_adapter_stock_returns_alpaca(self, router_both, mock_alpaca):
        """Test stock symbol returns Alpaca adapter."""
        adapter = router_both.get_adapter("AAPL")
        assert adapter is mock_alpaca

    def test_get_adapter_no_mt5_returns_none_for_forex(self, router_alpaca_only):
        """Test forex symbol returns None when MT5 not configured."""
        adapter = router_alpaca_only.get_adapter("EURUSD")
        assert adapter is None

    def test_get_adapter_no_alpaca_returns_none_for_stock(self, router_mt5_only):
        """Test stock symbol returns None when Alpaca not configured."""
        adapter = router_mt5_only.get_adapter("AAPL")
        assert adapter is None

    async def test_route_forex_order(self, router_both, mock_mt5, safe_portfolio, safe_risk_pct):
        """Test routing a forex order to MT5."""
        order = Order(
            platform="TradingView",
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("1.0"),
        )

        report = await router_both.route_order(
            order, portfolio_state=safe_portfolio, trade_risk_pct=safe_risk_pct
        )

        mock_mt5.place_order.assert_called_once_with(order)
        assert report.status == OrderStatus.FILLED
        assert report.platform == "MetaTrader5"

    async def test_route_stock_order(self, router_both, mock_alpaca, safe_portfolio, safe_risk_pct):
        """Test routing a stock order to Alpaca."""
        order = Order(
            platform="TradingView",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("100"),
            limit_price=Decimal("150.50"),
        )

        report = await router_both.route_order(
            order, portfolio_state=safe_portfolio, trade_risk_pct=safe_risk_pct
        )

        mock_alpaca.place_order.assert_called_once_with(order)
        assert report.status == OrderStatus.SUBMITTED
        assert report.platform == "Alpaca"

    async def test_route_order_no_adapter_returns_rejected(
        self, router_none, safe_portfolio, safe_risk_pct
    ):
        """Test routing when no adapter is available returns rejected report."""
        order = Order(
            platform="TradingView",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100"),
        )

        report = await router_none.route_order(
            order, portfolio_state=safe_portfolio, trade_risk_pct=safe_risk_pct
        )

        assert report.status == OrderStatus.REJECTED
        assert "No broker adapter configured" in report.error_message

    async def test_route_forex_no_mt5_returns_rejected(
        self, router_alpaca_only, safe_portfolio, safe_risk_pct
    ):
        """Test routing forex when MT5 not configured returns rejected."""
        order = Order(
            platform="TradingView",
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("1.0"),
        )

        report = await router_alpaca_only.route_order(
            order, portfolio_state=safe_portfolio, trade_risk_pct=safe_risk_pct
        )

        assert report.status == OrderStatus.REJECTED
        assert "forex" in report.error_message

    async def test_route_stock_no_alpaca_returns_rejected(
        self, router_mt5_only, safe_portfolio, safe_risk_pct
    ):
        """Test routing stock when Alpaca not configured returns rejected."""
        order = Order(
            platform="TradingView",
            symbol="MSFT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal("50"),
        )

        report = await router_mt5_only.route_order(
            order, portfolio_state=safe_portfolio, trade_risk_pct=safe_risk_pct
        )

        assert report.status == OrderStatus.REJECTED
        assert "stock" in report.error_message

    async def test_route_order_adapter_disconnected_still_routes(
        self, router_both, mock_mt5, safe_portfolio, safe_risk_pct
    ):
        """Test that orders are still forwarded to disconnected adapters (adapter handles reconnection)."""
        mock_mt5.is_connected.return_value = False

        order = Order(
            platform="TradingView",
            symbol="GBPUSD",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.5"),
        )

        report = await router_both.route_order(
            order, portfolio_state=safe_portfolio, trade_risk_pct=safe_risk_pct
        )

        # Should still try to place the order (adapter handles reconnection internally)
        mock_mt5.place_order.assert_called_once_with(order)
        assert report.status == OrderStatus.FILLED


class TestBrokerRouterRiskGateIntegration:
    """Test risk gate integration in BrokerRouter (Story 23.11 M-5)."""

    @pytest.fixture
    def mock_alpaca(self):
        adapter = MagicMock()
        adapter.platform_name = "Alpaca"
        adapter.is_connected.return_value = True
        adapter.place_order = AsyncMock(
            return_value=ExecutionReport(
                order_id="00000000-0000-0000-0000-000000000001",
                platform_order_id="ALP-123",
                platform="Alpaca",
                status=OrderStatus.FILLED,
                filled_quantity=Decimal("100"),
                remaining_quantity=Decimal("0"),
            )
        )
        return adapter

    @pytest.fixture
    def router(self, mock_alpaca):
        return BrokerRouter(alpaca_adapter=mock_alpaca)

    async def test_route_order_with_valid_risk_passes(self, router, mock_alpaca):
        """Order with valid risk params should pass through to broker."""
        order = Order(
            platform="TradingView",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100"),
        )
        portfolio = PortfolioState(
            account_equity=Decimal("100000"),
            current_heat_pct=Decimal("3.0"),
        )

        report = await router.route_order(
            order, portfolio_state=portfolio, trade_risk_pct=Decimal("1.0")
        )

        assert report.status == OrderStatus.FILLED
        mock_alpaca.place_order.assert_called_once_with(order)

    async def test_route_order_risk_exceeds_limit_blocked(self, router, mock_alpaca):
        """Order exceeding risk limits should be blocked without reaching broker."""
        order = Order(
            platform="TradingView",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100"),
        )
        portfolio = PortfolioState(
            account_equity=Decimal("100000"),
            current_heat_pct=Decimal("9.0"),
        )

        report = await router.route_order(
            order, portfolio_state=portfolio, trade_risk_pct=Decimal("3.0")
        )

        assert report.status == OrderStatus.REJECTED
        assert "Risk gate blocked" in report.error_message
        mock_alpaca.place_order.assert_not_called()

    async def test_route_order_at_exact_limit_blocked(self, router, mock_alpaca):
        """Order at exact risk limit (>=) should be blocked."""
        order = Order(
            platform="TradingView",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100"),
        )
        portfolio = PortfolioState(
            account_equity=Decimal("100000"),
            current_heat_pct=Decimal("0"),
        )

        report = await router.route_order(
            order, portfolio_state=portfolio, trade_risk_pct=Decimal("2.0")
        )

        assert report.status == OrderStatus.REJECTED
        assert "Risk gate blocked" in report.error_message
        mock_alpaca.place_order.assert_not_called()
