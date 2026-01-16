"""
Unit Tests for Exit Strategies Package - Story 18.11.1

Purpose:
--------
Comprehensive test coverage for exit strategy framework including
base classes, concrete implementations, and registry.

Target Coverage: 95%+

Author: Story 18.11.1
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.exit import (
    ExitContext,
    ExitSignal,
    ExitStrategy,
    ExitStrategyRegistry,
    TargetExitStrategy,
    TimeBasedExitStrategy,
    TrailingStopStrategy,
)
from src.models.ohlcv import OHLCVBar
from src.models.position import Position

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_position():
    """Create sample position for testing."""
    return Position(
        campaign_id=uuid4(),
        signal_id=uuid4(),
        symbol="AAPL",
        timeframe="1h",
        entry_date=datetime.now(UTC),
        entry_price=Decimal("150.00"),
        shares=Decimal("100"),
        stop_loss=Decimal("148.00"),
        current_price=Decimal("152.00"),
        pattern_type="SPRING",
    )


@pytest.fixture
def sample_bar():
    """Create sample OHLCV bar for testing."""
    return OHLCVBar(
        symbol="AAPL",
        timeframe="1h",
        timestamp=datetime.now(UTC),
        open=Decimal("151.00"),
        high=Decimal("153.00"),
        low=Decimal("150.50"),
        close=Decimal("152.00"),
        volume=1000000,
        spread=Decimal("2.50"),
    )


@pytest.fixture
def sample_context():
    """Create sample exit context for testing."""
    return ExitContext(
        trailing_stop=Decimal("148.50"),
        target_price=Decimal("160.00"),
        entry_time=datetime.now(UTC),
        max_hold_bars=50,
        bars_held=10,
        campaign_phase="D",
    )


@pytest.fixture
def registry_cleanup():
    """
    Automatically cleanup custom strategies registered during tests.

    Yields the strategy names to cleanup, then removes them from registry
    after test completes. Use this fixture when testing custom strategy
    registration to avoid registry pollution across tests.

    Usage:
    ------
    def test_custom_strategy(registry_cleanup):
        registry_cleanup.append("custom_exit")
        ExitStrategyRegistry.register_strategy("custom_exit", CustomStrategy)
        # Test runs...
        # Cleanup happens automatically after test
    """
    cleanup_list = []
    yield cleanup_list
    # Cleanup registered strategies after test
    for strategy_name in cleanup_list:
        if strategy_name in ExitStrategyRegistry._strategies:
            del ExitStrategyRegistry._strategies[strategy_name]


# ============================================================================
# TrailingStopStrategy Tests
# ============================================================================


class TestTrailingStopStrategy:
    """Test trailing stop exit strategy."""

    def test_name_property(self):
        """Test strategy name is correct."""
        strategy = TrailingStopStrategy()
        assert strategy.name == "trailing_stop"

    def test_stop_triggered_when_low_below_stop(self, sample_position, sample_bar, sample_context):
        """Test exit signal when bar.low falls below trailing stop."""
        strategy = TrailingStopStrategy()

        # Set bar low below trailing stop
        sample_bar.low = Decimal("148.00")  # Below stop at 148.50

        signal = strategy.should_exit(sample_position, sample_bar, sample_context)

        assert signal is not None
        assert signal.reason == "trailing_stop"
        assert signal.price == sample_context.trailing_stop
        assert signal.timestamp == sample_bar.timestamp

    def test_no_exit_when_above_stop(self, sample_position, sample_bar, sample_context):
        """Test no exit when bar.low stays above trailing stop."""
        strategy = TrailingStopStrategy()

        # Set bar low above trailing stop
        sample_bar.low = Decimal("149.00")  # Above stop at 148.50

        signal = strategy.should_exit(sample_position, sample_bar, sample_context)

        assert signal is None

    def test_exit_at_exact_stop_level(self, sample_position, sample_bar, sample_context):
        """Test exit triggered when bar.low equals trailing stop."""
        strategy = TrailingStopStrategy()

        # Set bar low exactly at trailing stop
        sample_bar.low = sample_context.trailing_stop

        signal = strategy.should_exit(sample_position, sample_bar, sample_context)

        assert signal is not None
        assert signal.price == sample_context.trailing_stop


# ============================================================================
# TargetExitStrategy Tests
# ============================================================================


class TestTargetExitStrategy:
    """Test target exit strategy."""

    def test_name_property(self):
        """Test strategy name is correct."""
        strategy = TargetExitStrategy()
        assert strategy.name == "target_exit"

    def test_target_hit_when_high_reaches_target(self, sample_position, sample_bar, sample_context):
        """Test exit signal when bar.high reaches profit target."""
        strategy = TargetExitStrategy()

        # Set bar high to reach target
        sample_bar.high = Decimal("160.50")  # Reaches target at 160.00

        signal = strategy.should_exit(sample_position, sample_bar, sample_context)

        assert signal is not None
        assert signal.reason == "target_hit"
        assert signal.price == sample_context.target_price
        assert signal.timestamp == sample_bar.timestamp

    def test_no_exit_when_below_target(self, sample_position, sample_bar, sample_context):
        """Test no exit when bar.high stays below target."""
        strategy = TargetExitStrategy()

        # Set bar high below target
        sample_bar.high = Decimal("159.00")  # Below target at 160.00

        signal = strategy.should_exit(sample_position, sample_bar, sample_context)

        assert signal is None

    def test_no_exit_when_target_not_set(self, sample_position, sample_bar, sample_context):
        """Test no exit when target_price is None."""
        strategy = TargetExitStrategy()

        # Remove target price
        sample_context.target_price = None

        signal = strategy.should_exit(sample_position, sample_bar, sample_context)

        assert signal is None

    def test_exit_at_exact_target_level(self, sample_position, sample_bar, sample_context):
        """Test exit triggered when bar.high equals target."""
        strategy = TargetExitStrategy()

        # Set bar high exactly at target
        sample_bar.high = sample_context.target_price

        signal = strategy.should_exit(sample_position, sample_bar, sample_context)

        assert signal is not None
        assert signal.price == sample_context.target_price


# ============================================================================
# TimeBasedExitStrategy Tests
# ============================================================================


class TestTimeBasedExitStrategy:
    """Test time-based exit strategy."""

    def test_name_property(self):
        """Test strategy name is correct."""
        strategy = TimeBasedExitStrategy()
        assert strategy.name == "time_exit"

    def test_time_exit_when_max_bars_reached(self, sample_position, sample_bar, sample_context):
        """Test exit signal when bars_held reaches max_hold_bars."""
        strategy = TimeBasedExitStrategy()

        # Set bars held to max
        sample_context.bars_held = 50
        sample_context.max_hold_bars = 50

        signal = strategy.should_exit(sample_position, sample_bar, sample_context)

        assert signal is not None
        assert signal.reason == "time_exit"
        assert signal.price == sample_bar.close
        assert signal.timestamp == sample_bar.timestamp

    def test_no_exit_when_below_max_bars(self, sample_position, sample_bar, sample_context):
        """Test no exit when bars_held is below max_hold_bars."""
        strategy = TimeBasedExitStrategy()

        # Set bars held below max
        sample_context.bars_held = 30
        sample_context.max_hold_bars = 50

        signal = strategy.should_exit(sample_position, sample_bar, sample_context)

        assert signal is None

    def test_time_exit_when_exceeding_max_bars(self, sample_position, sample_bar, sample_context):
        """Test exit triggered when bars_held exceeds max_hold_bars."""
        strategy = TimeBasedExitStrategy()

        # Set bars held above max
        sample_context.bars_held = 60
        sample_context.max_hold_bars = 50

        signal = strategy.should_exit(sample_position, sample_bar, sample_context)

        assert signal is not None
        assert signal.reason == "time_exit"


# ============================================================================
# ExitStrategyRegistry Tests
# ============================================================================


class TestExitStrategyRegistry:
    """Test exit strategy registry."""

    def test_get_trailing_stop_strategy(self):
        """Test getting trailing stop strategy from registry."""
        strategy = ExitStrategyRegistry.get_strategy("trailing_stop")

        assert isinstance(strategy, TrailingStopStrategy)
        assert strategy.name == "trailing_stop"

    def test_get_target_exit_strategy(self):
        """Test getting target exit strategy from registry."""
        strategy = ExitStrategyRegistry.get_strategy("target_exit")

        assert isinstance(strategy, TargetExitStrategy)
        assert strategy.name == "target_exit"

    def test_get_time_exit_strategy(self):
        """Test getting time exit strategy from registry."""
        strategy = ExitStrategyRegistry.get_strategy("time_exit")

        assert isinstance(strategy, TimeBasedExitStrategy)
        assert strategy.name == "time_exit"

    def test_get_unknown_strategy_raises_error(self):
        """Test getting unknown strategy raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ExitStrategyRegistry.get_strategy("unknown_strategy")

        assert "Unknown exit strategy: unknown_strategy" in str(exc_info.value)
        assert "trailing_stop" in str(exc_info.value)

    def test_list_strategies(self):
        """Test listing all registered strategies."""
        strategies = ExitStrategyRegistry.list_strategies()

        assert "trailing_stop" in strategies
        assert "target_exit" in strategies
        assert "time_exit" in strategies
        assert len(strategies) == 3

    def test_register_custom_strategy(self, registry_cleanup):
        """Test registering a custom strategy."""

        class CustomExitStrategy(ExitStrategy):
            @property
            def name(self) -> str:
                return "custom_exit"

            def should_exit(self, position, bar, context):
                return None

        # Register for automatic cleanup
        registry_cleanup.append("custom_exit")

        # Register custom strategy
        ExitStrategyRegistry.register_strategy("custom_exit", CustomExitStrategy)

        # Verify it's registered
        assert "custom_exit" in ExitStrategyRegistry.list_strategies()

        # Get and verify instance
        strategy = ExitStrategyRegistry.get_strategy("custom_exit")
        assert isinstance(strategy, CustomExitStrategy)
        assert strategy.name == "custom_exit"

    def test_register_duplicate_strategy_raises_error(self):
        """Test registering duplicate strategy name raises ValueError."""

        class DuplicateStrategy(ExitStrategy):
            @property
            def name(self) -> str:
                return "duplicate"

            def should_exit(self, position, bar, context):
                return None

        with pytest.raises(ValueError) as exc_info:
            ExitStrategyRegistry.register_strategy("trailing_stop", DuplicateStrategy)

        assert "already registered" in str(exc_info.value)

    def test_register_non_strategy_class_raises_error(self):
        """Test registering non-ExitStrategy class raises ValueError."""

        class NotAStrategy:
            pass

        with pytest.raises(ValueError) as exc_info:
            ExitStrategyRegistry.register_strategy("invalid", NotAStrategy)

        assert "must inherit from ExitStrategy" in str(exc_info.value)


