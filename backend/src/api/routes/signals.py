"""
Signal API Routes - Trade Signal Endpoints (Story 8.8)

Purpose:
--------
Provides REST API endpoints for trade signal retrieval and management.

Endpoints:
----------
GET /api/v1/signals - List signals with pagination and filters
GET /api/v1/signals/{signal_id} - Get single signal details
PATCH /api/v1/signals/{signal_id} - Update signal status

Author: Story 8.8 (AC 9)
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel, Field

from src.models.signal import TradeSignal

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/signals", tags=["signals"])


# ============================================================================
# Request/Response Models
# ============================================================================


class PaginationInfo(BaseModel):
    """Pagination metadata for list responses."""

    returned_count: int = Field(..., description="Number of items in this response")
    total_count: int = Field(..., description="Total number of items matching filters")
    limit: int = Field(..., description="Maximum items per page")
    offset: int = Field(..., description="Offset from start of results")
    has_more: bool = Field(..., description="Whether more items available")


class SignalListResponse(BaseModel):
    """Paginated list of trade signals."""

    data: list[TradeSignal] = Field(..., description="List of signals")
    pagination: PaginationInfo = Field(..., description="Pagination metadata")


class SignalStatusUpdate(BaseModel):
    """Request body for updating signal status."""

    status: Literal["FILLED", "STOPPED", "TARGET_HIT", "EXPIRED"] = Field(
        ..., description="New signal status"
    )
    filled_price: Decimal | None = Field(None, description="Actual fill price (if status=FILLED)")
    filled_timestamp: datetime | None = Field(None, description="Fill timestamp (if status=FILLED)")
    notes: str | None = Field(None, description="Optional notes about status change")


# ============================================================================
# Mock Data Store (Replace with database repository in production)
# ============================================================================

# In-memory storage for signals (MOCK - for demonstration only)
_signal_store: dict[UUID, TradeSignal] = {}


async def get_signal_by_id(signal_id: UUID) -> TradeSignal | None:
    """
    Fetch signal by ID from database.

    TODO: Replace with actual repository call when signal repository is implemented.

    Parameters:
    -----------
    signal_id : UUID
        Signal identifier

    Returns:
    --------
    TradeSignal | None
        Signal if found, None otherwise
    """
    # PLACEHOLDER: Return from mock store
    # In production, replace with:
    # from src.repositories.signal_repository import SignalRepository
    # repo = SignalRepository()
    # return await repo.get_by_id(signal_id)

    logger.debug("get_signal_by_id_called", signal_id=str(signal_id), note="Using mock store")
    return _signal_store.get(signal_id)


async def get_signals_with_filters(
    status: str | None = None,
    symbol: str | None = None,
    min_confidence: int | None = None,
    min_r_multiple: Decimal | None = None,
    since: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[TradeSignal], int]:
    """
    Fetch signals with filters and pagination.

    TODO: Replace with actual repository call when signal repository is implemented.

    Parameters:
    -----------
    status : str | None
        Filter by signal status
    symbol : str | None
        Filter by symbol
    min_confidence : int | None
        Minimum confidence score
    min_r_multiple : Decimal | None
        Minimum R-multiple
    since : datetime | None
        Only signals created after this timestamp
    limit : int
        Maximum number of results
    offset : int
        Offset from start of results

    Returns:
    --------
    tuple[list[TradeSignal], int]
        (list of signals, total count matching filters)
    """
    # PLACEHOLDER: Filter mock store
    # In production, replace with repository query

    logger.debug(
        "get_signals_with_filters_called",
        status=status,
        symbol=symbol,
        note="Using mock store",
    )

    signals = list(_signal_store.values())

    # Apply filters
    if status:
        signals = [s for s in signals if s.status == status]
    if symbol:
        signals = [s for s in signals if s.symbol == symbol]
    if min_confidence:
        signals = [s for s in signals if s.confidence_score >= min_confidence]
    if min_r_multiple:
        signals = [s for s in signals if s.r_multiple >= min_r_multiple]
    if since:
        signals = [s for s in signals if s.timestamp >= since]

    # Sort by timestamp descending (newest first)
    signals.sort(key=lambda s: s.timestamp, reverse=True)

    total_count = len(signals)

    # Apply pagination
    paginated_signals = signals[offset : offset + limit]

    return paginated_signals, total_count


async def update_signal_status(signal_id: UUID, status_update: SignalStatusUpdate) -> TradeSignal:
    """
    Update signal status in database.

    TODO: Replace with actual repository call when signal repository is implemented.

    Parameters:
    -----------
    signal_id : UUID
        Signal identifier
    status_update : SignalStatusUpdate
        Status update data

    Returns:
    --------
    TradeSignal
        Updated signal

    Raises:
    -------
    HTTPException
        404 if signal not found
    """
    # PLACEHOLDER: Update mock store
    # In production, replace with repository update

    logger.debug(
        "update_signal_status_called",
        signal_id=str(signal_id),
        new_status=status_update.status,
        note="Using mock store",
    )

    signal = _signal_store.get(signal_id)
    if not signal:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail=f"Signal {signal_id} not found"
        )

    # Create updated signal (immutability - new instance)
    updated_signal = signal.model_copy(update={"status": status_update.status})

    # Store updated signal
    _signal_store[signal_id] = updated_signal

    return updated_signal


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("", response_model=SignalListResponse, summary="List trade signals")
async def list_signals(
    status: Literal["PENDING", "APPROVED", "REJECTED", "FILLED", "STOPPED", "TARGET_HIT", "EXPIRED"]
    | None = Query(None, description="Filter by signal status"),
    symbol: str | None = Query(None, description="Filter by symbol (e.g., AAPL)"),
    min_confidence: int | None = Query(None, ge=70, le=95, description="Minimum confidence score"),
    min_r_multiple: Decimal | None = Query(
        None, ge=Decimal("0.0"), description="Minimum R-multiple"
    ),
    since: datetime | None = Query(None, description="Only signals created after this timestamp"),
    sorted: bool = Query(
        False,
        description="Return signals in priority order (Story 9.3). "
        "When True, signals ordered by FR28 priority score (highest first). "
        "When False, signals ordered by timestamp (newest first).",
    ),
    limit: int = Query(50, ge=1, le=200, description="Maximum results per page"),
    offset: int = Query(0, ge=0, description="Offset from start of results"),
) -> SignalListResponse:
    """
    List trade signals with pagination and filters (AC: 10).

    Query Parameters:
    -----------------
    - status: Filter by signal status (PENDING, APPROVED, REJECTED, etc.)
    - symbol: Filter by trading symbol (e.g., AAPL, EUR/USD)
    - min_confidence: Minimum confidence score (70-95)
    - min_r_multiple: Minimum risk/reward ratio
    - since: Only signals created after this timestamp
    - sorted: Return signals in FR28 priority order (Story 9.3)
    - limit: Maximum results per page (1-200, default 50)
    - offset: Offset from start of results (for pagination)

    Sorting Behavior (Story 9.3):
    ------------------------------
    - sorted=False (default): Signals ordered by timestamp DESC (newest first)
    - sorted=True: Signals ordered by FR28 priority score DESC (highest priority first)
      * Priority calculated from: confidence (40%), R-multiple (30%), pattern (30%)
      * Requires MasterOrchestrator with SignalPriorityQueue configured

    Returns:
    --------
    SignalListResponse
        Paginated list of signals with metadata

    Example:
    --------
    GET /api/v1/signals?status=APPROVED&symbol=AAPL&min_confidence=80&limit=20
    GET /api/v1/signals?sorted=true&limit=50  # Priority-ordered signals
    """
    try:
        # Story 9.3 AC 10: Handle sorted parameter
        if sorted:
            # TODO: Wire up MasterOrchestrator via dependency injection
            # When orchestrator available:
            #   from src.api.dependencies import get_orchestrator
            #   orchestrator = await get_orchestrator()
            #   if orchestrator.signal_priority_queue:
            #       signals = orchestrator.get_pending_signals(limit=limit)
            #       # Apply filters to sorted signals
            #       if status:
            #           signals = [s for s in signals if s.status == status]
            #       ...
            #
            # For now, use fallback sorting via calculate_adhoc_priority_score

            signals, total_count = await get_signals_with_filters(
                status=status,
                symbol=symbol,
                min_confidence=min_confidence,
                min_r_multiple=min_r_multiple,
                since=since,
                limit=999,  # Get all for sorting
                offset=0,
            )

            # Sort by ad-hoc priority score (FR28 weights)
            signals_with_scores = [
                (signal, calculate_adhoc_priority_score(signal)) for signal in signals
            ]
            signals_with_scores.sort(key=lambda x: x[1], reverse=True)  # Highest first
            signals = [s[0] for s in signals_with_scores]

            # Apply pagination after sorting
            total_count = len(signals)
            signals = signals[offset : offset + limit]

            logger.info(
                "signals_listed",
                returned_count=len(signals),
                total_count=total_count,
                sorted=True,
                filters={
                    "status": status,
                    "symbol": symbol,
                    "min_confidence": min_confidence,
                },
            )
        else:
            # Default: timestamp order (newest first)
            signals, total_count = await get_signals_with_filters(
                status=status,
                symbol=symbol,
                min_confidence=min_confidence,
                min_r_multiple=min_r_multiple,
                since=since,
                limit=limit,
                offset=offset,
            )

            logger.info(
                "signals_listed",
                returned_count=len(signals),
                total_count=total_count,
                sorted=False,
                filters={
                    "status": status,
                    "symbol": symbol,
                    "min_confidence": min_confidence,
                },
            )

        pagination = PaginationInfo(
            returned_count=len(signals),
            total_count=total_count,
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < total_count,
        )

        return SignalListResponse(data=signals, pagination=pagination)

    except Exception as e:
        logger.error("list_signals_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching signals: {str(e)}",
        ) from e


@router.get("/{signal_id}", response_model=TradeSignal, summary="Get single signal details")
async def get_signal(signal_id: UUID) -> TradeSignal:
    """
    Get single trade signal by ID.

    Path Parameters:
    ----------------
    - signal_id: Unique signal identifier (UUID)

    Returns:
    --------
    TradeSignal
        Complete signal with all FR22 fields and validation chain

    Raises:
    -------
    HTTPException
        404 if signal not found

    Example:
    --------
    GET /api/v1/signals/550e8400-e29b-41d4-a716-446655440000
    """
    signal = await get_signal_by_id(signal_id)

    if not signal:
        logger.warning("signal_not_found", signal_id=str(signal_id))
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Signal {signal_id} not found",
        )

    logger.info("signal_retrieved", signal_id=str(signal_id), symbol=signal.symbol)
    return signal


@router.patch("/{signal_id}", response_model=TradeSignal, summary="Update signal status")
async def update_signal(signal_id: UUID, status_update: SignalStatusUpdate) -> TradeSignal:
    """
    Update signal status (e.g., mark as FILLED, STOPPED, etc.).

    Path Parameters:
    ----------------
    - signal_id: Unique signal identifier (UUID)

    Request Body:
    -------------
    - status: New status (FILLED, STOPPED, TARGET_HIT, EXPIRED)
    - filled_price: Actual fill price (optional, for FILLED status)
    - filled_timestamp: Fill timestamp (optional, for FILLED status)
    - notes: Optional notes about status change

    Returns:
    --------
    TradeSignal
        Updated signal

    Raises:
    -------
    HTTPException
        404 if signal not found

    Example:
    --------
    PATCH /api/v1/signals/550e8400-e29b-41d4-a716-446655440000
    {
        "status": "FILLED",
        "filled_price": "150.50",
        "filled_timestamp": "2024-03-13T14:35:00Z"
    }
    """
    try:
        updated_signal = await update_signal_status(signal_id, status_update)

        logger.info(
            "signal_status_updated",
            signal_id=str(signal_id),
            old_status=updated_signal.status,  # Note: mock implementation doesn't track old status
            new_status=status_update.status,
        )

        return updated_signal

    except HTTPException:
        raise  # Re-raise 404 from update_signal_status
    except Exception as e:
        logger.error("update_signal_error", signal_id=str(signal_id), error=str(e), exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating signal: {str(e)}",
        ) from e


# ============================================================================
# Helper Functions
# ============================================================================


def calculate_adhoc_priority_score(signal: TradeSignal) -> float:
    """
    Calculate ad-hoc FR28 priority score for sorting (Story 9.3 AC 10).

    This is a fallback implementation for when MasterOrchestrator
    priority queue is not available. Uses same FR28 algorithm:
    - Confidence: 40% weight
    - R-multiple: 30% weight
    - Pattern priority: 30% weight

    Pattern priority order (lower = higher priority):
    - SPRING: 1 (highest)
    - LPS: 2
    - SOS: 3
    - UTAD: 4 (lowest)

    Parameters:
    -----------
    signal : TradeSignal
        Signal to score

    Returns:
    --------
    float
        Priority score 0.0-100.0 (higher = higher priority)
    """
    # Normalize confidence (70-95) to [0.0, 1.0]
    confidence_normalized = (signal.confidence_score - 70) / (95 - 70)
    confidence_normalized = max(0.0, min(1.0, confidence_normalized))

    # Normalize R-multiple (2.0-5.0) to [0.0, 1.0]
    r_multiple_float = float(signal.r_multiple)
    r_normalized = (r_multiple_float - 2.0) / (5.0 - 2.0)
    r_normalized = max(0.0, min(1.0, r_normalized))

    # Pattern priority: SPRING=1, LPS=2, SOS=3, UTAD=4
    pattern_priorities = {"SPRING": 1, "LPS": 2, "SOS": 3, "UTAD": 4}
    pattern_priority = pattern_priorities.get(signal.pattern_type, 4)

    # Normalize pattern priority (inverted: lower = higher score)
    pattern_normalized = (4 - pattern_priority) / (4 - 1)  # (max - p) / (max - min)

    # Apply FR28 weights
    weighted_score = (
        (confidence_normalized * 0.40) + (r_normalized * 0.30) + (pattern_normalized * 0.30)
    )

    # Scale to 0-100
    return weighted_score * 100.0


# ============================================================================
# Helper Functions for Testing
# ============================================================================


def add_signal_to_store(signal: TradeSignal) -> None:
    """
    Add signal to mock store (for testing only).

    This function is used by integration tests to populate the mock store.
    In production, signals would be saved via repository.

    Parameters:
    -----------
    signal : TradeSignal
        Signal to add to store
    """
    _signal_store[signal.id] = signal


def clear_signal_store() -> None:
    """
    Clear mock store (for testing only).

    Clears all signals from the in-memory store.
    Used by tests to ensure clean state between test runs.
    """
    _signal_store.clear()
