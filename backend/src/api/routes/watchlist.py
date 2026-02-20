"""
Watchlist API Routes (Story 19.12)

Purpose:
--------
REST API endpoints for user watchlist management.
Enables users to configure which symbols the system monitors.

Endpoints:
----------
GET    /api/v1/watchlist           - Get user's watchlist
GET    /api/v1/watchlist/status    - Get enriched Wyckoff status per symbol (Feature 6)
POST   /api/v1/watchlist           - Add symbol to watchlist
DELETE /api/v1/watchlist/{symbol}  - Remove symbol from watchlist
PATCH  /api/v1/watchlist/{symbol}  - Update symbol settings

Features:
---------
- Max 100 symbols per user
- Symbol validation against Alpaca
- Default watchlist initialization for new users
- Subscription sync with market data feed

Author: Story 19.12
"""

import random
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi import status as http_status

from src.database import async_session_maker
from src.models.watchlist import (
    AddSymbolRequest,
    OHLCVBar,
    UpdateSymbolRequest,
    WatchlistEntry,
    WatchlistResponse,
    WatchlistStatusResponse,
    WatchlistSymbolStatus,
)
from src.repositories.watchlist_repository import WatchlistRepository
from src.services.watchlist_service import WatchlistService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/watchlist", tags=["watchlist"])


# Dependency to get current user ID
# SECURITY: DO NOT DEPLOY - Requires auth integration (Story 11.7)
# This hardcoded ID means all users share the same watchlist with no authorization.
# TODO: Replace with actual JWT token validation from auth middleware.
async def get_current_user_id() -> UUID:
    """
    Get current authenticated user ID.

    SECURITY WARNING: This is a hardcoded test user ID.
    DO NOT use in production - requires auth integration (Story 11.7).

    Returns:
        Hardcoded test user UUID
    """
    return UUID("00000000-0000-0000-0000-000000000001")


async def get_watchlist_service() -> AsyncGenerator[WatchlistService, None]:
    """
    Dependency to get watchlist service instance.

    Creates repository with database session and initializes service.
    Session is properly managed via async context manager.

    Yields:
        WatchlistService instance with active database session
    """
    async with async_session_maker() as session:
        repository = WatchlistRepository(session)

        # Try to get market data coordinator if available
        market_data = None
        try:
            from src.api.main import _coordinator

            market_data = _coordinator
        except ImportError:
            pass

        yield WatchlistService(
            repository=repository,
            market_data_coordinator=market_data,
        )


