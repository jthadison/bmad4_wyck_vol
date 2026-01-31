"""
Scanner API Routes (Story 19.4, Story 20.2, Story 20.5a, Story 21.3, Story 21.4)

Provides REST API endpoints for multi-symbol scanner status monitoring,
watchlist management, and scanner control.

Scanner Control (Story 20.5a):
------------------------------
POST /api/v1/scanner/start - Start the background scanner
POST /api/v1/scanner/stop - Stop the background scanner
GET /api/v1/scanner/status - Get current scanner control status
GET /api/v1/scanner/history - Get scan history records
PATCH /api/v1/scanner/config - Update scanner configuration

Processing Status (Story 19.4):
-------------------------------
GET /api/v1/scanner/processing/status - Get overall scanner status with all symbols
GET /api/v1/scanner/symbols/{symbol}/status - Get status for a specific symbol
POST /api/v1/scanner/symbols/{symbol}/reset - Reset circuit breaker for a symbol

Watchlist Management (Story 20.2, Story 21.3):
----------------------------------------------
GET /api/v1/scanner/watchlist - List all watchlist symbols
POST /api/v1/scanner/watchlist - Add symbol to watchlist (with validation)
DELETE /api/v1/scanner/watchlist/{symbol} - Remove symbol from watchlist
PATCH /api/v1/scanner/watchlist/{symbol} - Update symbol (enabled flag)

Symbol Validation (Story 21.3):
-------------------------------
GET /api/v1/scanner/symbols/validate - Validate a symbol without adding to watchlist

Symbol Search (Story 21.4):
---------------------------
GET /api/v1/scanner/symbols/search - Search for symbols by name or partial match

Author: Story 19.4 (Multi-Symbol Concurrent Processing)
        Story 20.2 (Watchlist Management API)
        Story 20.5a (Scanner Control API)
        Story 21.3 (Scanner Watchlist Validation Integration)
        Story 21.4 (Symbol Search & Autocomplete API)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.scanner import ScannerStatusResponse, SymbolStatus
from src.models.scanner_persistence import (
    ScanCycleStatus,
    ScannerActionResponse,
    ScannerConfig,
    ScannerConfigUpdate,
    ScannerConfigUpdateRequest,
    ScannerControlStatusResponse,
    ScannerHistoryResponse,
    WatchlistSymbol,
    WatchlistSymbolCreate,
    WatchlistSymbolUpdate,
)
from src.models.symbol_search import SymbolSearchResponse
from src.pattern_engine.symbol_processor import get_multi_symbol_processor
from src.repositories.scanner_repository import ScannerRepository
from src.services.symbol_search import SymbolSearchService
from src.services.symbol_suggester import SymbolSuggester
from src.services.symbol_validation_service import SymbolValidationService

if TYPE_CHECKING:
    from src.services.signal_scanner_service import SignalScannerService

logger = structlog.get_logger(__name__)

# Constants
MAX_WATCHLIST_SIZE = 50
MAX_HISTORY_LIMIT = 100
DEFAULT_HISTORY_LIMIT = 50

router = APIRouter(prefix="/api/v1/scanner", tags=["scanner"])

# =========================================
# Scanner Service Singleton (Story 20.5a)
# =========================================

_scanner_service: SignalScannerService | None = None


def set_scanner_service(service: SignalScannerService) -> None:
    """
    Set the global scanner service instance.

    Called during application startup to wire up the scanner service.

    Args:
        service: SignalScannerService instance to use
    """
    global _scanner_service
    _scanner_service = service
    logger.info("scanner_service_registered")


async def get_scanner_service() -> SignalScannerService:
    """
    Dependency to get the scanner service instance.

    Returns:
        SignalScannerService singleton

    Raises:
        HTTPException 503: If scanner service not initialized
    """
    if _scanner_service is None:
        logger.error("scanner_service_not_initialized")
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scanner service not initialized",
        )
    return _scanner_service


# =========================================
# Symbol Validation Service (Story 21.3)
# =========================================

_validation_service: SymbolValidationService | None = None
_symbol_suggester: SymbolSuggester | None = None
_search_service: SymbolSearchService | None = None


def set_validation_service(service: SymbolValidationService) -> None:
    """
    Set the global validation service instance.

    Called during application startup.

    Args:
        service: SymbolValidationService instance to use
    """
    global _validation_service
    _validation_service = service
    logger.info("validation_service_registered")


def set_symbol_suggester(suggester: SymbolSuggester) -> None:
    """
    Set the global symbol suggester instance.

    Called during application startup.

    Args:
        suggester: SymbolSuggester instance to use
    """
    global _symbol_suggester
    _symbol_suggester = suggester
    logger.info("symbol_suggester_registered")


def get_validation_service() -> SymbolValidationService | None:
    """
    Get the validation service instance.

    Returns:
        SymbolValidationService singleton, or None if not configured
    """
    return _validation_service


def get_symbol_suggester() -> SymbolSuggester:
    """
    Get the symbol suggester instance.

    Returns:
        SymbolSuggester singleton

    Note:
        If not set, creates a default instance.
    """
    global _symbol_suggester
    if _symbol_suggester is None:
        _symbol_suggester = SymbolSuggester()
    return _symbol_suggester


def set_search_service(service: SymbolSearchService) -> None:
    """
    Set the global search service instance (Story 21.4).

    Called during application startup.

    Args:
        service: SymbolSearchService instance to use
    """
    global _search_service
    _search_service = service
    logger.info("search_service_registered")


def get_search_service() -> SymbolSearchService | None:
    """
    Get the search service instance (Story 21.4).

    Returns:
        SymbolSearchService singleton, or None if not configured
    """
    return _search_service


def _get_source_value(source) -> str:
    """
    Extract string value from validation source (may be enum or string).

    Args:
        source: SymbolValidationSource enum or string value

    Returns:
        String representation of the source
    """
    return source.value if hasattr(source, "value") else source


# =========================================
# Scanner Control Endpoints (Story 20.5a)
# =========================================


@router.post(
    "/start",
    response_model=ScannerActionResponse,
    summary="Start Scanner",
    description="Start the background signal scanner.",
)
async def start_scanner(
    scanner: SignalScannerService = Depends(get_scanner_service),
) -> ScannerActionResponse:
    """
    Start the background signal scanner (Story 20.5a AC1).

    Idempotent: Returns success if scanner is already running.

    Returns:
        ScannerActionResponse with status and message
    """
    if scanner.is_running:
        logger.info("scanner_start_requested_already_running")
        return ScannerActionResponse(
            status="already_running",
            message="Scanner is already running",
            is_running=True,
        )

    await scanner.start()

    logger.info("scanner_started_via_api")

    return ScannerActionResponse(
        status="started",
        message="Scanner started successfully",
        is_running=True,
    )


@router.post(
    "/stop",
    response_model=ScannerActionResponse,
    summary="Stop Scanner",
    description="Stop the background signal scanner.",
)
async def stop_scanner(
    scanner: SignalScannerService = Depends(get_scanner_service),
) -> ScannerActionResponse:
    """
    Stop the background signal scanner (Story 20.5a AC2).

    Idempotent: Returns success if scanner is already stopped.

    Returns:
        ScannerActionResponse with status and message
    """
    if not scanner.is_running:
        logger.info("scanner_stop_requested_already_stopped")
        return ScannerActionResponse(
            status="already_stopped",
            message="Scanner is already stopped",
            is_running=False,
        )

    await scanner.stop()

    logger.info("scanner_stopped_via_api")

    return ScannerActionResponse(
        status="stopped",
        message="Scanner stopped successfully",
        is_running=False,
    )


def _get_scanner_repository_dep(
    session: AsyncSession = Depends(get_db),
) -> ScannerRepository:
    """
    Dependency to get ScannerRepository for scanner control endpoints.

    Args:
        session: Database session from get_db dependency

    Returns:
        ScannerRepository instance
    """
    return ScannerRepository(session)


@router.get(
    "/status",
    response_model=ScannerControlStatusResponse,
    summary="Get Scanner Control Status",
    description="Returns current scanner control status including timing and configuration.",
)
async def get_scanner_control_status(
    scanner: SignalScannerService = Depends(get_scanner_service),
    repository: ScannerRepository = Depends(_get_scanner_repository_dep),
) -> ScannerControlStatusResponse:
    """
    Get scanner control status (Story 20.5a AC3).

    Returns current state, timing information, and configuration.

    Returns:
        ScannerControlStatusResponse with status details
    """
    # Get status from scanner service
    status = scanner.get_status()

    # Get config from repository for session_filter_enabled
    config = await repository.get_config()

    # Get enabled symbol count
    symbols_count = await repository.get_symbol_count()

    logger.info(
        "scanner_control_status_queried",
        is_running=status.is_running,
        current_state=status.current_state,
    )

    return ScannerControlStatusResponse(
        is_running=status.is_running,
        current_state=status.current_state,
        last_cycle_at=status.last_cycle_at,
        next_scan_in_seconds=status.next_scan_in_seconds,
        symbols_count=symbols_count,
        scan_interval_seconds=status.scan_interval_seconds,
        session_filter_enabled=config.session_filter_enabled,
    )


@router.get(
    "/history",
    response_model=list[ScannerHistoryResponse],
    summary="Get Scan History",
    description="Returns scan cycle history records.",
)
async def get_scanner_history(
    limit: int = Query(
        default=DEFAULT_HISTORY_LIMIT,
        ge=1,
        le=MAX_HISTORY_LIMIT,
        description="Maximum number of records to return (1-100)",
    ),
    repository: ScannerRepository = Depends(_get_scanner_repository_dep),
) -> list[ScannerHistoryResponse]:
    """
    Get scan cycle history (Story 20.5a AC4).

    Returns history records ordered by cycle_started_at descending.

    Args:
        limit: Maximum records to return (default 50, max 100)

    Returns:
        List of ScannerHistoryResponse records
    """
    history = await repository.get_history(limit=limit)

    logger.info("scanner_history_queried", count=len(history), limit=limit)

    return [
        ScannerHistoryResponse(
            id=h.id,
            cycle_started_at=h.cycle_started_at,
            cycle_ended_at=h.cycle_ended_at,
            symbols_scanned=h.symbols_scanned,
            signals_generated=h.signals_generated,
            errors_count=h.errors_count,
            status=h.status.value if isinstance(h.status, ScanCycleStatus) else str(h.status),
        )
        for h in history
    ]


@router.patch(
    "/config",
    response_model=ScannerConfig,
    summary="Update Scanner Configuration",
    description="Update scanner configuration. Scanner must be stopped.",
    responses={
        200: {"description": "Configuration updated successfully"},
        409: {"description": "Scanner is running - stop it first"},
        422: {"description": "Validation error"},
    },
)
async def update_scanner_config(
    request: ScannerConfigUpdateRequest,
    scanner: SignalScannerService = Depends(get_scanner_service),
    repository: ScannerRepository = Depends(_get_scanner_repository_dep),
) -> ScannerConfig:
    """
    Update scanner configuration (Story 20.5a AC5, AC6).

    Scanner must be stopped before configuration can be modified.

    Args:
        request: Configuration fields to update

    Returns:
        Updated ScannerConfig

    Raises:
        HTTPException 409: If scanner is running
        HTTPException 422: If validation fails
    """
    # Story 20.5a AC5: Reject if scanner is running
    if scanner.is_running:
        logger.warning("scanner_config_update_rejected_running")
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="Cannot modify configuration while scanner is running. Stop scanner first.",
        )

    # Convert to internal update model
    updates = ScannerConfigUpdate(
        scan_interval_seconds=request.scan_interval_seconds,
        batch_size=request.batch_size,
        session_filter_enabled=request.session_filter_enabled,
    )

    config = await repository.update_config(updates)

    logger.info(
        "scanner_config_updated_via_api",
        scan_interval_seconds=request.scan_interval_seconds,
        batch_size=request.batch_size,
        session_filter_enabled=request.session_filter_enabled,
    )

    return config


# =========================================
# Processing Status Endpoints (Story 19.4)
# =========================================


@router.get(
    "/processing/status",
    response_model=ScannerStatusResponse,
    summary="Get Processing Status",
    description="Returns overall scanner health and status for all monitored symbols.",
)
async def get_scanner_processing_status() -> ScannerStatusResponse:
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
async def reset_symbol_circuit_breaker(symbol: str):
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
    description="Add a new symbol to the scanner watchlist with validation (Story 21.3).",
    responses={
        201: {"description": "Symbol created successfully"},
        400: {"description": "Watchlist limit reached"},
        409: {"description": "Symbol already exists"},
        422: {"description": "Validation error - invalid symbol or asset class mismatch"},
    },
)
async def add_watchlist_symbol(
    request: WatchlistSymbolCreate,
    response: Response,
    repository: ScannerRepository = Depends(get_scanner_repository),
) -> WatchlistSymbol:
    """
    Add a symbol to the scanner watchlist (Story 20.2, Story 21.3).

    Story 21.3: Validates symbol against market data before adding.

    Input is normalized:
    - Symbol is converted to uppercase
    - Timeframe is validated against allowed values
    - Asset class is validated against allowed values

    Validation (Story 21.3):
    - Symbol is validated against TwelveData (forex, index, crypto) or Alpaca (stock)
    - Invalid symbols return 422 with suggestions for typo corrections
    - Asset class mismatches return 422 with actual type

    Response Headers:
    - X-Validation-Source: api, cache, or static (indicates validation source)

    Args:
        request: WatchlistSymbolCreate with symbol, timeframe, asset_class

    Returns:
        Created WatchlistSymbol

    Raises:
        HTTPException 400: Watchlist limit reached (50 symbols)
        HTTPException 409: Symbol already exists in watchlist
        HTTPException 422: Validation error (invalid symbol, asset class mismatch)
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

    # Story 21.3: Validate symbol before adding
    validation_service = get_validation_service()
    suggester = get_symbol_suggester()

    if validation_service is not None:
        result = await validation_service.validate_symbol(
            request.symbol,
            request.asset_class.value,
        )

        # Add validation source header
        # Note: source may be a string or enum depending on model config
        source_value = _get_source_value(result.source)
        response.headers["X-Validation-Source"] = source_value

        if not result.valid:
            # Get suggestions for invalid symbol
            suggestions = suggester.get_suggestions(
                request.symbol,
                request.asset_class.value,
            )

            # Check for asset class mismatch - symbol exists but in different class
            # First check if validation service returned info (mismatch detected by service)
            actual_type = None
            if result.info and result.info.type != request.asset_class.value:
                actual_type = result.info.type
            else:
                # Service didn't find it - check static lists for cross-asset-class match
                from src.data.static_symbols import get_symbol_info_from_static

                other_classes = ["forex", "index", "crypto", "stock"]
                for other_class in other_classes:
                    if other_class != request.asset_class.value:
                        info = get_symbol_info_from_static(request.symbol, other_class)
                        if info:
                            actual_type = info["type"]
                            break

            if actual_type:
                logger.warning(
                    "symbol_asset_class_mismatch",
                    symbol=request.symbol,
                    requested=request.asset_class.value,
                    actual=actual_type,
                )
                raise HTTPException(
                    status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "detail": f"Symbol {request.symbol.upper()} is a {actual_type}, not a {request.asset_class.value}",
                        "code": "ASSET_CLASS_MISMATCH",
                        "symbol": request.symbol.upper(),
                        "asset_class": request.asset_class.value,
                        "actual_asset_class": actual_type,
                    },
                )

            # Build error message with suggestions
            suggestion_text = ""
            if suggestions:
                suggestion_text = f" Did you mean {suggestions[0]}?"

            logger.warning(
                "invalid_symbol_rejected",
                symbol=request.symbol,
                asset_class=request.asset_class.value,
                suggestions=suggestions,
            )

            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "detail": f"Invalid symbol: {request.symbol.upper()} not found.{suggestion_text}",
                    "code": "INVALID_SYMBOL",
                    "symbol": request.symbol.upper(),
                    "asset_class": request.asset_class.value,
                    "suggestions": suggestions,
                },
            )
    else:
        # No validation service configured - use static as fallback source
        response.headers["X-Validation-Source"] = "static"

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
):
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


