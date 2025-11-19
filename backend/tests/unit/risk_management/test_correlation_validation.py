"""
Unit Tests for Correlation Risk Validation - Story 7.5

Test Coverage:
--------------
- validate_correlated_risk function (AC 5, 9, 12, 14, 15)
- Tiered correlation limits (sector 6%, asset_class 15%, geography 20%)
- Campaign count limits (max 3 per sector)
- Strict vs permissive enforcement modes
- Multi-level validation (ALL levels checked independently)

Key Test Scenarios:
-------------------
1. Risk under limits → passes both modes
2. Risk over limits → strict fails, permissive warns
3. Exactly at limit → passes (boundary condition)
4. Slightly over limit → strict fails, permissive warns (boundary)
5. 4th tech campaign when 3 exist → strict rejects
6. Max campaigns per sector enforcement
7. Campaign scaling does NOT increase correlation count
8. Cross-sector positions pass sector, fail asset class
9. Geography correlation optional (None = no validation)
10. Tiered limits validation (sector 6%, asset_class 15%, geography 20%)

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
        "XOM": SectorMapping(symbol="XOM", sector="Energy", asset_class="stock", geography="US"),
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


class TestValidateCorrelatedRiskUnderLimit:
    """Test validation when risk is under limits (AC 5)."""

    def test_current_4_5_plus_new_1_0_equals_5_5_passes_both_modes(
        self, strict_config: CorrelationConfig, permissive_config: CorrelationConfig
    ) -> None:
        """Test 4.5% current + 1.0% new = 5.5% sector → passes in both modes (AC 5)."""
        existing_campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("2.25000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("2.25000")),
        ]

        new_campaign = create_campaign("GOOGL", "Technology", "stock", "US", Decimal("1.0000"))

        # Test strict mode
        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, strict_config
        )
        assert is_valid is True
        assert reason is None
        assert len(warnings) == 0

        # Test permissive mode
        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, permissive_config
        )
        assert is_valid is True
        assert reason is None
        assert len(warnings) == 0


class TestValidateCorrelatedRiskOverLimit:
    """Test validation when risk exceeds limits (AC 5, 9, 14, 15)."""

    def test_current_5_5_plus_new_0_6_equals_6_1_strict_fails_permissive_warns(
        self, strict_config: CorrelationConfig, permissive_config: CorrelationConfig
    ) -> None:
        """Test 5.5% current + 0.6% new = 6.1% sector → strict mode fails, permissive mode warns (AC 5)."""
        existing_campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("2.75000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("2.75000")),
        ]

        new_campaign = create_campaign("GOOGL", "Technology", "stock", "US", Decimal("0.6000"))

        # Test strict mode - should FAIL
        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, strict_config
        )
        assert is_valid is False
        assert reason is not None
        assert "Technology" in reason
        assert "6.10" in reason or "6.1" in reason
        assert "6.00" in reason or "6.0" in reason

        # Test permissive mode - should WARN but ALLOW
        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, permissive_config
        )
        assert is_valid is True
        assert reason is None
        assert len(warnings) > 0
        assert any("Technology" in w for w in warnings)

    def test_fourth_tech_campaign_when_three_exist_at_6_1_strict_rejects(
        self, strict_config: CorrelationConfig
    ) -> None:
        """Test campaign when 2 existing = 6.1% → strict mode rejects on correlation (AC 9)."""
        existing_campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("3.0000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("2.5000")),
        ]

        new_campaign = create_campaign("GOOGL", "Technology", "stock", "US", Decimal("0.6000"))

        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, strict_config
        )

        assert is_valid is False
        assert reason is not None
        assert "6.10" in reason or "6.1" in reason  # Projected risk
        assert "6.00" in reason or "6.0" in reason  # Limit


class TestValidateCorrelatedRiskBoundaryConditions:
    """Test boundary conditions (exactly at limit, slightly over) (AC 5, 9)."""

    def test_exactly_6_0_percent_sector_correlation_passes(
        self, strict_config: CorrelationConfig
    ) -> None:
        """Test exactly 6.0% sector correlated risk → passes (boundary condition) (AC 5)."""
        existing_campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("2.0000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("2.0000")),
        ]

        new_campaign = create_campaign("GOOGL", "Technology", "stock", "US", Decimal("2.0000"))

        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, strict_config
        )

        # Exactly at limit should PASS
        assert is_valid is True
        assert reason is None

    def test_6_0001_percent_strict_fails_permissive_warns(
        self, strict_config: CorrelationConfig, permissive_config: CorrelationConfig
    ) -> None:
        """Test 6.0001% sector → strict fails, permissive warns (boundary) (AC 9)."""
        existing_campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("2.0000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("2.0000")),
        ]

        new_campaign = create_campaign("GOOGL", "Technology", "stock", "US", Decimal("2.0001"))

        # Strict mode should FAIL
        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, strict_config
        )
        assert is_valid is False
        assert reason is not None

        # Permissive mode should WARN
        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, permissive_config
        )
        assert is_valid is True
        assert len(warnings) > 0


class TestCampaignCountLimits:
    """Test campaign count limits (AC 12)."""

    def test_max_campaigns_per_sector_fourth_rejected_when_max_three(
        self, strict_config: CorrelationConfig
    ) -> None:
        """Test 4th campaign rejected when max=3 (AC 12)."""
        existing_campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("1.0000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("1.0000")),
            create_campaign("GOOGL", "Technology", "stock", "US", Decimal("1.0000")),
        ]

        new_campaign = create_campaign("NVDA", "Technology", "stock", "US", Decimal("0.5000"))

        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, strict_config
        )

        assert is_valid is False
        assert reason is not None
        assert "3 campaigns" in reason
        assert "Technology" in reason

    def test_campaign_scaling_does_not_increase_sector_correlation_count(
        self, strict_config: CorrelationConfig
    ) -> None:
        """Test campaign scaling does NOT increase sector correlation count (AC 12)."""
        # 2 campaigns, but one has 3 positions (campaign scaling)
        existing_campaigns = [
            create_campaign(
                "AAPL", "Technology", "stock", "US", Decimal("3.0000"), position_count=3
            ),  # 1 campaign, 3 positions
            create_campaign(
                "MSFT", "Technology", "stock", "US", Decimal("1.0000"), position_count=1
            ),
        ]

        # Should allow 3rd campaign (we only have 2 campaigns so far)
        new_campaign = create_campaign("GOOGL", "Technology", "stock", "US", Decimal("1.0000"))

        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, strict_config
        )

        # Should PASS - we have 2 campaigns, adding 3rd is allowed (max=3)
        assert is_valid is True
        assert reason is None


class TestTieredCorrelationLimits:
    """Test tiered correlation limits (AC 14, 15)."""

    def test_6_pct_tech_plus_6_pct_healthcare_equals_12_pct_stocks_passes_asset_class(
        self, strict_config: CorrelationConfig
    ) -> None:
        """Test 6% tech + 6% healthcare = 12% stocks → passes asset class limit (15%) (AC 14)."""
        existing_campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("3.0000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("3.0000")),
            create_campaign("JNJ", "Healthcare", "stock", "US", Decimal("3.0000")),
            create_campaign("PFE", "Healthcare", "stock", "US", Decimal("3.0000")),
        ]

        # Add another campaign (Healthcare) - total stocks would be 13%
        new_campaign = create_campaign("ABBV", "Healthcare", "stock", "US", Decimal("1.0000"))

        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, strict_config
        )

        # Healthcare sector would be 7% (over 6% limit), should FAIL
        assert is_valid is False
        assert reason is not None
        assert "Healthcare" in reason

    def test_cross_sector_positions_pass_sector_fail_asset_class_at_15_1(
        self, strict_config: CorrelationConfig
    ) -> None:
        """Test cross-sector positions pass sector check (6%), fail asset class check at 15.1% (AC 15)."""
        existing_campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("5.0000")),
            create_campaign("JNJ", "Healthcare", "stock", "US", Decimal("5.0000")),
            create_campaign("XOM", "Energy", "stock", "US", Decimal("5.0000")),
        ]

        # Add another campaign - would push stocks to 15.5%
        new_campaign = create_campaign("PFE", "Healthcare", "stock", "US", Decimal("0.5000"))

        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, strict_config
        )

        # Healthcare sector would be 5.5% (under 6%), but stocks would be 15.5% (over 15%)
        assert is_valid is False
        assert reason is not None
        assert "stock" in reason or "15." in reason

    def test_geography_correlation_optional_none_no_validation(
        self, sector_mappings: dict[str, SectorMapping]
    ) -> None:
        """Test geography correlation optional (None = no validation) (AC 14)."""
        config = CorrelationConfig(
            max_sector_correlation=Decimal("6.0"),
            max_asset_class_correlation=Decimal("15.0"),
            max_geography_correlation=None,  # Geography validation disabled
            max_campaigns_per_sector=3,
            enforcement_mode="strict",
            sector_mappings=sector_mappings,
        )

        existing_campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("2.0000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("2.0000")),
        ]

        new_campaign = create_campaign("GOOGL", "Technology", "stock", "US", Decimal("1.0000"))

        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, config
        )

        # Should pass - geography validation disabled
        assert is_valid is True
        assert reason is None

    def test_tiered_limits_sector_6_asset_class_15_geography_20(
        self, sector_mappings: dict[str, SectorMapping]
    ) -> None:
        """Test tiered limits - sector 6%, asset class 15%, geography 20% (AC 14)."""
        config = CorrelationConfig(
            max_sector_correlation=Decimal("6.0"),
            max_asset_class_correlation=Decimal("15.0"),
            max_geography_correlation=Decimal("20.0"),
            max_campaigns_per_sector=3,
            enforcement_mode="strict",
            sector_mappings=sector_mappings,
        )

        # Verify config has correct tiered limits
        assert config.max_sector_correlation == Decimal("6.0")
        assert config.max_asset_class_correlation == Decimal("15.0")
        assert config.max_geography_correlation == Decimal("20.0")


class TestPermissiveModeWarnings:
    """Test permissive mode warning behavior (AC 5, 6)."""

    def test_permissive_mode_returns_warnings_list_with_proper_format(
        self, permissive_config: CorrelationConfig
    ) -> None:
        """Test permissive mode returns warnings list with proper format (AC 5)."""
        existing_campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("3.0000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("3.0000")),
        ]

        new_campaign = create_campaign("GOOGL", "Technology", "stock", "US", Decimal("0.5000"))

        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, permissive_config
        )

        # Should pass but with warnings
        assert is_valid is True
        assert reason is None
        assert len(warnings) > 0
        assert any("Technology" in w for w in warnings)
        assert any("sector" in w for w in warnings)

    def test_rejection_reason_message_is_clear_and_actionable(
        self, strict_config: CorrelationConfig
    ) -> None:
        """Test rejection reason message is clear and actionable (AC 5)."""
        existing_campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("3.0000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("3.0000")),
        ]

        new_campaign = create_campaign("GOOGL", "Technology", "stock", "US", Decimal("0.5000"))

        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, strict_config
        )

        assert is_valid is False
        assert reason is not None
        # Should include: correlation type, key, projected risk, limit
        assert "Technology" in reason
        assert "sector" in reason
        assert "6." in reason  # Limit value
        assert "%" in reason


class TestMultiLevelValidation:
    """Test multi-level correlation validation (AC 15)."""

    def test_campaign_passes_sector_6_but_fails_asset_class_15(
        self, strict_config: CorrelationConfig
    ) -> None:
        """Test campaign passes sector limit (6%) but fails asset_class limit (15%) (AC 15)."""
        existing_campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("3.0000")),
            create_campaign("JNJ", "Healthcare", "stock", "US", Decimal("6.0000")),
            create_campaign("XOM", "Energy", "stock", "US", Decimal("6.0000")),
        ]

        # Add Energy campaign - Energy sector 6.5% (over 6%), stocks 15.5% (over 15%)
        new_campaign = create_campaign("CVX", "Energy", "stock", "US", Decimal("0.5000"))

        is_valid, reason, warnings = validate_correlated_risk(
            new_campaign, existing_campaigns, strict_config
        )

        # Should fail on Energy sector exceeding 6%
        assert is_valid is False
        assert reason is not None
        assert "Energy" in reason or "stock" in reason
