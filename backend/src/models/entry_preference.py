"""
Entry preference data model for SOS vs LPS entry type selection.

This module defines the EntryPreference model which determines optimal entry type
for SOS/LPS breakout patterns. Prefers LPS entries (tighter stops, better R-multiple)
over SOS direct entries (wider stops, acceptable risk/reward).

Entry Hierarchy:
---------------
1. LPS Entry (BEST): Pullback to Ice support with tighter stop (3% below Ice)
2. SOS Direct (ACCEPTABLE): Breakout entry if very strong (80+ confidence, 2.0x+ volume)
3. No Entry (WAIT): Monitor for LPS or SOS not strong enough

LPS Advantages:
--------------
- Tighter stop: 3% below Ice vs 5% for SOS direct
- Better R-multiple: Same target (Jump), tighter stop = better ratio (40% improvement)
- Confirmation: Support hold validates SOS breakout legitimacy
- Lower risk: Entry closer to support, less downside exposure

SOS Direct Entry Requirements:
-----------------------------
- Confidence >= 80 (higher bar than LPS minimum)
- Volume >= 2.0x (very strong buying interest)
- No LPS formed after 10-bar wait period

Wyckoff Context:
---------------
LPS (Last Point of Support) is the OPTIMAL entry for Phase D markup. After SOS breaks
above resistance (Ice), LPS is the pullback where price tests Ice as new support.
The pullback provides a lower-risk entry with tighter stop placement (3% below Ice).

SOS direct entry is acceptable ONLY when SOS is very strong (80+ confidence, 2.0x+ volume)
AND no LPS forms after 10 bars. Direct entry requires higher conviction due to wider stop
(5% below Ice).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_serializer, field_validator

# Import models - avoid circular imports
from src.models.lps import LPS
from src.models.sos_breakout import SOSBreakout


class EntryType(str, Enum):
    """
    Entry type classification for SOS/LPS patterns.

    Wyckoff Context:
    - LPS_ENTRY: Lower-risk pullback entry with tighter stop (3% below Ice)
    - SOS_DIRECT_ENTRY: Breakout entry with wider stop (5% below Ice)
    - NO_ENTRY: Waiting for LPS or SOS doesn't meet direct entry threshold
    """

    LPS_ENTRY = "LPS_ENTRY"  # Best: LPS formed, use LPS entry (preferred)
    SOS_DIRECT_ENTRY = "SOS_DIRECT_ENTRY"  # Acceptable: No LPS, use SOS direct (if strong)
    NO_ENTRY = "NO_ENTRY"  # Waiting or doesn't qualify


class EntryPreference(BaseModel):
    """
    Entry preference determination for SOS/LPS breakout patterns.

    Purpose:
    -------
    Determines optimal entry type based on pattern availability and quality.
    Prefers LPS entries (tighter stops, better R-multiple) over SOS direct entries.

    Entry Hierarchy:
    ---------------
    1. LPS Entry (BEST): Pullback to Ice support with tighter stop (3% below Ice)
    2. SOS Direct (ACCEPTABLE): Breakout entry if very strong (80+ confidence, 2.0x+ volume)
    3. No Entry (WAIT): Monitor for LPS or SOS not strong enough

    LPS Advantages:
    --------------
    - Tighter stop: 3% below Ice vs 5% for SOS direct
    - Better R-multiple: Same target (Jump), tighter stop = better ratio
    - Confirmation: Support hold validates SOS breakout legitimacy
    - Lower risk: Entry closer to support, less downside exposure

    SOS Direct Entry Requirements:
    -----------------------------
    - Confidence >= 80 (higher bar than LPS minimum)
    - Volume >= 2.0x (very strong buying interest)
    - Phase D with high confidence OR late Phase C (85+)
    - No LPS formed after 10-bar wait period

    Wait Period Logic:
    -----------------
    - After SOS detected: wait up to 10 bars for potential LPS
    - If LPS forms within 10 bars: use LPS entry
    - If no LPS after 10 bars: evaluate SOS direct entry

    Attributes:
        id: Unique identifier
        entry_type: Preferred entry type (LPS_ENTRY, SOS_DIRECT_ENTRY, NO_ENTRY)
        sos_breakout: SOS breakout pattern (required)
        lps_pattern: LPS pattern (if formed)
        trading_range_id: Associated trading range
        entry_price: Entry price
        stop_loss: Stop loss level
        stop_distance_pct: Stop distance % (3% LPS, 5% SOS)
        ice_level: Ice level reference
        bars_after_sos: Bars since SOS detected
        wait_period_complete: Whether 10-bar wait period completed
        sos_confidence: SOS confidence score (0-100)
        preference_reason: Why this entry type was selected
        user_notification: User-facing notification
        decision_timestamp: When preference was determined (UTC)

    Example:
        >>> # LPS Entry (preferred)
        >>> pref = EntryPreference(
        ...     entry_type=EntryType.LPS_ENTRY,
        ...     sos_breakout=sos,
        ...     lps_pattern=lps,
        ...     trading_range_id=UUID("..."),
        ...     entry_price=Decimal("100.50"),  # Near Ice
        ...     stop_loss=Decimal("97.00"),     # Ice - 3%
        ...     stop_distance_pct=Decimal("3.0"),
        ...     ice_level=Decimal("100.00"),
        ...     bars_after_sos=5,
        ...     wait_period_complete=True,
        ...     sos_confidence=85,
        ...     preference_reason="LPS entry preferred: tighter stop, confirmed support",
        ...     user_notification="LPS Entry Signal: Pullback to support confirmed."
        ... )
    """

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    entry_type: EntryType = Field(
        ..., description="Preferred entry type (LPS_ENTRY, SOS_DIRECT_ENTRY, NO_ENTRY)"
    )
    sos_breakout: SOSBreakout = Field(..., description="SOS breakout pattern (required)")
    lps_pattern: Optional[LPS] = Field(None, description="LPS pattern (if formed)")
    trading_range_id: UUID = Field(..., description="Associated trading range")

    # Entry and stop levels
    entry_price: Decimal = Field(..., decimal_places=8, max_digits=18, description="Entry price")
    stop_loss: Decimal = Field(..., decimal_places=8, max_digits=18, description="Stop loss level")
    stop_distance_pct: Decimal = Field(
        ..., decimal_places=4, max_digits=10, description="Stop distance % (3% LPS, 5% SOS)"
    )
    ice_level: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Ice level reference"
    )

    # Decision metadata
    bars_after_sos: int = Field(..., ge=0, description="Bars since SOS detected")
    wait_period_complete: bool = Field(..., description="Whether 10-bar wait period completed")
    sos_confidence: Optional[int] = Field(
        None, ge=0, le=100, description="SOS confidence score (0-100)"
    )

    # Rationale
    preference_reason: str = Field(..., description="Why this entry type was selected")
    user_notification: str = Field(..., description="User-facing notification")

    decision_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="When preference determined (UTC)"
    )

    @field_validator("decision_timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        """
        Enforce UTC timezone on decision timestamp.

        Args:
            v: Datetime value (may or may not have timezone)

        Returns:
            Datetime with UTC timezone or None
        """
        if v is None:
            return v
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=UTC)
            return v.astimezone(UTC)
        return v

    @field_serializer(
        "entry_price",
        "stop_loss",
        "stop_distance_pct",
        "ice_level",
    )
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value)

    @field_serializer("decision_timestamp")
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        """Serialize datetime fields as ISO format strings."""
        return value.isoformat() if value else None

    @field_serializer("id", "trading_range_id")
    def serialize_uuid(self, value: UUID) -> str:
        """Serialize UUID as string."""
        return str(value)

    def get_r_multiple_advantage(self) -> str:
        """
        Get qualitative R-multiple advantage description.

        Returns:
            str: "EXCELLENT" (LPS - tighter stop), "GOOD" (SOS - wider stop), "STANDARD" (no entry)
        """
        if self.entry_type == EntryType.LPS_ENTRY:
            # LPS: 3% stop vs SOS 5% stop = 40% better R-multiple
            return "EXCELLENT"  # Tighter stop, better risk/reward
        elif self.entry_type == EntryType.SOS_DIRECT_ENTRY:
            return "GOOD"  # Wider stop, acceptable risk/reward
        else:
            return "STANDARD"
