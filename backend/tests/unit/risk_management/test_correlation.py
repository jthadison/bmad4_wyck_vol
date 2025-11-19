"""
Unit Tests for Correlation Risk Calculation - Story 7.5

Test Coverage:
--------------
- calculate_correlated_risk function (AC 8, 11)
- validate_sector_campaign_count function (AC 12)
- Campaign-level correlation tracking (not position-level)
- Multi-level correlation (sector vs asset_class vs geography)
- Decimal precision maintenance

Key Test Scenarios:
-------------------
1. Empty campaigns → 0% risk
2. Single campaign → campaign's total_risk
3. Multiple campaigns in same sector → sum of campaign risks
4. Campaign scaling (3 positions in 1 campaign) → 1 campaign correlation
5. Multi-sector campaigns → only same-sector sum
6. Unknown symbols → treated as separate groups
7. Multi-level correlation → different limits per level
8. Campaign count validation → max 3 per sector

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
    calculate_correlated_risk,
    validate_sector_campaign_count,
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
def correlation_config(sector_mappings: dict[str, SectorMapping]) -> CorrelationConfig:
    """Correlation config fixture."""
    return CorrelationConfig(
        max_sector_correlation=Decimal("6.0"),
        max_asset_class_correlation=Decimal("15.0"),
        max_geography_correlation=Decimal("20.0"),
        max_campaigns_per_sector=3,
        enforcement_mode="strict",
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


class TestCalculateCorrelatedRisk:
    """Test calculate_correlated_risk function (AC 8, 11)."""

    def test_empty_campaigns_returns_zero(self, sector_mappings: dict[str, SectorMapping]) -> None:
        """Test empty campaigns list returns 0% risk."""
        result = calculate_correlated_risk(
            correlation_key="Technology",
            correlation_type="sector",
            open_campaigns=[],
            sector_mappings=sector_mappings,
        )

        assert result == Decimal("0.0000")
        assert isinstance(result, Decimal)

    def test_single_campaign_returns_campaign_risk(
        self, sector_mappings: dict[str, SectorMapping]
    ) -> None:
        """Test single campaign returns that campaign's total_risk."""
        campaign = create_campaign(
            symbol="AAPL",
            sector="Technology",
            asset_class="stock",
            geography="US",
            total_risk=Decimal("1.5000"),
        )

        result = calculate_correlated_risk(
            correlation_key="Technology",
            correlation_type="sector",
            open_campaigns=[campaign],
            sector_mappings=sector_mappings,
        )

        assert result == Decimal("1.5000")

    def test_three_tech_campaigns_sum_correctly(
        self, sector_mappings: dict[str, SectorMapping]
    ) -> None:
        """Test 3 Tech campaigns (AAPL 1.5%, MSFT 1.5%, GOOGL 1.5%) = 4.5% total (AC 8)."""
        campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("1.5000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("1.5000")),
            create_campaign("GOOGL", "Technology", "stock", "US", Decimal("1.5000")),
        ]

        result = calculate_correlated_risk(
            correlation_key="Technology",
            correlation_type="sector",
            open_campaigns=campaigns,
            sector_mappings=sector_mappings,
        )

        assert result == Decimal("4.5000")

    def test_campaign_scaling_one_campaign_correlation(
        self, sector_mappings: dict[str, SectorMapping]
    ) -> None:
        """
        Test campaign scaling: 3 positions in same AAPL campaign = 1 campaign correlation (AC 11).

        This is the KEY distinction for Wyckoff methodology:
        - Spring → LPS add #1 → LPS add #2 = ONE campaign with 3 positions
        - Campaign correlation counts the campaign ONCE, not three times
        """
        # Single campaign with 3 positions (Spring + 2 LPS adds)
        campaign = create_campaign(
            symbol="AAPL",
            sector="Technology",
            asset_class="stock",
            geography="US",
            total_risk=Decimal("3.0000"),  # Total risk across 3 positions
            position_count=3,  # 3 positions in this campaign
        )

        result = calculate_correlated_risk(
            correlation_key="Technology",
            correlation_type="sector",
            open_campaigns=[campaign],
            sector_mappings=sector_mappings,
        )

        # Should return campaign's total_risk (3.0%), NOT 3x individual position risk
        assert result == Decimal("3.0000")
        assert len(campaign.positions) == 3  # 3 positions
        # But it's ONE campaign correlation unit

    def test_three_positions_different_campaigns_three_correlations(
        self, sector_mappings: dict[str, SectorMapping]
    ) -> None:
        """
        Test 3 positions in different campaigns = 3 campaign correlations (AC 11).

        This is the contrast to campaign scaling:
        - AAPL campaign + MSFT campaign + GOOGL campaign = THREE correlation units
        - Each campaign is a separate correlation risk
        """
        campaigns = [
            create_campaign(
                "AAPL", "Technology", "stock", "US", Decimal("1.0000"), position_count=1
            ),
            create_campaign(
                "MSFT", "Technology", "stock", "US", Decimal("1.0000"), position_count=1
            ),
            create_campaign(
                "GOOGL", "Technology", "stock", "US", Decimal("1.0000"), position_count=1
            ),
        ]

        result = calculate_correlated_risk(
            correlation_key="Technology",
            correlation_type="sector",
            open_campaigns=campaigns,
            sector_mappings=sector_mappings,
        )

        # Should return sum of 3 campaign risks = 3.0%
        assert result == Decimal("3.0000")

    def test_multi_sector_campaigns_only_sum_same_sector(
        self, sector_mappings: dict[str, SectorMapping]
    ) -> None:
        """Test multi-sector campaigns only sum same-sector risk (AC 8)."""
        campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("1.5000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("1.5000")),
            create_campaign(
                "JNJ", "Healthcare", "stock", "US", Decimal("2.0000")
            ),  # Different sector
        ]

        tech_result = calculate_correlated_risk(
            correlation_key="Technology",
            correlation_type="sector",
            open_campaigns=campaigns,
            sector_mappings=sector_mappings,
        )

        healthcare_result = calculate_correlated_risk(
            correlation_key="Healthcare",
            correlation_type="sector",
            open_campaigns=campaigns,
            sector_mappings=sector_mappings,
        )

        assert tech_result == Decimal("3.0000")  # Only AAPL + MSFT
        assert healthcare_result == Decimal("2.0000")  # Only JNJ

    def test_unknown_symbol_treated_as_separate_group(
        self, sector_mappings: dict[str, SectorMapping]
    ) -> None:
        """Test unknown symbol treated as separate correlation group."""
        campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("1.5000")),
            create_campaign("UNKNOWN", "Unknown", "stock", None, Decimal("1.0000")),
        ]

        tech_result = calculate_correlated_risk(
            correlation_key="Technology",
            correlation_type="sector",
            open_campaigns=campaigns,
            sector_mappings=sector_mappings,
        )

        unknown_result = calculate_correlated_risk(
            correlation_key="Unknown",
            correlation_type="sector",
            open_campaigns=campaigns,
            sector_mappings=sector_mappings,
        )

        assert tech_result == Decimal("1.5000")  # Only AAPL
        assert unknown_result == Decimal("1.0000")  # Only UNKNOWN

    def test_multi_level_correlation_sector_vs_asset_class(
        self, sector_mappings: dict[str, SectorMapping]
    ) -> None:
        """Test multi-level correlation: sector 6% vs asset_class 15% returns different limits (AC 8)."""
        campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("3.0000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("3.0000")),
            create_campaign("JNJ", "Healthcare", "stock", "US", Decimal("3.0000")),
            create_campaign("PFE", "Healthcare", "stock", "US", Decimal("3.0000")),
        ]

        # Sector level: Technology = 6.0%, Healthcare = 6.0%
        tech_sector = calculate_correlated_risk(
            correlation_key="Technology",
            correlation_type="sector",
            open_campaigns=campaigns,
            sector_mappings=sector_mappings,
        )

        healthcare_sector = calculate_correlated_risk(
            correlation_key="Healthcare",
            correlation_type="sector",
            open_campaigns=campaigns,
            sector_mappings=sector_mappings,
        )

        # Asset class level: stock = 12.0% (Tech + Healthcare)
        stock_asset_class = calculate_correlated_risk(
            correlation_key="stock",
            correlation_type="asset_class",
            open_campaigns=campaigns,
            sector_mappings=sector_mappings,
        )

        assert tech_sector == Decimal("6.0000")
        assert healthcare_sector == Decimal("6.0000")
        assert stock_asset_class == Decimal("12.0000")  # Sum of both sectors

    def test_decimal_precision_maintained(self, sector_mappings: dict[str, SectorMapping]) -> None:
        """Test Decimal precision maintained (no floating point drift)."""
        campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("1.1111")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("2.2222")),
            create_campaign("GOOGL", "Technology", "stock", "US", Decimal("3.3333")),
        ]

        result = calculate_correlated_risk(
            correlation_key="Technology",
            correlation_type="sector",
            open_campaigns=campaigns,
            sector_mappings=sector_mappings,
        )

        # Exact Decimal match, no floating point drift
        assert result == Decimal("6.6666")
        assert isinstance(result, Decimal)

    def test_asset_class_correlation_calculation(
        self, sector_mappings: dict[str, SectorMapping]
    ) -> None:
        """Test asset_class correlation calculation."""
        campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("2.0000")),
            create_campaign("JNJ", "Healthcare", "stock", "US", Decimal("3.0000")),
            create_campaign("XOM", "Energy", "stock", "US", Decimal("1.5000")),
        ]

        result = calculate_correlated_risk(
            correlation_key="stock",
            correlation_type="asset_class",
            open_campaigns=campaigns,
            sector_mappings=sector_mappings,
        )

        # All campaigns are stocks, should sum all
        assert result == Decimal("6.5000")

    def test_geography_correlation_calculation(
        self, sector_mappings: dict[str, SectorMapping]
    ) -> None:
        """Test geography correlation calculation."""
        campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("2.0000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("1.5000")),
            create_campaign("JNJ", "Healthcare", "stock", "US", Decimal("2.5000")),
        ]

        result = calculate_correlated_risk(
            correlation_key="US",
            correlation_type="geography",
            open_campaigns=campaigns,
            sector_mappings=sector_mappings,
        )

        # All campaigns are US geography
        assert result == Decimal("6.0000")


