"""
Signal Approval Queue API Routes (Story 19.9)

REST API endpoints for signal approval queue operations.

Endpoints:
----------
GET /api/v1/signals/pending - List pending signals for approval
POST /api/v1/signals/{queue_id}/approve - Approve a pending signal
POST /api/v1/signals/{queue_id}/reject - Reject a pending signal

Author: Story 19.9
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user_id, get_db_session
from src.models.signal_approval import (
    PendingSignalsResponse,
    SignalApprovalResult,
    SignalRejectionRequest,
)
from src.repositories.signal_approval_repository import SignalApprovalRepository
from src.services.signal_approval_service import SignalApprovalService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/signals", tags=["Signal Approval"])


async def get_signal_approval_service(
    db: AsyncSession = Depends(get_db_session),
) -> SignalApprovalService:
    """
    Dependency to get signal approval service.

    Creates service with repository and configuration.
    """
    repository = SignalApprovalRepository(db)
    # Paper trading service would be injected here in production
    return SignalApprovalService(repository=repository)


@router.get(
    "/pending",
    response_model=PendingSignalsResponse,
    summary="List pending signals for approval",
    responses={
        200: {
            "description": "List of pending signals",
            "content": {
                "application/json": {
                    "example": {
                        "signals": [
                            {
                                "queue_id": "550e8400-e29b-41d4-a716-446655440000",
                                "signal_id": "660e8400-e29b-41d4-a716-446655440001",
                                "symbol": "AAPL",
                                "pattern_type": "SPRING",
                                "confidence_score": 92.5,
                                "confidence_grade": "A+",
                                "entry_price": "150.25",
                                "stop_loss": "149.50",
                                "target_price": "152.75",
                                "submitted_at": "2026-01-23T10:30:00Z",
                                "expires_at": "2026-01-23T10:35:00Z",
                                "time_remaining_seconds": 180,
                            }
                        ],
                        "total_count": 1,
                    }
                }
            },
        },
        401: {"description": "Unauthorized"},
    },
)
async def list_pending_signals(
    user_id: UUID = Depends(get_current_user_id),
    service: SignalApprovalService = Depends(get_signal_approval_service),
) -> PendingSignalsResponse:
    """
    List all pending signals awaiting user approval.

    Returns signals ordered by submission time (oldest first).
    Each signal includes time remaining until expiration.

    Authentication:
    ---------------
    Requires valid JWT Bearer token in Authorization header.
    """
    try:
        pending_signals = await service.get_pending_signals(user_id)

        logger.info(
            "pending_signals_listed",
            user_id=str(user_id),
            count=len(pending_signals),
        )

        return PendingSignalsResponse(
            signals=pending_signals,
            total_count=len(pending_signals),
        )

    except Exception as e:
        logger.error(
            "list_pending_signals_error",
            user_id=str(user_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while listing pending signals",
        ) from e


@router.post(
    "/{queue_id}/approve",
    response_model=SignalApprovalResult,
    summary="Approve a pending signal for execution",
    responses={
        200: {
            "description": "Signal approved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "approved",
                        "approved_at": "2026-01-23T10:32:00Z",
                        "execution": {
                            "position_id": "770e8400-e29b-41d4-a716-446655440002",
                            "entry_price": "150.30",
                            "shares": 100,
                        },
                        "message": "Signal approved and executed",
                    }
                }
            },
        },
        400: {"description": "Signal already processed"},
        401: {"description": "Unauthorized"},
        404: {"description": "Signal not found"},
    },
)
async def approve_signal(
    queue_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    service: SignalApprovalService = Depends(get_signal_approval_service),
) -> SignalApprovalResult:
    """
    Approve a pending signal for execution.

    Changes status to "approved" and triggers execution via paper trading service.
    Uses optimistic locking to prevent duplicate approvals.

    Path Parameters:
    ----------------
    - queue_id: UUID of the queue entry to approve

    Authentication:
    ---------------
    Requires valid JWT Bearer token in Authorization header.
    User must own the queue entry to approve it.
    """
    try:
        result = await service.approve_signal(queue_id, user_id)

        if result.status.value == "pending":
            # Error case - signal not found or not authorized
            if "not found" in result.message.lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=result.message,
                )
            elif "not authorized" in result.message.lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=result.message,
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=result.message,
                )

        if result.status.value == "expired":
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail=result.message,
            )

        logger.info(
            "signal_approved_via_api",
            queue_id=str(queue_id),
            user_id=str(user_id),
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "approve_signal_error",
            queue_id=str(queue_id),
            user_id=str(user_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while approving the signal",
        ) from e


@router.post(
    "/{queue_id}/reject",
    response_model=SignalApprovalResult,
    summary="Reject a pending signal",
    responses={
        200: {
            "description": "Signal rejected successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "rejected",
                        "rejection_reason": "Price moved too far from entry",
                        "message": "Signal rejected",
                    }
                }
            },
        },
        400: {"description": "Signal already processed"},
        401: {"description": "Unauthorized"},
        404: {"description": "Signal not found"},
    },
)
async def reject_signal(
    queue_id: UUID,
    request: SignalRejectionRequest,
    user_id: UUID = Depends(get_current_user_id),
    service: SignalApprovalService = Depends(get_signal_approval_service),
) -> SignalApprovalResult:
    """
    Reject a pending signal.

    Changes status to "rejected" with a reason.
    No execution occurs for rejected signals.

    Path Parameters:
    ----------------
    - queue_id: UUID of the queue entry to reject

    Request Body:
    -------------
    - reason: Explanation for rejection (3-500 characters)

    Authentication:
    ---------------
    Requires valid JWT Bearer token in Authorization header.
    User must own the queue entry to reject it.
    """
    try:
        result = await service.reject_signal(queue_id, user_id, request.reason)

        if result.status.value == "pending":
            # Error case - signal not found or not authorized
            if "not found" in result.message.lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=result.message,
                )
            elif "not authorized" in result.message.lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=result.message,
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=result.message,
                )

        logger.info(
            "signal_rejected_via_api",
            queue_id=str(queue_id),
            user_id=str(user_id),
            reason=request.reason,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "reject_signal_error",
            queue_id=str(queue_id),
            user_id=str(user_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while rejecting the signal",
        ) from e
