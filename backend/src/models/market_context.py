"""
Market context data models for strategy validation.

This module provides data models for representing market conditions, news events,
and invalidation history used by the StrategyValidator (Story 8.7).

Models:
    - AssetClass: STOCK, FOREX, CRYPTO enumeration
    - MarketRegime: TRENDING_UP, TRENDING_DOWN, SIDEWAYS, HIGH_VOLATILITY
    - ForexSession: ASIAN, LONDON, NY, OVERLAP
    - InvalidationEvent: Campaign stop-out tracking
    - NewsEvent: Base class for news events
    - EarningsEvent: Stock earnings announcements (FR29)
    - ForexNewsEvent: Forex high-impact economic events
    - MarketContext: Aggregated market conditions for strategy validation
"""

from datetime import UTC, datetime, time
from decimal import Decimal
from enum import Enum
from typing import ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


class AssetClass(str, Enum):
    """Asset class enumeration for multi-asset validation."""

    STOCK = "STOCK"  # Equity securities
    FOREX = "FOREX"  # Currency pairs
    CRYPTO = "CRYPTO"  # Cryptocurrencies (future support)


class MarketRegime(str, Enum):
    """Market regime classification for strategy validation."""

    TRENDING_UP = "TRENDING_UP"  # Strong uptrend: ADX > 25, price > 20 SMA
    TRENDING_DOWN = "TRENDING_DOWN"  # Strong downtrend: ADX > 25, price < 20 SMA
    SIDEWAYS = "SIDEWAYS"  # Ranging/choppy: ADX < 25
    HIGH_VOLATILITY = "HIGH_VOLATILITY"  # Extreme volatility: ATR > threshold


class ForexSession(str, Enum):
    """Forex trading session enumeration (NEW - AC: 12)."""

    ASIAN = "ASIAN"  # 7pm-4am EST (low liquidity)
    LONDON = "LONDON"  # 3am-12pm EST (high liquidity)
    NY = "NY"  # 8am-5pm EST (highest liquidity)
    OVERLAP = "OVERLAP"  # 8am-12pm EST (London+NY, peak activity)


class InvalidationEvent(BaseModel):
    """
    Record of a pattern/campaign that was invalidated (stop-out).

    Tracks failed campaigns to prevent immediate re-entry (AC: 2).
    Wyckoff principle: Respect invalidations, wait for new structure.
    """

    campaign_id: str = Field(..., description="Campaign that failed")
    symbol: str = Field(..., max_length=20)
    pattern_type: str = Field(..., description="Pattern that failed: SPRING, SOS, LPS, UTAD")
    invalidation_date: datetime = Field(..., description="When stop-out occurred (UTC)")
    invalidation_reason: str = Field(
        ..., description="Why pattern failed (e.g., 'Spring low broken')"
    )
    trading_range_id: UUID = Field(..., description="Which trading range invalidated")

    @computed_field  # type: ignore[misc]
    @property
    def days_ago(self) -> float:
        """Calculate how many days ago invalidation occurred."""
        delta = datetime.now(UTC) - self.invalidation_date
        return delta.total_seconds() / 86400  # Convert seconds to days

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: str}


