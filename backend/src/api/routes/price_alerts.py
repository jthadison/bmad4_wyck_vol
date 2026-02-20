"""
Price Alert API Routes.

Provides REST endpoints for managing user price alerts with Wyckoff-specific
alert types (Creek, Ice, Spring, Phase Change).

Endpoints:
- POST   /api/v1/price-alerts        - Create alert
- GET    /api/v1/price-alerts        - List user's alerts
- PUT    /api/v1/price-alerts/{id}   - Update alert
- DELETE /api/v1/price-alerts/{id}   - Delete alert
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user, get_db_session
from src.models.price_alert import (
    PriceAlert,
    PriceAlertCreate,
    PriceAlertListResponse,
    PriceAlertUpdate,
)
from src.repositories.price_alert_repository import PriceAlertRepository

router = APIRouter(prefix="/api/v1/price-alerts", tags=["price-alerts"])


async def get_price_alert_repository(
    session: AsyncSession = Depends(get_db_session),
) -> PriceAlertRepository:
    """Dependency: create PriceAlertRepository bound to the request session."""
    return PriceAlertRepository(session)


@router.post("", response_model=PriceAlert, status_code=201)
async def create_price_alert(
    payload: PriceAlertCreate,
    current_user: dict = Depends(get_current_user),
    repository: PriceAlertRepository = Depends(get_price_alert_repository),
) -> PriceAlert:
    """
    Create a new price alert.

    Supports Wyckoff-specific alert types:
    - **price_level**: Notify when price crosses above/below a custom level
    - **creek**: Notify when price breaks above the Creek/Ice resistance (SOS)
    - **ice**: Notify when price tests Ice support from above (LPS)
    - **spring**: Notify when price dips below Spring support (Phase C shakeout)
    - **phase_change**: Notify when the Wyckoff phase changes for the symbol
    """
    user_id = current_user["id"]

    # Validate required fields per alert type
    price_required_types = {"price_level", "creek", "ice", "spring"}
    if payload.alert_type.value in price_required_types and payload.price_level is None:
        raise HTTPException(
            status_code=422,
            detail=f"price_level is required for alert_type '{payload.alert_type.value}'",
        )

    if payload.alert_type.value == "price_level" and payload.direction is None:
        raise HTTPException(
            status_code=422,
            detail="direction (above/below) is required for alert_type 'price_level'",
        )

    try:
        alert = await repository.create(user_id=user_id, data=payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create alert: {exc}") from exc

    return alert


@router.get("", response_model=PriceAlertListResponse)
async def list_price_alerts(
    active_only: bool = Query(False, description="Return only active alerts"),
    current_user: dict = Depends(get_current_user),
    repository: PriceAlertRepository = Depends(get_price_alert_repository),
) -> PriceAlertListResponse:
    """
    List price alerts for the authenticated user.

    Returns all alerts ordered by creation date (newest first).
    Use active_only=true to filter to only un-triggered active alerts.
    """
    user_id = current_user["id"]

    alerts = await repository.list_for_user(user_id=user_id, active_only=active_only)

    active_count = sum(1 for a in alerts if a.is_active)

    return PriceAlertListResponse(
        data=alerts,
        total=len(alerts),
        active_count=active_count,
    )


@router.put("/{alert_id}", response_model=PriceAlert)
async def update_price_alert(
    alert_id: UUID = Path(..., description="Price alert UUID"),
    payload: PriceAlertUpdate = ...,
    current_user: dict = Depends(get_current_user),
    repository: PriceAlertRepository = Depends(get_price_alert_repository),
) -> PriceAlert:
    """
    Update a price alert.

    Only the owning user can update their alerts.
    All fields are optional - only provided fields will be updated.
    """
    user_id = current_user["id"]

    alert = await repository.update(alert_id=alert_id, user_id=user_id, data=payload)

    if alert is None:
        raise HTTPException(status_code=404, detail="Price alert not found or not authorized")

    return alert


@router.delete("/{alert_id}", status_code=204)
async def delete_price_alert(
    alert_id: UUID = Path(..., description="Price alert UUID"),
    current_user: dict = Depends(get_current_user),
    repository: PriceAlertRepository = Depends(get_price_alert_repository),
) -> None:
    """
    Delete a price alert.

    Only the owning user can delete their alerts.
    Returns 204 No Content on success.
    """
    user_id = current_user["id"]

    deleted = await repository.delete(alert_id=alert_id, user_id=user_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Price alert not found or not authorized")
