"""
Unit tests for ComposedCampaign model - Story 22.10

Tests the composed Campaign model including factory methods,
backward compatibility properties, and sub-model integration.
"""

from decimal import Decimal

from src.models.campaign_composed import (
    Campaign,
    ComposedCampaign,
)
from src.models.campaign_core import CampaignCore, CampaignState
from src.models.campaign_performance import CampaignPerformanceMetrics, ExitReason
from src.models.campaign_risk import CampaignRiskMetadata
from src.models.campaign_volume import (
    CampaignVolumeProfile,
    EffortVsResult,
    VolumeProfile,
)


class TestComposedCampaignCreation:
    """Test ComposedCampaign instantiation."""

    def test_default_creation(self):
        """Test creating ComposedCampaign with defaults."""
        campaign = ComposedCampaign()

        # Check sub-models exist
        assert isinstance(campaign.core, CampaignCore)
        assert isinstance(campaign.risk, CampaignRiskMetadata)
        assert isinstance(campaign.performance, CampaignPerformanceMetrics)
        assert isinstance(campaign.volume, CampaignVolumeProfile)

        # Check defaults
        assert campaign.campaign_id is not None
        assert campaign.state == CampaignState.FORMING
        assert campaign.patterns == []

    def test_factory_method(self):
        """Test create factory method."""
        campaign = ComposedCampaign.create(
            symbol="AAPL",
            support_level=Decimal("145.00"),
            resistance_level=Decimal("160.00"),
            timeframe="4h",
        )

        assert campaign.symbol == "AAPL"
        assert campaign.support_level == Decimal("145.00")
        assert campaign.resistance_level == Decimal("160.00")
        assert campaign.timeframe == "4h"
        assert campaign.range_width_pct is not None

    def test_factory_with_custom_id(self):
        """Test create factory method with custom ID."""
        campaign = ComposedCampaign.create(
            symbol="MSFT",
            campaign_id="custom-123",
        )

        assert campaign.campaign_id == "custom-123"

    def test_factory_with_sector(self):
        """Test create factory method with sector."""
        campaign = ComposedCampaign.create(
            symbol="AAPL",
            sector="TECH",
            correlation_group="high-beta-tech",
        )

        assert campaign.sector == "TECH"
        assert campaign.correlation_group == "high-beta-tech"


class TestBackwardCompatibilityCore:
    """Test backward compatibility properties for core fields."""

    def test_campaign_id_property(self):
        """Test campaign_id property accessor."""
        campaign = ComposedCampaign()
        campaign.campaign_id = "test-id"

        assert campaign.campaign_id == "test-id"
        assert campaign.core.campaign_id == "test-id"

    def test_symbol_property(self):
        """Test symbol property accessor."""
        campaign = ComposedCampaign()
        campaign.symbol = "AAPL"

        assert campaign.symbol == "AAPL"
        assert campaign.core.symbol == "AAPL"

    def test_state_property(self):
        """Test state property accessor."""
        campaign = ComposedCampaign()
        campaign.state = CampaignState.ACTIVE

        assert campaign.state == CampaignState.ACTIVE
        assert campaign.core.state == CampaignState.ACTIVE

    def test_patterns_property(self):
        """Test patterns property accessor."""
        campaign = ComposedCampaign()
        campaign.patterns = ["pattern1", "pattern2"]

        assert campaign.patterns == ["pattern1", "pattern2"]
        assert campaign.core.patterns == ["pattern1", "pattern2"]

    def test_timeframe_property(self):
        """Test timeframe property accessor."""
        campaign = ComposedCampaign()
        campaign.timeframe = "1h"

        assert campaign.timeframe == "1h"
        assert campaign.core.timeframe == "1h"


class TestBackwardCompatibilityRisk:
    """Test backward compatibility properties for risk fields."""

    def test_support_level_property(self):
        """Test support_level property accessor."""
        campaign = ComposedCampaign()
        campaign.support_level = Decimal("145.00")

        assert campaign.support_level == Decimal("145.00")
        assert campaign.risk.support_level == Decimal("145.00")

    def test_resistance_level_property(self):
        """Test resistance_level property accessor."""
        campaign = ComposedCampaign()
        campaign.resistance_level = Decimal("160.00")

        assert campaign.resistance_level == Decimal("160.00")
        assert campaign.risk.resistance_level == Decimal("160.00")

    def test_risk_per_share_property(self):
        """Test risk_per_share property accessor."""
        campaign = ComposedCampaign()
        campaign.risk_per_share = Decimal("5.00")

        assert campaign.risk_per_share == Decimal("5.00")
        assert campaign.risk.risk_per_share == Decimal("5.00")

    def test_position_size_property(self):
        """Test position_size property accessor."""
        campaign = ComposedCampaign()
        campaign.position_size = Decimal("100")

        assert campaign.position_size == Decimal("100")
        assert campaign.risk.position_size == Decimal("100")

    def test_dollar_risk_property(self):
        """Test dollar_risk property accessor."""
        campaign = ComposedCampaign()
        campaign.dollar_risk = Decimal("500.00")

        assert campaign.dollar_risk == Decimal("500.00")
        assert campaign.risk.dollar_risk == Decimal("500.00")

    def test_jump_level_property(self):
        """Test jump_level property accessor."""
        campaign = ComposedCampaign()
        campaign.jump_level = Decimal("175.00")

        assert campaign.jump_level == Decimal("175.00")
        assert campaign.risk.jump_level == Decimal("175.00")


