"""Unit tests for analytics data models."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.models.analytics import (
    PatternPerformanceMetrics,
    PatternPerformanceResponse,
    PreliminaryEvents,
    RelativeStrengthMetrics,
    SectorBreakdown,
    TradeDetail,
    TradeListResponse,
    TrendDataPoint,
    TrendResponse,
    VSAMetrics,
)


class TestTradeDetail:
    """Test TradeDetail model validation."""

    def test_valid_trade_detail(self) -> None:
        """Test creating valid trade detail."""
        trade = TradeDetail(
            signal_id=uuid4(),
            symbol="AAPL",
            entry_date=date(2024, 3, 1),
            entry_price=Decimal("175.50"),
            exit_price=Decimal("182.30"),
            r_multiple_achieved=Decimal("3.40"),
            status="TARGET_HIT",
            detection_phase="C",
        )
        assert trade.symbol == "AAPL"
        assert trade.status == "TARGET_HIT"
        assert trade.detection_phase == "C"

    def test_trade_detail_without_exit_price(self) -> None:
        """Test trade detail for active position (no exit price)."""
        trade = TradeDetail(
            signal_id=uuid4(),
            symbol="MSFT",
            entry_date=date(2024, 3, 5),
            entry_price=Decimal("400.00"),
            exit_price=None,
            r_multiple_achieved=Decimal("0.50"),
            status="ACTIVE",
        )
        assert trade.exit_price is None
        assert trade.status == "ACTIVE"

    def test_trade_detail_invalid_status(self) -> None:
        """Test validation fails for invalid status."""
        with pytest.raises(ValidationError):
            TradeDetail(
                signal_id=uuid4(),
                symbol="AAPL",
                entry_date=date(2024, 3, 1),
                entry_price=Decimal("175.50"),
                r_multiple_achieved=Decimal("3.40"),
                status="INVALID_STATUS",  # type: ignore
            )


class TestVSAMetrics:
    """Test VSAMetrics model validation."""

    def test_valid_vsa_metrics(self) -> None:
        """Test creating valid VSA metrics."""
        vsa = VSAMetrics(no_demand_count=5, no_supply_count=12, stopping_volume_count=3)
        assert vsa.no_demand_count == 5
        assert vsa.no_supply_count == 12
        assert vsa.stopping_volume_count == 3

    def test_vsa_metrics_defaults(self) -> None:
        """Test VSA metrics with default values."""
        vsa = VSAMetrics()
        assert vsa.no_demand_count == 0
        assert vsa.no_supply_count == 0
        assert vsa.stopping_volume_count == 0

    def test_vsa_metrics_negative_values(self) -> None:
        """Test validation fails for negative counts."""
        with pytest.raises(ValidationError):
            VSAMetrics(no_demand_count=-1)


class TestPreliminaryEvents:
    """Test PreliminaryEvents model validation."""

    def test_valid_preliminary_events(self) -> None:
        """Test creating valid preliminary events."""
        events = PreliminaryEvents(ps_count=2, sc_count=1, ar_count=1, st_count=3)
        assert events.ps_count == 2
        assert events.sc_count == 1
        assert events.ar_count == 1
        assert events.st_count == 3

    def test_preliminary_events_defaults(self) -> None:
        """Test preliminary events with default values."""
        events = PreliminaryEvents()
        assert events.ps_count == 0
        assert events.sc_count == 0
        assert events.ar_count == 0
        assert events.st_count == 0


class TestRelativeStrengthMetrics:
    """Test RelativeStrengthMetrics model validation."""

    def test_valid_rs_metrics(self) -> None:
        """Test creating valid relative strength metrics."""
        rs = RelativeStrengthMetrics(
            symbol="AAPL",
            rs_score=Decimal("1.42"),
            sector_rs=Decimal("1.15"),
            market_rs=Decimal("1.38"),
        )
        assert rs.symbol == "AAPL"
        assert rs.rs_score == Decimal("1.42")
        assert rs.sector_rs == Decimal("1.15")
        assert rs.market_rs == Decimal("1.38")

    def test_rs_metrics_weakness(self) -> None:
        """Test RS metrics showing weakness (RS < 1.0)."""
        rs = RelativeStrengthMetrics(
            symbol="XOM",
            rs_score=Decimal("0.78"),
            sector_rs=Decimal("0.85"),
            market_rs=Decimal("0.72"),
        )
        assert rs.rs_score < Decimal("1.0")
        assert rs.market_rs < Decimal("1.0")


class TestPatternPerformanceMetrics:
    """Test PatternPerformanceMetrics model validation."""

    def test_valid_pattern_metrics(self) -> None:
        """Test creating valid pattern performance metrics."""
        metrics = PatternPerformanceMetrics(
            pattern_type="SPRING",
            win_rate=Decimal("0.7200"),
            average_r_multiple=Decimal("3.45"),
            profit_factor=Decimal("2.80"),
            trade_count=42,
        )
        assert metrics.pattern_type == "SPRING"
        assert metrics.win_rate == Decimal("0.7200")
        assert metrics.average_r_multiple == Decimal("3.45")
        assert metrics.profit_factor == Decimal("2.80")
        assert metrics.trade_count == 42

    def test_pattern_metrics_with_best_worst_trades(self) -> None:
        """Test pattern metrics with best/worst trade details."""
        best_trade = TradeDetail(
            signal_id=uuid4(),
            symbol="AAPL",
            entry_date=date(2024, 3, 1),
            entry_price=Decimal("175.50"),
            exit_price=Decimal("195.00"),
            r_multiple_achieved=Decimal("5.20"),
            status="TARGET_HIT",
        )
        worst_trade = TradeDetail(
            signal_id=uuid4(),
            symbol="TSLA",
            entry_date=date(2024, 3, 10),
            entry_price=Decimal("200.00"),
            exit_price=Decimal("198.00"),
            r_multiple_achieved=Decimal("-1.00"),
            status="STOPPED",
        )

        metrics = PatternPerformanceMetrics(
            pattern_type="SOS",
            win_rate=Decimal("0.6500"),
            average_r_multiple=Decimal("2.80"),
            profit_factor=Decimal("2.10"),
            trade_count=28,
            best_trade=best_trade,
            worst_trade=worst_trade,
        )
        assert metrics.best_trade is not None
        assert metrics.best_trade.r_multiple_achieved == Decimal("5.20")
        assert metrics.worst_trade is not None
        assert metrics.worst_trade.r_multiple_achieved == Decimal("-1.00")

    def test_pattern_metrics_win_rate_bounds(self) -> None:
        """Test win rate must be between 0.0 and 1.0."""
        with pytest.raises(ValidationError):
            PatternPerformanceMetrics(
                pattern_type="SPRING",
                win_rate=Decimal("1.50"),  # Invalid: > 1.0
                average_r_multiple=Decimal("3.45"),
                profit_factor=Decimal("2.80"),
                trade_count=42,
            )

        with pytest.raises(ValidationError):
            PatternPerformanceMetrics(
                pattern_type="SPRING",
                win_rate=Decimal("-0.10"),  # Invalid: < 0.0
                average_r_multiple=Decimal("3.45"),
                profit_factor=Decimal("2.80"),
                trade_count=42,
            )

    def test_pattern_metrics_with_test_quality(self) -> None:
        """Test pattern metrics with test quality tracking."""
        metrics = PatternPerformanceMetrics(
            pattern_type="SPRING",
            win_rate=Decimal("0.7500"),
            average_r_multiple=Decimal("3.60"),
            profit_factor=Decimal("3.00"),
            trade_count=40,
            test_confirmed_count=30,
            test_confirmed_win_rate=Decimal("0.8500"),
            non_test_confirmed_win_rate=Decimal("0.6800"),
        )
        assert metrics.test_confirmed_count == 30
        assert metrics.test_confirmed_win_rate == Decimal("0.8500")
        assert metrics.non_test_confirmed_win_rate == Decimal("0.6800")

    def test_pattern_metrics_with_vsa_and_preliminary_events(self) -> None:
        """Test pattern metrics with Wyckoff enhancements."""
        vsa = VSAMetrics(no_demand_count=5, no_supply_count=12)
        prelim = PreliminaryEvents(ps_count=2, sc_count=1, ar_count=1, st_count=3)

        metrics = PatternPerformanceMetrics(
            pattern_type="SPRING",
            win_rate=Decimal("0.7200"),
            average_r_multiple=Decimal("3.45"),
            profit_factor=Decimal("2.80"),
            trade_count=42,
            vsa_metrics=vsa,
            preliminary_events=prelim,
        )
        assert metrics.vsa_metrics is not None
        assert metrics.vsa_metrics.no_supply_count == 12
        assert metrics.preliminary_events is not None
        assert metrics.preliminary_events.st_count == 3

    def test_pattern_metrics_with_phase_distribution(self) -> None:
        """Test pattern metrics with phase distribution."""
        metrics = PatternPerformanceMetrics(
            pattern_type="SPRING",
            win_rate=Decimal("0.7500"),
            average_r_multiple=Decimal("3.60"),
            profit_factor=Decimal("3.00"),
            trade_count=40,
            detection_phase="C",
            phase_distribution={"C": 32, "A": 8},
        )
        assert metrics.detection_phase == "C"
        assert metrics.phase_distribution is not None
        assert metrics.phase_distribution["C"] == 32
        assert metrics.phase_distribution["A"] == 8


class TestTrendDataPoint:
    """Test TrendDataPoint model validation."""

    def test_valid_trend_data_point(self) -> None:
        """Test creating valid trend data point."""
        point = TrendDataPoint(
            date=date(2024, 3, 1),
            win_rate=Decimal("0.7000"),
            pattern_type="SPRING",
        )
        assert point.date == date(2024, 3, 1)
        assert point.win_rate == Decimal("0.7000")
        assert point.pattern_type == "SPRING"

    def test_trend_data_point_win_rate_bounds(self) -> None:
        """Test win rate must be between 0.0 and 1.0."""
        with pytest.raises(ValidationError):
            TrendDataPoint(
                date=date(2024, 3, 1),
                win_rate=Decimal("1.20"),  # Invalid: > 1.0
            )


class TestSectorBreakdown:
    """Test SectorBreakdown model validation."""

    def test_valid_sector_breakdown(self) -> None:
        """Test creating valid sector breakdown."""
        sector = SectorBreakdown(
            sector_name="Technology",
            win_rate=Decimal("0.8500"),
            trade_count=25,
            average_r_multiple=Decimal("4.20"),
        )
        assert sector.sector_name == "Technology"
        assert sector.win_rate == Decimal("0.8500")
        assert sector.trade_count == 25
        assert sector.average_r_multiple == Decimal("4.20")

    def test_sector_breakdown_with_rs(self) -> None:
        """Test sector breakdown with relative strength."""
        sector = SectorBreakdown(
            sector_name="Technology",
            win_rate=Decimal("0.8500"),
            trade_count=25,
            average_r_multiple=Decimal("4.20"),
            rs_score=Decimal("1.42"),
            leadership_status="LEADER",
        )
        assert sector.rs_score == Decimal("1.42")
        assert sector.leadership_status == "LEADER"


class TestPatternPerformanceResponse:
    """Test PatternPerformanceResponse model validation."""

    def test_valid_response(self) -> None:
        """Test creating valid pattern performance response."""
        now = datetime.now()
        expires_at = now + timedelta(hours=24)

        metrics = PatternPerformanceMetrics(
            pattern_type="SPRING",
            win_rate=Decimal("0.7200"),
            average_r_multiple=Decimal("3.45"),
            profit_factor=Decimal("2.80"),
            trade_count=42,
        )
        sector = SectorBreakdown(
            sector_name="Technology",
            win_rate=Decimal("0.8500"),
            trade_count=25,
            average_r_multiple=Decimal("4.20"),
        )

        response = PatternPerformanceResponse(
            patterns=[metrics],
            sector_breakdown=[sector],
            time_period_days=30,
            generated_at=now,
            cache_expires_at=expires_at,
        )
        assert len(response.patterns) == 1
        assert len(response.sector_breakdown) == 1
        assert response.time_period_days == 30

    def test_response_invalid_time_period(self) -> None:
        """Test validation fails for invalid time period."""
        now = datetime.now()
        expires_at = now + timedelta(hours=24)

        with pytest.raises(ValidationError) as exc_info:
            PatternPerformanceResponse(
                patterns=[],
                sector_breakdown=[],
                time_period_days=45,  # Invalid: must be 7, 30, 90, or None
                generated_at=now,
                cache_expires_at=expires_at,
            )
        assert "time_period_days must be 7, 30, 90, or None" in str(exc_info.value)

    def test_response_valid_time_periods(self) -> None:
        """Test all valid time periods."""
        now = datetime.now()
        expires_at = now + timedelta(hours=24)

        for days in [7, 30, 90, None]:
            response = PatternPerformanceResponse(
                patterns=[],
                sector_breakdown=[],
                time_period_days=days,
                generated_at=now,
                cache_expires_at=expires_at,
            )
            assert response.time_period_days == days


class TestTrendResponse:
    """Test TrendResponse model validation."""

    def test_valid_trend_response(self) -> None:
        """Test creating valid trend response."""
        points = [
            TrendDataPoint(date=date(2024, 3, 1), win_rate=Decimal("0.7000")),
            TrendDataPoint(date=date(2024, 3, 2), win_rate=Decimal("0.7200")),
        ]

        response = TrendResponse(pattern_type="SPRING", trend_data=points, time_period_days=30)
        assert response.pattern_type == "SPRING"
        assert len(response.trend_data) == 2
        assert response.time_period_days == 30


class TestTradeListResponse:
    """Test TradeListResponse model validation."""

    def test_valid_trade_list_response(self) -> None:
        """Test creating valid trade list response."""
        trades = [
            TradeDetail(
                signal_id=uuid4(),
                symbol="AAPL",
                entry_date=date(2024, 3, 1),
                entry_price=Decimal("175.50"),
                exit_price=Decimal("182.30"),
                r_multiple_achieved=Decimal("3.40"),
                status="TARGET_HIT",
            )
        ]

        response = TradeListResponse(
            pattern_type="SPRING",
            trades=trades,
            pagination={
                "returned_count": 1,
                "total_count": 42,
                "limit": 50,
                "offset": 0,
            },
            time_period_days=30,
        )
        assert response.pattern_type == "SPRING"
        assert len(response.trades) == 1
        assert response.pagination["total_count"] == 42
