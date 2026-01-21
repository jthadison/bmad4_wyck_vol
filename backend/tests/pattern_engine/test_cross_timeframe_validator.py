"""
Unit Tests for Cross-Timeframe Validation Module (Story 16.6b)

Test Coverage:
--------------
- CrossTimeframeValidator class
- HTFCampaignSnapshot dataclass
- Timeframe hierarchy and ordering
- Pattern alignment with HTF trends
- Strict mode vs warning mode
- Confidence adjustment calculations

Author: Story 16.6b
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.pattern_engine.validators.cross_timeframe_validator import (
    BEARISH_PATTERNS,
    BULLISH_PATTERNS,
    HTF_MAPPING,
    TIMEFRAME_ORDER,
    CrossTimeframeValidator,
    HTFCampaignSnapshot,
    HTFTrend,
    TimeframeHierarchy,
    ValidationSeverity,
    create_htf_snapshot_from_campaign,
)


class TestTimeframeConstants:
    """Test Suite for timeframe hierarchy constants."""

    def test_timeframe_order_contains_all_timeframes(self):
        """Verify TIMEFRAME_ORDER has all 7 timeframes in order."""
        expected = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
        assert TIMEFRAME_ORDER == expected

    def test_htf_mapping_has_correct_relationships(self):
        """Verify HTF_MAPPING maps lower to higher timeframes correctly."""
        assert HTF_MAPPING["1m"] == ["5m", "15m"]
        assert HTF_MAPPING["5m"] == ["15m", "1h"]
        assert HTF_MAPPING["15m"] == ["1h", "4h"]
        assert HTF_MAPPING["1h"] == ["4h", "1d"]
        assert HTF_MAPPING["4h"] == ["1d", "1w"]
        assert HTF_MAPPING["1d"] == ["1w"]
        assert HTF_MAPPING["1w"] == []  # No higher timeframe

    def test_bullish_patterns_set(self):
        """Verify BULLISH_PATTERNS contains expected patterns."""
        assert "SPRING" in BULLISH_PATTERNS
        assert "SOS" in BULLISH_PATTERNS
        assert "LPS" in BULLISH_PATTERNS
        assert "AR" in BULLISH_PATTERNS

    def test_bearish_patterns_set(self):
        """Verify BEARISH_PATTERNS contains expected patterns."""
        assert "UTAD" in BEARISH_PATTERNS
        assert "SOW" in BEARISH_PATTERNS
        assert "LPSY" in BEARISH_PATTERNS


class TestHTFCampaignSnapshot:
    """Test Suite for HTFCampaignSnapshot dataclass."""

    def test_create_snapshot_with_all_fields(self):
        """Verify snapshot creation with all fields."""
        snapshot = HTFCampaignSnapshot(
            symbol="EUR/USD",
            timeframe="1d",
            trend=HTFTrend.ACCUMULATION,
            phase="D",
            confidence=Decimal("0.8"),
            last_updated=datetime.now(UTC),
        )
        assert snapshot.symbol == "EUR/USD"
        assert snapshot.timeframe == "1d"
        assert snapshot.trend == HTFTrend.ACCUMULATION
        assert snapshot.phase == "D"
        assert snapshot.confidence == Decimal("0.8")

    def test_create_snapshot_with_defaults(self):
        """Verify snapshot creation with default values."""
        snapshot = HTFCampaignSnapshot(
            symbol="AAPL",
            timeframe="1h",
            trend=HTFTrend.NEUTRAL,
            phase="B",
        )
        assert snapshot.confidence == Decimal("0.5")  # Default
        assert snapshot.last_updated is not None


class TestHTFTrend:
    """Test Suite for HTFTrend enum."""

    def test_htf_trend_values(self):
        """Verify all HTFTrend enum values."""
        assert HTFTrend.ACCUMULATION.value == "ACCUMULATION"
        assert HTFTrend.DISTRIBUTION.value == "DISTRIBUTION"
        assert HTFTrend.NEUTRAL.value == "NEUTRAL"
        assert HTFTrend.UNKNOWN.value == "UNKNOWN"


class TestValidationSeverity:
    """Test Suite for ValidationSeverity enum."""

    def test_validation_severity_values(self):
        """Verify all ValidationSeverity enum values."""
        assert ValidationSeverity.CONFIRMED.value == "CONFIRMED"
        assert ValidationSeverity.WARNING.value == "WARNING"
        assert ValidationSeverity.REJECTED.value == "REJECTED"
        assert ValidationSeverity.SKIPPED.value == "SKIPPED"


class TestCrossTimeframeValidator:
    """Test Suite for CrossTimeframeValidator class."""

    @pytest.fixture
    def validator(self):
        """Create validator instance with default settings."""
        return CrossTimeframeValidator(strict_mode=False)

    @pytest.fixture
    def strict_validator(self):
        """Create validator instance with strict mode enabled."""
        return CrossTimeframeValidator(strict_mode=True)

    @pytest.fixture
    def htf_accumulation_snapshot(self):
        """Create HTF snapshot in accumulation trend."""
        return HTFCampaignSnapshot(
            symbol="EUR/USD",
            timeframe="1d",
            trend=HTFTrend.ACCUMULATION,
            phase="D",
            confidence=Decimal("0.8"),
        )

    @pytest.fixture
    def htf_distribution_snapshot(self):
        """Create HTF snapshot in distribution trend."""
        return HTFCampaignSnapshot(
            symbol="EUR/USD",
            timeframe="1d",
            trend=HTFTrend.DISTRIBUTION,
            phase="D",
            confidence=Decimal("0.8"),
        )

    @pytest.fixture
    def htf_neutral_snapshot(self):
        """Create HTF snapshot in neutral trend."""
        return HTFCampaignSnapshot(
            symbol="EUR/USD",
            timeframe="1d",
            trend=HTFTrend.NEUTRAL,
            phase="B",
            confidence=Decimal("0.5"),
        )

    # =========================================================================
    # Bullish Pattern Validation Tests
    # =========================================================================

    def test_spring_confirmed_by_accumulation(self, validator, htf_accumulation_snapshot):
        """Verify SPRING pattern is confirmed by ACCUMULATION HTF."""
        result = validator.validate_pattern(
            pattern_type="SPRING",
            pattern_timeframe="1h",
            symbol="EUR/USD",
            htf_campaigns={"1d": htf_accumulation_snapshot},
        )
        assert result.is_valid is True
        assert result.severity == ValidationSeverity.CONFIRMED
        assert result.htf_trend == HTFTrend.ACCUMULATION
        assert result.confidence_adjustment > Decimal("0")

    def test_sos_confirmed_by_accumulation(self, validator, htf_accumulation_snapshot):
        """Verify SOS pattern is confirmed by ACCUMULATION HTF."""
        result = validator.validate_pattern(
            pattern_type="SOS",
            pattern_timeframe="1h",
            symbol="EUR/USD",
            htf_campaigns={"1d": htf_accumulation_snapshot},
        )
        assert result.is_valid is True
        assert result.severity == ValidationSeverity.CONFIRMED

    def test_lps_confirmed_by_accumulation(self, validator, htf_accumulation_snapshot):
        """Verify LPS pattern is confirmed by ACCUMULATION HTF."""
        result = validator.validate_pattern(
            pattern_type="LPS",
            pattern_timeframe="1h",
            symbol="EUR/USD",
            htf_campaigns={"1d": htf_accumulation_snapshot},
        )
        assert result.is_valid is True
        assert result.severity == ValidationSeverity.CONFIRMED

    # =========================================================================
    # Bearish Pattern Validation Tests
    # =========================================================================

    def test_utad_confirmed_by_distribution(self, validator, htf_distribution_snapshot):
        """Verify UTAD pattern is confirmed by DISTRIBUTION HTF."""
        result = validator.validate_pattern(
            pattern_type="UTAD",
            pattern_timeframe="1h",
            symbol="EUR/USD",
            htf_campaigns={"1d": htf_distribution_snapshot},
        )
        assert result.is_valid is True
        assert result.severity == ValidationSeverity.CONFIRMED
        assert result.htf_trend == HTFTrend.DISTRIBUTION
        assert result.confidence_adjustment > Decimal("0")

    # =========================================================================
    # Pattern Against HTF Trend Tests
    # =========================================================================

    def test_spring_warns_against_distribution(self, validator, htf_distribution_snapshot):
        """Verify SPRING pattern generates warning against DISTRIBUTION HTF."""
        result = validator.validate_pattern(
            pattern_type="SPRING",
            pattern_timeframe="1h",
            symbol="EUR/USD",
            htf_campaigns={"1d": htf_distribution_snapshot},
        )
        assert result.is_valid is True  # Non-strict mode allows
        assert result.severity == ValidationSeverity.WARNING
        assert result.warning_message is not None
        assert "conflicts" in result.warning_message.lower()
        assert result.confidence_adjustment < Decimal("0")

    def test_utad_warns_against_accumulation(self, validator, htf_accumulation_snapshot):
        """Verify UTAD pattern generates warning against ACCUMULATION HTF."""
        result = validator.validate_pattern(
            pattern_type="UTAD",
            pattern_timeframe="1h",
            symbol="EUR/USD",
            htf_campaigns={"1d": htf_accumulation_snapshot},
        )
        assert result.is_valid is True  # Non-strict mode allows
        assert result.severity == ValidationSeverity.WARNING
        assert result.confidence_adjustment < Decimal("0")

    # =========================================================================
    # Strict Mode Tests
    # =========================================================================

    def test_strict_mode_rejects_spring_against_distribution(
        self, strict_validator, htf_distribution_snapshot
    ):
        """Verify strict mode rejects SPRING against DISTRIBUTION HTF."""
        result = strict_validator.validate_pattern(
            pattern_type="SPRING",
            pattern_timeframe="1h",
            symbol="EUR/USD",
            htf_campaigns={"1d": htf_distribution_snapshot},
        )
        assert result.is_valid is False
        assert result.severity == ValidationSeverity.REJECTED
        assert result.strict_mode_applied is True

    def test_strict_mode_confirms_aligned_patterns(
        self, strict_validator, htf_accumulation_snapshot
    ):
        """Verify strict mode confirms aligned patterns."""
        result = strict_validator.validate_pattern(
            pattern_type="SPRING",
            pattern_timeframe="1h",
            symbol="EUR/USD",
            htf_campaigns={"1d": htf_accumulation_snapshot},
        )
        assert result.is_valid is True
        assert result.severity == ValidationSeverity.CONFIRMED
        assert result.strict_mode_applied is True

    # =========================================================================
    # Neutral HTF Trend Tests
    # =========================================================================

    def test_pattern_with_neutral_htf_allowed(self, validator, htf_neutral_snapshot):
        """Verify patterns are allowed with neutral HTF trend."""
        result = validator.validate_pattern(
            pattern_type="SPRING",
            pattern_timeframe="1h",
            symbol="EUR/USD",
            htf_campaigns={"1d": htf_neutral_snapshot},
        )
        assert result.is_valid is True
        assert result.severity == ValidationSeverity.CONFIRMED
        assert result.confidence_adjustment == Decimal("0")

    # =========================================================================
    # No HTF Data Tests
    # =========================================================================

    def test_no_htf_data_skips_validation(self, validator):
        """Verify validation is skipped when no HTF data available."""
        result = validator.validate_pattern(
            pattern_type="SPRING",
            pattern_timeframe="1h",
            symbol="EUR/USD",
            htf_campaigns={},  # No HTF data
        )
        assert result.is_valid is True
        assert result.severity == ValidationSeverity.SKIPPED

    def test_no_htf_for_highest_timeframe(self, validator):
        """Verify validation is skipped for 1w patterns (no HTF available)."""
        result = validator.validate_pattern(
            pattern_type="SPRING",
            pattern_timeframe="1w",
            symbol="EUR/USD",
            htf_campaigns={
                "1d": HTFCampaignSnapshot(
                    symbol="EUR/USD",
                    timeframe="1d",
                    trend=HTFTrend.ACCUMULATION,
                    phase="D",
                )
            },
        )
        # 1w has no HTF, so validation is skipped
        assert result.is_valid is True
        assert result.severity == ValidationSeverity.SKIPPED

    # =========================================================================
    # Timeframe Rank Tests
    # =========================================================================

    def test_get_timeframe_rank(self, validator):
        """Verify timeframe rank ordering."""
        assert validator.get_timeframe_rank("1m") == 0
        assert validator.get_timeframe_rank("5m") == 1
        assert validator.get_timeframe_rank("15m") == 2
        assert validator.get_timeframe_rank("1h") == 3
        assert validator.get_timeframe_rank("4h") == 4
        assert validator.get_timeframe_rank("1d") == 5
        assert validator.get_timeframe_rank("1w") == 6

    def test_get_timeframe_rank_invalid_raises_error(self, validator):
        """Verify invalid timeframe raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            validator.get_timeframe_rank("2h")

    def test_is_higher_timeframe(self, validator):
        """Verify is_higher_timeframe comparison."""
        assert validator.is_higher_timeframe("1d", "1h") is True
        assert validator.is_higher_timeframe("1h", "1d") is False
        assert validator.is_higher_timeframe("4h", "15m") is True
        assert validator.is_higher_timeframe("1w", "1m") is True

    # =========================================================================
    # Confidence Adjustment Tests
    # =========================================================================

    def test_confidence_adjustment_positive_for_alignment(
        self, validator, htf_accumulation_snapshot
    ):
        """Verify positive confidence adjustment for aligned patterns."""
        result = validator.validate_pattern(
            pattern_type="SPRING",
            pattern_timeframe="1h",
            symbol="EUR/USD",
            htf_campaigns={"1d": htf_accumulation_snapshot},
        )
        # 0.15 * 0.8 (confidence) = 0.12
        assert result.confidence_adjustment > Decimal("0")
        assert result.confidence_adjustment <= Decimal("0.15")

    def test_confidence_adjustment_negative_for_conflict(
        self, validator, htf_distribution_snapshot
    ):
        """Verify negative confidence adjustment for conflicting patterns."""
        result = validator.validate_pattern(
            pattern_type="SPRING",
            pattern_timeframe="1h",
            symbol="EUR/USD",
            htf_campaigns={"1d": htf_distribution_snapshot},
        )
        assert result.confidence_adjustment == Decimal("-0.25")


