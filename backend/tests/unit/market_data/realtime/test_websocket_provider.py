"""
Unit tests for WebSocket provider models and types.

Tests the MarketBar dataclass and ConnectionState enum.
"""

from datetime import UTC, datetime
from decimal import Decimal

from src.market_data.realtime.websocket_provider import (
    ConnectionState,
    MarketBar,
)


class TestConnectionState:
    """Tests for ConnectionState enum."""

    def test_all_states_defined(self):
        """Test all expected connection states exist."""
        assert ConnectionState.DISCONNECTED.value == "disconnected"
        assert ConnectionState.CONNECTING.value == "connecting"
        assert ConnectionState.CONNECTED.value == "connected"
        assert ConnectionState.RECONNECTING.value == "reconnecting"
        assert ConnectionState.ERROR.value == "error"

    def test_state_count(self):
        """Test expected number of states."""
        assert len(ConnectionState) == 5


class TestMarketBar:
    """Tests for MarketBar dataclass."""

    def test_create_market_bar(self):
        """Test creating a MarketBar."""
        bar = MarketBar(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
            open=Decimal("150.00"),
            high=Decimal("152.00"),
            low=Decimal("149.50"),
            close=Decimal("151.50"),
            volume=1000000,
            timeframe="1m",
        )

        assert bar.symbol == "AAPL"
        assert bar.open == Decimal("150.00")
        assert bar.high == Decimal("152.00")
        assert bar.low == Decimal("149.50")
        assert bar.close == Decimal("151.50")
        assert bar.volume == 1000000
        assert bar.timeframe == "1m"

    def test_default_timeframe(self):
        """Test default timeframe is 1m."""
        bar = MarketBar(
            symbol="AAPL",
            timestamp=datetime.now(UTC),
            open=Decimal("150.00"),
            high=Decimal("152.00"),
            low=Decimal("149.50"),
            close=Decimal("151.50"),
            volume=1000000,
        )

        assert bar.timeframe == "1m"

    def test_spread_property(self):
        """Test spread calculation."""
        bar = MarketBar(
            symbol="AAPL",
            timestamp=datetime.now(UTC),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("148.00"),
            close=Decimal("153.00"),
            volume=1000000,
        )

        assert bar.spread == Decimal("7.00")  # 155 - 148

    def test_spread_zero(self):
        """Test spread when high equals low."""
        bar = MarketBar(
            symbol="AAPL",
            timestamp=datetime.now(UTC),
            open=Decimal("150.00"),
            high=Decimal("150.00"),
            low=Decimal("150.00"),
            close=Decimal("150.00"),
            volume=1000000,
        )

        assert bar.spread == Decimal("0.00")

    def test_market_bar_immutability(self):
        """Test that MarketBar fields can be accessed as expected."""
        bar = MarketBar(
            symbol="TSLA",
            timestamp=datetime.now(UTC),
            open=Decimal("250.00"),
            high=Decimal("260.00"),
            low=Decimal("245.00"),
            close=Decimal("255.00"),
            volume=5000000,
            timeframe="5m",
        )

        # Dataclass fields are accessible
        assert bar.symbol == "TSLA"
        assert bar.timeframe == "5m"
        assert bar.volume == 5000000
