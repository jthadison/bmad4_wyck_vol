"""
Unit tests for Signal Statistics (Story 19.17)

Tests signal statistics models, caching, and aggregation calculations.

Author: Story 19.17
"""

from datetime import date
from decimal import Decimal
from time import sleep

import pytest

from src.cache.statistics_cache import StatisticsCache, get_statistics_cache
from src.models.signal_statistics import (
    DateRange,
    PatternWinRate,
    RejectionCount,
    SignalStatisticsResponse,
    SignalSummary,
    SymbolPerformance,
)


class TestSignalStatisticsModels:
    """Test Pydantic models for signal statistics."""

    def test_signal_summary_creation(self):
        """Test SignalSummary model creation and validation."""
        summary = SignalSummary(
            total_signals=100,
            signals_today=5,
            signals_this_week=25,
            signals_this_month=80,
            overall_win_rate=65.5,
            avg_confidence=82.3,
            avg_r_multiple=2.5,
            total_pnl=Decimal("1234.56"),
        )

        assert summary.total_signals == 100
        assert summary.signals_today == 5
        assert summary.overall_win_rate == 65.5
        assert summary.total_pnl == Decimal("1234.56")

    def test_signal_summary_validation_win_rate_bounds(self):
        """Test SignalSummary validates win rate is 0-100."""
        with pytest.raises(ValueError):
            SignalSummary(
                total_signals=100,
                signals_today=5,
                signals_this_week=25,
                signals_this_month=80,
                overall_win_rate=150.0,  # Invalid: > 100
                avg_confidence=82.3,
                avg_r_multiple=2.5,
                total_pnl=Decimal("1234.56"),
            )

    def test_signal_summary_validation_negative_count(self):
        """Test SignalSummary validates counts are non-negative."""
        with pytest.raises(ValueError):
            SignalSummary(
                total_signals=-1,  # Invalid: negative
                signals_today=5,
                signals_this_week=25,
                signals_this_month=80,
                overall_win_rate=65.5,
                avg_confidence=82.3,
                avg_r_multiple=2.5,
                total_pnl=Decimal("1234.56"),
            )

    def test_pattern_win_rate_creation(self):
        """Test PatternWinRate model creation."""
        pattern = PatternWinRate(
            pattern_type="SPRING",
            total_signals=50,
            closed_signals=30,
            winning_signals=20,
            win_rate=66.67,
            avg_confidence=85.0,
            avg_r_multiple=2.8,
        )

        assert pattern.pattern_type == "SPRING"
        assert pattern.total_signals == 50
        assert pattern.closed_signals == 30
        assert pattern.winning_signals == 20
        assert pattern.win_rate == 66.67

    def test_rejection_count_creation(self):
        """Test RejectionCount model creation."""
        rejection = RejectionCount(
            reason="Volume too low for Spring pattern",
            validation_stage="Volume",
            count=15,
            percentage=25.5,
        )

        assert rejection.reason == "Volume too low for Spring pattern"
        assert rejection.validation_stage == "Volume"
        assert rejection.count == 15
        assert rejection.percentage == 25.5

    def test_symbol_performance_creation(self):
        """Test SymbolPerformance model creation."""
        perf = SymbolPerformance(
            symbol="AAPL",
            total_signals=20,
            win_rate=70.0,
            avg_r_multiple=3.2,
            total_pnl=Decimal("5000.00"),
        )

        assert perf.symbol == "AAPL"
        assert perf.total_signals == 20
        assert perf.win_rate == 70.0
        assert perf.total_pnl == Decimal("5000.00")

    def test_signal_statistics_response_creation(self):
        """Test complete SignalStatisticsResponse creation."""
        summary = SignalSummary(
            total_signals=100,
            signals_today=5,
            signals_this_week=25,
            signals_this_month=80,
            overall_win_rate=65.5,
            avg_confidence=82.3,
            avg_r_multiple=2.5,
            total_pnl=Decimal("1234.56"),
        )

        pattern = PatternWinRate(
            pattern_type="SPRING",
            total_signals=50,
            closed_signals=30,
            winning_signals=20,
            win_rate=66.67,
            avg_confidence=85.0,
            avg_r_multiple=2.8,
        )

        rejection = RejectionCount(
            reason="Volume too low",
            validation_stage="Volume",
            count=10,
            percentage=50.0,
        )

        symbol = SymbolPerformance(
            symbol="AAPL",
            total_signals=20,
            win_rate=70.0,
            avg_r_multiple=3.2,
            total_pnl=Decimal("5000.00"),
        )

        response = SignalStatisticsResponse(
            summary=summary,
            win_rate_by_pattern=[pattern],
            rejection_breakdown=[rejection],
            symbol_performance=[symbol],
            date_range=DateRange(
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 26),
            ),
        )

        assert response.summary.total_signals == 100
        assert len(response.win_rate_by_pattern) == 1
        assert response.win_rate_by_pattern[0].pattern_type == "SPRING"
        assert len(response.rejection_breakdown) == 1
        assert len(response.symbol_performance) == 1
        assert response.date_range.start_date == date(2026, 1, 1)

    def test_signal_statistics_json_serialization(self):
        """Test SignalStatisticsResponse JSON serialization."""
        summary = SignalSummary(
            total_signals=100,
            signals_today=5,
            signals_this_week=25,
            signals_this_month=80,
            overall_win_rate=65.5,
            avg_confidence=82.3,
            avg_r_multiple=2.5,
            total_pnl=Decimal("1234.56"),
        )

        response = SignalStatisticsResponse(
            summary=summary,
            win_rate_by_pattern=[],
            rejection_breakdown=[],
            symbol_performance=[],
            date_range=DateRange(
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 26),
            ),
        )

        # Serialize to JSON
        json_data = response.model_dump(mode="json")

        assert json_data["summary"]["total_signals"] == 100
        assert json_data["summary"]["total_pnl"] == "1234.56"
        assert json_data["date_range"]["start_date"] == "2026-01-01"
        assert json_data["date_range"]["end_date"] == "2026-01-26"