class TestValidateSectorCampaignCount:
    """Test validate_sector_campaign_count function (AC 12)."""

    def test_three_campaigns_allowed(self) -> None:
        """Test 3 campaigns per sector allowed (max=3)."""
        campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("1.5000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("1.5000")),
            create_campaign("GOOGL", "Technology", "stock", "US", Decimal("1.5000")),
        ]

        is_valid, error = validate_sector_campaign_count("Technology", campaigns, max_campaigns=3)

        assert is_valid is False  # Already at max (3), can't add 4th
        assert error is not None
        assert "3 campaigns" in error

    def test_fourth_campaign_rejected_when_max_three(self) -> None:
        """Test 4th campaign rejected when max=3 (AC 12)."""
        # Existing 3 campaigns
        campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("1.5000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("1.5000")),
            create_campaign("GOOGL", "Technology", "stock", "US", Decimal("1.5000")),
        ]

        # Try to validate 4th campaign (NVDA)
        is_valid, error = validate_sector_campaign_count("Technology", campaigns, max_campaigns=3)

        assert is_valid is False
        assert error is not None
        assert "Technology" in error
        assert "3 campaigns" in error
        assert "maximum 3" in error

    def test_campaign_with_multiple_positions_counts_as_one(self) -> None:
        """Test campaign with multiple positions counts as 1 campaign (AC 12)."""
        campaigns = [
            create_campaign(
                "AAPL", "Technology", "stock", "US", Decimal("3.0000"), position_count=3
            ),  # 1 campaign with 3 positions
            create_campaign(
                "MSFT", "Technology", "stock", "US", Decimal("1.5000"), position_count=1
            ),
        ]

        is_valid, error = validate_sector_campaign_count("Technology", campaigns, max_campaigns=3)

        # 2 campaigns total, should pass
        assert is_valid is True
        assert error is None

    def test_two_campaigns_allows_third(self) -> None:
        """Test 2 campaigns allows 3rd to be added."""
        campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("1.5000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("1.5000")),
        ]

        is_valid, error = validate_sector_campaign_count("Technology", campaigns, max_campaigns=3)

        assert is_valid is True
        assert error is None

    def test_different_sectors_dont_affect_count(self) -> None:
        """Test different sectors don't affect each other's campaign count."""
        campaigns = [
            create_campaign("AAPL", "Technology", "stock", "US", Decimal("1.5000")),
            create_campaign("MSFT", "Technology", "stock", "US", Decimal("1.5000")),
            create_campaign("JNJ", "Healthcare", "stock", "US", Decimal("2.0000")),
            create_campaign("PFE", "Healthcare", "stock", "US", Decimal("2.0000")),
        ]

        # Technology has 2, should allow 3rd
        tech_valid, tech_error = validate_sector_campaign_count(
            "Technology", campaigns, max_campaigns=3
        )
        assert tech_valid is True
        assert tech_error is None

        # Healthcare has 2, should allow 3rd
        health_valid, health_error = validate_sector_campaign_count(
            "Healthcare", campaigns, max_campaigns=3
        )
        assert health_valid is True
        assert health_error is None
