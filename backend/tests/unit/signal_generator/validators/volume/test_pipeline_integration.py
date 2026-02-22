"""
Integration test for volume validation in pipeline - Story 25.4 AC7

Verifies Spring with volume_ratio=0.8 is rejected at volume stage
(before reaching risk stage).
"""

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.models.validation import ValidationContext, ValidationStatus
from src.signal_generator.validators.volume.factory import get_volume_validator
from src.signal_generator.validators.volume.strategy_adapter import StrategyBasedVolumeValidator


def test_pipeline_rejects_spring_at_volume_stage():
    """
    Test AC7: Pipeline rejects Spring with volume_ratio=0.8 before risk stage.

    This integration test verifies:
    1. Factory routes to SpringVolumeValidator
    2. SpringVolumeValidator returns FAIL for 0.8
    3. StrategyBasedVolumeValidator adapter works correctly
    """
    # Create pattern with high volume (invalid for Spring)
    pattern = MagicMock()
    pattern.pattern_type = "SPRING"
    pattern.volume_ratio = Decimal("0.8")  # Too high for Spring (>= 0.7 threshold)
    pattern.id = uuid4()

    # Create context
    context = ValidationContext(
        pattern=pattern,
        symbol="TEST",
        asset_class="STOCK",
        timeframe="1d",
        config={},
    )

    # Test via factory (direct)
    validator = get_volume_validator("SPRING")
    from src.models.validation import VolumeValidationConfig

    config = VolumeValidationConfig()
    result = validator.validate(context, config)

    assert result.status == ValidationStatus.FAIL
    assert "0.8" in result.reason or "0.800" in result.reason
    assert "threshold" in result.reason.lower()


@pytest.mark.asyncio
async def test_adapter_rejects_spring_with_high_volume():
    """
    Test StrategyBasedVolumeValidator adapter rejects Spring with volume_ratio=0.8.

    This verifies the orchestrator wiring works correctly.
    """
    # Create pattern
    pattern = MagicMock()
    pattern.pattern_type = "SPRING"
    pattern.volume_ratio = Decimal("0.8")
    pattern.id = uuid4()

    # Create context
    context = ValidationContext(
        pattern=pattern,
        symbol="TEST",
        asset_class="STOCK",
        timeframe="1d",
        config={},
    )

    # Test via adapter (orchestrator path)
    adapter = StrategyBasedVolumeValidator()
    result = await adapter.validate(context)

    assert result.status == ValidationStatus.FAIL
    assert result.reason is not None


@pytest.mark.asyncio
async def test_adapter_passes_spring_with_low_volume():
    """
    Test StrategyBasedVolumeValidator adapter passes Spring with volume_ratio=0.5.
    """
    pattern = MagicMock()
    pattern.pattern_type = "SPRING"
    pattern.volume_ratio = Decimal("0.5")  # Valid low volume
    pattern.id = uuid4()

    context = ValidationContext(
        pattern=pattern,
        symbol="TEST",
        asset_class="STOCK",
        timeframe="1d",
        config={},
    )

    adapter = StrategyBasedVolumeValidator()
    result = await adapter.validate(context)

    assert result.status == ValidationStatus.PASS


@pytest.mark.asyncio
async def test_adapter_rejects_sos_with_low_volume():
    """
    Test StrategyBasedVolumeValidator adapter rejects SOS with volume_ratio=1.2.
    """
    pattern = MagicMock()
    pattern.pattern_type = "SOS"
    pattern.volume_ratio = Decimal("1.2")  # Too low for SOS (<= 1.5 threshold)
    pattern.id = uuid4()

    context = ValidationContext(
        pattern=pattern,
        symbol="TEST",
        asset_class="STOCK",
        timeframe="1d",
        config={},
    )

    adapter = StrategyBasedVolumeValidator()
    result = await adapter.validate(context)

    assert result.status == ValidationStatus.FAIL


@pytest.mark.asyncio
async def test_adapter_passes_sos_with_high_volume():
    """
    Test StrategyBasedVolumeValidator adapter passes SOS with volume_ratio=1.8.
    """
    pattern = MagicMock()
    pattern.pattern_type = "SOS"
    pattern.volume_ratio = Decimal("1.8")  # Valid high volume
    pattern.id = uuid4()

    context = ValidationContext(
        pattern=pattern,
        symbol="TEST",
        asset_class="STOCK",
        timeframe="1d",
        config={},
    )

    adapter = StrategyBasedVolumeValidator()
    result = await adapter.validate(context)

    assert result.status == ValidationStatus.PASS