class TestCreateHTFSnapshotFromCampaign:
    """Test Suite for create_htf_snapshot_from_campaign factory function."""

    def test_create_snapshot_from_accumulation_campaign(self):
        """Verify snapshot creation from ACCUMULATION campaign type."""
        snapshot = create_htf_snapshot_from_campaign(
            symbol="AAPL",
            timeframe="1d",
            phase="D",
            campaign_type="ACCUMULATION",
            confidence=Decimal("0.7"),
        )
        assert snapshot.symbol == "AAPL"
        assert snapshot.timeframe == "1d"
        assert snapshot.trend == HTFTrend.ACCUMULATION
        assert snapshot.phase == "D"
        assert snapshot.confidence == Decimal("0.7")

    def test_create_snapshot_from_distribution_campaign(self):
        """Verify snapshot creation from DISTRIBUTION campaign type."""
        snapshot = create_htf_snapshot_from_campaign(
            symbol="AAPL",
            timeframe="1d",
            phase="D",
            campaign_type="DISTRIBUTION",
            confidence=Decimal("0.8"),
        )
        assert snapshot.trend == HTFTrend.DISTRIBUTION

    def test_create_snapshot_infers_accumulation_from_phase_d(self):
        """Verify trend inferred as ACCUMULATION for Phase D."""
        snapshot = create_htf_snapshot_from_campaign(
            symbol="AAPL",
            timeframe="1d",
            phase="D",
            campaign_type=None,  # No explicit type
        )
        assert snapshot.trend == HTFTrend.ACCUMULATION

    def test_create_snapshot_infers_accumulation_from_phase_e(self):
        """Verify trend inferred as ACCUMULATION for Phase E."""
        snapshot = create_htf_snapshot_from_campaign(
            symbol="AAPL",
            timeframe="1d",
            phase="E",
            campaign_type=None,
        )
        assert snapshot.trend == HTFTrend.ACCUMULATION

    def test_create_snapshot_infers_neutral_from_phase_a(self):
        """Verify trend inferred as NEUTRAL for Phase A."""
        snapshot = create_htf_snapshot_from_campaign(
            symbol="AAPL",
            timeframe="1d",
            phase="A",
            campaign_type=None,
        )
        assert snapshot.trend == HTFTrend.NEUTRAL

    def test_create_snapshot_infers_accumulation_from_phase_b(self):
        """Verify trend inferred as ACCUMULATION for Phase B."""
        snapshot = create_htf_snapshot_from_campaign(
            symbol="AAPL",
            timeframe="1d",
            phase="B",
            campaign_type=None,
        )
        assert snapshot.trend == HTFTrend.ACCUMULATION

    def test_create_snapshot_infers_accumulation_from_phase_c(self):
        """Verify trend inferred as ACCUMULATION for Phase C."""
        snapshot = create_htf_snapshot_from_campaign(
            symbol="AAPL",
            timeframe="1d",
            phase="C",
            campaign_type=None,
        )
        assert snapshot.trend == HTFTrend.ACCUMULATION


class TestTimeframeHierarchyEnum:
    """Test Suite for TimeframeHierarchy enum."""

    def test_timeframe_hierarchy_values(self):
        """Verify TimeframeHierarchy enum values."""
        assert TimeframeHierarchy.M1.value == "1m"
        assert TimeframeHierarchy.M5.value == "5m"
        assert TimeframeHierarchy.M15.value == "15m"
        assert TimeframeHierarchy.H1.value == "1h"
        assert TimeframeHierarchy.H4.value == "4h"
        assert TimeframeHierarchy.D1.value == "1d"
        assert TimeframeHierarchy.W1.value == "1w"
