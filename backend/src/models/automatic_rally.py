"""
Automatic Rally (AR) data model for Wyckoff Phase A detection.

The Automatic Rally represents the relief rally that follows a Selling Climax (SC).
It occurs as demand steps in to absorb panic selling, showing a rally of 3%+ from
the SC low. The AR, combined with the SC, confirms Phase A (stopping action) is complete.

AR must occur within 5 bars (ideal) or up to 10 bars (timeout) after SC.
"""

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    sc_reference: dict = Field(..., description="The SC that triggered this AR (stored as dict)")
    sc_low: Decimal = Field(..., description="SC bar low price (rally start)", decimal_places=8)
    ar_high: Decimal = Field(..., description="AR peak high price (rally end)", decimal_places=8)
    volume_profile: str = Field(..., pattern="^(HIGH|NORMAL)$", description="Volume classification")
    detection_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When AR was detected (UTC)",
    )

    # Story 14.1: Enhanced AR detection fields
    quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="AR quality score (0.0-1.0) based on volume, recovery, timing, range",
    )
    recovery_percent: Decimal = Field(
        default=Decimal("0"),
        ge=Decimal("0"),
        description="% recovery of prior decline (Spring/SC decline range)",
        decimal_places=4,
    )
    volume_trend: str = Field(
        default="UNKNOWN",
        pattern="^(DECLINING|NEUTRAL|INCREASING|UNKNOWN)$",
        description="Volume trend from Spring/SC to AR",
    )
    prior_pattern_bar: int | None = Field(
        default=None,
        description="Reference to Spring/SC bar index (bar that triggered this AR)",
    )
    prior_pattern_type: str = Field(
        default="SC",
        pattern="^(SPRING|SC)$",
        description="Type of pattern that triggered AR (SPRING or SC)",
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
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    def calculate_quality_score(
        self, volume_ratio: Decimal, close_position: Decimal | None = None
    ) -> float:
        """
        Calculate AR quality score (0.0-1.0) - Story 14.1 AC 4.

        Quality score based on:
        - Volume characteristics (40% weight): 0.8-1.2x average = ideal
        - Price recovery (30% weight): recovery_percent >= 50% = ideal
        - Timing (20% weight): bars_after_sc <= 5 = quick/strong
        - Range characteristics (10% weight): close in upper 60% = bullish

        Args:
            volume_ratio: Volume relative to average (e.g., 0.9 = 90%)
            close_position: Close position in bar range (0.0-1.0), optional

        Returns:
            float: Quality score 0.0-1.0
                - >0.75: High-quality AR
                - 0.5-0.75: Medium-quality AR
                - <0.5: Low-quality AR (valid but weak)

        Example:
            >>> ar = AutomaticRally(...)
            >>> score = ar.calculate_quality_score(Decimal("0.9"), Decimal("0.7"))
            >>> print(f"Quality: {score:.2f}")
            Quality: 0.80
        """
        score = 0.0

        # Volume characteristics (40% weight) - Story 14.1 AC 2
        # Ideal: 0.8-1.2x (moderate, declining from climax)
        if Decimal("0.8") <= volume_ratio <= Decimal("1.2"):
            score += 0.4  # Perfect moderate volume
        elif Decimal("0.7") <= volume_ratio < Decimal("0.8") or Decimal(
            "1.2"
        ) < volume_ratio <= Decimal("1.3"):
            score += 0.2  # Acceptable range
        # Volume >1.5x rejected in detection, <0.7 too low

        # Price recovery (30% weight) - Story 14.1 AC 1
        # recovery_percent already calculated as % of decline recovered
        if self.recovery_percent >= Decimal("0.5"):  # 50%+ recovery
            score += 0.3
        elif self.recovery_percent >= Decimal("0.4"):  # 40-50% recovery
            score += 0.2
        elif self.recovery_percent >= Decimal("0.3"):  # 30-40% recovery
            score += 0.1

        # Timing (20% weight) - Story 14.1 AC 1
        # bars_after_sc: 1-10 range, lower = stronger
        if self.bars_after_sc <= 5:
            score += 0.2  # Quick AR = strong demand
        elif self.bars_after_sc <= 7:
            score += 0.15
        elif self.bars_after_sc <= 10:
            score += 0.1

        # Range characteristics (10% weight) - Story 14.1 AC 3
        # close_position: where close is in bar range (0.0=low, 1.0=high)
        if close_position is not None:
            if close_position >= Decimal("0.6"):  # Upper 60% = bullish
                score += 0.1
            elif close_position >= Decimal("0.5"):  # Upper 50% = acceptable
                score += 0.05

        return min(score, 1.0)  # Cap at 1.0

    model_config = ConfigDict(
        # Allow validation of dict for bar and sc_reference fields
        arbitrary_types_allowed=True,
    )
