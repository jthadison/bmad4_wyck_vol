"""
Campaign Lifecycle Manager - Story 22.4

Extracts campaign state management from IntradayCampaignDetector.
Manages campaign lifecycle state transitions and indexes for O(1) lookups.

State Machine:
  FORMING → ACTIVE (required patterns detected)
  FORMING → DORMANT (inactivity timeout)
  FORMING → FAILED (expiration)
  ACTIVE → COMPLETED (target hit or Phase E)
  ACTIVE → FAILED (stop loss or expiration)
  ACTIVE → DORMANT (inactivity)
  DORMANT → ACTIVE (reactivation with new patterns)
  DORMANT → FAILED (expiration)
  COMPLETED/FAILED are terminal states (no further transitions)

Note: This class is distinct from CampaignStateManager in backtesting/exit/
which handles exit position state management (Story 18.11.3).

Author: Story 22.4 Implementation
"""

from __future__ import annotations

from collections import defaultdict
from enum import Enum
from typing import TYPE_CHECKING, Optional

import structlog
from structlog.stdlib import BoundLogger

if TYPE_CHECKING:
    from src.backtesting.intraday_campaign_detector import Campaign

logger: BoundLogger = structlog.get_logger(__name__)

__all__ = [
    "CampaignLifecycleManager",
    "StateTransitionError",
    "VALID_TRANSITIONS",
]


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, current_state: str, target_state: str, campaign_id: Optional[str] = None):
        self.current_state = current_state
        self.target_state = target_state
        self.campaign_id = campaign_id
        msg = f"Cannot transition from {current_state} to {target_state}"
        super().__init__(f"Campaign {campaign_id}: {msg}" if campaign_id else msg)


# Valid state transitions (terminal states have empty sets)
# Note: Only includes states that exist in CampaignState enum
VALID_TRANSITIONS: dict[str, set[str]] = {
    "FORMING": {"ACTIVE", "DORMANT", "FAILED"},
    "ACTIVE": {"COMPLETED", "FAILED", "DORMANT"},
    "DORMANT": {"ACTIVE", "FAILED"},
    "COMPLETED": set(),  # Terminal state
    "FAILED": set(),  # Terminal state
}


