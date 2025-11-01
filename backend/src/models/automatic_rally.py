"""
Automatic Rally (AR) data model for Wyckoff Phase A detection.

The Automatic Rally represents the relief rally that follows a Selling Climax (SC).
It occurs as demand steps in to absorb panic selling, showing a rally of 3%+ from
the SC low. The AR, combined with the SC, confirms Phase A (stopping action) is complete.

AR must occur within 5 bars (ideal) or up to 10 bars (timeout) after SC.
"""

from decimal import Decimal
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator, ConfigDict


class AutomaticRally(BaseModel):
    """
    Automatic Rally (AR) - Relief rally following Selling Climax.

    Wyckoff Interpretation:
    - AR is natural bounce after panic selling (SC)
    - Rally of 3%+ from SC low shows demand stepping in
    - Occurs within 5 bars after SC (ideal), up to 10 bars (timeout)
    - HIGH volume AR shows strong absorption (bullish)
    - NORMAL volume AR shows weak relief rally (less bullish)
    - AR + SC = Phase A confirmed (stopping action complete)

    Attributes:
        bar: The OHLCV bar where AR peaked (highest high after SC) - stored as dict
        bar_index: Index position of the bar in the data sequence
        rally_pct: Rally percentage from SC low (e.g., 0.035 = 3.5%)
        bars_after_sc: Number of bars from SC to AR peak (1-10)
        sc_reference: Reference to the SC that triggered this AR - stored as dict
        sc_low: SC bar low price (rally starting point)
        ar_high: AR peak high price (rally ending point)
        volume_profile: "HIGH" (>=1.2x) or "NORMAL" (<1.2x) volume on rally
        detection_timestamp: When AR was detected (UTC)
    """

    # Using dict for bar to avoid circular import with OHLCVBar
    bar: dict = Field(..., description="The bar where AR peaked (highest high after SC)")
    bar_index: int = Field(..., ge=0, description="Index position of the bar in the data sequence")
    rally_pct: Decimal = Field(
        ...,
        ge=Decimal("0.03"),
        description="Rally percentage from SC low (minimum 3%)",
        decimal_places=4,
    )
    bars_after_sc: int = Field(
        ..., ge=1, le=10, description="Number of bars from SC to AR peak (1-10)"
    )
    sc_reference: dict = Field(
        ..., description="The SC that triggered this AR (stored as dict)"
    )
    sc_low: Decimal = Field(
        ..., description="SC bar low price (rally start)", decimal_places=8
    )
    ar_high: Decimal = Field(
        ..., description="AR peak high price (rally end)", decimal_places=8
    )
    volume_profile: str = Field(
        ..., pattern="^(HIGH|NORMAL)$", description="Volume classification"
    )
    detection_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When AR was detected (UTC)",
    )

    @field_validator("ar_high")
    @classmethod
    def validate_rally_upward(cls, v: Decimal, info) -> Decimal:
        """Ensure AR high is above SC low (rally must go up)."""
        # Access sc_low from info.data if available
        if "sc_low" in info.data and v <= info.data["sc_low"]:
            raise ValueError("AR high must be above SC low (rally must be upward)")
        return v

    @field_validator("detection_timestamp")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Enforce UTC timezone."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    model_config = ConfigDict(
        # Allow validation of dict for bar and sc_reference fields
        arbitrary_types_allowed=True,
    )
