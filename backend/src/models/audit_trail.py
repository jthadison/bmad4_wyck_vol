"""
Audit Trail Pydantic Models (Task #2).

Pydantic models for audit trail persistence and API responses.
Used for correlation override audit logging and general compliance tracking.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuditTrailCreate(BaseModel):
    """Input schema for creating an audit trail entry."""

    event_type: str = Field(
        ..., max_length=50, description="Event category: CORRELATION_OVERRIDE, CONFIG_CHANGE, etc."
    )
    entity_type: str = Field(
        ..., max_length=50, description="Entity type: SIGNAL, CAMPAIGN, CONFIG, etc."
    )
    entity_id: str = Field(..., max_length=100, description="Entity identifier")
    actor: str = Field(..., max_length=255, description="Who performed the action")
    action: str = Field(..., description="Human-readable action description")
    correlation_id: str | None = Field(
        None, max_length=100, description="Correlation ID for cross-system tracing"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context data")


class AuditTrailEntry(BaseModel):
    """Audit trail entry returned from database."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Unique entry ID")
    event_type: str = Field(description="Event category")
    entity_type: str = Field(description="Entity type")
    entity_id: str = Field(description="Entity identifier")
    actor: str = Field(description="Who performed the action")
    action: str = Field(description="Action description")
    correlation_id: str | None = Field(None, description="Correlation ID for tracing")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context")
    created_at: datetime = Field(description="When the event occurred")

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | str) -> datetime:
        """Enforce UTC timezone."""
        if isinstance(v, str):
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)


class AuditTrailQuery(BaseModel):
    """Query parameters for audit trail endpoint."""

    event_type: str | None = Field(None, description="Filter by event type")
    entity_type: str | None = Field(None, description="Filter by entity type")
    entity_id: str | None = Field(None, description="Filter by entity ID")
    actor: str | None = Field(None, description="Filter by actor")
    correlation_id: str | None = Field(None, description="Filter by correlation ID")
    start_date: datetime | None = Field(None, description="Filter start (inclusive)")
    end_date: datetime | None = Field(None, description="Filter end (inclusive)")
    limit: int = Field(default=50, ge=1, le=200, description="Results per page")
    offset: int = Field(default=0, ge=0, description="Starting position")


class AuditTrailResponse(BaseModel):
    """Paginated audit trail response."""

    data: list[AuditTrailEntry] = Field(description="Audit trail entries")
    total_count: int = Field(ge=0, description="Total matching entries")
    limit: int = Field(ge=1, le=200, description="Results per page")
    offset: int = Field(ge=0, description="Starting position")
