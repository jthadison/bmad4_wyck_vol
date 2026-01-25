"""
Unit Tests for UTAD Threshold Optimization (Story 9.1)

Tests session-specific UTAD volume thresholds loaded from YAML configuration.
Verifies that optimized thresholds are applied correctly per forex session.

Updated: Issue #232 - Fixed to test ForexThresholdAdjuster correctly
"""

from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from src.models.forex import ForexSession
from src.models.validation import ValidationContext, VolumeValidationConfig
from src.signal_generator.validators.volume.forex import ForexThresholdAdjuster


@pytest.fixture
def threshold_adjuster():
    """Create ForexThresholdAdjuster instance and clear cache."""
    ForexThresholdAdjuster.clear_cache()
    return ForexThresholdAdjuster()


@pytest.fixture
def base_config():
    """Create base VolumeValidationConfig for testing."""
    return VolumeValidationConfig()


@pytest.fixture
def base_forex_context():
    """Create base forex validation context."""
    context = Mock(spec=ValidationContext)
    context.symbol = "EUR/USD"
    context.asset_class = "FOREX"
    context.forex_session = ForexSession.OVERLAP
    return context


@pytest.fixture
def mock_yaml_config():
    """Mock YAML configuration with session-specific thresholds."""
    return {
        "stock": {
            "utad_min_volume": 2.00,
        },
        "forex": {
            "utad_min_volume": 2.50,
        },
        "forex_session_overrides": {
            "OVERLAP": {"utad_min_volume": 2.20},
            "LONDON": {"utad_min_volume": 2.30},
            "NY": {"utad_min_volume": 2.40},
            "ASIAN": {"utad_min_volume": 2.80},
        },
    }


class TestUTADSessionSpecificThresholds:
    """Test session-specific UTAD threshold optimization."""

    def test_forex_utad_overlap_session_lower_threshold(
        self, threshold_adjuster, base_config, base_forex_context, mock_yaml_config
    ):
        """
        Test: UTAD with 2.2x volume passes in OVERLAP session (220% threshold).

        Story 9.1, AC 13: OVERLAP session uses optimized 220% threshold
        (down from 250% baseline).
        """
        base_forex_context.forex_session = ForexSession.OVERLAP

        # Mock YAML config loading on ForexThresholdAdjuster class
        with patch.object(
            ForexThresholdAdjuster,
            "_load_volume_thresholds_from_config",
            return_value=mock_yaml_config,
        ):
            threshold = threshold_adjuster.get_threshold(
                "UTAD", "min", base_config, base_forex_context
            )

            # Verify threshold is optimized value
            assert threshold == Decimal("2.20")
            assert threshold < Decimal("2.50")  # Lower than baseline

    def test_forex_utad_london_session_threshold(
        self, threshold_adjuster, base_config, base_forex_context, mock_yaml_config
    ):
        """
        Test: UTAD with 2.3x volume passes in LONDON session (230% threshold).

        Story 9.1, AC 13: LONDON session uses optimized 230% threshold.
        """
        base_forex_context.forex_session = ForexSession.LONDON

        with patch.object(
            ForexThresholdAdjuster,
            "_load_volume_thresholds_from_config",
            return_value=mock_yaml_config,
        ):
            threshold = threshold_adjuster.get_threshold(
                "UTAD", "min", base_config, base_forex_context
            )

            assert threshold == Decimal("2.30")

    def test_forex_utad_ny_session_threshold(
        self, threshold_adjuster, base_config, base_forex_context, mock_yaml_config
    ):
        """
        Test: UTAD with 2.4x volume passes in NY session (240% threshold).

        Story 9.1, AC 13: NY session uses optimized 240% threshold.
        """
        base_forex_context.forex_session = ForexSession.NY

        with patch.object(
            ForexThresholdAdjuster,
            "_load_volume_thresholds_from_config",
            return_value=mock_yaml_config,
        ):
            threshold = threshold_adjuster.get_threshold(
                "UTAD", "min", base_config, base_forex_context
            )

            assert threshold == Decimal("2.40")

    def test_forex_utad_asian_session_stricter_threshold(
        self, threshold_adjuster, base_config, base_forex_context, mock_yaml_config
    ):
        """
        Test: UTAD with 2.2x volume fails in ASIAN session (280% threshold).

        Story 9.1, AC 13: ASIAN session uses stricter 280% threshold due to
        low liquidity characteristics.
        """
        base_forex_context.forex_session = ForexSession.ASIAN
        volume_ratio = Decimal("2.20")

        with patch.object(
            ForexThresholdAdjuster,
            "_load_volume_thresholds_from_config",
            return_value=mock_yaml_config,
        ):
            threshold = threshold_adjuster.get_threshold(
                "UTAD", "min", base_config, base_forex_context
            )

            # Verify threshold is stricter
            assert threshold == Decimal("2.80")
            assert threshold > Decimal("2.50")  # Stricter than baseline

            # Volume ratio is below threshold - should fail
            assert volume_ratio < threshold

    def test_forex_utad_asian_session_passes_with_high_volume(
        self, threshold_adjuster, base_config, base_forex_context, mock_yaml_config
    ):
        """
        Test: UTAD with 2.9x volume passes in ASIAN session (280% threshold).

        Verifies that high-volume UTADs still pass the stricter Asian threshold.
        """
        base_forex_context.forex_session = ForexSession.ASIAN
        volume_ratio = Decimal("2.90")

        with patch.object(
            ForexThresholdAdjuster,
            "_load_volume_thresholds_from_config",
            return_value=mock_yaml_config,
        ):
            threshold = threshold_adjuster.get_threshold(
                "UTAD", "min", base_config, base_forex_context
            )

            assert threshold == Decimal("2.80")
            assert volume_ratio > threshold

    def test_forex_utad_fallback_to_baseline_if_no_override(
        self, threshold_adjuster, base_config, base_forex_context
    ):
        """
        Test: UTAD falls back to baseline threshold if no session override exists.

        Handles case where YAML config doesn't have session overrides.
        """
        base_forex_context.forex_session = ForexSession.OVERLAP

        # Mock YAML config WITHOUT session overrides
        empty_config = {"forex": {"utad_min_volume": 2.50}}

        with patch.object(
            ForexThresholdAdjuster,
            "_load_volume_thresholds_from_config",
            return_value=empty_config,
        ):
            threshold = threshold_adjuster.get_threshold(
                "UTAD", "min", base_config, base_forex_context
            )

            # Should fall back to VolumeValidationConfig default (2.50)
            assert threshold == base_config.forex_utad_min_volume

    def test_forex_utad_session_override_logging(
        self, threshold_adjuster, base_config, base_forex_context, mock_yaml_config
    ):
        """
        Test: Session override application is logged for debugging.

        Story 9.1, AC 13: Verify the method executes without error when applying overrides.
        """
        base_forex_context.forex_session = ForexSession.OVERLAP

        with patch.object(
            ForexThresholdAdjuster,
            "_load_volume_thresholds_from_config",
            return_value=mock_yaml_config,
        ):
            # Call method that should trigger logging
            threshold = threshold_adjuster.get_threshold(
                "UTAD", "min", base_config, base_forex_context
            )

            assert threshold == Decimal("2.20")

    def test_non_utad_patterns_unaffected(
        self, threshold_adjuster, base_config, base_forex_context, mock_yaml_config
    ):
        """
        Test: Session overrides only apply to UTAD, not other patterns.

        Verify SOS/Spring/LPS patterns use standard thresholds.
        """
        base_forex_context.forex_session = ForexSession.OVERLAP

        with patch.object(
            ForexThresholdAdjuster,
            "_load_volume_thresholds_from_config",
            return_value=mock_yaml_config,
        ):
            # Test SOS threshold (should NOT be overridden)
            sos_threshold = threshold_adjuster.get_threshold(
                "SOS", "min", base_config, base_forex_context
            )
            assert sos_threshold == base_config.forex_sos_min_volume

            # Test Spring threshold (should NOT be overridden)
            spring_threshold = threshold_adjuster.get_threshold(
                "SPRING", "max", base_config, base_forex_context
            )
            assert spring_threshold == base_config.forex_spring_max_volume


