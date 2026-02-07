"""
Unit Tests for UnifiedBacktestEngine (Story 18.9.2)

Tests for the unified backtest engine with dependency injection.
Validates bar-by-bar processing, signal handling, and result generation.

Author: Story 18.9.2
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import uuid4

import pytest

from src.backtesting.engine import (
    EngineConfig,
    UnifiedBacktestEngine,
)
from src.backtesting.position_manager import PositionManager
from src.models.backtest import BacktestOrder, EquityCurvePoint
from src.models.ohlcv import OHLCVBar

# --- Mock Implementations ---


@dataclass
class MockTradeSignal:
    """Simplified mock signal for testing (only fields used by engine)."""

    direction: str = "LONG"


class MockSignalDetector:
    """Mock signal detector for testing."""

    def __init__(self, signals: Optional[dict[int, Any]] = None):
        """
        Initialize with optional signals at specific indices.

        Args:
            signals: Dict mapping bar index to signal to return
        """
        self.signals = signals or {}
        self.detect_calls: list[tuple[list[OHLCVBar], int]] = []

    def detect(self, bars: list[OHLCVBar], index: int) -> Optional[Any]:
        """Return signal if configured for this index."""
        self.detect_calls.append((bars, index))
        return self.signals.get(index)


class MockCostModel:
    """Mock cost model for testing."""

    def __init__(
        self,
        commission: Decimal = Decimal("1.00"),
        slippage: Decimal = Decimal("0.01"),
    ):
        self.commission = commission
        self.slippage = slippage
        self.commission_calls: list[BacktestOrder] = []
        self.slippage_calls: list[tuple[BacktestOrder, OHLCVBar]] = []

    def calculate_commission(self, order: BacktestOrder) -> Decimal:
        self.commission_calls.append(order)
        return self.commission

    def calculate_slippage(self, order: BacktestOrder, bar: OHLCVBar) -> Decimal:
        self.slippage_calls.append((order, bar))
        return self.slippage


# --- Fixtures ---


@pytest.fixture
def sample_bar() -> OHLCVBar:
    """Create a sample OHLCV bar."""
    return OHLCVBar(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        open=Decimal("150.00"),
        high=Decimal("152.00"),
        low=Decimal("149.00"),
        close=Decimal("151.00"),
        volume=1000000,
        spread=Decimal("3.00"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("1.0"),
    )


@pytest.fixture
def sample_bars() -> list[OHLCVBar]:
    """Create a list of sample OHLCV bars."""
    bars = []
    base_price = Decimal("100.00")

    for i in range(10):
        bars.append(
            OHLCVBar(
                id=uuid4(),
                symbol="AAPL",
                timeframe="1d",
                timestamp=datetime(2024, 1, 15 + i, 9, 30, tzinfo=UTC),
                open=base_price + Decimal(str(i)),
                high=base_price + Decimal(str(i + 2)),
                low=base_price + Decimal(str(i - 1)),
                close=base_price + Decimal(str(i + 1)),
                volume=1000000 + i * 10000,
                spread=Decimal("3.00"),
                spread_ratio=Decimal("1.0"),
                volume_ratio=Decimal("1.0"),
            )
        )
    return bars


@pytest.fixture
def sample_signal() -> MockTradeSignal:
    """Create a sample mock trade signal."""
    return MockTradeSignal(direction="LONG")


@pytest.fixture
def default_config() -> EngineConfig:
    """Create default engine configuration."""
    return EngineConfig()


@pytest.fixture
def mock_detector() -> MockSignalDetector:
    """Create mock signal detector."""
    return MockSignalDetector()


@pytest.fixture
def mock_cost_model() -> MockCostModel:
    """Create mock cost model."""
    return MockCostModel()


# --- Test Classes ---


class TestUnifiedBacktestEngineInit:
    """Tests for UnifiedBacktestEngine initialization."""

    def test_init_accepts_dependencies(
        self,
        default_config: EngineConfig,
        mock_detector: MockSignalDetector,
        mock_cost_model: MockCostModel,
    ):
        """AC2: Engine accepts injected dependencies without error."""
        position_manager = PositionManager(default_config.initial_capital)

        # Should not raise - verifies constructor accepts all dependencies
        engine = UnifiedBacktestEngine(
            signal_detector=mock_detector,
            cost_model=mock_cost_model,
            position_manager=position_manager,
            config=default_config,
        )

        # Verify engine is usable (tests behavior, not internal state)
        assert engine is not None

    def test_injected_dependencies_are_used(
        self,
        sample_bars: list[OHLCVBar],
        default_config: EngineConfig,
        mock_cost_model: MockCostModel,
    ):
        """AC2: Injected dependencies are actually used during execution."""
        # Create detector that returns a signal
        signal = MockTradeSignal(direction="LONG")
        detector = MockSignalDetector(signals={2: signal})
        position_manager = PositionManager(default_config.initial_capital)

        engine = UnifiedBacktestEngine(
            signal_detector=detector,
            cost_model=mock_cost_model,
            position_manager=position_manager,
            config=default_config,
        )

        engine.run(sample_bars)

        # Verify detector was called (dependency was used)
        assert len(detector.detect_calls) == len(sample_bars)
        # Verify cost model was called when signal triggered
        assert len(mock_cost_model.commission_calls) > 0


class TestUnifiedBacktestEngineRun:
    """Tests for UnifiedBacktestEngine.run() method."""

    def test_run_processes_all_bars(
        self,
        sample_bars: list[OHLCVBar],
        default_config: EngineConfig,
        mock_detector: MockSignalDetector,
        mock_cost_model: MockCostModel,
    ):
        """AC3: run() processes each bar sequentially."""
        position_manager = PositionManager(default_config.initial_capital)
        engine = UnifiedBacktestEngine(
            mock_detector, mock_cost_model, position_manager, default_config
        )

        result = engine.run(sample_bars)

        # Detector should be called for each bar
        assert len(mock_detector.detect_calls) == len(sample_bars)

    def test_run_returns_backtest_result(
        self,
        sample_bars: list[OHLCVBar],
        default_config: EngineConfig,
        mock_detector: MockSignalDetector,
        mock_cost_model: MockCostModel,
    ):
        """AC3: run() returns BacktestResult."""
        position_manager = PositionManager(default_config.initial_capital)
        engine = UnifiedBacktestEngine(
            mock_detector, mock_cost_model, position_manager, default_config
        )

        result = engine.run(sample_bars)

        assert result is not None
        assert result.symbol == "AAPL"
        assert result.timeframe == "1d"
        assert result.summary is not None

    def test_run_records_equity_curve(
        self,
        sample_bars: list[OHLCVBar],
        default_config: EngineConfig,
        mock_detector: MockSignalDetector,
        mock_cost_model: MockCostModel,
    ):
        """run() records equity curve point for each bar."""
        position_manager = PositionManager(default_config.initial_capital)
        engine = UnifiedBacktestEngine(
            mock_detector, mock_cost_model, position_manager, default_config
        )

        result = engine.run(sample_bars)

        assert len(result.equity_curve) == len(sample_bars)

    def test_run_with_empty_bars(
        self,
        default_config: EngineConfig,
        mock_detector: MockSignalDetector,
        mock_cost_model: MockCostModel,
    ):
        """run() handles empty bar list with warning."""
        position_manager = PositionManager(default_config.initial_capital)
        engine = UnifiedBacktestEngine(
            mock_detector, mock_cost_model, position_manager, default_config
        )

        result = engine.run([])

        assert result.symbol == "EMPTY"  # Changed from UNKNOWN to EMPTY with warning
        assert result.trades == []
        assert result.equity_curve == []


class TestUnifiedBacktestEngineSignalHandling:
    """Tests for signal detection and handling."""

    def test_signal_creates_order(
        self,
        sample_bars: list[OHLCVBar],
        sample_signal: MockTradeSignal,
        default_config: EngineConfig,
        mock_cost_model: MockCostModel,
    ):
        """Signal detection creates an order."""
        detector = MockSignalDetector(signals={2: sample_signal})
        position_manager = PositionManager(default_config.initial_capital)
        engine = UnifiedBacktestEngine(detector, mock_cost_model, position_manager, default_config)

        result = engine.run(sample_bars)

        # Cost model should have been called (order was created)
        assert len(mock_cost_model.commission_calls) > 0

    def test_signal_respects_position_limit(
        self,
        sample_bars: list[OHLCVBar],
        sample_signal: MockTradeSignal,
        mock_cost_model: MockCostModel,
    ):
        """Signals respect max_open_positions limit."""
        config = EngineConfig(max_open_positions=1)

        # Signals at indices 0, 1, 2
        signals = {0: sample_signal, 1: sample_signal, 2: sample_signal}
        detector = MockSignalDetector(signals=signals)
        position_manager = PositionManager(config.initial_capital)

        engine = UnifiedBacktestEngine(detector, mock_cost_model, position_manager, config)

        result = engine.run(sample_bars)

        # Only 1 position should be opened (limit is 1)
        assert position_manager.get_pending_count() <= 1


class TestUnifiedBacktestEngineCostModel:
    """Tests for cost model integration."""

    def test_cost_model_called_when_enabled(
        self,
        sample_bars: list[OHLCVBar],
        sample_signal: MockTradeSignal,
        mock_cost_model: MockCostModel,
    ):
        """AC2: Cost model is called when enabled."""
        config = EngineConfig(enable_cost_model=True)
        detector = MockSignalDetector(signals={2: sample_signal})
        position_manager = PositionManager(config.initial_capital)

        engine = UnifiedBacktestEngine(detector, mock_cost_model, position_manager, config)

        engine.run(sample_bars)

        assert len(mock_cost_model.commission_calls) > 0
        assert len(mock_cost_model.slippage_calls) > 0

    def test_cost_model_skipped_when_disabled(
        self,
        sample_bars: list[OHLCVBar],
        sample_signal: MockTradeSignal,
        mock_cost_model: MockCostModel,
    ):
        """Cost model is skipped when disabled."""
        config = EngineConfig(enable_cost_model=False)
        detector = MockSignalDetector(signals={2: sample_signal})
        position_manager = PositionManager(config.initial_capital)

        engine = UnifiedBacktestEngine(detector, mock_cost_model, position_manager, config)

        engine.run(sample_bars)

        assert len(mock_cost_model.commission_calls) == 0
        assert len(mock_cost_model.slippage_calls) == 0


class TestUnifiedBacktestEnginePositionDelegation:
    """Tests for position management delegation."""

    def test_buy_signal_opens_position(
        self,
        sample_bars: list[OHLCVBar],
        sample_signal: MockTradeSignal,
        default_config: EngineConfig,
        mock_cost_model: MockCostModel,
    ):
        """AC4: BUY signals delegate to position manager."""
        detector = MockSignalDetector(signals={2: sample_signal})
        position_manager = PositionManager(default_config.initial_capital)

        engine = UnifiedBacktestEngine(detector, mock_cost_model, position_manager, default_config)

        engine.run(sample_bars)

        # Position should have been opened
        assert position_manager.has_position("AAPL") or len(position_manager.closed_trades) > 0


class TestUnifiedBacktestEngineMetrics:
    """Tests for metrics calculation."""

    def test_metrics_with_no_trades(
        self,
        sample_bars: list[OHLCVBar],
        default_config: EngineConfig,
        mock_detector: MockSignalDetector,
        mock_cost_model: MockCostModel,
    ):
        """Metrics handle zero trades gracefully."""
        position_manager = PositionManager(default_config.initial_capital)
        engine = UnifiedBacktestEngine(
            mock_detector, mock_cost_model, position_manager, default_config
        )

        result = engine.run(sample_bars)

        assert result.summary.total_trades == 0
        assert result.summary.win_rate == Decimal("0")
        assert result.summary.profit_factor == Decimal("0")

    def test_max_drawdown_calculation(
        self,
        default_config: EngineConfig,
        mock_detector: MockSignalDetector,
        mock_cost_model: MockCostModel,
    ):
        """Max drawdown is calculated correctly."""
        position_manager = PositionManager(default_config.initial_capital)
        engine = UnifiedBacktestEngine(
            mock_detector, mock_cost_model, position_manager, default_config
        )

        # Test with empty equity curve
        assert engine._calculate_max_drawdown() == Decimal("0")


class TestUnifiedBacktestEngineResult:
    """Tests for result generation."""

    def test_result_includes_config(
        self,
        sample_bars: list[OHLCVBar],
        default_config: EngineConfig,
        mock_detector: MockSignalDetector,
        mock_cost_model: MockCostModel,
    ):
        """AC5: Result includes configuration."""
        position_manager = PositionManager(default_config.initial_capital)
        engine = UnifiedBacktestEngine(
            mock_detector, mock_cost_model, position_manager, default_config
        )

        result = engine.run(sample_bars)

        assert result.config is not None
        assert result.config.initial_capital == default_config.initial_capital

    def test_result_includes_execution_time(
        self,
        sample_bars: list[OHLCVBar],
        default_config: EngineConfig,
        mock_detector: MockSignalDetector,
        mock_cost_model: MockCostModel,
    ):
        """Result includes execution time."""
        position_manager = PositionManager(default_config.initial_capital)
        engine = UnifiedBacktestEngine(
            mock_detector, mock_cost_model, position_manager, default_config
        )

        result = engine.run(sample_bars)

        assert result.execution_time_seconds >= Decimal("0")

    def test_result_dates_from_bars(
        self,
        sample_bars: list[OHLCVBar],
        default_config: EngineConfig,
        mock_detector: MockSignalDetector,
        mock_cost_model: MockCostModel,
    ):
        """Result dates are derived from bar data."""
        position_manager = PositionManager(default_config.initial_capital)
        engine = UnifiedBacktestEngine(
            mock_detector, mock_cost_model, position_manager, default_config
        )

        result = engine.run(sample_bars)

        assert result.start_date == sample_bars[0].timestamp.date()
        assert result.end_date == sample_bars[-1].timestamp.date()


class TestUnifiedBacktestEngineExports:
    """Tests for package exports."""

    def test_unified_engine_exported(self):
        """UnifiedBacktestEngine is exported from package."""
        from src.backtesting.engine import UnifiedBacktestEngine

        assert UnifiedBacktestEngine is not None

    def test_exports_in_all_list(self):
        """UnifiedBacktestEngine is in __all__ list."""
        import src.backtesting.engine as engine_module

        assert "UnifiedBacktestEngine" in engine_module.__all__


class TestUnifiedBacktestEngineEdgeCases:
    """Tests for edge cases and additional coverage."""

    def test_sell_signal_when_no_position(
        self,
        sample_bars: list[OHLCVBar],
        default_config: EngineConfig,
        mock_cost_model: MockCostModel,
    ):
        """SELL signal with no position is handled gracefully."""
        sell_signal = MockTradeSignal(direction="SHORT")
        detector = MockSignalDetector(signals={2: sell_signal})
        position_manager = PositionManager(default_config.initial_capital)

        engine = UnifiedBacktestEngine(detector, mock_cost_model, position_manager, default_config)

        # Should not raise even with SELL signal and no position
        result = engine.run(sample_bars)
        assert result is not None

    def test_zero_quantity_order_not_created(
        self,
        default_config: EngineConfig,
        mock_cost_model: MockCostModel,
    ):
        """Order with zero quantity is not created."""
        # Create a bar with very high price so quantity would be 0
        high_price_bar = OHLCVBar(
            id=uuid4(),
            symbol="EXPENSIVE",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("999999999.00"),
            high=Decimal("999999999.00"),
            low=Decimal("999999999.00"),
            close=Decimal("999999999.00"),
            volume=1000,
            spread=Decimal("0"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )

        signal = MockTradeSignal(direction="LONG")
        detector = MockSignalDetector(signals={0: signal})
        position_manager = PositionManager(default_config.initial_capital)

        engine = UnifiedBacktestEngine(detector, mock_cost_model, position_manager, default_config)

        result = engine.run([high_price_bar])

        # No position should be opened because quantity would be 0
        assert not position_manager.has_position("EXPENSIVE")

    def test_metrics_with_winning_and_losing_trades(
        self,
        default_config: EngineConfig,
        mock_detector: MockSignalDetector,
        mock_cost_model: MockCostModel,
    ):
        """Metrics correctly calculate with mixed trades."""
        position_manager = PositionManager(default_config.initial_capital)
        engine = UnifiedBacktestEngine(
            mock_detector, mock_cost_model, position_manager, default_config
        )

        # Create mock trades directly for testing metrics calculation
        from src.models.backtest import BacktestTrade

        winning_trade = BacktestTrade(
            trade_id=uuid4(),
            position_id=uuid4(),
            symbol="AAPL",
            side="LONG",
            quantity=100,
            entry_price=Decimal("100.00"),
            exit_price=Decimal("110.00"),
            entry_timestamp=datetime(2024, 1, 15, tzinfo=UTC),
            exit_timestamp=datetime(2024, 1, 16, tzinfo=UTC),
            realized_pnl=Decimal("1000.00"),
            commission=Decimal("2.00"),
            slippage=Decimal("0.02"),
        )

        losing_trade = BacktestTrade(
            trade_id=uuid4(),
            position_id=uuid4(),
            symbol="AAPL",
            side="LONG",
            quantity=100,
            entry_price=Decimal("100.00"),
            exit_price=Decimal("95.00"),
            entry_timestamp=datetime(2024, 1, 17, tzinfo=UTC),
            exit_timestamp=datetime(2024, 1, 18, tzinfo=UTC),
            realized_pnl=Decimal("-500.00"),
            commission=Decimal("2.00"),
            slippage=Decimal("0.02"),
        )

        trades = [winning_trade, losing_trade]
        metrics = engine._calculate_metrics(trades)

        assert metrics.total_trades == 2
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 1
        assert metrics.win_rate == Decimal("0.5")
        assert metrics.profit_factor == Decimal("2")  # 1000 / 500

    def test_max_drawdown_with_equity_curve(
        self,
        sample_bars: list[OHLCVBar],
        default_config: EngineConfig,
        mock_detector: MockSignalDetector,
        mock_cost_model: MockCostModel,
    ):
        """Max drawdown is calculated from equity curve."""
        position_manager = PositionManager(default_config.initial_capital)
        engine = UnifiedBacktestEngine(
            mock_detector, mock_cost_model, position_manager, default_config
        )

        # Run to generate equity curve
        result = engine.run(sample_bars)

        # Equity curve should have points
        assert len(result.equity_curve) == len(sample_bars)

        # Max drawdown should be calculated (even if 0 for flat curve)
        assert result.summary.max_drawdown >= Decimal("0")

    def test_position_limit_blocks_signals(
        self,
        sample_bars: list[OHLCVBar],
        mock_cost_model: MockCostModel,
    ):
        """Position limit prevents additional orders."""
        config = EngineConfig(max_open_positions=1)
        signal = MockTradeSignal(direction="LONG")

        # Signals at every bar
        signals = {i: signal for i in range(len(sample_bars))}
        detector = MockSignalDetector(signals=signals)
        position_manager = PositionManager(config.initial_capital)

        engine = UnifiedBacktestEngine(detector, mock_cost_model, position_manager, config)

        result = engine.run(sample_bars)

        # Should have at most 1 open position at a time
        assert position_manager.get_pending_count() <= 1

    def test_sell_signal_closes_existing_position(
        self,
        sample_bars: list[OHLCVBar],
        mock_cost_model: MockCostModel,
    ):
        """SELL signal closes an existing position."""
        from unittest.mock import MagicMock

        config = EngineConfig(max_open_positions=2)

        # Signal LONG first, then SELL to close
        signals = {
            0: MockTradeSignal(direction="LONG"),
            5: MockTradeSignal(direction="SHORT"),  # This should trigger close
        }
        detector = MockSignalDetector(signals=signals)

        # Create mock position manager to track close_position call
        position_manager = MagicMock(spec=PositionManager)
        position_manager.get_pending_count.return_value = 0
        position_manager.calculate_portfolio_value.return_value = Decimal("100000")
        position_manager.cash = Decimal("98000")
        position_manager.closed_trades = []
        position_manager.positions = {}  # Required for _check_position_exits iteration
        position_manager.has_position.return_value = True  # Has position to close

        engine = UnifiedBacktestEngine(detector, mock_cost_model, position_manager, config)

        engine.run(sample_bars)

        # close_position should have been called
        assert position_manager.close_position.called

    def test_max_drawdown_calculation_with_values(
        self,
        default_config: EngineConfig,
    ):
        """Max drawdown calculation handles actual drawdown values."""
        from src.backtesting.engine import UnifiedBacktestEngine

        # Setup minimal mocks
        detector = MockSignalDetector()
        cost_model = MockCostModel()
        position_manager = PositionManager(default_config.initial_capital)

        engine = UnifiedBacktestEngine(detector, cost_model, position_manager, default_config)

        # Manually set equity curve with a drawdown scenario
        engine._equity_curve = [
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 15, tzinfo=UTC),
                equity_value=Decimal("100000"),
                portfolio_value=Decimal("100000"),
                cash=Decimal("100000"),
                positions_value=Decimal("0"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 16, tzinfo=UTC),
                equity_value=Decimal("110000"),  # Peak
                portfolio_value=Decimal("110000"),
                cash=Decimal("100000"),
                positions_value=Decimal("10000"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 17, tzinfo=UTC),
                equity_value=Decimal("99000"),  # Drawdown from peak
                portfolio_value=Decimal("99000"),
                cash=Decimal("100000"),
                positions_value=Decimal("-1000"),
            ),
            EquityCurvePoint(
                timestamp=datetime(2024, 1, 18, tzinfo=UTC),
                equity_value=Decimal("105000"),  # Recovery
                portfolio_value=Decimal("105000"),
                cash=Decimal("100000"),
                positions_value=Decimal("5000"),
            ),
        ]

        max_dd = engine._calculate_max_drawdown()

        # Drawdown from 110000 to 99000 = 11000/110000 = 0.10 (10%)
        assert max_dd == Decimal("0.1")

    def test_invalid_signal_direction_skipped(
        self,
        sample_bars: list[OHLCVBar],
        default_config: EngineConfig,
        mock_cost_model: MockCostModel,
    ):
        """Invalid signal direction is logged and skipped."""
        invalid_signal = MockTradeSignal(direction="INVALID")
        detector = MockSignalDetector(signals={2: invalid_signal})
        position_manager = PositionManager(default_config.initial_capital)

        engine = UnifiedBacktestEngine(detector, mock_cost_model, position_manager, default_config)

        result = engine.run(sample_bars)

        # No orders should be created due to invalid direction
        assert len(mock_cost_model.commission_calls) == 0
        assert result is not None

    def test_look_ahead_prevention(
        self,
        sample_bars: list[OHLCVBar],
        default_config: EngineConfig,
        mock_cost_model: MockCostModel,
    ):
        """Detector only receives bars up to current index (no future data)."""

        class LookAheadCheckingDetector:
            """Detector that verifies it only sees past/current bars."""

            def __init__(self):
                self.max_bars_seen: list[int] = []

            def detect(self, bars: list[OHLCVBar], index: int) -> Optional[Any]:
                # Record how many bars we can see at each index
                self.max_bars_seen.append(len(bars))
                # Verify we can only see bars up to and including current index
                assert len(bars) == index + 1, (
                    f"Look-ahead detected: at index {index}, "
                    f"detector received {len(bars)} bars instead of {index + 1}"
                )
                return None

        detector = LookAheadCheckingDetector()
        position_manager = PositionManager(default_config.initial_capital)

        engine = UnifiedBacktestEngine(detector, mock_cost_model, position_manager, default_config)

        # This will raise assertion error if look-ahead is detected
        result = engine.run(sample_bars)

        # Verify detector was called for each bar with correct visible bars
        assert detector.max_bars_seen == list(range(1, len(sample_bars) + 1))

    def test_profit_factor_with_only_winning_trades(
        self,
        default_config: EngineConfig,
        mock_detector: MockSignalDetector,
        mock_cost_model: MockCostModel,
    ):
        """Profit factor uses cap (999.99) when all trades are winners."""
        from src.models.backtest import BacktestTrade

        position_manager = PositionManager(default_config.initial_capital)
        engine = UnifiedBacktestEngine(
            mock_detector, mock_cost_model, position_manager, default_config
        )

        # Create only winning trades
        winning_trades = [
            BacktestTrade(
                trade_id=uuid4(),
                position_id=uuid4(),
                symbol="AAPL",
                side="LONG",
                quantity=100,
                entry_price=Decimal("100.00"),
                exit_price=Decimal("110.00"),
                entry_timestamp=datetime(2024, 1, 15, tzinfo=UTC),
                exit_timestamp=datetime(2024, 1, 16, tzinfo=UTC),
                realized_pnl=Decimal("1000.00"),
                commission=Decimal("2.00"),
                slippage=Decimal("0.02"),
            ),
        ]

        metrics = engine._calculate_metrics(winning_trades)

        # With no losing trades, profit factor should be capped at 999.99
        assert metrics.profit_factor == Decimal("999.99")
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 0


class TestDirectionalSlippage:
    """Tests for directional slippage application in _fill_pending_orders.

    BUY orders should have slippage added to fill price (buyer pays more).
    SELL orders should have slippage subtracted from fill price (seller receives less).
    """

    def _make_bar(self, open_price: str = "150.00") -> OHLCVBar:
        """Create a bar with a specific open price."""
        return OHLCVBar(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 16, 9, 30, tzinfo=UTC),
            open=Decimal(open_price),
            high=Decimal("155.00"),
            low=Decimal("148.00"),
            close=Decimal("153.00"),
            volume=1000000,
            spread=Decimal("7.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )

    def _make_order(self, side: str, symbol: str = "AAPL") -> BacktestOrder:
        """Create a pending order with the given side."""
        return BacktestOrder(
            order_id=uuid4(),
            symbol=symbol,
            side=side,
            order_type="MARKET",
            quantity=100,
            status="PENDING",
            created_bar_timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
        )

    def test_buy_order_adds_slippage(self):
        """BUY order fill price = bar.open + slippage."""
        slippage_amount = Decimal("0.05")
        cost_model = MockCostModel(slippage=slippage_amount)
        config = EngineConfig(enable_cost_model=True)
        position_manager = PositionManager(config.initial_capital)
        detector = MockSignalDetector()

        engine = UnifiedBacktestEngine(detector, cost_model, position_manager, config)

        bar = self._make_bar("150.00")
        buy_order = self._make_order("BUY")
        engine._pending_orders.append(buy_order)
        engine._fill_pending_orders(bar)

        assert buy_order.fill_price == Decimal("150.00") + slippage_amount
        assert buy_order.slippage == slippage_amount

    def test_sell_order_subtracts_slippage(self):
        """SELL order fill price = bar.open - slippage."""
        slippage_amount = Decimal("0.05")
        cost_model = MockCostModel(slippage=slippage_amount)
        config = EngineConfig(enable_cost_model=True)
        position_manager = PositionManager(config.initial_capital)
        detector = MockSignalDetector()

        engine = UnifiedBacktestEngine(detector, cost_model, position_manager, config)

        # Must have an open position for SELL to close
        bar = self._make_bar("150.00")
        sell_order = self._make_order("SELL")
        engine._pending_orders.append(sell_order)
        engine._fill_pending_orders(bar)

        assert sell_order.fill_price == Decimal("150.00") - slippage_amount
        assert sell_order.slippage == slippage_amount

    def test_slippage_stored_as_absolute_value(self):
        """order.slippage is always stored as a positive (absolute) cost value."""
        # Cost model that returns negative slippage (signed convention for SELL)
        negative_slippage = Decimal("-0.03")
        cost_model = MockCostModel(slippage=negative_slippage)
        config = EngineConfig(enable_cost_model=True)
        position_manager = PositionManager(config.initial_capital)
        detector = MockSignalDetector()

        engine = UnifiedBacktestEngine(detector, cost_model, position_manager, config)

        bar = self._make_bar("150.00")
        buy_order = self._make_order("BUY")
        engine._pending_orders.append(buy_order)
        engine._fill_pending_orders(bar)

        # Even though cost model returned negative, stored slippage should be positive
        assert buy_order.slippage == Decimal("0.03")
        # BUY adds the absolute slippage
        assert buy_order.fill_price == Decimal("150.00") + Decimal("0.03")

    def test_sell_slippage_with_signed_cost_model(self):
        """SELL order correctly subtracts slippage even when cost model returns negative."""
        negative_slippage = Decimal("-0.03")
        cost_model = MockCostModel(slippage=negative_slippage)
        config = EngineConfig(enable_cost_model=True)
        position_manager = PositionManager(config.initial_capital)
        detector = MockSignalDetector()

        engine = UnifiedBacktestEngine(detector, cost_model, position_manager, config)

        bar = self._make_bar("150.00")
        sell_order = self._make_order("SELL")
        engine._pending_orders.append(sell_order)
        engine._fill_pending_orders(bar)

        # SELL subtracts the absolute slippage
        assert sell_order.fill_price == Decimal("150.00") - Decimal("0.03")
        assert sell_order.slippage == Decimal("0.03")

    def test_zero_slippage_no_impact(self):
        """Zero slippage has no impact on fill price for either side."""
        cost_model = MockCostModel(slippage=Decimal("0"))
        config = EngineConfig(enable_cost_model=True)
        position_manager = PositionManager(config.initial_capital)
        detector = MockSignalDetector()

        engine = UnifiedBacktestEngine(detector, cost_model, position_manager, config)

        bar = self._make_bar("150.00")

        buy_order = self._make_order("BUY")
        engine._pending_orders.append(buy_order)
        engine._fill_pending_orders(bar)
        assert buy_order.fill_price == Decimal("150.00")

        sell_order = self._make_order("SELL")
        engine._pending_orders.append(sell_order)
        engine._fill_pending_orders(bar)
        assert sell_order.fill_price == Decimal("150.00")


class TestShortPositionSupport:
    """Tests for SHORT/UTAD position opening, stop-loss, and take-profit."""

    def _make_bars(
        self, prices: list[tuple[str, str, str, str]], symbol: str = "AAPL"
    ) -> list[OHLCVBar]:
        """Create bars from (open, high, low, close) tuples."""
        bars = []
        for i, (op, hi, lo, cl) in enumerate(prices):
            bars.append(
                OHLCVBar(
                    id=uuid4(),
                    symbol=symbol,
                    timeframe="1d",
                    timestamp=datetime(2024, 1, 15 + i, 9, 30, tzinfo=UTC),
                    open=Decimal(op),
                    high=Decimal(hi),
                    low=Decimal(lo),
                    close=Decimal(cl),
                    volume=1000000,
                    spread=Decimal("3.00"),
                    spread_ratio=Decimal("1.0"),
                    volume_ratio=Decimal("1.0"),
                )
            )
        return bars

    def test_short_signal_opens_short_position(self):
        """SHORT signal creates SELL order that opens a SHORT position."""
        # Bar 0: signal bar, Bar 1: fill bar, Bar 2+: holding
        bars = self._make_bars(
            [
                ("100.00", "102.00", "99.00", "101.00"),  # bar 0: signal
                ("101.00", "103.00", "100.00", "102.00"),  # bar 1: fill at open 101
                ("102.00", "103.00", "100.00", "101.50"),  # bar 2: hold
            ]
        )

        short_signal = MockTradeSignal(direction="SHORT")
        detector = MockSignalDetector(signals={0: short_signal})
        config = EngineConfig(enable_cost_model=False, risk_per_trade=Decimal("0.02"))
        position_manager = PositionManager(config.initial_capital)

        engine = UnifiedBacktestEngine(detector, MockCostModel(), position_manager, config)
        result = engine.run(bars)

        # After bar 1, position should be SHORT
        assert position_manager.has_position("AAPL")
        pos = position_manager.get_position("AAPL")
        assert pos is not None
        assert pos.side == "SHORT"
        assert pos.average_entry_price == Decimal("101.00")  # filled at bar 1 open

    def test_short_stop_loss_exit(self):
        """SHORT position exits on stop-loss when price rises above stop."""
        # Bar 0: signal, Bar 1: fill, Bar 2: stop hit (high goes above stop)
        # With 2% risk_per_trade and fill at 100.00, stop = 100 * 1.02 = 102.00
        bars = self._make_bars(
            [
                ("100.00", "102.00", "99.00", "100.00"),  # bar 0: signal
                ("100.00", "101.00", "99.00", "100.50"),  # bar 1: fill at 100
                ("101.00", "103.00", "100.00", "102.50"),  # bar 2: high 103 > stop 102
            ]
        )

        short_signal = MockTradeSignal(direction="SHORT")
        detector = MockSignalDetector(signals={0: short_signal})
        config = EngineConfig(enable_cost_model=False, risk_per_trade=Decimal("0.02"))
        position_manager = PositionManager(config.initial_capital)

        engine = UnifiedBacktestEngine(detector, MockCostModel(), position_manager, config)
        result = engine.run(bars)

        # Position should be closed by stop-loss
        assert not position_manager.has_position("AAPL")
        assert len(position_manager.closed_trades) == 1

        trade = position_manager.closed_trades[0]
        assert trade.side == "SHORT"
        assert trade.entry_price == Decimal("100.00")
        assert trade.exit_price == Decimal("102.00")  # stop price
        assert trade.realized_pnl < Decimal("0")  # loss

    def test_short_take_profit_exit(self):
        """SHORT position exits on take-profit when price drops below target."""
        # With 2% risk_per_trade and fill at 100.00:
        # stop = 100 * 1.02 = 102, target = 100 - 2*3 = 94 (3:1 R:R)
        bars = self._make_bars(
            [
                ("100.00", "102.00", "99.00", "100.00"),  # bar 0: signal
                ("100.00", "101.00", "99.00", "100.00"),  # bar 1: fill at 100
                ("99.00", "100.00", "93.00", "93.50"),  # bar 2: low 93 < target 94
            ]
        )

        short_signal = MockTradeSignal(direction="SHORT")
        detector = MockSignalDetector(signals={0: short_signal})
        config = EngineConfig(enable_cost_model=False, risk_per_trade=Decimal("0.02"))
        position_manager = PositionManager(config.initial_capital)

        engine = UnifiedBacktestEngine(detector, MockCostModel(), position_manager, config)
        result = engine.run(bars)

        # Position should be closed by take-profit
        assert not position_manager.has_position("AAPL")
        assert len(position_manager.closed_trades) == 1

        trade = position_manager.closed_trades[0]
        assert trade.side == "SHORT"
        assert trade.entry_price == Decimal("100.00")
        assert trade.exit_price == Decimal("94.00")  # target price
        assert trade.realized_pnl > Decimal("0")  # profit

    def test_short_closed_by_buy_signal(self):
        """SHORT position is closed when a LONG (BUY) signal fills."""
        # Bar 0: SHORT signal, Bar 1: fill SHORT, Bar 2: LONG signal, Bar 3: fill BUY (closes SHORT)
        bars = self._make_bars(
            [
                ("100.00", "102.00", "99.00", "100.00"),  # bar 0: SHORT signal
                ("100.00", "101.00", "99.00", "100.00"),  # bar 1: fill SHORT at 100
                ("99.00", "100.50", "98.00", "99.00"),  # bar 2: LONG signal
                ("99.00", "100.00", "98.00", "99.50"),  # bar 3: fill BUY (closes SHORT at 99)
            ]
        )

        signals = {
            0: MockTradeSignal(direction="SHORT"),
            2: MockTradeSignal(direction="LONG"),
        }
        detector = MockSignalDetector(signals=signals)
        config = EngineConfig(enable_cost_model=False, risk_per_trade=Decimal("0.02"))
        position_manager = PositionManager(config.initial_capital)

        engine = UnifiedBacktestEngine(detector, MockCostModel(), position_manager, config)
        result = engine.run(bars)

        # SHORT should be closed (BUY order closed it)
        assert not position_manager.has_position("AAPL")

        # There should be 1 closed SHORT trade with profit
        assert len(position_manager.closed_trades) == 1
        trade = position_manager.closed_trades[0]
        assert trade.side == "SHORT"
        assert trade.entry_price == Decimal("100.00")
        assert trade.exit_price == Decimal("99.00")  # filled at bar 3 open
        assert trade.realized_pnl > Decimal("0")  # profitable (shorted 100, covered 99)

    def test_short_position_with_risk_manager(self):
        """SHORT signal processed through risk manager sizing and exit."""
        from src.backtesting.risk_integration import BacktestRiskManager

        # Bar 0: signal bar (close=100), Bar 1: fill bar (open=100),
        # Bar 2: stop hit (high=103 > stop=105? No, keep it simple: stop at 102, high=103)
        bars = self._make_bars(
            [
                ("100.00", "102.00", "99.00", "100.00"),  # bar 0: signal
                ("100.00", "101.00", "99.00", "100.50"),  # bar 1: fill at open 100
                ("101.00", "103.00", "100.00", "102.50"),  # bar 2: high 103 > stop 102
            ]
        )

        # Create signal with stop_loss so risk manager path is used
        short_signal = MockTradeSignal(direction="SHORT")
        short_signal.stop_loss = Decimal("102.00")  # stop above entry
        short_signal.target_levels = None
        short_signal.campaign_id = "TEST-SHORT-RM"

        detector = MockSignalDetector(signals={0: short_signal})
        risk_mgr = BacktestRiskManager(initial_capital=Decimal("100000"))
        config = EngineConfig(enable_cost_model=False)
        position_manager = PositionManager(config.initial_capital)

        engine = UnifiedBacktestEngine(
            detector, MockCostModel(), position_manager, config, risk_manager=risk_mgr
        )
        result = engine.run(bars)

        # Risk manager should have validated and sized the position
        assert risk_mgr.violations.total_entry_attempts == 1
        assert risk_mgr.violations.entries_allowed == 1

        # Position should be closed by stop-loss on bar 2
        assert not position_manager.has_position("AAPL")
        assert len(position_manager.closed_trades) == 1

        trade = position_manager.closed_trades[0]
        assert trade.side == "SHORT"
        assert trade.entry_price == Decimal("100.00")
        assert trade.exit_price == Decimal("102.00")  # stop price
        assert trade.realized_pnl < Decimal("0")  # loss on SHORT when price rises

    def test_short_r_multiple_calculation(self):
        """R-multiple is calculated correctly for SHORT trades."""
        config = EngineConfig(risk_per_trade=Decimal("0.02"))
        detector = MockSignalDetector()
        cost_model = MockCostModel()
        position_manager = PositionManager(config.initial_capital)

        engine = UnifiedBacktestEngine(detector, cost_model, position_manager, config)

        from src.models.backtest import BacktestTrade

        short_trade = BacktestTrade(
            trade_id=uuid4(),
            position_id=uuid4(),
            symbol="AAPL",
            side="SHORT",
            quantity=100,
            entry_price=Decimal("100.00"),
            exit_price=Decimal("94.00"),
            entry_timestamp=datetime(2024, 1, 15, tzinfo=UTC),
            exit_timestamp=datetime(2024, 1, 20, tzinfo=UTC),
            realized_pnl=Decimal("600.00"),
            commission=Decimal("2.00"),
            slippage=Decimal("0.02"),
        )

        avg_r = engine._calculate_avg_r_multiple([short_trade])

        # R = (entry - exit) / (entry * risk_pct) = (100 - 94) / (100 * 0.02) = 6/2 = 3.0
        assert avg_r == Decimal("3")
