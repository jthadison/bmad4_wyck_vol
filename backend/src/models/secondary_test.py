"""
Secondary Test (ST) data model for Wyckoff Phase A/B transition detection.

The Secondary Test represents a retest of the Selling Climax (SC) low on reduced volume.
ST occurs after the Automatic Rally (AR) and marks the completion of Phase A (stopping action)
and the beginning of Phase B (building cause). Multiple STs can occur, each building stronger
cause for accumulation.

Wyckoff Interpretation:
- ST retests SC low from above (after AR rally)
- Reduced volume (10%+ minimum from SC) shows sellers exhausted
- Price holds above SC low (minor penetration <1% allowed)
- 1st ST confirms Phase B entry
- Multiple STs (2nd, 3rd) build stronger cause → higher Jump potential
"""

from decimal import Decimal
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator, ConfigDict


class SecondaryTest(BaseModel):
    """
    Secondary Test (ST) - Retest of SC low on reduced volume marking Phase A→B transition.

    Wyckoff Interpretation:
    - ST retests SC low after AR (tests support established)
    - Material volume reduction (10%+ minimum) shows absorption complete
    - Holds above SC low (minor penetration <1% acceptable)
    - 1st ST marks Phase A complete, Phase B beginning
    - Multiple STs build cause (longer accumulation → stronger Jump potential)

    Detection Criteria (Story 4.3 AC):
    - Price proximity: within 2% of SC low (tolerance for range)
    - Volume reduction: 10%+ minimum from SC volume (filters noise)
    - Holding action: ideally holds above SC low, <1% penetration allowed
    - Occurs after AR within ~40 bars (Phase B typical duration)

    Attributes:
        bar: The OHLCV bar where ST occurred - stored as dict
        bar_index: Index position of the bar in the data sequence
        distance_from_sc_low: abs(test_low - sc_low) / sc_low (0.0-0.02, closer = better)
        volume_reduction_pct: (sc_vol - test_vol) / sc_vol (0.10+ minimum, higher = better)
        test_volume_ratio: Volume ratio of ST bar
        sc_volume_ratio: Volume ratio of SC (for comparison)
        penetration: (sc_low - test_low) / sc_low if below, else 0.0 (lower = better)
        confidence: Confidence score 0-100 (volume 40pts + proximity 30pts + holding 30pts)
        sc_reference: Reference to parent SC - stored as dict
        ar_reference: Reference to parent AR - stored as dict
        test_number: Sequential test number (1st ST, 2nd ST, 3rd ST, etc.)
        detection_timestamp: When ST was detected (UTC)
    """

    # Using dict for bar/references to avoid circular import issues
    bar: dict = Field(..., description="The bar where ST occurred")
    bar_index: int = Field(..., ge=0, description="Index position of the bar in the data sequence")
    distance_from_sc_low: Decimal = Field(
        ...,
        ge=Decimal("0.0"),
        le=Decimal("0.02"),
        description="Distance from SC low as percentage (0.0-0.02, within 2% tolerance)",
        decimal_places=4,
    )
    volume_reduction_pct: Decimal = Field(
        ...,
        ge=Decimal("0.0"),
        description="Volume reduction from SC as percentage (0.10+ minimum per AC 4)",
        decimal_places=4,
    )
    test_volume_ratio: Decimal = Field(
        ...,
        description="Volume ratio of ST bar",
        decimal_places=4,
    )
    sc_volume_ratio: Decimal = Field(
        ...,
        description="Volume ratio of SC (for comparison)",
        decimal_places=4,
    )
    penetration: Decimal = Field(
        ...,
        ge=Decimal("0.0"),
        description="Penetration below SC low as percentage (0.0 = no penetration, <0.01 acceptable)",
        decimal_places=4,
    )
    confidence: int = Field(
        ...,
        ge=0,
        le=100,
        description="Confidence score 0-100 (volume 40pts + proximity 30pts + holding 30pts)",
    )
    sc_reference: dict = Field(
        ..., description="The SC that this ST is testing (stored as dict)"
    )
    ar_reference: dict = Field(
        ..., description="The AR that preceded this ST (stored as dict)"
    )
    test_number: int = Field(
        ..., ge=1, description="Sequential test number (1 = first ST, 2 = second ST, etc.)"
    )
    detection_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When ST was detected (UTC)",
    )

    @field_validator("test_volume_ratio")
    @classmethod
    def validate_volume_reduced(cls, v: Decimal, info) -> Decimal:
        """Ensure ST volume is less than SC volume (material reduction required)."""
        # Access sc_volume_ratio from info.data if available
        if "sc_volume_ratio" in info.data and v >= info.data["sc_volume_ratio"]:
            raise ValueError(
                "ST volume must be less than SC volume (volume reduction required)"
            )
        return v

    @field_validator("detection_timestamp")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Enforce UTC timezone."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    model_config = ConfigDict(
        # Allow validation of dict for bar and reference fields
        arbitrary_types_allowed=True,
    )
