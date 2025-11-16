"""
SOS (Sign of Strength) breakout data model for Wyckoff markup detection.

This module defines the SOSBreakout model which represents a SOS breakout pattern
(decisive break above Ice resistance with high volume).
SOS patterns signal the transition from accumulation to markup (Phase D).

A SOS breakout is a decisive upward movement that:
- Breaks above Ice resistance (minimum 1% penetration)
- Shows high volume expansion (minimum 1.5x average - FR12)
- Confirms demand overwhelming supply
- Signals markup phase beginning

Key Characteristics:
- Breakout: 1%+ above Ice (2-3% ideal)
- Volume: >=1.5x average (HIGH volume critical - FR12)
- Phase: Must occur in Phase D (FR15 - Story 6.1A scope)
- Entry: On breakout or pullback (LPS)
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_serializer, field_validator

# Import models - avoid circular imports
from src.models.ohlcv import OHLCVBar


class SOSBreakout(BaseModel):
    """
    SOS (Sign of Strength) breakout pattern representing Ice breakout with high volume.

    A SOS is a critical Wyckoff markup signal that indicates the transition from
    accumulation to markup. It breaks decisively above Ice resistance on high
    volume, confirming demand overwhelming supply.

    Attributes:
        id: Unique identifier
        bar: OHLCV bar where SOS occurred (broke above Ice)
        breakout_pct: Percentage above Ice (minimum 1%, ideal 2-3%)
        volume_ratio: Volume relative to 20-bar average (>=1.5x required by FR12)
        ice_reference: Ice price level at detection time
        breakout_price: Closing price that broke above Ice
        detection_timestamp: When SOS was detected (UTC)
        trading_range_id: Associated trading range UUID
        spread_ratio: Bar spread expansion relative to average (>=1.2x - Story 6.1B)
        close_position: Close position within bar range 0.0-1.0 (>=0.5 - Story 6.1B)
        spread: Bar spread (high - low) for quality assessment (Story 6.1B)
        asset_class: Asset class identifier (stock/forex) - determines volume interpretation
        volume_reliability: Volume data quality (HIGH=real volume, LOW=tick volume only)

    Example:
        >>> sos = SOSBreakout(
        ...     bar=ohlcv_bar,
        ...     breakout_pct=Decimal("0.02"),  # 2% above Ice
        ...     volume_ratio=Decimal("2.0"),  # 200% of average (high volume)
        ...     ice_reference=Decimal("100.00"),
        ...     breakout_price=Decimal("102.00"),
        ...     detection_timestamp=datetime.now(UTC),
        ...     trading_range_id=UUID("..."),
        ...     spread_ratio=Decimal("1.4"),  # 1.4x spread expansion (Story 6.1B)
        ...     close_position=Decimal("0.75"),  # PASS tier (Story 6.1B)
        ...     spread=Decimal("5.00")  # $5 bar spread
        ... )
    """

    id: UUID = Field(default_factory=uuid4, description="Unique SOS identifier")
    bar: OHLCVBar = Field(..., description="Bar where SOS breakout occurred")
    breakout_pct: Decimal = Field(
        ...,
        ge=Decimal("0.01"),
        decimal_places=4,
        max_digits=10,
        description="Breakout above Ice (minimum 1%, ideal 2-3%)",
    )
    volume_ratio: Decimal = Field(
        ...,
        ge=Decimal("1.5"),
        decimal_places=4,
        max_digits=10,
        description="Volume ratio (>=1.5x required by FR12)",
    )
    ice_reference: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Ice level at detection time",
    )
    breakout_price: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Close price that broke above Ice",
    )
    detection_timestamp: datetime = Field(..., description="When SOS was detected (UTC)")
    trading_range_id: UUID = Field(..., description="Associated trading range")

    # Quality enhancement fields (Story 6.1B)
    spread_ratio: Decimal = Field(
        ...,
        ge=Decimal("1.2"),
        decimal_places=4,
        max_digits=10,
        description="Spread expansion (>=1.2x shows conviction - Story 6.1B)",
    )
    close_position: Decimal = Field(
        ...,
        ge=Decimal("0.0"),
        le=Decimal("1.0"),
        decimal_places=4,
        max_digits=10,
        description="Close position (close-low)/(high-low), >=0.5 required (Story 6.1B)",
    )
    spread: Decimal = Field(
        ...,
        gt=Decimal("0"),
        decimal_places=8,
        max_digits=18,
        description="Bar spread (high - low) for quality assessment (Story 6.1B)",
    )
    asset_class: str = Field(
        default="stock",
        description="Asset class ('stock', 'forex', etc.) - determines volume interpretation",
    )
    volume_reliability: str = Field(
        default="HIGH",
        description="Volume reliability ('HIGH'=real volume, 'LOW'=tick volume only)",
    )

    @field_validator("detection_timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """
        Enforce UTC timezone on detection timestamp.

        Args:
            v: Datetime value (may or may not have timezone)

        Returns:
            Datetime with UTC timezone
        """
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=UTC)
            return v.astimezone(UTC)
        return v

    @field_validator("breakout_pct")
    @classmethod
    def validate_breakout_range(cls, v: Decimal) -> Decimal:
        """
        Ensure breakout is >= 1% above Ice (AC 3).

        Args:
            v: Breakout percentage

        Returns:
            Validated breakout percentage

        Raises:
            ValueError: If breakout < 1%
        """
        if v < Decimal("0.01"):
            raise ValueError(f"Breakout {v*100:.2f}% must be >= 1% above Ice (AC 3)")
        return v

    @field_validator("volume_ratio")
    @classmethod
    def validate_volume_expansion(cls, v: Decimal) -> Decimal:
        """
        Ensure volume ratio >= 1.5x (FR12 enforcement).

        FR12: Volume >= 1.5x confirms breakout legitimacy.
        Low-volume breakouts are false breakouts (absorption at resistance).
        This is non-negotiable binary rejection.

        Args:
            v: Volume ratio

        Returns:
            Validated volume ratio

        Raises:
            ValueError: If volume_ratio < 1.5x
        """
        if v < Decimal("1.5"):
            raise ValueError(
                f"Volume ratio {v}x < 1.5x threshold - LOW VOLUME indicates false breakout (FR12)"
            )
        return v

    @field_validator("spread_ratio")
    @classmethod
    def validate_spread_expansion(cls, v: Decimal) -> Decimal:
        """
        Ensure spread ratio >= 1.2x (Story 6.1B AC 1).

        Wide bars (1.2x+ spread) show conviction.
        Narrow bars suggest absorption at resistance.

        Args:
            v: Spread ratio

        Returns:
            Validated spread ratio

        Raises:
            ValueError: If spread_ratio < 1.2x
        """
        if v < Decimal("1.2"):
            raise ValueError(
                f"Spread ratio {v}x < 1.2x threshold - narrow spread suggests absorption"
            )
        return v

    @field_validator("close_position")
    @classmethod
    def validate_close_strength(cls, v: Decimal) -> Decimal:
        """
        Ensure close position >= 0.5 (Story 6.1B AC 2).

        Three-tier logic:
        - >=0.7: PASS (strong close - buyers in control)
        - 0.5-0.69: MARGINAL (middling - penalty in confidence scoring)
        - <0.5: REJECT (weak close - sellers dominating)

        Args:
            v: Close position (0.0-1.0)

        Returns:
            Validated close position

        Raises:
            ValueError: If close_position < 0.5
        """
        if v < Decimal("0.5"):
            raise ValueError(
                f"Close position {v:.2f} < 0.5 - weak close indicates sellers dominating (REJECT)"
            )
        return v

    @field_serializer(
        "breakout_pct",
        "volume_ratio",
        "ice_reference",
        "breakout_price",
        "spread_ratio",
        "close_position",
        "spread",
    )
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value)

    @field_serializer("detection_timestamp")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime fields as ISO format strings."""
        return value.isoformat()

    @field_serializer("id", "trading_range_id")
    def serialize_uuid(self, value: UUID) -> str:
        """Serialize UUID as string."""
        return str(value)

    @property
    def is_ideal_sos(self) -> bool:
        """
        Check if SOS meets ideal Wyckoff characteristics.

        Ideal SOS:
        - Breakout: 2-3% above Ice
        - Volume: >=2.0x average (strong expansion)

        Returns:
            bool: True if SOS meets ideal characteristics
        """
        return Decimal("0.02") <= self.breakout_pct <= Decimal(
            "0.03"
        ) and self.volume_ratio >= Decimal("2.0")

    @property
    def close_position_tier(self) -> str:
        """
        Get close position tier (Story 6.1B).

        Tiers:
        - PASS: >= 0.7 (strong close - buyers in control)
        - MARGINAL: 0.5-0.69 (middling - penalty in confidence scoring)

        Returns:
            str: Close position tier (PASS or MARGINAL)
        """
        if self.close_position >= Decimal("0.7"):
            return "PASS"
        else:
            return "MARGINAL"

    @property
    def quality_tier(self) -> str:
        """
        Classify SOS quality based on Wyckoff guidelines.

        Tiers:
        - EXCELLENT: 2-3% breakout, >=2.5x volume (climactic)
        - GOOD: 2-3% breakout, 2.0-2.5x volume
        - ACCEPTABLE: 1-2% breakout, 1.5-2.0x volume

        Returns:
            str: Quality tier (EXCELLENT, GOOD, or ACCEPTABLE)
        """
        if self.breakout_pct >= Decimal("0.02") and self.volume_ratio >= Decimal("2.5"):
            return "EXCELLENT"
        elif self.breakout_pct >= Decimal("0.02") and self.volume_ratio >= Decimal("2.0"):
            return "GOOD"
        else:
            return "ACCEPTABLE"
