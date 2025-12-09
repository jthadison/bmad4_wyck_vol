"""
Feedback API Routes (Story 10.7)

Purpose:
--------
Provides REST API endpoints for trader feedback on rejection decisions.
Allows traders to submit feedback on whether pattern rejections were appropriate.

Endpoints:
----------
POST /api/v1/feedback - Submit feedback on rejection decision

Author: Story 10.7 (AC 7)
"""

from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, HTTPException
from fastapi import status as http_status

from src.models.feedback import Feedback, FeedbackResponse, FeedbackSubmission

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


# ============================================================================
# Mock Data Store (Replace with database repository in production)
# ============================================================================

# In-memory storage for feedback (MOCK - for demonstration only)
_feedback_store: dict[UUID, Feedback] = {}

# Mock signal store to validate signal_id exists
_mock_signal_ids: set[UUID] = set()


async def get_signal_by_id(signal_id: UUID) -> bool:
    """
    Check if signal exists in database.

    TODO: Replace with actual repository call when signal repository is implemented.

    Parameters:
    -----------
    signal_id : UUID
        Signal identifier

    Returns:
    --------
    bool
        True if signal exists, False otherwise
    """
    # PLACEHOLDER: Check mock store
    # In production, replace with:
    # from backend.src.repositories.signal_repository import SignalRepository
    # repo = SignalRepository()
    # signal = await repo.get_by_id(signal_id)
    # return signal is not None

    logger.debug("check_signal_exists", signal_id=str(signal_id), note="Using mock store")
    return signal_id in _mock_signal_ids


async def save_feedback(feedback: Feedback) -> Feedback:
    """
    Persist feedback to database.

    TODO: Replace with actual repository call when feedback repository is implemented.

    Parameters:
    -----------
    feedback : Feedback
        Feedback record to persist

    Returns:
    --------
    Feedback
        Persisted feedback record
    """
    # PLACEHOLDER: Save to mock store
    # In production, replace with:
    # from backend.src.repositories.feedback_repository import FeedbackRepository
    # repo = FeedbackRepository()
    # return await repo.create(feedback)

    logger.info(
        "feedback_saved",
        feedback_id=str(feedback.id),
        signal_id=str(feedback.signal_id),
        feedback_type=feedback.feedback_type,
        note="Using mock store",
    )
    _feedback_store[feedback.id] = feedback
    return feedback


# ============================================================================
# API Endpoints
# ============================================================================


@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="Submit feedback on rejection decision",
    description="""
    Submit trader feedback on a rejected signal.

    Feedback types:
    - positive: Rejection was correct, builds trust
    - review_request: Trader disagrees, requests human review (requires explanation)
    - question: Trader wants to ask William about the rejection (future feature)

    Returns 201 Created with feedback_id on success.
    Returns 404 Not Found if signal_id doesn't exist.
    Returns 400 Bad Request if explanation missing for review_request.
    """,
)
async def submit_feedback(submission: FeedbackSubmission) -> FeedbackResponse:
    """
    Submit trader feedback on rejection decision (AC: 7).

    Validates signal exists, persists feedback, and returns confirmation.

    Parameters:
    -----------
    submission : FeedbackSubmission
        Feedback submission request body

    Returns:
    --------
    FeedbackResponse
        Confirmation with feedback_id and message

    Raises:
    -------
    HTTPException 404
        If signal_id not found
    HTTPException 400
        If explanation missing for review_request type
    """
    logger.info(
        "feedback_submission_received",
        signal_id=str(submission.signal_id),
        feedback_type=submission.feedback_type,
    )

    # Validate signal exists
    signal_exists = await get_signal_by_id(submission.signal_id)
    if not signal_exists:
        logger.warning(
            "feedback_rejected_signal_not_found",
            signal_id=str(submission.signal_id),
        )
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Signal {submission.signal_id} not found",
        )

    # Create feedback record
    feedback = Feedback(
        id=uuid4(),
        signal_id=submission.signal_id,
        feedback_type=submission.feedback_type,
        explanation=submission.explanation,
        timestamp=submission.timestamp,
        processed=False,
    )

    # Persist to database
    saved_feedback = await save_feedback(feedback)

    # Determine response status
    status = "queued_for_review" if submission.feedback_type == "review_request" else "received"

    # Generate user-friendly message
    messages = {
        "positive": "Thank you for your feedback! This helps improve the system.",
        "review_request": "Your review request has been queued. A team member will investigate this rejection.",
        "question": "Your question has been received. The 'Ask William' feature is coming soon!",
    }
    message = messages.get(submission.feedback_type, "Feedback received.")

    logger.info(
        "feedback_submitted_successfully",
        feedback_id=str(saved_feedback.id),
        signal_id=str(submission.signal_id),
        status=status,
    )

    return FeedbackResponse(
        feedback_id=saved_feedback.id,
        status=status,
        message=message,
    )