@router.get(
    "",
    response_model=WatchlistResponse,
    summary="Get user's watchlist",
    description="Retrieve all symbols in user's watchlist. Initializes default watchlist for new users.",
)
async def get_watchlist(
    user_id: UUID = Depends(get_current_user_id),
    service: WatchlistService = Depends(get_watchlist_service),
) -> WatchlistResponse:
    """
    Get user's watchlist.

    Returns all watchlist entries for the authenticated user.
    If user has no watchlist, initializes with default symbols:
    AAPL, TSLA, SPY, QQQ, NVDA, MSFT, AMZN

    Returns:
        WatchlistResponse with symbols, count, and max_allowed

    Example Response:
        {
            "symbols": [
                {"symbol": "AAPL", "priority": "high", ...},
                {"symbol": "TSLA", "priority": "medium", ...}
            ],
            "count": 2,
            "max_allowed": 100
        }
    """
    try:
        response = await service.get_watchlist(user_id)

        logger.info(
            "watchlist_retrieved",
            user_id=str(user_id),
            count=response.count,
        )

        return response

    except Exception as e:
        logger.error(
            "watchlist_retrieval_failed",
            user_id=str(user_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve watchlist",
        ) from e


@router.get(
    "/status",
    response_model=WatchlistStatusResponse,
    summary="Get Wyckoff status for watchlist symbols",
    description=(
        "Returns enriched Wyckoff phase, pattern, sparkline, and cause-building "
        "progress for every symbol in the user's watchlist. Used by the dashboard card view."
    ),
)
async def get_watchlist_status(
    user_id: UUID = Depends(get_current_user_id),
    service: WatchlistService = Depends(get_watchlist_service),
) -> WatchlistStatusResponse:
    """
    Get Wyckoff dashboard status for all watchlist symbols.

    For each symbol the response includes:
    - current_phase (A/B/C/D/E) with confidence
    - active_pattern (Spring / SOS / UTAD / LPS / SC / AR) with confidence
    - cause_progress_pct (0-100)
    - recent_bars (last 8 OHLCV bars) for sparkline rendering
    - trend_direction (up / down / sideways)

    NOTE: When a live pattern-engine integration is not yet available this
    endpoint returns deterministic mock data derived from the symbol name so
    the API contract and UI can be developed and tested independently.

    Returns:
        WatchlistStatusResponse

    Raises:
        500: Internal server error
    """
    try:
        watchlist = await service.get_watchlist(user_id)

        statuses: list[WatchlistSymbolStatus] = []
        for entry in watchlist.symbols:
            statuses.append(_build_mock_status(entry.symbol))

        logger.info(
            "watchlist_status_retrieved",
            user_id=str(user_id),
            count=len(statuses),
        )

        return WatchlistStatusResponse(symbols=statuses)

    except Exception as e:
        logger.error(
            "watchlist_status_failed",
            user_id=str(user_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve watchlist status",
        ) from e


# ---------------------------------------------------------------------------
# Mock status builder
# ---------------------------------------------------------------------------
# Phases, patterns, and progress are derived deterministically from the symbol
# string so results are stable between calls (good for UI development/tests)
# while still covering the full range of possible values.
# ---------------------------------------------------------------------------

_PHASES = ["A", "B", "C", "D", "E"]
_PATTERNS: list[str | None] = ["Spring", "SOS", "UTAD", "LPS", "SC", "AR", None]
_DIRECTIONS = ["up", "down", "sideways"]


def _build_mock_status(symbol: str) -> WatchlistSymbolStatus:
    """Build a deterministic mock WatchlistSymbolStatus for a given symbol."""
    # Seed from symbol so output is stable
    seed = sum(ord(c) for c in symbol)

    phase = _PHASES[seed % len(_PHASES)]
    pattern = _PATTERNS[seed % len(_PATTERNS)]
    trend = _DIRECTIONS[(seed // 3) % len(_DIRECTIONS)]

    phase_confidence = round(0.50 + (seed % 47) / 100, 2)
    pattern_confidence = round(0.60 + (seed % 38) / 100, 2) if pattern else None
    cause_progress = round(float((seed * 7) % 100), 1)

    # Generate 8 bars of plausible OHLCV data
    base_price = 100.0 + (seed % 400)
    bars: list[OHLCVBar] = []
    rng = random.Random(seed)  # noqa: S311  (deterministic mock, not crypto)
    price = base_price
    for _ in range(8):
        move = rng.uniform(-2.0, 2.0)
        open_ = round(price, 2)
        close = round(price + move, 2)
        high = round(max(open_, close) + abs(rng.uniform(0, 1.0)), 2)
        low = round(min(open_, close) - abs(rng.uniform(0, 1.0)), 2)
        volume = round(base_price * 1_000 * rng.uniform(0.5, 2.0))
        bars.append(OHLCVBar(o=open_, h=high, low=low, c=close, v=volume))
        price = close

    # Wyckoff phase determines the trend override
    if phase in ("D", "E"):
        trend = "up"
    elif phase == "A":
        trend = "down"

    return WatchlistSymbolStatus(
        symbol=symbol,
        current_phase=phase,
        phase_confidence=phase_confidence,
        active_pattern=pattern,
        pattern_confidence=pattern_confidence,
        cause_progress_pct=cause_progress,
        recent_bars=bars,
        trend_direction=trend,
        last_updated=datetime.now(UTC),
    )


@router.post(
    "",
    response_model=WatchlistEntry,
    status_code=http_status.HTTP_201_CREATED,
    summary="Add symbol to watchlist",
    description="Add a new symbol to user's watchlist. Validates symbol against Alpaca.",
)
async def add_symbol(
    request: AddSymbolRequest,
    user_id: UUID = Depends(get_current_user_id),
    service: WatchlistService = Depends(get_watchlist_service),
) -> WatchlistEntry:
    """
    Add a symbol to user's watchlist.

    Validates symbol against Alpaca asset list before adding.
    Triggers subscription sync with market data feed.

    Args:
        request: AddSymbolRequest with symbol, priority, min_confidence

    Returns:
        Created WatchlistEntry

    Raises:
        400: Symbol already in watchlist
        400: Watchlist limit reached (100 symbols)
        404: Symbol not found in Alpaca
        500: Internal server error

    Example Request:
        POST /api/v1/watchlist
        {"symbol": "GOOGL", "priority": "medium", "min_confidence": null}

    Example Response:
        201 Created
        {"symbol": "GOOGL", "priority": "medium", "min_confidence": null, ...}
    """
    try:
        entry = await service.add_symbol(
            user_id=user_id,
            symbol=request.symbol,
            priority=request.priority,
            min_confidence=request.min_confidence,
            validate=True,
        )

        logger.info(
            "symbol_added_to_watchlist",
            user_id=str(user_id),
            symbol=request.symbol,
        )

        return entry

    except ValueError as e:
        error_msg = str(e)

        if "not found" in error_msg.lower():
            logger.warning(
                "symbol_not_found",
                user_id=str(user_id),
                symbol=request.symbol,
            )
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Symbol {request.symbol} not found",
            ) from e

        if "limit" in error_msg.lower():
            logger.warning(
                "watchlist_limit_reached",
                user_id=str(user_id),
            )
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Watchlist limit reached (100 symbols)",
            ) from e

        if "already" in error_msg.lower():
            logger.warning(
                "symbol_already_exists",
                user_id=str(user_id),
                symbol=request.symbol,
            )
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Symbol {request.symbol} already in watchlist",
            ) from e

        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        ) from e

    except Exception as e:
        logger.error(
            "add_symbol_failed",
            user_id=str(user_id),
            symbol=request.symbol,
            error=str(e),
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add symbol to watchlist",
        ) from e


