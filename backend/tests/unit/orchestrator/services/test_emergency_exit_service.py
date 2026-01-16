"""
Unit tests for EmergencyExitService.

Story 18.10.5: Services Extraction and Orchestrator Facade (AC3)
"""

from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.orchestrator.services.emergency_exit_service import (
    EmergencyExitRequest,
    EmergencyExitResult,
    EmergencyExitService,
)


class TestEmergencyExitRequest:
    """Tests for EmergencyExitRequest dataclass."""

    def test_create_request(self):
        """Test creating an emergency exit request."""
        campaign_id = uuid4()
        request = EmergencyExitRequest(
            campaign_id=campaign_id,
            symbol="AAPL",
            reason="Spring low broken",
            current_price=Decimal("145.00"),
        )

        assert request.campaign_id == campaign_id
        assert request.symbol == "AAPL"
        assert request.reason == "Spring low broken"
        assert request.current_price == Decimal("145.00")
        assert request.correlation_id is None

    def test_create_request_with_correlation_id(self):
        """Test creating request with correlation ID."""
        campaign_id = uuid4()
        correlation_id = uuid4()
        request = EmergencyExitRequest(
            campaign_id=campaign_id,
            symbol="AAPL",
            reason="Ice broken",
            current_price=Decimal("142.00"),
            correlation_id=correlation_id,
        )

        assert request.correlation_id == correlation_id


class TestEmergencyExitResult:
    """Tests for EmergencyExitResult dataclass."""

    def test_create_success_result(self):
        """Test creating a successful result."""
        from datetime import UTC, datetime

        campaign_id = uuid4()
        result = EmergencyExitResult(
            success=True,
            campaign_id=campaign_id,
            exit_order_count=3,
            reason="Pattern invalidated",
            timestamp=datetime.now(UTC),
        )

        assert result.success is True
        assert result.campaign_id == campaign_id
        assert result.exit_order_count == 3

    def test_create_failure_result(self):
        """Test creating a failed result."""
        from datetime import UTC, datetime

        campaign_id = uuid4()
        result = EmergencyExitResult(
            success=False,
            campaign_id=campaign_id,
            exit_order_count=0,
            reason="Exit failed: connection error",
            timestamp=datetime.now(UTC),
        )

        assert result.success is False
        assert result.exit_order_count == 0


class TestEmergencyExitService:
    """Tests for EmergencyExitService."""

    @pytest.fixture
    def service(self) -> EmergencyExitService:
        """Create test service instance."""
        return EmergencyExitService()

    @pytest.fixture
    def mock_exit_manager(self):
        """Create mock exit manager."""
        manager = AsyncMock()
        manager.execute_emergency_exit = AsyncMock(return_value=[])
        return manager

    @pytest.mark.asyncio
    async def test_trigger_exit_without_manager(self, service: EmergencyExitService):
        """Test triggering exit without exit manager (logs only)."""
        request = EmergencyExitRequest(
            campaign_id=uuid4(),
            symbol="AAPL",
            reason="Spring low broken",
            current_price=Decimal("145.00"),
        )

        result = await service.trigger_exit(request)

        assert result.success is True
        assert result.exit_order_count == 0
        assert result.reason == "Spring low broken"

    @pytest.mark.asyncio
    async def test_trigger_exit_with_manager(self, mock_exit_manager):
        """Test triggering exit with exit manager."""
        # Mock returns 3 exit orders
        mock_exit_manager.execute_emergency_exit = AsyncMock(
            return_value=[{"id": 1}, {"id": 2}, {"id": 3}]
        )
        service = EmergencyExitService(exit_manager=mock_exit_manager)

        campaign_id = uuid4()
        request = EmergencyExitRequest(
            campaign_id=campaign_id,
            symbol="AAPL",
            reason="Ice broken",
            current_price=Decimal("142.00"),
        )

        result = await service.trigger_exit(request)

        assert result.success is True
        assert result.exit_order_count == 3
        mock_exit_manager.execute_emergency_exit.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_exit_manager_error(self, mock_exit_manager):
        """Test handling of exit manager errors."""
        mock_exit_manager.execute_emergency_exit = AsyncMock(
            side_effect=Exception("Connection error")
        )
        service = EmergencyExitService(exit_manager=mock_exit_manager)

        request = EmergencyExitRequest(
            campaign_id=uuid4(),
            symbol="AAPL",
            reason="UTAD exceeded",
            current_price=Decimal("155.00"),
        )

        result = await service.trigger_exit(request)

        assert result.success is False
        assert result.exit_order_count == 0
        assert "Exit failed" in result.reason

    @pytest.mark.asyncio
    async def test_get_exit_history(self, service: EmergencyExitService):
        """Test retrieving exit history."""
        # Trigger some exits
        request1 = EmergencyExitRequest(
            campaign_id=uuid4(),
            symbol="AAPL",
            reason="Spring low broken",
            current_price=Decimal("145.00"),
        )
        request2 = EmergencyExitRequest(
            campaign_id=uuid4(),
            symbol="MSFT",
            reason="Ice broken",
            current_price=Decimal("380.00"),
        )

        await service.trigger_exit(request1)
        await service.trigger_exit(request2)

        history = service.get_exit_history()

        assert len(history) == 2
        assert history[0].reason == "Spring low broken"
        assert history[1].reason == "Ice broken"

    @pytest.mark.asyncio
    async def test_clear_history(self, service: EmergencyExitService):
        """Test clearing exit history."""
        request = EmergencyExitRequest(
            campaign_id=uuid4(),
            symbol="AAPL",
            reason="Test",
            current_price=Decimal("150.00"),
        )
        await service.trigger_exit(request)

        assert len(service.get_exit_history()) == 1

        service.clear_history()

        assert len(service.get_exit_history()) == 0

    @pytest.mark.asyncio
    async def test_history_is_copy(self, service: EmergencyExitService):
        """Test that get_exit_history returns a copy."""
        request = EmergencyExitRequest(
            campaign_id=uuid4(),
            symbol="AAPL",
            reason="Test",
            current_price=Decimal("150.00"),
        )
        await service.trigger_exit(request)

        history = service.get_exit_history()
        history.clear()

        # Original history should be unchanged
        assert len(service.get_exit_history()) == 1
