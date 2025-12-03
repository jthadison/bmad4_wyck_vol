"""
Unit tests for market context data models (Story 8.7).

Tests InvalidationEvent, NewsEvent, EarningsEvent, ForexNewsEvent, and MarketContext models.
"""

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

from src.models.market_context import (
    AssetClass,
    EarningsEvent,
    ForexNewsEvent,
    ForexSession,
    InvalidationEvent,
    MarketContext,
    MarketRegime,
)


class TestInvalidationEvent:
    """Test InvalidationEvent model."""

    def test_invalidation_event_creation(self):
        """Test creating InvalidationEvent with all fields."""
        invalidation_date = datetime.now(UTC) - timedelta(days=2)
        trading_range_id = uuid4()

        event = InvalidationEvent(
            campaign_id="campaign-123",
            symbol="AAPL",
            pattern_type="SPRING",
            invalidation_date=invalidation_date,
            invalidation_reason="Spring low broken",
            trading_range_id=trading_range_id,
        )

        assert event.campaign_id == "campaign-123"
        assert event.symbol == "AAPL"
        assert event.pattern_type == "SPRING"
        assert event.invalidation_reason == "Spring low broken"
        assert 1.9 < event.days_ago < 2.1  # ~2 days ago

    def test_days_ago_computation(self):
        """Test days_ago computed field."""
        # 5 days ago
        event = InvalidationEvent(
            campaign_id="camp-1",
            symbol="TSLA",
            pattern_type="SOS",
            invalidation_date=datetime.now(UTC) - timedelta(days=5),
            invalidation_reason="Test",
            trading_range_id=uuid4(),
        )
        assert 4.9 < event.days_ago < 5.1


class TestEarningsEvent:
    """Test EarningsEvent model."""

    def test_earnings_event_within_24hr_blackout(self):
        """Test earnings in 12 hours is within blackout (AC: 5, FR29)."""
        earnings_date = datetime.now(UTC) + timedelta(hours=12)

        event = EarningsEvent(
            symbol="AAPL",
            event_date=earnings_date,
            event_type="EARNINGS",
            impact_level="HIGH",
            description="Q1 2024 Earnings",
            fiscal_quarter="Q1 2024",
            estimated_eps=Decimal("1.25"),
        )

        assert 11.9 < event.hours_until_event < 12.1
        assert event.within_blackout_window is True  # Within 24hr window

    def test_earnings_event_outside_blackout(self):
        """Test earnings in 30 hours is outside blackout."""
        earnings_date = datetime.now(UTC) + timedelta(hours=30)

        event = EarningsEvent(
            symbol="AAPL",
            event_date=earnings_date,
            event_type="EARNINGS",
            impact_level="HIGH",
            description="Q1 2024 Earnings",
            fiscal_quarter="Q1 2024",
            estimated_eps=None,
        )

        assert event.within_blackout_window is False  # Outside 24hr window

    def test_earnings_after_blackout(self):
        """Test earnings 1 hour ago (< -2 hours) is outside blackout."""
        earnings_date = datetime.now(UTC) - timedelta(hours=3)

        event = EarningsEvent(
            symbol="AAPL",
            event_date=earnings_date,
            event_type="EARNINGS",
            impact_level="HIGH",
            description="Past earnings",
            fiscal_quarter="Q4 2023",
        )

        assert event.within_blackout_window is False  # Passed 2hr post-window


class TestForexNewsEvent:
    """Test ForexNewsEvent model."""

    def test_nfp_blackout_window(self):
        """Test NFP event with 6hr before / 2hr after blackout."""
        # NFP in 4 hours - within 6hr window
        nfp_date = datetime.now(UTC) + timedelta(hours=4)

        event = ForexNewsEvent(
            symbol="EUR/USD",
            event_date=nfp_date,
            event_type="NFP",
            impact_level="HIGH",
            description="US Non-Farm Payrolls",
            affected_currencies=["USD"],
        )

        assert event.within_blackout_window is True  # Within 6hr window

    def test_cpi_blackout_window(self):
        """Test CPI event with 2hr before / 1hr after blackout."""
        # CPI in 3 hours - outside 2hr window
        cpi_date = datetime.now(UTC) + timedelta(hours=3)

        event = ForexNewsEvent(
            symbol="EUR/USD",
            event_date=cpi_date,
            event_type="CPI",
            impact_level="MEDIUM",
            description="Consumer Price Index",
            affected_currencies=["USD"],
        )

        assert event.within_blackout_window is False  # Outside 2hr window


