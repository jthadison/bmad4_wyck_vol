"""
Unit tests for StrategyValidator (Story 8.7).

Tests market regime validation, news blackout, invalidations, time-based rules,
high-conviction overrides, and human review flagging.
"""

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.models.market_context import (
    AssetClass,
    EarningsEvent,
    ForexNewsEvent,
    ForexSession,
    InvalidationEvent,
    MarketContext,
    MarketRegime,
)
from src.models.validation import ValidationContext, ValidationStatus
from src.services.news_calendar_factory import NewsCalendarFactory
from src.signal_generator.validators.strategy_validator import StrategyValidator


# Mock Pattern class for testing
class MockPattern:
    """Mock pattern object with pattern_type and confidence_score."""

    def __init__(self, pattern_type: str, confidence_score: float, phase: str):
        self.id = uuid4()
        self.pattern_type = pattern_type
        self.confidence_score = confidence_score
        self.phase = phase


@pytest.fixture
def mock_news_calendar_factory():
    """Create mock NewsCalendarFactory."""
    factory = Mock(spec=NewsCalendarFactory)
    return factory


@pytest.fixture
def valid_market_context():
    """Create valid MarketContext for testing."""
    return MarketContext(
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
        news_event=None,
    )


@pytest.fixture
def valid_pattern():
    """Create valid MockPattern for testing."""
    return MockPattern(
        pattern_type="SPRING",
        confidence_score=0.85,
        phase="C",
    )


@pytest.fixture
def mock_volume_analysis():
    """Create mock VolumeAnalysis for ValidationContext."""
    return Mock()


class TestMarketRegimeValidation:
    """Test market regime validation rules."""

    @pytest.mark.asyncio
    async def test_spring_in_extreme_volatility_fails(
        self, mock_news_calendar_factory, valid_pattern, mock_volume_analysis
    ):
        """Spring in extreme volatility (ATR ≥95%, volume ≥85%) should FAIL."""
        market_context = MarketContext(
            asset_class=AssetClass.STOCK,
            symbol="TSLA",
            current_volatility=Decimal("0.05"),
            volatility_percentile=98,
            volume_percentile=90,
            market_regime=MarketRegime.HIGH_VOLATILITY,
            adx=Decimal("35"),
            recent_invalidations=[],
            time_of_day=time(10, 0),
            market_session="REGULAR",
        )

        context = ValidationContext(
            pattern=valid_pattern,
            symbol="TSLA",
            timeframe="1h",
            volume_analysis=mock_volume_analysis,
            market_context=market_context,
        )

        # Mock news service
        mock_service = AsyncMock()
        mock_service.check_blackout_window.return_value = (False, None)
        mock_news_calendar_factory.get_calendar.return_value = mock_service

        validator = StrategyValidator(mock_news_calendar_factory)
        result = await validator.validate(context)

        assert result.status == ValidationStatus.FAIL
        assert "extreme volatility" in result.reason.lower()
        assert "98th percentile" in result.reason

    @pytest.mark.asyncio
    async def test_sos_in_sideways_market_warns(
        self, mock_news_calendar_factory, valid_market_context, mock_volume_analysis
    ):
        """SOS in sideways market (ADX < 25) should WARN."""
        market_context = valid_market_context.model_copy(
            update={
                "market_regime": MarketRegime.SIDEWAYS,
                "adx": Decimal("18"),
            }
        )

        pattern = MockPattern(
            pattern_type="SOS",
            confidence_score=0.85,
            phase="D",
        )

        context = ValidationContext(
            pattern=pattern,
            symbol="AAPL",
            timeframe="1h",
            volume_analysis=mock_volume_analysis,
            market_context=market_context,
        )

        # Mock news service
        mock_service = AsyncMock()
        mock_service.check_blackout_window.return_value = (False, None)
        mock_news_calendar_factory.get_calendar.return_value = mock_service

        validator = StrategyValidator(mock_news_calendar_factory)
        result = await validator.validate(context)

        assert result.status == ValidationStatus.WARN
        assert "sideways market" in result.reason.lower()
        assert "adx" in result.reason.lower()


