"""
Broker Dashboard API Routes (Issue 17)

Provides per-broker connection status, account information,
connection testing, and kill switch status for the broker dashboard UI.

Author: Issue P4-I17
"""

from __future__ import annotations

import asyncio
import time
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.dependencies import get_current_user_id

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/brokers", tags=["Broker Dashboard"])

# --- Singleton holders ---

_broker_router = None
_emergency_exit_service = None


def set_broker_router(br: object) -> None:
    """Register the BrokerRouter singleton for route handlers."""
    global _broker_router
    _broker_router = br


def set_emergency_exit_service(service: object) -> None:
    """Register the EmergencyExitService singleton for kill switch status."""
    global _emergency_exit_service
    _emergency_exit_service = service


def _get_broker_router():
    """Get the BrokerRouter, raising 503 if not configured."""
    if _broker_router is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Broker infrastructure not configured",
        )
    return _broker_router


def _get_emergency_exit_service():
    """Get the EmergencyExitService, or None if not configured."""
    return _emergency_exit_service


# --- Response Models ---


class BrokerAccountInfo(BaseModel):
    """Per-broker connection and account status."""

    broker: str = Field(description="Broker identifier: 'mt5' or 'alpaca'")
    connected: bool = Field(description="Whether the broker is currently connected")
    last_connected_at: Optional[str] = Field(
        default=None, description="ISO timestamp of last successful connection"
    )
    platform_name: str = Field(description="Display name of the trading platform")
    account_id: Optional[str] = Field(default=None, description="Account identifier")
    account_balance: Optional[str] = Field(
        default=None, description="Account equity/balance as decimal string"
    )
    buying_power: Optional[str] = Field(
        default=None, description="Available buying power as decimal string"
    )
    cash: Optional[str] = Field(default=None, description="Cash balance as decimal string")
    margin_used: Optional[str] = Field(default=None, description="Margin in use as decimal string")
    margin_available: Optional[str] = Field(
        default=None, description="Available margin as decimal string"
    )
    margin_level_pct: Optional[str] = Field(
        default=None, description="Margin level percentage as decimal string"
    )
    latency_ms: Optional[int] = Field(
        default=None, description="Last measured connection latency in milliseconds"
    )
    error_message: Optional[str] = Field(default=None, description="Error message if disconnected")


class AllBrokersStatus(BaseModel):
    """Aggregated status for all brokers plus kill switch."""

    brokers: list[BrokerAccountInfo] = Field(default_factory=list)
    kill_switch_active: bool = Field(default=False)
    kill_switch_activated_at: Optional[str] = Field(default=None)
    kill_switch_reason: Optional[str] = Field(default=None)


class ConnectionTestResult(BaseModel):
    """Result of a broker connection test."""

    broker: str
    success: bool
    latency_ms: Optional[int] = None
    error_message: Optional[str] = None


# --- Helpers ---


def _decimal_to_str(val: Optional[Decimal]) -> Optional[str]:
    """Convert Decimal to string for JSON serialization, or None."""
    if val is None:
        return None
    return str(val)


