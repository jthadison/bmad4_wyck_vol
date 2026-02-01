"""
Unit tests for CampaignVolumeProfile model - Story 22.10

Tests the volume analysis functionality including volume profiles,
effort vs result analysis, and Wyckoff volume rules.
"""

from decimal import Decimal

import pytest

from src.models.campaign_volume import (
    CLIMAX_VOLUME_THRESHOLD,
    SOS_HIGH_EFFORT_THRESHOLD,
    SPRING_HIGH_EFFORT_THRESHOLD,
    CampaignVolumeProfile,
    EffortVsResult,
    VolumeProfile,
)


class TestVolumeProfileEnum:
    """Test VolumeProfile enum."""

    def test_all_profiles_exist(self):
        """Test all expected volume profiles are defined."""
        assert VolumeProfile.INCREASING.value == "INCREASING"
        assert VolumeProfile.DECLINING.value == "DECLINING"
        assert VolumeProfile.NEUTRAL.value == "NEUTRAL"
        assert VolumeProfile.UNKNOWN.value == "UNKNOWN"


class TestEffortVsResultEnum:
    """Test EffortVsResult enum."""

    def test_all_relationships_exist(self):
        """Test all expected relationships are defined."""
        assert EffortVsResult.HARMONY.value == "HARMONY"
        assert EffortVsResult.DIVERGENCE.value == "DIVERGENCE"
        assert EffortVsResult.UNKNOWN.value == "UNKNOWN"


class TestCampaignVolumeProfileCreation:
    """Test CampaignVolumeProfile instantiation."""

    def test_default_creation(self):
        """Test creating with defaults."""
        volume = CampaignVolumeProfile()

        assert volume.volume_profile == VolumeProfile.UNKNOWN
        assert volume.volume_trend_quality == 0.0
        assert volume.effort_vs_result == EffortVsResult.UNKNOWN
        assert volume.volume_confirmation is False
        assert volume.relative_volume == 1.0
        assert volume.climax_detected is False
        assert volume.climax_volume is None
        assert volume.spring_volume is None
        assert volume.breakout_volume is None
        assert volume.volume_history == []
        assert volume.absorption_quality == 0.0

    def test_custom_creation(self):
        """Test creating with custom values."""
        volume = CampaignVolumeProfile(
            volume_profile=VolumeProfile.DECLINING,
            effort_vs_result=EffortVsResult.HARMONY,
            volume_confirmation=True,
            relative_volume=0.6,
        )

        assert volume.volume_profile == VolumeProfile.DECLINING
        assert volume.effort_vs_result == EffortVsResult.HARMONY
        assert volume.volume_confirmation is True
        assert volume.relative_volume == 0.6


class TestVolumeConfirming:
    """Test is_volume_confirming method."""

    def test_volume_confirming_true(self):
        """Test volume is confirming when both conditions met."""
        volume = CampaignVolumeProfile(
            volume_confirmation=True,
            effort_vs_result=EffortVsResult.HARMONY,
        )

        assert volume.is_volume_confirming() is True

    def test_volume_confirming_false_no_confirmation(self):
        """Test volume not confirming without confirmation flag."""
        volume = CampaignVolumeProfile(
            volume_confirmation=False,
            effort_vs_result=EffortVsResult.HARMONY,
        )

        assert volume.is_volume_confirming() is False

    def test_volume_confirming_false_divergence(self):
        """Test volume not confirming with divergence."""
        volume = CampaignVolumeProfile(
            volume_confirmation=True,
            effort_vs_result=EffortVsResult.DIVERGENCE,
        )

        assert volume.is_volume_confirming() is False