class TestNewsBlackoutValidation:
    """Test earnings blackout and forex news validation (FR29)."""

    @pytest.mark.asyncio
    async def test_earnings_12_hours_fails(
        self, mock_news_calendar_factory, valid_pattern, valid_market_context, mock_volume_analysis
    ):
        """Earnings in 12 hours should FAIL (AC: 5, FR29)."""
        earnings = EarningsEvent(
            symbol="AAPL",
            event_date=datetime.now(UTC) + timedelta(hours=12),
            event_type="EARNINGS",
            impact_level="HIGH",
            description="Q1 Earnings",
            fiscal_quarter="Q1 2024",
        )

        context = ValidationContext(
            pattern=valid_pattern,
            symbol="AAPL",
            timeframe="1h",
            volume_analysis=mock_volume_analysis,
            market_context=valid_market_context,
        )

        # Mock earnings service
        mock_service = AsyncMock()
        mock_service.check_blackout_window.return_value = (True, earnings)
        mock_news_calendar_factory.get_calendar.return_value = mock_service

        validator = StrategyValidator(mock_news_calendar_factory)
        result = await validator.validate(context)

        assert result.status == ValidationStatus.FAIL
        assert "earnings" in result.reason.lower()
        assert "fr29" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_nfp_4_hours_fails(
        self, mock_news_calendar_factory, valid_pattern, mock_volume_analysis
    ):
        """NFP in 4 hours should FAIL (within 6hr window)."""
        nfp = ForexNewsEvent(
            symbol="EUR/USD",
            event_date=datetime.now(UTC) + timedelta(hours=4),
            event_type="NFP",
            impact_level="HIGH",
            description="US Non-Farm Payrolls",
            affected_currencies=["USD"],
        )

        market_context = MarketContext(
            asset_class=AssetClass.FOREX,
            symbol="EUR/USD",
            current_volatility=Decimal("0.015"),
            volatility_percentile=50,
            volume_percentile=50,
            market_regime=MarketRegime.TRENDING_UP,
            recent_invalidations=[],
            time_of_day=time(10, 0),
            market_session="REGULAR",
            forex_session=ForexSession.LONDON,
        )

        context = ValidationContext(
            pattern=valid_pattern,
            symbol="EUR/USD",
            timeframe="1h",
            volume_analysis=mock_volume_analysis,
            market_context=market_context,
        )

        # Mock forex news service
        mock_service = AsyncMock()
        mock_service.check_blackout_window.return_value = (True, nfp)
        mock_news_calendar_factory.get_calendar.return_value = mock_service

        validator = StrategyValidator(mock_news_calendar_factory)
        result = await validator.validate(context)

        assert result.status == ValidationStatus.FAIL
        assert "nfp" in result.reason.lower()


class TestInvalidationValidation:
    """Test recent invalidation checks."""

    @pytest.mark.asyncio
    async def test_invalidation_2_days_ago_stock_fails(
        self, mock_news_calendar_factory, valid_pattern, mock_volume_analysis
    ):
        """Stock invalidation 2 days ago (within 5-day cooldown) should FAIL."""
        invalidation = InvalidationEvent(
            campaign_id="campaign-123",
            symbol="AAPL",
            pattern_type="SPRING",
            invalidation_date=datetime.now(UTC) - timedelta(days=2),
            invalidation_reason="Spring low broken",
            trading_range_id=uuid4(),
        )

        market_context = MarketContext(
            asset_class=AssetClass.STOCK,
            symbol="AAPL",
            current_volatility=Decimal("0.02"),
            volatility_percentile=50,
            volume_percentile=50,
            market_regime=MarketRegime.TRENDING_UP,
            adx=Decimal("28"),
            recent_invalidations=[invalidation],
            time_of_day=time(10, 0),
            market_session="REGULAR",
        )

        context = ValidationContext(
            pattern=valid_pattern,
            symbol="AAPL",
            timeframe="1h",
            volume_analysis=mock_volume_analysis,
            market_context=market_context,
            campaign_id="campaign-123",
        )

        # Mock news service
        mock_service = AsyncMock()
        mock_service.check_blackout_window.return_value = (False, None)
        mock_news_calendar_factory.get_calendar.return_value = mock_service

        validator = StrategyValidator(mock_news_calendar_factory)
        result = await validator.validate(context)

        assert result.status == ValidationStatus.FAIL
        assert "recent invalidation" in result.reason.lower() or "stop-out" in result.reason.lower()
        assert "2" in result.reason  # Days ago

    @pytest.mark.asyncio
    async def test_invalidation_6_days_ago_stock_passes(
        self, mock_news_calendar_factory, valid_pattern, mock_volume_analysis
    ):
        """Stock invalidation 6 days ago (outside 5-day cooldown) should PASS."""
        invalidation = InvalidationEvent(
            campaign_id="campaign-123",
            symbol="AAPL",
            pattern_type="SPRING",
            invalidation_date=datetime.now(UTC) - timedelta(days=6),
            invalidation_reason="Spring low broken",
            trading_range_id=uuid4(),
        )

        market_context = MarketContext(
            asset_class=AssetClass.STOCK,
            symbol="AAPL",
            current_volatility=Decimal("0.02"),
            volatility_percentile=50,
            volume_percentile=50,
            market_regime=MarketRegime.TRENDING_UP,
            adx=Decimal("28"),
            recent_invalidations=[invalidation],
            time_of_day=time(10, 0),
            market_session="REGULAR",
        )

        context = ValidationContext(
            pattern=valid_pattern,
            symbol="AAPL",
            timeframe="1h",
            volume_analysis=mock_volume_analysis,
            market_context=market_context,
            campaign_id="campaign-123",
        )

        # Mock news service
        mock_service = AsyncMock()
        mock_service.check_blackout_window.return_value = (False, None)
        mock_news_calendar_factory.get_calendar.return_value = mock_service

        validator = StrategyValidator(mock_news_calendar_factory)
        result = await validator.validate(context)

        assert result.status == ValidationStatus.PASS


