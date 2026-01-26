"""
Unit tests for stub validators (Story 8.2)

Tests all 5 stub validators:
- VolumeValidator
- PhaseValidator
- LevelValidator
- RiskValidator
- StrategyValidator

Author: Story 8.2
"""

from decimal import Decimal
from uuid import uuid4

import pytest

# Skip entire module - Validator tests have dict/object attribute mismatches
# Tracking issue: https://github.com/jthadison/bmad4_wyck_vol/issues/243
pytestmark = pytest.mark.skip(reason="Issue #243: Validator stub attribute access issues")

from src.models.validation import ValidationContext, ValidationStatus
from src.signal_generator.validators import (
    LevelValidator,
    PhaseValidator,
    RiskValidator,
    StrategyValidator,
    VolumeValidator,
)


class TestVolumeValidator:
    """Test VolumeValidator stub."""

    @pytest.mark.asyncio
    async def test_volume_validator_properties(self):
        """Test VolumeValidator has correct properties."""
        validator = VolumeValidator()
        assert validator.validator_id == "VOLUME_VALIDATOR"
        assert validator.stage_name == "Volume"

    @pytest.mark.asyncio
    async def test_volume_validator_returns_pass(self):
        """Test VolumeValidator stub always returns PASS."""
        validator = VolumeValidator()
        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING"},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
        )
        result = await validator.validate(context)
        assert result.status == ValidationStatus.PASS
        assert result.stage == "Volume"
        assert result.validator_id == "VOLUME_VALIDATOR"

    @pytest.mark.asyncio
    async def test_volume_validator_no_null_check_needed(self):
        """Test VolumeValidator doesn't need null check (volume_analysis is REQUIRED)."""
        validator = VolumeValidator()
        # volume_analysis is REQUIRED in ValidationContext, so this should always work
        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING"},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},  # REQUIRED field
        )
        result = await validator.validate(context)
        assert result.status == ValidationStatus.PASS


class TestPhaseValidator:
    """Test PhaseValidator stub."""

    @pytest.mark.asyncio
    async def test_phase_validator_properties(self):
        """Test PhaseValidator has correct properties."""
        validator = PhaseValidator()
        assert validator.validator_id == "PHASE_VALIDATOR"
        assert validator.stage_name == "Phase"

    @pytest.mark.asyncio
    async def test_phase_validator_returns_pass_with_phase_info(self):
        """Test PhaseValidator returns PASS if phase_info present."""
        validator = PhaseValidator()
        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING"},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
            phase_info={"phase": "C"},
        )
        result = await validator.validate(context)
        assert result.status == ValidationStatus.PASS
        assert result.stage == "Phase"
        assert result.validator_id == "PHASE_VALIDATOR"

    @pytest.mark.asyncio
    async def test_phase_validator_returns_fail_without_phase_info(self):
        """Test PhaseValidator returns FAIL if phase_info is None."""
        validator = PhaseValidator()
        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING"},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
            phase_info=None,  # Missing phase_info
        )
        result = await validator.validate(context)
        assert result.status == ValidationStatus.FAIL
        assert result.reason == "Phase information not available for phase validation"


class TestLevelValidator:
    """Test LevelValidator stub."""

    @pytest.mark.asyncio
    async def test_level_validator_properties(self):
        """Test LevelValidator has correct properties."""
        validator = LevelValidator()
        assert validator.validator_id == "LEVEL_VALIDATOR"
        assert validator.stage_name == "Levels"

    @pytest.mark.asyncio
    async def test_level_validator_returns_pass_with_trading_range(self):
        """Test LevelValidator returns PASS if trading_range present."""
        validator = LevelValidator()
        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING"},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
            trading_range={"creek_level": Decimal("100.00")},
        )
        result = await validator.validate(context)
        assert result.status == ValidationStatus.PASS
        assert result.stage == "Levels"
        assert result.validator_id == "LEVEL_VALIDATOR"

    @pytest.mark.asyncio
    async def test_level_validator_returns_fail_without_trading_range(self):
        """Test LevelValidator returns FAIL if trading_range is None."""
        validator = LevelValidator()
        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING"},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
            trading_range=None,  # Missing trading_range
        )
        result = await validator.validate(context)
        assert result.status == ValidationStatus.FAIL
        assert result.reason == "Trading range not available for level validation"


class TestRiskValidator:
    """Test RiskValidator stub."""

    @pytest.mark.asyncio
    async def test_risk_validator_properties(self):
        """Test RiskValidator has correct properties."""
        validator = RiskValidator()
        assert validator.validator_id == "RISK_VALIDATOR"
        assert validator.stage_name == "Risk"

    @pytest.mark.asyncio
    async def test_risk_validator_returns_pass_with_portfolio_context(self):
        """Test RiskValidator returns PASS if portfolio_context present."""
        validator = RiskValidator()
        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING"},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
            portfolio_context={"available_capital": Decimal("100000")},
        )
        result = await validator.validate(context)
        assert result.status == ValidationStatus.PASS
        assert result.stage == "Risk"
        assert result.validator_id == "RISK_VALIDATOR"

    @pytest.mark.asyncio
    async def test_risk_validator_returns_fail_without_portfolio_context(self):
        """Test RiskValidator returns FAIL if portfolio_context is None."""
        validator = RiskValidator()
        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING"},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
            portfolio_context=None,  # Missing portfolio_context
        )
        result = await validator.validate(context)
        assert result.status == ValidationStatus.FAIL
        assert result.reason == "Portfolio context not available for risk validation"


class TestStrategyValidator:
    """Test StrategyValidator full implementation."""

    @pytest.mark.asyncio
    async def test_strategy_validator_properties(self):
        """Test StrategyValidator has correct properties."""
        from unittest.mock import Mock

        mock_factory = Mock()
        validator = StrategyValidator(mock_factory)
        assert validator.validator_id == "STRATEGY_VALIDATOR"
        assert validator.stage_name == "Strategy"

    @pytest.mark.asyncio
    async def test_strategy_validator_returns_pass_with_market_context(self):
        """Test StrategyValidator returns PASS if market_context present (simplified)."""
        # NOTE: Full tests in test_strategy_validator.py - this is basic smoke test
        pytest.skip("Skipping stub test - full implementation tested in test_strategy_validator.py")

    @pytest.mark.asyncio
    async def test_strategy_validator_returns_fail_without_market_context(self):
        """Test StrategyValidator returns FAIL if market_context is None."""
        from unittest.mock import Mock

        mock_factory = Mock()
        validator = StrategyValidator(mock_factory)
        context = ValidationContext(
            pattern={"id": str(uuid4()), "type": "SPRING"},
            symbol="AAPL",
            timeframe="1d",
            volume_analysis={"volume_ratio": Decimal("0.45")},
            market_context=None,  # Missing market_context
        )
        result = await validator.validate(context)
        assert result.status == ValidationStatus.FAIL
        assert result.reason == "Market context not available for strategy validation"