@router.delete(
    "/{symbol}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    summary="Remove symbol from watchlist",
    description="Remove a symbol from user's watchlist.",
)
async def remove_symbol(
    symbol: str = Path(..., description="Symbol to remove", max_length=10),
    user_id: UUID = Depends(get_current_user_id),
    service: WatchlistService = Depends(get_watchlist_service),
) -> None:
    """
    Remove a symbol from user's watchlist.

    Triggers unsubscribe from market data feed for the symbol.

    Args:
        symbol: Symbol to remove (path parameter)

    Returns:
        204 No Content on success

    Raises:
        404: Symbol not found in watchlist
        500: Internal server error

    Example:
        DELETE /api/v1/watchlist/SPY
        Response: 204 No Content
    """
    try:
        removed = await service.remove_symbol(user_id, symbol)

        if not removed:
            logger.warning(
                "symbol_not_in_watchlist",
                user_id=str(user_id),
                symbol=symbol,
            )
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Symbol {symbol.upper()} not found in watchlist",
            )

        logger.info(
            "symbol_removed_from_watchlist",
            user_id=str(user_id),
            symbol=symbol,
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "remove_symbol_failed",
            user_id=str(user_id),
            symbol=symbol,
            error=str(e),
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove symbol from watchlist",
        ) from e


@router.patch(
    "/{symbol}",
    response_model=WatchlistEntry,
    summary="Update symbol settings",
    description="Update priority, min_confidence, or enabled state for a symbol.",
)
async def update_symbol(
    request: UpdateSymbolRequest,
    symbol: str = Path(..., description="Symbol to update", max_length=10),
    user_id: UUID = Depends(get_current_user_id),
    service: WatchlistService = Depends(get_watchlist_service),
) -> WatchlistEntry:
    """
    Update a symbol's settings in watchlist.

    All fields are optional - only provided fields are updated.
    If enabled state changes, triggers subscription sync.

    Args:
        symbol: Symbol to update (path parameter)
        request: UpdateSymbolRequest with optional priority, min_confidence, enabled

    Returns:
        Updated WatchlistEntry

    Raises:
        404: Symbol not found in watchlist
        500: Internal server error

    Example Request:
        PATCH /api/v1/watchlist/AAPL
        {"priority": "high", "min_confidence": 80.0}

        To clear min_confidence:
        {"min_confidence": null}

    Example Response:
        {"symbol": "AAPL", "priority": "high", "min_confidence": 80.0, ...}
    """
    try:
        # Check if min_confidence was explicitly provided in the request body
        # This allows us to distinguish between "not provided" and "explicitly null"
        clear_min_confidence = (
            "min_confidence" in request.model_fields_set and request.min_confidence is None
        )

        entry = await service.update_symbol(
            user_id=user_id,
            symbol=symbol,
            priority=request.priority,
            min_confidence=request.min_confidence,
            enabled=request.enabled,
            clear_min_confidence=clear_min_confidence,
        )

        if not entry:
            logger.warning(
                "symbol_not_in_watchlist_for_update",
                user_id=str(user_id),
                symbol=symbol,
            )
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Symbol {symbol.upper()} not found in watchlist",
            )

        logger.info(
            "symbol_updated_in_watchlist",
            user_id=str(user_id),
            symbol=symbol,
        )

        return entry

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "update_symbol_failed",
            user_id=str(user_id),
            symbol=symbol,
            error=str(e),
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update symbol in watchlist",
        ) from e
