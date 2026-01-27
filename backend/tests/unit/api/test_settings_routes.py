"""
Unit tests for Settings API Routes

Tests IP address validation and other route utilities.
Story 19.14: Auto-Execution Configuration Backend
Story 19.22: Emergency Kill Switch
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from src.api.routes.settings import validate_ip_address
from src.models.auto_execution_config import AutoExecutionConfigResponse


class TestIPAddressValidation:
    """Tests for IP address validation."""

    def test_valid_ipv4_address(self):
        """Test validation of valid IPv4 address."""
        result = validate_ip_address("192.168.1.1")
        assert result == "192.168.1.1"

    def test_valid_ipv6_address(self):
        """Test validation of valid IPv6 address."""
        result = validate_ip_address("2001:0db8:85a3:0000:0000:8a2e:0370:7334")
        # ipaddress normalizes IPv6 addresses
        assert result == "2001:db8:85a3::8a2e:370:7334"

    def test_ipv6_shorthand(self):
        """Test validation of IPv6 shorthand notation."""
        result = validate_ip_address("::1")
        assert result == "::1"

    def test_unknown_ip_allowed(self):
        """Test that 'unknown' is allowed as a special case."""
        result = validate_ip_address("unknown")
        assert result == "unknown"

    def test_invalid_ip_format_raises_error(self):
        """Test that invalid IP format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid IP address format"):
            validate_ip_address("not-an-ip")

    def test_empty_string_raises_error(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid IP address format"):
            validate_ip_address("")

    def test_invalid_ipv4_raises_error(self):
        """Test that invalid IPv4 raises ValueError."""
        with pytest.raises(ValueError, match="Invalid IP address format"):
            validate_ip_address("256.256.256.256")

    def test_localhost_ipv4(self):
        """Test validation of localhost IPv4."""
        result = validate_ip_address("127.0.0.1")
        assert result == "127.0.0.1"

    def test_localhost_ipv6(self):
        """Test validation of localhost IPv6."""
        result = validate_ip_address("::1")
        assert result == "::1"


class TestKillSwitchActivation:
    """Tests for kill switch activation endpoint (Story 19.22)."""

    @pytest.fixture
    def mock_service(self):
        """Create mock AutoExecutionConfigService."""
        return AsyncMock()

    @pytest.fixture
    def mock_websocket_manager(self):
        """Create mock WebSocket manager."""
        manager = AsyncMock()
        manager.broadcast = AsyncMock()
        return manager

    @pytest.fixture
    def sample_config(self):
        """Create sample config response."""
        return AutoExecutionConfigResponse(
            enabled=True,
            min_confidence=Decimal("85.0"),
            max_trades_per_day=10,
            max_risk_per_day=Decimal("2.0"),
            circuit_breaker_losses=3,
            enabled_patterns=["SPRING", "UTAD"],
            symbol_whitelist=None,
            symbol_blacklist=[],
            trades_today=0,
            risk_today=Decimal("0.0"),
            consent_given_at=datetime.now(UTC),
            kill_switch_active=False,
        )

    @pytest.mark.asyncio
    async def test_activate_kill_switch_success(
        self, mock_service, mock_websocket_manager, sample_config
    ):
        """Test successful kill switch activation."""
        # Arrange
        user_id = uuid4()
        sample_config.kill_switch_active = True
        mock_service.activate_kill_switch.return_value = sample_config

        with (
            patch(
                "src.api.routes.settings.AutoExecutionConfigService",
                return_value=mock_service,
            ),
            patch(
                "src.api.routes.settings.websocket_manager",
                mock_websocket_manager,
            ),
        ):
            # Import after patching
            from src.api.routes.settings import activate_kill_switch

            # Mock dependencies
            mock_db = AsyncMock()

            # Act
            result = await activate_kill_switch(user_id=user_id, db=mock_db)

            # Assert
            assert result.kill_switch_active is True
            assert result.activated_at is not None
            mock_service.activate_kill_switch.assert_called_once_with(user_id)
            mock_websocket_manager.broadcast.assert_called_once()

            # Verify broadcast message structure
            broadcast_call = mock_websocket_manager.broadcast.call_args
            message = broadcast_call[0][0]
            assert message["type"] == "kill_switch_activated"
            assert "message" in message
            assert "activated_at" in message
            assert message["user_id"] == str(user_id)

    @pytest.mark.asyncio
    async def test_activate_kill_switch_config_not_found(self, mock_service):
        """Test kill switch activation when config doesn't exist."""
        # Arrange
        user_id = uuid4()
        mock_service.activate_kill_switch.side_effect = ValueError("Configuration not found")

        with patch(
            "src.api.routes.settings.AutoExecutionConfigService",
            return_value=mock_service,
        ):
            from fastapi import HTTPException

            from src.api.routes.settings import activate_kill_switch

            mock_db = AsyncMock()

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await activate_kill_switch(user_id=user_id, db=mock_db)

            assert exc_info.value.status_code == 404
            assert "Configuration not found" in exc_info.value.detail


class TestKillSwitchDeactivation:
    """Tests for kill switch deactivation endpoint (Story 19.22)."""

    @pytest.fixture
    def mock_service(self):
        """Create mock AutoExecutionConfigService."""
        return AsyncMock()

    @pytest.fixture
    def sample_config(self):
        """Create sample config response."""
        return AutoExecutionConfigResponse(
            enabled=True,
            min_confidence=Decimal("85.0"),
            max_trades_per_day=10,
            max_risk_per_day=Decimal("2.0"),
            circuit_breaker_losses=3,
            enabled_patterns=["SPRING", "UTAD"],
            symbol_whitelist=None,
            symbol_blacklist=[],
            trades_today=0,
            risk_today=Decimal("0.0"),
            consent_given_at=datetime.now(UTC),
            kill_switch_active=False,
        )

    @pytest.mark.asyncio
    async def test_deactivate_kill_switch_success(self, mock_service, sample_config):
        """Test successful kill switch deactivation."""
        # Arrange
        user_id = uuid4()
        sample_config.kill_switch_active = False
        mock_service.deactivate_kill_switch.return_value = sample_config

        with patch(
            "src.api.routes.settings.AutoExecutionConfigService",
            return_value=mock_service,
        ):
            from src.api.routes.settings import deactivate_kill_switch

            mock_db = AsyncMock()

            # Act
            result = await deactivate_kill_switch(user_id=user_id, db=mock_db)

            # Assert
            assert result.kill_switch_active is False
            mock_service.deactivate_kill_switch.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_deactivate_kill_switch_config_not_found(self, mock_service):
        """Test kill switch deactivation when config doesn't exist."""
        # Arrange
        user_id = uuid4()
        mock_service.deactivate_kill_switch.side_effect = ValueError("Configuration not found")

        with patch(
            "src.api.routes.settings.AutoExecutionConfigService",
            return_value=mock_service,
        ):
            from fastapi import HTTPException

            from src.api.routes.settings import deactivate_kill_switch

            mock_db = AsyncMock()

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await deactivate_kill_switch(user_id=user_id, db=mock_db)

            assert exc_info.value.status_code == 404
            assert "Configuration not found" in exc_info.value.detail