async def _build_broker_info(
    broker_key: str,
    adapter: object,
    platform_name: str,
) -> BrokerAccountInfo:
    """Build BrokerAccountInfo for a single adapter."""
    connected = adapter.is_connected() if adapter else False

    account_info: dict = {}
    if adapter and connected:
        try:
            account_info = await asyncio.wait_for(adapter.get_account_info(), timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning("broker_account_info_timeout", broker=broker_key)
        except Exception as e:
            logger.warning(
                "broker_dashboard_account_info_failed",
                broker=broker_key,
                error=str(e),
            )

    return BrokerAccountInfo(
        broker=broker_key,
        connected=connected,
        last_connected_at=adapter.connected_at.isoformat()
        if adapter and hasattr(adapter, "connected_at") and adapter.connected_at
        else None,
        platform_name=platform_name,
        account_id=account_info.get("account_id"),
        account_balance=_decimal_to_str(account_info.get("balance")),
        buying_power=_decimal_to_str(account_info.get("buying_power")),
        cash=_decimal_to_str(account_info.get("cash")),
        margin_used=_decimal_to_str(account_info.get("margin_used")),
        margin_available=_decimal_to_str(account_info.get("margin_available")),
        margin_level_pct=_decimal_to_str(account_info.get("margin_level_pct")),
        error_message="Not connected"
        if not connected and adapter
        else ("Adapter not configured" if not adapter else None),
    )


# --- Endpoints ---


@router.get(
    "/status",
    response_model=AllBrokersStatus,
    summary="Get all broker statuses with account info",
)
async def get_all_brokers_status(
    _user_id: UUID = Depends(get_current_user_id),
) -> AllBrokersStatus:
    """Return connection status and account info for all configured brokers."""
    br = _get_broker_router()

    results = await asyncio.gather(
        _build_broker_info("mt5", br._mt5_adapter, "MetaTrader 5"),
        _build_broker_info("alpaca", br._alpaca_adapter, "Alpaca"),
        return_exceptions=True,
    )
    brokers: list[BrokerAccountInfo] = []
    for r in results:
        if isinstance(r, Exception):
            logger.warning("broker_info_fetch_failed", error=str(r))
        elif isinstance(r, BrokerAccountInfo):
            brokers.append(r)

    # Kill switch status - read from EmergencyExitService (authoritative source)
    # to stay in sync with the kill_switch.py endpoints that write through it
    exit_svc = _get_emergency_exit_service()
    if exit_svc is not None:
        ks = exit_svc.get_kill_switch_status()
    else:
        # Fallback to BrokerRouter if EmergencyExitService not wired
        ks = br.get_kill_switch_status()

    logger.info("broker_dashboard_status_requested", broker_count=len(brokers))

    return AllBrokersStatus(
        brokers=brokers,
        kill_switch_active=ks.get("active", False),
        kill_switch_activated_at=ks.get("activated_at"),
        kill_switch_reason=ks.get("reason"),
    )


@router.get(
    "/{broker}/status",
    response_model=BrokerAccountInfo,
    summary="Get single broker detailed status",
)
async def get_broker_status(
    broker: Literal["mt5", "alpaca"],
    _user_id: UUID = Depends(get_current_user_id),
) -> BrokerAccountInfo:
    """Return detailed status for a single broker."""
    br = _get_broker_router()

    if broker == "mt5":
        adapter = br._mt5_adapter
        platform_name = "MetaTrader 5"
    else:
        adapter = br._alpaca_adapter
        platform_name = "Alpaca"

    return await _build_broker_info(broker, adapter, platform_name)


@router.post(
    "/{broker}/test",
    response_model=ConnectionTestResult,
    summary="Test broker connection and measure latency",
)
async def test_broker_connection(
    broker: Literal["mt5", "alpaca"],
    _user_id: UUID = Depends(get_current_user_id),
) -> ConnectionTestResult:
    """Ping the broker and return latency."""
    br = _get_broker_router()

    if broker == "mt5":
        adapter = br._mt5_adapter
    else:
        adapter = br._alpaca_adapter

    if adapter is None:
        return ConnectionTestResult(
            broker=broker,
            success=False,
            error_message=f"{broker} adapter not configured",
        )

    try:
        start = time.monotonic()
        # Use get_account_info as a lightweight ping, with timeout matching _build_broker_info
        await asyncio.wait_for(adapter.get_account_info(), timeout=10.0)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        connected = adapter.is_connected()

        logger.info(
            "broker_connection_test",
            broker=broker,
            success=connected,
            latency_ms=elapsed_ms,
        )

        return ConnectionTestResult(
            broker=broker,
            success=connected,
            latency_ms=elapsed_ms,
            error_message=None if connected else "Adapter reports disconnected",
        )
    except asyncio.TimeoutError:
        logger.warning("broker_connection_test_timeout", broker=broker)
        return ConnectionTestResult(
            broker=broker,
            success=False,
            latency_ms=None,
            error_message="Connection timed out after 10 seconds",
        )
    except Exception as e:
        logger.warning("broker_connection_test_failed", broker=broker, error=str(e))
        return ConnectionTestResult(
            broker=broker,
            success=False,
            error_message=str(e),
        )


@router.post(
    "/{broker}/connect",
    response_model=BrokerAccountInfo,
    summary="Reconnect to a broker",
)
async def connect_broker(
    broker: Literal["mt5", "alpaca"],
    _user_id: UUID = Depends(get_current_user_id),
) -> BrokerAccountInfo:
    """Attempt to reconnect to a broker using server-side credentials."""
    br = _get_broker_router()

    if broker == "mt5":
        adapter = br._mt5_adapter
        platform_name = "MetaTrader 5"
    else:
        adapter = br._alpaca_adapter
        platform_name = "Alpaca"

    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{broker} adapter not configured - check server credentials",
        )

    try:
        await adapter.connect()
        logger.info("broker_dashboard_connect_success", broker=broker)
    except Exception as e:
        logger.error("broker_dashboard_connect_failed", broker=broker, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to connect to {broker}. Check server credentials and configuration.",
        ) from e

    return await _build_broker_info(broker, adapter, platform_name)


@router.post(
    "/{broker}/disconnect",
    response_model=BrokerAccountInfo,
    summary="Disconnect from a broker",
)
async def disconnect_broker(
    broker: Literal["mt5", "alpaca"],
    _user_id: UUID = Depends(get_current_user_id),
) -> BrokerAccountInfo:
    """Gracefully disconnect from a broker."""
    br = _get_broker_router()

    if broker == "mt5":
        adapter = br._mt5_adapter
        platform_name = "MetaTrader 5"
    else:
        adapter = br._alpaca_adapter
        platform_name = "Alpaca"

    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{broker} adapter not configured",
        )

    try:
        await adapter.disconnect()
        logger.info("broker_dashboard_disconnect_success", broker=broker)
    except Exception as e:
        logger.warning("broker_dashboard_disconnect_failed", broker=broker, error=str(e))

    return await _build_broker_info(broker, adapter, platform_name)