# ============================================================================
# ExitContext Tests
# ============================================================================


class TestExitContext:
    """Test exit context dataclass."""

    def test_create_minimal_context(self):
        """Test creating context with minimal required fields."""
        context = ExitContext(trailing_stop=Decimal("100.00"))

        assert context.trailing_stop == Decimal("100.00")
        assert context.target_price is None
        assert context.max_hold_bars == 100
        assert context.bars_held == 0

    def test_create_full_context(self):
        """Test creating context with all fields."""
        entry_time = datetime.now(UTC)
        context = ExitContext(
            trailing_stop=Decimal("100.00"),
            target_price=Decimal("120.00"),
            entry_time=entry_time,
            max_hold_bars=50,
            bars_held=25,
            campaign_phase="D",
        )

        assert context.trailing_stop == Decimal("100.00")
        assert context.target_price == Decimal("120.00")
        assert context.entry_time == entry_time
        assert context.max_hold_bars == 50
        assert context.bars_held == 25
        assert context.campaign_phase == "D"


# ============================================================================
# ExitSignal Tests
# ============================================================================


class TestExitSignal:
    """Test exit signal dataclass."""

    def test_create_minimal_signal(self):
        """Test creating signal with minimal required fields."""
        signal = ExitSignal(reason="test_exit", price=Decimal("100.00"))

        assert signal.reason == "test_exit"
        assert signal.price == Decimal("100.00")
        assert signal.timestamp is None

    def test_create_full_signal(self):
        """Test creating signal with all fields."""
        timestamp = datetime.now(UTC)
        signal = ExitSignal(reason="trailing_stop", price=Decimal("148.50"), timestamp=timestamp)

        assert signal.reason == "trailing_stop"
        assert signal.price == Decimal("148.50")
        assert signal.timestamp == timestamp


