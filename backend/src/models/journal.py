"""
Trade Journal Data Models - Wyckoff Learning & Retrospective Analysis

Purpose:
--------
Provides SQLAlchemy ORM model and Pydantic schemas for the Trade Journal feature.
Allows traders to attach pre-trade reasoning, post-trade reviews, emotional state
tags, and Wyckoff checklist items to any campaign or signal.

The Wyckoff checklist is the key learning mechanism - tracking 4 criteria:
1. Phase confirmed: Was the Wyckoff phase clearly identified before entry?
2. Volume confirmed: Did volume support the setup?
3. Creek/Ice identified: Was the key support/resistance level mapped?
4. Pattern confirmed: Was the Spring/SOS/LPS/UTAD pattern clearly formed?

Author: Feature P2-8 (Trade Journal)
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base

# =====================
# Enums
# =====================


class EntryType(str, Enum):
    """Type of journal entry."""

    PRE_TRADE = "pre_trade"
    POST_TRADE = "post_trade"
    OBSERVATION = "observation"


class EmotionalState(str, Enum):
    """Trader emotional state at time of entry."""

    CONFIDENT = "confident"
    UNCERTAIN = "uncertain"
    FOMO = "fomo"
    DISCIPLINED = "disciplined"
    NEUTRAL = "neutral"


# =====================
# SQLAlchemy ORM Model
# =====================


class JournalEntryModel(Base):
    """
    Journal entry database model.

    Stores trade journal entries with optional campaign/signal linkage,
    Wyckoff checklist (stored as JSON), and emotional state tags.
    """

    __tablename__ = "journal_entries"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Optional campaign linkage (no FK constraint to avoid migration complexity)
    campaign_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Optional signal linkage (no FK constraint - signals may be ephemeral)
    signal_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
    )

    symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    entry_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=EntryType.OBSERVATION.value,
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    emotional_state: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        default=EmotionalState.NEUTRAL.value,
    )

    # Wyckoff checklist stored as JSON:
    # {
    #   "phase_confirmed": bool,
    #   "volume_confirmed": bool,
    #   "creek_identified": bool,
    #   "pattern_confirmed": bool
    # }
    wyckoff_checklist: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        default=lambda: {
            "phase_confirmed": False,
            "volume_confirmed": False,
            "creek_identified": False,
            "pattern_confirmed": False,
        },
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


# =====================
# Pydantic Schemas
# =====================


class WyckoffChecklist(BaseModel):
    """The 4-point Wyckoff criteria checklist."""

    phase_confirmed: bool = False
    volume_confirmed: bool = False
    creek_identified: bool = False
    pattern_confirmed: bool = False

    @property
    def score(self) -> int:
        """Number of criteria met (0-4)."""
        return sum(
            [
                self.phase_confirmed,
                self.volume_confirmed,
                self.creek_identified,
                self.pattern_confirmed,
            ]
        )


class JournalEntryCreate(BaseModel):
    """Request schema for creating a journal entry."""

    model_config = ConfigDict(use_enum_values=True)

    symbol: str = Field(..., min_length=1, max_length=20, description="Trading symbol")
    entry_type: EntryType = Field(
        default=EntryType.OBSERVATION, description="Type of journal entry"
    )
    notes: Optional[str] = Field(None, description="Full text notes")
    campaign_id: Optional[UUID] = Field(None, description="Linked campaign ID (optional)")
    signal_id: Optional[UUID] = Field(None, description="Linked signal ID (optional)")
    emotional_state: Optional[EmotionalState] = Field(
        default=EmotionalState.NEUTRAL, description="Trader emotional state"
    )
    wyckoff_checklist: Optional[WyckoffChecklist] = Field(
        default=None, description="Wyckoff 4-point criteria checklist"
    )


class JournalEntryUpdate(BaseModel):
    """Request schema for updating a journal entry (all fields optional)."""

    model_config = ConfigDict(use_enum_values=True)

    symbol: Optional[str] = Field(None, min_length=1, max_length=20)
    entry_type: Optional[EntryType] = None
    notes: Optional[str] = None
    emotional_state: Optional[EmotionalState] = None
    wyckoff_checklist: Optional[WyckoffChecklist] = None


class JournalEntryResponse(BaseModel):
    """Response schema for a single journal entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    campaign_id: Optional[UUID]
    signal_id: Optional[UUID]
    symbol: str
    entry_type: str
    notes: Optional[str]
    emotional_state: Optional[str]
    wyckoff_checklist: Optional[dict[str, Any]]
    checklist_score: int = Field(default=0, description="Number of Wyckoff criteria met (0-4)")
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, model: JournalEntryModel) -> "JournalEntryResponse":
        """Build response from ORM model, computing checklist_score."""
        checklist = model.wyckoff_checklist or {}
        score = sum(
            [
                bool(checklist.get("phase_confirmed", False)),
                bool(checklist.get("volume_confirmed", False)),
                bool(checklist.get("creek_identified", False)),
                bool(checklist.get("pattern_confirmed", False)),
            ]
        )
        return cls(
            id=model.id,
            user_id=model.user_id,
            campaign_id=model.campaign_id,
            signal_id=model.signal_id,
            symbol=model.symbol,
            entry_type=model.entry_type,
            notes=model.notes,
            emotional_state=model.emotional_state,
            wyckoff_checklist=model.wyckoff_checklist,
            checklist_score=score,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class JournalListResponse(BaseModel):
    """Paginated list response for journal entries."""

    data: list[JournalEntryResponse]
    pagination: dict[str, Any]