# =========================================
# Symbol Validation Endpoint (Story 21.3)
# =========================================


@router.get(
    "/symbols/validate",
    summary="Validate Symbol",
    description="Validate a symbol without adding to watchlist (Story 21.3 AC6).",
    responses={
        200: {"description": "Validation result with symbol info or error"},
    },
)
async def validate_symbol(
    symbol: str = Query(
        ...,
        description="Symbol to validate (e.g., EURUSD, AAPL)",
        max_length=20,
    ),
    asset_class: str = Query(
        ...,
        description="Asset class (forex, index, crypto, stock)",
        max_length=10,
    ),
) -> dict:
    """
    Validate a symbol without adding to watchlist (Story 21.3 AC6).

    Useful for checking if a symbol is valid before attempting to add it.
    Returns detailed information about valid symbols, or error with
    suggestions for invalid symbols.

    Args:
        symbol: Symbol to validate
        asset_class: Asset class to validate against

    Returns:
        dict: Validation result:
            - valid: True if symbol is valid
            - symbol: The validated symbol (normalized)
            - name: Full instrument name (if valid)
            - exchange: Exchange or market (if valid)
            - type: Asset type (if valid)
            - source: Validation source (api, cache, static)
            - error: Error message (if invalid)
            - suggestions: Similar symbols (if invalid)
    """
    validation_service = get_validation_service()
    suggester = get_symbol_suggester()

    # Normalize inputs
    symbol_upper = symbol.upper().strip()
    asset_class_lower = asset_class.lower().strip()

    # Validate asset class
    valid_asset_classes = {"forex", "index", "crypto", "stock"}
    if asset_class_lower not in valid_asset_classes:
        return {
            "valid": False,
            "symbol": symbol_upper,
            "error": f"Invalid asset class. Must be one of: {', '.join(valid_asset_classes)}",
            "suggestions": [],
        }

    if validation_service is not None:
        result = await validation_service.validate_symbol(symbol_upper, asset_class_lower)

        # Note: source may be a string or enum depending on model config
        source_value = _get_source_value(result.source)

        if result.valid:
            logger.info(
                "symbol_validated_successfully",
                symbol=symbol_upper,
                asset_class=asset_class_lower,
                source=source_value,
            )
            return {
                "valid": True,
                "symbol": result.symbol,
                "name": result.info.name if result.info else None,
                "exchange": result.info.exchange if result.info else None,
                "type": result.info.type if result.info else None,
                "source": source_value,
            }
        else:
            suggestions = suggester.get_suggestions(symbol_upper, asset_class_lower)
            logger.info(
                "symbol_validation_failed",
                symbol=symbol_upper,
                asset_class=asset_class_lower,
                error=result.error,
                suggestions=suggestions,
            )
            return {
                "valid": False,
                "symbol": symbol_upper,
                "error": result.error or f"Symbol {symbol_upper} not found",
                "suggestions": suggestions,
            }
    else:
        # No validation service - check static lists
        from src.data.static_symbols import get_symbol_info_from_static, is_known_symbol

        if is_known_symbol(symbol_upper, asset_class_lower):
            info = get_symbol_info_from_static(symbol_upper, asset_class_lower)
            return {
                "valid": True,
                "symbol": symbol_upper,
                "name": info["name"] if info else symbol_upper,
                "exchange": info["exchange"] if info else asset_class_lower.upper(),
                "type": info["type"] if info else asset_class_lower,
                "source": "static",
            }
        else:
            suggestions = suggester.get_suggestions(symbol_upper, asset_class_lower)
            return {
                "valid": False,
                "symbol": symbol_upper,
                "error": f"Symbol {symbol_upper} not found",
                "suggestions": suggestions,
            }


