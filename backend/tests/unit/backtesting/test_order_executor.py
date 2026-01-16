"""
Unit Tests for OrderExecutor (Story 18.9.3)

Tests for order execution logic including cost modeling, slippage calculation,
and both market and limit order handling.

Author: Story 18.9.3
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.engine.order_executor import (
    ExecutionResult,
    NoCostModel,
    OrderExecutor,
    SimpleCostModel,
)
from src.models.backtest import BacktestOrder
from src.models.ohlcv import OHLCVBar


class TestNoCostModel:
    """Tests for NoCostModel (zero-cost default)."""

    @pytest.fixture
    def cost_model(self):
        """Create NoCostModel instance."""
        return NoCostModel()

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
        """AC3: NoCostModel returns zero commission."""
        commission = cost_model.calculate_commission(sample_order)
        assert commission == Decimal("0")

    def test_zero_slippage(self, cost_model, sample_order, sample_bar):
        """AC3: NoCostModel returns zero slippage."""
        slippage = cost_model.calculate_slippage(sample_order, sample_bar)
        assert slippage == Decimal("0")


class TestSimpleCostModel:
    """Tests for SimpleCostModel with configurable costs."""

    def test_default_values(self):
        """AC3: SimpleCostModel has sensible defaults."""
        model = SimpleCostModel()

        order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=100,
            status="PENDING",
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        )

        commission = model.calculate_commission(order)
        assert commission == Decimal("1.00")

    def test_custom_commission(self):
        """AC3: SimpleCostModel accepts custom commission."""
        model = SimpleCostModel(commission_per_trade=Decimal("2.50"))

        order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=100,
            status="PENDING",
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        )

        commission = model.calculate_commission(order)
        assert commission == Decimal("2.50")

    def test_slippage_for_buy_order(self):
        """AC3: SimpleCostModel calculates positive slippage for BUY."""
        model = SimpleCostModel(slippage_pct=Decimal("0.001"))  # 0.1%

        order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=100,
            status="PENDING",
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        )

        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("102.00"),
            low=Decimal("99.00"),
            close=Decimal("100.00"),
            volume=1000000,
            spread=Decimal("3.00"),
        )

        slippage = model.calculate_slippage(order, bar)
        # 0.1% of $100 = $0.10
        assert slippage == Decimal("0.100")

    def test_slippage_for_sell_order(self):
        """AC3: SimpleCostModel calculates negative slippage for SELL."""
        model = SimpleCostModel(slippage_pct=Decimal("0.001"))  # 0.1%

        order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="SELL",
            quantity=100,
            status="PENDING",
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        )

        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("102.00"),
            low=Decimal("99.00"),
            close=Decimal("100.00"),
            volume=1000000,
            spread=Decimal("3.00"),
        )

        slippage = model.calculate_slippage(order, bar)
        # -0.1% of $100 = -$0.10
        assert slippage == Decimal("-0.100")

    def test_commission_validation(self):
        """AC3: SimpleCostModel validates commission not negative."""
        with pytest.raises(ValueError, match="Commission cannot be negative"):
            SimpleCostModel(commission_per_trade=Decimal("-1.00"))

    def test_slippage_validation(self):
        """AC3: SimpleCostModel validates slippage range."""
        with pytest.raises(ValueError, match="Slippage must be in"):
            SimpleCostModel(slippage_pct=Decimal("-0.01"))

        with pytest.raises(ValueError, match="Slippage must be in"):
            SimpleCostModel(slippage_pct=Decimal("0.15"))  # > 10%

        # Edge cases: 0 and 0.1 should be valid
        model_zero = SimpleCostModel(slippage_pct=Decimal("0"))
        assert model_zero is not None

        model_max = SimpleCostModel(slippage_pct=Decimal("0.1"))
        assert model_max is not None


class TestOrderExecutorInit:
    """Tests for OrderExecutor initialization."""

    def test_default_initialization(self):
        """AC2: OrderExecutor initializes with defaults."""
        executor = OrderExecutor()

        assert executor.enable_costs is True

    def test_custom_cost_model(self):
        """AC2: OrderExecutor accepts custom cost model."""
        cost_model = SimpleCostModel(commission_per_trade=Decimal("5.00"))
        executor = OrderExecutor(cost_model=cost_model, enable_costs=True)

        assert executor.enable_costs is True

    def test_disable_costs(self):
        """AC2: OrderExecutor can disable costs."""
        executor = OrderExecutor(enable_costs=False)

        assert executor.enable_costs is False


class TestOrderExecutorMarketOrders:
    """Tests for OrderExecutor market order execution."""

    @pytest.fixture
    def executor(self):
        """Create OrderExecutor with simple cost model."""
        cost_model = SimpleCostModel(
            commission_per_trade=Decimal("1.00"),
            slippage_pct=Decimal("0.001"),  # 0.1%
        )
        return OrderExecutor(cost_model=cost_model, enable_costs=True)

    @pytest.fixture
    def market_buy_order(self):
        """Create a market BUY order."""
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
    def market_sell_order(self):
        """Create a market SELL order."""
        return BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="SELL",
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

    def test_execute_market_buy(self, executor, market_buy_order, sample_bar):
        """AC3: Market BUY executes at close + slippage."""
        result = executor.execute(market_buy_order, sample_bar)

        assert isinstance(result, ExecutionResult)
        assert result.success is True
        # Fill price = $151 + 0.1% = $151.151
        assert result.fill_price == Decimal("151.151")
        assert result.commission == Decimal("1.00")
        assert result.slippage == Decimal("0.151")
        assert result.filled_timestamp == sample_bar.timestamp

    def test_execute_market_sell(self, executor, market_sell_order, sample_bar):
        """AC3: Market SELL executes at close - slippage."""
        result = executor.execute(market_sell_order, sample_bar)

        assert result.success is True
        # Fill price = $151 - 0.1% = $150.849
        assert result.fill_price == Decimal("150.849")
        assert result.slippage == Decimal("-0.151")

    def test_execute_without_costs(self, market_buy_order, sample_bar):
        """AC3: Order executes without costs when disabled."""
        executor = OrderExecutor(enable_costs=False)

        result = executor.execute(market_buy_order, sample_bar)

        assert result.success is True
        assert result.fill_price == sample_bar.close  # No slippage
        assert result.commission == Decimal("0")
        assert result.slippage == Decimal("0")


class TestOrderExecutorLimitOrders:
    """Tests for OrderExecutor limit order execution."""

    @pytest.fixture
    def executor(self):
        """Create OrderExecutor with simple cost model."""
        cost_model = SimpleCostModel(
            commission_per_trade=Decimal("1.00"),
            slippage_pct=Decimal("0.001"),
        )
        return OrderExecutor(cost_model=cost_model, enable_costs=True)

    @pytest.fixture
    def limit_buy_order(self):
        """Create a limit BUY order."""
        return BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="LIMIT",
            side="BUY",
            quantity=100,
            limit_price=Decimal("149.00"),
            status="PENDING",
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        )

    @pytest.fixture
    def limit_sell_order(self):
        """Create a limit SELL order."""
        return BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="LIMIT",
            side="SELL",
            quantity=100,
            limit_price=Decimal("152.00"),
            status="PENDING",
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        )

    def test_limit_buy_fills_when_price_reaches(self, executor, limit_buy_order):
        """AC3: Limit BUY fills when low reaches limit price."""
        # Bar low is below limit price
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("150.00"),
            high=Decimal("152.00"),
            low=Decimal("148.00"),  # Below limit of $149
            close=Decimal("151.00"),
            volume=1000000,
            spread=Decimal("4.00"),
        )

        result = executor.execute(limit_buy_order, bar)

        assert result.success is True
        assert result.fill_price == Decimal("149.00")  # Fills at limit
        assert result.commission == Decimal("1.00")

    def test_limit_buy_rejected_when_price_not_reached(self, executor, limit_buy_order):
        """AC3: Limit BUY rejected when low doesn't reach limit."""
        # Bar low is above limit price
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("150.00"),
            high=Decimal("152.00"),
            low=Decimal("149.50"),  # Above limit of $149
            close=Decimal("151.00"),
            volume=1000000,
            spread=Decimal("2.50"),
        )

        result = executor.execute(limit_buy_order, bar)

        assert result.success is False
        assert result.rejection_reason == "Limit price not reached"
        assert result.fill_price == Decimal("0")
        assert result.commission == Decimal("0")

    def test_limit_sell_fills_when_price_reaches(self, executor, limit_sell_order):
        """AC3: Limit SELL fills when high reaches limit price."""
        # Bar high is above limit price
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("150.00"),
            high=Decimal("153.00"),  # Above limit of $152
            low=Decimal("149.00"),
            close=Decimal("151.00"),
            volume=1000000,
            spread=Decimal("4.00"),
        )

        result = executor.execute(limit_sell_order, bar)

        assert result.success is True
        assert result.fill_price == Decimal("152.00")  # Fills at limit

    def test_limit_sell_rejected_when_price_not_reached(self, executor, limit_sell_order):
        """AC3: Limit SELL rejected when high doesn't reach limit."""
        # Bar high is below limit price
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("150.00"),
            high=Decimal("151.50"),  # Below limit of $152
            low=Decimal("149.00"),
            close=Decimal("151.00"),
            volume=1000000,
            spread=Decimal("2.50"),
        )

        result = executor.execute(limit_sell_order, bar)

        assert result.success is False
        assert result.rejection_reason == "Limit price not reached"

    def test_limit_order_without_limit_price(self, executor):
        """AC3: Limit order without limit_price is rejected."""
        order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="LIMIT",
            side="BUY",
            quantity=100,
            limit_price=None,  # Missing limit price
            status="PENDING",
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        )

        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("150.00"),
            high=Decimal("152.00"),
            low=Decimal("148.00"),
            close=Decimal("151.00"),
            volume=1000000,
            spread=Decimal("4.00"),
        )

        result = executor.execute(order, bar)

        assert result.success is False
        assert result.rejection_reason == "Limit price not reached"


