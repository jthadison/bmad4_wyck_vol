"""
Orchestrator API Routes.

Provides REST endpoints for orchestrator health checks and signal generation.

Story 8.1: Master Orchestrator Architecture (AC: 7)
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.orchestrator.service import (
    analyze_symbol,
    analyze_symbols,
    get_orchestrator_health,
)

router = APIRouter(
    prefix="/api/v1/orchestrator",
    tags=["orchestrator"],
    responses={
        500: {"description": "Internal server error"},
    },
)


class TradeSignalResponse(BaseModel):
    """Response model for trade signals."""

    signal_id: str
    symbol: str
    timeframe: str
    pattern_type: str
    phase: str
    entry_price: str
    stop_price: str
    target_price: str
    position_size: int
    risk_amount: str
    r_multiple: str
    confidence_score: int

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "signal_id": "550e8400-e29b-41d4-a716-446655440000",
                "symbol": "AAPL",
                "timeframe": "1d",
                "pattern_type": "SPRING",
                "phase": "C",
                "entry_price": "150.00",
                "stop_price": "145.00",
                "target_price": "170.00",
                "position_size": 100,
                "risk_amount": "500.00",
                "r_multiple": "4.0",
                "confidence_score": 85,
            }
        }


class AnalyzeRequest(BaseModel):
    """Request model for symbol analysis."""

    symbols: list[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of symbols to analyze",
    )
    timeframe: str = Field(
        default="1d",
        description="Bar timeframe",
        pattern="^(1m|5m|15m|30m|1h|4h|1d|1w)$",
    )


class AnalyzeResponse(BaseModel):
    """Response model for symbol analysis."""

    signals: dict[str, list[TradeSignalResponse]]
    total_signals: int
    symbols_analyzed: int


class OrchestratorHealthResponse(BaseModel):
    """Response model for orchestrator health."""

    status: str
    components: dict[str, Any]
    metrics: dict[str, Any]


@router.get("/health", response_model=OrchestratorHealthResponse)
async def orchestrator_health() -> OrchestratorHealthResponse:
    """
    Get orchestrator health status.

    Returns comprehensive health information including:
    - Overall status (healthy/degraded/unhealthy)
    - Component health (cache, event_bus, container)
    - Operational metrics (analysis_count, signal_count, error_count)

    Returns:
        OrchestratorHealthResponse with health details
    """
    try:
        health = get_orchestrator_health()
        return OrchestratorHealthResponse(**health)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get orchestrator health: {str(e)}",
        ) from e


@router.get("/analyze/{symbol}", response_model=list[TradeSignalResponse])
async def analyze_single_symbol(
    symbol: str,
    timeframe: str = Query(
        default="1d",
        pattern="^(1m|5m|15m|30m|1h|4h|1d|1w)$",
        description="Bar timeframe",
    ),
) -> list[TradeSignalResponse]:
    """
    Analyze a single symbol for Wyckoff patterns and trade signals.

    Runs the full 7-stage pipeline:
    1. Data ingestion (fetch bars)
    2. Volume analysis
    3. Trading range detection
    4. Phase classification
    5. Pattern detection (Spring, SOS, LPS)
    6. Risk validation
    7. Signal generation

    Args:
        symbol: Stock symbol to analyze (e.g., "AAPL")
        timeframe: Bar timeframe (default: "1d")

    Returns:
        List of generated trade signals for the symbol

    Raises:
        HTTPException: If analysis fails
    """
    try:
        signals = await analyze_symbol(symbol.upper(), timeframe)

        return [
            TradeSignalResponse(
                signal_id=str(signal.signal_id),
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                pattern_type=signal.pattern_type,
                phase=signal.phase,
                entry_price=str(signal.entry_price),
                stop_price=str(signal.stop_price),
                target_price=str(signal.target_price),
                position_size=signal.position_size,
                risk_amount=str(signal.risk_amount),
                r_multiple=str(signal.r_multiple),
                confidence_score=signal.confidence_score,
            )
            for signal in signals
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed for {symbol}: {str(e)}",
        ) from e


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_multiple_symbols(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Analyze multiple symbols for Wyckoff patterns and trade signals.

    Processes symbols in parallel for efficiency. Each symbol goes through
    the full 7-stage analysis pipeline.

    Args:
        request: AnalyzeRequest with symbols and timeframe

    Returns:
        AnalyzeResponse with signals grouped by symbol

    Raises:
        HTTPException: If analysis fails
    """
    try:
        symbols = [s.upper() for s in request.symbols]
        results = await analyze_symbols(symbols, request.timeframe)

        # Convert to response format
        signals_response: dict[str, list[TradeSignalResponse]] = {}
        total_signals = 0

        for symbol, signals in results.items():
            signals_response[symbol] = [
                TradeSignalResponse(
                    signal_id=str(signal.signal_id),
                    symbol=signal.symbol,
                    timeframe=signal.timeframe,
                    pattern_type=signal.pattern_type,
                    phase=signal.phase,
                    entry_price=str(signal.entry_price),
                    stop_price=str(signal.stop_price),
                    target_price=str(signal.target_price),
                    position_size=signal.position_size,
                    risk_amount=str(signal.risk_amount),
                    r_multiple=str(signal.r_multiple),
                    confidence_score=signal.confidence_score,
                )
                for signal in signals
            ]
            total_signals += len(signals)

        return AnalyzeResponse(
            signals=signals_response,
            total_signals=total_signals,
            symbols_analyzed=len(results),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Batch analysis failed: {str(e)}",
        ) from e


@router.get("/cache/stats")
async def get_cache_stats() -> dict[str, Any]:
    """
    Get cache statistics.

    Returns cache metrics including hit rate, size, and access patterns.

    Returns:
        Dictionary with cache statistics
    """
    try:
        health = get_orchestrator_health()
        return health.get("components", {}).get("cache", {"error": "Not available"})
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get cache stats: {str(e)}",
        ) from e


@router.post("/cache/invalidate/{symbol}")
async def invalidate_symbol_cache(
    symbol: str,
    timeframe: str = Query(
        default="1d",
        pattern="^(1m|5m|15m|30m|1h|4h|1d|1w)$",
        description="Bar timeframe",
    ),
) -> dict[str, Any]:
    """
    Invalidate cache for a specific symbol.

    Removes all cached data for the symbol/timeframe combination,
    forcing fresh analysis on next request.

    Args:
        symbol: Symbol to invalidate
        timeframe: Timeframe to invalidate

    Returns:
        Confirmation with number of entries invalidated
    """
    try:
        from src.orchestrator.cache import get_orchestrator_cache

        cache = get_orchestrator_cache()
        count = cache.invalidate_symbol(symbol.upper(), timeframe)

        return {
            "message": f"Cache invalidated for {symbol.upper()}/{timeframe}",
            "entries_removed": count,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Cache invalidation failed: {str(e)}",
        ) from e