# =========================================
# Symbol Search Endpoint (Story 21.4)
# =========================================


@router.get(
    "/symbols/search",
    response_model=list[SymbolSearchResponse],
    summary="Search Symbols",
    description="Search for symbols by name or ticker (Story 21.4).",
    responses={
        200: {"description": "List of matching symbols sorted by relevance"},
        422: {"description": "Validation error (query too short/long)"},
        503: {"description": "Search service not available"},
    },
)
async def search_symbols(
    q: str = Query(
        ...,
        min_length=2,
        max_length=20,
        description="Search query (2-20 characters)",
    ),
    type: str | None = Query(
        None,
        description="Asset type filter (forex, crypto, index, stock)",
    ),
    limit: int = Query(
        10,
        ge=1,
        le=50,
        description="Maximum results (1-50, default 10)",
    ),
) -> list[SymbolSearchResponse]:
    """
    Search for symbols by name or ticker (Story 21.4).

    Returns matching symbols sorted by relevance:
    - Exact symbol matches first
    - Symbol prefix matches
    - Name substring matches

    Searches across forex, crypto, and indices by default.
    Use the `type` parameter to filter by asset class.

    Args:
        q: Search query (2-20 characters)
        type: Optional asset type filter (forex, crypto, index, stock)
        limit: Maximum results to return (default 10, max 50)

    Returns:
        List of SymbolSearchResponse sorted by relevance

    Raises:
        HTTPException 422: Query too short/long or invalid type
        HTTPException 503: Search service not configured
    """
    search_service = get_search_service()

    if search_service is None:
        logger.warning("search_service_not_configured")
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service not available",
        )

    # Validate type if provided
    valid_types = {"forex", "crypto", "index", "stock"}
    if type and type.lower() not in valid_types:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid type. Must be one of: {', '.join(valid_types)}",
        )

    # Normalize type
    normalized_type = type.lower() if type else None

    results = await search_service.search(
        query=q.strip(),
        asset_type=normalized_type,
        limit=limit,
    )

    logger.info(
        "symbol_search_api_completed",
        query=q,
        type=normalized_type,
        limit=limit,
        count=len(results),
    )

    return results