class TestTimeBasedValidation:
    """Test time-based validation rules."""

    @pytest.mark.asyncio
    async def test_end_of_day_entry_warns(
        self, mock_news_calendar_factory, valid_pattern, mock_volume_analysis
    ):
        """Entry at 15:30 (30 min before close) should WARN."""
        market_context = MarketContext(
            asset_class=AssetClass.STOCK,
            symbol="AAPL",
            current_volatility=Decimal("0.02"),
            volatility_percentile=50,
            volume_percentile=50,
            market_regime=MarketRegime.TRENDING_UP,
            adx=Decimal("28"),
            recent_invalidations=[],
            time_of_day=time(15, 30),
            market_session="REGULAR",
        )

        context = ValidationContext(
            pattern=valid_pattern,
            symbol="AAPL",
            timeframe="1h",
            volume_analysis=mock_volume_analysis,
            market_context=market_context,
        )

        # Mock news service
        mock_service = AsyncMock()
        mock_service.check_blackout_window.return_value = (False, None)
        mock_news_calendar_factory.get_calendar.return_value = mock_service

        validator = StrategyValidator(mock_news_calendar_factory)
        result = await validator.validate(context)

        assert result.status == ValidationStatus.WARN
        assert "close" in result.reason.lower() or "15:30" in result.reason

    @pytest.mark.asyncio
    async def test_friday_pm_forex_fails(
        self, mock_news_calendar_factory, valid_pattern, mock_volume_analysis
    ):
        """Friday after 17:00 UTC (12pm EST) forex entry should FAIL."""
        # Friday 18:00 UTC
        friday_dt = datetime(2024, 1, 5, 18, 0, tzinfo=UTC)

        market_context = MarketContext(
            asset_class=AssetClass.FOREX,
            symbol="EUR/USD",
            current_volatility=Decimal("0.012"),
            volatility_percentile=50,
            volume_percentile=50,
            market_regime=MarketRegime.TRENDING_UP,
            recent_invalidations=[],
            time_of_day=time(18, 0),
            market_session="REGULAR",
            forex_session=ForexSession.NY,
            data_timestamp=friday_dt,
        )

        context = ValidationContext(
            pattern=valid_pattern,
            symbol="EUR/USD",
            timeframe="1h",
            volume_analysis=mock_volume_analysis,
            market_context=market_context,
        )

        # Mock news service
        mock_service = AsyncMock()
        mock_service.check_blackout_window.return_value = (False, None)
        mock_news_calendar_factory.get_calendar.return_value = mock_service

        validator = StrategyValidator(mock_news_calendar_factory)
        result = await validator.validate(context)

        assert result.status == ValidationStatus.FAIL
        assert "friday" in result.reason.lower()
        assert "weekend gap" in result.reason.lower()


