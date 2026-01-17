"""
Unit Tests for Campaign State Manager - Story 18.11.3

Purpose:
--------
Comprehensive test coverage for centralized campaign state management
including position updates, exit handling, and batch operations.

Target Coverage: 95%+

Author: Story 18.11.3
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from src.backtesting.exit import ExitSignal
from src.backtesting.exit.campaign_state_manager import CampaignStateManager
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
            self.update_position_calls = []
            self.close_position_calls = []
            self.batch_update_calls = []

        async def update_position(
            self,
            position_id: UUID,
            current_price: Decimal,
        ) -> Position:
            """Mock update_position method."""
            self.update_position_calls.append(
                {"position_id": position_id, "current_price": current_price}
            )

            # Simulate position update
            if position_id not in self.positions:
                raise ValueError(f"Position {position_id} not found")

            position = self.positions[position_id]
            position.current_price = current_price
            # Simulate P&L calculation
            position.current_pnl = (current_price - position.entry_price) * position.shares
            return position

        async def close_position(
            self,
            position_id: UUID,
            exit_price: Decimal,
            closed_date: datetime,
        ) -> Position:
            """Mock close_position method."""
            self.close_position_calls.append(
                {
                    "position_id": position_id,
                    "exit_price": exit_price,
                    "closed_date": closed_date,
                }
            )

            # Simulate position closure
            if position_id not in self.positions:
                raise ValueError(f"Position {position_id} not found")

            position = self.positions[position_id]
            position.status = PositionStatus.CLOSED
            position.exit_price = exit_price
            position.closed_date = closed_date
            position.realized_pnl = (exit_price - position.entry_price) * position.shares
            position.current_price = None
            position.current_pnl = Decimal("0")
            return position

        async def batch_update_positions(
            self, position_updates: dict[UUID, Decimal]
        ) -> list[Position]:
            """Mock batch_update_positions method."""
            self.batch_update_calls.append({"updates": position_updates})

            updated_positions = []
            for position_id, current_price in position_updates.items():
                if position_id in self.positions:
                    position = self.positions[position_id]
                    position.current_price = current_price
                    position.current_pnl = (current_price - position.entry_price) * position.shares
                    updated_positions.append(position)

            return updated_positions

    return MockCampaignRepository()


@pytest.fixture
def state_manager(mock_repository):
    """Create campaign state manager with mock repository."""
    return CampaignStateManager(mock_repository)


@pytest.fixture
def sample_campaign_id():
    """Sample campaign ID."""
    return uuid4()


@pytest.fixture
def sample_position(sample_campaign_id):
    """Create sample position for testing."""
    position = Position(
        campaign_id=sample_campaign_id,
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
    return position


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
def sample_exit_signal():
    """Create sample exit signal."""
    return ExitSignal(
        reason="trailing_stop",
        price=Decimal("148.00"),
        timestamp=datetime.now(UTC),
    )


# ============================================================================
# Test CampaignStateManager.__init__
# ============================================================================


def test_state_manager_initialization(mock_repository):
    """Test state manager initializes with repository."""
    state_manager = CampaignStateManager(mock_repository)

    assert state_manager._repository is mock_repository


# ============================================================================
# Test update_position_state
# ============================================================================


@pytest.mark.asyncio
async def test_update_position_state_success(
    state_manager, mock_repository, sample_campaign_id, sample_position, sample_bar
):
    """Test successful position state update."""
    # Setup: Add position to mock repository
    mock_repository.positions[sample_position.id] = sample_position

    # Execute
    updated_position = await state_manager.update_position_state(
        campaign_id=sample_campaign_id,
        position_id=sample_position.id,
        bar=sample_bar,
    )

    # Verify
    assert updated_position.current_price == sample_bar.close
    assert updated_position.current_pnl == (sample_bar.close - Decimal("150.00")) * Decimal("100")
    assert len(mock_repository.update_position_calls) == 1
    assert mock_repository.update_position_calls[0]["current_price"] == sample_bar.close


@pytest.mark.asyncio
async def test_update_position_state_not_found(state_manager, sample_campaign_id, sample_bar):
    """Test position state update with non-existent position."""
    non_existent_id = uuid4()

    # Execute & Verify
    with pytest.raises(ValueError, match="Position .* not found"):
        await state_manager.update_position_state(
            campaign_id=sample_campaign_id,
            position_id=non_existent_id,
            bar=sample_bar,
        )


@pytest.mark.asyncio
async def test_update_position_state_price_movement(
    state_manager, mock_repository, sample_campaign_id, sample_position, sample_bar
):
    """Test position state update reflects accurate price movement."""
    # Setup: Position with entry at 150.00
    mock_repository.positions[sample_position.id] = sample_position

    # Execute: Update with bar close at 152.00
    updated_position = await state_manager.update_position_state(
        campaign_id=sample_campaign_id,
        position_id=sample_position.id,
        bar=sample_bar,
    )

    # Verify: P&L should be (152.00 - 150.00) * 100 = 200.00
    expected_pnl = Decimal("200.00")
    assert updated_position.current_pnl == expected_pnl
    assert updated_position.current_price == Decimal("152.00")


# ============================================================================
# Test handle_exit
# ============================================================================


@pytest.mark.asyncio
async def test_handle_exit_success(
    state_manager, mock_repository, sample_campaign_id, sample_position, sample_exit_signal
):
    """Test successful exit handling."""
    # Setup
    mock_repository.positions[sample_position.id] = sample_position

    # Execute
    closed_position = await state_manager.handle_exit(
        campaign_id=sample_campaign_id,
        position_id=sample_position.id,
        exit_signal=sample_exit_signal,
    )

    # Verify
    assert closed_position.status == PositionStatus.CLOSED
    assert closed_position.exit_price == sample_exit_signal.price
    assert closed_position.closed_date == sample_exit_signal.timestamp
    assert len(mock_repository.close_position_calls) == 1


@pytest.mark.asyncio
async def test_handle_exit_without_timestamp(
    state_manager, mock_repository, sample_campaign_id, sample_position
):
    """Test exit handling with signal that has no timestamp."""
    # Setup
    mock_repository.positions[sample_position.id] = sample_position
    exit_signal = ExitSignal(reason="target_hit", price=Decimal("160.00"))

    # Execute
    closed_position = await state_manager.handle_exit(
        campaign_id=sample_campaign_id,
        position_id=sample_position.id,
        exit_signal=exit_signal,
    )

    # Verify: Should use current time
    assert closed_position.status == PositionStatus.CLOSED
    assert closed_position.exit_price == Decimal("160.00")
    assert closed_position.closed_date is not None
    assert isinstance(closed_position.closed_date, datetime)


@pytest.mark.asyncio
async def test_handle_exit_calculates_realized_pnl(
    state_manager, mock_repository, sample_campaign_id, sample_position
):
    """Test exit handling calculates realized P&L correctly."""
    # Setup: Entry at 150.00, exit at 155.00, 100 shares
    mock_repository.positions[sample_position.id] = sample_position
    exit_signal = ExitSignal(
        reason="target_hit",
        price=Decimal("155.00"),
        timestamp=datetime.now(UTC),
    )

    # Execute
    closed_position = await state_manager.handle_exit(
        campaign_id=sample_campaign_id,
        position_id=sample_position.id,
        exit_signal=exit_signal,
    )

    # Verify: Realized P&L = (155.00 - 150.00) * 100 = 500.00
    expected_pnl = Decimal("500.00")
    assert closed_position.realized_pnl == expected_pnl


@pytest.mark.asyncio
async def test_handle_exit_not_found(state_manager, sample_campaign_id, sample_exit_signal):
    """Test exit handling with non-existent position."""
    non_existent_id = uuid4()

    # Execute & Verify
    with pytest.raises(ValueError, match="Position .* not found"):
        await state_manager.handle_exit(
            campaign_id=sample_campaign_id,
            position_id=non_existent_id,
            exit_signal=sample_exit_signal,
        )


# ============================================================================
# Test batch_update_positions
# ============================================================================


@pytest.mark.asyncio
async def test_batch_update_positions_success(state_manager, mock_repository, sample_campaign_id):
    """Test successful batch position updates."""
    # Setup: Create multiple positions
    position1_id = uuid4()
    position2_id = uuid4()
    position1 = Position(
        id=position1_id,
        campaign_id=sample_campaign_id,
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
    position2 = Position(
        id=position2_id,
        campaign_id=sample_campaign_id,
        signal_id=uuid4(),
        symbol="MSFT",
        timeframe="1h",
        entry_date=datetime.now(UTC),
        entry_price=Decimal("300.00"),
        shares=Decimal("50"),
        stop_loss=Decimal("295.00"),
        current_price=Decimal("300.00"),
        pattern_type="SOS",
    )
    mock_repository.positions[position1_id] = position1
    mock_repository.positions[position2_id] = position2

    # Execute
    position_updates = {
        position1_id: Decimal("152.00"),
        position2_id: Decimal("305.00"),
    }
    updated_positions = await state_manager.batch_update_positions(
        campaign_id=sample_campaign_id,
        position_updates=position_updates,
    )

    # Verify
    assert len(updated_positions) == 2
    assert updated_positions[0].current_price == Decimal("152.00")
    assert updated_positions[1].current_price == Decimal("305.00")
    assert len(mock_repository.batch_update_calls) == 1


@pytest.mark.asyncio
async def test_batch_update_positions_empty(state_manager, sample_campaign_id):
    """Test batch update with empty position list."""
    # Execute
    updated_positions = await state_manager.batch_update_positions(
        campaign_id=sample_campaign_id,
        position_updates={},
    )

    # Verify
    assert len(updated_positions) == 0


@pytest.mark.asyncio
async def test_batch_update_positions_partial_success(
    state_manager, mock_repository, sample_campaign_id
):
    """Test batch update with some positions not found."""
    # Setup: Create only one position
    position_id = uuid4()
    position = Position(
        id=position_id,
        campaign_id=sample_campaign_id,
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
    mock_repository.positions[position_id] = position

    # Execute: Request update for existing and non-existent positions
    position_updates = {
        position_id: Decimal("152.00"),
        uuid4(): Decimal("305.00"),  # Non-existent
    }
    updated_positions = await state_manager.batch_update_positions(
        campaign_id=sample_campaign_id,
        position_updates=position_updates,
    )

    # Verify: Only existing position should be updated
    assert len(updated_positions) == 1
    assert updated_positions[0].id == position_id
    assert updated_positions[0].current_price == Decimal("152.00")


@pytest.mark.asyncio
async def test_batch_update_positions_calculates_pnl(
    state_manager, mock_repository, sample_campaign_id
):
    """Test batch update calculates P&L correctly for all positions."""
    # Setup
    position1_id = uuid4()
    position2_id = uuid4()
    position1 = Position(
        id=position1_id,
        campaign_id=sample_campaign_id,
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
    position2 = Position(
        id=position2_id,
        campaign_id=sample_campaign_id,
        signal_id=uuid4(),
        symbol="MSFT",
        timeframe="1h",
        entry_date=datetime.now(UTC),
        entry_price=Decimal("300.00"),
        shares=Decimal("50"),
        stop_loss=Decimal("295.00"),
        current_price=Decimal("300.00"),
        pattern_type="SOS",
    )
    mock_repository.positions[position1_id] = position1
    mock_repository.positions[position2_id] = position2

    # Execute
    position_updates = {
        position1_id: Decimal("152.00"),  # +2 * 100 = +200
        position2_id: Decimal("298.00"),  # -2 * 50 = -100
    }
    updated_positions = await state_manager.batch_update_positions(
        campaign_id=sample_campaign_id,
        position_updates=position_updates,
    )

    # Verify
    assert updated_positions[0].current_pnl == Decimal("200.00")
    assert updated_positions[1].current_pnl == Decimal("-100.00")


# ============================================================================
# Integration-Style Tests
# ============================================================================


@pytest.mark.asyncio
async def test_full_position_lifecycle(
    state_manager, mock_repository, sample_campaign_id, sample_position
):
    """Test complete position lifecycle: create -> update -> exit."""
    # Setup: Create position
    mock_repository.positions[sample_position.id] = sample_position

    # Step 1: Update position state with new bar
    bar1 = OHLCVBar(
        symbol="AAPL",
        timeframe="1h",
        timestamp=datetime.now(UTC),
        open=Decimal("151.00"),
        high=Decimal("152.50"),
        low=Decimal("150.50"),
        close=Decimal("151.50"),
        volume=1000000,
        spread=Decimal("2.00"),
    )
    updated_position = await state_manager.update_position_state(
        campaign_id=sample_campaign_id,
        position_id=sample_position.id,
        bar=bar1,
    )
    assert updated_position.current_price == Decimal("151.50")
    assert updated_position.current_pnl == Decimal("150.00")  # (151.50 - 150.00) * 100

    # Step 2: Another update
    bar2 = OHLCVBar(
        symbol="AAPL",
        timeframe="1h",
        timestamp=datetime.now(UTC),
        open=Decimal("151.50"),
        high=Decimal("153.00"),
        low=Decimal("151.00"),
        close=Decimal("152.50"),
        volume=1200000,
        spread=Decimal("2.00"),
    )
    updated_position = await state_manager.update_position_state(
        campaign_id=sample_campaign_id,
        position_id=sample_position.id,
        bar=bar2,
    )
    assert updated_position.current_price == Decimal("152.50")
    assert updated_position.current_pnl == Decimal("250.00")  # (152.50 - 150.00) * 100

    # Step 3: Exit position
    exit_signal = ExitSignal(
        reason="target_hit",
        price=Decimal("155.00"),
        timestamp=datetime.now(UTC),
    )
    closed_position = await state_manager.handle_exit(
        campaign_id=sample_campaign_id,
        position_id=sample_position.id,
        exit_signal=exit_signal,
    )
    assert closed_position.status == PositionStatus.CLOSED
    assert closed_position.exit_price == Decimal("155.00")
    assert closed_position.realized_pnl == Decimal("500.00")  # (155.00 - 150.00) * 100

    # Verify repository calls
    assert len(mock_repository.update_position_calls) == 2
    assert len(mock_repository.close_position_calls) == 1
