"""
Unit tests for OrderBuilder service (Story 16.4a).

Tests building orders from trade signals for platform execution.
"""

from decimal import Decimal

import pytest

from src.brokers.order_builder import OrderBuilder
from src.models.order import OCOOrder, Order, OrderSide, OrderType
from tests.fixtures.signal_fixtures import valid_spring_signal


class TestOrderBuilder:
    """Test suite for OrderBuilder service."""

    @pytest.fixture
    def order_builder(self):
        """Create OrderBuilder instance."""
        return OrderBuilder(default_platform="TradingView")

    @pytest.fixture
    def sample_signal(self):
        """Create sample TradeSignal for testing."""
        return valid_spring_signal()

    def test_builder_initialization(self, order_builder):
        """Test OrderBuilder initializes correctly."""
        assert order_builder.default_platform == "TradingView"

    def test_build_entry_order_market(self, order_builder, sample_signal):
        """Test building market entry order."""
        order = order_builder.build_entry_order(signal=sample_signal, order_type=OrderType.MARKET)

        assert isinstance(order, Order)
        assert order.signal_id == sample_signal.id
        assert order.campaign_id == sample_signal.campaign_id
        assert order.platform == "TradingView"
        assert order.symbol == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.MARKET
        assert order.quantity == Decimal("100")
        assert order.limit_price is None
        assert order.stop_loss == sample_signal.stop_loss
        assert order.take_profit == sample_signal.target_levels.primary_target

    def test_build_entry_order_limit(self, order_builder, sample_signal):
        """Test building limit entry order."""
        order = order_builder.build_entry_order(signal=sample_signal, order_type=OrderType.LIMIT)

        assert order.order_type == OrderType.LIMIT
        assert order.limit_price == Decimal("150.00")

    def test_build_entry_order_custom_platform(self, order_builder, sample_signal):
        """Test building order for custom platform."""
        order = order_builder.build_entry_order(signal=sample_signal, platform="MetaTrader5")

        assert order.platform == "MetaTrader5"

    def test_build_entry_order_missing_symbol(self, order_builder, sample_signal):
        """Test building order fails with missing symbol."""
        sample_signal.symbol = ""

        with pytest.raises(ValueError, match="Signal must have symbol"):
            order_builder.build_entry_order(sample_signal)

    def test_build_entry_order_invalid_position_size(self, order_builder, sample_signal):
        """Test building order fails with invalid position size."""
        sample_signal.position_size = Decimal("-10")

        with pytest.raises(ValueError, match="Invalid position size"):
            order_builder.build_entry_order(sample_signal)

    def test_build_stop_loss_order(self, order_builder, sample_signal):
        """Test building stop loss order."""
        order = order_builder.build_stop_loss_order(signal=sample_signal)

        assert isinstance(order, Order)
        assert order.symbol == "AAPL"
        assert order.side == OrderSide.SELL
        assert order.order_type == OrderType.STOP
        assert order.quantity == Decimal("100")
        assert order.stop_price == Decimal("145.00")

    def test_build_stop_loss_order_missing_stop(self, order_builder, sample_signal):
        """Test building stop loss fails without stop_loss."""
        sample_signal.stop_loss = None

        with pytest.raises(ValueError, match="must have stop_loss"):
            order_builder.build_stop_loss_order(sample_signal)

    def test_build_take_profit_order(self, order_builder, sample_signal):
        """Test building take profit order."""
        order = order_builder.build_take_profit_order(signal=sample_signal)

        assert isinstance(order, Order)
        assert order.symbol == "AAPL"
        assert order.side == OrderSide.SELL
        assert order.order_type == OrderType.LIMIT
        assert order.quantity == Decimal("100")
        assert order.limit_price == Decimal("160.00")

    def test_build_take_profit_order_custom_target(self, order_builder, sample_signal):
        """Test building take profit with custom target price."""
        order = order_builder.build_take_profit_order(
            signal=sample_signal, target_price=Decimal("165.00")
        )

        assert order.limit_price == Decimal("165.00")

    def test_build_take_profit_order_missing_targets(self, order_builder, sample_signal):
        """Test building take profit fails without targets."""
        sample_signal.target_levels = None

        with pytest.raises(ValueError, match="must have target_levels"):
            order_builder.build_take_profit_order(sample_signal)

    def test_build_oco_order(self, order_builder, sample_signal):
        """Test building OCO order group."""
        oco = order_builder.build_oco_order(signal=sample_signal)

        assert isinstance(oco, OCOOrder)
        assert isinstance(oco.primary_order, Order)
        assert isinstance(oco.stop_loss_order, Order)
        assert isinstance(oco.take_profit_order, Order)

        # Verify primary order
        assert oco.primary_order.symbol == "AAPL"
        assert oco.primary_order.side == OrderSide.BUY
        assert oco.primary_order.order_type == OrderType.MARKET

        # Verify stop loss order
        assert oco.stop_loss_order.side == OrderSide.SELL
        assert oco.stop_loss_order.order_type == OrderType.STOP
        assert oco.stop_loss_order.stop_price == Decimal("145.00")

        # Verify take profit order
        assert oco.take_profit_order.side == OrderSide.SELL
        assert oco.take_profit_order.order_type == OrderType.LIMIT
        assert oco.take_profit_order.limit_price == Decimal("160.00")

    def test_build_oco_order_limit_entry(self, order_builder, sample_signal):
        """Test building OCO with limit entry order."""
        oco = order_builder.build_oco_order(signal=sample_signal, entry_order_type=OrderType.LIMIT)

        assert oco.primary_order.order_type == OrderType.LIMIT
        assert oco.primary_order.limit_price == Decimal("150.00")

    def test_build_partial_exit_order(self, order_builder, sample_signal):
        """Test building partial exit order."""
        order = order_builder.build_partial_exit_order(
            signal=sample_signal,
            exit_quantity=Decimal("50"),
            exit_price=Decimal("155.00"),
        )

        assert order.symbol == "AAPL"
        assert order.side == OrderSide.SELL
        assert order.order_type == OrderType.LIMIT
        assert order.quantity == Decimal("50")
        assert order.limit_price == Decimal("155.00")

    def test_build_partial_exit_invalid_quantity(self, order_builder, sample_signal):
        """Test partial exit fails with invalid quantity."""
        with pytest.raises(ValueError, match="Invalid exit quantity"):
            order_builder.build_partial_exit_order(
                signal=sample_signal,
                exit_quantity=Decimal("150"),  # > position_size
                exit_price=Decimal("155.00"),
            )

    def test_build_partial_exit_negative_quantity(self, order_builder, sample_signal):
        """Test partial exit fails with negative quantity."""
        with pytest.raises(ValueError, match="Invalid exit quantity"):
            order_builder.build_partial_exit_order(
                signal=sample_signal,
                exit_quantity=Decimal("-10"),
                exit_price=Decimal("155.00"),
            )

    def test_validate_signal_for_order_success(self, order_builder, sample_signal):
        """Test signal validation succeeds for valid signal."""
        assert order_builder.validate_signal_for_order(sample_signal) is True

    def test_validate_signal_missing_symbol(self, order_builder, sample_signal):
        """Test validation fails for missing symbol."""
        sample_signal.symbol = ""

        with pytest.raises(ValueError, match="Missing symbol"):
            order_builder.validate_signal_for_order(sample_signal)

    def test_validate_signal_invalid_position_size(self, order_builder, sample_signal):
        """Test validation fails for invalid position size."""
        sample_signal.position_size = Decimal("-10")

        with pytest.raises(ValueError, match="Invalid position_size"):
            order_builder.validate_signal_for_order(sample_signal)

    def test_validate_signal_invalid_entry_price(self, order_builder, sample_signal):
        """Test validation fails for invalid entry price."""
        sample_signal.entry_price = Decimal("0")

        with pytest.raises(ValueError, match="Invalid entry_price"):
            order_builder.validate_signal_for_order(sample_signal)

    def test_validate_signal_invalid_stop_loss(self, order_builder, sample_signal):
        """Test validation fails for invalid stop loss."""
        sample_signal.stop_loss = None

        with pytest.raises(ValueError, match="Invalid stop_loss"):
            order_builder.validate_signal_for_order(sample_signal)

    def test_validate_signal_missing_targets(self, order_builder, sample_signal):
        """Test validation fails for missing targets."""
        sample_signal.target_levels = None

        with pytest.raises(ValueError, match="Missing target_levels"):
            order_builder.validate_signal_for_order(sample_signal)

    def test_validate_signal_stop_above_entry(self, order_builder, sample_signal):
        """Test validation fails when stop loss above entry."""
        sample_signal.stop_loss = Decimal("155.00")  # Above entry price

        with pytest.raises(ValueError, match="Stop loss .* must be below entry"):
            order_builder.validate_signal_for_order(sample_signal)
