"""
Audit Log API Routes (Story 10.8)

Purpose:
--------
Provides REST API endpoint for trade audit log - searchable history of all pattern
detections (both executed signals and rejected patterns).

Endpoints:
----------
GET /api/v1/audit-log - Query audit log with filtering, sorting, pagination

Features:
---------
- Filtering: Date range, symbol, pattern type, status, confidence range
- Full-text search: Across symbol, pattern type, phase, status, rejection reason
- Sorting: By timestamp, symbol, pattern type, confidence, status
- Pagination: Efficient handling of large result sets (default 50/page, max 200)
- Performance: Target <500ms for 10,000+ patterns

Integration:
------------
- Story 10.8: Trade audit log table
- AuditRepository: Database queries with LEFT JOIN on patterns/signals
- ValidationChainStep: Wyckoff educational layer

Author: Story 10.8 (AC 9)
"""

from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.audit import AuditLogQueryParams, AuditLogResponse
from src.models.audit_trail import AuditTrailQuery, AuditTrailResponse
from src.repositories.audit_repository import AuditRepository
from src.repositories.audit_trail_repository import AuditTrailRepository

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1", tags=["audit"])


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "/audit-log",
    response_model=AuditLogResponse,
    summary="Query trade audit log",
    description=(
        "Retrieve audit log of all pattern detections (executed and rejected) "
        "with filtering, sorting, and pagination. "
        "Supports date range, symbol, pattern type, status, confidence filters, "
        "and full-text search."
    ),
)
async def get_audit_log(
    # Filtering (AC: 2)
    start_date: Optional[datetime] = Query(
        None, description="Filter patterns detected after this date (UTC, ISO 8601)"
    ),
    end_date: Optional[datetime] = Query(
        None, description="Filter patterns detected before this date (UTC, ISO 8601)"
    ),
    symbols: Optional[list[str]] = Query(
        None,
        description="Filter by symbol(s) (e.g., ?symbols=AAPL&symbols=TSLA)",
        examples=["AAPL", "TSLA"],
    ),
    pattern_types: Optional[list[str]] = Query(
        None,
        description="Filter by pattern type(s)",
        examples=["SPRING", "SOS"],
    ),
    statuses: Optional[list[str]] = Query(
        None,
        description="Filter by status(es)",
        examples=["FILLED", "REJECTED"],
    ),
    min_confidence: Optional[int] = Query(
        None, ge=0, le=100, description="Minimum confidence score (0-100)"
    ),
    max_confidence: Optional[int] = Query(
        None, ge=0, le=100, description="Maximum confidence score (0-100)"
    ),
    # Search (AC: 7)
    search_text: Optional[str] = Query(
        None,
        max_length=200,
        description="Full-text search across symbol, pattern, phase, status, rejection reason",
    ),
    # Sorting (AC: 3)
    order_by: str = Query(
        "timestamp",
        description="Column to sort by",
        pattern="^(timestamp|symbol|pattern_type|confidence|status)$",
    ),
    order_direction: str = Query("desc", description="Sort direction", pattern="^(asc|desc)$"),
    # Pagination (AC: 6)
    limit: int = Query(50, ge=1, le=200, description="Results per page (max 200)"),
    offset: int = Query(0, ge=0, description="Starting position"),
) -> AuditLogResponse:
    """
    Query audit log with filtering, sorting, and pagination.

    Returns paginated list of audit log entries with complete pattern/signal data,
    validation chains with Wyckoff rule references, and pattern metrics.

    Args:
        start_date: Filter after this date (UTC)
        end_date: Filter before this date (UTC)
        symbols: List of symbols to filter
        pattern_types: List of pattern types to filter
        statuses: List of statuses to filter
        min_confidence: Minimum confidence score
        max_confidence: Maximum confidence score
        search_text: Full-text search across fields
        order_by: Column to sort by (timestamp|symbol|pattern_type|confidence|status)
        order_direction: Sort direction (asc|desc)
        limit: Results per page (default 50, max 200)
        offset: Starting position (default 0)

    Returns:
        AuditLogResponse with paginated data and metadata

    Raises:
        HTTPException 400: Invalid query parameters
        HTTPException 422: Invalid date range (start_date > end_date)
        HTTPException 500: Database query error

    Example:
        GET /api/v1/audit-log?symbols=AAPL&pattern_types=SPRING&limit=50&offset=0
    """
    try:
        # Validate date range
        if start_date and end_date and start_date > end_date:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="start_date must be before end_date",
            )

        # Build query parameters
        params = AuditLogQueryParams(
            start_date=start_date,
            end_date=end_date,
            symbols=symbols,
            pattern_types=pattern_types,
            statuses=statuses,
            min_confidence=min_confidence,
            max_confidence=max_confidence,
            search_text=search_text,
            order_by=order_by,
            order_direction=order_direction,  # type: ignore
            limit=limit,
            offset=offset,
        )

        # Query repository
        repository = AuditRepository()
        entries, total_count = repository.get_audit_log(params)

        # Build response
        response = AuditLogResponse(
            data=entries, total_count=total_count, limit=limit, offset=offset
        )

        logger.info(
            "audit_log_query_success",
            returned_count=len(entries),
            total_count=total_count,
            filters={
                "start_date": start_date,
                "end_date": end_date,
                "symbols": symbols,
                "pattern_types": pattern_types,
                "statuses": statuses,
                "min_confidence": min_confidence,
                "max_confidence": max_confidence,
                "search_text": search_text,
            },
            order_by=order_by,
            order_direction=order_direction,
            limit=limit,
            offset=offset,
        )

        return response

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except ValueError as e:
        # Invalid parameters
        logger.error("audit_log_query_validation_error", error=str(e))
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"Invalid parameters: {e}"
        ) from e
    except Exception as e:
        # Database or other errors
        logger.error("audit_log_query_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query audit log",
        ) from e


@router.get(
    "/audit-trail",
    response_model=AuditTrailResponse,
    summary="Query audit trail (overrides, config changes)",
    description=(
        "Retrieve audit trail entries for manual overrides and compliance tracking. "
        "Supports filtering by event type, entity, actor, and date range."
    ),
)
async def get_audit_trail(
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
    actor: Optional[str] = Query(None, description="Filter by actor"),
    correlation_id: Optional[str] = Query(None, description="Filter by correlation ID"),
    start_date: Optional[datetime] = Query(None, description="Filter start date (UTC)"),
    end_date: Optional[datetime] = Query(None, description="Filter end date (UTC)"),
    limit: int = Query(50, ge=1, le=200, description="Results per page"),
    offset: int = Query(0, ge=0, description="Starting position"),
    db: AsyncSession = Depends(get_db),
) -> AuditTrailResponse:
    """
    Query audit trail with filtering and pagination.

    Returns paginated list of audit trail entries for compliance review.
    """
    try:
        if start_date and end_date and start_date > end_date:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="start_date must be before end_date",
            )

        params = AuditTrailQuery(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            correlation_id=correlation_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )

        repo = AuditTrailRepository(db)
        entries, total_count = await repo.query(params)

        return AuditTrailResponse(data=entries, total_count=total_count, limit=limit, offset=offset)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("audit_trail_query_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query audit trail",
        ) from e