class TestBackwardCompatibilityPerformance:
    """Test backward compatibility properties for performance fields."""

    def test_r_multiple_property(self):
        """Test r_multiple property accessor."""
        campaign = ComposedCampaign()
        campaign.r_multiple = Decimal("2.5")

        assert campaign.r_multiple == Decimal("2.5")
        assert campaign.performance.r_multiple == Decimal("2.5")

    def test_points_gained_property(self):
        """Test points_gained property accessor."""
        campaign = ComposedCampaign()
        campaign.points_gained = Decimal("15.00")

        assert campaign.points_gained == Decimal("15.00")
        assert campaign.performance.points_gained == Decimal("15.00")

    def test_exit_price_property(self):
        """Test exit_price property accessor."""
        campaign = ComposedCampaign()
        campaign.exit_price = Decimal("165.00")

        assert campaign.exit_price == Decimal("165.00")
        assert campaign.performance.exit_price == Decimal("165.00")

    def test_exit_reason_property(self):
        """Test exit_reason property accessor."""
        campaign = ComposedCampaign()
        campaign.exit_reason = ExitReason.TARGET_HIT

        assert campaign.exit_reason == ExitReason.TARGET_HIT
        assert campaign.performance.exit_reason == ExitReason.TARGET_HIT

    def test_duration_bars_property(self):
        """Test duration_bars property accessor."""
        campaign = ComposedCampaign()
        campaign.duration_bars = 45

        assert campaign.duration_bars == 45
        assert campaign.performance.duration_bars == 45


class TestBackwardCompatibilityVolume:
    """Test backward compatibility properties for volume fields."""

    def test_volume_profile_property(self):
        """Test volume_profile property accessor."""
        campaign = ComposedCampaign()
        campaign.volume_profile = VolumeProfile.DECLINING

        assert campaign.volume_profile == VolumeProfile.DECLINING
        assert campaign.volume.volume_profile == VolumeProfile.DECLINING

    def test_effort_vs_result_property(self):
        """Test effort_vs_result property accessor."""
        campaign = ComposedCampaign()
        campaign.effort_vs_result = EffortVsResult.HARMONY

        assert campaign.effort_vs_result == EffortVsResult.HARMONY
        assert campaign.volume.effort_vs_result == EffortVsResult.HARMONY

    def test_climax_detected_property(self):
        """Test climax_detected property accessor."""
        campaign = ComposedCampaign()
        campaign.climax_detected = True

        assert campaign.climax_detected is True
        assert campaign.volume.climax_detected is True

    def test_absorption_quality_property(self):
        """Test absorption_quality property accessor."""
        campaign = ComposedCampaign()
        campaign.absorption_quality = 0.8

        assert campaign.absorption_quality == 0.8
        assert campaign.volume.absorption_quality == 0.8

    def test_volume_history_property(self):
        """Test volume_history property accessor."""
        campaign = ComposedCampaign()
        campaign.volume_history = [Decimal("1.2"), Decimal("1.5")]

        assert campaign.volume_history == [Decimal("1.2"), Decimal("1.5")]
        assert campaign.volume.volume_history == [Decimal("1.2"), Decimal("1.5")]


class TestCampaignMethods:
    """Test campaign methods."""

    def test_is_terminal(self):
        """Test is_terminal delegates to core."""
        campaign = ComposedCampaign()
        campaign.state = CampaignState.COMPLETED

        assert campaign.is_terminal() is True

    def test_is_actionable(self):
        """Test is_actionable delegates to core."""
        campaign = ComposedCampaign()
        campaign.state = CampaignState.ACTIVE

        assert campaign.is_actionable() is True

    def test_invalidate_validation_cache(self):
        """Test validation cache methods work."""
        campaign = ComposedCampaign()

        # Should not raise
        campaign.invalidate_validation_cache()


class TestCampaignAlias:
    """Test Campaign alias works."""

    def test_campaign_is_composed_campaign(self):
        """Test Campaign is aliased to ComposedCampaign."""
        assert Campaign is ComposedCampaign

    def test_create_via_alias(self):
        """Test creating via Campaign alias."""
        campaign = Campaign.create(symbol="AAPL")

        assert isinstance(campaign, ComposedCampaign)
        assert campaign.symbol == "AAPL"


class TestSubModelIntegration:
    """Test sub-model integration."""

    def test_risk_validation_through_composed(self):
        """Test risk validation accessible through composed model."""
        campaign = ComposedCampaign.create(
            symbol="AAPL",
            support_level=Decimal("100.00"),
            resistance_level=Decimal("110.00"),
        )

        campaign.risk.risk_per_share = Decimal("5.00")
        valid, errors = campaign.risk.validate()

        assert valid is True

    def test_volume_classification_through_composed(self):
        """Test volume classification through composed model."""
        campaign = ComposedCampaign()

        campaign.volume.add_volume_reading(Decimal("1.0"))
        campaign.volume.add_volume_reading(Decimal("1.2"))
        campaign.volume.add_volume_reading(Decimal("1.5"))
        campaign.volume.add_volume_reading(Decimal("1.8"))

        campaign.volume.update_classification()

        # Also accessible via backward compat
        assert campaign.volume_profile == VolumeProfile.INCREASING
