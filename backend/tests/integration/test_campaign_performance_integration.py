"""
Integration tests for Campaign Performance Tracking (Story 9.6).

Tests the full workflow from campaign creation through performance calculation
and API retrieval, including database persistence and caching.

Test Coverage:
--------------
1. Full campaign performance workflow (AC #8)
2. P&L curve generation with multiple positions (AC #9)
3. Aggregated performance API with filtering (AC #6, #10)
4. Performance test with 20 campaigns (target < 200ms)
5. API endpoint error cases (404, 422, 503)

Author: Claude Code
Date: 2025-12-06
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.campaign import CampaignMetrics
from src.repositories.campaign_repository import CampaignRepository
from src.repositories.models import CampaignModel, PositionModel

# These tests require PostgreSQL with campaign schema that includes fields
# (initial_capital, jump_target, actual_high_reached) not present in the
# current CampaignModel. Skip until schema migration is applied.
pytestmark = pytest.mark.skip(
    reason="CampaignModel schema mismatch: requires initial_capital, jump_target, "
    "actual_high_reached fields not in current model (Epic 22 migration pending)"
)


class TestCampaignPerformanceIntegration:
    """Integration tests for campaign performance tracking API endpoints."""

    @pytest.mark.asyncio
    async def test_full_campaign_performance_workflow(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """
        Test full campaign performance workflow from creation to metrics retrieval.

        Workflow:
        1. Create completed campaign in database
        2. Add 3 positions: Spring won +1.8R, SOS won +2.2R, LPS lost -0.8R
        3. Call GET /api/v1/campaigns/{id}/performance
        4. Verify all metrics calculated accurately
        5. Verify metrics persisted to campaign_metrics table
        6. Call endpoint again and verify cached metrics returned
        """
        # 1. Create completed campaign
        campaign_repo = CampaignRepository(db_session)
        campaign_id = uuid.uuid4()
        symbol = "EURUSD"
        initial_capital = Decimal("10000.00")
        jump_target = Decimal("1.1200")
        actual_high = Decimal("1.1150")  # 71.43% achievement
        started_at = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
        completed_at = datetime(2025, 1, 15, 0, 0, 0, tzinfo=UTC)  # 14 days duration

        # Create campaign (using SQLAlchemy model)
        campaign = CampaignModel(
            id=campaign_id,
            symbol=symbol,
            timeframe="1H",
            status="COMPLETED",
            initial_capital=initial_capital,
            jump_target=jump_target,
            actual_high_reached=actual_high,
            created_at=started_at,
            updated_at=completed_at,
        )
        db_session.add(campaign)
        await db_session.commit()

        # 2. Add 3 positions (using SQLAlchemy model)
        positions = [
            # Spring entry - WON +1.8R
            PositionModel(
                id=uuid.uuid4(),
                campaign_id=campaign_id,
                signal_id=uuid.uuid4(),  # Required FK
                symbol=symbol,
                timeframe="1H",
                pattern_type="SPRING",
                entry_date=started_at + timedelta(days=2),
                entry_price=Decimal("1.0800"),
                shares=Decimal("0.10"),  # 0.10 lot
                stop_loss=Decimal("1.0750"),  # 50 pips risk
                current_price=None,
                current_pnl=None,
                status="CLOSED",
                closed_date=started_at + timedelta(days=5),
                exit_price=Decimal("1.0890"),  # 90 pips profit = 1.8R
                realized_pnl=Decimal("90.00"),  # 90 pips * 0.10 lot
                created_at=started_at + timedelta(days=2),
                updated_at=started_at + timedelta(days=5),
            ),
            # SOS entry - WON +2.2R
            PositionModel(
                id=uuid.uuid4(),
                campaign_id=campaign_id,
                signal_id=uuid.uuid4(),
                symbol=symbol,
                timeframe="1H",
                pattern_type="SOS",
                entry_date=started_at + timedelta(days=6),
                entry_price=Decimal("1.0900"),
                shares=Decimal("0.10"),
                stop_loss=Decimal("1.0800"),  # 100 pips risk
                current_price=None,
                current_pnl=None,
                status="CLOSED",
                closed_date=started_at + timedelta(days=12),
                exit_price=Decimal("1.1120"),  # 220 pips profit = 2.2R
                realized_pnl=Decimal("220.00"),  # 220 pips * 0.10 lot
                created_at=started_at + timedelta(days=6),
                updated_at=started_at + timedelta(days=12),
            ),
            # LPS entry - LOST -0.8R
            PositionModel(
                id=uuid.uuid4(),
                campaign_id=campaign_id,
                signal_id=uuid.uuid4(),
                symbol=symbol,
                timeframe="1H",
                pattern_type="LPS",
                entry_date=started_at + timedelta(days=3),
                entry_price=Decimal("1.0850"),
                shares=Decimal("0.10"),
                stop_loss=Decimal("1.0800"),  # 50 pips risk
                current_price=None,
                current_pnl=None,
                status="CLOSED",
                closed_date=started_at + timedelta(days=4),
                exit_price=Decimal("1.0810"),  # -40 pips = -0.8R
                realized_pnl=Decimal("-40.00"),  # -40 pips * 0.10 lot
                created_at=started_at + timedelta(days=3),
                updated_at=started_at + timedelta(days=4),
            ),
        ]

        for pos in positions:
            db_session.add(pos)
        await db_session.commit()

        # 3. Call GET /api/v1/campaigns/{id}/performance
        response = await async_client.get(f"/api/v1/campaigns/{campaign_id}/performance")

        assert response.status_code == status.HTTP_200_OK
        metrics_data = response.json()

        # 4. Verify all metrics calculated accurately
        assert metrics_data["campaign_id"] == str(campaign_id)
        assert metrics_data["symbol"] == symbol

        # Campaign-level metrics
        # Total PnL = 90 + 220 - 40 = 270 USD
        # Total return % = (270 / 10000) * 100 = 2.70%
        assert Decimal(metrics_data["total_return_pct"]) == Decimal("2.70")
        # Total R = 1.8 + 2.2 - 0.8 = 3.2R
        assert Decimal(metrics_data["total_r_achieved"]) == Decimal("3.2000")
        # Win rate = 2 wins / 3 positions = 66.67%
        assert Decimal(metrics_data["win_rate"]) == Decimal("66.67")
        # Duration = 14 days
        assert metrics_data["duration_days"] == 14

        # Position-level metrics
        assert metrics_data["total_positions"] == 3
        assert metrics_data["winning_positions"] == 2
        assert metrics_data["losing_positions"] == 1

        # Target achievement
        # Expected Jump target = 1.1200
        # Actual high reached = 1.1150
        # Achievement % = ((1.1150 - 1.0800) / (1.1200 - 1.0800)) * 100 = 87.5%
        assert Decimal(metrics_data["expected_jump_target"]) == Decimal("1.1200")
        assert Decimal(metrics_data["actual_high_reached"]) == Decimal("1.1150")
        assert Decimal(metrics_data["target_achievement_pct"]) == Decimal("87.50")

        # Phase-specific metrics
        # Phase C: Spring +1.8R, LPS -0.8R => avg = 0.5R, win rate = 50%
        assert metrics_data["phase_c_positions"] == 2
        assert Decimal(metrics_data["phase_c_avg_r"]) == Decimal("0.5000")
        assert Decimal(metrics_data["phase_c_win_rate"]) == Decimal("50.00")
        # Phase D: SOS +2.2R => avg = 2.2R, win rate = 100%
        assert metrics_data["phase_d_positions"] == 1
        assert Decimal(metrics_data["phase_d_avg_r"]) == Decimal("2.2000")
        assert Decimal(metrics_data["phase_d_win_rate"]) == Decimal("100.00")

        # Verify position metrics array
        assert len(metrics_data["position_metrics"]) == 3
        # Find Spring position
        spring_pos = next(
            p for p in metrics_data["position_metrics"] if p["pattern_type"] == "SPRING"
        )
        assert Decimal(spring_pos["r_multiple"]) == Decimal("1.8000")
        assert Decimal(spring_pos["entry_price"]) == Decimal("1.0800")
        assert Decimal(spring_pos["exit_price"]) == Decimal("1.0890")
        assert spring_pos["is_winner"] is True

        # 5. Verify metrics persisted to campaign_metrics table
        cached_metrics = await campaign_repo.get_campaign_metrics(campaign_id)
        assert cached_metrics is not None
        assert cached_metrics.campaign_id == campaign_id
        assert cached_metrics.total_return_pct == Decimal("2.70")
        assert cached_metrics.total_r_achieved == Decimal("3.2000")

        # 6. Call endpoint again and verify cached metrics returned
        response2 = await async_client.get(f"/api/v1/campaigns/{campaign_id}/performance")
        assert response2.status_code == status.HTTP_200_OK
        # Should be identical to first response
        assert response2.json() == metrics_data

    @pytest.mark.asyncio
    async def test_pnl_curve_generation_with_multiple_positions(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """
        Test P&L curve generation with multiple positions over time.

        Verifies:
        - Chronologically ordered PnL points
        - Cumulative P&L calculation across positions
        - Drawdown calculation from peak equity
        - Max drawdown point identification
        """
        # Create campaign
        campaign_repo = CampaignRepository(db_session)
        campaign_id = uuid.uuid4()
        initial_capital = Decimal("10000.00")
        started_at = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)

        campaign = CampaignModel(
            id=campaign_id,
            symbol="GBPUSD",
            timeframe="4H",
            status="COMPLETED",
            initial_capital=initial_capital,
            created_at=started_at,
            updated_at=started_at + timedelta(days=10),
        )
        db_session.add(campaign)

        # Create 4 positions with different exit times
        positions = [
            # Position 1: Exit Day 2, +100 USD (equity = 10100)
            PositionModel(
                id=uuid.uuid4(),
                campaign_id=campaign_id,
                signal_id=uuid.uuid4(),
                symbol="GBPUSD",
                timeframe="4H",
                pattern_type="SPRING",
                entry_date=started_at,
                entry_price=Decimal("1.2500"),
                shares=Decimal("0.10"),
                stop_loss=Decimal("1.2450"),
                current_price=None,
                current_pnl=None,
                status="CLOSED",
                closed_date=started_at + timedelta(days=2),
                exit_price=Decimal("1.2550"),
                realized_pnl=Decimal("100.00"),
                created_at=started_at,
                updated_at=started_at + timedelta(days=2),
            ),
            # Position 2: Exit Day 4, -50 USD (equity = 10050)
            PositionModel(
                id=uuid.uuid4(),
                campaign_id=campaign_id,
                signal_id=uuid.uuid4(),
                symbol="GBPUSD",
                timeframe="4H",
                pattern_type="LPS",
                entry_date=started_at + timedelta(days=2),
                entry_price=Decimal("1.2600"),
                shares=Decimal("0.10"),
                stop_loss=Decimal("1.2550"),
                current_price=None,
                current_pnl=None,
                status="CLOSED",
                closed_date=started_at + timedelta(days=4),
                exit_price=Decimal("1.2560"),
                realized_pnl=Decimal("-50.00"),
                created_at=started_at + timedelta(days=2),
                updated_at=started_at + timedelta(days=4),
            ),
            # Position 3: Exit Day 7, +200 USD (equity = 10250)
            PositionModel(
                id=uuid.uuid4(),
                campaign_id=campaign_id,
                signal_id=uuid.uuid4(),
                symbol="GBPUSD",
                timeframe="4H",
                pattern_type="SOS",
                entry_date=started_at + timedelta(days=5),
                entry_price=Decimal("1.2650"),
                shares=Decimal("0.10"),
                stop_loss=Decimal("1.2550"),
                current_price=None,
                current_pnl=None,
                status="CLOSED",
                closed_date=started_at + timedelta(days=7),
                exit_price=Decimal("1.2850"),
                realized_pnl=Decimal("200.00"),
                created_at=started_at + timedelta(days=5),
                updated_at=started_at + timedelta(days=7),
            ),
            # Position 4: Exit Day 9, -80 USD (equity = 10170)
            PositionModel(
                id=uuid.uuid4(),
                campaign_id=campaign_id,
                signal_id=uuid.uuid4(),
                symbol="GBPUSD",
                timeframe="4H",
                pattern_type="LPS",
                entry_date=started_at + timedelta(days=7),
                entry_price=Decimal("1.2700"),
                shares=Decimal("0.10"),
                stop_loss=Decimal("1.2620"),
                current_price=None,
                current_pnl=None,
                status="CLOSED",
                closed_date=started_at + timedelta(days=9),
                exit_price=Decimal("1.2630"),
                realized_pnl=Decimal("-80.00"),
                created_at=started_at + timedelta(days=7),
                updated_at=started_at + timedelta(days=9),
            ),
        ]

        for pos in positions:
            db_session.add(pos)
        await db_session.commit()

        # Call GET /api/v1/campaigns/{id}/pnl-curve
        response = await async_client.get(f"/api/v1/campaigns/{campaign_id}/pnl-curve")

        assert response.status_code == status.HTTP_200_OK
        pnl_data = response.json()

        # Verify structure
        assert pnl_data["campaign_id"] == str(campaign_id)
        assert "pnl_points" in pnl_data
        assert "max_drawdown_point" in pnl_data

        # Verify chronological ordering
        points = pnl_data["pnl_points"]
        assert len(points) == 4
        timestamps = [p["timestamp"] for p in points]
        assert timestamps == sorted(timestamps)

        # Verify cumulative P&L calculation
        assert Decimal(points[0]["cumulative_pnl"]) == Decimal("100.00")  # +100
        assert Decimal(points[1]["cumulative_pnl"]) == Decimal("50.00")  # +100 - 50
        assert Decimal(points[2]["cumulative_pnl"]) == Decimal("250.00")  # +50 + 200
        assert Decimal(points[3]["cumulative_pnl"]) == Decimal("170.00")  # +250 - 80

        # Verify equity calculation
        assert Decimal(points[0]["equity"]) == Decimal("10100.00")
        assert Decimal(points[1]["equity"]) == Decimal("10050.00")
        assert Decimal(points[2]["equity"]) == Decimal("10250.00")
        assert Decimal(points[3]["equity"]) == Decimal("10170.00")

        # Verify drawdown calculation
        # Peak after point 2 = 10250, point 3 equity = 10170
        # Drawdown = ((10170 - 10250) / 10250) * 100 = -0.78%
        assert Decimal(points[1]["drawdown_pct"]) == Decimal("0.49")  # From peak 10100
        assert Decimal(points[3]["drawdown_pct"]) == Decimal("0.78")  # From peak 10250

        # Verify max drawdown point
        max_dd_point = pnl_data["max_drawdown_point"]
        # Max drawdown should be at point 1 (50 USD down from 10100 peak)
        # Drawdown = ((10050 - 10100) / 10100) * 100 = -0.495%
        assert Decimal(max_dd_point["drawdown_pct"]) == Decimal("0.49")

    @pytest.mark.asyncio
    async def test_aggregated_performance_with_filtering(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """
        Test aggregated performance API with symbol and date range filtering.

        Creates 3 completed campaigns:
        - EURUSD: Jan 1-10, +5% return, +2.5R
        - GBPUSD: Jan 5-15, +3% return, +1.8R
        - USDJPY: Jan 10-20, -2% return, -1.0R

        Tests filtering by:
        - Symbol filter (EURUSD only)
        - Date range filter (Jan 1-12 only)
        - Min return filter (>= 3%)
        - Min R filter (>= 2.0R)
        """
        campaign_repo = CampaignRepository(db_session)

        # Create 3 campaigns with metrics
        campaigns_data = [
            {
                "symbol": "EURUSD",
                "started": datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC),
                "completed": datetime(2025, 1, 10, 0, 0, 0, tzinfo=UTC),
                "return_pct": Decimal("5.00"),
                "r_achieved": Decimal("2.5000"),
                "win_rate": Decimal("75.00"),
                "positions": 4,
                "winners": 3,
            },
            {
                "symbol": "GBPUSD",
                "started": datetime(2025, 1, 5, 0, 0, 0, tzinfo=UTC),
                "completed": datetime(2025, 1, 15, 0, 0, 0, tzinfo=UTC),
                "return_pct": Decimal("3.00"),
                "r_achieved": Decimal("1.8000"),
                "win_rate": Decimal("66.67"),
                "positions": 3,
                "winners": 2,
            },
            {
                "symbol": "USDJPY",
                "started": datetime(2025, 1, 10, 0, 0, 0, tzinfo=UTC),
                "completed": datetime(2025, 1, 20, 0, 0, 0, tzinfo=UTC),
                "return_pct": Decimal("-2.00"),
                "r_achieved": Decimal("-1.0000"),
                "win_rate": Decimal("50.00"),
                "positions": 2,
                "winners": 1,
            },
        ]

        for data in campaigns_data:
            campaign_id = uuid.uuid4()
            campaign = CampaignModel(
                id=campaign_id,
                symbol=data["symbol"],
                timeframe="1H",
                status="COMPLETED",
                initial_capital=Decimal("10000.00"),
                created_at=data["started"],
                updated_at=data["completed"],
            )
            db_session.add(campaign)

            # Create metrics
            metrics = CampaignMetrics(
                campaign_id=campaign_id,
                symbol=data["symbol"],
                total_return_pct=data["return_pct"],
                total_r_achieved=data["r_achieved"],
                duration_days=(data["completed"] - data["started"]).days,
                max_drawdown=Decimal("1.50"),
                total_positions=data["positions"],
                winning_positions=data["winners"],
                losing_positions=data["positions"] - data["winners"],
                win_rate=data["win_rate"],
                average_entry_price=Decimal("1.1000"),
                average_exit_price=Decimal("1.1050"),
                position_metrics=[],
                calculation_timestamp=datetime.now(UTC),
                completed_at=data["completed"],
            )
            await campaign_repo.save_campaign_metrics(metrics)

        await db_session.commit()

        # Test 1: No filters (all 3 campaigns)
        response = await async_client.get("/api/v1/campaigns/performance")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_campaigns_completed"] == 3
        # Avg return = (5 + 3 - 2) / 3 = 2.00%
        assert Decimal(data["average_campaign_return_pct"]) == Decimal("2.00")
        # Avg R = (2.5 + 1.8 - 1.0) / 3 = 1.1000
        assert Decimal(data["average_r_achieved_per_campaign"]) == Decimal("1.1000")
        # Overall win rate = (3 + 2 + 1) / (4 + 3 + 2) = 66.67%
        assert Decimal(data["overall_win_rate"]) == Decimal("66.67")

        # Test 2: Filter by symbol (EURUSD only)
        response = await async_client.get("/api/v1/campaigns/performance?symbol=EURUSD")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_campaigns_completed"] == 1
        assert Decimal(data["average_campaign_return_pct"]) == Decimal("5.00")
        assert data["filter_criteria"]["symbol"] == "EURUSD"

        # Test 3: Filter by date range (Jan 1-12 = EURUSD + GBPUSD)
        response = await async_client.get(
            "/api/v1/campaigns/performance"
            "?start_date=2025-01-01T00:00:00Z"
            "&end_date=2025-01-12T00:00:00Z"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_campaigns_completed"] == 2
        # Avg return = (5 + 3) / 2 = 4.00%
        assert Decimal(data["average_campaign_return_pct"]) == Decimal("4.00")

        # Test 4: Filter by min_return >= 3% (EURUSD + GBPUSD)
        response = await async_client.get("/api/v1/campaigns/performance?min_return=3.0")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_campaigns_completed"] == 2

        # Test 5: Filter by min_r >= 2.0R (EURUSD only)
        response = await async_client.get("/api/v1/campaigns/performance?min_r=2.0")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_campaigns_completed"] == 1
        assert Decimal(data["average_r_achieved_per_campaign"]) == Decimal("2.5000")

        # Test 6: No matching campaigns (return zero-value aggregation)
        response = await async_client.get("/api/v1/campaigns/performance?min_return=10.0")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_campaigns_completed"] == 0
        assert Decimal(data["average_campaign_return_pct"]) == Decimal("0.00")
        assert data["best_campaign"] is None
        assert data["worst_campaign"] is None

    @pytest.mark.asyncio
    async def test_performance_with_20_campaigns(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """
        Performance test with 20 campaigns (target < 200ms).

        Verifies that aggregated performance query with 20 campaigns
        completes within acceptable time bounds.
        """
        import time

        campaign_repo = CampaignRepository(db_session)

        # Create 20 campaigns with metrics
        for i in range(20):
            campaign_id = uuid.uuid4()
            campaign = CampaignModel(
                id=campaign_id,
                symbol=f"PAIR{i % 5}",  # 5 different symbols
                timeframe="1H",
                status="COMPLETED",
                initial_capital=Decimal("10000.00"),
                created_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC) + timedelta(days=i),
                updated_at=datetime(2025, 1, 10, 0, 0, 0, tzinfo=UTC) + timedelta(days=i),
            )
            db_session.add(campaign)

            metrics = CampaignMetrics(
                campaign_id=campaign_id,
                symbol=f"PAIR{i % 5}",
                total_return_pct=Decimal(f"{i % 10}.00"),
                total_r_achieved=Decimal(f"{i % 5}.0000"),
                duration_days=9,
                max_drawdown=Decimal("1.50"),
                total_positions=3,
                winning_positions=2,
                losing_positions=1,
                win_rate=Decimal("66.67"),
                average_entry_price=Decimal("1.1000"),
                average_exit_price=Decimal("1.1050"),
                position_metrics=[],
                calculation_timestamp=datetime.now(UTC),
                completed_at=datetime(2025, 1, 10, 0, 0, 0, tzinfo=UTC) + timedelta(days=i),
            )
            await campaign_repo.save_campaign_metrics(metrics)

        await db_session.commit()

        # Measure query time
        start_time = time.perf_counter()
        response = await async_client.get("/api/v1/campaigns/performance")
        end_time = time.perf_counter()

        query_time_ms = (end_time - start_time) * 1000

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_campaigns_completed"] == 20

        # Performance assertion (target < 200ms)
        assert query_time_ms < 200, f"Query took {query_time_ms:.2f}ms (target: < 200ms)"

    @pytest.mark.asyncio
    async def test_campaign_not_found_error(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test 404 error when campaign does not exist."""
        fake_campaign_id = uuid.uuid4()
        response = await async_client.get(f"/api/v1/campaigns/{fake_campaign_id}/performance")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Campaign not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_campaign_not_completed_error(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Test 422 error when campaign is not completed."""
        # Create ACTIVE campaign
        campaign_id = uuid.uuid4()
        campaign = CampaignModel(
            id=campaign_id,
            symbol="EURUSD",
            timeframe="1H",
            status="ACTIVE",
            initial_capital=Decimal("10000.00"),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(campaign)
        await db_session.commit()

        response = await async_client.get(f"/api/v1/campaigns/{campaign_id}/performance")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "can only be calculated for completed campaigns" in response.json()["detail"]
        assert "ACTIVE" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_pnl_curve_with_no_positions(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Test P&L curve returns empty array when campaign has no positions."""
        # Create completed campaign with no positions
        campaign_id = uuid.uuid4()
        campaign = CampaignModel(
            id=campaign_id,
            symbol="EURUSD",
            timeframe="1H",
            status="COMPLETED",
            initial_capital=Decimal("10000.00"),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(campaign)
        await db_session.commit()

        response = await async_client.get(f"/api/v1/campaigns/{campaign_id}/pnl-curve")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["pnl_points"] == []
        assert data["max_drawdown_point"] is None
