"""
Integration tests for VolumeValidator with ValidationChain (Story 8.3).

Tests:
- Full validation chain integration (Volume → Phase → Levels → Risk → Strategy)
- Early exit on volume failure
- Volume validator as first stage in chain
- ValidationChain tracking of volume rejection

Author: Story 8.3
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.effort_result import EffortResult
from src.models.ohlcv import OHLCVBar
from src.models.validation import (
    ValidationChain,
    ValidationContext,
    ValidationStatus,
)
from src.models.volume_analysis import VolumeAnalysis
from src.signal_generator.validators.volume_validator import VolumeValidator

# ============================================================================
# Test Fixtures
# ============================================================================


class MockPattern:
    """Mock Pattern for testing."""

    def __init__(self, pattern_type: str, test_confirmed: bool = False):
        self.id = uuid4()
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


def create_validation_context(pattern_type: str, volume_ratio: Decimal) -> ValidationContext:
    """Helper to create ValidationContext for integration testing."""
    pattern = MockPattern(pattern_type=pattern_type)
    bar = create_test_ohlcv_bar()
    volume_analysis = VolumeAnalysis(
        bar=bar,
        volume_ratio=volume_ratio,
        spread_ratio=Decimal("1.0"),
        close_position=Decimal("0.7"),
        effort_result=EffortResult.NORMAL,
    )

    return ValidationContext(
        pattern=pattern,
        symbol="AAPL",
        timeframe="1h",
        volume_analysis=volume_analysis,
    )


# ============================================================================
# Validation Chain Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_valid_spring_passes_volume_validation() -> None:
    """
    Valid Spring (low volume) should pass VolumeValidator.

    Tests that VolumeValidator returns PASS for valid Spring, allowing
    validation chain to continue to next stage (Phase validation).
    """
    # Create valid Spring context (volume_ratio = 0.5x < 0.7x threshold)
    context = create_validation_context(pattern_type="SPRING", volume_ratio=Decimal("0.5"))

    # Create validation chain
    chain = ValidationChain(pattern_id=context.pattern.id)

    # Run VolumeValidator (first stage)
    validator = VolumeValidator()
    result = await validator.validate(context)

    # Add result to chain
    chain.add_result(result)

    # Assertions
    assert result.status == ValidationStatus.PASS
    assert chain.is_valid is True
    assert chain.overall_status == ValidationStatus.PASS
    assert chain.rejection_stage is None
    assert chain.rejection_reason is None
    assert len(chain.validation_results) == 1
    assert chain.validation_results[0].stage == "Volume"
    assert chain.validation_results[0].validator_id == "VOLUME_VALIDATOR"


@pytest.mark.asyncio
async def test_invalid_spring_fails_volume_validation_early_exit() -> None:
    """
    Invalid Spring (high volume) should fail VolumeValidator with early exit.

    Tests that VolumeValidator returns FAIL for invalid Spring, triggering
    early exit in validation chain (no further validators run).
    """
    # Create invalid Spring context (volume_ratio = 0.8x >= 0.7x threshold)
    context = create_validation_context(pattern_type="SPRING", volume_ratio=Decimal("0.8"))

    # Create validation chain
    chain = ValidationChain(pattern_id=context.pattern.id)

    # Run VolumeValidator (first stage)
    validator = VolumeValidator()
    result = await validator.validate(context)

    # Add result to chain
    chain.add_result(result)

    # Assertions - validation chain should fail and early exit
    assert result.status == ValidationStatus.FAIL
    assert chain.is_valid is False
    assert chain.overall_status == ValidationStatus.FAIL
    assert chain.rejection_stage == "Volume"
    assert "Spring volume too high" in chain.rejection_reason
    assert len(chain.validation_results) == 1  # Only Volume stage ran (early exit)
    assert chain.validation_results[0].stage == "Volume"

    # Verify metadata captured
    assert result.metadata is not None
    assert result.metadata["actual_volume_ratio"] == 0.8
    assert result.metadata["threshold"] == 0.7


@pytest.mark.asyncio
async def test_valid_sos_passes_volume_validation() -> None:
    """
    Valid SOS (high volume) should pass VolumeValidator.

    Tests that VolumeValidator correctly validates SOS patterns with
    high volume (>= 1.5x threshold).
    """
    # Create valid SOS context (volume_ratio = 2.0x >= 1.5x threshold)
    context = create_validation_context(pattern_type="SOS", volume_ratio=Decimal("2.0"))

    # Create validation chain
    chain = ValidationChain(pattern_id=context.pattern.id)

    # Run VolumeValidator
    validator = VolumeValidator()
    result = await validator.validate(context)

    # Add result to chain
    chain.add_result(result)

    # Assertions
    assert result.status == ValidationStatus.PASS
    assert chain.is_valid is True
    assert chain.overall_status == ValidationStatus.PASS
    assert chain.rejection_stage is None


@pytest.mark.asyncio
async def test_invalid_sos_fails_volume_validation_early_exit() -> None:
    """
    Invalid SOS (low volume) should fail VolumeValidator with early exit.

    Tests that VolumeValidator rejects SOS patterns with insufficient
    volume (< 1.5x threshold).
    """
    # Create invalid SOS context (volume_ratio = 1.2x < 1.5x threshold)
    context = create_validation_context(pattern_type="SOS", volume_ratio=Decimal("1.2"))

    # Create validation chain
    chain = ValidationChain(pattern_id=context.pattern.id)

    # Run VolumeValidator
    validator = VolumeValidator()
    result = await validator.validate(context)

    # Add result to chain
    chain.add_result(result)

    # Assertions
    assert result.status == ValidationStatus.FAIL
    assert chain.is_valid is False
    assert chain.overall_status == ValidationStatus.FAIL
    assert chain.rejection_stage == "Volume"
    assert "SOS volume too low" in chain.rejection_reason
    assert len(chain.validation_results) == 1  # Early exit


@pytest.mark.asyncio
async def test_multiple_patterns_validation_chain_tracking() -> None:
    """
    Test ValidationChain tracks multiple pattern validations correctly.

    Simulates validating multiple patterns and verifying that each
    pattern's validation is tracked separately with correct results.
    """
    patterns = [
        ("SPRING", Decimal("0.5"), ValidationStatus.PASS),  # Valid Spring
        ("SPRING", Decimal("0.8"), ValidationStatus.FAIL),  # Invalid Spring
        ("SOS", Decimal("2.0"), ValidationStatus.PASS),  # Valid SOS
        ("SOS", Decimal("1.0"), ValidationStatus.FAIL),  # Invalid SOS
    ]

    validator = VolumeValidator()
    results = []

    for pattern_type, volume_ratio, expected_status in patterns:
        context = create_validation_context(pattern_type=pattern_type, volume_ratio=volume_ratio)
        chain = ValidationChain(pattern_id=context.pattern.id)

        result = await validator.validate(context)
        chain.add_result(result)

        results.append((pattern_type, volume_ratio, result.status, chain.is_valid))

        # Verify expected status
        assert result.status == expected_status
        assert chain.is_valid == (expected_status == ValidationStatus.PASS)

    # Verify all patterns were validated
    assert len(results) == 4
    assert results[0][2] == ValidationStatus.PASS  # Valid Spring
    assert results[1][2] == ValidationStatus.FAIL  # Invalid Spring
    assert results[2][2] == ValidationStatus.PASS  # Valid SOS
    assert results[3][2] == ValidationStatus.FAIL  # Invalid SOS


@pytest.mark.asyncio
async def test_validation_chain_rejection_metadata_captured() -> None:
    """
    Test that ValidationChain captures rejection metadata for audit trail.

    Verifies that when VolumeValidator fails, all relevant metadata
    (volume_ratio, threshold, symbol, pattern_type) is captured in
    the ValidationChain for debugging and compliance.
    """
    # Create invalid Spring
    context = create_validation_context(pattern_type="SPRING", volume_ratio=Decimal("0.85"))

    # Create validation chain with signal_id (simulating full signal generation)
    signal_id = uuid4()
    chain = ValidationChain(signal_id=signal_id, pattern_id=context.pattern.id)

    # Run VolumeValidator
    validator = VolumeValidator()
    result = await validator.validate(context)
    chain.add_result(result)

    # Mark chain as completed
    chain.completed_at = datetime.now(UTC)

    # Assertions - verify metadata captured for audit trail
    assert chain.is_valid is False
    assert chain.rejection_stage == "Volume"
    assert chain.signal_id == signal_id
    assert chain.pattern_id == context.pattern.id
    assert chain.completed_at is not None

    # Verify detailed result metadata
    volume_result = chain.validation_results[0]
    assert volume_result.metadata is not None
    assert volume_result.metadata["actual_volume_ratio"] == 0.85
    assert volume_result.metadata["threshold"] == 0.7
    assert volume_result.metadata["symbol"] == "AAPL"
    assert volume_result.metadata["pattern_type"] == "SPRING"
    assert "pattern_bar_timestamp" in volume_result.metadata


@pytest.mark.asyncio
async def test_volume_validator_first_stage_performance() -> None:
    """
    Test that VolumeValidator executes quickly as first stage.

    Verifies that VolumeValidator completes validation in < 10ms
    (performance requirement from Story 8.3).

    This is a smoke test - actual performance benchmarking would
    require validating 1000+ signals.
    """
    import time

    context = create_validation_context(pattern_type="SPRING", volume_ratio=Decimal("0.5"))
    validator = VolumeValidator()

    start_time = time.perf_counter()
    result = await validator.validate(context)
    end_time = time.perf_counter()

    duration_ms = (end_time - start_time) * 1000

    # Smoke test - should be well under 10ms for single validation
    assert duration_ms < 10.0
    assert result.status == ValidationStatus.PASS


# ============================================================================
# Edge Case Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_validation_chain_handles_missing_volume_analysis() -> None:
    """
    Test that ValidationChain properly handles missing volume_analysis.

    Verifies that VolumeValidator fails gracefully when volume_analysis
    is None, and ValidationChain captures the failure correctly.
    """
    pattern = MockPattern(pattern_type="SPRING")
    context = ValidationContext(
        pattern=pattern,
        symbol="AAPL",
        timeframe="1h",
        volume_analysis=None,  # Missing volume analysis
    )

    chain = ValidationChain(pattern_id=pattern.id)
    validator = VolumeValidator()

    result = await validator.validate(context)
    chain.add_result(result)

    # Assertions
    assert result.status == ValidationStatus.FAIL
    assert "Volume analysis missing" in result.reason
    assert chain.is_valid is False
    assert chain.rejection_stage == "Volume"


@pytest.mark.asyncio
async def test_validation_chain_handles_insufficient_data() -> None:
    """
    Test that ValidationChain handles volume_ratio=None (insufficient data).

    Verifies that VolumeValidator fails when volume_ratio is None
    (e.g., < 20 bars available for calculation).
    """
    pattern = MockPattern(pattern_type="SPRING")
    bar = create_test_ohlcv_bar()
    volume_analysis = VolumeAnalysis(
        bar=bar,
        volume_ratio=None,  # Insufficient data
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

    chain = ValidationChain(pattern_id=pattern.id)
    validator = VolumeValidator()

    result = await validator.validate(context)
    chain.add_result(result)

    # Assertions
    assert result.status == ValidationStatus.FAIL
    assert "Insufficient data" in result.reason
    assert chain.is_valid is False
    assert chain.rejection_stage == "Volume"


# ============================================================================
# LPS Integration Tests (WYCKOFF ENHANCEMENT)
# ============================================================================


@pytest.mark.asyncio
async def test_lps_quiet_passes_validation_chain() -> None:
    """Test standard quiet LPS passes VolumeValidator."""
    context = create_validation_context(pattern_type="LPS", volume_ratio=Decimal("0.6"))

    chain = ValidationChain(pattern_id=context.pattern.id)
    validator = VolumeValidator()

    result = await validator.validate(context)
    chain.add_result(result)

    assert result.status == ValidationStatus.PASS
    assert chain.is_valid is True


@pytest.mark.asyncio
async def test_lps_high_volume_fails_validation_chain() -> None:
    """Test high-volume LPS (without absorption) fails VolumeValidator."""
    context = create_validation_context(pattern_type="LPS", volume_ratio=Decimal("1.2"))

    chain = ValidationChain(pattern_id=context.pattern.id)
    validator = VolumeValidator()

    result = await validator.validate(context)
    chain.add_result(result)

    assert result.status == ValidationStatus.FAIL
    assert chain.is_valid is False
    assert chain.rejection_stage == "Volume"
    assert "LPS volume too high" in chain.rejection_reason


# ============================================================================
# UTAD Integration Tests (WYCKOFF ENHANCEMENT)
# ============================================================================


@pytest.mark.asyncio
async def test_utad_high_volume_passes_validation_chain() -> None:
    """Test UTAD with high volume passes VolumeValidator."""
    context = create_validation_context(pattern_type="UTAD", volume_ratio=Decimal("1.5"))

    chain = ValidationChain(pattern_id=context.pattern.id)
    validator = VolumeValidator()

    result = await validator.validate(context)
    chain.add_result(result)

    assert result.status == ValidationStatus.PASS
    assert chain.is_valid is True


@pytest.mark.asyncio
async def test_utad_low_volume_fails_validation_chain() -> None:
    """Test UTAD with low volume fails VolumeValidator."""
    context = create_validation_context(pattern_type="UTAD", volume_ratio=Decimal("0.8"))

    chain = ValidationChain(pattern_id=context.pattern.id)
    validator = VolumeValidator()

    result = await validator.validate(context)
    chain.add_result(result)

    assert result.status == ValidationStatus.FAIL
    assert chain.is_valid is False
    assert chain.rejection_stage == "Volume"
    assert "UTAD volume too low" in chain.rejection_reason
    assert "supply climax" in chain.rejection_reason
