"""
Tests for SpringVolumeValidator - Story 25.4

Validates AC1, AC2, AC5 (Spring-specific requirements).
"""

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.models.validation import ValidationContext, ValidationStatus, VolumeValidationConfig
from src.signal_generator.validators.volume.spring_validator import SpringVolumeValidator


@pytest.mark.parametrize(
    "volume_ratio,expected_pass",
    [
        (Decimal("0.3"), True),  # well below threshold
        (Decimal("0.5"), True),  # below threshold (AC2)
        (Decimal("0.69"), True),  # just below 0.7
        (Decimal("0.7"), False),  # EXACTLY at threshold — must FAIL (>= means 0.7 fails)
        (Decimal("0.71"), False),  # just above
        (Decimal("0.8"), False),  # well above (AC1)
        (Decimal("0.9"), False),  # well above
    ],
)
def test_spring_volume_ratio_boundaries(volume_ratio, expected_pass):
    """Test Spring volume ratio against threshold (AC1, AC2)."""
    validator = SpringVolumeValidator()

    # Create mock pattern
    pattern = MagicMock()
    pattern.volume_ratio = volume_ratio
    pattern.id = uuid4()

    # Create minimal context
    context = ValidationContext(
        pattern=pattern,
        symbol="TEST",
        asset_class="STOCK",
        timeframe="1d",
        config={},
    )

    config = VolumeValidationConfig()

    # Execute validation
    result = validator.validate(context, config)

    # Check result
    if expected_pass:
        assert result.status == ValidationStatus.PASS, (
            f"Expected PASS for volume_ratio={volume_ratio}, got {result.status}. "
            f"Reason: {result.reason}"
        )
    else:
        assert result.status == ValidationStatus.FAIL, (
            f"Expected FAIL for volume_ratio={volume_ratio}, got {result.status}"
        )


def test_spring_fail_reason_informative():
    """Test that failure reason contains volume_ratio and threshold."""
    validator = SpringVolumeValidator()

    pattern = MagicMock()
    pattern.volume_ratio = Decimal("0.8")
    pattern.id = uuid4()

    context = ValidationContext(
        pattern=pattern,
        symbol="TEST",
        asset_class="STOCK",
        timeframe="1d",
        config={},
    )

    config = VolumeValidationConfig()
    result = validator.validate(context, config)

    assert result.status == ValidationStatus.FAIL
    assert result.reason is not None
    assert "0.8" in result.reason or "0.800" in result.reason
    assert "0.7" in result.reason or "0.700" in result.reason
    assert "threshold" in result.reason.lower()


def test_spring_none_volume_ratio():
    """Test None volume_ratio → FAIL (not crash)."""
    validator = SpringVolumeValidator()

    pattern = MagicMock()
    pattern.volume_ratio = None
    pattern.id = uuid4()

    context = ValidationContext(
        pattern=pattern,
        symbol="TEST",
        asset_class="STOCK",
        timeframe="1d",
        config={},
    )

    config = VolumeValidationConfig()
    result = validator.validate(context, config)

    assert result.status == ValidationStatus.FAIL
    assert "None" in result.reason or "missing" in result.reason.lower()


def test_spring_nan_volume_ratio():
    """Test NaN volume_ratio → FAIL (not crash or silent pass)."""
    validator = SpringVolumeValidator()

    pattern = MagicMock()
    pattern.volume_ratio = float("nan")  # NaN
    pattern.id = uuid4()

    context = ValidationContext(
        pattern=pattern,
        symbol="TEST",
        asset_class="STOCK",
        timeframe="1d",
        config={},
    )

    config = VolumeValidationConfig()
    result = validator.validate(context, config)

    assert result.status == ValidationStatus.FAIL
    assert "nan" in result.reason.lower() or "invalid" in result.reason.lower()
