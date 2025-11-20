"""
Correlation Risk Data Models - Stock Sector Correlation Tracking

Purpose:
--------
Provides Pydantic models for tracking correlated risk at the campaign level
with tiered limits (sector 6%, asset class 15%, geography 20%) to prevent
over-concentration in stock sectors while respecting Wyckoff campaign methodology.

Data Models:
------------
1. SectorMapping: Symbol → sector/asset class/geography mapping
2. CorrelationConfig: Tiered correlation limits configuration
3. CorrelatedRisk: Campaign-level correlation tracking with utilization

Wyckoff Context - Campaign-Level Correlation:
----------------------------------------------
Wyckoff methodology manages CAMPAIGNS (accumulation cycles), not individual positions.
A campaign may scale into multiple positions (Spring → LPS add #1 → LPS add #2), but
this is ONE correlated risk unit, not three separate risks.

Key Distinction:
----------------
- Campaign scaling: Spring → LPS add #1 → LPS add #2 = ONE correlation risk unit
- New campaign: AAPL campaign + MSFT campaign = TWO correlation risk units

Tiered Correlation Limits (AC 14):
-----------------------------------
- Sector: 6% max (strictest - sectors rotate together, e.g., Technology)
- Asset class: 15% max (moderate - allows cross-sector diversification, e.g., stocks)
- Geography: 20% max or optional (loosest - macro risk control, e.g., US)

Example: 6% Tech + 6% Healthcare = 12% stocks → PASSES (under 15% asset class limit)

Integration:
------------
- Story 7.4: Uses Campaign model for campaign-level correlation
- Story 7.5: Core data models for correlation risk tracking

Author: Story 7.5
"""

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer


class SectorMapping(BaseModel):
    """
    Symbol sector/asset class/geography mapping.

    Maps trading symbols to their sector classification, asset class,
    and optional geography for correlation risk calculations.

    Fields:
    -------
    - symbol: Trading symbol (e.g., "AAPL")
    - sector: Sector classification (e.g., "Technology", "Healthcare")
    - asset_class: Asset class (e.g., "stock", "futures", "crypto", "forex")
    - geography: Optional geography (e.g., "US", "EU", "ASIA", None)

    Example:
    --------
    >>> mapping = SectorMapping(
    ...     symbol="AAPL",
    ...     sector="Technology",
    ...     asset_class="stock",
    ...     geography="US"
    ... )
    """

    symbol: str = Field(..., max_length=20, description="Trading symbol")
    sector: str = Field(..., description="Sector classification")
    asset_class: str = Field(..., description="stocks, futures, crypto, forex")
    geography: str | None = Field(None, description="US, EU, ASIA, etc.")

    model_config = ConfigDict(frozen=True)  # Immutable after loading


