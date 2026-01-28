"""
Watchlist API Routes (Story 19.12)

Purpose:
--------
REST API endpoints for user watchlist management.
Enables users to configure which symbols the system monitors.

Endpoints:
----------
GET    /api/v1/watchlist           - Get user's watchlist
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

from collections.abc import AsyncGenerator
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi import status as http_status

from src.database import async_session_maker
from src.models.watchlist import (
    AddSymbolRequest,
    UpdateSymbolRequest,
    WatchlistEntry,
    WatchlistResponse,
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

    Example Response:
        {"symbol": "AAPL", "priority": "high", "min_confidence": 80.0, ...}
    """
    try:
        entry = await service.update_symbol(
            user_id=user_id,
            symbol=symbol,
            priority=request.priority,
            min_confidence=request.min_confidence,
            enabled=request.enabled,
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
