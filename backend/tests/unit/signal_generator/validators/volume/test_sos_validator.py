"""
Tests for SOSVolumeValidator - Story 25.4

Validates AC3, AC4, AC5 (SOS-specific requirements).
"""

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.models.validation import ValidationContext, ValidationStatus, VolumeValidationConfig
from src.signal_generator.validators.volume.sos_validator import SOSVolumeValidator


@pytest.mark.parametrize(
    "volume_ratio,expected_pass",
    [
        (Decimal("1.0"), False),  # well below threshold
        (Decimal("1.2"), False),  # below threshold (AC3)
        (Decimal("1.49"), False),  # just below 1.5
        (Decimal("1.5"), False),  # EXACTLY at threshold — must FAIL (<= means 1.5 fails)
        (Decimal("1.51"), True),  # just above
        (Decimal("1.8"), True),  # above threshold (AC4)
        (Decimal("2.0"), True),  # well above
    ],
)
def test_sos_volume_ratio_boundaries(volume_ratio, expected_pass):
    """Test SOS volume ratio against threshold (AC3, AC4)."""
    validator = SOSVolumeValidator()

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


def test_sos_fail_reason_informative():
    """Test that failure reason contains volume_ratio and threshold."""
    validator = SOSVolumeValidator()

    pattern = MagicMock()
    pattern.volume_ratio = Decimal("1.2")
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
    assert "1.2" in result.reason or "1.200" in result.reason
    assert "1.5" in result.reason or "1.500" in result.reason
    assert "threshold" in result.reason.lower()


def test_sos_none_volume_ratio():
    """Test None volume_ratio → FAIL (not crash)."""
    validator = SOSVolumeValidator()

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


def test_sos_nan_volume_ratio():
    """Test NaN volume_ratio → FAIL (not crash or silent pass)."""
    validator = SOSVolumeValidator()

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
