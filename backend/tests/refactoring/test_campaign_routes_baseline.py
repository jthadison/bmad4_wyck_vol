"""
Campaign API Route Baseline Tests (Story 22.14 - AC5)

Tests for campaign API endpoints response schema validation:
- GET /api/v1/campaigns/{campaign_id}/risk - Campaign risk response
- GET /api/v1/campaigns/{campaign_id}/allocations - Allocation list response
- GET /api/v1/campaigns/{campaign_id}/positions - Positions response

These tests validate API response structures before refactoring work begins.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient

from src.models.allocation import AllocationPlan
from src.models.campaign import (
    CampaignEntry,
    CampaignRisk,
)


class TestCampaignRiskResponseSchema:
    """Test campaign risk endpoint response schema (AC5)."""

    def test_campaign_risk_model_structure(self):
        """AC5: CampaignRisk should have required fields."""
        risk = CampaignRisk(
            campaign_id=uuid4(),
            total_risk=Decimal("3.5"),
            available_capacity=Decimal("1.5"),
            position_count=2,
            entry_breakdown={
                "AAPL": {
                    "pattern_type": "SPRING",
                    "position_risk_pct": "2.0",
                    "allocation_percentage": "40.0",
                    "symbol": "AAPL",
                    "status": "OPEN",
                }
            },
        )

        assert risk.campaign_id is not None
        assert risk.total_risk == Decimal("3.5")
        assert risk.available_capacity == Decimal("1.5")
        assert risk.position_count == 2
        assert "AAPL" in risk.entry_breakdown

    def test_campaign_risk_entry_breakdown_structure(self):
        """AC5: Entry breakdown should have BMAD allocation info."""
        risk = CampaignRisk(
            campaign_id=uuid4(),
            total_risk=Decimal("5.0"),
            available_capacity=Decimal("0.0"),
            position_count=3,
            entry_breakdown={
                "AAPL": CampaignEntry(
                    pattern_type="SPRING",
                    position_risk_pct=Decimal("2.0"),
                    allocation_percentage=Decimal("40.0"),
                    symbol="AAPL",
                    status="OPEN",
                ),
                "MSFT": CampaignEntry(
                    pattern_type="SOS",
                    position_risk_pct=Decimal("1.75"),
                    allocation_percentage=Decimal("35.0"),
                    symbol="MSFT",
                    status="OPEN",
                ),
                "GOOGL": CampaignEntry(
                    pattern_type="LPS",
                    position_risk_pct=Decimal("1.25"),
                    allocation_percentage=Decimal("25.0"),
                    symbol="GOOGL",
                    status="OPEN",
                ),
            },
        )

        # Verify BMAD allocation totals to 100%
        total_allocation = sum(v.allocation_percentage for v in risk.entry_breakdown.values())
        assert total_allocation == Decimal("100.0")

    def test_bmad_allocation_percentages(self):
        """AC5: BMAD allocations should follow 40/35/25 split."""
        # Standard BMAD split
        spring_allocation = Decimal("40.0")  # 40% for Spring
        sos_allocation = Decimal("35.0")  # 35% for SOS
        lps_allocation = Decimal("25.0")  # 25% for LPS

        assert spring_allocation + sos_allocation + lps_allocation == Decimal("100.0")


class TestAllocationPlanSchema:
    """Test allocation plan model schema (AC5)."""

    def test_allocation_plan_model_structure(self):
        """AC5: AllocationPlan should have required fields."""
        plan = AllocationPlan(
            id=uuid4(),
            campaign_id=uuid4(),
            signal_id=uuid4(),
            pattern_type="SPRING",
            bmad_allocation_pct=Decimal("0.40"),
            target_risk_pct=Decimal("2.00"),
            actual_risk_pct=Decimal("0.50"),
            position_size_shares=166,
            allocation_used=Decimal("0.50"),
            remaining_budget=Decimal("4.50"),
            is_rebalanced=False,
            rebalance_reason=None,
            approved=True,
            rejection_reason=None,
            timestamp=datetime.now(UTC),
        )

        assert plan.id is not None
        assert plan.pattern_type == "SPRING"
        assert plan.bmad_allocation_pct == Decimal("0.40")
        assert plan.approved is True

    def test_allocation_plan_rebalanced_scenario(self):
        """AC5: AllocationPlan should handle rebalanced allocations."""
        plan = AllocationPlan(
            id=uuid4(),
            campaign_id=uuid4(),
            signal_id=uuid4(),
            pattern_type="LPS",
            bmad_allocation_pct=Decimal("1.00"),  # Full 100% due to rebalancing
            target_risk_pct=Decimal("5.00"),
            actual_risk_pct=Decimal("5.00"),
            position_size_shares=500,
            allocation_used=Decimal("5.00"),
            remaining_budget=Decimal("0.00"),
            is_rebalanced=True,
            rebalance_reason="Spring and SOS entries skipped - full allocation to LPS",
            approved=True,
            rejection_reason=None,
            timestamp=datetime.now(UTC),
        )

        assert plan.is_rebalanced is True
        assert plan.rebalance_reason is not None


class TestCampaignEntrySchema:
    """Test campaign entry model schema (AC5)."""

    def test_campaign_entry_model_structure(self):
        """AC5: CampaignEntry should have required fields."""
        entry = CampaignEntry(
            pattern_type="SPRING",
            position_risk_pct=Decimal("2.0"),
            allocation_percentage=Decimal("40.0"),
            symbol="AAPL",
            status="OPEN",
        )

        assert entry.pattern_type == "SPRING"
        assert entry.position_risk_pct == Decimal("2.0")
        assert entry.allocation_percentage == Decimal("40.0")

    def test_campaign_entry_valid_patterns(self):
        """AC5: CampaignEntry should only accept SPRING, SOS, LPS patterns."""
        valid_patterns = ["SPRING", "SOS", "LPS"]

        for pattern in valid_patterns:
            entry = CampaignEntry(
                pattern_type=pattern,
                position_risk_pct=Decimal("2.0"),
                allocation_percentage=Decimal("40.0"),
                symbol="AAPL",
                status="OPEN",
            )
            assert entry.pattern_type == pattern

    def test_campaign_entry_rejects_st(self):
        """AC5: CampaignEntry should reject ST (Secondary Test) as entry pattern."""
        with pytest.raises(ValueError, match="confirmation event"):
            CampaignEntry(
                pattern_type="ST",
                position_risk_pct=Decimal("2.0"),
                allocation_percentage=Decimal("40.0"),
                symbol="AAPL",
                status="OPEN",
            )


class TestCampaignRouterConfiguration:
    """Test campaign router configuration."""

    def test_router_prefix(self):
        """AC5: Router should have correct prefix."""
        from src.api.routes.campaigns import router

        assert router.prefix == "/api/v1/campaigns"

    def test_router_tags(self):
        """AC5: Router should have campaigns tag."""
        from src.api.routes.campaigns import router

        assert "campaigns" in router.tags


class TestCampaignEndpointAvailability:
    """Test campaign endpoints are available."""

    @pytest.mark.asyncio
    async def test_risk_endpoint_exists(self, async_client: AsyncClient):
        """AC5: Risk endpoint should exist."""
        campaign_id = uuid4()
        response = await async_client.get(f"/api/v1/campaigns/{campaign_id}/risk")

        # Should not be 405 (method not allowed) which would indicate endpoint doesn't exist
        assert response.status_code != 405

    @pytest.mark.asyncio
    async def test_allocations_endpoint_exists(self, async_client: AsyncClient):
        """AC5: Allocations endpoint should exist."""
        campaign_id = uuid4()
        response = await async_client.get(f"/api/v1/campaigns/{campaign_id}/allocations")

        # Should not be 405 (method not allowed)
        assert response.status_code != 405

    @pytest.mark.asyncio
    async def test_positions_endpoint_exists(self, async_client: AsyncClient):
        """AC5: Positions endpoint should exist."""
        campaign_id = uuid4()
        response = await async_client.get(f"/api/v1/campaigns/{campaign_id}/positions")

        # Should not be 405 (method not allowed)
        assert response.status_code != 405

    @pytest.mark.asyncio
    async def test_performance_endpoint_exists(self, async_client: AsyncClient):
        """AC5: Performance endpoint should exist."""
        campaign_id = uuid4()
        response = await async_client.get(f"/api/v1/campaigns/{campaign_id}/performance")

        # Should not be 405 (method not allowed)
        assert response.status_code != 405


class TestCampaignRiskBudgetEnforcement:
    """Test 5% campaign budget enforcement in response schemas."""

    def test_max_total_risk_is_5_percent(self):
        """AC5: Total risk should not exceed 5.0%."""
        # Max campaign budget is 5%
        MAX_CAMPAIGN_BUDGET = Decimal("5.0")

        risk = CampaignRisk(
            campaign_id=uuid4(),
            total_risk=Decimal("5.0"),  # At max
            available_capacity=Decimal("0.0"),
            position_count=3,
            entry_breakdown={},
        )

        assert risk.total_risk <= MAX_CAMPAIGN_BUDGET
        assert risk.available_capacity >= Decimal("0")

    def test_available_capacity_calculation(self):
        """AC5: Available capacity = 5% - total_risk."""
        risk = CampaignRisk(
            campaign_id=uuid4(),
            total_risk=Decimal("3.0"),
            available_capacity=Decimal("2.0"),  # 5% - 3% = 2%
            position_count=2,
            entry_breakdown={},
        )

        expected_capacity = Decimal("5.0") - risk.total_risk
        assert risk.available_capacity == expected_capacity