class TestSpringValidation:
    """Test is_spring_valid method."""

    def test_spring_valid_low_volume(self):
        """Test Spring is valid with low volume."""
        volume = CampaignVolumeProfile(spring_volume=Decimal("0.4"))

        assert volume.is_spring_valid() is True

    def test_spring_invalid_high_volume(self):
        """Test Spring is invalid with high volume."""
        volume = CampaignVolumeProfile(spring_volume=Decimal("0.6"))

        assert volume.is_spring_valid() is False

    def test_spring_invalid_at_threshold(self):
        """Test Spring at threshold is invalid."""
        volume = CampaignVolumeProfile(spring_volume=Decimal(str(SPRING_HIGH_EFFORT_THRESHOLD)))

        assert volume.is_spring_valid() is False

    def test_spring_invalid_no_volume(self):
        """Test Spring with no volume data is invalid."""
        volume = CampaignVolumeProfile()

        assert volume.is_spring_valid() is False


class TestBreakoutValidation:
    """Test is_breakout_valid method."""

    def test_breakout_valid_high_volume(self):
        """Test breakout is valid with high volume."""
        volume = CampaignVolumeProfile(breakout_volume=Decimal("1.8"))

        assert volume.is_breakout_valid() is True

    def test_breakout_invalid_low_volume(self):
        """Test breakout is invalid with low volume."""
        volume = CampaignVolumeProfile(breakout_volume=Decimal("1.2"))

        assert volume.is_breakout_valid() is False

    def test_breakout_invalid_at_threshold(self):
        """Test breakout at threshold is invalid."""
        volume = CampaignVolumeProfile(breakout_volume=Decimal(str(SOS_HIGH_EFFORT_THRESHOLD)))

        assert volume.is_breakout_valid() is False

    def test_breakout_invalid_no_volume(self):
        """Test breakout with no volume data is invalid."""
        volume = CampaignVolumeProfile()

        assert volume.is_breakout_valid() is False


class TestClimaxDetection:
    """Test has_climax method."""

    def test_has_climax_true(self):
        """Test has_climax when climax detected."""
        volume = CampaignVolumeProfile(climax_detected=True)

        assert volume.has_climax() is True

    def test_has_climax_false(self):
        """Test has_climax when no climax."""
        volume = CampaignVolumeProfile(climax_detected=False)

        assert volume.has_climax() is False


class TestVolumeHistory:
    """Test add_volume_reading method."""

    def test_add_volume_reading(self):
        """Test adding volume readings."""
        volume = CampaignVolumeProfile()

        volume.add_volume_reading(Decimal("1.2"))
        volume.add_volume_reading(Decimal("1.5"))
        volume.add_volume_reading(Decimal("1.8"))

        assert len(volume.volume_history) == 3
        assert volume.volume_history[0] == Decimal("1.2")
        assert volume.volume_history[2] == Decimal("1.8")

    def test_get_average_volume_empty(self):
        """Test get_average_volume with empty history."""
        volume = CampaignVolumeProfile()

        assert volume.get_average_volume() is None

    def test_get_average_volume(self):
        """Test get_average_volume calculation."""
        volume = CampaignVolumeProfile()
        volume.volume_history = [Decimal("1.0"), Decimal("1.5"), Decimal("2.0")]

        avg = volume.get_average_volume()

        assert avg == Decimal("1.5")


class TestTrendClassification:
    """Test classify_trend method."""

    def test_classify_trend_insufficient_data(self):
        """Test classification with insufficient patterns."""
        volume = CampaignVolumeProfile()
        volume.volume_history = [Decimal("1.0"), Decimal("1.2")]  # Only 2

        result = volume.classify_trend()

        assert result == VolumeProfile.UNKNOWN

    def test_classify_trend_increasing(self):
        """Test classification with increasing volume."""
        volume = CampaignVolumeProfile()
        volume.volume_history = [
            Decimal("1.0"),
            Decimal("1.1"),
            Decimal("1.2"),
            Decimal("1.5"),
            Decimal("1.8"),
            Decimal("2.0"),
        ]

        result = volume.classify_trend()

        assert result == VolumeProfile.INCREASING

    def test_classify_trend_declining(self):
        """Test classification with declining volume."""
        volume = CampaignVolumeProfile()
        volume.volume_history = [
            Decimal("2.0"),
            Decimal("1.8"),
            Decimal("1.5"),
            Decimal("1.2"),
            Decimal("1.0"),
            Decimal("0.8"),
        ]

        result = volume.classify_trend()

        assert result == VolumeProfile.DECLINING

    def test_classify_trend_neutral(self):
        """Test classification with neutral volume."""
        volume = CampaignVolumeProfile()
        volume.volume_history = [
            Decimal("1.0"),
            Decimal("1.1"),
            Decimal("0.9"),
            Decimal("1.05"),
            Decimal("0.95"),
            Decimal("1.0"),
        ]

        result = volume.classify_trend()

        assert result == VolumeProfile.NEUTRAL


