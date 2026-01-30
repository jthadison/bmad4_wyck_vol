"""
Scanner API Routes (Story 19.4, Story 20.2)

Provides REST API endpoints for multi-symbol scanner status monitoring
and watchlist management.

Endpoints:
----------
GET /api/v1/scanner/status - Get overall scanner status with all symbols
GET /api/v1/scanner/symbols/{symbol}/status - Get status for a specific symbol
POST /api/v1/scanner/symbols/{symbol}/reset - Reset circuit breaker for a symbol

Watchlist Management (Story 20.2):
----------------------------------
GET /api/v1/scanner/watchlist - List all watchlist symbols
POST /api/v1/scanner/watchlist - Add symbol to watchlist
DELETE /api/v1/scanner/watchlist/{symbol} - Remove symbol from watchlist
PATCH /api/v1/scanner/watchlist/{symbol} - Update symbol (enabled flag)

Author: Story 19.4 (Multi-Symbol Concurrent Processing)
        Story 20.2 (Watchlist Management API)
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.scanner import ScannerStatusResponse, SymbolStatus
from src.models.scanner_persistence import (
    WatchlistSymbol,
    WatchlistSymbolCreate,
    WatchlistSymbolUpdate,
)
from src.pattern_engine.symbol_processor import get_multi_symbol_processor
from src.repositories.scanner_repository import ScannerRepository

logger = structlog.get_logger(__name__)

# Constants
MAX_WATCHLIST_SIZE = 50

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


# =========================================
# Watchlist Management Endpoints (Story 20.2)
# =========================================


def get_scanner_repository(
    session: AsyncSession = Depends(get_db),
) -> ScannerRepository:
    """
    Dependency to get ScannerRepository instance.

    Creates repository with injected database session.
    Session lifecycle is managed by the get_db dependency.

    Args:
        session: Database session from get_db dependency

    Returns:
        ScannerRepository instance with the provided session
    """
    return ScannerRepository(session)


@router.get(
    "/watchlist",
    response_model=list[WatchlistSymbol],
    summary="List Watchlist Symbols",
    description="Returns all symbols in the scanner watchlist, ordered by created_at descending.",
)
async def get_watchlist(
    repository: ScannerRepository = Depends(get_scanner_repository),
) -> list[WatchlistSymbol]:
    """
    Get all symbols in the scanner watchlist.

    Returns:
        List of WatchlistSymbol objects ordered by created_at descending (newest first)

    Example Response:
        [
            {
                "id": "uuid",
                "symbol": "EURUSD",
                "timeframe": "1H",
                "asset_class": "forex",
                "enabled": true,
                "last_scanned_at": null,
                "created_at": "2026-01-30T10:00:00Z"
            }
        ]
    """
    # Story 20.2: order by created_at descending (newest first)
    symbols = await repository.get_all_symbols(order_desc=True)

    logger.info("scanner_watchlist_retrieved", count=len(symbols))

    return symbols


@router.post(
    "/watchlist",
    response_model=WatchlistSymbol,
    status_code=http_status.HTTP_201_CREATED,
    summary="Add Symbol to Watchlist",
    description="Add a new symbol to the scanner watchlist.",
    responses={
        201: {"description": "Symbol created successfully"},
        400: {"description": "Watchlist limit reached"},
        409: {"description": "Symbol already exists"},
        422: {"description": "Validation error"},
    },
)
async def add_watchlist_symbol(
    request: WatchlistSymbolCreate,
    repository: ScannerRepository = Depends(get_scanner_repository),
) -> WatchlistSymbol:
    """
    Add a symbol to the scanner watchlist.

    Input is normalized:
    - Symbol is converted to uppercase
    - Timeframe is validated against allowed values
    - Asset class is validated against allowed values

    Args:
        request: WatchlistSymbolCreate with symbol, timeframe, asset_class

    Returns:
        Created WatchlistSymbol

    Raises:
        HTTPException 400: Watchlist limit reached (50 symbols)
        HTTPException 409: Symbol already exists in watchlist
        HTTPException 422: Validation error (invalid symbol, timeframe, or asset_class)
    """
    # Check watchlist size limit
    current_count = await repository.get_symbol_count()
    if current_count >= MAX_WATCHLIST_SIZE:
        logger.warning(
            "scanner_watchlist_limit_reached",
            current_count=current_count,
            limit=MAX_WATCHLIST_SIZE,
        )
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Watchlist limit of {MAX_WATCHLIST_SIZE} symbols reached",
        )

    try:
        # Add symbol (repository handles validation and normalization)
        symbol = await repository.add_symbol(
            symbol=request.symbol,
            timeframe=request.timeframe.value,
            asset_class=request.asset_class.value,
        )

        logger.info(
            "symbol_added_to_scanner_watchlist_via_api",
            symbol=symbol.symbol,
            timeframe=symbol.timeframe,
            asset_class=symbol.asset_class,
        )

        return symbol

    except ValueError as e:
        error_msg = str(e)

        if "already exists" in error_msg.lower():
            logger.warning(
                "scanner_watchlist_duplicate_symbol",
                symbol=request.symbol,
            )
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=f"Symbol {request.symbol.upper()} already exists in watchlist",
            ) from e

        # Re-raise as 422 for validation errors
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_msg,
        ) from e


@router.delete(
    "/watchlist/{symbol}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    summary="Remove Symbol from Watchlist",
    description="Remove a symbol from the scanner watchlist.",
    responses={
        204: {"description": "Symbol removed successfully"},
        404: {"description": "Symbol not found"},
    },
)
async def remove_watchlist_symbol(
    symbol: str = Path(
        ...,
        description="Symbol to remove (case-insensitive)",
        max_length=20,
    ),
    repository: ScannerRepository = Depends(get_scanner_repository),
) -> None:
    """
    Remove a symbol from the scanner watchlist.

    Args:
        symbol: Symbol to remove (normalized to uppercase)

    Returns:
        204 No Content on success

    Raises:
        HTTPException 404: Symbol not found in watchlist
    """
    removed = await repository.remove_symbol(symbol)

    if not removed:
        logger.warning(
            "scanner_watchlist_symbol_not_found_for_removal",
            symbol=symbol,
        )
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {symbol.upper()} not found in watchlist",
        )

    logger.info(
        "symbol_removed_from_scanner_watchlist_via_api",
        symbol=symbol.upper(),
    )


@router.patch(
    "/watchlist/{symbol}",
    response_model=WatchlistSymbol,
    summary="Update Watchlist Symbol",
    description="Update a symbol's enabled state in the scanner watchlist.",
    responses={
        200: {"description": "Symbol updated successfully"},
        404: {"description": "Symbol not found"},
    },
)
async def update_watchlist_symbol(
    request: WatchlistSymbolUpdate,
    symbol: str = Path(
        ...,
        description="Symbol to update (case-insensitive)",
        max_length=20,
    ),
    repository: ScannerRepository = Depends(get_scanner_repository),
) -> WatchlistSymbol:
    """
    Update a symbol's enabled state in the scanner watchlist.

    Args:
        symbol: Symbol to update (normalized to uppercase)
        request: WatchlistSymbolUpdate with enabled field

    Returns:
        Updated WatchlistSymbol

    Raises:
        HTTPException 404: Symbol not found in watchlist
    """
    updated = await repository.toggle_symbol_enabled(
        symbol=symbol,
        enabled=request.enabled,
    )

    if updated is None:
        logger.warning(
            "scanner_watchlist_symbol_not_found_for_update",
            symbol=symbol,
        )
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Symbol {symbol.upper()} not found in watchlist",
        )

    logger.info(
        "scanner_watchlist_symbol_updated_via_api",
        symbol=symbol.upper(),
        enabled=request.enabled,
    )

    return updated
