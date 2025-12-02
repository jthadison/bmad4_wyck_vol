"""
Unit tests for VolumeValidator (Story 8.3).

Tests pattern-specific volume validation rules:
- Spring: volume_ratio < 0.7x
- SOS: volume_ratio >= 1.5x
- LPS: volume_ratio < 1.0x OR absorption pattern
- UTAD: volume_ratio >= 1.2x
- Test confirmation: test_volume < pattern_volume

Author: Story 8.3
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from src.models.effort_result import EffortResult
from src.models.ohlcv import OHLCVBar
from src.models.validation import (
    ValidationContext,
    ValidationStatus,
)
from src.models.volume_analysis import VolumeAnalysis
from src.signal_generator.validators.volume_validator import VolumeValidator

# ============================================================================
# Test Fixtures
# ============================================================================


class MockPattern:
    """Mock Pattern for testing without full Pattern model dependency."""

    def __init__(
        self,
        pattern_type: str,
        test_confirmed: bool = False,
        pattern_id: str | None = None,
    ):
        self.id = uuid4() if pattern_id is None else pattern_id
        self.pattern_type = pattern_type
        self.test_confirmed = test_confirmed
        self.pattern_bar_timestamp = datetime(2024, 3, 13, 13, 0, tzinfo=UTC)


def create_test_ohlcv_bar(
    symbol: str = "AAPL",
    timeframe: str = "1h",
    timestamp: datetime | None = None,
    volume: int = 1000000,
) -> OHLCVBar:
    """Create a test OHLCV bar."""
    if timestamp is None:
        timestamp = datetime(2024, 3, 13, 13, 0, tzinfo=UTC)

    return OHLCVBar(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("99.00"),
        close=Decimal("100.50"),
        volume=volume,
        spread=Decimal("2.00"),
    )


@pytest.fixture
def volume_validator() -> VolumeValidator:
    """VolumeValidator instance."""
    return VolumeValidator()


def create_validation_context(
    pattern_type: str,
    volume_ratio: Decimal,
    test_confirmed: bool = False,
    test_volume_ratio: Decimal | None = None,
    config_overrides: dict[str, Any] | None = None,
    close_position: Decimal = Decimal("0.7"),
    effort_result: EffortResult = EffortResult.NORMAL,
) -> ValidationContext:
    """
    Helper to create ValidationContext for testing.

    Parameters:
    -----------
    pattern_type : str
        Pattern type (SPRING, SOS, LPS, UTAD)
    volume_ratio : Decimal
        Volume ratio of pattern bar
    test_confirmed : bool
        Whether pattern has test confirmation
    test_volume_ratio : Decimal | None
        Volume ratio of test bar (if test_confirmed=True)
    config_overrides : dict | None
        Configuration overrides for thresholds
    close_position : Decimal
        Close position within bar range (for LPS absorption)
    effort_result : EffortResult
        Effort vs result classification (for LPS absorption)
    """
    pattern = MockPattern(pattern_type=pattern_type, test_confirmed=test_confirmed)

    # Create OHLCV bar for VolumeAnalysis
    bar = create_test_ohlcv_bar()

    volume_analysis = VolumeAnalysis(
        bar=bar,
        volume_ratio=volume_ratio,
        spread_ratio=Decimal("1.0"),
        close_position=close_position,
        effort_result=effort_result,
    )

    config: dict[str, Any] = {}
    if config_overrides:
        config["volume_validation"] = config_overrides

    return ValidationContext(
        pattern=pattern,
        symbol="AAPL",
        timeframe="1h",
        volume_analysis=volume_analysis,
        test_volume_ratio=test_volume_ratio,
        config=config,
    )


# ============================================================================
# Spring Volume Validation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_spring_low_volume_passes(volume_validator: VolumeValidator) -> None:
    """Spring with volume_ratio = 0.5x should PASS (below 0.7x threshold)."""
    context = create_validation_context(pattern_type="SPRING", volume_ratio=Decimal("0.5"))
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.PASS
    assert result.stage == "Volume"
    assert result.validator_id == "VOLUME_VALIDATOR"
    assert result.reason is None


@pytest.mark.asyncio
async def test_spring_at_boundary_below_passes(volume_validator: VolumeValidator) -> None:
    """Spring with volume_ratio = 0.69x should PASS (just under threshold)."""
    context = create_validation_context(pattern_type="SPRING", volume_ratio=Decimal("0.69"))
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.PASS


@pytest.mark.asyncio
async def test_spring_at_threshold_fails(volume_validator: VolumeValidator) -> None:
    """Spring with volume_ratio = 0.7x should FAIL (at threshold - FR12 non-negotiable)."""
    context = create_validation_context(pattern_type="SPRING", volume_ratio=Decimal("0.7"))
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "Spring volume too high" in result.reason
    assert "0.7" in result.reason
    assert result.metadata is not None
    assert result.metadata["actual_volume_ratio"] == 0.7
    assert result.metadata["threshold"] == 0.7
    assert result.metadata["pattern_type"] == "SPRING"


@pytest.mark.asyncio
async def test_spring_high_volume_fails_ac7(volume_validator: VolumeValidator) -> None:
    """Spring with volume_ratio = 0.8x should FAIL (AC 7 - explicit requirement)."""
    context = create_validation_context(pattern_type="SPRING", volume_ratio=Decimal("0.8"))
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "Spring volume too high" in result.reason
    assert "0.8" in result.reason
    assert result.metadata["actual_volume_ratio"] == 0.8
    assert result.metadata["threshold"] == 0.7
    assert result.metadata["symbol"] == "AAPL"


@pytest.mark.asyncio
async def test_spring_very_high_volume_fails(volume_validator: VolumeValidator) -> None:
    """Spring with volume_ratio = 1.2x should FAIL (way over threshold)."""
    context = create_validation_context(pattern_type="SPRING", volume_ratio=Decimal("1.2"))
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "Spring volume too high" in result.reason
    assert result.metadata["actual_volume_ratio"] == 1.2


# ============================================================================
# SOS Volume Validation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_sos_high_volume_passes(volume_validator: VolumeValidator) -> None:
    """SOS with volume_ratio = 2.0x should PASS (above 1.5x threshold)."""
    context = create_validation_context(pattern_type="SOS", volume_ratio=Decimal("2.0"))
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.PASS
    assert result.stage == "Volume"


@pytest.mark.asyncio
async def test_sos_at_threshold_passes(volume_validator: VolumeValidator) -> None:
    """SOS with volume_ratio = 1.5x should PASS (at threshold)."""
    context = create_validation_context(pattern_type="SOS", volume_ratio=Decimal("1.5"))
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.PASS


@pytest.mark.asyncio
async def test_sos_just_under_threshold_fails(volume_validator: VolumeValidator) -> None:
    """SOS with volume_ratio = 1.49x should FAIL (just under threshold)."""
    context = create_validation_context(pattern_type="SOS", volume_ratio=Decimal("1.49"))
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "SOS volume too low" in result.reason
    assert "1.49" in result.reason
    assert result.metadata["actual_volume_ratio"] == 1.49
    assert result.metadata["threshold"] == 1.5


@pytest.mark.asyncio
async def test_sos_low_volume_fails_ac8(volume_validator: VolumeValidator) -> None:
    """SOS with volume_ratio = 1.2x should FAIL (AC 8 - explicit requirement)."""
    context = create_validation_context(pattern_type="SOS", volume_ratio=Decimal("1.2"))
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "SOS volume too low" in result.reason
    assert "1.2" in result.reason
    assert result.metadata["actual_volume_ratio"] == 1.2
    assert result.metadata["pattern_type"] == "SOS"


@pytest.mark.asyncio
async def test_sos_very_low_volume_fails(volume_validator: VolumeValidator) -> None:
    """SOS with volume_ratio = 0.8x should FAIL (way under threshold)."""
    context = create_validation_context(pattern_type="SOS", volume_ratio=Decimal("0.8"))
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "SOS volume too low" in result.reason


# ============================================================================
# LPS Volume Validation Tests (Standard + WYCKOFF ENHANCEMENT)
# ============================================================================


@pytest.mark.asyncio
async def test_lps_quiet_low_volume_passes(volume_validator: VolumeValidator) -> None:
    """LPS with volume_ratio = 0.6x should PASS (standard quiet LPS)."""
    context = create_validation_context(pattern_type="LPS", volume_ratio=Decimal("0.6"))
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.PASS
    assert result.stage == "Volume"


@pytest.mark.asyncio
async def test_lps_just_under_threshold_passes(volume_validator: VolumeValidator) -> None:
    """LPS with volume_ratio = 0.99x should PASS (just under threshold)."""
    context = create_validation_context(pattern_type="LPS", volume_ratio=Decimal("0.99"))
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.PASS


@pytest.mark.asyncio
async def test_lps_at_threshold_fails_no_absorption(volume_validator: VolumeValidator) -> None:
    """LPS with volume_ratio = 1.0x should FAIL (at threshold, no absorption enabled)."""
    context = create_validation_context(pattern_type="LPS", volume_ratio=Decimal("1.0"))
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "LPS volume too high" in result.reason
    assert "1.0" in result.reason


@pytest.mark.asyncio
async def test_lps_high_volume_fails_no_absorption(volume_validator: VolumeValidator) -> None:
    """LPS with volume_ratio = 1.2x should FAIL (too high, no absorption)."""
    context = create_validation_context(pattern_type="LPS", volume_ratio=Decimal("1.2"))
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "LPS volume too high" in result.reason
    assert result.metadata["actual_volume_ratio"] == 1.2
    assert result.metadata["threshold"] == 1.0


@pytest.mark.asyncio
async def test_lps_absorption_pattern_passes(volume_validator: VolumeValidator) -> None:
    """
    LPS absorption pattern should PASS (WYCKOFF ENHANCEMENT).

    Criteria: volume_ratio=1.3, close_position=0.8, effort_result=ABSORPTION,
    lps_allow_absorption=True
    """
    config_overrides = {"lps_allow_absorption": True}
    context = create_validation_context(
        pattern_type="LPS",
        volume_ratio=Decimal("1.3"),
        close_position=Decimal("0.8"),
        effort_result=EffortResult.ABSORPTION,
        config_overrides=config_overrides,
    )
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.PASS
    assert result.metadata is not None
    assert result.metadata["lps_type"] == "absorption_shakeout"
    assert result.metadata["volume_ratio"] == 1.3
    assert result.metadata["close_position"] == 0.8
    assert result.metadata["effort_result"] == "ABSORPTION"


@pytest.mark.asyncio
async def test_lps_absorption_low_close_fails(volume_validator: VolumeValidator) -> None:
    """
    LPS absorption with low close_position should FAIL.

    Criteria: volume_ratio=1.3, close_position=0.5 (below 0.7), effort_result=ABSORPTION
    """
    config_overrides = {"lps_allow_absorption": True}
    context = create_validation_context(
        pattern_type="LPS",
        volume_ratio=Decimal("1.3"),
        close_position=Decimal("0.5"),
        effort_result=EffortResult.ABSORPTION,
        config_overrides=config_overrides,
    )
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "LPS volume too high" in result.reason
    assert "absorption pattern criteria not met" in result.reason


@pytest.mark.asyncio
async def test_lps_absorption_not_absorption_effort_fails(
    volume_validator: VolumeValidator,
) -> None:
    """
    LPS with high volume but effort_result != ABSORPTION should FAIL.

    Criteria: volume_ratio=1.3, close_position=0.8, effort_result=NORMAL (not ABSORPTION)
    """
    config_overrides = {"lps_allow_absorption": True}
    context = create_validation_context(
        pattern_type="LPS",
        volume_ratio=Decimal("1.3"),
        close_position=Decimal("0.8"),
        effort_result=EffortResult.NORMAL,
        config_overrides=config_overrides,
    )
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "absorption pattern criteria not met" in result.reason


@pytest.mark.asyncio
async def test_lps_absorption_excessive_volume_fails(volume_validator: VolumeValidator) -> None:
    """
    LPS absorption with volume > 1.5x should FAIL (exceeds absorption threshold).

    Criteria: volume_ratio=1.6, close_position=0.8, effort_result=ABSORPTION
    """
    config_overrides = {"lps_allow_absorption": True}
    context = create_validation_context(
        pattern_type="LPS",
        volume_ratio=Decimal("1.6"),
        close_position=Decimal("0.8"),
        effort_result=EffortResult.ABSORPTION,
        config_overrides=config_overrides,
    )
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "absorption pattern criteria not met" in result.reason


@pytest.mark.asyncio
async def test_lps_absorption_disabled_fails(volume_validator: VolumeValidator) -> None:
    """
    LPS absorption pattern with lps_allow_absorption=False should FAIL.

    Criteria: Perfect absorption pattern but feature disabled (default)
    """
    context = create_validation_context(
        pattern_type="LPS",
        volume_ratio=Decimal("1.3"),
        close_position=Decimal("0.8"),
        effort_result=EffortResult.ABSORPTION,
        config_overrides={"lps_allow_absorption": False},
    )
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "LPS volume too high" in result.reason
    # Should NOT mention "absorption pattern criteria not met" since feature is disabled
    assert "absorption pattern criteria not met" not in result.reason


# ============================================================================
# UTAD Volume Validation Tests (WYCKOFF ENHANCEMENT)
# ============================================================================


@pytest.mark.asyncio
async def test_utad_high_volume_passes(volume_validator: VolumeValidator) -> None:
    """UTAD with volume_ratio = 1.5x should PASS (high volume supply climax)."""
    context = create_validation_context(pattern_type="UTAD", volume_ratio=Decimal("1.5"))
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.PASS
    assert result.stage == "Volume"


@pytest.mark.asyncio
async def test_utad_at_threshold_passes(volume_validator: VolumeValidator) -> None:
    """UTAD with volume_ratio = 1.2x should PASS (at threshold)."""
    context = create_validation_context(pattern_type="UTAD", volume_ratio=Decimal("1.2"))
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.PASS


@pytest.mark.asyncio
async def test_utad_just_under_threshold_fails(volume_validator: VolumeValidator) -> None:
    """UTAD with volume_ratio = 1.19x should FAIL (just under threshold)."""
    context = create_validation_context(pattern_type="UTAD", volume_ratio=Decimal("1.19"))
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "UTAD volume too low" in result.reason
    assert "1.19" in result.reason
    assert "supply climax requires elevated volume" in result.reason
    assert result.metadata["actual_volume_ratio"] == 1.19
    assert result.metadata["threshold"] == 1.2


@pytest.mark.asyncio
async def test_utad_low_volume_fails(volume_validator: VolumeValidator) -> None:
    """UTAD with volume_ratio = 0.8x should FAIL (too low for supply climax)."""
    context = create_validation_context(pattern_type="UTAD", volume_ratio=Decimal("0.8"))
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "UTAD volume too low" in result.reason
    assert "0.8" in result.reason
    assert result.metadata["pattern_type"] == "UTAD"


# ============================================================================
# Test Confirmation Volume Validation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_spring_test_volume_decreasing_passes(volume_validator: VolumeValidator) -> None:
    """Spring with test_volume < pattern_volume should PASS."""
    context = create_validation_context(
        pattern_type="SPRING",
        volume_ratio=Decimal("0.6"),
        test_confirmed=True,
        test_volume_ratio=Decimal("0.4"),
    )
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.PASS


@pytest.mark.asyncio
async def test_spring_test_volume_equal_fails(volume_validator: VolumeValidator) -> None:
    """Spring with test_volume = pattern_volume should FAIL."""
    context = create_validation_context(
        pattern_type="SPRING",
        volume_ratio=Decimal("0.6"),
        test_confirmed=True,
        test_volume_ratio=Decimal("0.6"),
    )
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "Test volume not decreasing" in result.reason
    assert "test 0.6" in result.reason
    assert "pattern 0.6" in result.reason
    assert result.metadata["test_volume_ratio"] == 0.6
    assert result.metadata["pattern_volume_ratio"] == 0.6


@pytest.mark.asyncio
async def test_spring_test_volume_increasing_fails(volume_validator: VolumeValidator) -> None:
    """Spring with test_volume > pattern_volume should FAIL."""
    context = create_validation_context(
        pattern_type="SPRING",
        volume_ratio=Decimal("0.6"),
        test_confirmed=True,
        test_volume_ratio=Decimal("0.8"),
    )
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "Test volume not decreasing" in result.reason
    assert "test 0.8" in result.reason
    assert "pattern 0.6" in result.reason


@pytest.mark.asyncio
async def test_spring_test_not_confirmed_skips_check(volume_validator: VolumeValidator) -> None:
    """Spring with test_confirmed=False should skip test volume check."""
    context = create_validation_context(
        pattern_type="SPRING",
        volume_ratio=Decimal("0.6"),
        test_confirmed=False,
        # test_volume_ratio not provided (test pending)
    )
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.PASS


@pytest.mark.asyncio
async def test_spring_test_confirmed_missing_test_volume_fails(
    volume_validator: VolumeValidator,
) -> None:
    """Spring with test_confirmed=True but missing test_volume_ratio should FAIL."""
    context = create_validation_context(
        pattern_type="SPRING",
        volume_ratio=Decimal("0.6"),
        test_confirmed=True,
        test_volume_ratio=None,  # Missing test volume
    )
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "Test volume ratio missing" in result.reason


# ============================================================================
# Edge Case Tests
# ============================================================================


@pytest.mark.asyncio
async def test_volume_analysis_missing_fails(volume_validator: VolumeValidator) -> None:
    """ValidationContext with volume_analysis=None should FAIL."""
    pattern = MockPattern(pattern_type="SPRING")
    context = ValidationContext(
        pattern=pattern,
        symbol="AAPL",
        timeframe="1h",
        volume_analysis=None,  # Missing volume analysis
    )
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "Volume analysis missing" in result.reason


@pytest.mark.asyncio
async def test_volume_ratio_none_fails(volume_validator: VolumeValidator) -> None:
    """VolumeAnalysis with volume_ratio=None should FAIL (insufficient data)."""
    pattern = MockPattern(pattern_type="SPRING")
    bar = create_test_ohlcv_bar()
    volume_analysis = VolumeAnalysis(
        bar=bar,
        volume_ratio=None,  # Insufficient data (<20 bars)
        spread_ratio=None,
        close_position=Decimal("0.7"),
        effort_result=EffortResult.NORMAL,
    )
    context = ValidationContext(
        pattern=pattern,
        symbol="AAPL",
        timeframe="1h",
        volume_analysis=volume_analysis,
    )
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "Insufficient data" in result.reason
    assert "<20 bars" in result.reason


@pytest.mark.asyncio
async def test_unknown_pattern_type_fails(volume_validator: VolumeValidator) -> None:
    """Pattern with unknown pattern_type should FAIL."""
    context = create_validation_context(pattern_type="UNKNOWN_PATTERN", volume_ratio=Decimal("1.0"))
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "Unknown pattern type" in result.reason
    assert "UNKNOWN_PATTERN" in result.reason


# ============================================================================
# Configuration Override Tests
# ============================================================================


@pytest.mark.asyncio
async def test_spring_custom_threshold_applied(volume_validator: VolumeValidator) -> None:
    """Spring with custom spring_max_volume=0.6 should apply custom threshold."""
    config_overrides = {"spring_max_volume": "0.6"}
    context = create_validation_context(
        pattern_type="SPRING", volume_ratio=Decimal("0.65"), config_overrides=config_overrides
    )
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "0.6" in result.reason  # Custom threshold
    assert result.metadata["threshold"] == 0.6


@pytest.mark.asyncio
async def test_sos_custom_threshold_applied(volume_validator: VolumeValidator) -> None:
    """SOS with custom sos_min_volume=2.0 should apply custom threshold."""
    config_overrides = {"sos_min_volume": "2.0"}
    context = create_validation_context(
        pattern_type="SOS", volume_ratio=Decimal("1.8"), config_overrides=config_overrides
    )
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert "2.0" in result.reason  # Custom threshold
    assert result.metadata["threshold"] == 2.0


@pytest.mark.asyncio
async def test_default_config_used_when_no_overrides(volume_validator: VolumeValidator) -> None:
    """Validator should use default config when no overrides provided."""
    context = create_validation_context(
        pattern_type="SPRING",
        volume_ratio=Decimal("0.65"),
        # No config_overrides - should use default 0.7
    )
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.PASS  # 0.65 < default 0.7


# ============================================================================
# Non-Negotiable FAIL Behavior Tests (FR12)
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "pattern_type,volume_ratio",
    [
        ("SPRING", Decimal("0.7")),  # At threshold
        ("SPRING", Decimal("1.0")),  # Over threshold
        ("SOS", Decimal("1.4")),  # Below threshold
        ("SOS", Decimal("0.8")),  # Way below
        ("LPS", Decimal("1.0")),  # At threshold
        ("LPS", Decimal("1.5")),  # Over threshold
        ("UTAD", Decimal("1.1")),  # Below threshold
    ],
)
async def test_volume_violations_always_fail_never_warn(
    volume_validator: VolumeValidator, pattern_type: str, volume_ratio: Decimal
) -> None:
    """All volume violations should return FAIL, never WARN (FR12 non-negotiable)."""
    context = create_validation_context(pattern_type=pattern_type, volume_ratio=volume_ratio)
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert result.status != ValidationStatus.WARN  # Never WARN for volume violations


# ============================================================================
# Metadata Tests
# ============================================================================


@pytest.mark.asyncio
async def test_fail_result_includes_detailed_metadata(volume_validator: VolumeValidator) -> None:
    """Failed validation should include detailed metadata for debugging."""
    context = create_validation_context(pattern_type="SPRING", volume_ratio=Decimal("0.85"))
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert result.metadata is not None
    assert "actual_volume_ratio" in result.metadata
    assert "threshold" in result.metadata
    assert "symbol" in result.metadata
    assert "pattern_type" in result.metadata
    assert "pattern_bar_timestamp" in result.metadata
    assert result.metadata["actual_volume_ratio"] == 0.85
    assert result.metadata["symbol"] == "AAPL"


@pytest.mark.asyncio
async def test_pass_result_has_no_reason(volume_validator: VolumeValidator) -> None:
    """Passed validation should have reason=None."""
    context = create_validation_context(pattern_type="SPRING", volume_ratio=Decimal("0.5"))
    result = await volume_validator.validate(context)

    assert result.status == ValidationStatus.PASS
    assert result.reason is None


# ============================================================================
# Validator Properties Tests
# ============================================================================


def test_validator_id_property(volume_validator: VolumeValidator) -> None:
    """Validator should have correct validator_id."""
    assert volume_validator.validator_id == "VOLUME_VALIDATOR"


def test_stage_name_property(volume_validator: VolumeValidator) -> None:
    """Validator should have correct stage_name."""
    assert volume_validator.stage_name == "Volume"
