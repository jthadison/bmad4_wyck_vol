"""
Unit tests for stub validators (Story 8.2)

Tests all 5 stub validators:
- VolumeValidator
- PhaseValidator
- LevelValidator
- RiskValidator
- StrategyValidator

Author: Story 8.2
Fixed: Issue #243 - Updated fixtures for proper attribute access using SimpleNamespace
"""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.models.validation import ValidationContext, ValidationStatus
from src.signal_generator.validators import (
    LevelValidator,
    PhaseValidator,
    RiskValidator,
    StrategyValidator,
    VolumeValidator,
)


def create_mock_pattern(
    pattern_id=None,
    pattern_type="SPRING",
    test_confirmed=False,
    confidence_score=0.85,
    pattern_bar_timestamp=None,
):
    """Create a mock pattern object with proper attribute access."""
    return SimpleNamespace(
        id=pattern_id or uuid4(),
        pattern_type=pattern_type,
        test_confirmed=test_confirmed,
        confidence_score=confidence_score,
        pattern_bar_timestamp=pattern_bar_timestamp or datetime.now(UTC),
    )


def create_mock_volume_analysis(volume_ratio=Decimal("0.45")):
    """Create a mock volume analysis object with proper attribute access."""
    return SimpleNamespace(
        volume_ratio=volume_ratio,
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
        """Test VolumeValidator stub returns PASS for valid Spring volume."""
        validator = VolumeValidator()
        pattern = create_mock_pattern(pattern_type="SPRING")
        volume_analysis = create_mock_volume_analysis(volume_ratio=Decimal("0.45"))

        context = ValidationContext(
            pattern=pattern,
            symbol="AAPL",
            timeframe="1d",
            volume_analysis=volume_analysis,
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
        pattern = create_mock_pattern(pattern_type="SPRING")
        volume_analysis = create_mock_volume_analysis(volume_ratio=Decimal("0.45"))

        context = ValidationContext(
            pattern=pattern,
            symbol="AAPL",
            timeframe="1d",
            volume_analysis=volume_analysis,  # REQUIRED field
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
        """Test PhaseValidator returns PASS if phase_info present and valid.

        NOTE: Full validation tests are in test_phase_validator.py.
        This test verifies basic PASS with proper PhaseClassification object.
        """
        from src.models.phase_classification import (
            PhaseClassification,
            PhaseEvents,
            WyckoffPhase,
        )

        validator = PhaseValidator()
        pattern = create_mock_pattern(pattern_type="SPRING")
        volume_analysis = create_mock_volume_analysis()

        # Create proper PhaseClassification object with all required fields
        phase_info = PhaseClassification(
            phase=WyckoffPhase.C,
            confidence=80,
            duration=15,
            events_detected=PhaseEvents(),
            trading_allowed=True,
            phase_start_index=0,
            phase_start_timestamp=datetime.now(UTC),
        )

        context = ValidationContext(
            pattern=pattern,
            symbol="AAPL",
            timeframe="1d",
            volume_analysis=volume_analysis,
            phase_info=phase_info,
        )
        result = await validator.validate(context)
        assert result.status == ValidationStatus.PASS
        assert result.stage == "Phase"
        assert result.validator_id == "PHASE_VALIDATOR"

    @pytest.mark.asyncio
    async def test_phase_validator_returns_fail_without_phase_info(self):
        """Test PhaseValidator returns FAIL if phase_info is None."""
        validator = PhaseValidator()
        pattern = create_mock_pattern(pattern_type="SPRING")
        volume_analysis = create_mock_volume_analysis()

        context = ValidationContext(
            pattern=pattern,
            symbol="AAPL",
            timeframe="1d",
            volume_analysis=volume_analysis,
            phase_info=None,  # Missing phase_info
        )
        result = await validator.validate(context)
        assert result.status == ValidationStatus.FAIL
        assert "Phase information not available" in result.reason


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
        """Test LevelValidator returns PASS if trading_range present and valid.

        NOTE: Full validation tests are in test_level_validator.py.
        This test requires many complex domain models (Creek, Ice, Jump, TouchDetail).
        Skipping in favor of dedicated test file.
        """
        pytest.skip("Complex domain model setup - full tests in test_level_validator.py")

    @pytest.mark.asyncio
    async def test_level_validator_returns_fail_without_trading_range(self):
        """Test LevelValidator returns FAIL if trading_range is None."""
        validator = LevelValidator()
        pattern = create_mock_pattern(pattern_type="SPRING")
        volume_analysis = create_mock_volume_analysis()

        context = ValidationContext(
            pattern=pattern,
            symbol="AAPL",
            timeframe="1d",
            volume_analysis=volume_analysis,
            trading_range=None,  # Missing trading_range
        )
        result = await validator.validate(context)
        assert result.status == ValidationStatus.FAIL
        assert "Trading range" in result.reason


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
        """Test RiskValidator returns PASS if portfolio_context present and valid.

        NOTE: Full validation tests are in test_risk_validator.py.
        This test requires PortfolioContext with CorrelationConfig and entry/stop/target.
        Skipping in favor of dedicated test file.
        """
        pytest.skip("Complex domain model setup - full tests in test_risk_validator.py")

    @pytest.mark.asyncio
    async def test_risk_validator_returns_fail_without_portfolio_context(self):
        """Test RiskValidator returns FAIL if portfolio_context is None."""
        validator = RiskValidator()
        pattern = create_mock_pattern(pattern_type="SPRING")
        volume_analysis = create_mock_volume_analysis()

        context = ValidationContext(
            pattern=pattern,
            symbol="AAPL",
            timeframe="1d",
            volume_analysis=volume_analysis,
            portfolio_context=None,  # Missing portfolio_context
        )
        result = await validator.validate(context)
        assert result.status == ValidationStatus.FAIL
        assert "Portfolio context not available" in result.reason


class TestStrategyValidator:
    """Test StrategyValidator full implementation."""

    @pytest.mark.asyncio
    async def test_strategy_validator_properties(self):
        """Test StrategyValidator has correct properties."""
        mock_factory = Mock()
        validator = StrategyValidator(mock_factory)
        assert validator.validator_id == "STRATEGY_VALIDATOR"
        assert validator.stage_name == "Strategy"

    @pytest.mark.asyncio
    async def test_strategy_validator_returns_pass_with_market_context(self):
        """Test StrategyValidator returns PASS if market_context present (simplified).

        NOTE: Full tests in test_strategy_validator.py - this is basic smoke test.
        """
        pytest.skip("Skipping stub test - full implementation tested in test_strategy_validator.py")

    @pytest.mark.asyncio
    async def test_strategy_validator_returns_fail_without_market_context(self):
        """Test StrategyValidator returns FAIL if market_context is None."""
        mock_factory = Mock()
        validator = StrategyValidator(mock_factory)
        pattern = create_mock_pattern(pattern_type="SPRING")
        volume_analysis = create_mock_volume_analysis()

        context = ValidationContext(
            pattern=pattern,
            symbol="AAPL",
            timeframe="1d",
            volume_analysis=volume_analysis,
            market_context=None,  # Missing market_context
        )
        result = await validator.validate(context)
        assert result.status == ValidationStatus.FAIL
        assert "Market context not available" in result.reason