class CorrelationConfig(BaseModel):
    """
    Tiered correlation limits configuration (Wyckoff Review - AC 14).

    Implements tiered limits by specificity:
    - Sector: 6% (strictest - sectors rotate together)
    - Asset class: 15% (moderate - allows cross-sector diversification)
    - Geography: 20% or None (loosest - optional macro risk control)

    Campaign Count Limits (AC 12):
    -------------------------------
    - Maximum 3 simultaneous campaigns per sector
    - Prevents over-fragmentation of sector exposure

    Enforcement Modes (AC 6):
    --------------------------
    - Strict: Reject if ANY level exceeds its specific limit
    - Permissive: Warn but allow if ANY level exceeds its specific limit

    Fields:
    -------
    - max_sector_correlation: Sector limit (default 6.0%)
    - max_asset_class_correlation: Asset class limit (default 15.0%)
    - max_geography_correlation: Geography limit (default None = disabled)
    - max_campaigns_per_sector: Campaign count limit (default 3)
    - enforcement_mode: "strict" or "permissive"
    - sector_mappings: Symbol → SectorMapping lookup dictionary

    Example:
    --------
    >>> from decimal import Decimal
    >>> config = CorrelationConfig(
    ...     max_sector_correlation=Decimal("6.0"),
    ...     max_asset_class_correlation=Decimal("15.0"),
    ...     max_geography_correlation=None,
    ...     max_campaigns_per_sector=3,
    ...     enforcement_mode="strict",
    ...     sector_mappings={}
    ... )
    """

    max_sector_correlation: Decimal = Field(
        Decimal("6.0"),
        decimal_places=2,
        max_digits=4,
        description="Maximum sector correlation percentage (strictest)",
    )

    max_asset_class_correlation: Decimal = Field(
        Decimal("15.0"),
        decimal_places=2,
        max_digits=4,
        description="Maximum asset class correlation percentage (moderate)",
    )

    max_geography_correlation: Decimal | None = Field(
        None,
        description="Maximum geography correlation percentage (optional)",
    )

    max_campaigns_per_sector: int = Field(
        3, ge=1, description="Maximum number of simultaneous campaigns per sector"
    )

    enforcement_mode: Literal["strict", "permissive"] = Field(
        "strict", description="strict=reject, permissive=warn"
    )

    sector_mappings: dict[str, SectorMapping] = Field(
        default_factory=dict, description="Symbol -> SectorMapping lookup"
    )

    @field_validator("max_geography_correlation")
    @classmethod
    def validate_geography_correlation(cls, v: Decimal | None) -> Decimal | None:
        """Validate geography correlation if provided."""
        if v is not None and v <= Decimal("0"):
            raise ValueError("max_geography_correlation must be positive or None")
        return v

    model_config = ConfigDict()

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with Decimal as strings."""
        return {
            "max_sector_correlation": str(self.max_sector_correlation),
            "max_asset_class_correlation": str(self.max_asset_class_correlation),
            "max_geography_correlation": (
                str(self.max_geography_correlation) if self.max_geography_correlation else None
            ),
            "max_campaigns_per_sector": self.max_campaigns_per_sector,
            "enforcement_mode": self.enforcement_mode,
            "sector_mappings": {
                symbol: {
                    "symbol": mapping.symbol,
                    "sector": mapping.sector,
                    "asset_class": mapping.asset_class,
                    "geography": mapping.geography,
                }
                for symbol, mapping in self.sector_mappings.items()
            },
        }


class CorrelatedRisk(BaseModel):
    """
    Campaign-level correlation tracking (Wyckoff Review - AC 11, 13).

    Tracks correlated risk at CAMPAIGN level (not position level) to properly
    handle Wyckoff campaign scaling. A campaign with 3 positions (Spring → LPS adds)
    is ONE correlation risk unit, not three.

    Campaign vs Position Distinction:
    ----------------------------------
    - Campaign scaling: Spring → LPS add #1 → LPS add #2 = 1 campaign correlation
    - New campaigns: AAPL campaign + MSFT campaign = 2 campaign correlations

    Fields:
    -------
    - correlation_type: "sector", "asset_class", or "geography"
    - correlation_key: The specific correlation group (e.g., "Technology", "stock", "US")
    - total_risk: Total correlated risk percentage across all campaigns
    - campaign_count: Number of campaigns in this correlation group (NEW - AC 13)
    - campaign_breakdown: Campaign ID → risk mapping (NEW - AC 13)
    - position_count: Total positions across all campaigns (for reporting)
    - risk_breakdown: Symbol → risk mapping (position-level detail)
    - limit: Appropriate limit for this correlation type (6%, 15%, or 20%)
    - utilization_pct: (total_risk / limit) × 100

    Example:
    --------
    >>> from decimal import Decimal
    >>> from uuid import uuid4
    >>> correlated_risk = CorrelatedRisk(
    ...     correlation_type="sector",
    ...     correlation_key="Technology",
    ...     total_risk=Decimal("4.5"),
    ...     campaign_count=3,
    ...     campaign_breakdown={
    ...         str(uuid4()): Decimal("1.5"),
    ...         str(uuid4()): Decimal("1.5"),
    ...         str(uuid4()): Decimal("1.5")
    ...     },
    ...     position_count=5,
    ...     risk_breakdown={
    ...         "AAPL": Decimal("1.5"),
    ...         "MSFT": Decimal("1.5"),
    ...         "GOOGL": Decimal("1.5")
    ...     },
    ...     limit=Decimal("6.0"),
    ...     utilization_pct=Decimal("75.0")
    ... )
    """

    correlation_type: str = Field(..., description="sector, asset_class, geography")
    correlation_key: str = Field(..., description="e.g., Technology, stock, US")
    total_risk: Decimal = Field(..., decimal_places=4, max_digits=6)

    # NEW: Campaign-level tracking (AC 13)
    campaign_count: int = Field(
        ..., ge=0, description="Number of campaigns in this correlation group"
    )
    campaign_breakdown: dict[str, Decimal] = Field(
        default_factory=dict, description="Campaign ID -> risk_pct mapping"
    )

    # KEEP: Position-level detail for reporting
    position_count: int = Field(..., ge=0, description="Total positions across all campaigns")
    risk_breakdown: dict[str, Decimal] = Field(
        default_factory=dict, description="Symbol -> risk_pct mapping (position-level detail)"
    )

    limit: Decimal = Field(
        ..., decimal_places=2, max_digits=4, description="Limit for this correlation type"
    )
    utilization_pct: Decimal = Field(
        ..., decimal_places=2, max_digits=6, description="(total_risk / limit) * 100"
    )

    model_config = ConfigDict()

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with Decimal as strings."""
        return {
            "correlation_type": self.correlation_type,
            "correlation_key": self.correlation_key,
            "total_risk": str(self.total_risk),
            "campaign_count": self.campaign_count,
            "campaign_breakdown": {k: str(v) for k, v in self.campaign_breakdown.items()},
            "position_count": self.position_count,
            "risk_breakdown": {k: str(v) for k, v in self.risk_breakdown.items()},
            "limit": str(self.limit),
            "utilization_pct": str(self.utilization_pct),
        }


