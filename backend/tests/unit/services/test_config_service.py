"""
Unit tests for ConfigurationService.

Tests configuration validation and business logic.
"""

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from src.models.config import (
    CauseFactors,
    PatternConfidence,
    RiskLimits,
    SystemConfiguration,
    VolumeThresholds,
)
from src.repositories.config_repository import OptimisticLockError
from src.services.config_service import ConfigurationService


@pytest.fixture
def mock_session():
    """Create mock database session."""
    return AsyncMock()


@pytest.fixture
def config_service(mock_session):
    """Create ConfigurationService with mock session."""
    return ConfigurationService(mock_session)


@pytest.fixture
def valid_config():
    """Create valid test configuration."""
    return SystemConfiguration(
        volume_thresholds=VolumeThresholds(
            spring_volume_min=Decimal("0.7"),
            spring_volume_max=Decimal("1.0"),
            sos_volume_min=Decimal("2.0"),
            lps_volume_min=Decimal("0.5"),
            utad_volume_max=Decimal("0.7"),
        ),
        risk_limits=RiskLimits(
            max_risk_per_trade=Decimal("2.0"),
            max_campaign_risk=Decimal("5.0"),
            max_portfolio_heat=Decimal("10.0"),
        ),
        cause_factors=CauseFactors(
            min_cause_factor=Decimal("2.0"), max_cause_factor=Decimal("3.0")
        ),
        pattern_confidence=PatternConfidence(
            min_spring_confidence=70,
            min_sos_confidence=70,
            min_lps_confidence=70,
            min_utad_confidence=70,
        ),
    )


class TestConfigurationValidation:
    """Tests for configuration validation business rules."""

    def test_valid_configuration_passes(self, config_service, valid_config):
        """Test that valid configuration passes validation."""
        # Should not raise any exceptions
        config_service._validate_business_rules(valid_config)

    def test_invalid_risk_hierarchy_fails(self, config_service, valid_config):
        """Test that invalid risk limit hierarchy fails validation."""
        # Set max_campaign_risk equal to max_risk_per_trade (invalid)
        valid_config.risk_limits.max_campaign_risk = Decimal("2.0")

        with pytest.raises(ValueError, match="Risk limits must satisfy"):
            config_service._validate_business_rules(valid_config)

    def test_invalid_risk_hierarchy_portfolio_heat_fails(self, config_service, valid_config):
        """Test that portfolio heat less than campaign risk fails."""
        # Set max_portfolio_heat less than max_campaign_risk (invalid)
        valid_config.risk_limits.max_portfolio_heat = Decimal("4.0")

        with pytest.raises(ValueError, match="Risk limits must satisfy"):
            config_service._validate_business_rules(valid_config)

    def test_invalid_cause_factor_range_fails(self, config_service, valid_config):
        """Test that min_cause_factor >= max_cause_factor fails."""
        # Set min equal to max (invalid)
        valid_config.cause_factors.min_cause_factor = Decimal("3.0")

        with pytest.raises(ValueError, match="min_cause_factor must be less than"):
            config_service._validate_business_rules(valid_config)

    def test_invalid_spring_volume_range_fails(self, config_service, valid_config):
        """Test that spring_volume_min > spring_volume_max fails."""
        # Set min greater than max (invalid)
        valid_config.volume_thresholds.spring_volume_min = Decimal("1.0")
        valid_config.volume_thresholds.spring_volume_max = Decimal("0.7")

        with pytest.raises(ValueError, match="spring_volume_min must be less than"):
            config_service._validate_business_rules(valid_config)


class TestConfigurationUpdate:
    """Tests for configuration update operations."""

    @pytest.mark.asyncio
    async def test_update_configuration_success(self, config_service, valid_config):
        """Test successful configuration update."""
        # Mock repository to return updated config with applied_by set
        updated_config = valid_config.model_copy()
        updated_config.version = 2
        updated_config.applied_by = "test_user"
        config_service.repository.update_config = AsyncMock(return_value=updated_config)

        result = await config_service.update_configuration(
            config=valid_config, current_version=1, applied_by="test_user"
        )

        assert result.version == 2
        assert result.applied_by == "test_user"
        config_service.repository.update_config.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_configuration_optimistic_lock_error(self, config_service, valid_config):
        """Test that optimistic lock error is propagated."""
        # Mock repository to raise OptimisticLockError
        config_service.repository.update_config = AsyncMock(
            side_effect=OptimisticLockError("Version conflict")
        )

        with pytest.raises(OptimisticLockError, match="Version conflict"):
            await config_service.update_configuration(config=valid_config, current_version=1)

    @pytest.mark.asyncio
    async def test_update_configuration_validation_error(self, config_service, valid_config):
        """Test that validation errors prevent update."""
        # Create invalid config (risk hierarchy violated)
        invalid_config = valid_config.model_copy()
        invalid_config.risk_limits.max_campaign_risk = Decimal("1.5")

        with pytest.raises(ValueError, match="Risk limits must satisfy"):
            await config_service.update_configuration(config=invalid_config, current_version=1)


class TestPydanticValidation:
    """Tests for Pydantic field validation in models."""

    def test_spring_volume_above_1_0_fails(self):
        """Test that spring volume > 1.0x fails Wyckoff validation."""
        with pytest.raises(ValueError, match="Spring patterns require volume BELOW average"):
            VolumeThresholds(
                spring_volume_min=Decimal("1.1"),  # Invalid: > 1.0x
                sos_volume_min=Decimal("2.0"),
            )

    def test_sos_volume_below_1_5_fails(self):
        """Test that SOS volume < 1.5x fails Wyckoff validation."""
        with pytest.raises(ValueError, match="Sign of Strength requires volume expansion"):
            VolumeThresholds(
                spring_volume_min=Decimal("0.7"),
                sos_volume_min=Decimal("1.0"),  # Invalid: < 1.5x
            )

    def test_min_cause_factor_below_2_0_fails(self):
        """Test that min_cause_factor < 2.0 fails Wyckoff validation."""
        with pytest.raises(ValueError, match="Wyckoff methodology requires minimum 2:1"):
            CauseFactors(
                min_cause_factor=Decimal("1.5"),  # Invalid: < 2.0
                max_cause_factor=Decimal("3.0"),
            )

    def test_risk_limits_hierarchy_validation(self):
        """Test risk limits hierarchy: campaign > per-trade."""
        with pytest.raises(ValueError, match="max_campaign_risk must be greater than"):
            RiskLimits(
                max_risk_per_trade=Decimal("3.0"),
                max_campaign_risk=Decimal("3.0"),  # Invalid: equal to per-trade, must be greater
                max_portfolio_heat=Decimal("10.0"),
            )

    def test_pattern_confidence_bounds(self):
        """Test pattern confidence must be between 70 and 95."""
        with pytest.raises(ValueError):
            PatternConfidence(
                min_spring_confidence=60  # Invalid: below 70
            )

        with pytest.raises(ValueError):
            PatternConfidence(
                min_spring_confidence=100  # Invalid: above 95
            )
