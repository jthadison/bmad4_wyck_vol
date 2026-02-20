"""
Unit tests for Phase Status API endpoint (Feature 11: Wyckoff Cycle Compass)

Tests GET /api/v1/patterns/{symbol}/phase-status endpoint:
- Returns 200 with valid symbol
- Returns 422 with invalid bars param
- Response schema matches PhaseStatusResponse
- Progression percentage within valid range
- Bias correctly derived from events
"""

from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_get_phase_status_valid_symbol():
    """Test endpoint returns 200 with valid symbol."""
    response = client.get("/api/v1/patterns/AAPL/phase-status")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["timeframe"] == "1d"
    assert data["phase"] in ("A", "B", "C", "D", "E", None)
    assert 0.0 <= data["confidence"] <= 1.0
    assert data["phase_duration_bars"] >= 0
    assert 0.0 <= data["progression_pct"] <= 1.0
    assert data["bias"] in ("ACCUMULATION", "DISTRIBUTION", "UNKNOWN")
    assert "updated_at" in data
    assert isinstance(data["recent_events"], list)


def test_get_phase_status_with_timeframe():
    """Test endpoint respects timeframe query parameter."""
    response = client.get(
        "/api/v1/patterns/TSLA/phase-status",
        params={"timeframe": "4h"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["symbol"] == "TSLA"
    assert data["timeframe"] == "4h"


def test_get_phase_status_invalid_bars_too_low():
    """Test endpoint returns 422 when bars < 20."""
    response = client.get(
        "/api/v1/patterns/AAPL/phase-status",
        params={"bars": 5},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_get_phase_status_invalid_bars_too_high():
    """Test endpoint returns 422 when bars > 500."""
    response = client.get(
        "/api/v1/patterns/AAPL/phase-status",
        params={"bars": 1000},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_get_phase_status_response_schema():
    """Test response schema matches expected structure."""
    response = client.get("/api/v1/patterns/SPY/phase-status")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Verify all required fields are present
    required_fields = {
        "symbol",
        "timeframe",
        "phase",
        "confidence",
        "phase_duration_bars",
        "progression_pct",
        "dominant_event",
        "recent_events",
        "bias",
        "updated_at",
    }
    assert required_fields.issubset(set(data.keys()))


def test_get_phase_status_events_structure():
    """Test recent_events contain proper event structure."""
    response = client.get("/api/v1/patterns/AAPL/phase-status")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    for event in data["recent_events"]:
        assert "event_type" in event
        assert "bar_index" in event
        assert "price" in event
        assert "confidence" in event
        assert 0.0 <= event["confidence"] <= 1.0


def test_get_phase_status_progression_capped():
    """Test progression_pct never exceeds 0.95 (per Wyckoff rules)."""
    response = client.get("/api/v1/patterns/AAPL/phase-status")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["progression_pct"] <= 0.95


def test_get_phase_status_symbol_uppercased():
    """Test symbol is returned uppercased regardless of input."""
    response = client.get("/api/v1/patterns/aapl/phase-status")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["symbol"] == "AAPL"