# Correlation limit constants (AC 1, 14)
MAX_SECTOR_CORRELATION_PCT = Decimal("6.0")  # Strictest
MAX_ASSET_CLASS_CORRELATION_PCT = Decimal("15.0")  # Moderate
MAX_GEOGRAPHY_CORRELATION_PCT = Decimal("20.0")  # Loosest (optional)

# Campaign count limits (AC 12)
MAX_CAMPAIGNS_PER_SECTOR = 3

# Proximity warning threshold (80% of limit)
SECTOR_PROXIMITY_WARNING_PCT = Decimal("4.8")  # 80% of 6.0%
ASSET_CLASS_PROXIMITY_WARNING_PCT = Decimal("12.0")  # 80% of 15.0%
GEOGRAPHY_PROXIMITY_WARNING_PCT = Decimal("16.0")  # 80% of 20.0%


class RMultipleConfig(BaseModel):
    """
    Pattern-specific R-multiple (risk/reward) threshold configuration.

    Implements Wyckoff-optimized R-multiple requirements per pattern type.
    R-multiple = (Target - Entry) / (Entry - Stop)

    Pattern-Specific Thresholds:
    -----------------------------
    - Spring: min 3.0R, ideal 4.0R, max 10.0R (Phase C test - tight stop, high probability)
    - ST (Secondary Test): min 2.5R, ideal 3.5R, max 8.0R (validates Spring)
    - SOS: min 2.5R, ideal 3.5R, max 8.0R (breakout volatility + "Jump the Creek" risk)
    - LPS: min 2.5R, ideal 3.5R, max 8.0R (pullback confirmation)
    - UTAD: min 3.5R, ideal 5.0R, max 12.0R (SHORT trade - higher R required)

    Fields:
    -------
    - pattern_type: SPRING, ST, SOS, LPS, or UTAD
    - minimum_r: Reject if R < minimum (hard stop)
    - ideal_r: Warn if R < ideal (suboptimal but acceptable)
    - maximum_r: Reject if R > maximum (unrealistic target/stop combo)

    Example:
    --------
    >>> from decimal import Decimal
    >>> config = RMultipleConfig(
    ...     pattern_type="SPRING",
    ...     minimum_r=Decimal("3.0"),
    ...     ideal_r=Decimal("4.0"),
    ...     maximum_r=Decimal("10.0")
    ... )

    Author: Story 7.6
    """

    pattern_type: Literal["SPRING", "ST", "SOS", "LPS", "UTAD"] = Field(
        ..., description="Pattern type"
    )
    minimum_r: Decimal = Field(
        ...,
        decimal_places=2,
        max_digits=6,
        description="Minimum R-multiple threshold (reject below)",
    )
    ideal_r: Decimal = Field(
        ...,
        decimal_places=2,
        max_digits=6,
        description="Ideal R-multiple threshold (warn below)",
    )
    maximum_r: Decimal = Field(
        ...,
        decimal_places=2,
        max_digits=6,
        description="Maximum reasonable R-multiple (reject above)",
    )

    model_config = ConfigDict()

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with Decimal as strings."""
        return {
            "pattern_type": self.pattern_type,
            "minimum_r": str(self.minimum_r),
            "ideal_r": str(self.ideal_r),
            "maximum_r": str(self.maximum_r),
        }


class RMultipleValidation(BaseModel):
    """
    R-multiple validation result.

    Contains calculated R-multiple and validation status for a trade setup.

    Fields:
    -------
    - is_valid: True if R-multiple meets minimum requirements
    - r_multiple: Calculated R-multiple value
    - rejection_reason: Reason for rejection if is_valid=False
    - warning: Warning message if below ideal but acceptable
    - status: REJECTED, ACCEPTABLE, or IDEAL

    Example:
    --------
    >>> from decimal import Decimal
    >>> validation = RMultipleValidation(
    ...     is_valid=True,
    ...     r_multiple=Decimal("3.5"),
    ...     rejection_reason=None,
    ...     warning="R-multiple 3.5 below ideal 4.0 for SPRING",
    ...     status="ACCEPTABLE"
    ... )

    Author: Story 7.6
    """

    is_valid: bool = Field(..., description="Whether R-multiple meets minimum requirements")
    r_multiple: Decimal = Field(
        ..., decimal_places=2, max_digits=6, description="Calculated R-multiple"
    )
    rejection_reason: str | None = Field(
        default=None, description="Reason for rejection if is_valid=False"
    )
    warning: str | None = Field(
        default=None, description="Warning message if below ideal but acceptable"
    )
    status: Literal["REJECTED", "ACCEPTABLE", "IDEAL"] = Field(
        ..., description="R-multiple validation status"
    )

    model_config = ConfigDict()

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with Decimal as strings."""
        return {
            "is_valid": self.is_valid,
            "r_multiple": str(self.r_multiple),
            "rejection_reason": self.rejection_reason,
            "warning": self.warning,
            "status": self.status,
        }


