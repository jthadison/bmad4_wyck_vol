"""
Integration tests for Campaign Tracker API with Authentication (Story 11.4 + QA Fixes)

Tests GET /api/v1/campaigns endpoint with:
- JWT authentication (SEC-001)
- User isolation (CODE-002)
- Pagination (CODE-003)
- Database integration
- Filtering by status and symbol
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from src.models.campaign import Campaign as CampaignModel
from src.models.position import Position as PositionModel
from src.models.trading_range import TradingRange

# Note: Authentication fixtures (test_user_id, test_user_id_2, auth_token, auth_headers)
# are provided by conftest.py


@pytest.mark.asyncio
class TestCampaignTrackerAPIAuthentication:
    """Test authentication requirements (SEC-001)."""

    async def test_get_campaigns_without_auth_returns_401(self, async_client: AsyncClient):
        """Test GET /campaigns without auth token returns 401 Unauthorized."""
        response = await async_client.get("/api/v1/campaigns")

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    async def test_get_campaigns_with_invalid_token_returns_401(self, async_client: AsyncClient):
        """Test GET /campaigns with invalid token returns 401."""
        headers = {"Authorization": "Bearer invalid_token_12345"}
        response = await async_client.get("/api/v1/campaigns", headers=headers)

        assert response.status_code == 401

    async def test_get_campaigns_with_valid_token_returns_200(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test GET /campaigns with valid token returns 200."""
        response = await async_client.get("/api/v1/campaigns", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data


@pytest.mark.asyncio
class TestCampaignTrackerAPIUserIsolation:
    """Test user isolation (CODE-002)."""

    async def test_user_only_sees_own_campaigns(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_user_id: UUID,
        test_user_id_2: UUID,
        db_session,
    ):
        """Test users can only see their own campaigns, not other users'."""
        # Create trading range
        trading_range = TradingRange(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1D",
            range_low=Decimal("148.00"),
            range_high=Decimal("156.00"),
            start_timestamp=datetime.now(UTC),
            status="ACTIVE",
        )
        db_session.add(trading_range)

        # Create campaign for user 1
        campaign_user1 = CampaignModel(
            id=uuid4(),
            user_id=test_user_id,  # User 1's campaign
            symbol="AAPL",
            timeframe="1D",
            trading_range_id=trading_range.id,
            status="ACTIVE",
            total_allocation=Decimal("10000.00"),
            current_risk=Decimal("3000.00"),
            created_at=datetime.now(UTC),
        )
        db_session.add(campaign_user1)

        # Create campaign for user 2
        campaign_user2 = CampaignModel(
            id=uuid4(),
            user_id=test_user_id_2,  # User 2's campaign
            symbol="MSFT",
            timeframe="1D",
            trading_range_id=trading_range.id,
            status="ACTIVE",
            total_allocation=Decimal("10000.00"),
            current_risk=Decimal("3000.00"),
            created_at=datetime.now(UTC),
        )
        db_session.add(campaign_user2)
        await db_session.commit()

        # User 1 fetches campaigns (should only see AAPL, not MSFT)
        response = await async_client.get("/api/v1/campaigns", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        campaigns = data["data"]

        # Verify user 1 only sees their own campaign
        campaign_symbols = [c["symbol"] for c in campaigns]
        assert "AAPL" in campaign_symbols
        assert "MSFT" not in campaign_symbols  # Should NOT see user 2's campaign


@pytest.mark.asyncio
class TestCampaignTrackerAPIPagination:
    """Test pagination (CODE-003)."""

    async def test_pagination_default_limit(self, async_client: AsyncClient, auth_headers: dict):
        """Test default pagination limit of 50."""
        response = await async_client.get("/api/v1/campaigns", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["limit"] == 50
        assert data["pagination"]["offset"] == 0

    async def test_pagination_custom_limit(self, async_client: AsyncClient, auth_headers: dict):
        """Test custom pagination limit."""
        response = await async_client.get(
            "/api/v1/campaigns?limit=20&offset=10", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["limit"] == 20
        assert data["pagination"]["offset"] == 10

    async def test_pagination_max_limit_enforced(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test max limit of 100 is enforced."""
        response = await async_client.get("/api/v1/campaigns?limit=150", headers=auth_headers)

        # Should reject limit > 100
        assert response.status_code == 422  # Validation error

    async def test_pagination_has_more_flag(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_user_id: UUID,
        db_session,
    ):
        """Test has_more flag is set correctly."""
        # Create 60 campaigns for user (more than default page size of 50)
        trading_range = TradingRange(
            id=uuid4(),
            symbol="TEST",
            timeframe="1D",
            range_low=Decimal("100.00"),
            range_high=Decimal("110.00"),
            start_timestamp=datetime.now(UTC),
            status="ACTIVE",
        )
        db_session.add(trading_range)

        for i in range(60):
            campaign = CampaignModel(
                id=uuid4(),
                user_id=test_user_id,
                symbol=f"TICK{i}",
                timeframe="1D",
                trading_range_id=trading_range.id,
                status="ACTIVE",
                total_allocation=Decimal("1000.00"),
                current_risk=Decimal("300.00"),
                created_at=datetime.now(UTC),
            )
            db_session.add(campaign)
        await db_session.commit()

        # First page
        response = await async_client.get(
            "/api/v1/campaigns?limit=50&offset=0", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["returned_count"] == 50
        assert data["pagination"]["total_count"] == 60
        assert data["pagination"]["has_more"] is True  # More records available

        # Second page
        response = await async_client.get(
            "/api/v1/campaigns?limit=50&offset=50", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["returned_count"] == 10
        assert data["pagination"]["has_more"] is False  # No more records


@pytest.mark.asyncio
class TestCampaignTrackerAPIFiltering:
    """Test filtering with authentication."""

    async def test_filter_by_status_with_auth(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_user_id: UUID,
        db_session,
    ):
        """Test filtering campaigns by status with authentication."""
        trading_range = TradingRange(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1D",
            range_low=Decimal("148.00"),
            range_high=Decimal("156.00"),
            start_timestamp=datetime.now(UTC),
            status="ACTIVE",
        )
        db_session.add(trading_range)

        # Create ACTIVE campaign
        active_campaign = CampaignModel(
            id=uuid4(),
            user_id=test_user_id,
            symbol="AAPL",
            timeframe="1D",
            trading_range_id=trading_range.id,
            status="ACTIVE",
            total_allocation=Decimal("10000.00"),
            current_risk=Decimal("3000.00"),
            created_at=datetime.now(UTC),
        )
        db_session.add(active_campaign)

        # Create COMPLETED campaign
        completed_campaign = CampaignModel(
            id=uuid4(),
            user_id=test_user_id,
            symbol="MSFT",
            timeframe="1D",
            trading_range_id=trading_range.id,
            status="COMPLETED",
            total_allocation=Decimal("10000.00"),
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

        # All returned campaigns should be ACTIVE
        for campaign in campaigns:
            assert campaign["status"] == "ACTIVE"

    async def test_filter_by_symbol_with_auth(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_user_id: UUID,
        db_session,
    ):
        """Test filtering campaigns by symbol with authentication."""
        trading_range = TradingRange(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1D",
            range_low=Decimal("148.00"),
            range_high=Decimal("156.00"),
            start_timestamp=datetime.now(UTC),
            status="ACTIVE",
        )
        db_session.add(trading_range)

        # Create AAPL campaign
        campaign_aapl = CampaignModel(
            id=uuid4(),
            user_id=test_user_id,
            symbol="AAPL",
            timeframe="1D",
            trading_range_id=trading_range.id,
            status="ACTIVE",
            total_allocation=Decimal("10000.00"),
            current_risk=Decimal("3000.00"),
            created_at=datetime.now(UTC),
        )
        db_session.add(campaign_aapl)

        # Create MSFT campaign
        campaign_msft = CampaignModel(
            id=uuid4(),
            user_id=test_user_id,
            symbol="MSFT",
            timeframe="1D",
            trading_range_id=trading_range.id,
            status="ACTIVE",
            total_allocation=Decimal("10000.00"),
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

        # All returned campaigns should have AAPL symbol
        for campaign in campaigns:
            assert campaign["symbol"] == "AAPL"


@pytest.mark.asyncio
class TestCampaignTrackerAPIResponseStructure:
    """Test response structure with all QA fixes applied."""

    async def test_campaign_response_has_all_required_fields(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_user_id: UUID,
        db_session,
    ):
        """Test campaign response includes all required fields."""
        # Create trading range
        trading_range = TradingRange(
            id=uuid4(),
            symbol="AAPL",
            timeframe="1D",
            range_low=Decimal("148.00"),
            range_high=Decimal("156.00"),
            start_timestamp=datetime.now(UTC),
            status="ACTIVE",
        )
        db_session.add(trading_range)

        # Create campaign with position
        campaign = CampaignModel(
            id=uuid4(),
            user_id=test_user_id,
            symbol="AAPL",
            timeframe="1D",
            trading_range_id=trading_range.id,
            status="ACTIVE",
            total_allocation=Decimal("10000.00"),
            current_risk=Decimal("3000.00"),
            created_at=datetime.now(UTC),
        )
        db_session.add(campaign)

        position = PositionModel(
            id=uuid4(),
            campaign_id=campaign.id,
            signal_id=uuid4(),
            entry_pattern="SPRING",
            entry_price=Decimal("150.00"),
            shares=20,
            position_size=Decimal("3000.00"),
            stop_loss=Decimal("148.50"),
            status="FILLED",
            created_at=datetime.now(UTC),
        )
        db_session.add(position)
        await db_session.commit()

        response = await async_client.get("/api/v1/campaigns", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify pagination structure
        assert "pagination" in data
        pagination = data["pagination"]
        assert "returned_count" in pagination
        assert "total_count" in pagination
        assert "limit" in pagination
        assert "offset" in pagination
        assert "has_more" in pagination

        # Verify campaign structure
        assert "data" in data
        if len(data["data"]) > 0:
            campaign_data = data["data"][0]

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
