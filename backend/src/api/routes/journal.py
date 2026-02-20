"""
Trade Journal API Routes

Provides CRUD endpoints for trade journal entries with Wyckoff checklist,
emotional state tracking, and campaign/signal linkage.

Endpoints:
- POST   /api/v1/journal              - Create journal entry
- GET    /api/v1/journal              - List entries (paginated, filterable)
- GET    /api/v1/journal/{id}         - Get single entry
- PUT    /api/v1/journal/{id}         - Update entry
- DELETE /api/v1/journal/{id}         - Delete entry
- GET    /api/v1/journal/campaign/{campaign_id} - Get all entries for a campaign

Author: Feature P2-8 (Trade Journal)
"""

from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user_id
from src.database import get_db
from src.models.journal import (
    JournalEntryCreate,
    JournalEntryResponse,
    JournalEntryUpdate,
    JournalListResponse,
)
from src.repositories.journal_repository import JournalRepository

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/journal", tags=["journal"])


@router.post("", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_journal_entry(
    payload: JournalEntryCreate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> JournalEntryResponse:
    """
    Create a new trade journal entry.

    Links to a campaign or signal (both optional). Includes Wyckoff checklist
    and emotional state for retrospective analysis.
    """
    repo = JournalRepository(db)

    checklist = None
    if payload.wyckoff_checklist is not None:
        checklist = payload.wyckoff_checklist.model_dump()

    entry = await repo.create(
        user_id=user_id,
        symbol=payload.symbol,
        entry_type=payload.entry_type
        if isinstance(payload.entry_type, str)
        else payload.entry_type.value,
        notes=payload.notes,
        campaign_id=payload.campaign_id,
        signal_id=payload.signal_id,
        emotional_state=payload.emotional_state
        if isinstance(payload.emotional_state, str)
        else (payload.emotional_state.value if payload.emotional_state else None),
        wyckoff_checklist=checklist,
    )

    await db.commit()
    return JournalEntryResponse.from_model(entry)


@router.get("", response_model=JournalListResponse)
async def list_journal_entries(
    symbol: Optional[str] = Query(None, description="Filter by trading symbol"),
    entry_type: Optional[str] = Query(
        None, description="Filter by entry type: pre_trade, post_trade, observation"
    ),
    limit: int = Query(50, ge=1, le=100, description="Number of entries to return"),
    offset: int = Query(0, ge=0, description="Number of entries to skip"),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> JournalListResponse:
    """
    List journal entries with optional filtering.

    Filterable by symbol and entry_type. Results are sorted by date descending.
    """
    # Validate entry_type if provided
    valid_entry_types = ["pre_trade", "post_trade", "observation"]
    if entry_type and entry_type not in valid_entry_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid entry_type. Must be one of: {', '.join(valid_entry_types)}",
        )

    repo = JournalRepository(db)
    entries, total_count = await repo.list_entries(
        user_id=user_id,
        symbol=symbol,
        entry_type=entry_type,
        limit=limit,
        offset=offset,
    )

    responses = [JournalEntryResponse.from_model(e) for e in entries]
    has_more = (offset + len(responses)) < total_count

    return JournalListResponse(
        data=responses,
        pagination={
            "returned_count": len(responses),
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": has_more,
        },
    )


@router.get("/campaign/{campaign_id}", response_model=list[JournalEntryResponse])
async def get_entries_for_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> list[JournalEntryResponse]:
    """
    Get all journal entries linked to a specific campaign.

    Returns entries sorted by date descending.
    """
    repo = JournalRepository(db)
    entries = await repo.list_by_campaign(campaign_id=campaign_id, user_id=user_id)
    return [JournalEntryResponse.from_model(e) for e in entries]


@router.get("/{entry_id}", response_model=JournalEntryResponse)
async def get_journal_entry(
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> JournalEntryResponse:
    """
    Get a single journal entry by ID.

    Returns 404 if the entry does not exist or belongs to another user.
    """
    repo = JournalRepository(db)
    entry = await repo.get_by_id(entry_id=entry_id, user_id=user_id)

    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journal entry not found",
        )

    return JournalEntryResponse.from_model(entry)


@router.put("/{entry_id}", response_model=JournalEntryResponse)
async def update_journal_entry(
    entry_id: UUID,
    payload: JournalEntryUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> JournalEntryResponse:
    """
    Update an existing journal entry.

    All fields are optional - only provided fields are updated.
    Returns 404 if the entry does not exist or belongs to another user.
    """
    repo = JournalRepository(db)
    entry = await repo.get_by_id(entry_id=entry_id, user_id=user_id)

    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journal entry not found",
        )

    checklist = None
    if payload.wyckoff_checklist is not None:
        checklist = payload.wyckoff_checklist.model_dump()

    entry_type_val = None
    if payload.entry_type is not None:
        entry_type_val = (
            payload.entry_type if isinstance(payload.entry_type, str) else payload.entry_type.value
        )

    emotional_state_val = None
    if payload.emotional_state is not None:
        emotional_state_val = (
            payload.emotional_state
            if isinstance(payload.emotional_state, str)
            else payload.emotional_state.value
        )

    updated = await repo.update(
        entry=entry,
        symbol=payload.symbol,
        entry_type=entry_type_val,
        notes=payload.notes,
        emotional_state=emotional_state_val,
        wyckoff_checklist=checklist,
    )

    await db.commit()
    return JournalEntryResponse.from_model(updated)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_journal_entry(
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> None:
    """
    Delete a journal entry.

    Returns 404 if the entry does not exist or belongs to another user.
    """
    repo = JournalRepository(db)
    entry = await repo.get_by_id(entry_id=entry_id, user_id=user_id)

    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journal entry not found",
        )

    await repo.delete(entry)
    await db.commit()
