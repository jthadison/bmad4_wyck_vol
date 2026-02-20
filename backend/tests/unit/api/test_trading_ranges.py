"""
Unit tests for Trading Ranges API endpoint (P3-F12).

Tests GET /api/v1/patterns/{symbol}/trading-ranges endpoint:
- Returns list of historical ranges
- Separates active range from historical
- Respects limit parameter
- Response schema validation
- Correct outcome and type classification
"""

from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_get_trading_ranges_returns_200():
    """Test endpoint returns 200 with valid symbol."""
    response = client.get("/api/v1/patterns/AAPL/trading-ranges")
    assert response.status_code == status.HTTP_200_OK


def test_get_trading_ranges_response_schema():
    """Test response matches TradingRangeListResponse schema."""
    response = client.get("/api/v1/patterns/AAPL/trading-ranges")
    data = response.json()

    assert "symbol" in data
    assert "timeframe" in data
    assert "ranges" in data
    assert "active_range" in data
    assert "total_count" in data
    assert data["symbol"] == "AAPL"
    assert data["timeframe"] == "1d"
    assert isinstance(data["ranges"], list)
    assert isinstance(data["total_count"], int)


def test_get_trading_ranges_active_range_separated():
    """Test active range is in active_range field, not in ranges list."""
    response = client.get("/api/v1/patterns/AAPL/trading-ranges")
    data = response.json()

    # Active range should be present
    assert data["active_range"] is not None
    assert data["active_range"]["outcome"] == "ACTIVE"

    # Historical ranges should NOT contain active
    for r in data["ranges"]:
        assert r["outcome"] != "ACTIVE"


def test_get_trading_ranges_historical_sorted_descending():
    """Test historical ranges are sorted by start_date descending."""
    response = client.get("/api/v1/patterns/AAPL/trading-ranges")
    data = response.json()

    ranges = data["ranges"]
    if len(ranges) >= 2:
        for i in range(len(ranges) - 1):
            assert ranges[i]["start_date"] >= ranges[i + 1]["start_date"]


def test_get_trading_ranges_limit_parameter():
    """Test limit parameter restricts number of historical ranges."""
    response = client.get("/api/v1/patterns/AAPL/trading-ranges", params={"limit": 1})
    data = response.json()

    # Should have at most 1 historical range (active is separate)
    assert len(data["ranges"]) <= 1


def test_get_trading_ranges_custom_timeframe():
    """Test timeframe parameter is respected."""
    response = client.get("/api/v1/patterns/AAPL/trading-ranges", params={"timeframe": "4h"})
    data = response.json()
    assert data["timeframe"] == "4h"


def test_get_trading_ranges_symbol_uppercased():
    """Test symbol is uppercased in response."""
    response = client.get("/api/v1/patterns/aapl/trading-ranges")
    data = response.json()
    assert data["symbol"] == "AAPL"


def test_get_trading_ranges_range_fields():
    """Test each range has required Wyckoff fields."""
    response = client.get("/api/v1/patterns/AAPL/trading-ranges")
    data = response.json()

    # Check active range fields
    active = data["active_range"]
    assert "id" in active
    assert "symbol" in active
    assert "timeframe" in active
    assert "start_date" in active
    assert "duration_bars" in active
    assert "low" in active
    assert "high" in active
    assert "range_pct" in active
    assert "creek_level" in active
    assert "ice_level" in active
    assert "range_type" in active
    assert "outcome" in active
    assert "key_events" in active
    assert "avg_bar_volume" in active
    assert "total_volume" in active


def test_get_trading_ranges_range_pct_calculation():
    """Test range_pct = (high-low)/low * 100 is accurate."""
    response = client.get("/api/v1/patterns/AAPL/trading-ranges")
    data = response.json()

    for r in data["ranges"] + ([data["active_range"]] if data["active_range"] else []):
        expected_pct = (r["high"] - r["low"]) / r["low"] * 100
        assert abs(r["range_pct"] - expected_pct) < 0.01


def test_get_trading_ranges_avg_volume_calculation():
    """Test avg_bar_volume = total_volume / duration_bars."""
    response = client.get("/api/v1/patterns/AAPL/trading-ranges")
    data = response.json()

    for r in data["ranges"] + ([data["active_range"]] if data["active_range"] else []):
        expected_avg = r["total_volume"] / r["duration_bars"]
        assert abs(r["avg_bar_volume"] - expected_avg) < 0.01


def test_get_trading_ranges_key_events_present():
    """Test key_events list contains valid Wyckoff events."""
    response = client.get("/api/v1/patterns/AAPL/trading-ranges")
    data = response.json()

    active = data["active_range"]
    assert len(active["key_events"]) > 0

    event = active["key_events"][0]
    assert "event_type" in event
    assert "price" in event
    assert "volume" in event
    assert "significance" in event
    assert 0.0 <= event["significance"] <= 1.0


def test_get_trading_ranges_outcome_types():
    """Test ranges have diverse outcome types."""
    response = client.get("/api/v1/patterns/AAPL/trading-ranges")
    data = response.json()

    outcomes = {r["outcome"] for r in data["ranges"]}
    # Mock data includes MARKUP, MARKDOWN, FAILED
    assert "MARKUP" in outcomes
    assert "MARKDOWN" in outcomes
    assert "FAILED" in outcomes


def test_get_trading_ranges_range_types():
    """Test ranges have accumulation and distribution types."""
    response = client.get("/api/v1/patterns/AAPL/trading-ranges")
    data = response.json()

    all_ranges = data["ranges"] + ([data["active_range"]] if data["active_range"] else [])
    types = {r["range_type"] for r in all_ranges}
    assert "ACCUMULATION" in types
    assert "DISTRIBUTION" in types


def test_get_trading_ranges_active_has_no_end_date():
    """Test active range has null end_date."""
    response = client.get("/api/v1/patterns/AAPL/trading-ranges")
    data = response.json()

    active = data["active_range"]
    assert active["end_date"] is None
    assert active["price_change_pct"] is None


def test_get_trading_ranges_historical_has_end_date():
    """Test historical ranges have non-null end_date."""
    response = client.get("/api/v1/patterns/AAPL/trading-ranges")
    data = response.json()

    for r in data["ranges"]:
        assert r["end_date"] is not None
