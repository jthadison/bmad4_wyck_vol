"""
Integration tests for Campaign Tracker API (Story 11.4)

Tests GET /api/v1/campaigns endpoint with database integration,
filtering by status and symbol, and response structure validation.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient

from src.repositories.models import CampaignModel
from src.repositories.models import PositionModel as PositionDBModel


@pytest.mark.asyncio
class TestCampaignTrackerAPI:
    """Integration tests for campaign tracker API endpoint."""

    async def test_get_campaigns_empty(self, async_client: AsyncClient, auth_headers: dict):
        """Test GET /campaigns with no campaigns returns empty list."""
        response = await async_client.get("/api/v1/campaigns", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert isinstance(data["data"], list)

    async def test_get_campaigns_with_data(
        self, async_client: AsyncClient, auth_headers: dict, db_session
    ):
        """Test GET /campaigns returns campaign list with correct structure."""
        # Create test campaign (trading_range_id is optional)
        campaign = CampaignModel(
            id=uuid4(),
            campaign_id="AAPL-2024-01-01",  # Required field
            symbol="AAPL",
            timeframe="1D",
            trading_range_id=uuid4(),  # Just use a UUID reference
            status="ACTIVE",
            phase="C",  # Wyckoff phase
            start_date=datetime.now(UTC),
            total_allocation=Decimal("5.00"),
            current_risk=Decimal("3000.00"),
            created_at=datetime.now(UTC),
        )
        db_session.add(campaign)
        await db_session.commit()

        response = await async_client.get("/api/v1/campaigns", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        campaigns = data["data"]
        assert len(campaigns) >= 1

        # Verify campaign structure
        campaign_response = campaigns[0]
        assert "id" in campaign_response
        assert "symbol" in campaign_response
        assert campaign_response["symbol"] == "AAPL"
        assert "status" in campaign_response
        assert "progression" in campaign_response
        assert "health" in campaign_response
        assert "entries" in campaign_response

    async def test_filter_campaigns_by_status(
        self, async_client: AsyncClient, auth_headers: dict, db_session
    ):
        """Test filtering campaigns by status parameter."""
        # Create active campaign
        active_campaign = CampaignModel(
            id=uuid4(),
            campaign_id="AAPL-2024-01-01",  # Required field
            symbol="AAPL",
            timeframe="1D",
            trading_range_id=uuid4(),  # Just use a UUID reference
            status="ACTIVE",
            phase="C",  # Wyckoff phase
            start_date=datetime.now(UTC),
            total_allocation=Decimal("5.00"),
            current_risk=Decimal("3000.00"),
            created_at=datetime.now(UTC),
        )
        db_session.add(active_campaign)

        # Create completed campaign
        completed_campaign = CampaignModel(
            id=uuid4(),
            campaign_id="AAPL-2024-01-02",  # Required field
            symbol="AAPL",
            timeframe="1D",
            trading_range_id=uuid4(),  # Just use a UUID reference
            status="COMPLETED",
            phase="C",  # Wyckoff phase
            start_date=datetime.now(UTC),
            total_allocation=Decimal("5.00"),
            current_risk=Decimal("0.00"),
            created_at=datetime.now(UTC),
        )
        db_session.add(completed_campaign)
        await db_session.commit()

        # Filter by ACTIVE status
        response = await async_client.get("/api/v1/campaigns?status=ACTIVE", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        campaigns = data["data"]

        # All campaigns should have ACTIVE status
        for campaign in campaigns:
            assert campaign["status"] == "ACTIVE"

    async def test_filter_campaigns_by_symbol(
        self, async_client: AsyncClient, auth_headers: dict, db_session
    ):
        """Test filtering campaigns by symbol parameter."""
        # Create campaigns
        campaign_aapl = CampaignModel(
            id=uuid4(),
            campaign_id="AAPL-2024-01-01",  # Required field
            symbol="AAPL",
            timeframe="1D",
            trading_range_id=uuid4(),  # Just use a UUID reference
            status="ACTIVE",
            phase="C",  # Wyckoff phase
            start_date=datetime.now(UTC),
            total_allocation=Decimal("5.00"),
            current_risk=Decimal("3000.00"),
            created_at=datetime.now(UTC),
        )
        db_session.add(campaign_aapl)

        campaign_msft = CampaignModel(
            id=uuid4(),
            campaign_id="MSFT-2024-01-01",  # Required field
            symbol="MSFT",
            timeframe="1D",
            trading_range_id=uuid4(),  # Just use a UUID reference
            status="ACTIVE",
            phase="C",  # Wyckoff phase
            start_date=datetime.now(UTC),
            total_allocation=Decimal("5.00"),
            current_risk=Decimal("3000.00"),
            created_at=datetime.now(UTC),
        )
        db_session.add(campaign_msft)
        await db_session.commit()

        # Filter by AAPL symbol
        response = await async_client.get("/api/v1/campaigns?symbol=AAPL", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        campaigns = data["data"]

        # All campaigns should have AAPL symbol
        for campaign in campaigns:
            assert campaign["symbol"] == "AAPL"

    async def test_campaign_response_structure(
        self, async_client: AsyncClient, auth_headers: dict, db_session
    ):
        """Test campaign response has all required fields."""
        # Create campaign with position
        campaign = CampaignModel(
            id=uuid4(),
            campaign_id="AAPL-2024-01-01",  # Required field
            symbol="AAPL",
            timeframe="1D",
            trading_range_id=uuid4(),  # Just use a UUID reference
            status="ACTIVE",
            phase="C",  # Wyckoff phase
            start_date=datetime.now(UTC),
            total_allocation=Decimal("5.00"),
            current_risk=Decimal("3000.00"),
            created_at=datetime.now(UTC),
        )
        db_session.add(campaign)

        position = PositionDBModel(
            id=uuid4(),
            campaign_id=campaign.id,
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1D",
            pattern_type="SPRING",
            entry_date=datetime.now(UTC),
            entry_price=Decimal("150.00"),
            shares=20,
            stop_loss=Decimal("148.50"),
            status="OPEN",
            created_at=datetime.now(UTC),
        )
        db_session.add(position)
        await db_session.commit()

        response = await async_client.get("/api/v1/campaigns", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        campaign_data = data["data"][0]

        # Verify all required fields
        required_fields = [
            "id",
            "symbol",
            "timeframe",
            "trading_range_id",
            "status",
            "total_allocation",
            "current_risk",
            "entries",
            "average_entry",
            "total_pnl",
            "total_pnl_percent",
            "progression",
            "health",
            "exit_plan",
            "trading_range_levels",
            "preliminary_events",
            "campaign_quality_score",
            "started_at",
        ]

        for field in required_fields:
            assert field in campaign_data, f"Missing required field: {field}"

        # Verify nested structures
        assert "current_phase" in campaign_data["progression"]
        assert "completed_phases" in campaign_data["progression"]
        assert "next_expected" in campaign_data["progression"]

        assert isinstance(campaign_data["entries"], list)
        if len(campaign_data["entries"]) > 0:
            entry = campaign_data["entries"][0]
            assert "pattern_type" in entry
            assert "entry_price" in entry
            assert "shares" in entry
            assert "pnl" in entry
            assert "pnl_percent" in entry
