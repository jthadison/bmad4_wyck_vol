"""
Forex Session Service.

Provides forex trading session detection and session-aware validation.

Story 18.10.5: Services Extraction and Orchestrator Facade (AC1)
"""

from datetime import UTC, datetime
from typing import NamedTuple

import structlog

from src.models.forex import ForexSession, get_forex_session

logger = structlog.get_logger(__name__)


class SessionInfo(NamedTuple):
    """Information about a forex trading session."""

    session: ForexSession
    is_high_liquidity: bool
    volume_multiplier: float


class ForexSessionService:
    """
    Service for forex session detection and session-aware operations.

    Provides session classification and liquidity assessment for
    forex-specific volume validation adjustments.

    Example:
        >>> service = ForexSessionService()
        >>> info = service.get_session_info(datetime.now(UTC))
        >>> if info.is_high_liquidity:
        ...     # Apply stricter volume thresholds
        ...     pass
    """

    # Session liquidity and volume multipliers
    _SESSION_CONFIG: dict[ForexSession, tuple[bool, float]] = {
        ForexSession.ASIAN: (False, 0.7),  # Low liquidity, lower threshold
        ForexSession.LONDON: (True, 1.0),  # High liquidity, standard threshold
        ForexSession.OVERLAP: (True, 1.2),  # Peak liquidity, higher threshold
        ForexSession.NY: (True, 1.0),  # High liquidity, standard threshold
        ForexSession.NY_CLOSE: (False, 0.8),  # Declining liquidity
    }

    def get_current_session(self) -> ForexSession:
        """Get current forex trading session based on UTC time."""
        return get_forex_session(datetime.now(UTC))

    def get_session_info(self, timestamp: datetime) -> SessionInfo:
        """
        Get detailed session information for a timestamp.

        Args:
            timestamp: UTC datetime to classify

        Returns:
            SessionInfo with session, liquidity flag, and volume multiplier
        """
        session = get_forex_session(timestamp)
        is_high_liquidity, volume_multiplier = self._SESSION_CONFIG[session]

        logger.debug(
            "forex_session_classified",
            timestamp=timestamp.isoformat(),
            session=session.value,
            is_high_liquidity=is_high_liquidity,
            volume_multiplier=volume_multiplier,
        )

        return SessionInfo(
            session=session,
            is_high_liquidity=is_high_liquidity,
            volume_multiplier=volume_multiplier,
        )

    def is_trading_allowed(self, timestamp: datetime) -> bool:
        """
        Check if trading is recommended during this session.

        Returns True for high-liquidity sessions (London, Overlap, NY).
        """
        info = self.get_session_info(timestamp)
        return info.is_high_liquidity

    def get_volume_adjustment(self, timestamp: datetime) -> float:
        """
        Get volume threshold adjustment multiplier for session.

        Returns multiplier to apply to standard volume thresholds.
        """
        info = self.get_session_info(timestamp)
        return info.volume_multiplier
