"""
Auto-Execution Configuration Models

Pydantic models for automatic signal execution configuration.
Allows traders to set rules for automated trade execution without manual approval.

Story 19.14: Auto-Execution Configuration Backend
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AutoExecutionConfig(BaseModel):
    """
    Auto-execution configuration model.

    Stores user preferences for automatic signal execution including
    confidence thresholds, trade limits, pattern filters, and safety controls.
    """

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID = Field(..., description="User UUID")
    enabled: bool = Field(default=False, description="Auto-execution enabled flag")
    min_confidence: Decimal = Field(
        default=Decimal("85.00"),
        ge=60,
        le=100,
        description="Minimum signal confidence threshold (60-100%)",
    )
    max_trades_per_day: int = Field(
        default=10, ge=1, le=50, description="Maximum trades allowed per day (1-50)"
    )
    max_risk_per_day: Optional[Decimal] = Field(
        default=None, description="Maximum risk per day as percentage (optional, max 10%)"
    )
    circuit_breaker_losses: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Consecutive losses before circuit breaker activates (1-10)",
    )
    enabled_patterns: list[str] = Field(
        default_factory=lambda: ["SPRING", "SOS", "LPS"],
        description="Patterns enabled for auto-execution",
    )
    symbol_whitelist: Optional[list[str]] = Field(
        default=None, description="Symbols allowed for auto-execution (null = all allowed)"
    )
    symbol_blacklist: Optional[list[str]] = Field(
        default=None, description="Symbols blocked from auto-execution"
    )
    kill_switch_active: bool = Field(default=False, description="Emergency kill switch flag")
    consent_given_at: Optional[datetime] = Field(
        default=None, description="Timestamp when user consented to auto-execution"
    )
    consent_ip_address: Optional[str] = Field(
        default=None, max_length=45, description="IP address when consent was given"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Configuration creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Configuration last update timestamp"
    )

    @field_validator("max_risk_per_day")
    @classmethod
    def validate_max_risk(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate max_risk_per_day is within acceptable range."""
        if v is not None:
            if v <= 0:
                raise ValueError("max_risk_per_day must be greater than 0")
            if v > 10:
                raise ValueError("max_risk_per_day cannot exceed 10%")
        return v

    @field_validator("enabled_patterns")
    @classmethod
    def validate_patterns(cls, v: list[str]) -> list[str]:
        """Validate enabled_patterns contains valid pattern types."""
        valid_patterns = {"SPRING", "UTAD", "SOS", "LPS", "SELLING_CLIMAX", "AUTOMATIC_RALLY"}
        invalid = [p for p in v if p not in valid_patterns]
        if invalid:
            raise ValueError(f"Invalid patterns: {invalid}. Valid patterns: {valid_patterns}")
        return v


class AutoExecutionConfigUpdate(BaseModel):
    """
    Update request for auto-execution configuration.

    Allows partial updates to configuration fields.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "min_confidence": 90.0,
                "max_trades_per_day": 5,
                "enabled_patterns": ["SPRING"],
            }
        }
    )

    min_confidence: Optional[Decimal] = Field(
        default=None, ge=60, le=100, description="Minimum signal confidence threshold (60-100%)"
    )
    max_trades_per_day: Optional[int] = Field(
        default=None, ge=1, le=50, description="Maximum trades allowed per day (1-50)"
    )
    max_risk_per_day: Optional[Decimal] = Field(
        default=None, description="Maximum risk per day as percentage (max 10%)"
    )
    circuit_breaker_losses: Optional[int] = Field(
        default=None, ge=1, le=10, description="Consecutive losses before circuit breaker"
    )
    enabled_patterns: Optional[list[str]] = Field(
        default=None, description="Patterns enabled for auto-execution"
    )
    symbol_whitelist: Optional[list[str]] = Field(
        default=None, description="Symbols allowed for auto-execution"
    )
    symbol_blacklist: Optional[list[str]] = Field(
        default=None, description="Symbols blocked from auto-execution"
    )

    @field_validator("max_risk_per_day")
    @classmethod
    def validate_max_risk(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate max_risk_per_day is within acceptable range."""
        if v is not None:
            if v <= 0:
                raise ValueError("max_risk_per_day must be greater than 0")
            if v > 10:
                raise ValueError("max_risk_per_day cannot exceed 10%")
        return v

    @field_validator("enabled_patterns")
    @classmethod
    def validate_patterns(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        """Validate enabled_patterns contains valid pattern types."""
        if v is not None:
            valid_patterns = {"SPRING", "UTAD", "SOS", "LPS", "SELLING_CLIMAX", "AUTOMATIC_RALLY"}
            invalid = [p for p in v if p not in valid_patterns]
            if invalid:
                raise ValueError(f"Invalid patterns: {invalid}. Valid patterns: {valid_patterns}")
        return v


class AutoExecutionEnableRequest(BaseModel):
    """
    Request to enable auto-execution with consent.

    Requires explicit user acknowledgment.

    Note: Password verification will be added in a future story for additional security.
    """

    model_config = ConfigDict(json_schema_extra={"example": {"consent_acknowledged": True}})

    consent_acknowledged: bool = Field(..., description="User acknowledges auto-execution risks")

    @field_validator("consent_acknowledged")
    @classmethod
    def validate_consent(cls, v: bool) -> bool:
        """Ensure consent is explicitly acknowledged."""
        if not v:
            raise ValueError("Consent must be acknowledged to enable auto-execution")
        return v


class AutoExecutionConfigResponse(BaseModel):
    """
    API response with auto-execution configuration and current status.

    Includes real-time metrics like trades executed today and current risk.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "enabled": False,
                "min_confidence": 85.0,
                "max_trades_per_day": 10,
                "max_risk_per_day": None,
                "circuit_breaker_losses": 3,
                "enabled_patterns": ["SPRING", "SOS", "LPS"],
                "symbol_whitelist": None,
                "symbol_blacklist": None,
                "kill_switch_active": False,
                "consent_given_at": None,
                "trades_today": 0,
                "risk_today": 0.0,
            }
        },
    )

    enabled: bool
    min_confidence: Decimal
    max_trades_per_day: int
    max_risk_per_day: Optional[Decimal]
    circuit_breaker_losses: int
    enabled_patterns: list[str]
    symbol_whitelist: Optional[list[str]]
    symbol_blacklist: Optional[list[str]]
    kill_switch_active: bool
    consent_given_at: Optional[datetime]
    trades_today: int = Field(default=0, description="Number of auto-executed trades today")
    risk_today: Decimal = Field(
        default=Decimal("0.0"), description="Total risk deployed today as percentage"
    )


class KillSwitchActivationResponse(BaseModel):
    """Response when kill switch is activated."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "kill_switch_active": True,
                "activated_at": "2026-01-26T10:30:00Z",
                "message": "Kill switch activated - all auto-execution stopped",
            }
        }
    )

    kill_switch_active: bool
    activated_at: datetime
    message: str = Field(default="Kill switch activated - all auto-execution stopped")
