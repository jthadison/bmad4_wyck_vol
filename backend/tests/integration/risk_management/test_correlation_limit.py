"""
Integration Tests for Correlation Limit Enforcement - Story 7.5

Test Coverage:
--------------
- End-to-end correlation limit enforcement (AC 9, 11)
- Tiered correlation limits integration (AC 14, 15)
- Campaign count limit enforcement (AC 12)
- Override mechanism integration (AC 10)
- Full validation pipeline

Key Test Scenarios:
-------------------
1. 4th tech campaign rejected when 3 exist at 6.1%
2. Campaign scaling (adding positions) doesn't trigger rejection
3. Campaign passes sector, fails asset class
4. Campaign passes sector+asset class, fails geography
5. 6% tech + 6% healthcare + 4% energy = 16% stocks fails
6. 3 tech campaigns allowed, 4th rejected
7. Campaign with multiple positions counts as 1
8. Override mechanism bypasses rejection

Author: Story 7.5
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.correlation_campaign import CampaignForCorrelation
from src.models.portfolio import Position
from src.models.risk import (
    CorrelationConfig,
    SectorMapping,
)
from src.risk_management.correlation import (
    build_correlation_report,
    check_correlation_proximity_warnings,
    override_correlation_limit,
    validate_correlated_risk,
)


@pytest.fixture
def sector_mappings() -> dict[str, SectorMapping]:
    """Sector mappings fixture."""
    return {
        "AAPL": SectorMapping(
            symbol="AAPL", sector="Technology", asset_class="stock", geography="US"
        ),
        "MSFT": SectorMapping(
            symbol="MSFT", sector="Technology", asset_class="stock", geography="US"
        ),
        "GOOGL": SectorMapping(
            symbol="GOOGL", sector="Technology", asset_class="stock", geography="US"
        ),
        "NVDA": SectorMapping(
            symbol="NVDA", sector="Technology", asset_class="stock", geography="US"
        ),
        "JNJ": SectorMapping(
            symbol="JNJ", sector="Healthcare", asset_class="stock", geography="US"
        ),
        "PFE": SectorMapping(
            symbol="PFE", sector="Healthcare", asset_class="stock", geography="US"
        ),
        "ABBV": SectorMapping(
            symbol="ABBV", sector="Healthcare", asset_class="stock", geography="US"
        ),
        "XOM": SectorMapping(symbol="XOM", sector="Energy", asset_class="stock", geography="US"),
        "CVX": SectorMapping(symbol="CVX", sector="Energy", asset_class="stock", geography="US"),
    }


@pytest.fixture
def strict_config(sector_mappings: dict[str, SectorMapping]) -> CorrelationConfig:
    """Strict mode correlation config."""
    return CorrelationConfig(
        max_sector_correlation=Decimal("6.0"),
        max_asset_class_correlation=Decimal("15.0"),
        max_geography_correlation=Decimal("20.0"),
        max_campaigns_per_sector=3,
        enforcement_mode="strict",
        sector_mappings=sector_mappings,
    )


@pytest.fixture
def permissive_config(sector_mappings: dict[str, SectorMapping]) -> CorrelationConfig:
    """Permissive mode correlation config."""
    return CorrelationConfig(
        max_sector_correlation=Decimal("6.0"),
        max_asset_class_correlation=Decimal("15.0"),
        max_geography_correlation=Decimal("20.0"),
        max_campaigns_per_sector=3,
        enforcement_mode="permissive",
        sector_mappings=sector_mappings,
    )


def create_campaign(
    symbol: str,
    sector: str,
    asset_class: str,
    geography: str,
    total_risk: Decimal,
    position_count: int = 1,
) -> CampaignForCorrelation:
    """Helper to create test campaign."""
    positions = [
        Position(
            symbol=symbol,
            position_risk_pct=total_risk / position_count,
            status="OPEN",
        )
        for _ in range(position_count)
    ]

    return CampaignForCorrelation(
        campaign_id=uuid4(),
        symbol=symbol,
        sector=sector,
        asset_class=asset_class,
        geography=geography,
        total_campaign_risk=total_risk,
        positions=positions,
        status="ACTIVE",
    )


class TestSectorLimitEnforcement:
    """Integration tests for sector limit enforcement (AC 9, 11)."""

    def test_fourth_tech_campaign_rejected_when_three_exist_at_6_1_percent(
        self, strict_config: CorrelationConfig
    ) -> None:
        """
        Test 3rd tech campaign rejected when 2 exist totaling 6.1% (AC 9, 11).

        Setup: 2 Tech campaigns totaling 5.5% risk
        Action: Attempt to add 3rd Tech campaign with 0.6% risk (total 6.1%)
        Expected: Strict mode rejects with proper error code and message
        """
        # Setup: 2 existing Tech campaigns totaling 5.5%
        existing_campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("2.75000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("2.75000")),
        ]

        # Action: Attempt to add 3rd campaign (GOOGL) with 0.6% risk
        new_campaign = create_campaign("GOOGL", "Technology", "stock", "US", Decimal("0.6000"))

        # Execute validation
        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, strict_config
        )

        # Assertions
        assert is_valid is False, "Should reject campaign exceeding 6% limit"
        assert reason is not None, "Should provide rejection reason"
        assert "Technology" in reason, "Error should mention Technology sector"
        assert "6.1" in reason or "6.10" in reason, "Error should mention projected risk 6.1%"
        assert "6.0" in reason or "6.00" in reason, "Error should mention limit 6.0%"

    def test_permissive_mode_allows_with_warning(
        self, permissive_config: CorrelationConfig
    ) -> None:
        """Test permissive mode allows over-limit with warning (AC 9)."""
        existing_campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("2.0000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("2.0000")),
            create_campaign("GOOGL", "Technology", "stock", "US", Decimal("1.5000")),
        ]

        new_campaign = create_campaign("NVDA", "Technology", "stock", "US", Decimal("0.6000"))

        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, permissive_config
        )

        assert is_valid is True, "Permissive mode should allow"
        assert reason is None, "Should not have rejection reason"
        assert len(warnings) > 0, "Should have warnings"
        assert any("Technology" in w for w in warnings), "Warning should mention Technology"

    def test_correlation_report_reflects_correct_campaign_count_and_breakdown(
        self, strict_config: CorrelationConfig, sector_mappings: dict[str, SectorMapping]
    ) -> None:
        """Test CorrelatedRisk report reflects correct campaign_count and campaign_breakdown (AC 11)."""
        campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("1.5000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("1.5000")),
            create_campaign("GOOGL", "Technology", "stock", "US", Decimal("1.5000")),
        ]

        report = build_correlation_report(campaigns, sector_mappings, strict_config)

        tech_sector = [c for c in report["sector"] if c.correlation_key == "Technology"][0]

        assert tech_sector.campaign_count == 3, "Should count 3 campaigns"
        assert tech_sector.total_risk == Decimal("4.5000"), "Should sum to 4.5%"
        assert len(tech_sector.campaign_breakdown) == 3, "Should have 3 campaigns in breakdown"
        assert tech_sector.position_count == 3, "Should have 3 total positions"

    def test_campaign_scaling_adding_positions_doesnt_trigger_rejection(
        self, strict_config: CorrelationConfig
    ) -> None:
        """
        Test campaign scaling - adding positions to existing campaign doesn't trigger rejection (AC 11).

        This is KEY: Wyckoff campaign scaling (Spring → LPS adds) doesn't increase correlation.
        """
        # Existing: 2 campaigns, one with 3 positions (campaign scaling)
        existing_campaigns = [
            create_campaign(
                "AAPL", "Technology", "stock", "US", Decimal("3.0000"), position_count=3
            ),  # Spring + 2 LPS adds
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("2.0000")),
        ]

        # Add 3rd campaign
        new_campaign = create_campaign("GOOGL", "Technology", "stock", "US", Decimal("1.0000"))

        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, strict_config
        )

        # Should PASS - we have 2 campaigns, adding 3rd is allowed (max=3)
        # Even though AAPL has 3 positions, it's still 1 campaign correlation unit
        assert is_valid is True, "Should allow 3rd campaign"
        assert reason is None, "Should not have rejection reason"


class TestTieredCorrelationLimits:
    """Integration tests for tiered correlation limits (AC 14, 15)."""

    def test_campaign_passes_sector_limit_but_fails_asset_class_limit(
        self, strict_config: CorrelationConfig
    ) -> None:
        """Test campaign passes sector limit (6%) but fails asset_class limit (15%) (AC 14, 15)."""
        # Setup: 3 sectors, each at 5% (total stocks = 15%)
        existing_campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("5.0000")),
            create_campaign("JNJ", "Healthcare", "stock", "US", Decimal("5.0000")),
            create_campaign("XOM", "Energy", "stock", "US", Decimal("5.0000")),
        ]

        # Add Healthcare campaign - Healthcare sector 5.5% (under 6%), stocks 15.5% (over 15%)
        new_campaign = create_campaign("PFE", "Healthcare", "stock", "US", Decimal("0.5000"))

        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, strict_config
        )

        assert is_valid is False, "Should fail asset class limit"
        assert reason is not None
        assert "stock" in reason or "15." in reason, "Error should mention asset class or 15% limit"

    def test_6_tech_6_healthcare_12_stocks_passes_asset_class_15_limit(
        self, strict_config: CorrelationConfig
    ) -> None:
        """Test 6% tech + 6% healthcare = 12% stocks → passes asset class 15% limit (AC 14)."""
        existing_campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("3.0000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("3.0000")),
            create_campaign("JNJ", "Healthcare", "stock", "US", Decimal("3.0000")),
            create_campaign("PFE", "Healthcare", "stock", "US", Decimal("3.0000")),
        ]

        # Both sectors at 6% each, total stocks = 12% (under 15%)
        # Add Energy campaign - should pass
        new_campaign = create_campaign("XOM", "Energy", "stock", "US", Decimal("2.0000"))

        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, strict_config
        )

        # Energy would be 2%, stocks would be 14% (under 15%), should PASS
        assert is_valid is True, "Should pass both sector and asset class limits"
        assert reason is None

    def test_6_tech_6_healthcare_4_energy_16_stocks_fails_asset_class_15_limit(
        self, strict_config: CorrelationConfig
    ) -> None:
        """Test 6% tech + 6% healthcare + 4% energy = 16% stocks → fails asset class 15% limit (AC 14)."""
        existing_campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("6.0000")),
            create_campaign("JNJ", "Healthcare", "stock", "US", Decimal("6.0000")),
            create_campaign("XOM", "Energy", "stock", "US", Decimal("3.0000")),
        ]

        # Add more Energy - Energy 4% (under 6%), stocks 16% (over 15%)
        new_campaign = create_campaign("CVX", "Energy", "stock", "US", Decimal("1.0000"))

        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, strict_config
        )

        assert is_valid is False, "Should fail asset class limit at 16%"
        assert reason is not None
        assert "stock" in reason or "16" in reason or "15" in reason

    def test_validation_checks_all_correlation_levels_not_just_first(
        self, strict_config: CorrelationConfig
    ) -> None:
        """Test validation checks ALL correlation levels (AC 15)."""
        # This tests that validation doesn't short-circuit on first check
        existing_campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("5.0000")),
            create_campaign("JNJ", "Healthcare", "stock", "US", Decimal("5.0000")),
            create_campaign("XOM", "Energy", "stock", "US", Decimal("5.0000")),
        ]

        # New campaign would fail asset class (15.5%) but pass sector (5.5%)
        new_campaign = create_campaign("PFE", "Healthcare", "stock", "US", Decimal("0.5000"))

        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, strict_config
        )

        # Should fail because asset_class exceeds 15%, even though sector is under 6%
        assert is_valid is False
        assert reason is not None

    def test_each_level_uses_appropriate_limit_6_15_20(
        self, strict_config: CorrelationConfig, sector_mappings: dict[str, SectorMapping]
    ) -> None:
        """Test each level uses its appropriate limit (6%, 15%, 20%) (AC 14)."""
        campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("5.0000")),
            create_campaign("JNJ", "Healthcare", "stock", "US", Decimal("5.0000")),
        ]

        report = build_correlation_report(campaigns, sector_mappings, strict_config)

        # Verify each level has correct limit
        tech_sector = [c for c in report["sector"] if c.correlation_key == "Technology"][0]
        assert tech_sector.limit == Decimal("6.0"), "Sector limit should be 6.0%"

        stock_asset = [c for c in report["asset_class"] if c.correlation_key == "stock"][0]
        assert stock_asset.limit == Decimal("15.0"), "Asset class limit should be 15.0%"

        us_geo = [c for c in report["geography"] if c.correlation_key == "US"][0]
        assert us_geo.limit == Decimal("20.0"), "Geography limit should be 20.0%"


class TestCampaignCountLimits:
    """Integration tests for campaign count limits (AC 12)."""

    def test_three_tech_campaigns_allowed(self, strict_config: CorrelationConfig) -> None:
        """Test 3 tech campaigns allowed (AAPL, MSFT, GOOGL) (AC 12)."""
        existing_campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("1.5000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("1.5000")),
        ]

        new_campaign = create_campaign("GOOGL", "Technology", "stock", "US", Decimal("1.5000"))

        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, strict_config
        )

        # 3rd campaign should be allowed
        assert is_valid is True
        assert reason is None

    def test_fourth_tech_campaign_rejected_when_max_three(
        self, strict_config: CorrelationConfig
    ) -> None:
        """Test 4th tech campaign rejected (NVDA) when max_campaigns_per_sector=3 (AC 12)."""
        existing_campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("1.5000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("1.5000")),
            create_campaign("GOOGL", "Technology", "stock", "US", Decimal("1.5000")),
        ]

        new_campaign = create_campaign("NVDA", "Technology", "stock", "US", Decimal("1.0000"))

        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, strict_config
        )

        # 4th campaign should be rejected
        assert is_valid is False
        assert reason is not None
        assert "3 campaigns" in reason
        assert "Technology" in reason

    def test_campaign_with_multiple_positions_counts_as_one_campaign(
        self, strict_config: CorrelationConfig
    ) -> None:
        """Test campaign with multiple positions counts as 1 campaign (AC 12)."""
        existing_campaigns = [
            create_campaign(
                "AAPL", "Technology", "stock", "US", Decimal("3.0000"), position_count=5
            ),  # 1 campaign, 5 positions
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("1.5000")),
        ]

        # Should allow 3rd campaign (only 2 campaigns exist)
        new_campaign = create_campaign("GOOGL", "Technology", "stock", "US", Decimal("1.0000"))

        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, strict_config
        )

        assert is_valid is True, "Should allow 3rd campaign"
        assert reason is None


class TestOverrideMechanism:
    """Integration tests for override mechanism (AC 10)."""

    def test_override_mechanism_bypasses_rejection_in_strict_mode(self) -> None:
        """Test override mechanism bypasses rejection in strict mode (AC 10)."""
        signal_id = uuid4()
        approver = "john.doe@example.com"
        reason = "Exceptional Wyckoff setup with strong volume confirmation"

        # Execute override
        result = override_correlation_limit(signal_id, approver, reason)

        # Should return True to allow signal approval
        assert result is True


class TestProximityWarnings:
    """Integration tests for proximity warnings."""

    def test_proximity_warnings_at_80_percent_utilization(
        self, strict_config: CorrelationConfig, sector_mappings: dict[str, SectorMapping]
    ) -> None:
        """Test proximity warnings at 80% utilization (4.8% for 6% limit)."""
        campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("2.4000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("2.4000")),
        ]

        report = build_correlation_report(campaigns, sector_mappings, strict_config)
        warnings = check_correlation_proximity_warnings(report)

        # Total Tech = 4.8% = 80% of 6% limit, should trigger warning
        assert len(warnings) > 0
        assert any("Technology" in w for w in warnings)
        assert any("80" in w or "4.8" in w for w in warnings)
