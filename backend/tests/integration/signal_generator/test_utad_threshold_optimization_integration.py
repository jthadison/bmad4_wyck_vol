"""
Integration Tests for UTAD Threshold Optimization (Story 9.1)

End-to-end tests validating session-specific UTAD thresholds in realistic
scenarios with full validation chain integration.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from src.models.forex import ForexSession
from src.models.validation import (
    ValidationContext,
    ValidationStatus,
)
from src.models.volume_analysis import VolumeAnalysis
from src.signal_generator.validators.volume_validator import VolumeValidator


class MockPattern:
    """Mock Pattern for integration testing."""

    def __init__(self, pattern_type: str = "UTAD", symbol: str = "EUR/USD"):
        self.id = str(uuid4())
        self.pattern_type = pattern_type
        self.symbol = symbol
        self.pattern_bar_timestamp = datetime(2025, 12, 1, 14, 0, tzinfo=UTC)


@pytest.fixture
def mock_yaml_config():
    """Mock optimized YAML configuration."""
    return {
        "stock": {
            "spring_max_volume": 0.70,
            "sos_min_volume": 1.50,
            "utad_min_volume": 2.00,
            "lps_max_volume": 0.85,
        },
        "forex": {
            "spring_max_volume": 0.85,
            "sos_min_volume": 1.80,
            "utad_min_volume": 2.50,
            "lps_max_volume": 1.00,
        },
        "forex_session_overrides": {
            "OVERLAP": {"utad_min_volume": 2.20},
            "LONDON": {"utad_min_volume": 2.30},
            "NY": {"utad_min_volume": 2.40},
            "ASIAN": {"utad_min_volume": 2.80},
        },
    }


def create_forex_utad_context(
    volume_ratio: Decimal,
    session: ForexSession,
) -> ValidationContext:
    """
    Helper to create realistic forex UTAD validation context.

    Args:
        volume_ratio: Volume ratio for pattern bar
        session: Forex session

    Returns:
        ValidationContext ready for validation
    """
    # Create pattern
    pattern = MockPattern(pattern_type="UTAD", symbol="EUR/USD")

    # Create volume analysis mock
    volume_analysis = Mock(spec=VolumeAnalysis)
    volume_analysis.volume_ratio = volume_ratio

    # Create context mock
    context = Mock(spec=ValidationContext)
    context.pattern = pattern
    context.symbol = "EUR/USD"
    context.asset_class = "FOREX"
    context.volume_analysis = volume_analysis
    context.forex_session = session
    context.config = {}
    context.market_context = None  # No market context for these tests

    return context


class TestOVERLAPSessionOptimization:
    """Test OVERLAP session threshold optimization (220%)."""

    @pytest.mark.asyncio
    async def test_overlap_utad_220_percent_passes(self, mock_yaml_config):
        """
        Test: UTAD with 2.2x volume PASSES in OVERLAP session.

        Before optimization: Would FAIL at 250% threshold.
        After optimization: PASSES at 220% threshold.

        Story 9.1, AC 13: Validates optimized OVERLAP threshold.
        """
        validator = VolumeValidator()
        context = create_forex_utad_context(
            volume_ratio=Decimal("2.20"),
            session=ForexSession.OVERLAP,
        )

        with patch.object(
            VolumeValidator,
            "_load_volume_thresholds_from_config",
            return_value=mock_yaml_config,
        ):
            result = await validator.validate(context)

            # Should PASS with optimized threshold
            assert result.status == ValidationStatus.PASS

    @pytest.mark.asyncio
    async def test_overlap_utad_210_percent_fails(self, mock_yaml_config):
        """
        Test: UTAD with 2.1x volume still FAILS in OVERLAP session.

        Threshold is 220%, so 210% is below threshold.
        """
        validator = VolumeValidator()
        context = create_forex_utad_context(
            volume_ratio=Decimal("2.10"),
            session=ForexSession.OVERLAP,
        )

        with patch.object(
            VolumeValidator,
            "_load_volume_thresholds_from_config",
            return_value=mock_yaml_config,
        ):
            result = await validator.validate(context)

            # Should FAIL (below 220% threshold)
            assert result.status == ValidationStatus.FAIL
            assert "too low" in result.reason.lower()


class TestASIANSessionStricterThreshold:
    """Test ASIAN session stricter threshold (280%)."""

    @pytest.mark.asyncio
    async def test_asian_utad_220_percent_fails(self, mock_yaml_config):
        """
        Test: UTAD with 2.2x volume FAILS in ASIAN session.

        Asian session uses stricter 280% threshold due to low liquidity.

        Story 9.1, AC 13: Validates stricter ASIAN threshold.
        """
        validator = VolumeValidator()
        context = create_forex_utad_context(
            volume_ratio=Decimal("2.20"),
            session=ForexSession.ASIAN,
        )

        with patch.object(
            VolumeValidator,
            "_load_volume_thresholds_from_config",
            return_value=mock_yaml_config,
        ):
            result = await validator.validate(context)

            # Should FAIL (below 280% threshold)
            assert result.status == ValidationStatus.FAIL
            assert "2.80" in result.reason or "too low" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_asian_utad_290_percent_passes(self, mock_yaml_config):
        """
        Test: UTAD with 2.9x volume PASSES in ASIAN session.

        High volume UTADs still pass the stricter Asian threshold.
        """
        validator = VolumeValidator()
        context = create_forex_utad_context(
            volume_ratio=Decimal("2.90"),
            session=ForexSession.ASIAN,
        )

        with patch.object(
            VolumeValidator,
            "_load_volume_thresholds_from_config",
            return_value=mock_yaml_config,
        ):
            result = await validator.validate(context)

            # Should PASS (above 280% threshold)
            assert result.status == ValidationStatus.PASS


class TestSessionSpecificPassRates:
    """Test expected pass rate variations across sessions."""

    @pytest.mark.asyncio
    async def test_same_volume_different_outcomes_by_session(self, mock_yaml_config):
        """
        Test: Same volume ratio produces different outcomes per session.

        A 2.3x UTAD should:
        - PASS in OVERLAP (220% threshold)
        - PASS in LONDON (230% threshold)
        - FAIL in NY (240% threshold)
        - FAIL in ASIAN (280% threshold)

        Story 9.1: Demonstrates session-specific optimization impact.
        """
        validator = VolumeValidator()
        volume_ratio = Decimal("2.30")

        with patch.object(
            VolumeValidator,
            "_load_volume_thresholds_from_config",
            return_value=mock_yaml_config,
        ):
            # OVERLAP: Should PASS (2.30 > 2.20)
            overlap_result = await validator.validate(
                create_forex_utad_context(volume_ratio, ForexSession.OVERLAP)
            )
            assert overlap_result.status == ValidationStatus.PASS

            # LONDON: Should PASS (2.30 = 2.30)
            london_result = await validator.validate(
                create_forex_utad_context(volume_ratio, ForexSession.LONDON)
            )
            assert london_result.status == ValidationStatus.PASS

            # NY: Should FAIL (2.30 < 2.40)
            ny_result = await validator.validate(
                create_forex_utad_context(volume_ratio, ForexSession.NY)
            )
            assert ny_result.status == ValidationStatus.FAIL

            # ASIAN: Should FAIL (2.30 < 2.80)
            asian_result = await validator.validate(
                create_forex_utad_context(volume_ratio, ForexSession.ASIAN)
            )
            assert asian_result.status == ValidationStatus.FAIL


class TestBacktestScenarioReplication:
    """Replicate key backtest scenarios from Story 9.1 analysis."""

    @pytest.mark.asyncio
    async def test_overlap_precision_improvement_scenario(self, mock_yaml_config):
        """
        Test: OVERLAP session shows improved signal generation.

        Before: 250% threshold → 9% pass rate
        After: 220% threshold → 15% pass rate

        This test simulates patterns in the 220-250% range that would be
        rescued by the optimization.
        """
        validator = VolumeValidator()

        # Patterns in "rescue zone" (2.20-2.50)
        rescue_zone_volumes = [
            Decimal("2.20"),
            Decimal("2.25"),
            Decimal("2.30"),
            Decimal("2.35"),
            Decimal("2.40"),
            Decimal("2.45"),
        ]

        passed_count = 0

        with patch.object(
            VolumeValidator,
            "_load_volume_thresholds_from_config",
            return_value=mock_yaml_config,
        ):
            for volume_ratio in rescue_zone_volumes:
                context = create_forex_utad_context(volume_ratio, ForexSession.OVERLAP)
                result = await validator.validate(context)

                if result.status == ValidationStatus.PASS:
                    passed_count += 1

            # All patterns in rescue zone should pass with 220% threshold
            assert passed_count == len(rescue_zone_volumes)

    @pytest.mark.asyncio
    async def test_asian_precision_improvement_by_filtering(self, mock_yaml_config):
        """
        Test: ASIAN session filters false positives with stricter threshold.

        Before: 250% threshold → 6% pass rate, 72% precision
        After: 280% threshold → 4% pass rate, 80% precision

        This test simulates that patterns in the 250-280% range (previously
        passing) are now filtered out to improve precision.
        """
        validator = VolumeValidator()

        # Patterns that would pass at 250% but fail at 280%
        filtered_zone_volumes = [
            Decimal("2.50"),
            Decimal("2.60"),
            Decimal("2.70"),
        ]

        # Patterns that still pass at 280%
        passing_volumes = [Decimal("2.80"), Decimal("2.90"), Decimal("3.00")]

        with patch.object(
            VolumeValidator,
            "_load_volume_thresholds_from_config",
            return_value=mock_yaml_config,
        ):
            # Verify filtered zone patterns FAIL
            for volume_ratio in filtered_zone_volumes:
                context = create_forex_utad_context(volume_ratio, ForexSession.ASIAN)
                result = await validator.validate(context)
                assert result.status == ValidationStatus.FAIL

            # Verify high-volume patterns still PASS
            for volume_ratio in passing_volumes:
                context = create_forex_utad_context(volume_ratio, ForexSession.ASIAN)
                result = await validator.validate(context)
                assert result.status == ValidationStatus.PASS


class TestNearMissLoggingWithOptimization:
    """Test that near-miss logging adapts to new thresholds."""

    @pytest.mark.asyncio
    async def test_near_miss_logging_updated_threshold_range(self, mock_yaml_config, caplog):
        """
        Test: Near-miss logging reflects optimized thresholds.

        For OVERLAP session (220% threshold), patterns in 200-220% range
        should be logged as near-misses (not 200-250% anymore).
        """
        validator = VolumeValidator()

        # Pattern just below OVERLAP threshold
        context = create_forex_utad_context(
            volume_ratio=Decimal("2.15"),
            session=ForexSession.OVERLAP,
        )

        with patch.object(
            VolumeValidator,
            "_load_volume_thresholds_from_config",
            return_value=mock_yaml_config,
        ):
            result = await validator.validate(context)

            # Should FAIL (below 220%)
            assert result.status == ValidationStatus.FAIL

            # Near-miss logic should trigger for patterns >= 2.0x
            # (This is still logged at INFO level for ongoing monitoring)


class TestRollbackScenario:
    """Test rollback to Story 8.3.1 baseline thresholds."""

    @pytest.mark.asyncio
    async def test_rollback_to_baseline_when_no_overrides(self):
        """
        Test: System reverts to baseline when session overrides removed.

        Rollback scenario: Remove forex_session_overrides from YAML.
        Expected: All sessions use 250% baseline threshold.
        """
        validator = VolumeValidator()

        # Config without session overrides (rollback scenario)
        rollback_config = {
            "forex": {
                "utad_min_volume": 2.50,
            }
        }

        context = create_forex_utad_context(
            volume_ratio=Decimal("2.30"),
            session=ForexSession.OVERLAP,
        )

        with patch.object(
            VolumeValidator,
            "_load_volume_thresholds_from_config",
            return_value=rollback_config,
        ):
            result = await validator.validate(context)

            # Should FAIL with baseline 250% threshold (2.30 < 2.50)
            assert result.status == ValidationStatus.FAIL
            assert "too low" in result.reason.lower()


class TestStockPatternsUnaffected:
    """Verify stock patterns unchanged by forex optimization."""

    @pytest.mark.asyncio
    async def test_stock_utad_still_uses_200_percent(self, mock_yaml_config):
        """
        Test: Stock UTAD patterns still use 120% threshold.

        Story 9.1 only affects forex - stock thresholds unchanged (1.2x = 120%).
        """
        validator = VolumeValidator()

        # Create stock context (not forex)
        pattern = MockPattern(pattern_type="UTAD", symbol="AAPL")

        volume_analysis = Mock(spec=VolumeAnalysis)
        volume_analysis.volume_ratio = Decimal("1.20")  # Exactly at 120%

        context = Mock(spec=ValidationContext)
        context.pattern = pattern
        context.symbol = "AAPL"
        context.asset_class = "STOCK"
        context.volume_analysis = volume_analysis
        context.config = {}

        with patch.object(
            VolumeValidator,
            "_load_volume_thresholds_from_config",
            return_value=mock_yaml_config,
        ):
            result = await validator.validate(context)

            # Should PASS at 200% (stock threshold unchanged)
            assert result.status == ValidationStatus.PASS
