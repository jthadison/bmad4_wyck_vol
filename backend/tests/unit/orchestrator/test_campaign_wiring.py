"""
Unit tests for campaign wiring in orchestrator_facade.py (Story 25.10).

Tests all 7 acceptance criteria:
- AC1: Spring creates new campaign
- AC2: SOS adds to existing campaign
- AC3: LPS adds to campaign
- AC4: No duplicate campaigns per range
- AC5: Campaign state persists (integration test)
- AC6: Signal campaign_id visible in API (integration test)
- AC7: Graceful degradation without campaign_manager
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from src.campaign_management.campaign_manager import CampaignManager
from src.models.campaign_lifecycle import Campaign, CampaignStatus
from src.models.signal import ConfidenceComponents, TargetLevels, TradeSignal
from src.models.validation import ValidationChain
from src.orchestrator.orchestrator_facade import MasterOrchestratorFacade

# Test Fixtures


@pytest.fixture
def mock_campaign_manager():
    """Mock CampaignManager for testing."""
    manager = Mock(spec=CampaignManager)
    manager.get_active_campaigns = AsyncMock(return_value=[])
    manager.create_campaign = AsyncMock()
    manager.add_signal_to_campaign = AsyncMock()
    return manager


@pytest.fixture
def spring_signal():
    """Sample Spring signal for testing (TradeSignalModel)."""
    return TradeSignal(
        symbol="AAPL",
        pattern_type="SPRING",
        phase="C",
        timeframe="1h",
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


@pytest.fixture
def sos_signal():
    """Sample SOS signal for testing (TradeSignalModel)."""
    return TradeSignal(
        symbol="AAPL",
        pattern_type="SOS",
        phase="D",
        timeframe="1h",
        entry_price=Decimal("157.00"),
        stop_loss=Decimal("154.00"),
        target_levels=TargetLevels(primary_target=Decimal("163.00")),
        position_size=Decimal("100"),
        risk_amount=Decimal("300.00"),
        r_multiple=Decimal("2.0"),
        notional_value=Decimal("15700.00"),
        confidence_score=80,
        confidence_components=ConfidenceComponents(
            pattern_confidence=80,
            phase_confidence=80,
            volume_confidence=80,
            overall_confidence=80,
        ),
        validation_chain=ValidationChain(pattern_id=uuid4()),
        campaign_id=None,
        timestamp=datetime.now(UTC),
    )


@pytest.fixture
def lps_signal():
    """Sample LPS signal for testing (TradeSignalModel)."""
    return TradeSignal(
        symbol="AAPL",
        pattern_type="LPS",
        phase="E",
        timeframe="1h",
        entry_price=Decimal("155.50"),
        stop_loss=Decimal("153.00"),
        target_levels=TargetLevels(primary_target=Decimal("161.50")),
        position_size=Decimal("100"),
        risk_amount=Decimal("250.00"),
        r_multiple=Decimal("2.4"),
        notional_value=Decimal("15550.00"),
        confidence_score=82,
        confidence_components=ConfidenceComponents(
            pattern_confidence=82,
            phase_confidence=82,
            volume_confidence=82,
            overall_confidence=82,
        ),
        validation_chain=ValidationChain(pattern_id=uuid4()),
        campaign_id=None,
        timestamp=datetime.now(UTC),
    )


@pytest.fixture
def existing_campaign():
    """Sample existing campaign for testing."""
    return Campaign(
        id=uuid4(),
        campaign_id="AAPL-2024-02-22",
        symbol="AAPL",
        timeframe="1h",
        trading_range_id=uuid4(),
        status=CampaignStatus.ACTIVE,
        phase="C",
        positions=[],
        entries={},
        total_risk=Decimal("200.00"),
        total_allocation=Decimal("2.0"),
        current_risk=Decimal("200.00"),
        total_shares=Decimal("100"),
        total_pnl=Decimal("0.00"),
        start_date=datetime.now(UTC),
        version=1,
    )


# AC1: Spring Creates New Campaign


@pytest.mark.asyncio
async def test_spring_creates_new_campaign_when_none_exists(mock_campaign_manager, spring_signal):
    """
    AC1: Given a Spring signal with no existing campaigns,
    When analyze_symbol processes the signal,
    Then create_campaign() is called and campaign_id is populated.
    """
    # Arrange
    campaign_id_str = "AAPL-2024-02-22"
    created_campaign = Campaign(
        id=uuid4(),
        campaign_id=campaign_id_str,
        symbol="AAPL",
        timeframe="1h",
        trading_range_id=uuid4(),
        status=CampaignStatus.ACTIVE,
        phase="C",
        positions=[],
        entries={},
        total_risk=Decimal("200.00"),
        total_allocation=Decimal("2.0"),
        current_risk=Decimal("200.00"),
        total_shares=Decimal("100"),
        total_pnl=Decimal("0.00"),
        start_date=datetime.now(UTC),
        version=1,
    )
    mock_campaign_manager.get_active_campaigns.return_value = []
    mock_campaign_manager.create_campaign.return_value = created_campaign

    facade = MasterOrchestratorFacade(campaign_manager=mock_campaign_manager)

    # Act
    await facade._associate_campaigns([spring_signal], "AAPL")

    # Assert
    mock_campaign_manager.create_campaign.assert_called_once()
    assert spring_signal.campaign_id == campaign_id_str


# AC2: SOS Adds to Existing Campaign


@pytest.mark.asyncio
async def test_sos_adds_to_existing_spring_campaign(
    mock_campaign_manager, sos_signal, existing_campaign
):
    """
    AC2: Given an existing Spring campaign,
    When an SOS signal is generated,
    Then add_signal_to_campaign() is called with the existing campaign_id.
    """
    # Arrange
    mock_campaign_manager.get_active_campaigns.return_value = [existing_campaign]

    facade = MasterOrchestratorFacade(campaign_manager=mock_campaign_manager)

    # Act
    await facade._associate_campaigns([sos_signal], "AAPL")

    # Assert
    mock_campaign_manager.add_signal_to_campaign.assert_called_once_with(
        existing_campaign.campaign_id, sos_signal
    )
    assert sos_signal.campaign_id == existing_campaign.campaign_id


# AC3: LPS Adds to Campaign


@pytest.mark.asyncio
async def test_lps_adds_to_existing_campaign(mock_campaign_manager, lps_signal, existing_campaign):
    """
    AC3: Given an existing campaign in ADD phase,
    When an LPS signal is generated,
    Then the LPS signal is associated with the existing campaign.
    """
    # Arrange
    existing_campaign.phase = "D"  # ADD phase after SOS
    mock_campaign_manager.get_active_campaigns.return_value = [existing_campaign]

    facade = MasterOrchestratorFacade(campaign_manager=mock_campaign_manager)

    # Act
    await facade._associate_campaigns([lps_signal], "AAPL")

    # Assert
    mock_campaign_manager.add_signal_to_campaign.assert_called_once_with(
        existing_campaign.campaign_id, lps_signal
    )
    assert lps_signal.campaign_id == existing_campaign.campaign_id


# AC4: No Duplicate Campaigns per Range


@pytest.mark.asyncio
async def test_second_spring_uses_existing_campaign(
    mock_campaign_manager, spring_signal, existing_campaign
):
    """
    AC4: Given an existing Spring campaign,
    When a second Spring signal is generated (overlapping range),
    Then no new campaign is created and the signal uses the existing campaign_id.
    """
    # Arrange
    mock_campaign_manager.get_active_campaigns.return_value = [existing_campaign]

    facade = MasterOrchestratorFacade(campaign_manager=mock_campaign_manager)

    # Act
    await facade._associate_campaigns([spring_signal], "AAPL")

    # Assert
    mock_campaign_manager.create_campaign.assert_not_called()
    assert spring_signal.campaign_id == existing_campaign.campaign_id


# AC7: Graceful Degradation Without Campaign Manager


@pytest.mark.asyncio
async def test_no_campaign_manager_graceful_degradation(spring_signal):
    """
    AC7: Given campaign_manager = None,
    When analyze_symbol generates a signal,
    Then the signal is returned with campaign_id = None and no exception is raised.
    """
    # Arrange
    facade = MasterOrchestratorFacade(campaign_manager=None)

    # Act
    await facade._associate_campaigns([spring_signal], "AAPL")

    # Assert - no exception raised, campaign_id remains None
    assert spring_signal.campaign_id is None


# SOS Without Prior Campaign


@pytest.mark.asyncio
async def test_sos_without_campaign_logs_warning(mock_campaign_manager, sos_signal):
    """
    When an SOS signal is generated without a prior Spring campaign,
    Then a warning is logged and the signal proceeds without campaign_id.
    """
    # Arrange
    mock_campaign_manager.get_active_campaigns.return_value = []

    facade = MasterOrchestratorFacade(campaign_manager=mock_campaign_manager)

    # Act
    with patch("src.orchestrator.orchestrator_facade.logger") as mock_logger:
        await facade._associate_campaigns([sos_signal], "AAPL")

        # Assert
        mock_logger.warning.assert_called()
        assert sos_signal.campaign_id is None


# Multiple Signals in One Batch


@pytest.mark.asyncio
async def test_multiple_signals_spring_sos_lps_sequence(
    mock_campaign_manager, spring_signal, sos_signal, lps_signal
):
    """
    When Spring, SOS, and LPS signals are processed in sequence,
    Then Spring creates campaign, SOS and LPS add to it, all share campaign_id.
    """
    # Arrange
    campaign_id_str = "AAPL-2024-02-22"
    created_campaign = Campaign(
        id=uuid4(),
        campaign_id=campaign_id_str,
        symbol="AAPL",
        timeframe="1h",
        trading_range_id=uuid4(),
        status=CampaignStatus.ACTIVE,
        phase="C",
        positions=[],
        entries={},
        total_risk=Decimal("200.00"),
        total_allocation=Decimal("2.0"),
        current_risk=Decimal("200.00"),
        total_shares=Decimal("100"),
        total_pnl=Decimal("0.00"),
        start_date=datetime.now(UTC),
        version=1,
    )

    # First call: no campaigns (Spring creates)
    # Second call: campaign exists (SOS adds)
    # Third call: campaign exists (LPS adds)
    mock_campaign_manager.get_active_campaigns.side_effect = [
        [],  # Spring: no campaigns
        [created_campaign],  # SOS: campaign exists
        [created_campaign],  # LPS: campaign exists
    ]
    mock_campaign_manager.create_campaign.return_value = created_campaign

    facade = MasterOrchestratorFacade(campaign_manager=mock_campaign_manager)

    # Act - process Spring first
    await facade._associate_campaigns([spring_signal], "AAPL")
    # Then SOS
    await facade._associate_campaigns([sos_signal], "AAPL")
    # Then LPS
    await facade._associate_campaigns([lps_signal], "AAPL")

    # Assert
    assert spring_signal.campaign_id == campaign_id_str
    assert sos_signal.campaign_id == campaign_id_str
    assert lps_signal.campaign_id == campaign_id_str
    mock_campaign_manager.create_campaign.assert_called_once()
    assert mock_campaign_manager.add_signal_to_campaign.call_count == 2