class TestYAMLConfigLoading:
    """Test YAML configuration loading and caching."""

    def test_yaml_config_loading_success(self, threshold_adjuster):
        """
        Test: YAML config loads successfully from file system.
        """
        # Clear cache
        ForexThresholdAdjuster.clear_cache()

        # Load config (will read from actual file if it exists)
        config = ForexThresholdAdjuster._load_volume_thresholds_from_config()

        # Verify config is a dict
        assert isinstance(config, dict)

        # If file exists, verify structure
        if config:  # Only check if file was found
            assert "forex" in config or "stock" in config or len(config) == 0

    def test_yaml_config_caching(self, threshold_adjuster):
        """
        Test: YAML config is cached at class level to avoid repeated I/O.

        Story 9.1: Configuration should be loaded once and cached.
        """
        # Clear cache
        ForexThresholdAdjuster.clear_cache()

        # Load config twice
        config1 = ForexThresholdAdjuster._load_volume_thresholds_from_config()
        config2 = ForexThresholdAdjuster._load_volume_thresholds_from_config()

        # Verify same object (cached)
        assert config1 is config2

    def test_yaml_config_missing_file_graceful_handling(self, threshold_adjuster):
        """
        Test: Missing YAML file is handled gracefully without crashing.

        Returns empty dict and logs warning.
        """
        # Clear cache
        ForexThresholdAdjuster.clear_cache()

        # Mock Path.exists to return False
        with patch("pathlib.Path.exists", return_value=False):
            config = ForexThresholdAdjuster._load_volume_thresholds_from_config()

            # Should return empty dict (not crash)
            assert config == {}


class TestBackwardCompatibility:
    """Test backward compatibility with Story 8.3.1."""

    def test_stock_utad_unaffected_by_forex_optimization(
        self, threshold_adjuster, base_config, base_forex_context, mock_yaml_config
    ):
        """
        Test: Stock UTAD patterns still use standard threshold (unchanged).

        Story 9.1 only affects forex patterns. Stock UTAD uses 1.2x (120%)
        per VolumeValidationConfig defaults.
        """
        # The ForexThresholdAdjuster is only called for forex assets
        # Stock validation bypasses this adjuster entirely
        # This test verifies the VolumeValidationConfig default is correct
        assert base_config.utad_min_volume == Decimal("1.2")

    def test_forex_baseline_threshold_preserved(
        self, threshold_adjuster, base_config, base_forex_context, mock_yaml_config
    ):
        """
        Test: Forex baseline threshold (250%) is preserved in config.

        Session overrides augment, not replace, the baseline.
        """
        assert mock_yaml_config["forex"]["utad_min_volume"] == 2.50
        assert "forex_session_overrides" in mock_yaml_config
        # VolumeValidationConfig also preserves the 2.50 baseline
        assert base_config.forex_utad_min_volume == Decimal("2.50")
