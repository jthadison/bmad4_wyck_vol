"""
Watchlist Management Models (Story 19.12)

Purpose:
--------
Provides Pydantic models for user watchlist management.
Enables users to configure which symbols the system monitors.

Data Models:
------------
- WatchlistPriority: Priority levels for watchlist symbols
- WatchlistEntry: Single watchlist item
- WatchlistResponse: Response for GET /api/watchlist
- AddSymbolRequest: Request for POST /api/watchlist
- UpdateSymbolRequest: Request for PATCH /api/watchlist/{symbol}

Features:
---------
- Symbol priority levels (low, medium, high)
- Optional minimum confidence threshold per symbol
- Enable/disable symbols without removal
- Max 100 symbols per user

Author: Story 19.12
"""

import re
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator

# Valid stock symbol pattern: 1-5 uppercase letters, optional .X suffix for share classes
SYMBOL_PATTERN = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")


class WatchlistPriority(str, Enum):
    """Priority levels for watchlist symbols."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class WatchlistEntry(BaseModel):
    """
    Single watchlist entry.

    Fields:
    -------
    - symbol: Trading symbol (e.g., AAPL, TSLA)
    - priority: Signal priority level
    - min_confidence: Minimum confidence score filter (optional, 60-100%)
    - enabled: Whether symbol is actively monitored
    - added_at: When symbol was added to watchlist

    Example:
    --------
    >>> entry = WatchlistEntry(
    ...     symbol="AAPL",
    ...     priority=WatchlistPriority.HIGH,
    ...     min_confidence=Decimal("85.0"),
    ...     enabled=True,
    ...     added_at=datetime.now(UTC)
    ... )
    """

    symbol: str = Field(..., max_length=10, description="Trading symbol")
    priority: WatchlistPriority = Field(
        default=WatchlistPriority.MEDIUM, description="Signal priority level"
    )
    min_confidence: Decimal | None = Field(
        None,
        ge=60,
        le=100,
        decimal_places=2,
        max_digits=5,
        description="Minimum confidence filter (60-100%). Must be at least 60%.",
    )
    enabled: bool = Field(default=True, description="Whether symbol is actively monitored")
    added_at: datetime = Field(..., description="When symbol was added (UTC)")

    @field_validator("added_at", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | str) -> datetime:
        """Enforce UTC timezone."""
        if isinstance(v, str):
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    @field_validator("symbol", mode="before")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate and normalize symbol format."""
        if not isinstance(v, str):
            raise ValueError("Symbol must be a string")
        symbol = v.upper().strip()
        if not SYMBOL_PATTERN.match(symbol):
            raise ValueError(
                f"Invalid symbol format: {symbol}. "
                "Must be 1-5 letters, optionally followed by .X for share class"
            )
        return symbol

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
            Decimal: str,
        }
    }


class WatchlistResponse(BaseModel):
    """
    Response for GET /api/watchlist.

    Fields:
    -------
    - symbols: List of watchlist entries
    - count: Current number of symbols
    - max_allowed: Maximum allowed symbols

    Example:
    --------
    >>> response = WatchlistResponse(
    ...     symbols=[entry1, entry2],
    ...     count=2,
    ...     max_allowed=100
    ... )
    """

    symbols: list[WatchlistEntry] = Field(..., description="Watchlist entries")
    count: int = Field(..., ge=0, description="Current symbol count")
    max_allowed: int = Field(default=100, description="Maximum allowed symbols")

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
            Decimal: str,
        }
    }


class AddSymbolRequest(BaseModel):
    """
    Request for POST /api/watchlist.

    Fields:
    -------
    - symbol: Trading symbol to add
    - priority: Signal priority level (default: medium)
    - min_confidence: Minimum confidence filter (optional, 60-100%)

    Example:
    --------
    >>> request = AddSymbolRequest(
    ...     symbol="GOOGL",
    ...     priority=WatchlistPriority.MEDIUM,
    ...     min_confidence=None
    ... )
    """

    symbol: str = Field(..., max_length=10, min_length=1, description="Trading symbol to add")
    priority: WatchlistPriority = Field(
        default=WatchlistPriority.MEDIUM, description="Signal priority level"
    )
    min_confidence: Decimal | None = Field(
        None,
        ge=60,
        le=100,
        decimal_places=2,
        max_digits=5,
        description="Minimum confidence filter (60-100%). Must be at least 60%.",
    )

    @field_validator("symbol", mode="before")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate and normalize symbol format."""
        if not isinstance(v, str):
            raise ValueError("Symbol must be a string")
        symbol = v.upper().strip()
        if not SYMBOL_PATTERN.match(symbol):
            raise ValueError(
                f"Invalid symbol format: {symbol}. "
                "Must be 1-5 letters, optionally followed by .X for share class"
            )
        return symbol

    model_config = {"json_encoders": {Decimal: str}}


class UpdateSymbolRequest(BaseModel):
    """
    Request for PATCH /api/watchlist/{symbol}.

    All fields are optional - only provided fields are updated.

    Fields:
    -------
    - priority: New priority level (optional)
    - min_confidence: New minimum confidence (optional, 60-100%)
    - enabled: Enable/disable symbol (optional)

    Example:
    --------
    >>> request = UpdateSymbolRequest(
    ...     priority=WatchlistPriority.HIGH,
    ...     min_confidence=Decimal("85.0")
    ... )
    """

    priority: WatchlistPriority | None = Field(None, description="New priority level")
    min_confidence: Decimal | None = Field(
        None,
        ge=60,
        le=100,
        decimal_places=2,
        max_digits=5,
        description="New minimum confidence (60-100%). Must be at least 60%.",
    )
    enabled: bool | None = Field(None, description="Enable/disable symbol")

    model_config = {"json_encoders": {Decimal: str}}


# Default watchlist for new users
DEFAULT_WATCHLIST_SYMBOLS = ["AAPL", "TSLA", "SPY", "QQQ", "NVDA", "MSFT", "AMZN"]

# Maximum symbols per user
MAX_WATCHLIST_SYMBOLS = 100
