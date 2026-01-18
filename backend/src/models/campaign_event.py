"""
Campaign Event Models (Story 15.6)

Purpose:
--------
Defines event types and data structures for campaign event notifications.
Used by EventPublisher to notify subscribers of campaign lifecycle events.

Event Types:
------------
- CAMPAIGN_FORMED: New campaign detected (first pattern)
- CAMPAIGN_ACTIVATED: Campaign transitions to ACTIVE
- PATTERN_DETECTED: New pattern added (Spring, AR, SOS, LPS)
- CAMPAIGN_COMPLETED: Campaign exits with outcome
- CAMPAIGN_FAILED: Campaign expires or invalidates

Author: Developer Agent (Story 15.6 Implementation)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class CampaignEventType(str, Enum):
    """
    Campaign event types for notification system.

    Attributes:
        CAMPAIGN_FORMED: New campaign created with first pattern
        CAMPAIGN_ACTIVATED: Campaign transitioned to ACTIVE state
        PATTERN_DETECTED: New pattern added to existing campaign
        CAMPAIGN_COMPLETED: Campaign completed with exit
        CAMPAIGN_FAILED: Campaign failed (expired or invalidated)
        PORTFOLIO_HEAT_WARNING: Portfolio heat at 80% of limit (Story 15.7)
        PORTFOLIO_HEAT_CRITICAL: Portfolio heat at 95% of limit (Story 15.7)
        PORTFOLIO_HEAT_EXCEEDED: Portfolio heat above limit (Story 15.7)
        PORTFOLIO_HEAT_NORMAL: Portfolio heat dropped below warning (Story 15.7)
    """

    CAMPAIGN_FORMED = "CAMPAIGN_FORMED"
    CAMPAIGN_ACTIVATED = "CAMPAIGN_ACTIVATED"
    PATTERN_DETECTED = "PATTERN_DETECTED"
    CAMPAIGN_COMPLETED = "CAMPAIGN_COMPLETED"
    CAMPAIGN_FAILED = "CAMPAIGN_FAILED"

    # Portfolio heat alerts (Story 15.7)
    PORTFOLIO_HEAT_WARNING = "PORTFOLIO_HEAT_WARNING"
    PORTFOLIO_HEAT_CRITICAL = "PORTFOLIO_HEAT_CRITICAL"
    PORTFOLIO_HEAT_EXCEEDED = "PORTFOLIO_HEAT_EXCEEDED"
    PORTFOLIO_HEAT_NORMAL = "PORTFOLIO_HEAT_NORMAL"


@dataclass
class CampaignEvent:
    """
    Campaign event for notifications.

    Immutable event object containing all relevant information about
    a campaign lifecycle event.

    Attributes:
        event_type: Type of event (CampaignEventType)
        campaign_id: Unique campaign identifier
        timestamp: When the event occurred (UTC)
        pattern_type: Pattern type for PATTERN_DETECTED events (optional)
        metadata: Additional event context (campaign state, phase, etc.)

    Example:
        >>> event = CampaignEvent(
        ...     event_type=CampaignEventType.PATTERN_DETECTED,
        ...     campaign_id="abc123",
        ...     timestamp=datetime.now(),
        ...     pattern_type="Spring",
        ...     metadata={"campaign_state": "ACTIVE", "pattern_count": 2}
        ... )
        >>> event.to_dict()
        {"event_type": "PATTERN_DETECTED", "campaign_id": "abc123", ...}
    """

    event_type: CampaignEventType
    campaign_id: str
    timestamp: datetime
    pattern_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Ensure metadata is always a dict."""
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict[str, Any]:
        """
        Convert event to dictionary for serialization.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "event_type": self.event_type.value,
            "campaign_id": self.campaign_id,
            "timestamp": self.timestamp.isoformat(),
            "pattern_type": self.pattern_type,
            "metadata": self.metadata,
        }
