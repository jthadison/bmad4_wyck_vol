"""
Campaign Core Identity and State - Story 22.10

Purpose:
--------
Core campaign identity and state tracking extracted from the monolithic Campaign
dataclass for improved Single Responsibility Principle compliance.

Contains the minimal information needed to identify and track a campaign's basic
lifecycle, without risk, performance, or volume details.

Classes:
--------
- CampaignState: Campaign lifecycle states enum
- CampaignCore: Core campaign identity and state dataclass

Author: Story 22.10 - Decompose Campaign Dataclass
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class CampaignState(Enum):
    """
    Campaign lifecycle states.

    State Transitions:
    - FORMING: 1 pattern detected, waiting for second pattern
    - ACTIVE: 2+ patterns, campaign is actionable
    - DORMANT: Campaign inactive but not failed (no recent patterns)
    - COMPLETED: Campaign reached Phase E or successful exit
    - FAILED: Exceeded 72h expiration without completion
    - CANCELLED: Manual or system cancellation

    Usage:
        >>> state = CampaignState.FORMING
        >>> if state == CampaignState.ACTIVE:
        ...     print("Campaign is actionable")
    """

    FORMING = "FORMING"
    ACTIVE = "ACTIVE"
    DORMANT = "DORMANT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Terminal states that cannot transition to other states
TERMINAL_STATES = frozenset(
    {
        CampaignState.COMPLETED,
        CampaignState.FAILED,
        CampaignState.CANCELLED,
    }
)


@dataclass
class CampaignCore:
    """
    Core campaign identity and state.

    Contains the minimal information needed to identify and track a campaign's
    basic lifecycle. This is the foundation for campaign tracking, with other
    aspects (risk, performance, volume) tracked in separate focused models.

    Attributes:
        campaign_id: Unique campaign identifier (UUID string)
        symbol: Trading symbol (e.g., "AAPL", "EURUSD")
        start_time: First pattern timestamp
        state: Current campaign state (FORMING/ACTIVE/COMPLETED/FAILED)
        patterns: List of detected patterns in chronological order
        timeframe: Chart timeframe (e.g., "1d", "4h", "1h")
        asset_class: Asset class type (e.g., "stock", "forex", "crypto")
        end_time: Campaign completion timestamp (None if still active)
        current_phase: Current Wyckoff phase based on pattern sequence

    Example:
        >>> from datetime import datetime, UTC
        >>> core = CampaignCore(
        ...     campaign_id="abc123",
        ...     symbol="AAPL",
        ...     start_time=datetime.now(UTC),
        ...     timeframe="1d"
        ... )
        >>> core.is_terminal()
        False
        >>> core.state = CampaignState.COMPLETED
        >>> core.is_terminal()
        True
    """

    # Identity
    campaign_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""

    # Timestamps
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    end_time: Optional[datetime] = None

    # State
    state: CampaignState = CampaignState.FORMING
    current_phase: Optional[str] = None  # Wyckoff phase (A, B, C, D, E)
    failure_reason: Optional[str] = None

    # Pattern tracking (references to patterns, not embedded)
    patterns: list[Any] = field(default_factory=list)

    # Classification
    timeframe: str = "1d"
    asset_class: str = "stock"

    def is_terminal(self) -> bool:
        """
        Check if campaign is in a terminal state.

        Terminal states (COMPLETED, FAILED, CANCELLED) cannot transition
        to other states. Once a campaign reaches a terminal state, it's
        considered finished and read-only.

        Returns:
            True if campaign is in COMPLETED, FAILED, or CANCELLED state

        Example:
            >>> core = CampaignCore(state=CampaignState.ACTIVE)
            >>> core.is_terminal()
            False
            >>> core.state = CampaignState.COMPLETED
            >>> core.is_terminal()
            True
        """
        return self.state in TERMINAL_STATES

    def is_actionable(self) -> bool:
        """
        Check if campaign is in an actionable state.

        Actionable campaigns are ACTIVE and can have trades placed against them.
        FORMING campaigns are collecting patterns but not yet ready for trading.

        Returns:
            True if campaign is ACTIVE

        Example:
            >>> core = CampaignCore(state=CampaignState.ACTIVE)
            >>> core.is_actionable()
            True
        """
        return self.state == CampaignState.ACTIVE

    def can_transition_to(self, new_state: CampaignState) -> bool:
        """
        Check if a state transition is valid.

        Valid transitions:
        - FORMING -> ACTIVE, CANCELLED, FAILED
        - ACTIVE -> COMPLETED, FAILED, CANCELLED, DORMANT
        - DORMANT -> ACTIVE, FAILED, CANCELLED
        - Terminal states (COMPLETED, FAILED, CANCELLED) -> None

        Args:
            new_state: Target state to transition to

        Returns:
            True if transition is valid

        Example:
            >>> core = CampaignCore(state=CampaignState.FORMING)
            >>> core.can_transition_to(CampaignState.ACTIVE)
            True
            >>> core.can_transition_to(CampaignState.COMPLETED)
            False
        """
        if self.is_terminal():
            return False

        valid_transitions = {
            CampaignState.FORMING: {
                CampaignState.ACTIVE,
                CampaignState.CANCELLED,
                CampaignState.FAILED,
            },
            CampaignState.ACTIVE: {
                CampaignState.COMPLETED,
                CampaignState.FAILED,
                CampaignState.CANCELLED,
                CampaignState.DORMANT,
            },
            CampaignState.DORMANT: {
                CampaignState.ACTIVE,
                CampaignState.FAILED,
                CampaignState.CANCELLED,
            },
        }

        allowed = valid_transitions.get(self.state, set())
        return new_state in allowed

    @property
    def pattern_count(self) -> int:
        """
        Get the number of patterns in this campaign.

        Returns:
            Number of patterns detected

        Example:
            >>> core = CampaignCore()
            >>> core.patterns = [pattern1, pattern2]
            >>> core.pattern_count
            2
        """
        return len(self.patterns)

    @property
    def duration_seconds(self) -> Optional[float]:
        """
        Calculate campaign duration in seconds.

        Returns:
            Duration in seconds if end_time is set, None otherwise

        Example:
            >>> core = CampaignCore(start_time=datetime(2025, 1, 1, 0, 0))
            >>> core.end_time = datetime(2025, 1, 1, 1, 0)
            >>> core.duration_seconds
            3600.0
        """
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds()
