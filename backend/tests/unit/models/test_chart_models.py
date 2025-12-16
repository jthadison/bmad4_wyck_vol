"""Unit tests for chart data models.

Story 11.5: Advanced Charting Integration
Tests Pydantic model validation and transformation logic.
"""

from datetime import datetime
from uuid import uuid4

import pytest

from src.models.chart import (
    LEVEL_LINE_CONFIG,
    PATTERN_MARKER_CONFIG,
    PHASE_COLOR_CONFIG,
    ChartBar,
    ChartDataRequest,
    ChartDataResponse,
    LevelLine,
    PatternMarker,
    PhaseAnnotation,
    PreliminaryEvent,
    TradingRangeLevels,
)


class TestChartBar:
    """Test ChartBar model."""

    def test_chart_bar_creation(self):
        """Test creating a valid ChartBar."""
        bar = ChartBar(
            time=1710345600,  # Unix timestamp
            open=150.00,
            high=152.50,
            low=149.75,
            close=151.00,
            volume=1000000,
        )

        assert bar.time == 1710345600
        assert bar.open == 150.00
        assert bar.high == 152.50
        assert bar.low == 149.75
        assert bar.close == 151.00
        assert bar.volume == 1000000

    def test_chart_bar_json_serialization(self):
        """Test ChartBar serializes to JSON correctly."""
        bar = ChartBar(
            time=1710345600, open=150.00, high=152.50, low=149.75, close=151.00, volume=1000000
        )

        json_data = bar.model_dump()
        assert json_data["time"] == 1710345600
        assert json_data["open"] == 150.00
        assert json_data["volume"] == 1000000


class TestPatternMarker:
    """Test PatternMarker model."""

    def test_pattern_marker_spring(self):
        """Test creating a Spring pattern marker."""
        marker = PatternMarker(
            id=uuid4(),
            pattern_type="SPRING",
            time=1710345600,
            price=150.00,
            position="belowBar",
            confidence_score=85,
            label_text="Spring (85%)",
            icon="⬆️",
            color="#16A34A",
            shape="arrowUp",
            entry_price=150.00,
            stop_loss=148.00,
            phase="C",
        )

        assert marker.pattern_type == "SPRING"
        assert marker.position == "belowBar"
        assert marker.confidence_score == 85
        assert marker.icon == "⬆️"
        assert marker.color == "#16A34A"
        assert marker.shape == "arrowUp"

    def test_pattern_marker_utad(self):
        """Test creating a UTAD pattern marker."""
        marker = PatternMarker(
            id=uuid4(),
            pattern_type="UTAD",
            time=1710345600,
            price=160.00,
            position="aboveBar",
            confidence_score=78,
            label_text="UTAD (78%)",
            icon="⬇️",
            color="#DC2626",
            shape="arrowDown",
            entry_price=160.00,
            stop_loss=162.00,
            phase="D",
        )

        assert marker.pattern_type == "UTAD"
        assert marker.position == "aboveBar"
        assert marker.icon == "⬇️"

    def test_pattern_marker_config_complete(self):
        """Test that all pattern types have marker configs."""
        pattern_types = ["SPRING", "UTAD", "SOS", "LPS", "TEST"]

        for ptype in pattern_types:
            assert ptype in PATTERN_MARKER_CONFIG
            config = PATTERN_MARKER_CONFIG[ptype]
            assert "icon" in config
            assert "color" in config
            assert "position" in config
            assert "shape" in config


class TestLevelLine:
    """Test LevelLine model."""

    def test_creek_level_line(self):
        """Test creating a Creek level line."""
        level = LevelLine(
            level_type="CREEK",
            price=150.00,
            label="Creek: $150.00",
            color="#DC2626",
            line_style="SOLID",
            line_width=2,
        )

        assert level.level_type == "CREEK"
        assert level.price == 150.00
        assert level.color == "#DC2626"
        assert level.line_style == "SOLID"

    def test_ice_level_line(self):
        """Test creating an Ice level line."""
        level = LevelLine(
            level_type="ICE",
            price=160.00,
            label="Ice: $160.00",
            color="#2563EB",
            line_style="SOLID",
            line_width=2,
        )

        assert level.level_type == "ICE"
        assert level.color == "#2563EB"

    def test_jump_level_line(self):
        """Test creating a Jump level line."""
        level = LevelLine(
            level_type="JUMP",
            price=168.50,
            label="Jump: $168.50",
            color="#16A34A",
            line_style="DASHED",
            line_width=2,
        )

        assert level.level_type == "JUMP"
        assert level.color == "#16A34A"
        assert level.line_style == "DASHED"

    def test_level_line_config_complete(self):
        """Test that all level types have configs."""
        level_types = ["CREEK", "ICE", "JUMP"]

        for ltype in level_types:
            assert ltype in LEVEL_LINE_CONFIG
            config = LEVEL_LINE_CONFIG[ltype]
            assert "color" in config
            assert "label_prefix" in config


