"""
Scanner Persistence Models (Story 20.1).

Pydantic models for scanner database persistence including:
- WatchlistSymbol: Symbol entry in scanner watchlist
- WatchlistSymbolCreate: Input for adding symbols
- ScannerConfig: Scanner configuration
- ScannerConfigUpdate: Input for updating config
- ScannerHistory: Scan cycle history record
- ScanCycleStatus: Enum for cycle status

These models define the schema for scanner state persistence.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Symbol validation pattern: uppercase alphanumeric with ./^- allowed
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9./^-]+$")


class Timeframe(str, Enum):
    """Valid timeframes for scanner watchlist."""

    M1 = "1M"
    M5 = "5M"
    M15 = "15M"
    M30 = "30M"
    H1 = "1H"
    H4 = "4H"
    D1 = "1D"
    W1 = "1W"


class AssetClass(str, Enum):
    """Valid asset classes for scanner watchlist."""

    FOREX = "forex"
    STOCK = "stock"
    INDEX = "index"
    CRYPTO = "crypto"


class ScanCycleStatus(str, Enum):
    """Status of a scan cycle."""

    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    FILTERED = "FILTERED"  # Story 20.4: All symbols were filtered/skipped


def validate_symbol(symbol: str) -> str:
    """
    Validate symbol format.

    Args:
        symbol: Symbol string to validate

    Returns:
        Validated symbol (uppercase)

    Raises:
        ValueError: If symbol is invalid
    """
    if not symbol:
        raise ValueError("Symbol cannot be empty")
    symbol = symbol.upper()
    if len(symbol) > 20:
        raise ValueError("Symbol must be 1-20 characters")
    if not SYMBOL_PATTERN.match(symbol):
        raise ValueError("Symbol must be uppercase alphanumeric with ./^- allowed")
    return symbol


class WatchlistSymbol(BaseModel):
    """
    Symbol entry in scanner watchlist.

    Represents a symbol that the scanner should process.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Unique identifier")
    symbol: Annotated[str, Field(min_length=1, max_length=20, description="Symbol ticker")]
    timeframe: Timeframe = Field(description="Timeframe for scanning")
    asset_class: AssetClass = Field(description="Asset class")
    enabled: bool = Field(default=True, description="Whether symbol is actively scanned")
    last_scanned_at: datetime | None = Field(default=None, description="Last scan timestamp")
    created_at: datetime = Field(description="When symbol was added")
    updated_at: datetime = Field(description="When symbol was last modified")

    @field_validator("symbol", mode="before")
    @classmethod
    def validate_symbol_format(cls, v: str) -> str:
        """Validate and uppercase symbol."""
        return validate_symbol(v)


class WatchlistSymbolCreate(BaseModel):
    """
    Input schema for adding a symbol to watchlist.

    Only requires symbol, timeframe, and asset_class.
    Input is normalized: symbol -> uppercase, timeframe -> uppercase, asset_class -> lowercase.
    """

    symbol: Annotated[str, Field(min_length=1, max_length=20, description="Symbol ticker")]
    timeframe: Timeframe = Field(description="Timeframe for scanning")
    asset_class: AssetClass = Field(description="Asset class")

    @field_validator("symbol", mode="before")
    @classmethod
    def validate_symbol_format(cls, v: str) -> str:
        """Validate and uppercase symbol."""
        return validate_symbol(v)

    @field_validator("timeframe", mode="before")
    @classmethod
    def normalize_timeframe(cls, v: str | Timeframe) -> str:
        """Normalize timeframe to uppercase before enum conversion."""
        if isinstance(v, Timeframe):
            return v.value
        return v.upper() if isinstance(v, str) else v

    @field_validator("asset_class", mode="before")
    @classmethod
    def normalize_asset_class(cls, v: str | AssetClass) -> str:
        """Normalize asset_class to lowercase before enum conversion."""
        if isinstance(v, AssetClass):
            return v.value
        return v.lower() if isinstance(v, str) else v


class WatchlistSymbolUpdate(BaseModel):
    """
    Input schema for updating a watchlist symbol (PATCH request).

    Used to toggle the enabled state of a symbol.
    """

    enabled: bool = Field(description="New enabled state for the symbol")


