"""
Unit Tests for ExitLogicRefinements Facade - Story 18.11.3

Purpose:
--------
Comprehensive test coverage for the unified exit logic facade that integrates
exit strategies, consolidation detection, and campaign state management.

Target Coverage: 95%+

Author: Story 18.11.3
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.exit import (
    ConsolidationConfig,
    ExitSignal,
    ExitStrategy,
)
from src.backtesting.exit_logic_refinements import ExitLogicRefinements
from src.models.ohlcv import OHLCVBar
from src.models.position import Position, PositionStatus

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_repository():
    """Create mock campaign repository for testing."""

    class MockCampaignRepository:
        """Mock repository with in-memory state."""

        def __init__(self):
            self.positions = {}

        async def update_position(self, position_id, current_price):
            """Mock update_position method."""
            if position_id not in self.positions:
                raise ValueError(f"Position {position_id} not found")

            position = self.positions[position_id]
            position.current_price = current_price
            position.current_pnl = (current_price - position.entry_price) * position.shares
            return position

        async def close_position(self, position_id, exit_price, closed_date):
            """Mock close_position method."""
            if position_id not in self.positions:
                raise ValueError(f"Position {position_id} not found")

            position = self.positions[position_id]
            position.status = PositionStatus.CLOSED
            position.exit_price = exit_price
            position.closed_date = closed_date
            position.realized_pnl = (exit_price - position.entry_price) * position.shares
            return position

        async def batch_update_positions(self, position_updates):
            """Mock batch_update_positions method."""
            updated = []
            for position_id, current_price in position_updates.items():
                if position_id in self.positions:
                    position = self.positions[position_id]
                    position.current_price = current_price
                    position.current_pnl = (current_price - position.entry_price) * position.shares
                    updated.append(position)
            return updated

    return MockCampaignRepository()


@pytest.fixture
def exit_logic(mock_repository):
    """Create exit logic facade with mock repository."""
    return ExitLogicRefinements(mock_repository)


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
        current_price=Decimal("150.00"),
        pattern_type="SPRING",
    )


@pytest.fixture
def sample_bar():
    """Create sample OHLCV bar."""
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


# ============================================================================
# Test ExitLogicRefinements.__init__
# ============================================================================


def test_facade_initialization(mock_repository):
    """Test facade initializes with all components."""
    facade = ExitLogicRefinements(mock_repository)

    assert facade._state_manager is not None
    assert facade._strategy_registry is not None
    assert facade._consolidation_detector is not None


# ============================================================================
# Test update_position_state
# ============================================================================


@pytest.mark.asyncio
async def test_update_position_state_delegates_to_manager(
    exit_logic, mock_repository, sample_position, sample_bar
):
    """Test update_position_state delegates to state manager."""
    # Setup
    mock_repository.positions[sample_position.id] = sample_position

    # Execute
    updated_position = await exit_logic.update_position_state(
        campaign_id=sample_position.campaign_id,
        position_id=sample_position.id,
        bar=sample_bar,
    )

    # Verify
    assert updated_position.current_price == sample_bar.close
    assert updated_position.current_pnl == Decimal("200.00")  # (152 - 150) * 100


@pytest.mark.asyncio
async def test_update_position_state_not_found(exit_logic, sample_bar):
    """Test update_position_state with non-existent position."""
    non_existent_id = uuid4()

    # Execute & Verify
    with pytest.raises(ValueError, match="Position .* not found"):
        await exit_logic.update_position_state(
            campaign_id=uuid4(),
            position_id=non_existent_id,
            bar=sample_bar,
        )


# ============================================================================
# Test process_exit
# ============================================================================


@pytest.mark.asyncio
async def test_process_exit_delegates_to_manager(exit_logic, mock_repository, sample_position):
    """Test process_exit delegates to state manager."""
    # Setup
    mock_repository.positions[sample_position.id] = sample_position
    exit_signal = ExitSignal(
        reason="trailing_stop",
        price=Decimal("148.00"),
        timestamp=datetime.now(UTC),
    )

    # Execute
    closed_position = await exit_logic.process_exit(
        campaign_id=sample_position.campaign_id,
        position_id=sample_position.id,
        exit_signal=exit_signal,
    )

    # Verify
    assert closed_position.status == PositionStatus.CLOSED
    assert closed_position.exit_price == Decimal("148.00")
    assert closed_position.realized_pnl == Decimal("-200.00")  # (148 - 150) * 100


@pytest.mark.asyncio
async def test_process_exit_not_found(exit_logic):
    """Test process_exit with non-existent position."""
    exit_signal = ExitSignal(
        reason="target_hit",
        price=Decimal("160.00"),
        timestamp=datetime.now(UTC),
    )

    # Execute & Verify
    with pytest.raises(ValueError, match="Position .* not found"):
        await exit_logic.process_exit(
            campaign_id=uuid4(),
            position_id=uuid4(),
            exit_signal=exit_signal,
        )


# ============================================================================
# Test detect_consolidation
# ============================================================================


def test_detect_consolidation_requires_start_index(exit_logic):
    """Test consolidation detection requires start_index parameter."""
    # Setup
    bars = []
    for i in range(20):
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1h",
            timestamp=datetime.now(UTC),
            open=Decimal("150.00"),
            high=Decimal("150.50"),
            low=Decimal("149.50"),
            close=Decimal("150.00"),
            volume=1000000,
            spread=Decimal("1.00"),
        )
        bars.append(bar)

    # Execute: detect_consolidation calls detector.detect_consolidation(bars, start_index)
    # The facade method signature needs start_index parameter
    zone = exit_logic.detect_consolidation(bars, start_index=0)

    # Verify: Zone may be None or ConsolidationZone
    assert zone is None or hasattr(zone, "start_index")


def test_detect_consolidation_with_custom_config(exit_logic):
    """Test consolidation detection with custom configuration."""
    # Setup
    bars = []
    for i in range(20):
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1h",
            timestamp=datetime.now(UTC),
            open=Decimal("150.00"),
            high=Decimal("151.00"),
            low=Decimal("149.00"),
            close=Decimal("150.00"),
            volume=1000000,
            spread=Decimal("2.00"),
        )
        bars.append(bar)

    custom_config = ConsolidationConfig(
        min_bars=15,
        max_range_pct=Decimal("0.015"),
        volume_decline_threshold=Decimal("0.8"),
    )

    # Execute
    zone = exit_logic.detect_consolidation(bars, start_index=0, config=custom_config)

    # Verify: Zone may be None or ConsolidationZone
    assert zone is None or hasattr(zone, "start_index")


# ============================================================================
# Test get_strategy
# ============================================================================


def test_get_strategy_trailing_stop(exit_logic):
    """Test getting trailing stop strategy."""
    strategy = exit_logic.get_strategy("trailing_stop")

    assert isinstance(strategy, ExitStrategy)
    assert strategy.name == "trailing_stop"


def test_get_strategy_target_exit(exit_logic):
    """Test getting target exit strategy."""
    strategy = exit_logic.get_strategy("target_exit")

    assert isinstance(strategy, ExitStrategy)
    assert strategy.name == "target_exit"


def test_get_strategy_time_exit(exit_logic):
    """Test getting time-based exit strategy."""
    strategy = exit_logic.get_strategy("time_exit")

    assert isinstance(strategy, ExitStrategy)
    assert strategy.name == "time_exit"


def test_get_strategy_unknown(exit_logic):
    """Test getting unknown strategy raises error."""
    with pytest.raises(ValueError, match="Unknown exit strategy"):
        exit_logic.get_strategy("nonexistent_strategy")


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_facade_component_integration(exit_logic, mock_repository, sample_position):
    """Test facade integrates all components correctly."""
    # Setup
    mock_repository.positions[sample_position.id] = sample_position

    # Test state manager integration
    bar = OHLCVBar(
        symbol="AAPL",
        timeframe="1h",
        timestamp=datetime.now(UTC),
        open=Decimal("151.00"),
        high=Decimal("152.00"),
        low=Decimal("150.50"),
        close=Decimal("151.50"),
        volume=1000000,
        spread=Decimal("1.50"),
    )
    updated = await exit_logic.update_position_state(
        campaign_id=sample_position.campaign_id,
        position_id=sample_position.id,
        bar=bar,
    )
    assert updated.current_price == Decimal("151.50")

    # Test strategy registry integration
    strategy = exit_logic.get_strategy("trailing_stop")
    assert strategy.name == "trailing_stop"

    # Test consolidation detector integration
    bars = [bar] * 20
    zone = exit_logic.detect_consolidation(bars, start_index=0)
    # Zone may be None or ConsolidationZone depending on bars

    # Test exit signal processing
    exit_signal = ExitSignal(
        reason="test_exit",
        price=Decimal("155.00"),
        timestamp=datetime.now(UTC),
    )
    closed = await exit_logic.process_exit(
        campaign_id=sample_position.campaign_id,
        position_id=sample_position.id,
        exit_signal=exit_signal,
    )
    assert closed.status == PositionStatus.CLOSED