class TestPhaseAnnotation:
    """Test PhaseAnnotation model."""

    def test_phase_c_annotation(self):
        """Test creating a Phase C annotation."""
        annotation = PhaseAnnotation(
            phase="C",
            start_time=1710000000,
            end_time=1710345600,
            background_color="#FCD34D20",
            label="Phase C",
        )

        assert annotation.phase == "C"
        assert annotation.start_time == 1710000000
        assert annotation.end_time == 1710345600
        assert annotation.background_color == "#FCD34D20"

    def test_phase_color_config_complete(self):
        """Test that all phases have color configs."""
        phases = ["A", "B", "C", "D", "E"]

        for phase in phases:
            assert phase in PHASE_COLOR_CONFIG
            color = PHASE_COLOR_CONFIG[phase]
            assert color.endswith("20")  # Alpha transparency


class TestTradingRangeLevels:
    """Test TradingRangeLevels model."""

    def test_active_trading_range(self):
        """Test creating an active trading range."""
        tr = TradingRangeLevels(
            trading_range_id=uuid4(),
            symbol="AAPL",
            creek_level=150.00,
            ice_level=160.00,
            jump_target=168.50,
            range_status="ACTIVE",
        )

        assert tr.symbol == "AAPL"
        assert tr.creek_level == 150.00
        assert tr.ice_level == 160.00
        assert tr.jump_target == 168.50
        assert tr.range_status == "ACTIVE"

    def test_completed_trading_range(self):
        """Test creating a completed trading range."""
        tr = TradingRangeLevels(
            trading_range_id=uuid4(),
            symbol="AAPL",
            creek_level=150.00,
            ice_level=160.00,
            jump_target=168.50,
            range_status="COMPLETED",
        )

        assert tr.range_status == "COMPLETED"


class TestPreliminaryEvent:
    """Test PreliminaryEvent model."""

    def test_selling_climax_event(self):
        """Test creating a Selling Climax event."""
        event = PreliminaryEvent(
            event_type="SC",
            time=1710345600,
            price=145.00,
            label="Selling Climax",
            description="Panic selling exhaustion",
            color="#DC2626",
            shape="triangle",
        )

        assert event.event_type == "SC"
        assert event.label == "Selling Climax"
        assert event.shape == "triangle"


class TestChartDataRequest:
    """Test ChartDataRequest model."""

    def test_valid_request_with_defaults(self):
        """Test request with default values."""
        request = ChartDataRequest(symbol="AAPL")

        assert request.symbol == "AAPL"
        assert request.timeframe == "1D"
        assert request.start_date is None
        assert request.end_date is None
        assert request.limit == 500

    def test_valid_request_with_custom_values(self):
        """Test request with custom values."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 3, 13)

        request = ChartDataRequest(
            symbol="MSFT", timeframe="1W", start_date=start, end_date=end, limit=1000
        )

        assert request.symbol == "MSFT"
        assert request.timeframe == "1W"
        assert request.start_date == start
        assert request.end_date == end
        assert request.limit == 1000

    def test_request_limit_validation(self):
        """Test limit validation (50-2000)."""
        # Valid limits
        request = ChartDataRequest(symbol="AAPL", limit=50)
        assert request.limit == 50

        request = ChartDataRequest(symbol="AAPL", limit=2000)
        assert request.limit == 2000

        # Invalid limits should raise validation error
        with pytest.raises(Exception):  # Pydantic ValidationError
            ChartDataRequest(symbol="AAPL", limit=25)

        with pytest.raises(Exception):  # Pydantic ValidationError
            ChartDataRequest(symbol="AAPL", limit=3000)


class TestChartDataResponse:
    """Test ChartDataResponse model."""

    def test_complete_response(self):
        """Test creating a complete chart data response."""
        bars = [
            ChartBar(
                time=1710345600, open=150.00, high=152.00, low=149.00, close=151.00, volume=1000000
            )
        ]

        patterns = [
            PatternMarker(
                id=uuid4(),
                pattern_type="SPRING",
                time=1710345600,
                price=149.00,
                position="belowBar",
                confidence_score=85,
                label_text="Spring (85%)",
                icon="⬆️",
                color="#16A34A",
                shape="arrowUp",
                entry_price=149.00,
                stop_loss=147.00,
                phase="C",
            )
        ]

        level_lines = [
            LevelLine(
                level_type="CREEK",
                price=148.00,
                label="Creek: $148.00",
                color="#DC2626",
                line_style="SOLID",
                line_width=2,
            )
        ]

        response = ChartDataResponse(
            symbol="AAPL",
            timeframe="1D",
            bars=bars,
            patterns=patterns,
            level_lines=level_lines,
            phase_annotations=[],
            trading_ranges=[],
            preliminary_events=[],
            schematic_match=None,
            cause_building=None,
            bar_count=1,
            date_range={"start": "2024-01-01", "end": "2024-03-13"},
        )

        assert response.symbol == "AAPL"
        assert response.timeframe == "1D"
        assert len(response.bars) == 1
        assert len(response.patterns) == 1
        assert len(response.level_lines) == 1
        assert response.bar_count == 1

    def test_response_json_serialization(self):
        """Test response serializes to JSON correctly."""
        response = ChartDataResponse(
            symbol="AAPL",
            timeframe="1D",
            bars=[],
            patterns=[],
            level_lines=[],
            phase_annotations=[],
            trading_ranges=[],
            preliminary_events=[],
            schematic_match=None,
            cause_building=None,
            bar_count=0,
            date_range={"start": "2024-01-01", "end": "2024-03-13"},
        )

        json_data = response.model_dump()
        assert json_data["symbol"] == "AAPL"
        assert json_data["bar_count"] == 0
        assert json_data["date_range"]["start"] == "2024-01-01"