class ScannerConfig(BaseModel):
    """
    Scanner configuration (singleton).

    Controls scanner behavior including scan interval,
    batch size, and session filtering.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Config ID (singleton)")
    scan_interval_seconds: Annotated[
        int, Field(ge=60, description="Scan interval (min 60 seconds)")
    ] = 300
    batch_size: Annotated[int, Field(ge=1, le=50, description="Symbols per batch (1-50)")] = 10
    session_filter_enabled: bool = Field(default=True, description="Filter by trading session")
    is_running: bool = Field(default=False, description="Scanner running state")
    last_cycle_at: datetime | None = Field(default=None, description="Last completed cycle")
    updated_at: datetime = Field(description="Last config update")


class ScannerConfigUpdate(BaseModel):
    """
    Input schema for updating scanner config.

    All fields are optional - only provided fields are updated.
    """

    scan_interval_seconds: Annotated[
        int | None, Field(ge=60, description="Scan interval (min 60 seconds)")
    ] = None
    batch_size: Annotated[
        int | None, Field(ge=1, le=50, description="Symbols per batch (1-50)")
    ] = None
    session_filter_enabled: bool | None = Field(
        default=None, description="Filter by trading session"
    )
    is_running: bool | None = Field(default=None, description="Scanner running state")


class ScannerHistory(BaseModel):
    """
    Scan cycle history record.

    Records the results of a single scan cycle for
    monitoring and debugging.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="History entry ID")
    cycle_started_at: datetime = Field(description="Cycle start time")
    cycle_ended_at: datetime | None = Field(default=None, description="Cycle end time")
    symbols_scanned: Annotated[int, Field(ge=0, description="Symbols processed")] = 0
    signals_generated: Annotated[int, Field(ge=0, description="Signals created")] = 0
    errors_count: Annotated[int, Field(ge=0, description="Errors encountered")] = 0
    status: ScanCycleStatus = Field(description="Cycle outcome")
    # Story 20.4: Skip tracking
    symbols_skipped_session: Annotated[
        int, Field(ge=0, description="Symbols skipped due to session filter")
    ] = 0
    symbols_skipped_rate_limit: Annotated[
        int, Field(ge=0, description="Symbols skipped due to rate limiting")
    ] = 0


class ScannerHistoryCreate(BaseModel):
    """
    Input schema for creating a history entry.

    Used to record a completed scan cycle.
    """

    cycle_started_at: datetime = Field(description="Cycle start time")
    cycle_ended_at: datetime | None = Field(default=None, description="Cycle end time")
    symbols_scanned: Annotated[int, Field(ge=0, description="Symbols processed")] = 0
    signals_generated: Annotated[int, Field(ge=0, description="Signals created")] = 0
    errors_count: Annotated[int, Field(ge=0, description="Errors encountered")] = 0
    status: ScanCycleStatus = Field(description="Cycle outcome")
    # Story 20.4: Skip tracking
    symbols_skipped_session: Annotated[
        int, Field(ge=0, description="Symbols skipped due to session filter")
    ] = 0
    symbols_skipped_rate_limit: Annotated[
        int, Field(ge=0, description="Symbols skipped due to rate limiting")
    ] = 0


# =========================================
# Scanner Control API Models (Story 20.5a)
# =========================================


class ScannerActionResponse(BaseModel):
    """
    Response for scanner start/stop actions (Story 20.5a AC1, AC2).

    Returns action status and current running state.
    """

    status: str = Field(
        description="Action result: 'started', 'stopped', 'already_running', 'already_stopped'"
    )
    message: str = Field(description="Human-readable status message")
    is_running: bool = Field(description="Current scanner running state")


class ScannerControlStatusResponse(BaseModel):
    """
    Scanner status response for control API (Story 20.5a AC3).

    Provides current state, timing information, and configuration.
    """

    is_running: bool = Field(description="Whether scanner is actively running")
    current_state: str = Field(
        description="Current state: stopped, starting, running, waiting, scanning, stopping"
    )
    last_cycle_at: datetime | None = Field(
        default=None, description="When last scan cycle completed"
    )
    next_scan_in_seconds: int | None = Field(
        default=None, description="Seconds until next scan (None if stopped)"
    )
    symbols_count: int = Field(description="Number of enabled symbols in watchlist")
    scan_interval_seconds: int = Field(description="Configured scan interval")
    session_filter_enabled: bool = Field(description="Whether session filtering is enabled")


class ScannerHistoryResponse(BaseModel):
    """
    Scanner history response (Story 20.5a AC4).

    Returns scan cycle history records.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="History entry ID")
    cycle_started_at: datetime = Field(description="Cycle start time")
    cycle_ended_at: datetime | None = Field(default=None, description="Cycle end time")
    symbols_scanned: int = Field(ge=0, description="Symbols processed")
    signals_generated: int = Field(ge=0, description="Signals created")
    errors_count: int = Field(ge=0, description="Errors encountered")
    status: str = Field(description="Cycle outcome: COMPLETED, PARTIAL, FAILED, SKIPPED")


class ScannerConfigUpdateRequest(BaseModel):
    """
    Request schema for updating scanner config via API (Story 20.5a AC5, AC6).

    All fields are optional. Includes validation constraints:
    - scan_interval_seconds: 60-3600
    - batch_size: 1-50
    """

    scan_interval_seconds: Annotated[
        int | None, Field(ge=60, le=3600, description="Scan interval (60-3600 seconds)")
    ] = None
    batch_size: Annotated[
        int | None, Field(ge=1, le=50, description="Symbols per batch (1-50)")
    ] = None
    session_filter_enabled: bool | None = Field(
        default=None, description="Filter by trading session"
    )
