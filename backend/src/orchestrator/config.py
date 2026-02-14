"""
Orchestrator Configuration Module.

Single source of truth for MasterOrchestrator settings. All fields use the
ORCHESTRATOR_ environment variable prefix (e.g., ORCHESTRATOR_MAX_CONCURRENT_SYMBOLS).

The global Settings class in src/config.py does NOT duplicate these fields;
see docs/architecture/configuration.md for the full configuration map.

Story 8.1: Master Orchestrator Architecture (AC: 4, 7)
"""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class OrchestratorConfig(BaseSettings):
    """
    Configuration for MasterOrchestrator.

    All settings can be overridden via environment variables with ORCHESTRATOR_ prefix.

    Example:
        # Via environment variables:
        ORCHESTRATOR_DEFAULT_LOOKBACK_BARS=1000
        ORCHESTRATOR_CACHE_TTL_SECONDS=600
        ORCHESTRATOR_DETECTOR_MODE=test
    """

    # Pipeline settings
    default_lookback_bars: int = Field(
        default=500,
        ge=50,
        le=5000,
        description="Number of bars to fetch for analysis",
    )
    max_concurrent_symbols: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum symbols to analyze concurrently",
    )

    # Cache settings
    cache_ttl_seconds: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Cache time-to-live in seconds (5 minutes default)",
    )
    cache_max_size: int = Field(
        default=1000,
        ge=100,
        le=50000,
        description="Maximum cache entries before LRU eviction",
    )

    # Performance settings
    enable_parallel_processing: bool = Field(
        default=True,
        description="Enable parallel symbol analysis via asyncio",
    )
    enable_caching: bool = Field(
        default=True,
        description="Enable caching of intermediate results (ranges, phases, volume)",
    )

    # Error handling
    max_detector_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retries for failed detectors before giving up",
    )
    circuit_breaker_threshold: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Consecutive failures before circuit breaker opens",
    )
    circuit_breaker_reset_seconds: int = Field(
        default=60,
        ge=10,
        le=600,
        description="Seconds before circuit breaker resets from open to half-open",
    )

    # Detector modes
    detector_mode: Literal["production", "test", "mock"] = Field(
        default="production",
        description="Detector mode: production uses real detectors, test/mock for testing",
    )

    # Validation thresholds (from FR requirements)
    min_range_quality_score: int = Field(
        default=60,
        ge=0,
        le=100,
        description="Minimum quality score for trading ranges (FR9)",
    )
    min_phase_confidence: int = Field(
        default=70,
        ge=0,
        le=100,
        description="Minimum phase confidence percentage (FR3)",
    )

    # Performance targets
    target_per_symbol_ms: int = Field(
        default=500,
        ge=100,
        le=5000,
        description="Target processing time per symbol in milliseconds",
    )
    target_total_ms: int = Field(
        default=5000,
        ge=1000,
        le=30000,
        description="Target total processing time for all symbols in milliseconds",
    )

    class Config:
        """Pydantic configuration."""

        env_prefix = "ORCHESTRATOR_"
        case_sensitive = False
