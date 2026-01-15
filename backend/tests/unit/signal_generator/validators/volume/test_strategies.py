"""
Unit tests for Volume Validation Strategies (Story 18.6.2)

Tests:
------
- SpringVolumeStrategy: Low volume validation (< 0.7x)
- SOSVolumeStrategy: High volume validation (> 1.5x)
- LPSVolumeStrategy: Moderate volume with absorption support
- UTADVolumeStrategy: High volume on failure validation
- register_all_strategies: Strategy registration

Author: Story 18.6.2
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.models.forex import ForexSession
from src.models.validation import (
    ValidationContext,
    ValidationStatus,
    VolumeValidationConfig,
)
from src.signal_generator.validators.volume import (
    LPSVolumeStrategy,
    SOSVolumeStrategy,
    SpringVolumeStrategy,
    UTADVolumeStrategy,
    VolumeStrategyRegistry,
    register_all_strategies,
)

# ============================================================================
# Test Fixtures
# ============================================================================


class MockPattern:
    """Mock pattern for testing."""

    def __init__(self, pattern_type: str = "SPRING"):
        self.id = uuid4()
        self.pattern_type = pattern_type
        self.pattern_bar_timestamp = datetime.now(UTC)


class MockVolumeAnalysis:
    """Mock volume analysis for testing."""

    def __init__(
        self,
        volume_ratio: Decimal = Decimal("0.65"),
        close_position: Decimal | None = Decimal("0.5"),
    ):
        self.volume_ratio = volume_ratio
        self.close_position = close_position
        self.bar = MagicMock(volume=1000)


@pytest.fixture
def stock_context():
    """Create a stock validation context."""
    return ValidationContext(
        pattern=MockPattern("SPRING"),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=MockVolumeAnalysis(Decimal("0.65")),
        asset_class="STOCK",
    )


@pytest.fixture
def forex_context():
    """Create a forex validation context."""
    return ValidationContext(
        pattern=MockPattern("SPRING"),
        symbol="EUR_USD",
        timeframe="1h",
        volume_analysis=MockVolumeAnalysis(Decimal("0.65")),
        asset_class="FOREX",
        forex_session=ForexSession.LONDON,
    )


@pytest.fixture
def asian_forex_context():
    """Create an Asian session forex context."""
    return ValidationContext(
        pattern=MockPattern("SPRING"),
        symbol="EUR_USD",
        timeframe="1h",
        volume_analysis=MockVolumeAnalysis(Decimal("0.65")),
        asset_class="FOREX",
        forex_session=ForexSession.ASIAN,
    )


@pytest.fixture
def default_config():
    """Create default volume validation config."""
    return VolumeValidationConfig()


# ============================================================================
# SpringVolumeStrategy Tests
# ============================================================================


class TestSpringVolumeStrategy:
    """Test SpringVolumeStrategy validation logic."""

    def test_pattern_type(self):
        """Test strategy returns correct pattern type."""
        strategy = SpringVolumeStrategy()
        assert strategy.pattern_type == "SPRING"

    def test_volume_threshold_type(self):
        """Test strategy returns max threshold type."""
        strategy = SpringVolumeStrategy()
        assert strategy.volume_threshold_type == "max"

    def test_default_stock_threshold(self):
        """Test default stock threshold is 0.7."""
        strategy = SpringVolumeStrategy()
        assert strategy.default_stock_threshold == Decimal("0.7")

    def test_default_forex_threshold(self):
        """Test default forex threshold is 0.85."""
        strategy = SpringVolumeStrategy()
        assert strategy.default_forex_threshold == Decimal("0.85")

    def test_validate_pass_low_volume_stock(self, stock_context, default_config):
        """Test validation passes for low volume stock (< 0.7x)."""
        strategy = SpringVolumeStrategy()
        # Volume ratio 0.65 < 0.7 threshold
        result = strategy.validate(stock_context, default_config)
        assert result.status == ValidationStatus.PASS
        assert result.metadata["actual_volume_ratio"] == 0.65
        assert result.metadata["threshold"] == 0.7

    def test_validate_fail_high_volume_stock(self, stock_context, default_config):
        """Test validation fails for high volume stock (>= 0.7x)."""
        strategy = SpringVolumeStrategy()
        stock_context.volume_analysis = MockVolumeAnalysis(Decimal("0.75"))
        result = strategy.validate(stock_context, default_config)
        assert result.status == ValidationStatus.FAIL
        assert "too high" in result.reason
        assert result.metadata["actual_volume_ratio"] == 0.75

    def test_validate_pass_low_volume_forex(self, forex_context, default_config):
        """Test validation passes for low volume forex (< 0.85x)."""
        strategy = SpringVolumeStrategy()
        forex_context.volume_analysis = MockVolumeAnalysis(Decimal("0.80"))
        result = strategy.validate(forex_context, default_config)
        assert result.status == ValidationStatus.PASS

    def test_validate_fail_high_volume_forex(self, forex_context, default_config):
        """Test validation fails for high volume forex (>= 0.85x)."""
        strategy = SpringVolumeStrategy()
        forex_context.volume_analysis = MockVolumeAnalysis(Decimal("0.90"))
        result = strategy.validate(forex_context, default_config)
        assert result.status == ValidationStatus.FAIL

    def test_asian_session_stricter_threshold(self, asian_forex_context, default_config):
        """Test Asian session uses stricter 0.60x threshold."""
        strategy = SpringVolumeStrategy()
        # 0.55 < 0.60 - should pass for Asian
        asian_forex_context.volume_analysis = MockVolumeAnalysis(Decimal("0.55"))
        result = strategy.validate(asian_forex_context, default_config)
        assert result.status == ValidationStatus.PASS
        assert result.metadata["threshold"] == 0.6

    def test_asian_session_fail_moderate_volume(self, asian_forex_context, default_config):
        """Test Asian session fails for moderate volume (>= 0.60x)."""
        strategy = SpringVolumeStrategy()
        # 0.65 >= 0.60 - should fail for Asian (but would pass for London)
        asian_forex_context.volume_analysis = MockVolumeAnalysis(Decimal("0.65"))
        result = strategy.validate(asian_forex_context, default_config)
        assert result.status == ValidationStatus.FAIL

    def test_validate_boundary_volume_equals_threshold(self, stock_context, default_config):
        """Test boundary case: volume_ratio == threshold fails (Spring requires < threshold)."""
        strategy = SpringVolumeStrategy()
        # Volume ratio exactly at 0.7 threshold - should FAIL (>= comparison)
        stock_context.volume_analysis = MockVolumeAnalysis(Decimal("0.7"))
        result = strategy.validate(stock_context, default_config)
        assert result.status == ValidationStatus.FAIL
        assert result.metadata["actual_volume_ratio"] == 0.7
        assert result.metadata["threshold"] == 0.7

    def test_get_threshold_uses_config(self, stock_context, default_config):
        """Test get_threshold uses config values."""
        strategy = SpringVolumeStrategy()
        default_config.spring_max_volume = Decimal("0.6")
        threshold = strategy.get_threshold(stock_context, default_config)
        assert threshold == Decimal("0.6")

    def test_metadata_includes_volume_source(self, stock_context, default_config):
        """Test metadata includes volume source (ACTUAL for stocks)."""
        strategy = SpringVolumeStrategy()
        result = strategy.validate(stock_context, default_config)
        assert result.metadata["volume_source"] == "ACTUAL"

    def test_metadata_includes_tick_for_forex(self, forex_context, default_config):
        """Test metadata includes volume source (TICK for forex)."""
        strategy = SpringVolumeStrategy()
        result = strategy.validate(forex_context, default_config)
        assert result.metadata["volume_source"] == "TICK"


# ============================================================================
# SOSVolumeStrategy Tests
# ============================================================================


class TestSOSVolumeStrategy:
    """Test SOSVolumeStrategy validation logic."""

    def test_pattern_type(self):
        """Test strategy returns correct pattern type."""
        strategy = SOSVolumeStrategy()
        assert strategy.pattern_type == "SOS"

    def test_volume_threshold_type(self):
        """Test strategy returns min threshold type."""
        strategy = SOSVolumeStrategy()
        assert strategy.volume_threshold_type == "min"

    def test_default_stock_threshold(self):
        """Test default stock threshold is 1.5."""
        strategy = SOSVolumeStrategy()
        assert strategy.default_stock_threshold == Decimal("1.5")

    def test_default_forex_threshold(self):
        """Test default forex threshold is 1.8."""
        strategy = SOSVolumeStrategy()
        assert strategy.default_forex_threshold == Decimal("1.8")

    def test_validate_pass_high_volume_stock(self, stock_context, default_config):
        """Test validation passes for high volume stock (> 1.5x)."""
        strategy = SOSVolumeStrategy()
        stock_context.pattern = MockPattern("SOS")
        stock_context.volume_analysis = MockVolumeAnalysis(Decimal("2.0"))
        result = strategy.validate(stock_context, default_config)
        assert result.status == ValidationStatus.PASS
        assert result.metadata["actual_volume_ratio"] == 2.0
        assert result.metadata["threshold"] == 1.5

    def test_validate_fail_low_volume_stock(self, stock_context, default_config):
        """Test validation fails for low volume stock (< 1.5x)."""
        strategy = SOSVolumeStrategy()
        stock_context.pattern = MockPattern("SOS")
        stock_context.volume_analysis = MockVolumeAnalysis(Decimal("1.2"))
        result = strategy.validate(stock_context, default_config)
        assert result.status == ValidationStatus.FAIL
        assert "too low" in result.reason

    def test_validate_pass_high_volume_forex(self, forex_context, default_config):
        """Test validation passes for high volume forex (> 1.8x)."""
        strategy = SOSVolumeStrategy()
        forex_context.pattern = MockPattern("SOS")
        forex_context.volume_analysis = MockVolumeAnalysis(Decimal("2.0"))
        result = strategy.validate(forex_context, default_config)
        assert result.status == ValidationStatus.PASS

    def test_validate_fail_moderate_volume_forex(self, forex_context, default_config):
        """Test validation fails for moderate volume forex (< 1.8x)."""
        strategy = SOSVolumeStrategy()
        forex_context.pattern = MockPattern("SOS")
        forex_context.volume_analysis = MockVolumeAnalysis(Decimal("1.6"))
        result = strategy.validate(forex_context, default_config)
        assert result.status == ValidationStatus.FAIL

    def test_asian_session_higher_threshold(self, asian_forex_context, default_config):
        """Test Asian session uses higher 2.0x threshold."""
        strategy = SOSVolumeStrategy()
        asian_forex_context.pattern = MockPattern("SOS")
        # 1.9 < 2.0 - should fail for Asian
        asian_forex_context.volume_analysis = MockVolumeAnalysis(Decimal("1.9"))
        result = strategy.validate(asian_forex_context, default_config)
        assert result.status == ValidationStatus.FAIL
        assert result.metadata["threshold"] == 2.0

    def test_asian_session_pass_very_high_volume(self, asian_forex_context, default_config):
        """Test Asian session passes for very high volume (>= 2.0x)."""
        strategy = SOSVolumeStrategy()
        asian_forex_context.pattern = MockPattern("SOS")
        asian_forex_context.volume_analysis = MockVolumeAnalysis(Decimal("2.5"))
        result = strategy.validate(asian_forex_context, default_config)
        assert result.status == ValidationStatus.PASS

    def test_validate_boundary_volume_equals_threshold(self, stock_context, default_config):
        """Test boundary case: volume_ratio == threshold passes (SOS requires >= threshold)."""
        strategy = SOSVolumeStrategy()
        stock_context.pattern = MockPattern("SOS")
        # Volume ratio exactly at 1.5 threshold - should PASS (< comparison, so == passes)
        stock_context.volume_analysis = MockVolumeAnalysis(Decimal("1.5"))
        result = strategy.validate(stock_context, default_config)
        assert result.status == ValidationStatus.PASS
        assert result.metadata["actual_volume_ratio"] == 1.5
        assert result.metadata["threshold"] == 1.5

    def test_get_threshold_uses_config(self, stock_context, default_config):
        """Test get_threshold uses config values."""
        strategy = SOSVolumeStrategy()
        default_config.sos_min_volume = Decimal("2.0")
        threshold = strategy.get_threshold(stock_context, default_config)
        assert threshold == Decimal("2.0")


# ============================================================================
# LPSVolumeStrategy Tests
# ============================================================================


class TestLPSVolumeStrategy:
    """Test LPSVolumeStrategy validation logic."""

    def test_pattern_type(self):
        """Test strategy returns correct pattern type."""
        strategy = LPSVolumeStrategy()
        assert strategy.pattern_type == "LPS"

    def test_volume_threshold_type(self):
        """Test strategy returns max threshold type."""
        strategy = LPSVolumeStrategy()
        assert strategy.volume_threshold_type == "max"

    def test_default_stock_threshold(self):
        """Test default stock threshold is 1.0."""
        strategy = LPSVolumeStrategy()
        assert strategy.default_stock_threshold == Decimal("1.0")

    def test_default_forex_threshold(self):
        """Test default forex threshold is 1.0."""
        strategy = LPSVolumeStrategy()
        assert strategy.default_forex_threshold == Decimal("1.0")

    def test_validate_pass_moderate_volume(self, stock_context, default_config):
        """Test validation passes for moderate volume (< 1.0x)."""
        strategy = LPSVolumeStrategy()
        stock_context.pattern = MockPattern("LPS")
        stock_context.volume_analysis = MockVolumeAnalysis(Decimal("0.8"))
        result = strategy.validate(stock_context, default_config)
        assert result.status == ValidationStatus.PASS

    def test_validate_fail_high_volume(self, stock_context, default_config):
        """Test validation fails for high volume (>= 1.0x)."""
        strategy = LPSVolumeStrategy()
        stock_context.pattern = MockPattern("LPS")
        stock_context.volume_analysis = MockVolumeAnalysis(Decimal("1.2"))
        result = strategy.validate(stock_context, default_config)
        assert result.status == ValidationStatus.FAIL

    def test_validate_boundary_volume_equals_threshold(self, stock_context, default_config):
        """Test boundary case: volume_ratio == threshold fails (LPS requires < threshold)."""
        strategy = LPSVolumeStrategy()
        stock_context.pattern = MockPattern("LPS")
        # Volume ratio exactly at 1.0 threshold - should FAIL (>= comparison)
        stock_context.volume_analysis = MockVolumeAnalysis(Decimal("1.0"))
        result = strategy.validate(stock_context, default_config)
        assert result.status == ValidationStatus.FAIL
        assert result.metadata["actual_volume_ratio"] == 1.0
        assert result.metadata["threshold"] == 1.0

    def test_absorption_not_enabled_by_default(self, stock_context, default_config):
        """Test absorption feature is not enabled by default."""
        strategy = LPSVolumeStrategy()
        stock_context.pattern = MockPattern("LPS")
        stock_context.volume_analysis = MockVolumeAnalysis(
            Decimal("1.2"), close_position=Decimal("0.8")
        )
        result = strategy.validate(stock_context, default_config)
        # Should fail because absorption is not enabled
        assert result.status == ValidationStatus.FAIL
        assert result.metadata.get("absorption_enabled") is None

    def test_absorption_pattern_pass_high_volume_with_strong_close(
        self, stock_context, default_config
    ):
        """Test absorption pattern passes with high volume and strong close."""
        strategy = LPSVolumeStrategy()
        stock_context.pattern = MockPattern("LPS")
        stock_context.volume_analysis = MockVolumeAnalysis(
            Decimal("1.2"),
            close_position=Decimal("0.8"),  # High volume  # Strong close
        )
        default_config.lps_allow_absorption = True
        result = strategy.validate(stock_context, default_config)
        # Should pass because absorption pattern detected
        assert result.status == ValidationStatus.PASS
        assert result.metadata["is_absorption_pattern"] is True
        assert result.metadata["threshold"] == 1.5  # Uses absorption threshold

    def test_absorption_pattern_fail_high_volume_weak_close(self, stock_context, default_config):
        """Test absorption fails with high volume but weak close."""
        strategy = LPSVolumeStrategy()
        stock_context.pattern = MockPattern("LPS")
        stock_context.volume_analysis = MockVolumeAnalysis(
            Decimal("1.2"),
            close_position=Decimal("0.5"),  # High volume  # Weak close
        )
        default_config.lps_allow_absorption = True
        result = strategy.validate(stock_context, default_config)
        # Should fail because close position too weak for absorption
        assert result.status == ValidationStatus.FAIL
        assert result.metadata["is_absorption_pattern"] is False

    def test_absorption_pattern_fail_very_high_volume(self, stock_context, default_config):
        """Test absorption fails even with strong close if volume too high."""
        strategy = LPSVolumeStrategy()
        stock_context.pattern = MockPattern("LPS")
        stock_context.volume_analysis = MockVolumeAnalysis(
            Decimal("1.8"),
            close_position=Decimal("0.8"),  # Very high volume  # Strong close
        )
        default_config.lps_allow_absorption = True
        result = strategy.validate(stock_context, default_config)
        # Should fail because volume exceeds absorption threshold (1.5x)
        assert result.status == ValidationStatus.FAIL
        assert "absorption" in result.reason.lower()

    def test_metadata_includes_absorption_info(self, stock_context, default_config):
        """Test metadata includes absorption pattern info when enabled."""
        strategy = LPSVolumeStrategy()
        stock_context.pattern = MockPattern("LPS")
        stock_context.volume_analysis = MockVolumeAnalysis(
            Decimal("0.8"), close_position=Decimal("0.6")
        )
        default_config.lps_allow_absorption = True
        result = strategy.validate(stock_context, default_config)
        assert result.metadata["absorption_enabled"] is True
        assert result.metadata["is_absorption_pattern"] is False
        assert result.metadata["close_position"] == 0.6
        assert result.metadata["absorption_threshold"] == 0.7

    def test_get_threshold_standard(self, stock_context, default_config):
        """Test get_threshold returns standard threshold without absorption."""
        strategy = LPSVolumeStrategy()
        stock_context.volume_analysis = MockVolumeAnalysis(Decimal("0.8"))
        threshold = strategy.get_threshold(stock_context, default_config)
        assert threshold == Decimal("1.0")

    def test_get_threshold_absorption(self, stock_context, default_config):
        """Test get_threshold returns absorption threshold when pattern detected."""
        strategy = LPSVolumeStrategy()
        stock_context.volume_analysis = MockVolumeAnalysis(
            Decimal("0.8"), close_position=Decimal("0.8")
        )
        default_config.lps_allow_absorption = True
        threshold = strategy.get_threshold(stock_context, default_config)
        assert threshold == Decimal("1.5")


# ============================================================================
# UTADVolumeStrategy Tests
# ============================================================================


class TestUTADVolumeStrategy:
    """Test UTADVolumeStrategy validation logic."""

    def test_pattern_type(self):
        """Test strategy returns correct pattern type."""
        strategy = UTADVolumeStrategy()
        assert strategy.pattern_type == "UTAD"

    def test_volume_threshold_type(self):
        """Test strategy returns min threshold type."""
        strategy = UTADVolumeStrategy()
        assert strategy.volume_threshold_type == "min"

    def test_default_stock_threshold(self):
        """Test default stock threshold is 1.2."""
        strategy = UTADVolumeStrategy()
        assert strategy.default_stock_threshold == Decimal("1.2")

    def test_default_forex_threshold(self):
        """Test default forex threshold is 2.5."""
        strategy = UTADVolumeStrategy()
        assert strategy.default_forex_threshold == Decimal("2.5")

    def test_validate_pass_high_volume_stock(self, stock_context, default_config):
        """Test validation passes for high volume stock (>= 1.2x)."""
        strategy = UTADVolumeStrategy()
        stock_context.pattern = MockPattern("UTAD")
        stock_context.volume_analysis = MockVolumeAnalysis(Decimal("1.5"))
        result = strategy.validate(stock_context, default_config)
        assert result.status == ValidationStatus.PASS
        assert result.metadata["actual_volume_ratio"] == 1.5
        assert result.metadata["threshold"] == 1.2

    def test_validate_fail_low_volume_stock(self, stock_context, default_config):
        """Test validation fails for low volume stock (< 1.2x)."""
        strategy = UTADVolumeStrategy()
        stock_context.pattern = MockPattern("UTAD")
        stock_context.volume_analysis = MockVolumeAnalysis(Decimal("1.0"))
        result = strategy.validate(stock_context, default_config)
        assert result.status == ValidationStatus.FAIL
        assert "too low" in result.reason

    def test_validate_pass_high_volume_forex(self, forex_context, default_config):
        """Test validation passes for high volume forex (>= 2.5x)."""
        strategy = UTADVolumeStrategy()
        forex_context.pattern = MockPattern("UTAD")
        forex_context.volume_analysis = MockVolumeAnalysis(Decimal("3.0"))
        result = strategy.validate(forex_context, default_config)
        assert result.status == ValidationStatus.PASS

    def test_validate_fail_moderate_volume_forex(self, forex_context, default_config):
        """Test validation fails for moderate volume forex (< 2.5x)."""
        strategy = UTADVolumeStrategy()
        forex_context.pattern = MockPattern("UTAD")
        forex_context.volume_analysis = MockVolumeAnalysis(Decimal("2.0"))
        result = strategy.validate(forex_context, default_config)
        assert result.status == ValidationStatus.FAIL

    def test_validate_boundary_volume_equals_threshold(self, stock_context, default_config):
        """Test boundary case: volume_ratio == threshold passes (UTAD requires >= threshold)."""
        strategy = UTADVolumeStrategy()
        stock_context.pattern = MockPattern("UTAD")
        # Volume ratio exactly at 1.2 threshold - should PASS (< comparison, so == passes)
        stock_context.volume_analysis = MockVolumeAnalysis(Decimal("1.2"))
        result = strategy.validate(stock_context, default_config)
        assert result.status == ValidationStatus.PASS
        assert result.metadata["actual_volume_ratio"] == 1.2
        assert result.metadata["threshold"] == 1.2

    def test_get_threshold_uses_config(self, stock_context, default_config):
        """Test get_threshold uses config values."""
        strategy = UTADVolumeStrategy()
        default_config.utad_min_volume = Decimal("1.5")
        threshold = strategy.get_threshold(stock_context, default_config)
        assert threshold == Decimal("1.5")


# ============================================================================
# Registration Tests
# ============================================================================


class TestRegisterAllStrategies:
    """Test strategy registration functionality."""

    def setup_method(self):
        """Clear registry before each test."""
        VolumeStrategyRegistry.clear()

    def teardown_method(self):
        """Clear registry after each test."""
        VolumeStrategyRegistry.clear()

    def test_register_all_strategies(self):
        """Test register_all_strategies registers all four strategies."""
        register_all_strategies()

        assert VolumeStrategyRegistry.count() == 4
        assert VolumeStrategyRegistry.has("SPRING")
        assert VolumeStrategyRegistry.has("SOS")
        assert VolumeStrategyRegistry.has("LPS")
        assert VolumeStrategyRegistry.has("UTAD")

    def test_registered_strategies_are_correct_types(self):
        """Test registered strategies are correct class types."""
        register_all_strategies()

        assert isinstance(VolumeStrategyRegistry.get("SPRING"), SpringVolumeStrategy)
        assert isinstance(VolumeStrategyRegistry.get("SOS"), SOSVolumeStrategy)
        assert isinstance(VolumeStrategyRegistry.get("LPS"), LPSVolumeStrategy)
        assert isinstance(VolumeStrategyRegistry.get("UTAD"), UTADVolumeStrategy)

    def test_registered_strategies_can_validate(self, stock_context, default_config):
        """Test registered strategies can perform validation."""
        register_all_strategies()

        for pattern_type in ["SPRING", "SOS", "LPS", "UTAD"]:
            strategy = VolumeStrategyRegistry.get(pattern_type)
            assert strategy is not None
            # Just verify validate can be called without error
            result = strategy.validate(stock_context, default_config)
            assert result.status in [ValidationStatus.PASS, ValidationStatus.FAIL]

    def test_case_insensitive_lookup(self):
        """Test registry lookup is case-insensitive."""
        register_all_strategies()

        assert VolumeStrategyRegistry.get("spring") is not None
        assert VolumeStrategyRegistry.get("SPRING") is not None
        assert VolumeStrategyRegistry.get("Spring") is not None

    def test_get_registered_patterns(self):
        """Test get_registered_patterns returns all pattern types."""
        register_all_strategies()

        patterns = VolumeStrategyRegistry.get_registered_patterns()
        assert set(patterns) == {"SPRING", "SOS", "LPS", "UTAD"}
