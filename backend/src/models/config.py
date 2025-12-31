"""
Configuration models for system parameters and impact analysis.

This module defines Pydantic models for system configuration including
volume thresholds, risk limits, cause factors, and pattern confidence settings.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VolumeThresholds(BaseModel):
    """Volume ratio thresholds for pattern detection.

    All volume ratios are relative to average volume (1.0x = average).
    """

    spring_volume_min: Decimal = Field(
        default=Decimal("0.7"),
        ge=Decimal("0.5"),
        le=Decimal("1.0"),
        description="Minimum volume ratio for Spring detection (must be < 1.0x per Wyckoff)",
    )
    spring_volume_max: Decimal = Field(
        default=Decimal("1.0"),
        ge=Decimal("0.5"),
        le=Decimal("1.0"),
        description="Maximum volume ratio for Spring detection",
    )
    sos_volume_min: Decimal = Field(
        default=Decimal("2.0"),
        ge=Decimal("1.5"),
        le=Decimal("3.0"),
        description="Minimum volume ratio for SOS detection (≥1.5x confirms demand)",
    )
    lps_volume_min: Decimal = Field(
        default=Decimal("0.5"),
        ge=Decimal("0.3"),
        le=Decimal("1.0"),
        description="Minimum volume ratio for LPS detection",
    )
    utad_volume_max: Decimal = Field(
        default=Decimal("0.7"),
        ge=Decimal("0.3"),
        le=Decimal("1.0"),
        description="Maximum volume ratio for UTAD detection",
    )

    @field_validator("spring_volume_min", "spring_volume_max")
    @classmethod
    def validate_spring_volume(cls, v: Decimal) -> Decimal:
        """Validate spring volume is below average per Wyckoff methodology."""
        if v > Decimal("1.0"):
            raise ValueError(
                "Spring patterns require volume BELOW average (< 1.0x) per Wyckoff principles"
            )
        return v

    @field_validator("sos_volume_min")
    @classmethod
    def validate_sos_volume(cls, v: Decimal) -> Decimal:
        """Validate SOS volume shows expansion per Wyckoff methodology."""
        if v < Decimal("1.5"):
            raise ValueError(
                "Sign of Strength requires volume expansion (≥ 1.5x) to confirm demand"
            )
        return v


class RiskLimits(BaseModel):
    """Risk management limits as percentages of account equity."""

    max_risk_per_trade: Decimal = Field(
        default=Decimal("2.0"),
        ge=Decimal("1.0"),
        le=Decimal("3.0"),
        description="Maximum risk per trade (%)",
    )
    max_campaign_risk: Decimal = Field(
        default=Decimal("5.0"),
        ge=Decimal("3.0"),
        le=Decimal("7.0"),
        description="Maximum campaign risk (%)",
    )
    max_portfolio_heat: Decimal = Field(
        default=Decimal("10.0"),
        ge=Decimal("5.0"),
        le=Decimal("15.0"),
        description="Maximum portfolio heat (%)",
    )

    @field_validator("max_campaign_risk")
    @classmethod
    def validate_campaign_risk(cls, v: Decimal, info) -> Decimal:
        """Validate campaign risk is greater than per-trade risk."""
        if "max_risk_per_trade" in info.data and v <= info.data["max_risk_per_trade"]:
            raise ValueError("max_campaign_risk must be greater than max_risk_per_trade")
        return v

    @field_validator("max_portfolio_heat")
    @classmethod
    def validate_portfolio_heat(cls, v: Decimal, info) -> Decimal:
        """Validate portfolio heat is greater than campaign risk."""
        if "max_campaign_risk" in info.data and v <= info.data["max_campaign_risk"]:
            raise ValueError("max_portfolio_heat must be greater than max_campaign_risk")
        return v


class CauseFactors(BaseModel):
    """Cause-to-effect ratio thresholds per Wyckoff methodology.

    A 2:1 ratio means accumulation period is 2x the expected move duration.
    """

    min_cause_factor: Decimal = Field(
        default=Decimal("2.0"),
        ge=Decimal("2.0"),
        le=Decimal("2.5"),
        description="Minimum cause-to-effect ratio (Wyckoff requires ≥2.0)",
    )
    max_cause_factor: Decimal = Field(
        default=Decimal("3.0"),
        ge=Decimal("2.5"),
        le=Decimal("4.0"),
        description="Maximum cause-to-effect ratio for filtering",
    )

    @field_validator("min_cause_factor")
    @classmethod
    def validate_min_cause_factor(cls, v: Decimal) -> Decimal:
        """Validate minimum cause factor follows Wyckoff methodology."""
        if v < Decimal("2.0"):
            raise ValueError(
                "Wyckoff methodology requires minimum 2:1 cause-to-effect ratio for reliable projections"
            )
        return v

    @field_validator("max_cause_factor")
    @classmethod
    def validate_max_cause_factor(cls, v: Decimal, info) -> Decimal:
        """Validate max cause factor is greater than min."""
        if "min_cause_factor" in info.data and v <= info.data["min_cause_factor"]:
            raise ValueError("max_cause_factor must be greater than min_cause_factor")
        return v


class PatternConfidence(BaseModel):
    """Minimum confidence thresholds for pattern-based signals."""

    min_spring_confidence: int = Field(
        default=70, ge=70, le=95, description="Minimum confidence for Spring signals"
    )
    min_sos_confidence: int = Field(
        default=70, ge=70, le=95, description="Minimum confidence for SOS signals"
    )
    min_lps_confidence: int = Field(
        default=70, ge=70, le=95, description="Minimum confidence for LPS signals"
    )
    min_utad_confidence: int = Field(
        default=70, ge=70, le=95, description="Minimum confidence for UTAD signals"
    )


class SystemConfiguration(BaseModel):
    """Complete system configuration with all parameter categories.

    This model supports optimistic locking via the version field.

    Example:
        >>> config = SystemConfiguration(
        ...     volume_thresholds=VolumeThresholds(),
        ...     risk_limits=RiskLimits(),
        ...     cause_factors=CauseFactors(),
        ...     pattern_confidence=PatternConfidence()
        ... )
    """

    model_config = ConfigDict(
        json_encoders={
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        }
    )

    id: UUID = Field(default_factory=uuid4)
    version: int = Field(default=1, ge=1, description="Version for optimistic locking")
    volume_thresholds: VolumeThresholds = Field(default_factory=VolumeThresholds)
    risk_limits: RiskLimits = Field(default_factory=RiskLimits)
    cause_factors: CauseFactors = Field(default_factory=CauseFactors)
    pattern_confidence: PatternConfidence = Field(default_factory=PatternConfidence)
    applied_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    applied_by: Optional[str] = Field(default=None, max_length=100)


class ImpactAnalysisResult(BaseModel):
    """Result of analyzing configuration change impact.

    Provides metrics on how proposed configuration changes would affect
    signal generation and performance based on historical pattern data.
    """

    model_config = ConfigDict(
        json_encoders={
            Decimal: str,
        }
    )

    signal_count_delta: int = Field(
        description="Change in qualifying signals (positive = more signals)"
    )
    current_signal_count: int = Field(description="Number of signals under current configuration")
    proposed_signal_count: int = Field(description="Number of signals under proposed configuration")
    current_win_rate: Optional[Decimal] = Field(
        default=None, description="Historical win rate under current configuration"
    )
    proposed_win_rate: Optional[Decimal] = Field(
        default=None, description="Estimated win rate under proposed configuration"
    )
    win_rate_delta: Optional[Decimal] = Field(
        default=None, description="Change in win rate (positive = improvement)"
    )
    confidence_range: dict[str, Decimal] = Field(
        default_factory=dict, description="Confidence bounds: {'min': Decimal, 'max': Decimal}"
    )
    recommendations: list["Recommendation"] = Field(
        default_factory=list, description="AI-generated recommendations about proposed changes"
    )
    risk_impact: Optional[str] = Field(
        default=None, description="Description of risk profile changes"
    )


class Recommendation(BaseModel):
    """AI-generated recommendation about configuration changes.

    Uses rule-based system (MVP) to provide contextual advice.
    """

    severity: str = Field(description="Severity level: INFO, WARNING, CAUTION")
    message: str = Field(description="Human-readable recommendation message")
    category: Optional[str] = Field(
        default=None, description="Configuration category affected (volume, risk, etc.)"
    )

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        """Validate severity is a known level."""
        allowed = {"INFO", "WARNING", "CAUTION"}
        if v not in allowed:
            raise ValueError(f"Severity must be one of {allowed}")
        return v


# Update forward references
ImpactAnalysisResult.model_rebuild()
