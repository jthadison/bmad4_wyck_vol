"""
Tests for threshold configuration - Story 25.4 AC5

Verifies validators use imported constants from timeframe_config.py,
not hardcoded literals.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from src.models.validation import ValidationContext, ValidationStatus, VolumeValidationConfig
from src.signal_generator.validators.volume.sos_validator import SOSVolumeValidator
from src.signal_generator.validators.volume.spring_validator import SpringVolumeValidator


def test_spring_uses_config_threshold():
    """
    Verify SpringVolumeValidator uses SPRING_VOLUME_THRESHOLD from config.

    Monkeypatch SPRING_VOLUME_THRESHOLD to 0.5 and verify volume_ratio=0.6
    now FAILS (it would PASS with default 0.7).
    """
    # Patch at module level where it's imported
    with patch(
        "src.signal_generator.validators.volume.spring_validator.SPRING_VOLUME_THRESHOLD",
        new=Decimal("0.5"),
    ):
        validator = SpringVolumeValidator()

        pattern = MagicMock()
        pattern.volume_ratio = Decimal("0.6")  # Would pass with 0.7 threshold
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

        # With threshold=0.5, volume_ratio=0.6 should FAIL (0.6 >= 0.5)
        assert result.status == ValidationStatus.FAIL, (
            f"Expected FAIL with patched threshold=0.5 and volume_ratio=0.6, "
            f"got {result.status}. This proves validator uses imported constant."
        )
        assert "0.5" in result.reason  # Verify patched threshold appears in reason


def test_sos_uses_config_threshold():
    """
    Verify SOSVolumeValidator uses SOS_VOLUME_THRESHOLD from config.

    Monkeypatch SOS_VOLUME_THRESHOLD to 2.0 and verify volume_ratio=1.8
    now FAILS (it would PASS with default 1.5).
    """
    # Patch at module level where it's imported
    with patch(
        "src.signal_generator.validators.volume.sos_validator.SOS_VOLUME_THRESHOLD",
        new=Decimal("2.0"),
    ):
        validator = SOSVolumeValidator()

        pattern = MagicMock()
        pattern.volume_ratio = Decimal("1.8")  # Would pass with 1.5 threshold
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

        # With threshold=2.0, volume_ratio=1.8 should FAIL (1.8 <= 2.0)
        assert result.status == ValidationStatus.FAIL, (
            f"Expected FAIL with patched threshold=2.0 and volume_ratio=1.8, "
            f"got {result.status}. This proves validator uses imported constant."
        )
        assert "2.0" in result.reason or "2.000" in result.reason  # Verify patched threshold


def test_spring_default_threshold_value():
    """Verify Spring default threshold is exactly 0.7 (AC5 - no hardcoded literals)."""
    validator = SpringVolumeValidator()
    assert validator.default_stock_threshold == Decimal("0.7")
    assert validator.default_forex_threshold == Decimal("0.7")


def test_sos_default_threshold_value():
    """Verify SOS default threshold is exactly 1.5 (AC5 - no hardcoded literals)."""
    validator = SOSVolumeValidator()
    assert validator.default_stock_threshold == Decimal("1.5")
    assert validator.default_forex_threshold == Decimal("1.5")