class NewsEvent(BaseModel):
    """
    Base class for news events (earnings, forex news).

    Used for FR29 earnings blackout and forex high-impact event validation.
    """

    symbol: str = Field(..., description="Trading symbol or currency pair")
    event_date: datetime = Field(..., description="Scheduled event time (UTC)")
    event_type: str = Field(
        ...,
        description=("EARNINGS | NFP | FOMC | ECB | BOJ | GDP | CPI | UNEMPLOYMENT | etc."),
    )
    impact_level: Literal["LOW", "MEDIUM", "HIGH"] = Field(
        ..., description="Expected market impact"
    )
    description: str = Field(..., description="Human-readable event description")

    @computed_field  # type: ignore[misc]
    @property
    def hours_until_event(self) -> float:
        """Calculate hours until event."""
        delta = self.event_date - datetime.now(UTC)
        return delta.total_seconds() / 3600  # Convert seconds to hours

    @computed_field  # type: ignore[misc]
    @property
    def within_blackout_window(self) -> bool:
        """
        Check if within blackout window (asset-class-specific).

        This is a base implementation. Subclasses should override with
        asset-class-specific logic.
        """
        return False  # Subclasses override

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class EarningsEvent(NewsEvent):
    """
    Upcoming earnings announcement for a stock (FR29).

    Blackout window: 24 hours before OR 2 hours after announcement.
    """

    fiscal_quarter: str = Field(..., description="e.g., 'Q1 2024', 'Q3 2023'")
    estimated_eps: Decimal | None = Field(
        default=None, description="Estimated earnings per share (if available)"
    )

    @computed_field  # type: ignore[misc]
    @property
    def within_blackout_window(self) -> bool:
        """
        Check if within FR29 blackout window (24hr before or 2hr after).

        Returns:
            True if within blackout window, False otherwise
        """
        hours = self.hours_until_event
        return -2.0 <= hours <= 24.0  # 24 hours before, 2 hours after

    class Config:
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}


