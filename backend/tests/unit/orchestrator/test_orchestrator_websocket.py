"""
Tests for WebSocket emission in orchestrator signal generation.

Story 25.11: Wire orchestrator signal generation to WebSocket broadcast

Test Coverage:
- AC1: emit_signal_generated called once per signal when signals exist
- AC3: emit NOT called when signals list is empty
- AC4: WebSocket exception in emit → analyze_symbol still returns signals, no crash
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.models.signal import TradeSignal as TradeSignalModel
from src.orchestrator.orchestrator_facade import MasterOrchestratorFacade


@pytest.fixture
def mock_websocket_manager():
    """Mock WebSocket manager with emit_signal_generated method."""
    with patch("src.orchestrator.orchestrator_facade.websocket_manager") as mock_mgr:
        mock_mgr.emit_signal_generated = AsyncMock()
        yield mock_mgr


@pytest.fixture
def mock_coordinator():
    """Mock pipeline coordinator that returns successful result."""
    with patch("src.orchestrator.orchestrator_facade.PipelineCoordinator") as mock_coord_cls:
        mock_coord = MagicMock()
        mock_coord.run = AsyncMock()
        mock_coord_cls.return_value = mock_coord
        yield mock_coord


@pytest.fixture
def mock_fetch_bars():
    """Mock _fetch_bars to return sample bars."""

    async def _mock_fetch(symbol, timeframe):
        # Return mock bars
        from datetime import UTC, datetime
        from decimal import Decimal

        bar = MagicMock()
        bar.timestamp = datetime.now(UTC)
        bar.open = Decimal("100.0")
        bar.high = Decimal("105.0")
        bar.low = Decimal("95.0")
        bar.close = Decimal("102.0")
        bar.volume = Decimal("1000000")
        return [bar]

    return _mock_fetch


@pytest.fixture
def sample_signal():
    """Create a sample TradeSignalModel."""
    from datetime import UTC, datetime
    from decimal import Decimal

    from src.models.signal import ConfidenceComponents, TargetLevels
    from src.models.validation import ValidationChain

    return TradeSignalModel(
        symbol="AAPL",
        pattern_type="SPRING",
        phase="C",
        timeframe="1d",
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("148.00"),
        target_levels=TargetLevels(primary_target=Decimal("156.00")),
        position_size=Decimal("100"),
        risk_amount=Decimal("200.00"),
        r_multiple=Decimal("3.0"),
        notional_value=Decimal("15000.00"),
        confidence_score=85,
        confidence_components=ConfidenceComponents(
            pattern_confidence=85,
            phase_confidence=85,
            volume_confidence=85,
            overall_confidence=85,
        ),
        validation_chain=ValidationChain(pattern_id=uuid4()),
        campaign_id=None,
        timestamp=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_emit_signal_generated_called_for_each_signal(
    mock_websocket_manager, mock_coordinator, mock_fetch_bars, sample_signal
):
    """
    AC1: emit_signal_generated called once per signal when signals exist.

    Verify:
    - emit_signal_generated is called with signal dict
    - Called once for each signal in the list
    - Signal serialized via model_dump()
    """
    # Arrange
    facade = MasterOrchestratorFacade()
    facade._fetch_bars = mock_fetch_bars
    facade._persist_signals = AsyncMock(return_value=[])  # No failed persists
    facade._associate_campaigns = AsyncMock()

    # Mock pipeline to return 2 signals
    from src.models.signal import ConfidenceComponents
    from src.models.validation import ValidationChain

    signal2 = TradeSignalModel(
        symbol="AAPL",
        pattern_type="SOS",
        phase="D",
        timeframe="1d",
        entry_price=sample_signal.entry_price,
        stop_loss=sample_signal.stop_loss,
        target_levels=sample_signal.target_levels,
        position_size=sample_signal.position_size,
        risk_amount=sample_signal.risk_amount,
        r_multiple=sample_signal.r_multiple,
        notional_value=sample_signal.notional_value,
        confidence_score=80,
        confidence_components=ConfidenceComponents(
            pattern_confidence=80,
            phase_confidence=80,
            volume_confidence=80,
            overall_confidence=80,
        ),
        validation_chain=ValidationChain(pattern_id=uuid4()),
        campaign_id=None,
        timestamp=sample_signal.timestamp,
    )

    mock_coordinator.run.return_value.success = True
    mock_coordinator.run.return_value.output = [sample_signal, signal2]

    # Act
    result = await facade.analyze_symbol("AAPL", "1d")

    # Assert
    assert len(result) == 2
    assert mock_websocket_manager.emit_signal_generated.call_count == 2

    # Verify signal was serialized via model_dump()
    first_call_arg = mock_websocket_manager.emit_signal_generated.call_args_list[0][0][0]
    assert isinstance(first_call_arg, dict)
    assert first_call_arg["symbol"] == "AAPL"
    assert first_call_arg["pattern_type"] == "SPRING"


@pytest.mark.asyncio
async def test_emit_not_called_when_no_signals(
    mock_websocket_manager, mock_coordinator, mock_fetch_bars
):
    """
    AC3: emit NOT called when signals list is empty.

    Verify:
    - emit_signal_generated is NOT called when pipeline returns empty list
    - No errors raised
    """
    # Arrange
    facade = MasterOrchestratorFacade()
    facade._fetch_bars = mock_fetch_bars
    facade._persist_signals = AsyncMock(return_value=[])
    facade._associate_campaigns = AsyncMock()

    # Mock pipeline to return no signals
    mock_coordinator.run.return_value.success = True
    mock_coordinator.run.return_value.output = []

    # Act
    result = await facade.analyze_symbol("AAPL", "1d")

    # Assert
    assert len(result) == 0
    mock_websocket_manager.emit_signal_generated.assert_not_called()


@pytest.mark.asyncio
async def test_websocket_exception_does_not_block_return(
    mock_websocket_manager, mock_coordinator, mock_fetch_bars, sample_signal
):
    """
    AC4: WebSocket exception in emit → analyze_symbol still returns signals, no crash.

    Verify:
    - emit_signal_generated raises exception
    - analyze_symbol catches exception and continues
    - analyze_symbol returns signals successfully
    - Exception logged but not re-raised
    """
    # Arrange
    facade = MasterOrchestratorFacade()
    facade._fetch_bars = mock_fetch_bars
    facade._persist_signals = AsyncMock(return_value=[])
    facade._associate_campaigns = AsyncMock()

    # Mock WebSocket to raise exception
    mock_websocket_manager.emit_signal_generated.side_effect = Exception(
        "WebSocket connection lost"
    )

    # Mock pipeline to return 1 signal
    mock_coordinator.run.return_value.success = True
    mock_coordinator.run.return_value.output = [sample_signal]

    # Act - should NOT raise exception
    result = await facade.analyze_symbol("AAPL", "1d")

    # Assert
    assert len(result) == 1
    assert result[0].symbol == "AAPL"
    # Verify emit was attempted but failed gracefully
    mock_websocket_manager.emit_signal_generated.assert_called_once()


@pytest.mark.asyncio
async def test_websocket_exception_in_one_signal_does_not_block_others(
    mock_websocket_manager, mock_coordinator, mock_fetch_bars, sample_signal
):
    """
    Edge case: If emit fails for first signal, still emit for second signal.

    Verify:
    - First emit raises exception
    - Second emit succeeds
    - Both signals returned in result
    """
    # Arrange
    facade = MasterOrchestratorFacade()
    facade._fetch_bars = mock_fetch_bars
    facade._persist_signals = AsyncMock(return_value=[])
    facade._associate_campaigns = AsyncMock()

    from src.models.signal import ConfidenceComponents
    from src.models.validation import ValidationChain

    signal2 = TradeSignalModel(
        symbol="AAPL",
        pattern_type="SOS",
        phase="D",
        timeframe="1d",
        entry_price=sample_signal.entry_price,
        stop_loss=sample_signal.stop_loss,
        target_levels=sample_signal.target_levels,
        position_size=sample_signal.position_size,
        risk_amount=sample_signal.risk_amount,
        r_multiple=sample_signal.r_multiple,
        notional_value=sample_signal.notional_value,
        confidence_score=80,
        confidence_components=ConfidenceComponents(
            pattern_confidence=80,
            phase_confidence=80,
            volume_confidence=80,
            overall_confidence=80,
        ),
        validation_chain=ValidationChain(pattern_id=uuid4()),
        campaign_id=None,
        timestamp=sample_signal.timestamp,
    )

    # First call raises, second call succeeds
    mock_websocket_manager.emit_signal_generated.side_effect = [
        Exception("WebSocket error"),
        None,  # Second call succeeds
    ]

    mock_coordinator.run.return_value.success = True
    mock_coordinator.run.return_value.output = [sample_signal, signal2]

    # Act
    result = await facade.analyze_symbol("AAPL", "1d")

    # Assert
    assert len(result) == 2
    assert mock_websocket_manager.emit_signal_generated.call_count == 2


@pytest.mark.asyncio
async def test_signal_serialization_uses_model_dump(
    mock_websocket_manager, mock_coordinator, mock_fetch_bars, sample_signal
):
    """
    Verify signal serialization uses model_dump() exclusively.

    Per approval notes: Do NOT use signal.__dict__ as fallback.
    If signal lacks model_dump(), that's a bug to raise.
    """
    # Arrange
    facade = MasterOrchestratorFacade()
    facade._fetch_bars = mock_fetch_bars
    facade._persist_signals = AsyncMock(return_value=[])
    facade._associate_campaigns = AsyncMock()

    mock_coordinator.run.return_value.success = True
    mock_coordinator.run.return_value.output = [sample_signal]

    # Act
    await facade.analyze_symbol("AAPL", "1d")

    # Assert
    call_arg = mock_websocket_manager.emit_signal_generated.call_args[0][0]

    # Verify it's a dict (result of model_dump())
    assert isinstance(call_arg, dict)

    # Verify it matches model_dump() output structure
    expected_dict = sample_signal.model_dump()
    assert call_arg == expected_dict
