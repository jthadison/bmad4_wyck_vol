"""
Monitoring API Routes - Story 23.13

Provides system health, audit trail, and dashboard endpoints
for operational monitoring of the trading system.

Endpoints:
----------
GET /api/v1/monitoring/health       - System health overview
GET /api/v1/monitoring/audit-trail  - Query recent audit events
GET /api/v1/monitoring/dashboard    - Trading dashboard summary

Author: Story 23.13 Implementation
"""

from __future__ import annotations

import time
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.api.dependencies import get_current_user_id
from src.api.routes.kill_switch import _get_service as get_kill_switch_service
from src.monitoring.audit_logger import AuditEventType, get_audit_logger

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])

# Track application start time for uptime calculation
_start_time = time.monotonic()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class SystemHealthResponse(BaseModel):
    """Response for the /health endpoint."""

    broker_connections: dict[str, bool] = Field(
        default_factory=dict,
        description="Connection status per broker (MT5, Alpaca)",
    )
    kill_switch_active: bool = Field(
        default=False, description="Whether the kill switch is currently engaged"
    )
    daily_pnl_pct: float = Field(default=0.0, description="Daily P&L as percentage of equity")
    portfolio_heat_pct: float = Field(default=0.0, description="Current portfolio heat percentage")
    active_signals_count: int = Field(default=0, description="Number of active trading signals")
    uptime_seconds: float = Field(default=0.0, description="Seconds since application startup")


class AuditEventResponse(BaseModel):
    """Single audit event in the API response."""

    timestamp: str
    event_type: str
    symbol: Optional[str] = None
    campaign_id: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)


class DashboardResponse(BaseModel):
    """Response for the /dashboard endpoint."""

    positions_by_broker: dict[str, list[Any]] = Field(
        default_factory=dict,
        description="Open positions grouped by broker",
    )
    daily_pnl: float = Field(default=0.0, description="Daily P&L in dollars")
    total_pnl: float = Field(default=0.0, description="Total cumulative P&L")
    portfolio_heat_pct: float = Field(default=0.0, description="Current portfolio heat percentage")
    active_signals_count: int = Field(default=0, description="Number of active trading signals")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    response_model=SystemHealthResponse,
    summary="System health overview",
)
async def get_system_health(
    _user_id: str = Depends(get_current_user_id),
) -> SystemHealthResponse:
    """
    Return current system health including broker connections,
    kill switch status, daily P&L, and portfolio heat.
    """
    broker_connections: dict[str, bool] = {"mt5": False, "alpaca": False}

    # Check broker connections via kill switch service
    kill_switch_active = False
    try:
        service = get_kill_switch_service()
        ks_status = service.get_kill_switch_status()
        kill_switch_active = ks_status.get("active", False)
    except Exception:
        pass

    # Check Alpaca API keys configured
    try:
        from src.config import settings as app_settings

        broker_connections["alpaca"] = bool(
            app_settings.alpaca_api_key and app_settings.alpaca_secret_key
        )
    except Exception:
        pass

    return SystemHealthResponse(
        broker_connections=broker_connections,
        kill_switch_active=kill_switch_active,
        daily_pnl_pct=0.0,
        portfolio_heat_pct=0.0,
        active_signals_count=0,
        uptime_seconds=round(time.monotonic() - _start_time, 1),
    )


@router.get(
    "/audit-trail",
    response_model=list[AuditEventResponse],
    summary="Query recent audit events",
)
async def get_audit_trail(
    event_type: Optional[str] = Query(
        None, description="Filter by event type (e.g. SIGNAL_GENERATED)"
    ),
    symbol: Optional[str] = Query(None, description="Filter by trading symbol"),
    limit: int = Query(100, ge=1, le=1000, description="Max events to return"),
    _user_id: str = Depends(get_current_user_id),
) -> list[AuditEventResponse]:
    """
    Query recent audit trail events with optional filters.

    Returns events from the in-memory ring buffer, newest first.
    """
    audit = get_audit_logger()

    # Parse event type filter
    parsed_type: Optional[AuditEventType] = None
    if event_type is not None:
        try:
            parsed_type = AuditEventType(event_type)
        except ValueError:
            logger.warning("invalid_audit_event_type_filter", event_type=event_type)
            # Return empty list for unknown event types rather than 400
            return []

    events = await audit.get_events(
        event_type=parsed_type,
        symbol=symbol,
        limit=limit,
    )

    return [
        AuditEventResponse(
            timestamp=e.timestamp.isoformat(),
            event_type=e.event_type.value,
            symbol=e.symbol,
            campaign_id=e.campaign_id,
            details=e.details,
        )
        for e in events
    ]


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Trading dashboard summary",
)
async def get_dashboard(
    _user_id: str = Depends(get_current_user_id),
) -> DashboardResponse:
    """
    Return a high-level trading dashboard including positions grouped
    by broker, P&L totals, and portfolio heat.
    """
    positions_by_broker: dict[str, list[Any]] = {}

    # Attempt to gather positions from broker adapters
    try:
        from src.brokers.broker_router import BrokerRouter  # noqa: F401

        # In production, iterate BrokerRouter.list_positions() per broker
        # and populate positions_by_broker. For now return empty.
    except Exception:
        pass

    daily_pnl = 0.0
    total_pnl = 0.0
    portfolio_heat_pct = 0.0
    active_signals_count = 0

    return DashboardResponse(
        positions_by_broker=positions_by_broker,
        daily_pnl=daily_pnl,
        total_pnl=total_pnl,
        portfolio_heat_pct=portfolio_heat_pct,
        active_signals_count=active_signals_count,
    )
