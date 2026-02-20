"""
Volume Profile by Wyckoff Phase models.

Pydantic models for VPVR (Volume Profile Visible Range) data
segmented by Wyckoff phase. Used by the volume-profile API endpoint.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class VolumeProfileBin(BaseModel):
    """A single price bin in the volume profile."""

    price_level: float = Field(..., description="Mid-price of this bin")
    price_low: float = Field(..., description="Bottom of bin")
    price_high: float = Field(..., description="Top of bin")
    volume: float = Field(..., ge=0, description="Total volume in this bin")
    pct_of_phase_volume: float = Field(
        ..., ge=0.0, le=1.0, description="Fraction of total phase volume"
    )
    is_poc: bool = Field(False, description="Point of Control for this phase")
    in_value_area: bool = Field(False, description="Within 70% value area")


class PhaseVolumeData(BaseModel):
    """Volume profile data for a single Wyckoff phase."""

    phase: str = Field(..., description="Phase label: A, B, C, D, E, or COMBINED")
    bins: list[VolumeProfileBin] = Field(default_factory=list)
    poc_price: Optional[float] = Field(None, description="Point of Control price level")
    total_volume: float = Field(0.0, ge=0)
    bar_count: int = Field(0, ge=0, description="Number of bars in this phase")
    value_area_low: Optional[float] = None
    value_area_high: Optional[float] = None


class VolumeProfileResponse(BaseModel):
    """Full volume profile response segmented by Wyckoff phase."""

    symbol: str
    timeframe: str
    price_range_low: float
    price_range_high: float
    bin_width: float
    num_bins: int
    phases: list[PhaseVolumeData] = Field(
        default_factory=list, description="One per phase present in data"
    )
    combined: PhaseVolumeData = Field(..., description="All phases combined")
    current_price: Optional[float] = None