class CampaignLifecycleManager:
    """
    Manages campaign lifecycle state transitions and index operations.

    Provides O(1) lookups by ID, state, and timeframe.

    Warning:
        Not thread-safe - external synchronization required.
        IntradayCampaignDetector handles synchronization when using this manager.
    """

    def __init__(self) -> None:
        """Initialize with empty indexes."""
        self._campaigns_by_id: dict[str, Campaign] = {}
        self._campaigns_by_state: dict[str, set[str]] = defaultdict(set)
        self._campaigns_by_timeframe: dict[str, set[str]] = defaultdict(set)
        self._active_time_windows: dict[str, bool] = {}
        self._logger: BoundLogger = logger.bind(component="campaign_lifecycle_manager")

    def register_campaign(self, campaign: Campaign) -> None:
        """Register a campaign. Raises ValueError if already registered."""
        campaign_id = campaign.campaign_id
        if campaign_id in self._campaigns_by_id:
            raise ValueError(f"Campaign {campaign_id} already registered")

        self._campaigns_by_id[campaign_id] = campaign
        self._add_to_indexes(campaign)
        self._logger.debug(
            "campaign_registered",
            campaign_id=campaign_id,
            state=self._get_state_value(campaign.state),
            timeframe=campaign.timeframe,
        )

    def unregister_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Remove a campaign. Returns the campaign or None if not found."""
        if campaign_id not in self._campaigns_by_id:
            return None
        campaign = self._campaigns_by_id[campaign_id]
        self._remove_from_indexes(campaign_id)
        self._logger.debug("campaign_unregistered", campaign_id=campaign_id)
        return campaign

    def transition_to(
        self, campaign_id: str, new_state: Enum | str, reason: Optional[str] = None
    ) -> None:
        """Transition campaign to new state. Raises StateTransitionError if invalid."""
        if campaign_id not in self._campaigns_by_id:
            raise KeyError(f"Campaign {campaign_id} not found")

        campaign = self._campaigns_by_id[campaign_id]
        current_state_value = self._get_state_value(campaign.state)
        new_state_value = self._get_state_value(new_state)

        if not self.can_transition_to(campaign_id, new_state):
            raise StateTransitionError(current_state_value, new_state_value, campaign_id)

        # Update indexes
        self._campaigns_by_state[current_state_value].discard(campaign_id)
        self._campaigns_by_state[new_state_value].add(campaign_id)

        if new_state_value == "ACTIVE":
            self._active_time_windows[campaign_id] = True
        else:
            self._active_time_windows.pop(campaign_id, None)

        self._set_campaign_state(campaign, new_state)
        self._logger.info(
            "campaign_state_transitioned",
            campaign_id=campaign_id,
            from_state=current_state_value,
            to_state=new_state_value,
            reason=reason,
        )

    def can_transition_to(self, campaign_id: str, new_state: Enum | str) -> bool:
        """Check if transition is valid."""
        campaign = self._campaigns_by_id.get(campaign_id)
        if not campaign:
            return False
        current = self._get_state_value(campaign.state)
        return self._get_state_value(new_state) in VALID_TRANSITIONS.get(current, set())

    def is_terminal_state(self, state: Enum | str) -> bool:
        """Check if state is terminal (no further transitions)."""
        return len(VALID_TRANSITIONS.get(self._get_state_value(state), set())) == 0

    def get_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Get campaign by ID."""
        return self._campaigns_by_id.get(campaign_id)

    def get_campaigns_by_state(self, state: Enum | str) -> set[str]:
        """Get campaign IDs in given state."""
        return self._campaigns_by_state.get(self._get_state_value(state), set()).copy()

    def get_campaigns_by_timeframe(self, timeframe: str) -> set[str]:
        """Get campaign IDs for given timeframe."""
        return self._campaigns_by_timeframe.get(timeframe, set()).copy()

    def get_active_campaign_ids(self) -> set[str]:
        """Get all active campaign IDs (optimized)."""
        return set(self._active_time_windows.keys())

    def get_all_campaigns(self) -> list[Campaign]:
        """Get all registered campaigns."""
        return list(self._campaigns_by_id.values())

    @property
    def campaign_count(self) -> int:
        """Total registered campaigns."""
        return len(self._campaigns_by_id)

    def _get_state_value(self, state: Enum | str) -> str:
        """Convert state to string. Raises TypeError for invalid types."""
        if isinstance(state, str):
            return state
        if isinstance(state, Enum):
            return state.value
        raise TypeError(f"Expected Enum or str, got {type(state).__name__}")

    def _set_campaign_state(self, campaign: Campaign, new_state: Enum | str) -> None:
        """Set campaign state with type conversion."""
        if isinstance(new_state, str):
            state_enum_class = type(campaign.state)
            campaign.state = state_enum_class(new_state)
        else:
            campaign.state = new_state

    def _add_to_indexes(self, campaign: Campaign) -> None:
        """Add campaign to secondary indexes."""
        campaign_id = campaign.campaign_id
        state_value = self._get_state_value(campaign.state)
        self._campaigns_by_state[state_value].add(campaign_id)
        self._campaigns_by_timeframe[campaign.timeframe].add(campaign_id)
        if state_value == "ACTIVE":
            self._active_time_windows[campaign_id] = True

    def _remove_from_indexes(self, campaign_id: str) -> None:
        """Remove campaign from all indexes."""
        if campaign_id not in self._campaigns_by_id:
            return
        campaign = self._campaigns_by_id[campaign_id]
        state_value = self._get_state_value(campaign.state)
        self._campaigns_by_state[state_value].discard(campaign_id)
        self._campaigns_by_timeframe[campaign.timeframe].discard(campaign_id)
        self._active_time_windows.pop(campaign_id, None)
        del self._campaigns_by_id[campaign_id]

    def _update_indexes_for_state_change(self, campaign: Campaign, old_state: Enum | str) -> None:
        """
        Update indexes after external state change.

        Use this when campaign state is modified directly (e.g., by IntradayCampaignDetector)
        rather than through transition_to(). This keeps indexes synchronized with the
        campaign's actual state without re-validating the transition.
        """
        campaign_id = campaign.campaign_id
        old_value = self._get_state_value(old_state)
        new_value = self._get_state_value(campaign.state)
        self._campaigns_by_state[old_value].discard(campaign_id)
        self._campaigns_by_state[new_value].add(campaign_id)
        if new_value == "ACTIVE":
            self._active_time_windows[campaign_id] = True
        else:
            self._active_time_windows.pop(campaign_id, None)

    def rebuild_indexes(self) -> None:
        """Rebuild all secondary indexes from primary store."""
        self._campaigns_by_state.clear()
        self._campaigns_by_timeframe.clear()
        self._active_time_windows.clear()
        for campaign in self._campaigns_by_id.values():
            state_value = self._get_state_value(campaign.state)
            self._campaigns_by_state[state_value].add(campaign.campaign_id)
            self._campaigns_by_timeframe[campaign.timeframe].add(campaign.campaign_id)
            if state_value == "ACTIVE":
                self._active_time_windows[campaign.campaign_id] = True
        self._logger.info(
            "indexes_rebuilt",
            total_campaigns=len(self._campaigns_by_id),
            active_campaigns=len(self._active_time_windows),
        )

    def get_state_summary(self) -> dict[str, int]:
        """Get campaign counts by state."""
        return {state: len(ids) for state, ids in self._campaigns_by_state.items()}

    def clear(self) -> None:
        """Clear all campaigns and indexes."""
        self._campaigns_by_id.clear()
        self._campaigns_by_state.clear()
        self._campaigns_by_timeframe.clear()
        self._active_time_windows.clear()
        self._logger.info("state_manager_cleared")
