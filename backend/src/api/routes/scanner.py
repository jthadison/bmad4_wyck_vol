"""
Scanner API Routes (Story 19.4)

Provides REST API endpoints for multi-symbol scanner status monitoring.
Supports querying processing status, circuit breaker states, and latency metrics.

Endpoints:
----------
GET /api/v1/scanner/status - Get overall scanner status with all symbols
GET /api/v1/scanner/symbols/{symbol}/status - Get status for a specific symbol
POST /api/v1/scanner/symbols/{symbol}/reset - Reset circuit breaker for a symbol

Author: Story 19.4 (Multi-Symbol Concurrent Processing)
"""

import structlog
from fastapi import APIRouter, HTTPException
from fastapi import status as http_status

from src.models.scanner import ScannerStatusResponse, SymbolStatus
from src.pattern_engine.symbol_processor import get_multi_symbol_processor

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/scanner", tags=["scanner"])


@router.get(
    "/status",
    response_model=ScannerStatusResponse,
    summary="Get Scanner Status",
    description="Returns overall scanner health and status for all monitored symbols.",
)
async def get_scanner_status() -> ScannerStatusResponse:
    """
    Get overall scanner status.

    Returns status for all monitored symbols including:
    - Processing state (processing, paused, failed, idle)
    - Circuit breaker state (closed, open, half_open)
    - Average processing latency
    - Failure counts

    Returns:
        ScannerStatusResponse with overall health and per-symbol status

    Example Response:
        {
            "overall_status": "healthy",
            "symbols": [
                {
                    "symbol": "AAPL",
                    "state": "processing",
                    "last_processed": "2026-01-23T10:30:00Z",
                    "consecutive_failures": 0,
                    "circuit_state": "closed",
                    "avg_latency_ms": 45.2
                }
            ],
            "total_symbols": 10,
            "healthy_symbols": 9,
            "paused_symbols": 1,
            "failed_symbols": 0,
            "avg_latency_ms": 42.8,
            "is_running": true
        }
    """
    processor = get_multi_symbol_processor()

    if processor is None:
        logger.warning("scanner_not_initialized")
        return ScannerStatusResponse(
            overall_status="unhealthy",
            symbols=[],
            total_symbols=0,
            healthy_symbols=0,
            paused_symbols=0,
            failed_symbols=0,
            avg_latency_ms=0.0,
            is_running=False,
        )

    status = processor.get_status()
    logger.info(
        "scanner_status_queried",
        total_symbols=status.total_symbols,
        healthy_symbols=status.healthy_symbols,
        overall_status=status.overall_status,
    )

    return status


@router.get(
    "/symbols/{symbol}/status",
    response_model=SymbolStatus,
    summary="Get Symbol Status",
    description="Returns processing status for a specific symbol.",
)
async def get_symbol_status(symbol: str) -> SymbolStatus:
    """
    Get status for a specific symbol.

    Args:
        symbol: Symbol ticker (e.g., "AAPL", "TSLA")

    Returns:
        SymbolStatus for the requested symbol

    Raises:
        HTTPException 404: If symbol is not found
        HTTPException 503: If scanner is not initialized
    """
    processor = get_multi_symbol_processor()

    if processor is None:
        logger.warning("scanner_not_initialized")
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scanner not initialized",
        )

    status = processor.get_symbol_status(symbol.upper())

    if status is None:
        logger.warning("symbol_not_found", symbol=symbol)
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Symbol '{symbol}' not found in scanner",
        )

    logger.info(
        "symbol_status_queried",
        symbol=symbol,
        state=status.state,
        circuit_state=status.circuit_state,
    )

    return status


@router.post(
    "/symbols/{symbol}/reset",
    status_code=http_status.HTTP_204_NO_CONTENT,
    summary="Reset Symbol Circuit Breaker",
    description="Resets the circuit breaker for a symbol, restoring normal processing.",
)
async def reset_symbol_circuit_breaker(symbol: str) -> None:
    """
    Reset circuit breaker for a symbol.

    Forces the circuit breaker back to CLOSED state, allowing
    normal processing to resume. Use this after fixing the root
    cause of failures.

    Args:
        symbol: Symbol ticker to reset

    Raises:
        HTTPException 404: If symbol is not found
        HTTPException 503: If scanner is not initialized
    """
    processor = get_multi_symbol_processor()

    if processor is None:
        logger.warning("scanner_not_initialized")
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scanner not initialized",
        )

    success = await processor.reset_circuit_breaker(symbol.upper())

    if not success:
        logger.warning("symbol_not_found_for_reset", symbol=symbol)
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Symbol '{symbol}' not found in scanner",
        )

    logger.info("circuit_breaker_reset_via_api", symbol=symbol)
