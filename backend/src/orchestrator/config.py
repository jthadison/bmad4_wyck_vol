"""
Orchestrator Configuration Module.

Defines configuration settings for the MasterOrchestrator including pipeline
settings, cache configuration, performance tuning, and error handling parameters.

Story 8.1: Master Orchestrator Architecture (AC: 4, 7)
"""

from typing import Literal

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

    Attributes:
        default_lookback_bars: Number of bars to fetch for analysis (default: 500)
        max_concurrent_symbols: Maximum symbols to analyze concurrently (default: 10)
        cache_ttl_seconds: Cache time-to-live in seconds (default: 300)
        cache_max_size: Maximum cache entries (default: 1000)
        enable_parallel_processing: Enable parallel symbol analysis (default: True)
        enable_caching: Enable result caching (default: True)
        max_detector_retries: Max retries for failed detectors (default: 3)
        circuit_breaker_threshold: Failures before circuit opens (default: 5)
        detector_mode: Detector mode - production/test/mock (default: production)
        min_range_quality_score: Minimum quality score for ranges (default: 60)
        min_phase_confidence: Minimum phase confidence percentage (default: 70)
    """

    # Pipeline settings
    default_lookback_bars: int = 500
    max_concurrent_symbols: int = 10

    # Cache settings
    cache_ttl_seconds: int = 300  # 5 minutes
    cache_max_size: int = 1000

    # Performance settings
    enable_parallel_processing: bool = True
    enable_caching: bool = True

    # Error handling
    max_detector_retries: int = 3
    circuit_breaker_threshold: int = 5  # failures before circuit opens
    circuit_breaker_reset_seconds: int = 60  # time before circuit closes

    # Detector modes
    detector_mode: Literal["production", "test", "mock"] = "production"

    # Validation thresholds (from FR requirements)
    min_range_quality_score: int = 60  # FR9
    min_phase_confidence: int = 70  # FR3

    # Performance targets
    target_per_symbol_ms: int = 500  # Target <500ms per symbol
    target_total_ms: int = 5000  # Target <5s for 10 symbols

    class Config:
        """Pydantic configuration."""

        env_prefix = "ORCHESTRATOR_"
        case_sensitive = False