# ============================================================================
# Integration Tests
# ============================================================================


class TestExitStrategyIntegration:
    """Integration tests for exit strategies working together."""

    def test_multiple_strategies_evaluation_order(
        self, sample_position, sample_bar, sample_context
    ):
        """Test evaluating multiple strategies to find first exit."""
        # Create all strategies
        trailing_stop = TrailingStopStrategy()
        target_exit = TargetExitStrategy()
        time_exit = TimeBasedExitStrategy()

        # Set bar to trigger target (but not stop or time)
        sample_bar.high = Decimal("160.50")  # Hits target
        sample_bar.low = Decimal("149.00")  # Above stop
        sample_context.bars_held = 30  # Below max

        # Evaluate in order: stop -> target -> time
        signal = (
            trailing_stop.should_exit(sample_position, sample_bar, sample_context)
            or target_exit.should_exit(sample_position, sample_bar, sample_context)
            or time_exit.should_exit(sample_position, sample_bar, sample_context)
        )

        assert signal is not None
        assert signal.reason == "target_hit"

    def test_stop_takes_precedence_over_target(self, sample_position, sample_bar, sample_context):
        """Test trailing stop triggers before target when both conditions met."""
        trailing_stop = TrailingStopStrategy()
        target_exit = TargetExitStrategy()

        # Set bar to trigger both stop and target
        sample_bar.high = Decimal("160.50")  # Hits target
        sample_bar.low = Decimal("148.00")  # Hits stop

        # Evaluate stop first (typical priority order)
        signal = trailing_stop.should_exit(
            sample_position, sample_bar, sample_context
        ) or target_exit.should_exit(sample_position, sample_bar, sample_context)

        assert signal is not None
        assert signal.reason == "trailing_stop"