class TestStatisticsCache:
    """Test in-memory TTL cache for statistics."""

    def test_cache_set_and_get(self):
        """Test basic cache set and get operations."""
        cache = StatisticsCache()

        # Set value
        cache.set("test_key", {"data": "value"}, ttl_seconds=60)

        # Get value
        result = cache.get("test_key")

        assert result is not None
        assert result["data"] == "value"

    def test_cache_miss(self):
        """Test cache miss returns None."""
        cache = StatisticsCache()

        result = cache.get("nonexistent_key")

        assert result is None

    def test_cache_expiration(self):
        """Test cache entry expires after TTL."""
        cache = StatisticsCache()

        # Set with very short TTL
        cache.set("expiring_key", "value", ttl_seconds=1)

        # Wait for expiration
        sleep(1.1)

        # Should return None after expiration
        result = cache.get("expiring_key")

        assert result is None

    def test_cache_invalidate_key(self):
        """Test invalidating specific cache key."""
        cache = StatisticsCache()

        cache.set("key1", "value1", ttl_seconds=60)
        cache.set("key2", "value2", ttl_seconds=60)

        # Invalidate key1
        cache.invalidate("key1")

        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_cache_invalidate_pattern(self):
        """Test invalidating keys by pattern prefix."""
        cache = StatisticsCache()

        cache.set("summary:2026-01-01:2026-01-26", "data1", ttl_seconds=60)
        cache.set("summary:2026-01-02:2026-01-27", "data2", ttl_seconds=60)
        cache.set("win_rate:2026-01-01:2026-01-26", "data3", ttl_seconds=60)

        # Invalidate all summary keys
        removed = cache.invalidate_pattern("summary:")

        assert removed == 2
        assert cache.get("summary:2026-01-01:2026-01-26") is None
        assert cache.get("summary:2026-01-02:2026-01-27") is None
        assert cache.get("win_rate:2026-01-01:2026-01-26") == "data3"

    def test_cache_clear(self):
        """Test clearing all cache entries."""
        cache = StatisticsCache()

        cache.set("key1", "value1", ttl_seconds=60)
        cache.set("key2", "value2", ttl_seconds=60)
        cache.set("key3", "value3", ttl_seconds=60)

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") is None

    def test_cache_make_key(self):
        """Test cache key generation."""
        key = StatisticsCache.make_key("summary", "2026-01-01", "2026-01-26")

        assert key == "summary:2026-01-01:2026-01-26"

    def test_cache_ttl_constants(self):
        """Test cache TTL constants are set correctly."""
        assert StatisticsCache.SUMMARY_TTL == 300  # 5 minutes
        assert StatisticsCache.WIN_RATE_TTL == 900  # 15 minutes
        assert StatisticsCache.REJECTION_TTL == 1800  # 30 minutes
        assert StatisticsCache.SYMBOL_PERF_TTL == 900  # 15 minutes

    def test_global_cache_singleton(self):
        """Test get_statistics_cache returns singleton."""
        cache1 = get_statistics_cache()
        cache2 = get_statistics_cache()

        assert cache1 is cache2


class TestWinRateCalculations:
    """Test win rate calculation logic."""

    def test_win_rate_basic_calculation(self):
        """Test basic win rate calculation: winning / closed * 100."""
        closed = 30
        winning = 20
        win_rate = (winning / closed * 100) if closed > 0 else 0.0

        assert win_rate == pytest.approx(66.67, rel=0.01)

    def test_win_rate_zero_closed(self):
        """Test win rate is 0 when no closed signals."""
        closed = 0
        winning = 0
        win_rate = (winning / closed * 100) if closed > 0 else 0.0

        assert win_rate == 0.0

    def test_win_rate_all_winning(self):
        """Test win rate is 100% when all signals win."""
        closed = 10
        winning = 10
        win_rate = (winning / closed * 100) if closed > 0 else 0.0

        assert win_rate == 100.0

    def test_win_rate_all_losing(self):
        """Test win rate is 0% when all signals lose."""
        closed = 10
        winning = 0
        win_rate = (winning / closed * 100) if closed > 0 else 0.0

        assert win_rate == 0.0

    def test_rejection_percentage_calculation(self):
        """Test rejection percentage calculation."""
        total_rejections = 60
        reason_count = 15
        percentage = (reason_count / total_rejections * 100) if total_rejections > 0 else 0.0

        assert percentage == 25.0
