"""
Feedback Models (Story 10.7)

Purpose:
--------
Pydantic models for trader feedback on rejection decisions.
Allows traders to provide feedback on whether rejections were appropriate,
request review, or ask questions.

Data Models:
------------
- FeedbackSubmission: Request body for submitting feedback
- FeedbackResponse: API response after feedback submission
- Feedback: Database model for persisting feedback

Integration:
------------
- Story 10.7: Educational Rejection Detail View
- POST /api/v1/feedback endpoint for feedback submission

Author: Story 10.7
"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class FeedbackSubmission(BaseModel):
    """
    Request body for submitting trader feedback on rejection decisions.

    Fields:
    -------
    - signal_id: UUID of rejected signal
    - feedback_type: Type of feedback (positive, review_request, question)
    - explanation: Optional explanation text (required for review_request)
    - timestamp: Submission timestamp (auto-generated)

    Example:
    --------
    >>> submission = FeedbackSubmission(
    ...     signal_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
    ...     feedback_type="positive",
    ...     explanation=None,
    ...     timestamp=datetime.now(UTC)
    ... )
    """

    signal_id: UUID = Field(..., description="UUID of rejected signal")
    feedback_type: Literal["positive", "review_request", "question"] = Field(
        ..., description="Type of feedback"
    )
    explanation: str | None = Field(
        None, max_length=1000, description="Optional explanation (required for review_request)"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Submission timestamp (UTC)"
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | str) -> datetime:
        """Enforce UTC timezone on timestamps."""
        if isinstance(v, str):
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    @field_validator("explanation")
    @classmethod
    def validate_explanation_required(cls, v: str | None, info) -> str | None:
        """Require explanation for review_request feedback type."""
        values = info.data
        if "feedback_type" in values and values["feedback_type"] == "review_request":
            if not v or v.strip() == "":
                raise ValueError("explanation is required for feedback_type='review_request'")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "signal_id": "550e8400-e29b-41d4-a716-446655440000",
                    "feedback_type": "positive",
                    "explanation": None,
                    "timestamp": "2024-03-15T14:30:00Z",
                }
            ]
        }
    }


class FeedbackResponse(BaseModel):
    """
    API response after feedback submission.

    Fields:
    -------
    - feedback_id: Unique identifier for the feedback record
    - status: Processing status (received, queued_for_review)
    - message: User-friendly confirmation message

    Example:
    --------
    >>> response = FeedbackResponse(
    ...     feedback_id=UUID("660e8400-e29b-41d4-a716-446655440001"),
    ...     status="received",
    ...     message="Thank you for your feedback! This helps improve the system."
    ... )
    """

    feedback_id: UUID = Field(..., description="Unique feedback identifier")
    status: Literal["received", "queued_for_review"] = Field(..., description="Processing status")
    message: str = Field(..., description="User-friendly confirmation message")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "feedback_id": "660e8400-e29b-41d4-a716-446655440001",
                    "status": "received",
                    "message": "Thank you for your feedback! This helps improve the system.",
                }
            ]
        }
    }


class Feedback(BaseModel):
    """
    Database model for persisting trader feedback.

    Fields:
    -------
    - id: Unique feedback identifier
    - signal_id: UUID of rejected signal
    - feedback_type: Type of feedback
    - explanation: Optional explanation text
    - timestamp: Submission timestamp
    - created_at: Database record creation timestamp
    - processed: Whether feedback has been reviewed

    Example:
    --------
    >>> feedback = Feedback(
    ...     id=UUID("660e8400-e29b-41d4-a716-446655440001"),
    ...     signal_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
    ...     feedback_type="positive",
    ...     explanation=None,
    ...     timestamp=datetime.now(UTC),
    ...     processed=False
    ... )
    """

    id: UUID = Field(default_factory=uuid4, description="Unique feedback identifier")
    signal_id: UUID = Field(..., description="UUID of rejected signal")
    feedback_type: Literal["positive", "review_request", "question"] = Field(
        ..., description="Type of feedback"
    )
    explanation: str | None = Field(None, description="Optional explanation text")
    timestamp: datetime = Field(..., description="Submission timestamp (UTC)")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Database record creation timestamp"
    )
    processed: bool = Field(default=False, description="Whether feedback has been reviewed")

    @field_validator("timestamp", "created_at", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | str) -> datetime:
        """Enforce UTC timezone on timestamps."""
        if isinstance(v, str):
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}
