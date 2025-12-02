"""
Unit tests for LevelValidator (Story 8.5).

Tests Creek/Ice/Jump level validation rules using mocks to avoid complex model dependencies.

Author: Story 8.5
"""

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.models.validation import ValidationContext, ValidationStatus
from src.signal_generator.validators.level_validator import LevelValidator


class MockPattern:
    """Mock Pattern for testing."""

    def __init__(self, pattern_type: str = "SPRING"):
        self.id = uuid4()
        self.pattern_type = pattern_type


def create_mock_creek(price: Decimal, strength_score: int) -> MagicMock:
    """Create mock CreekLevel."""
    creek = MagicMock()
    creek.price = price
    creek.strength_score = strength_score
    return creek


def create_mock_ice(price: Decimal, strength_score: int) -> MagicMock:
    """Create mock IceLevel."""
    ice = MagicMock()
    ice.price = price
    ice.strength_score = strength_score
    return ice


def create_mock_jump(price: Decimal, cause_factor: Decimal) -> MagicMock:
    """Create mock JumpLevel."""
    jump = MagicMock()
    jump.price = price
    jump.cause_factor = cause_factor
    return jump


def create_mock_trading_range(creek, ice, jump, duration: int) -> MagicMock:
    """Create mock TradingRange."""
    tr = MagicMock()
    tr.creek = creek
    tr.ice = ice
    tr.jump = jump
    tr.duration = duration
    return tr


@pytest.fixture
def level_validator() -> LevelValidator:
    """LevelValidator instance."""
    return LevelValidator()


def test_validator_id(level_validator):
    """Test validator_id property."""
    assert level_validator.validator_id == "LEVEL_VALIDATOR"


def test_stage_name(level_validator):
    """Test stage_name property."""
    assert level_validator.stage_name == "Levels"


@pytest.mark.asyncio
async def test_missing_trading_range_fails(level_validator):
    """Test FAIL when trading_range is None."""
    context = ValidationContext(
        pattern=MockPattern(),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=MagicMock(),
        trading_range=None,
    )
    result = await level_validator.validate(context)
    assert result.status == ValidationStatus.FAIL
    assert "Trading range information not available" in result.reason


@pytest.mark.asyncio
async def test_creek_strength_above_60_passes(level_validator):
    """Test PASS when Creek strength is 75."""
    creek = create_mock_creek(Decimal("95.00"), 75)
    ice = create_mock_ice(Decimal("105.00"), 80)
    jump = create_mock_jump(Decimal("135.00"), Decimal("3.0"))
    tr = create_mock_trading_range(creek, ice, jump, 45)

    context = ValidationContext(
        pattern=MockPattern(),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=MagicMock(),
        trading_range=tr,
    )
    result = await level_validator.validate(context)
    assert result.status == ValidationStatus.PASS


@pytest.mark.asyncio
async def test_creek_strength_45_fails(level_validator):
    """Test FAIL when Creek strength is 45."""
    creek = create_mock_creek(Decimal("95.00"), 45)
    ice = create_mock_ice(Decimal("105.00"), 80)
    jump = create_mock_jump(Decimal("135.00"), Decimal("3.0"))
    tr = create_mock_trading_range(creek, ice, jump, 45)

    context = ValidationContext(
        pattern=MockPattern(),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=MagicMock(),
        trading_range=tr,
    )
    result = await level_validator.validate(context)
    assert result.status == ValidationStatus.FAIL
    assert "45" in result.reason
    assert "60 minimum requirement" in result.reason
    assert "FR9" in result.reason


@pytest.mark.asyncio
async def test_ice_less_than_creek_fails(level_validator):
    """Test FAIL when Ice < Creek."""
    creek = create_mock_creek(Decimal("105.00"), 75)
    ice = create_mock_ice(Decimal("95.00"), 80)
    jump = create_mock_jump(Decimal("135.00"), Decimal("3.0"))
    tr = create_mock_trading_range(creek, ice, jump, 45)

    context = ValidationContext(
        pattern=MockPattern(),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=MagicMock(),
        trading_range=tr,
    )
    result = await level_validator.validate(context)
    assert result.status == ValidationStatus.FAIL
    assert "Ice price" in result.reason
    assert "greater than Creek" in result.reason


@pytest.mark.asyncio
async def test_jump_conservative_warns(level_validator):
    """Test WARN when Jump is conservative (<80% expected)."""
    creek = create_mock_creek(Decimal("100.00"), 75)
    ice = create_mock_ice(Decimal("110.00"), 80)
    # Expected: $30, Actual: $22 (73%)
    jump = create_mock_jump(Decimal("132.00"), Decimal("3.0"))
    tr = create_mock_trading_range(creek, ice, jump, 45)

    context = ValidationContext(
        pattern=MockPattern(),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=MagicMock(),
        trading_range=tr,
    )
    result = await level_validator.validate(context)
    assert result.status == ValidationStatus.WARN
    assert "conservative" in result.reason.lower()


@pytest.mark.asyncio
async def test_jump_aggressive_fails(level_validator):
    """Test FAIL when Jump is aggressive (>200% expected)."""
    creek = create_mock_creek(Decimal("100.00"), 75)
    ice = create_mock_ice(Decimal("110.00"), 80)
    # Expected: $30, Actual: $70 (233%)
    jump = create_mock_jump(Decimal("180.00"), Decimal("3.0"))
    tr = create_mock_trading_range(creek, ice, jump, 45)

    context = ValidationContext(
        pattern=MockPattern(),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=MagicMock(),
        trading_range=tr,
    )
    result = await level_validator.validate(context)
    assert result.status == ValidationStatus.FAIL
    assert "too aggressive" in result.reason.lower()
    assert "unrealistic" in result.reason.lower()


@pytest.mark.asyncio
async def test_range_2_5_percent_fails(level_validator):
    """Test FAIL when range is 2.5% (<3% minimum)."""
    creek = create_mock_creek(Decimal("100.00"), 75)
    ice = create_mock_ice(Decimal("102.50"), 80)
    jump = create_mock_jump(Decimal("107.50"), Decimal("2.0"))
    tr = create_mock_trading_range(creek, ice, jump, 20)

    context = ValidationContext(
        pattern=MockPattern(),
        symbol="AAPL",
        timeframe="1d",
        volume_analysis=MagicMock(),
        trading_range=tr,
    )
    result = await level_validator.validate(context)
    assert result.status == ValidationStatus.FAIL
    assert "Range size" in result.reason
    assert "3.0% minimum" in result.reason
    assert "FR1" in result.reason