class ForexNewsEvent(NewsEvent):
    """
    Forex high-impact economic event (NEW - AC: 14).

    Blackout windows are event-specific:
    - NFP: 6 hours before, 2 hours after (highest volatility)
    - FOMC: 4 hours before, 2 hours after
    - CPI/GDP: 2 hours before, 1 hour after
    """

    affected_currencies: list[str] = Field(..., description="e.g., ['USD', 'EUR'] for FOMC")
    previous_value: str | None = Field(
        default=None, description="Previous release value (for economic data)"
    )
    forecast_value: str | None = Field(default=None, description="Forecast consensus")

    # Event-specific blackout windows (hours before, hours after)
    EVENT_BLACKOUT_WINDOWS: ClassVar[dict] = {
        "NFP": (6.0, 2.0),  # Non-Farm Payrolls - highest volatility
        "FOMC": (4.0, 2.0),  # Federal Reserve rate decision
        "ECB_RATE_DECISION": (4.0, 1.0),  # European Central Bank
        "BOJ_RATE_DECISION": (4.0, 1.0),  # Bank of Japan
        "CPI": (2.0, 1.0),  # Consumer Price Index
        "GDP": (2.0, 1.0),  # Gross Domestic Product
        "UNEMPLOYMENT": (2.0, 1.0),  # Unemployment rate
    }

    @computed_field  # type: ignore[misc]
    @property
    def within_blackout_window(self) -> bool:
        """
        Check if within event-specific blackout window.

        Different events have different blackout windows based on volatility impact.

        Returns:
            True if within blackout window, False otherwise
        """
        hours = self.hours_until_event

        # Get event-specific window, default to 4hr before / 1hr after
        hours_before, hours_after = self.EVENT_BLACKOUT_WINDOWS.get(self.event_type, (4.0, 1.0))

        return -hours_after <= hours <= hours_before

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class MarketContext(BaseModel):
    """
    Market conditions and context for strategy validation (Story 8.7).

    Aggregates all market state needed for William's strategic checks:
    - Volatility metrics (from Epic 2 VolumeAnalyzer)
    - Market regime (from ADX and trend analysis)
    - Recent invalidations (from Epic 7 campaign tracking)
    - Time-based context (session, time of day)
    - News events (FR29 earnings calendar, forex news)
    """

    asset_class: AssetClass = Field(..., description="STOCK or FOREX (NEW - AC: 11)")
    symbol: str = Field(..., max_length=20)

    # Volatility metrics (from Epic 2 VolumeAnalyzer)
    current_volatility: Decimal = Field(..., description="ATR as percentage of price", ge=0)
    volatility_percentile: int = Field(
        ..., description="Where ATR ranks vs 20-day range (0-100)", ge=0, le=100
    )
    volume_percentile: int = Field(
        ...,
        description="Where is current volume vs 20-day range (0-100) (Victoria enhancement)",
        ge=0,
        le=100,
    )

    # Market regime (derived from ADX and trend)
    market_regime: MarketRegime = Field(..., description="Current market classification")
    adx: Decimal | None = Field(
        default=None, description="Average Directional Index (trend strength indicator)"
    )

    # Invalidation history (from Epic 7 campaign tracking)
    recent_invalidations: list[InvalidationEvent] = Field(
        default_factory=list, description="Recent stop-outs in this symbol"
    )

    # Timing information
    time_of_day: time = Field(..., description="Current market time (HH:MM in market timezone)")
    market_session: str = Field(..., description="PRE_MARKET | REGULAR | AFTER_HOURS (stocks only)")
    forex_session: ForexSession | None = Field(
        default=None,
        description="ASIAN/LONDON/NY/OVERLAP (forex only, NEW - AC: 12)",
    )

    # News events (FR29, asset-class-aware)
    news_event: NewsEvent | None = Field(
        default=None, description="Upcoming high-impact event (FR29, asset-class-aware)"
    )

    # Metadata
    data_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this context was calculated",
    )

    @computed_field  # type: ignore[misc]
    @property
    def is_extreme_volatility(self) -> bool:
        """
        Wyckoff: Chaos (wide spreads + erratic volume) vs Controlled Accumulation.

        ENHANCED - Victoria: Check BOTH price volatility (ATR) AND volume volatility.

        Genuine accumulation: Calm markets, steady volume
        Panic/Euphoria: Wide spreads + volume spikes = noise, not opportunity

        Note: High ATR with LOW volume may indicate stopping volume (valid Wyckoff).
        High ATR with HIGH volume indicates chaos/panic (reject).

        Returns:
            True if extreme volatility (chaos), False otherwise
        """
        if self.asset_class == AssetClass.FOREX:
            atr_threshold = 90  # Forex: more frequent spikes
        else:
            atr_threshold = 95  # Stocks: 95th percentile

        # Check BOTH price volatility (ATR) AND volume volatility
        # Wide spreads alone may be stopping volume (valid Wyckoff)
        # Wide spreads + volume spikes = chaos (reject)
        return (
            self.volatility_percentile >= atr_threshold
            and self.volume_percentile >= 85  # Volume also erratic
        )

    @computed_field  # type: ignore[misc]
    @property
    def has_upcoming_news(self) -> bool:
        """Check if news scheduled and within blackout window."""
        return self.news_event is not None and self.news_event.within_blackout_window

    @computed_field  # type: ignore[misc]
    @property
    def is_friday_pm_forex(self) -> bool:
        """
        Check if Friday afternoon forex (weekend gap risk - AC: 13).

        Returns:
            True if Friday after 12pm EST (17:00 UTC)
        """
        if self.asset_class != AssetClass.FOREX:
            return False

        # Get current datetime in UTC
        now = datetime.now(UTC)
        weekday = now.weekday()  # 0=Mon, 4=Fri
        hour = now.hour

        # Friday after 17:00 UTC (12pm EST)
        return weekday == 4 and hour >= 17

    @computed_field  # type: ignore[misc]
    @property
    def is_wednesday_pm_forex(self) -> bool:
        """
        Check if Wednesday PM forex (triple rollover warning - Rachel enhancement).

        Returns:
            True if Wednesday after 17:00 UTC (5pm EST)
        """
        if self.asset_class != AssetClass.FOREX:
            return False

        now = datetime.now(UTC)
        weekday = now.weekday()  # 2=Wednesday
        hour = now.hour

        # Wednesday after 17:00 UTC (5pm EST)
        return weekday == 2 and hour >= 17

    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat(),
            time: lambda v: v.strftime("%H:%M"),
        }