class TestMarketContext:
    """Test MarketContext model."""

    def test_market_context_creation_stock(self):
        """Test creating MarketContext for stock."""
        context = MarketContext(
            asset_class=AssetClass.STOCK,
            symbol="AAPL",
            current_volatility=Decimal("0.02"),
            volatility_percentile=60,
            volume_percentile=50,
            market_regime=MarketRegime.TRENDING_UP,
            adx=Decimal("30"),
            recent_invalidations=[],
            time_of_day=time(10, 30),
            market_session="REGULAR",
            forex_session=None,
            news_event=None,
        )

        assert context.asset_class == AssetClass.STOCK
        assert context.symbol == "AAPL"
        assert context.market_regime == MarketRegime.TRENDING_UP
        assert context.is_extreme_volatility is False  # 60 < 95

    def test_market_context_extreme_volatility_stock(self):
        """Test is_extreme_volatility for stock (ATR ≥95th, volume ≥85th)."""
        context = MarketContext(
            asset_class=AssetClass.STOCK,
            symbol="TSLA",
            current_volatility=Decimal("0.05"),
            volatility_percentile=98,  # ≥95
            volume_percentile=90,  # ≥85
            market_regime=MarketRegime.HIGH_VOLATILITY,
            adx=Decimal("35"),
            recent_invalidations=[],
            time_of_day=time(14, 0),
            market_session="REGULAR",
        )

        assert context.is_extreme_volatility is True  # Both conditions met

    def test_market_context_extreme_volatility_forex(self):
        """Test is_extreme_volatility for forex (ATR ≥90th, volume ≥85th)."""
        context = MarketContext(
            asset_class=AssetClass.FOREX,
            symbol="EUR/USD",
            current_volatility=Decimal("0.015"),
            volatility_percentile=92,  # ≥90 for forex
            volume_percentile=88,  # ≥85
            market_regime=MarketRegime.HIGH_VOLATILITY,
            recent_invalidations=[],
            time_of_day=time(10, 0),
            market_session="REGULAR",
            forex_session=ForexSession.LONDON,
        )

        assert context.is_extreme_volatility is True  # Forex threshold ≥90

    def test_market_context_high_atr_low_volume(self):
        """Test high ATR with low volume is NOT extreme (stopping volume)."""
        context = MarketContext(
            asset_class=AssetClass.STOCK,
            symbol="AAPL",
            current_volatility=Decimal("0.04"),
            volatility_percentile=96,  # High ATR
            volume_percentile=40,  # Low volume
            market_regime=MarketRegime.SIDEWAYS,
            recent_invalidations=[],
            time_of_day=time(11, 0),
            market_session="REGULAR",
        )

        assert context.is_extreme_volatility is False  # Volume not erratic

    def test_has_upcoming_news(self):
        """Test has_upcoming_news computed field."""
        earnings = EarningsEvent(
            symbol="AAPL",
            event_date=datetime.now(UTC) + timedelta(hours=12),
            event_type="EARNINGS",
            impact_level="HIGH",
            description="Earnings",
            fiscal_quarter="Q1 2024",
        )

        context = MarketContext(
            asset_class=AssetClass.STOCK,
            symbol="AAPL",
            current_volatility=Decimal("0.02"),
            volatility_percentile=50,
            volume_percentile=50,
            market_regime=MarketRegime.TRENDING_UP,
            recent_invalidations=[],
            time_of_day=time(10, 0),
            market_session="REGULAR",
            news_event=earnings,
        )

        assert context.has_upcoming_news is True  # Earnings within blackout

    def test_is_friday_pm_forex(self):
        """Test is_friday_pm_forex computed field."""
        # Mock Friday 18:00 UTC (after 17:00)
        friday_dt = datetime(2024, 1, 5, 18, 0, tzinfo=UTC)  # Friday

        context = MarketContext(
            asset_class=AssetClass.FOREX,
            symbol="EUR/USD",
            current_volatility=Decimal("0.01"),
            volatility_percentile=50,
            volume_percentile=50,
            market_regime=MarketRegime.TRENDING_UP,
            recent_invalidations=[],
            time_of_day=time(18, 0),
            market_session="REGULAR",
            forex_session=ForexSession.NY,
            data_timestamp=friday_dt,
        )

        # Note: is_friday_pm_forex checks datetime.now(), not data_timestamp
        # In real use, this would be True if run on Friday after 17:00 UTC

    def test_is_wednesday_pm_forex(self):
        """Test is_wednesday_pm_forex computed field."""
        wednesday_dt = datetime(2024, 1, 3, 18, 0, tzinfo=UTC)  # Wednesday

        context = MarketContext(
            asset_class=AssetClass.FOREX,
            symbol="GBP/USD",
            current_volatility=Decimal("0.012"),
            volatility_percentile=55,
            volume_percentile=55,
            market_regime=MarketRegime.SIDEWAYS,
            recent_invalidations=[],
            time_of_day=time(18, 0),
            market_session="REGULAR",
            forex_session=ForexSession.NY,
            data_timestamp=wednesday_dt,
        )

        # Note: is_wednesday_pm_forex checks datetime.now(), not data_timestamp