# R-Multiple Threshold Constants (Story 7.6 - AC 2, 5)
# Pattern-specific minimum R-multiples (rejection threshold)
SPRING_MINIMUM_R = Decimal("3.0")  # Phase C test - tight stop, high probability
ST_MINIMUM_R = Decimal("2.5")  # Secondary Test - validates Spring
SOS_MINIMUM_R = Decimal("2.5")  # Breakout volatility + "Jump the Creek" risk
LPS_MINIMUM_R = Decimal("2.5")  # Pullback confirmation
UTAD_MINIMUM_R = Decimal("3.5")  # SHORT trade - higher R required

# Pattern-specific ideal R-multiples (warning threshold)
SPRING_IDEAL_R = Decimal("4.0")
ST_IDEAL_R = Decimal("3.5")
SOS_IDEAL_R = Decimal("3.5")
LPS_IDEAL_R = Decimal("3.5")
UTAD_IDEAL_R = Decimal("5.0")  # SHORT trade - better reward needed

# Pattern-specific maximum R-multiples (unreasonable threshold)
SPRING_MAXIMUM_R = Decimal("10.0")  # Tight stop, realistic target
ST_MAXIMUM_R = Decimal("8.0")  # Medium stops, breakout/pullback dynamics
SOS_MAXIMUM_R = Decimal("8.0")
LPS_MAXIMUM_R = Decimal("8.0")
UTAD_MAXIMUM_R = Decimal("12.0")  # SHORT - allow higher R due to markdown velocity
