"""
Unit tests for PortfolioMonitor.

Story 18.10.5: Services Extraction and Orchestrator Facade (AC2)
"""

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from src.orchestrator.services.portfolio_monitor import PortfolioMonitor


class TestPortfolioMonitor:
    """Tests for PortfolioMonitor."""

    @pytest.fixture
    def monitor(self) -> PortfolioMonitor:
        """Create test monitor instance."""
        return PortfolioMonitor()

    @pytest.fixture
    def mock_position_repo(self):
        """Create mock position repository."""
        repo = AsyncMock()
        repo.get_open_positions = AsyncMock(return_value=[])
        return repo

    @pytest.fixture
    def mock_campaign_repo(self):
        """Create mock campaign repository."""
        repo = AsyncMock()
        repo.get_active_campaigns = AsyncMock(return_value=[])
        return repo

    @pytest.fixture
    def mock_account_service(self):
        """Create mock account service."""
        service = AsyncMock()
        service.get_equity = AsyncMock(return_value=Decimal("100000.00"))
        return service

    @pytest.mark.asyncio
    async def test_build_context_default_equity(self, monitor: PortfolioMonitor):
        """Test context building with default equity."""
        context = await monitor.build_context()

        assert context.account_equity == Decimal("100000.00")
        assert context.open_positions == []
        assert context.active_campaigns == []

    @pytest.mark.asyncio
    async def test_build_context_with_custom_default_equity(self):
        """Test context building with custom default equity."""
        monitor = PortfolioMonitor(default_equity=Decimal("50000.00"))
        context = await monitor.build_context()

        assert context.account_equity == Decimal("50000.00")

    @pytest.mark.asyncio
    async def test_build_context_with_account_service(self, mock_account_service):
        """Test context building with account service."""
        mock_account_service.get_equity = AsyncMock(return_value=Decimal("200000.00"))
        monitor = PortfolioMonitor(account_service=mock_account_service)

        context = await monitor.build_context()

        assert context.account_equity == Decimal("200000.00")
        mock_account_service.get_equity.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_context_with_position_repo(self, mock_position_repo):
        """Test context building with position repository."""
        from uuid import uuid4

        from src.models.portfolio import Position

        mock_positions = [
            Position(
                symbol="AAPL",
                position_risk_pct=Decimal("2.0"),
                status="OPEN",
                wyckoff_phase="D",
                volume_confirmation_score=Decimal("25.0"),
                sector="Technology",
                campaign_id=uuid4(),
            )
        ]
        mock_position_repo.get_open_positions = AsyncMock(return_value=mock_positions)
        monitor = PortfolioMonitor(position_repo=mock_position_repo)

        context = await monitor.build_context()

        assert len(context.open_positions) == 1
        assert context.open_positions[0].symbol == "AAPL"
        mock_position_repo.get_open_positions.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_context_with_campaign_repo(self, mock_campaign_repo):
        """Test context building with campaign repository."""
        from uuid import uuid4

        from src.models.correlation_campaign import CampaignForCorrelation

        mock_campaigns = [
            CampaignForCorrelation(
                campaign_id=uuid4(),
                symbol="AAPL",
                sector="Technology",
                asset_class="US_EQUITIES",
                total_campaign_risk=Decimal("3.0"),
                status="ACTIVE",
            )
        ]
        mock_campaign_repo.get_active_campaigns = AsyncMock(return_value=mock_campaigns)
        monitor = PortfolioMonitor(campaign_repo=mock_campaign_repo)

        context = await monitor.build_context()

        assert len(context.active_campaigns) == 1
        assert context.active_campaigns[0].symbol == "AAPL"
        mock_campaign_repo.get_active_campaigns.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_context_handles_account_service_error(self, mock_account_service):
        """Test graceful handling of account service errors."""
        mock_account_service.get_equity = AsyncMock(side_effect=Exception("DB error"))
        monitor = PortfolioMonitor(
            account_service=mock_account_service,
            default_equity=Decimal("75000.00"),
        )

        context = await monitor.build_context()

        # Should fall back to default equity
        assert context.account_equity == Decimal("75000.00")

    @pytest.mark.asyncio
    async def test_build_context_handles_position_repo_error(self, mock_position_repo):
        """Test graceful handling of position repo errors."""
        mock_position_repo.get_open_positions = AsyncMock(side_effect=Exception("DB error"))
        monitor = PortfolioMonitor(position_repo=mock_position_repo)

        context = await monitor.build_context()

        # Should return empty list
        assert context.open_positions == []

    @pytest.mark.asyncio
    async def test_build_context_handles_campaign_repo_error(self, mock_campaign_repo):
        """Test graceful handling of campaign repo errors."""
        mock_campaign_repo.get_active_campaigns = AsyncMock(side_effect=Exception("DB error"))
        monitor = PortfolioMonitor(campaign_repo=mock_campaign_repo)

        context = await monitor.build_context()

        # Should return empty list
        assert context.active_campaigns == []

    @pytest.mark.asyncio
    async def test_get_portfolio_heat_empty_positions(self, monitor: PortfolioMonitor):
        """Test portfolio heat calculation with no positions."""
        heat = await monitor.get_portfolio_heat()

        assert heat == Decimal("0")

    @pytest.mark.asyncio
    async def test_context_has_correlation_config(self, monitor: PortfolioMonitor):
        """Test that context includes correlation config."""
        context = await monitor.build_context()

        assert context.correlation_config is not None
        assert context.correlation_config.max_sector_correlation == Decimal("6.0")
        assert context.correlation_config.max_asset_class_correlation == Decimal("15.0")
