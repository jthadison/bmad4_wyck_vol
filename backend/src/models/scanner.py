"""
Scanner Models for Multi-Symbol Processing.

Pydantic models for scanner status, symbol processing state,
and health monitoring. Story 19.4.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class SymbolState(str, Enum):
    """Processing state for a symbol."""

    PROCESSING = "processing"
    PAUSED = "paused"
    FAILED = "failed"
    IDLE = "idle"


class CircuitStateEnum(str, Enum):
    """Circuit breaker states for API responses."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class SymbolStatus(BaseModel):
    """
    Status of a single symbol's processing.

    Tracks processing state, failures, and performance metrics.
    """

    symbol: str = Field(description="Symbol ticker")
    state: SymbolState = Field(description="Current processing state")
    last_processed: datetime | None = Field(
        default=None, description="Timestamp of last processed bar"
    )
    consecutive_failures: int = Field(default=0, ge=0, description="Number of consecutive failures")
    circuit_state: CircuitStateEnum = Field(
        default=CircuitStateEnum.CLOSED, description="Circuit breaker state"
    )
    avg_latency_ms: float = Field(default=0.0, ge=0, description="Average processing latency in ms")
    bars_processed: int = Field(default=0, ge=0, description="Total bars processed for this symbol")
    last_error: str | None = Field(default=None, description="Last error message if any")

    class Config:
        """Pydantic config."""

        use_enum_values = True


class ScannerStatusResponse(BaseModel):
    """
    API response for scanner status endpoint.

    Provides overall health and per-symbol status.
    """

    overall_status: Literal["healthy", "degraded", "unhealthy"] = Field(
        description="Overall scanner health status"
    )
    symbols: list[SymbolStatus] = Field(default_factory=list, description="Status for each symbol")
    total_symbols: int = Field(ge=0, description="Total number of symbols monitored")
    healthy_symbols: int = Field(ge=0, description="Number of healthy symbols")
    paused_symbols: int = Field(ge=0, description="Number of paused symbols")
    failed_symbols: int = Field(default=0, ge=0, description="Number of failed symbols")
    avg_latency_ms: float = Field(default=0.0, ge=0, description="Overall average latency in ms")
    is_running: bool = Field(default=False, description="Whether scanner is currently running")


class SymbolProcessingConfig(BaseModel):
    """Configuration for symbol processing."""

    symbol: str = Field(description="Symbol ticker")
    timeframe: str = Field(default="1m", description="Bar timeframe")
    enabled: bool = Field(default=True, description="Whether processing is enabled")


class ScannerConfig(BaseModel):
    """Configuration for the multi-symbol scanner."""

    symbols: list[SymbolProcessingConfig] = Field(
        default_factory=list, description="Symbols to process"
    )
    max_concurrent: int = Field(
        default=10, ge=1, le=100, description="Maximum concurrent symbol processing"
    )
    processing_timeout_ms: int = Field(
        default=200, ge=50, le=5000, description="Target processing time per bar"
    )
    circuit_breaker_threshold: int = Field(
        default=3, ge=1, le=10, description="Failures before circuit opens"
    )
    circuit_breaker_reset_seconds: float = Field(
        default=30.0, ge=5.0, le=300.0, description="Time before circuit half-opens"
    )
