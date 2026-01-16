"""
Unit tests for ForexSessionService.

Story 18.10.5: Services Extraction and Orchestrator Facade (AC1)
"""

from datetime import UTC, datetime

import pytest

from src.models.forex import ForexSession
from src.orchestrator.services.forex_session_service import ForexSessionService, SessionInfo


class TestForexSessionService:
    """Tests for ForexSessionService."""

    @pytest.fixture
    def service(self) -> ForexSessionService:
        """Create test service instance."""
        return ForexSessionService()

    def test_get_session_info_asian(self, service: ForexSessionService):
        """Test Asian session classification."""
        timestamp = datetime(2025, 1, 15, 3, 0, tzinfo=UTC)  # 3 AM UTC
        info = service.get_session_info(timestamp)

        assert info.session == ForexSession.ASIAN
        assert info.is_high_liquidity is False
        assert info.volume_multiplier == 0.7

    def test_get_session_info_london(self, service: ForexSessionService):
        """Test London session classification."""
        timestamp = datetime(2025, 1, 15, 10, 0, tzinfo=UTC)  # 10 AM UTC
        info = service.get_session_info(timestamp)

        assert info.session == ForexSession.LONDON
        assert info.is_high_liquidity is True
        assert info.volume_multiplier == 1.0

    def test_get_session_info_overlap(self, service: ForexSessionService):
        """Test London/NY overlap classification."""
        timestamp = datetime(2025, 1, 15, 14, 0, tzinfo=UTC)  # 2 PM UTC
        info = service.get_session_info(timestamp)

        assert info.session == ForexSession.OVERLAP
        assert info.is_high_liquidity is True
        assert info.volume_multiplier == 1.2

    def test_get_session_info_ny(self, service: ForexSessionService):
        """Test NY session classification."""
        timestamp = datetime(2025, 1, 15, 18, 0, tzinfo=UTC)  # 6 PM UTC
        info = service.get_session_info(timestamp)

        assert info.session == ForexSession.NY
        assert info.is_high_liquidity is True
        assert info.volume_multiplier == 1.0

    def test_get_session_info_ny_close(self, service: ForexSessionService):
        """Test NY close session classification."""
        timestamp = datetime(2025, 1, 15, 21, 0, tzinfo=UTC)  # 9 PM UTC
        info = service.get_session_info(timestamp)

        assert info.session == ForexSession.NY_CLOSE
        assert info.is_high_liquidity is False
        assert info.volume_multiplier == 0.8

    def test_is_trading_allowed_high_liquidity(self, service: ForexSessionService):
        """Test trading allowed during high liquidity sessions."""
        timestamp = datetime(2025, 1, 15, 14, 0, tzinfo=UTC)  # Overlap
        assert service.is_trading_allowed(timestamp) is True

    def test_is_trading_allowed_low_liquidity(self, service: ForexSessionService):
        """Test trading not recommended during low liquidity sessions."""
        timestamp = datetime(2025, 1, 15, 3, 0, tzinfo=UTC)  # Asian
        assert service.is_trading_allowed(timestamp) is False

    def test_get_volume_adjustment_overlap(self, service: ForexSessionService):
        """Test volume adjustment for overlap session."""
        timestamp = datetime(2025, 1, 15, 14, 0, tzinfo=UTC)
        assert service.get_volume_adjustment(timestamp) == 1.2

    def test_get_volume_adjustment_asian(self, service: ForexSessionService):
        """Test volume adjustment for asian session."""
        timestamp = datetime(2025, 1, 15, 3, 0, tzinfo=UTC)
        assert service.get_volume_adjustment(timestamp) == 0.7

    def test_session_info_is_named_tuple(self, service: ForexSessionService):
        """Test that session info is a proper NamedTuple."""
        timestamp = datetime(2025, 1, 15, 10, 0, tzinfo=UTC)
        info = service.get_session_info(timestamp)

        assert isinstance(info, SessionInfo)
        assert hasattr(info, "session")
        assert hasattr(info, "is_high_liquidity")
        assert hasattr(info, "volume_multiplier")