class TestOrderExecutorApplyFill:
    """Tests for OrderExecutor.apply_fill_to_order method."""

    @pytest.fixture
    def executor(self):
        """Create OrderExecutor."""
        return OrderExecutor()

    @pytest.fixture
    def pending_order(self):
        """Create a pending order."""
        return BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=100,
            status="PENDING",
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        )

    def test_apply_successful_fill(self, executor, pending_order):
        """AC2: Apply successful fill updates order correctly."""
        result = ExecutionResult(
            order_id=str(pending_order.order_id),
            fill_price=Decimal("151.50"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.15"),
            filled_timestamp=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            success=True,
        )

        updated_order = executor.apply_fill_to_order(pending_order, result)

        assert updated_order.status == "FILLED"
        assert updated_order.fill_price == Decimal("151.50")
        assert updated_order.commission == Decimal("1.00")
        assert updated_order.slippage == Decimal("0.15")
        assert updated_order.filled_bar_timestamp == result.filled_timestamp

    def test_apply_rejected_fill(self, executor, pending_order):
        """AC2: Apply rejected fill updates order status."""
        result = ExecutionResult(
            order_id=str(pending_order.order_id),
            fill_price=Decimal("0"),
            commission=Decimal("0"),
            slippage=Decimal("0"),
            filled_timestamp=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            success=False,
            rejection_reason="Limit price not reached",
        )

        updated_order = executor.apply_fill_to_order(pending_order, result)

        assert updated_order.status == "REJECTED"


class TestExecutionResultDataclass:
    """Tests for ExecutionResult dataclass."""

    def test_successful_result(self):
        """AC2: ExecutionResult can represent successful execution."""
        result = ExecutionResult(
            order_id="test-123",
            fill_price=Decimal("151.00"),
            commission=Decimal("1.00"),
            slippage=Decimal("0.15"),
            filled_timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            success=True,
        )

        assert result.success is True
        assert result.rejection_reason is None

    def test_failed_result(self):
        """AC2: ExecutionResult can represent failed execution."""
        result = ExecutionResult(
            order_id="test-456",
            fill_price=Decimal("0"),
            commission=Decimal("0"),
            slippage=Decimal("0"),
            filled_timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            success=False,
            rejection_reason="Insufficient funds",
        )

        assert result.success is False
        assert result.rejection_reason == "Insufficient funds"


class TestOrderExecutorEnableCosts:
    """Tests for enable_costs property."""

    def test_enable_costs_setter(self):
        """AC2: enable_costs can be toggled at runtime."""
        executor = OrderExecutor(enable_costs=True)
        assert executor.enable_costs is True

        executor.enable_costs = False
        assert executor.enable_costs is False

        executor.enable_costs = True
        assert executor.enable_costs is True
