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
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user_id
from src.database import get_db
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


# ============================================================================
# Signal Audit Trail Endpoints (Story 19.11)
# ============================================================================


@router.get(
    "/history",
    response_model=dict,
    summary="Query signal history with filters",
    description="Query historical signals with filters and pagination for performance analysis",
)
async def get_signal_history(
    start_date: datetime | None = Query(None, description="Filter start date (inclusive)"),
    end_date: datetime | None = Query(None, description="Filter end date (inclusive)"),
    symbol: str | None = Query(None, description="Filter by symbol"),
    pattern_type: str | None = Query(
        None, description="Filter by pattern type (SPRING, SOS, etc.)"
    ),
    status: str | None = Query(None, description="Filter by lifecycle state"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Query signal history with filters and pagination (Story 19.11).

    Supports filtering by:
    - Date range (start_date, end_date)
    - Symbol (exact match)
    - Pattern type (SPRING, SOS, LPS, UTAD)
    - Lifecycle status (generated, pending, approved, executed, closed)

    Returns paginated results with complete audit trail for each signal.

    Example:
        GET /api/v1/signals/history?symbol=AAPL&status=executed&page=1&page_size=50
    """
    from src.models.signal_audit import SignalHistoryQuery, SignalLifecycleState
    from src.repositories.signal_audit_repository import SignalAuditRepository
    from src.services.signal_audit_service import SignalAuditService

    # Validate status if provided
    if status:
        try:
            SignalLifecycleState(status)
        except ValueError:
            valid_states = [state.value for state in SignalLifecycleState]
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid lifecycle state. Valid values: {', '.join(valid_states)}",
            ) from None

    try:
        # Build query
        query = SignalHistoryQuery(
            start_date=start_date,
            end_date=end_date,
            symbol=symbol,
            pattern_type=pattern_type,
            status=status,
            page=page,
            page_size=page_size,
        )

        # Execute query
        repository = SignalAuditRepository(db)
        service = SignalAuditService(repository)
        response = await service.query_signal_history(query)

        logger.info(
            "signal_history_queried",
            user_id=str(user_id),
            page=page,
            page_size=page_size,
            total_items=response.pagination.total_items,
            filters={
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "symbol": symbol,
                "pattern_type": pattern_type,
                "status": status,
            },
        )

        return response.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "signal_history_query_failed", user_id=str(user_id), error=str(e), exc_info=True
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query signal history",
        ) from e


@router.get(
    "/{signal_id}/audit",
    response_model=dict,
    summary="Get detailed audit trail for a signal",
    description="Retrieve complete lifecycle audit trail for a specific signal",
)
async def get_signal_audit_trail(
    signal_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get detailed audit trail for a specific signal (Story 19.11).

    Returns all state transitions in chronological order with:
    - Previous and new state
    - User who triggered transition (if applicable)
    - Timestamp
    - Transition reason
    - Metadata

    Example:
        GET /api/v1/signals/550e8400-e29b-41d4-a716-446655440000/audit
    """
    from src.models.signal_audit import SignalAuditLog
    from src.repositories.signal_audit_repository import SignalAuditRepository
    from src.services.signal_audit_service import SignalAuditService

    try:
        repository = SignalAuditRepository(db)
        service = SignalAuditService(repository)
        audit_entries = await service.get_signal_audit_trail(signal_id)

        if not audit_entries:
            logger.warning(
                "signal_audit_trail_not_found", signal_id=str(signal_id), user_id=str(user_id)
            )
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="No audit trail found for signal",
            )

        audit_log = SignalAuditLog(signal_id=signal_id, audit_entries=audit_entries)

        logger.info(
            "signal_audit_trail_retrieved",
            signal_id=str(signal_id),
            user_id=str(user_id),
            entry_count=len(audit_entries),
        )

        return audit_log.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "signal_audit_trail_retrieval_failed",
            signal_id=str(signal_id),
            user_id=str(user_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit trail",
        ) from e