class TestUpdateClassification:
    """Test update_classification method."""

    def test_update_classification(self):
        """Test update_classification updates profile."""
        volume = CampaignVolumeProfile()
        volume.volume_history = [
            Decimal("1.0"),
            Decimal("1.2"),
            Decimal("1.5"),
            Decimal("1.8"),
        ]

        volume.update_classification()

        assert volume.volume_profile == VolumeProfile.INCREASING
        assert volume.volume_trend_quality > 0

    def test_update_classification_insufficient_data(self):
        """Test update_classification with insufficient data."""
        volume = CampaignVolumeProfile()
        volume.volume_history = [Decimal("1.0")]

        volume.update_classification()

        assert volume.volume_profile == VolumeProfile.UNKNOWN
        assert volume.volume_trend_quality == 0.0


class TestRecordSpring:
    """Test record_spring method."""

    def test_record_spring_low_volume(self):
        """Test recording low volume Spring."""
        volume = CampaignVolumeProfile()

        volume.record_spring(Decimal("0.3"))

        assert volume.spring_volume == Decimal("0.3")
        assert Decimal("0.3") in volume.volume_history
        assert volume.absorption_quality == pytest.approx(0.4, rel=0.01)

    def test_record_spring_very_low_volume(self):
        """Test recording very low volume Spring has high absorption."""
        volume = CampaignVolumeProfile()

        volume.record_spring(Decimal("0.1"))

        assert volume.absorption_quality == pytest.approx(0.8, rel=0.01)

    def test_record_spring_zero_volume(self):
        """Test recording zero volume Spring has max absorption."""
        volume = CampaignVolumeProfile()

        volume.record_spring(Decimal("0"))

        assert volume.absorption_quality == 1.0

    def test_record_spring_high_volume(self):
        """Test recording high volume Spring has low absorption."""
        volume = CampaignVolumeProfile()

        volume.record_spring(Decimal("0.5"))

        assert volume.absorption_quality == 0.0


class TestRecordBreakout:
    """Test record_breakout method."""

    def test_record_breakout(self):
        """Test recording breakout volume."""
        volume = CampaignVolumeProfile()

        volume.record_breakout(Decimal("1.8"))

        assert volume.breakout_volume == Decimal("1.8")
        assert Decimal("1.8") in volume.volume_history

    def test_record_breakout_climactic(self):
        """Test recording climactic breakout volume."""
        volume = CampaignVolumeProfile()

        volume.record_breakout(Decimal("2.5"))

        assert volume.climax_detected is True
        assert volume.climax_volume == Decimal("2.5")

    def test_record_breakout_non_climactic(self):
        """Test recording non-climactic breakout volume."""
        volume = CampaignVolumeProfile()

        volume.record_breakout(Decimal("1.8"))

        assert volume.climax_detected is False
        assert volume.climax_volume is None

    def test_record_breakout_at_climax_threshold(self):
        """Test breakout at exactly climax threshold."""
        volume = CampaignVolumeProfile()

        volume.record_breakout(Decimal(str(CLIMAX_VOLUME_THRESHOLD)))

        assert volume.climax_detected is True