class TestStrategicOverrides:
    """Test high-conviction override logic."""

    @pytest.mark.asyncio
    async def test_high_conviction_overrides_warn(
        self, mock_news_calendar_factory, mock_volume_analysis
    ):
        """92% confidence should override WARN → PASS."""
        market_context = MarketContext(
            asset_class=AssetClass.STOCK,
            symbol="AAPL",
            current_volatility=Decimal("0.02"),
            volatility_percentile=50,
            volume_percentile=50,
            market_regime=MarketRegime.SIDEWAYS,
            adx=Decimal("18"),  # Will trigger WARN for SOS
            recent_invalidations=[],
            time_of_day=time(10, 0),
            market_session="REGULAR",
        )

        pattern = MockPattern(
            pattern_type="SOS",
            confidence_score=0.92,  # High conviction
            phase="D",
        )

        context = ValidationContext(
            pattern=pattern,
            symbol="AAPL",
            timeframe="1h",
            volume_analysis=mock_volume_analysis,
            market_context=market_context,
        )

        # Mock news service
        mock_service = AsyncMock()
        mock_service.check_blackout_window.return_value = (False, None)
        mock_news_calendar_factory.get_calendar.return_value = mock_service

        validator = StrategyValidator(mock_news_calendar_factory)
        result = await validator.validate(context)

        assert result.status == ValidationStatus.PASS
        assert "high-conviction override" in result.reason.lower()
        assert "92" in result.reason

    @pytest.mark.asyncio
    async def test_low_conviction_cannot_override_warn(
        self, mock_news_calendar_factory, mock_volume_analysis
    ):
        """75% confidence should NOT override WARN."""
        market_context = MarketContext(
            asset_class=AssetClass.STOCK,
            symbol="AAPL",
            current_volatility=Decimal("0.02"),
            volatility_percentile=50,
            volume_percentile=50,
            market_regime=MarketRegime.SIDEWAYS,
            adx=Decimal("18"),
            recent_invalidations=[],
            time_of_day=time(10, 0),
            market_session="REGULAR",
        )

        pattern = MockPattern(
            pattern_type="SOS",
            confidence_score=0.75,  # Low conviction
            phase="D",
        )

        context = ValidationContext(
            pattern=pattern,
            symbol="AAPL",
            timeframe="1h",
            volume_analysis=mock_volume_analysis,
            market_context=market_context,
        )

        # Mock news service
        mock_service = AsyncMock()
        mock_service.check_blackout_window.return_value = (False, None)
        mock_news_calendar_factory.get_calendar.return_value = mock_service

        validator = StrategyValidator(mock_news_calendar_factory)
        result = await validator.validate(context)

        assert result.status == ValidationStatus.WARN  # No override


class TestHumanReviewFlagging:
    """Test human review flagging."""

    @pytest.mark.asyncio
    async def test_low_confidence_with_warnings_flags_review(
        self, mock_news_calendar_factory, mock_volume_analysis
    ):
        """72% confidence with warnings should flag for review."""
        market_context = MarketContext(
            asset_class=AssetClass.STOCK,
            symbol="AAPL",
            current_volatility=Decimal("0.02"),
            volatility_percentile=50,
            volume_percentile=50,
            market_regime=MarketRegime.SIDEWAYS,
            adx=Decimal("18"),  # Triggers warning
            recent_invalidations=[],
            time_of_day=time(10, 0),
            market_session="REGULAR",
        )

        pattern = MockPattern(
            pattern_type="SOS",
            confidence_score=0.72,  # Low confidence
            phase="D",
        )

        context = ValidationContext(
            pattern=pattern,
            symbol="AAPL",
            timeframe="1h",
            volume_analysis=mock_volume_analysis,
            market_context=market_context,
        )

        # Mock news service
        mock_service = AsyncMock()
        mock_service.check_blackout_window.return_value = (False, None)
        mock_news_calendar_factory.get_calendar.return_value = mock_service

        validator = StrategyValidator(mock_news_calendar_factory)
        result = await validator.validate(context)

        assert result.metadata["needs_human_review"] is True
        assert "72" in result.metadata["review_reason"]
