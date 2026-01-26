"""
Unit tests for Auto-Execution Configuration Service

Tests configuration CRUD operations, validation logic, and signal eligibility.
Story 19.14: Auto-Execution Configuration Backend
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.models.auto_execution_config import (
    AutoExecutionConfig,
    AutoExecutionConfigUpdate,
)
from src.models.signal import ConfidenceComponents, TargetLevels, TradeSignal
from src.models.validation import StageValidationResult, ValidationChain, ValidationStatus
from src.services.auto_execution_config_service import AutoExecutionConfigService


@pytest.fixture
def mock_repository():
    """Create a mock repository."""
    return AsyncMock()


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def service(mock_session, mock_repository):
    """Create service with mock dependencies."""
    service = AutoExecutionConfigService(mock_session)
    service.repository = mock_repository
    return service


@pytest.fixture
def default_config():
    """Create default auto-execution configuration."""
    user_id = uuid4()
    now = datetime.now(UTC)
    return AutoExecutionConfig(
        user_id=user_id,
        enabled=False,
        min_confidence=Decimal("85.00"),
        max_trades_per_day=10,
        max_risk_per_day=None,
        circuit_breaker_losses=3,
        enabled_patterns=["SPRING", "SOS", "LPS"],
        symbol_whitelist=None,
        symbol_blacklist=None,
        kill_switch_active=False,
        consent_given_at=None,
        consent_ip_address=None,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def enabled_config(default_config):
    """Create enabled configuration with consent."""
    default_config.enabled = True
    default_config.consent_given_at = datetime.now(UTC)
    default_config.consent_ip_address = "192.168.1.1"
    return default_config


@pytest.fixture
def sample_signal():
    """Create a sample trade signal."""
    confidence_components = ConfidenceComponents(
        pattern_confidence=90,
        phase_confidence=85,
        volume_confidence=80,
        overall_confidence=87,
    )

    target_levels = TargetLevels(
        primary_target=Decimal("156.00"),
        secondary_targets=[],
    )

    validation_chain = ValidationChain(
        pattern_id=uuid4(),
        validation_results=[
            StageValidationResult(
                stage="VOLUME",
                status=ValidationStatus.PASS,
                validator_id="VolumeValidator",
                metadata={},
            )
        ],
    )

    return TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        asset_class="STOCK",
        pattern_type="SPRING",
        phase="C",
        timeframe="1H",
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("148.00"),
        target_levels=target_levels,
        position_size=Decimal("100"),
        position_size_unit="SHARES",
        notional_value=Decimal("15000.00"),
        risk_amount=Decimal("200.00"),
        r_multiple=Decimal("3.0"),
        confidence_score=87,
        confidence_components=confidence_components,
        validation_chain=validation_chain,
        timestamp=datetime.now(UTC),
    )


class TestConfigurationRetrieval:
    """Tests for get_config operation."""

    @pytest.mark.asyncio
    async def test_get_config_returns_existing(self, service, mock_repository, default_config):
        """Test retrieving existing configuration."""
        mock_repository.get_or_create_config.return_value = default_config

        result = await service.get_config(default_config.user_id)

        assert result.enabled == default_config.enabled
        assert result.min_confidence == default_config.min_confidence
        assert result.trades_today == 0
        assert result.risk_today == Decimal("0.0")
        mock_repository.get_or_create_config.assert_called_once_with(default_config.user_id)


class TestConfigurationUpdate:
    """Tests for update_config operation."""

    @pytest.mark.asyncio
    async def test_update_min_confidence(self, service, mock_repository, default_config):
        """Test updating minimum confidence threshold."""
        updates = AutoExecutionConfigUpdate(min_confidence=Decimal("90.00"))

        # Mock update to return updated config
        updated_config = default_config.model_copy()
        updated_config.min_confidence = Decimal("90.00")
        mock_repository.update_config.return_value = updated_config

        # Mock get_or_create to return default first, then updated config
        mock_repository.get_or_create_config.side_effect = [default_config, updated_config]

        result = await service.update_config(default_config.user_id, updates)

        assert result.min_confidence == Decimal("90.00")
        mock_repository.update_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_enabled_patterns(self, service, mock_repository, default_config):
        """Test updating enabled patterns."""
        updates = AutoExecutionConfigUpdate(enabled_patterns=["SPRING"])

        updated_config = default_config.model_copy()
        updated_config.enabled_patterns = ["SPRING"]
        mock_repository.update_config.return_value = updated_config

        # Mock get_or_create to return default first, then updated config
        mock_repository.get_or_create_config.side_effect = [default_config, updated_config]

        result = await service.update_config(default_config.user_id, updates)

        assert result.enabled_patterns == ["SPRING"]
        assert "SPRING" in result.enabled_patterns

    @pytest.mark.asyncio
    async def test_update_multiple_fields(self, service, mock_repository, default_config):
        """Test updating multiple configuration fields."""
        updates = AutoExecutionConfigUpdate(
            min_confidence=Decimal("92.00"),
            max_trades_per_day=5,
            enabled_patterns=["SPRING", "SOS"],
        )

        updated_config = default_config.model_copy()
        updated_config.min_confidence = Decimal("92.00")
        updated_config.max_trades_per_day = 5
        updated_config.enabled_patterns = ["SPRING", "SOS"]
        mock_repository.update_config.return_value = updated_config

        # Mock get_or_create to return default first, then updated config
        mock_repository.get_or_create_config.side_effect = [default_config, updated_config]

        result = await service.update_config(default_config.user_id, updates)

        assert result.min_confidence == Decimal("92.00")
        assert result.max_trades_per_day == 5
        assert len(result.enabled_patterns) == 2


class TestEnableDisable:
    """Tests for enable/disable operations."""

    @pytest.mark.asyncio
    async def test_enable_with_consent(self, service, mock_repository, default_config):
        """Test enabling auto-execution with consent tracking."""
        consent_ip = "192.168.1.100"

        enabled_config = default_config.model_copy()
        enabled_config.enabled = True
        enabled_config.consent_given_at = datetime.now(UTC)
        enabled_config.consent_ip_address = consent_ip
        mock_repository.enable.return_value = enabled_config

        # Mock get_or_create to return default first, then enabled config
        mock_repository.get_or_create_config.side_effect = [default_config, enabled_config]

        result = await service.enable_auto_execution(default_config.user_id, consent_ip)

        assert result.enabled is True
        mock_repository.enable.assert_called_once_with(default_config.user_id, consent_ip)

    @pytest.mark.asyncio
    async def test_disable(self, service, mock_repository, enabled_config):
        """Test disabling auto-execution."""
        disabled_config = enabled_config.model_copy()
        disabled_config.enabled = False
        mock_repository.disable.return_value = disabled_config

        # Mock get_or_create to return disabled config after disable
        mock_repository.get_or_create_config.return_value = disabled_config

        result = await service.disable_auto_execution(enabled_config.user_id)

        assert result.enabled is False
        mock_repository.disable.assert_called_once_with(enabled_config.user_id)


class TestKillSwitch:
    """Tests for kill switch operations."""

    @pytest.mark.asyncio
    async def test_activate_kill_switch(self, service, mock_repository, enabled_config):
        """Test activating emergency kill switch."""
        kill_switch_config = enabled_config.model_copy()
        kill_switch_config.kill_switch_active = True
        mock_repository.activate_kill_switch.return_value = kill_switch_config

        # Mock get_or_create to return kill switch config after activation
        mock_repository.get_or_create_config.return_value = kill_switch_config

        result = await service.activate_kill_switch(enabled_config.user_id)

        assert result.kill_switch_active is True
        mock_repository.activate_kill_switch.assert_called_once()

    @pytest.mark.asyncio
    async def test_deactivate_kill_switch(self, service, mock_repository, enabled_config):
        """Test deactivating kill switch."""
        deactivated_config = enabled_config.model_copy()
        deactivated_config.kill_switch_active = False
        mock_repository.update_config.return_value = deactivated_config

        # Mock get_or_create to return deactivated config
        mock_repository.get_or_create_config.return_value = deactivated_config

        result = await service.deactivate_kill_switch(enabled_config.user_id)

        assert result.kill_switch_active is False
        mock_repository.update_config.assert_called_once()


class TestSignalEligibility:
    """Tests for is_signal_eligible validation."""

    @pytest.mark.asyncio
    async def test_eligible_signal(self, service, mock_repository, enabled_config, sample_signal):
        """Test signal that passes all eligibility checks."""
        mock_repository.get_config.return_value = enabled_config

        eligible, reason = await service.is_signal_eligible(enabled_config.user_id, sample_signal)

        assert eligible is True
        assert "eligible" in reason.lower()

    @pytest.mark.asyncio
    async def test_disabled_rejected(self, service, mock_repository, default_config, sample_signal):
        """Test signal rejected when auto-execution is disabled."""
        mock_repository.get_config.return_value = default_config

        eligible, reason = await service.is_signal_eligible(default_config.user_id, sample_signal)

        assert eligible is False
        assert "disabled" in reason.lower()

    @pytest.mark.asyncio
    async def test_kill_switch_rejected(
        self, service, mock_repository, enabled_config, sample_signal
    ):
        """Test signal rejected when kill switch is active."""
        enabled_config.kill_switch_active = True
        mock_repository.get_config.return_value = enabled_config

        eligible, reason = await service.is_signal_eligible(enabled_config.user_id, sample_signal)

        assert eligible is False
        assert "kill switch" in reason.lower()

    @pytest.mark.asyncio
    async def test_no_consent_rejected(
        self, service, mock_repository, default_config, sample_signal
    ):
        """Test signal rejected when consent not given."""
        default_config.enabled = True  # Enable but no consent
        mock_repository.get_config.return_value = default_config

        eligible, reason = await service.is_signal_eligible(default_config.user_id, sample_signal)

        assert eligible is False
        assert "consent" in reason.lower()

    @pytest.mark.asyncio
    async def test_low_confidence_rejected(
        self, service, mock_repository, enabled_config, sample_signal
    ):
        """Test signal rejected when confidence below threshold."""
        sample_signal.confidence_score = 80.0  # Below 85% threshold
        mock_repository.get_config.return_value = enabled_config

        eligible, reason = await service.is_signal_eligible(enabled_config.user_id, sample_signal)

        assert eligible is False
        assert "confidence" in reason.lower()

    @pytest.mark.asyncio
    async def test_pattern_not_enabled_rejected(
        self, service, mock_repository, enabled_config, sample_signal
    ):
        """Test signal rejected when pattern not enabled."""
        sample_signal.pattern_type = "UTAD"  # Not in enabled_patterns
        mock_repository.get_config.return_value = enabled_config

        eligible, reason = await service.is_signal_eligible(enabled_config.user_id, sample_signal)

        assert eligible is False
        assert "pattern" in reason.lower()

    @pytest.mark.asyncio
    async def test_symbol_whitelist_rejected(
        self, service, mock_repository, enabled_config, sample_signal
    ):
        """Test signal rejected when symbol not in whitelist."""
        enabled_config.symbol_whitelist = ["TSLA", "NVDA"]  # AAPL not in list
        mock_repository.get_config.return_value = enabled_config

        eligible, reason = await service.is_signal_eligible(enabled_config.user_id, sample_signal)

        assert eligible is False
        assert "whitelist" in reason.lower()

    @pytest.mark.asyncio
    async def test_symbol_blacklist_rejected(
        self, service, mock_repository, enabled_config, sample_signal
    ):
        """Test signal rejected when symbol in blacklist."""
        enabled_config.symbol_blacklist = ["AAPL"]
        mock_repository.get_config.return_value = enabled_config

        eligible, reason = await service.is_signal_eligible(enabled_config.user_id, sample_signal)

        assert eligible is False
        assert "blacklist" in reason.lower()


class TestConfigValidation:
    """Tests for validate_config method."""

    def test_valid_config(self, service, default_config):
        """Test validation passes for valid configuration."""
        errors = service.validate_config(default_config)
        assert len(errors) == 0

    def test_min_confidence_too_low(self, service, default_config):
        """Test validation fails when min_confidence < 60."""
        default_config.min_confidence = Decimal("50.00")
        errors = service.validate_config(default_config)
        assert any("60%" in error for error in errors)

    def test_min_confidence_too_high(self, service, default_config):
        """Test validation fails when min_confidence > 100."""
        default_config.min_confidence = Decimal("105.00")
        errors = service.validate_config(default_config)
        assert any("100%" in error for error in errors)

    def test_max_trades_too_low(self, service, default_config):
        """Test validation fails when max_trades_per_day < 1."""
        default_config.max_trades_per_day = 0
        errors = service.validate_config(default_config)
        assert any("at least 1" in error for error in errors)

    def test_max_trades_too_high(self, service, default_config):
        """Test validation fails when max_trades_per_day > 50."""
        default_config.max_trades_per_day = 100
        errors = service.validate_config(default_config)
        assert any("50" in error for error in errors)

    def test_max_risk_too_high(self, service, default_config):
        """Test validation fails when max_risk_per_day > 10%."""
        default_config.max_risk_per_day = Decimal("15.00")
        errors = service.validate_config(default_config)
        assert any("10%" in error for error in errors)

    def test_enabled_without_consent(self, service, default_config):
        """Test validation fails when enabled without consent."""
        default_config.enabled = True
        default_config.consent_given_at = None
        errors = service.validate_config(default_config)
        assert any("consent" in error.lower() for error in errors)

    def test_invalid_pattern(self, service, default_config):
        """Test validation fails with invalid pattern type."""
        default_config.enabled_patterns = ["SPRING", "INVALID_PATTERN"]
        errors = service.validate_config(default_config)
        assert any("invalid" in error.lower() for error in errors)
