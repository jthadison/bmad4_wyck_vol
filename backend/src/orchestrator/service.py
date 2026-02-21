"""
Orchestrator Service - FastAPI Integration.

Provides singleton orchestrator instance for use across the application,
with lifespan management and health check endpoint integration.

Story 8.1: Master Orchestrator Architecture (AC: 6, 7)
Story 23.2: Wire orchestrator pipeline with real detectors
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI

from src.orchestrator.cache import reset_orchestrator_cache
from src.orchestrator.config import OrchestratorConfig
from src.orchestrator.container import (
    reset_orchestrator_container,
)
from src.orchestrator.event_bus import reset_event_bus
from src.orchestrator.master_orchestrator import TradeSignal
from src.orchestrator.orchestrator_facade import MasterOrchestratorFacade

logger = structlog.get_logger(__name__)

# Global orchestrator instance (Story 23.2: uses facade with real detectors)
_orchestrator: MasterOrchestratorFacade | None = None


def get_orchestrator() -> MasterOrchestratorFacade:
    """
    Get the global orchestrator instance.

    Creates a new instance if one doesn't exist.
    Uses MasterOrchestratorFacade which wires real detectors
    (Spring, SOS, UTAD, LPS) via PipelineCoordinator.

    Returns:
        The global MasterOrchestratorFacade instance
    """
    global _orchestrator

    if _orchestrator is None:
        _orchestrator = MasterOrchestratorFacade()
        logger.info("orchestrator_service_created")

    return _orchestrator


def reset_orchestrator() -> None:
    """
    Reset the global orchestrator instance.

    Useful for testing and reinitialization scenarios.
    """
    global _orchestrator

    if _orchestrator is not None:
        logger.info("orchestrator_service_reset")
        _orchestrator = None

    # Also reset dependencies
    reset_event_bus()
    reset_orchestrator_cache()
    reset_orchestrator_container()


async def analyze_symbol(symbol: str, timeframe: str = "1d") -> list[TradeSignal]:
    """
    Analyze a single symbol for trade signals.

    Convenience function for API endpoints.

    Args:
        symbol: Stock symbol to analyze
        timeframe: Bar timeframe (default: "1d")

    Returns:
        List of generated trade signals
    """
    orchestrator = get_orchestrator()
    return await orchestrator.analyze_symbol(symbol, timeframe)


async def trigger_analysis(symbol: str, timeframe: str) -> None:
    """
    Called by MarketDataCoordinator when a new bar is inserted.

    Runs orchestrator analysis and logs any generated signals.
    Exceptions are caught and logged so they never propagate
    back to the bar-insertion path.
    """
    orchestrator = get_orchestrator()
    try:
        signals = await orchestrator.analyze_symbol(symbol, timeframe)
        if signals:
            logger.info(
                "live_signals_generated",
                symbol=symbol,
                timeframe=timeframe,
                count=len(signals),
            )
    except Exception as exc:
        logger.warning(
            "live_analysis_failed",
            symbol=symbol,
            timeframe=timeframe,
            error=str(exc),
        )


async def analyze_symbols(
    symbols: list[str], timeframe: str = "1d"
) -> dict[str, list[TradeSignal]]:
    """
    Analyze multiple symbols for trade signals.

    Processes symbols in parallel for efficiency.

    Args:
        symbols: List of stock symbols to analyze
        timeframe: Bar timeframe (default: "1d")

    Returns:
        Dictionary mapping symbols to their generated signals
    """
    orchestrator = get_orchestrator()
    return await orchestrator.analyze_symbols(symbols, timeframe)


def get_orchestrator_health() -> dict[str, Any]:
    """
    Get orchestrator health status.

    Returns health information including component status and metrics.

    Returns:
        Dictionary with health information
    """
    orchestrator = get_orchestrator()
    return orchestrator.get_health()


@asynccontextmanager
async def orchestrator_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan context manager for orchestrator initialization.

    Use with FastAPI's lifespan parameter:

        app = FastAPI(lifespan=orchestrator_lifespan)

    Yields:
        None
    """
    # Startup: Initialize orchestrator
    logger.info("orchestrator_service_starting")

    try:
        orchestrator = get_orchestrator()
        logger.info(
            "orchestrator_service_started",
            config={
                "lookback_bars": orchestrator._config.default_lookback_bars,
                "max_concurrent": orchestrator._config.max_concurrent_symbols,
                "cache_enabled": orchestrator._config.enable_caching,
            },
        )
    except Exception as e:
        logger.error("orchestrator_service_startup_failed", error=str(e))
        raise

    yield

    # Shutdown: Cleanup orchestrator
    logger.info("orchestrator_service_stopping")
    reset_orchestrator()
    logger.info("orchestrator_service_stopped")


def create_orchestrator_with_config(config: OrchestratorConfig) -> MasterOrchestratorFacade:
    """
    Create an orchestrator with custom configuration.

    Replaces the global instance with a new one using the provided config.

    Args:
        config: Custom orchestrator configuration

    Returns:
        The new MasterOrchestratorFacade instance
    """
    global _orchestrator

    # Reset existing resources
    reset_orchestrator()

    # Create with custom config
    _orchestrator = MasterOrchestratorFacade(config=config)

    logger.info(
        "orchestrator_service_reconfigured",
        config={
            "lookback_bars": config.default_lookback_bars,
            "max_concurrent": config.max_concurrent_symbols,
            "cache_enabled": config.enable_caching,
        },
    )

    return _orchestrator
