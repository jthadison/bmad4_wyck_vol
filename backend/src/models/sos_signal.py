"""
SOS/LPS Signal data model for actionable entry signals.

This module defines the SOSSignal model which represents complete entry signals
for SOS (Sign of Strength) breakouts and LPS (Last Point of Support) pullbacks
with appropriate stops and targets.

A SOS/LPS Signal is an actionable trade signal that:
- Specifies entry price (LPS: Ice+1%, SOS: breakout price)
- Sets structural stop loss (LPS: Ice-3%, SOS: Ice-5%) per FR17
- Targets Jump level (Wyckoff cause-effect calculation)
- Validates minimum 2.0R risk/reward ratio (FR19)
- Includes full pattern context for audit trail

Signal Types:
1. LPS_ENTRY (preferred): Entry after pullback to Ice with tighter stop (3%)
2. SOS_DIRECT_ENTRY (fallback): Direct entry on SOS breakout with wider stop (5%)

Key Features:
- Entry/Stop/Target: Clear actionable levels
- R-Multiple: Risk/reward calculation and validation (minimum 2.0R)
- Confidence: Pattern quality score from Story 6.5
- Campaign Linkage: Spring → SOS progression tracking
- Pattern Data: Complete SOS/LPS context for audit trail
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

from src.models.validation import ValidationChain

if TYPE_CHECKING:
    from src.risk_management.forex_position_sizer import ForexPositionSize


class SOSSignal(BaseModel):
    """
    SOS/LPS Entry Signal with structural stops and Wyckoff targets.

    Represents a complete actionable entry signal for Phase D breakout patterns.
    Includes entry price, stop loss, target, and risk/reward validation.

    Signal types:
    - LPS_ENTRY: Pullback to Ice after SOS (preferred, tighter stop)
    - SOS_DIRECT_ENTRY: Direct entry on SOS breakout (no LPS)

    Entry/Stop/Target Calculation:
    LPS Entry (AC 1):
    - Entry = Ice × 1.01 (1% above Ice for slippage)
    - Stop = Ice × 0.97 (3% below Ice, structural stop - FR17)
    - Target = Jump level (Wyckoff cause-effect)

    SOS Direct Entry (AC 2):
    - Entry = SOS breakout price (close of SOS bar)
    - Stop = Ice × 0.95 (5% below Ice, wider for no confirmation - FR17)
    - Target = Jump level

    R-Multiple Validation (FR19):
    - Minimum 2.0R required for SOS/LPS signals
    - R = (target - entry) / (entry - stop)
    - Signals with R < 2.0R are rejected

    Attributes:
        id: Unique signal identifier
        symbol: Ticker symbol
        entry_type: LPS_ENTRY or SOS_DIRECT_ENTRY
        entry_price: Entry price level
        stop_loss: Stop loss level (structural, based on Ice - FR17)
        target: Jump level target (Wyckoff cause-effect)
        confidence: Pattern confidence score 0-100 (from Story 6.5)
        r_multiple: Risk/reward ratio (minimum 2.0R - FR19)
        pattern_data: SOS and LPS pattern details (audit trail)
        sos_bar_timestamp: SOS breakout bar timestamp
        lps_bar_timestamp: LPS bar timestamp if applicable
        sos_volume_ratio: SOS breakout volume expansion
        lps_volume_ratio: LPS pullback volume if applicable
        phase: Wyckoff phase context (typically "D")
        campaign_id: Link to campaign if Spring→SOS progression
        trading_range_id: Associated trading range
        ice_level: Ice level reference (for stop calculation)
        jump_level: Jump level (for target calculation)
        generated_at: Signal generation timestamp (UTC)
        expires_at: Signal expiration timestamp (optional)

    Example:
        >>> # LPS Entry Signal
        >>> lps_signal = SOSSignal(
        ...     symbol="AAPL",
        ...     entry_type="LPS_ENTRY",
        ...     entry_price=Decimal("101.00"),  # Ice + 1%
        ...     stop_loss=Decimal("97.00"),     # Ice - 3%
        ...     target=Decimal("115.00"),       # Jump level
        ...     confidence=85,
        ...     r_multiple=Decimal("3.5"),      # ($115-$101) / ($101-$97) = 3.5R
        ...     pattern_data={...},
        ...     sos_bar_timestamp=datetime.now(UTC),
        ...     lps_bar_timestamp=datetime.now(UTC),
        ...     sos_volume_ratio=Decimal("2.5"),
        ...     lps_volume_ratio=Decimal("0.8"),
        ...     phase="D",
        ...     campaign_id=UUID("..."),
        ...     trading_range_id=UUID("..."),
        ...     ice_level=Decimal("100.00"),
        ...     jump_level=Decimal("115.00"),
        ...     generated_at=datetime.now(UTC),
        ...     expires_at=None
        ... )
        >>> print(f"R-multiple: {lps_signal.r_multiple}R")
        >>> print(f"Risk: ${lps_signal.get_risk_distance()}")
        >>> print(f"Reward: ${lps_signal.get_reward_distance()}")
    """

    id: UUID = Field(default_factory=uuid4, description="Unique signal identifier")
    symbol: str = Field(..., max_length=20, description="Ticker symbol")
    entry_type: Literal["LPS_ENTRY", "SOS_DIRECT_ENTRY"] = Field(
        ..., description="Entry signal type"
    )
    entry_price: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Entry price level"
    )
    stop_loss: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Stop loss level (FR17)"
    )
    target: Decimal = Field(..., decimal_places=8, max_digits=18, description="Jump level target")
    confidence: int = Field(..., ge=0, le=100, description="Pattern confidence (Story 6.5)")
    r_multiple: Decimal = Field(
        ..., decimal_places=4, max_digits=10, ge=Decimal("0"), description="Risk/reward ratio"
    )
    r_multiple_status: Literal["REJECTED", "ACCEPTABLE", "IDEAL"] = Field(
        ..., description="R-multiple validation status (Story 7.6)"
    )
    r_multiple_warning: Optional[str] = Field(
        default=None, description="Warning if R-multiple below ideal (Story 7.6)"
    )
    pattern_data: dict = Field(..., description="SOS and LPS pattern details")
    sos_bar_timestamp: datetime = Field(..., description="SOS breakout bar timestamp")
    lps_bar_timestamp: Optional[datetime] = Field(
        None, description="LPS bar timestamp if applicable"
    )
    sos_volume_ratio: Decimal = Field(
        ..., decimal_places=4, max_digits=10, description="SOS breakout volume"
    )
    lps_volume_ratio: Optional[Decimal] = Field(
        None, decimal_places=4, max_digits=10, description="LPS pullback volume"
    )
    phase: str = Field(..., max_length=10, description="Wyckoff phase (typically D)")
    campaign_id: Optional[UUID] = Field(None, description="Campaign linkage (Spring→SOS)")
    trading_range_id: UUID = Field(..., description="Associated trading range")
    ice_level: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Ice level reference"
    )
    jump_level: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Jump level target"
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Signal generation timestamp (UTC)",
    )
    expires_at: Optional[datetime] = Field(None, description="Signal expiration timestamp")

    # Forex-specific position sizing (Story 7.2-FX, AC 9)
    forex_position_size: Optional[ForexPositionSize] = Field(
        default=None, description="Forex position size (lot-based, for forex signals only)"
    )

    # Phase validation fields (Story 7.9, AC 9)
    phase_validation_status: Literal["PASSED", "WARNING", "FAILED"] = Field(
        default="PASSED", description="Phase prerequisite validation status"
    )
    phase_prerequisites_met: list[str] = Field(
        default_factory=list, description="List of prerequisite events detected"
    )
    phase_prerequisites_missing: Optional[list[str]] = Field(
        default=None, description="Missing prerequisites if validation failed/warned"
    )

    # Multi-stage validation chain (Story 8.2, AC 7)
    validation_chain: Optional[ValidationChain] = Field(
        default=None,
        description="Complete audit trail of validation stages (Volume → Phase → Levels → Risk → Strategy)",
    )

    @field_validator("r_multiple")
    @classmethod
    def validate_minimum_r_multiple(cls, v: Decimal) -> Decimal:
        """
        FR19: Minimum 2.0R required for SOS/LPS signals.

        Ensures favorable risk/reward ratio. Signals with R < 2.0R indicate:
        - Target too close to entry (weak accumulation, small range)
        - Stop too wide (poor setup structure)
        - Not worth the risk (better opportunities available)

        Args:
            v: R-multiple value

        Returns:
            Validated R-multiple

        Raises:
            ValueError: If R-multiple < 2.0R (FR19 minimum)
        """
        MIN_R_MULTIPLE = Decimal("2.0")
        if v < MIN_R_MULTIPLE:
            raise ValueError(f"R-multiple {v:.2f}R below minimum 2.0R (FR19 requirement)")
        return v

    @field_validator("stop_loss")
    @classmethod
    def validate_stop_below_entry(cls, v: Decimal, info) -> Decimal:
        """
        Validate stop < entry for long positions.

        Args:
            v: Stop loss price
            info: Validation context

        Returns:
            Validated stop loss

        Raises:
            ValueError: If stop >= entry
        """
        if "entry_price" in info.data and v >= info.data["entry_price"]:
            raise ValueError(
                f"Stop loss {v} must be below entry price "
                f"{info.data['entry_price']} for long position"
            )
        return v

    @field_validator("target")
    @classmethod
    def validate_target_above_entry(cls, v: Decimal, info) -> Decimal:
        """
        Validate target > entry for long positions.

        Args:
            v: Target price
            info: Validation context

        Returns:
            Validated target

        Raises:
            ValueError: If target <= entry
        """
        if "entry_price" in info.data and v <= info.data["entry_price"]:
            raise ValueError(
                f"Target {v} must be above entry price {info.data['entry_price']} for long position"
            )
        return v

    @model_validator(mode="after")
    def validate_entry_type_consistency(self) -> SOSSignal:
        """
        Validate entry_type consistency with lps_bar_timestamp.

        - LPS_ENTRY requires lps_bar_timestamp
        - SOS_DIRECT_ENTRY should have lps_bar_timestamp = None

        Returns:
            Validated SOSSignal instance

        Raises:
            ValueError: If entry type inconsistent with LPS timestamp
        """
        if self.entry_type == "LPS_ENTRY" and self.lps_bar_timestamp is None:
            raise ValueError("LPS_ENTRY requires lps_bar_timestamp")
        if self.entry_type == "SOS_DIRECT_ENTRY" and self.lps_bar_timestamp is not None:
            raise ValueError("SOS_DIRECT_ENTRY should not have lps_bar_timestamp")

        return self

    @field_validator(
        "generated_at", "expires_at", "sos_bar_timestamp", "lps_bar_timestamp", mode="before"
    )
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        """
        Enforce UTC timezone on all datetime fields.

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
        "target",
        "r_multiple",
        "sos_volume_ratio",
        "lps_volume_ratio",
        "ice_level",
        "jump_level",
    )
    def serialize_decimal(self, value: Optional[Decimal]) -> Optional[str]:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value) if value is not None else None

    @field_serializer("generated_at", "expires_at", "sos_bar_timestamp", "lps_bar_timestamp")
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        """Serialize datetime fields as ISO format strings."""
        return value.isoformat() if value else None

    @field_serializer("id", "campaign_id", "trading_range_id")
    def serialize_uuid(self, value: Optional[UUID]) -> Optional[str]:
        """Serialize UUID as string."""
        return str(value) if value is not None else None

    def get_risk_distance(self) -> Decimal:
        """
        Calculate risk distance (entry - stop).

        Returns:
            Decimal: Risk per share (entry - stop_loss)

        Example:
            >>> signal = SOSSignal(entry_price=101, stop_loss=97, ...)
            >>> signal.get_risk_distance()
            Decimal('4.00')
        """
        return self.entry_price - self.stop_loss

    def get_reward_distance(self) -> Decimal:
        """
        Calculate reward distance (target - entry).

        Returns:
            Decimal: Reward per share (target - entry_price)

        Example:
            >>> signal = SOSSignal(entry_price=101, target=115, ...)
            >>> signal.get_reward_distance()
            Decimal('14.00')
        """
        return self.target - self.entry_price

    def validate_r_multiple(self) -> bool:
        """
        Validate R-multiple meets minimum 2.0R requirement (FR19).

        Returns:
            bool: True if R-multiple >= 2.0R, False otherwise

        Example:
            >>> signal = SOSSignal(r_multiple=Decimal("3.5"), ...)
            >>> signal.validate_r_multiple()
            True
        """
        return self.r_multiple >= Decimal("2.0")

    @property
    def is_lps_entry(self) -> bool:
        """
        Check if signal is LPS entry type.

        Returns:
            bool: True if LPS_ENTRY, False if SOS_DIRECT_ENTRY
        """
        return self.entry_type == "LPS_ENTRY"

    @property
    def is_sos_direct_entry(self) -> bool:
        """
        Check if signal is SOS direct entry type.

        Returns:
            bool: True if SOS_DIRECT_ENTRY, False if LPS_ENTRY
        """
        return self.entry_type == "SOS_DIRECT_ENTRY"

    @property
    def has_campaign(self) -> bool:
        """
        Check if signal is linked to a campaign (Spring→SOS progression).

        Returns:
            bool: True if campaign_id is set, False otherwise
        """
        return self.campaign_id is not None

    @property
    def stop_distance_pct(self) -> Decimal:
        """
        Calculate stop distance as percentage of entry price.

        Returns:
            Decimal: Stop distance percentage

        Example:
            >>> signal = SOSSignal(entry_price=101, stop_loss=97, ...)
            >>> signal.stop_distance_pct
            Decimal('0.0396')  # 3.96%
        """
        return (self.entry_price - self.stop_loss) / self.entry_price
