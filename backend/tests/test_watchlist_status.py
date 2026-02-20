"""
Tests for GET /api/v1/watchlist/status (Feature 6: Wyckoff Status Dashboard)

Tests verify:
- Endpoint returns 200 with valid WatchlistStatusResponse structure
- Each symbol entry has required fields (phase, confidence, bars, etc.)
- Phase value is one of the valid Wyckoff phases (A/B/C/D/E)
- recent_bars is a non-empty list of OHLCV dicts
- cause_progress_pct is within [0, 100]
- Endpoint works when watchlist is empty
- FastAPI dependency override is used to avoid real DB dependency
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.api.main import app
from src.api.routes.watchlist import get_watchlist_service
from src.models.watchlist import WatchlistEntry, WatchlistPriority, WatchlistResponse

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_PHASES = {"A", "B", "C", "D", "E"}
VALID_TRENDS = {"up", "down", "sideways"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_watchlist_response(symbols: list[str]) -> WatchlistResponse:
    """Build a WatchlistResponse from a list of symbol strings."""
    entries = [
        WatchlistEntry(
            symbol=s,
            priority=WatchlistPriority.MEDIUM,
            min_confidence=None,
            enabled=True,
            added_at=datetime.now(UTC),
        )
        for s in symbols
    ]
    return WatchlistResponse(symbols=entries, count=len(entries), max_allowed=100)


def _make_mock_service(symbols: list[str]):
    """Return an AsyncMock WatchlistService that returns the given symbols."""
    mock = AsyncMock()
    mock.get_watchlist = AsyncMock(return_value=_make_watchlist_response(symbols))
    return mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client():
    """HTTP test client using ASGI transport (no running server needed)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Helper to override FastAPI dependency
# ---------------------------------------------------------------------------


def override_service(symbols: list[str]):
    """
    Returns a FastAPI dependency override that yields a mock WatchlistService.

    Usage:
        app.dependency_overrides[get_watchlist_service] = override_service(["AAPL"])
        ...
        del app.dependency_overrides[get_watchlist_service]
    """
    mock_svc = _make_mock_service(symbols)

    async def _dep():
        yield mock_svc

    return _dep


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_endpoint_returns_200(client):
    """GET /api/v1/watchlist/status returns 200 OK."""
    app.dependency_overrides[get_watchlist_service] = override_service(["AAPL", "TSLA"])
    try:
        response = await client.get("/api/v1/watchlist/status")
    finally:
        del app.dependency_overrides[get_watchlist_service]
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_status_response_has_symbols_list(client):
    """Response body contains a 'symbols' list."""
    app.dependency_overrides[get_watchlist_service] = override_service(["AAPL"])
    try:
        response = await client.get("/api/v1/watchlist/status")
    finally:
        del app.dependency_overrides[get_watchlist_service]
    data = response.json()
    assert "symbols" in data
    assert isinstance(data["symbols"], list)


@pytest.mark.asyncio
async def test_status_symbol_count_matches_watchlist(client):
    """Number of symbols in response equals the watchlist size."""
    symbols = ["AAPL", "TSLA", "SPY"]
    app.dependency_overrides[get_watchlist_service] = override_service(symbols)
    try:
        response = await client.get("/api/v1/watchlist/status")
    finally:
        del app.dependency_overrides[get_watchlist_service]
    assert len(response.json()["symbols"]) == len(symbols)


@pytest.mark.asyncio
async def test_status_each_entry_has_required_fields(client):
    """Each symbol entry contains all required fields."""
    required = {
        "symbol",
        "current_phase",
        "phase_confidence",
        "cause_progress_pct",
        "recent_bars",
        "trend_direction",
        "last_updated",
    }
    app.dependency_overrides[get_watchlist_service] = override_service(["AAPL"])
    try:
        response = await client.get("/api/v1/watchlist/status")
    finally:
        del app.dependency_overrides[get_watchlist_service]
    entry = response.json()["symbols"][0]
    assert required.issubset(entry.keys())


@pytest.mark.asyncio
async def test_status_phase_is_valid_wyckoff_phase(client):
    """current_phase for each entry must be one of A/B/C/D/E."""
    syms = ["AAPL", "TSLA", "NVDA", "SPY", "QQQ"]
    app.dependency_overrides[get_watchlist_service] = override_service(syms)
    try:
        response = await client.get("/api/v1/watchlist/status")
    finally:
        del app.dependency_overrides[get_watchlist_service]
    for entry in response.json()["symbols"]:
        assert (
            entry["current_phase"] in VALID_PHASES
        ), f"{entry['symbol']}: unexpected phase {entry['current_phase']}"


@pytest.mark.asyncio
async def test_status_phase_confidence_in_range(client):
    """phase_confidence must be between 0.0 and 1.0."""
    app.dependency_overrides[get_watchlist_service] = override_service(["AAPL"])
    try:
        response = await client.get("/api/v1/watchlist/status")
    finally:
        del app.dependency_overrides[get_watchlist_service]
    entry = response.json()["symbols"][0]
    assert 0.0 <= entry["phase_confidence"] <= 1.0


@pytest.mark.asyncio
async def test_status_cause_progress_in_range(client):
    """cause_progress_pct must be between 0 and 100."""
    app.dependency_overrides[get_watchlist_service] = override_service(["AAPL"])
    try:
        response = await client.get("/api/v1/watchlist/status")
    finally:
        del app.dependency_overrides[get_watchlist_service]
    entry = response.json()["symbols"][0]
    assert 0.0 <= entry["cause_progress_pct"] <= 100.0


@pytest.mark.asyncio
async def test_status_recent_bars_is_list(client):
    """recent_bars must be a list."""
    app.dependency_overrides[get_watchlist_service] = override_service(["AAPL"])
    try:
        response = await client.get("/api/v1/watchlist/status")
    finally:
        del app.dependency_overrides[get_watchlist_service]
    entry = response.json()["symbols"][0]
    assert isinstance(entry["recent_bars"], list)


@pytest.mark.asyncio
async def test_status_recent_bars_contain_ohlcv_fields(client):
    """Each bar in recent_bars must have o, h, l, c, v fields."""
    app.dependency_overrides[get_watchlist_service] = override_service(["AAPL"])
    try:
        response = await client.get("/api/v1/watchlist/status")
    finally:
        del app.dependency_overrides[get_watchlist_service]
    entry = response.json()["symbols"][0]
    assert len(entry["recent_bars"]) > 0
    bar = entry["recent_bars"][0]
    for field in ("o", "h", "l", "c", "v"):
        assert field in bar, f"Bar missing field: {field}"


@pytest.mark.asyncio
async def test_status_trend_direction_is_valid(client):
    """trend_direction must be one of up/down/sideways."""
    app.dependency_overrides[get_watchlist_service] = override_service(["AAPL"])
    try:
        response = await client.get("/api/v1/watchlist/status")
    finally:
        del app.dependency_overrides[get_watchlist_service]
    entry = response.json()["symbols"][0]
    assert entry["trend_direction"] in VALID_TRENDS


@pytest.mark.asyncio
async def test_status_empty_watchlist_returns_empty_symbols(client):
    """Empty watchlist returns symbols: []."""
    app.dependency_overrides[get_watchlist_service] = override_service([])
    try:
        response = await client.get("/api/v1/watchlist/status")
    finally:
        del app.dependency_overrides[get_watchlist_service]
    assert response.status_code == 200
    assert response.json()["symbols"] == []


@pytest.mark.asyncio
async def test_status_symbol_name_matches_watchlist(client):
    """Symbol names in response match the watchlist symbols."""
    app.dependency_overrides[get_watchlist_service] = override_service(["GOOGL", "AMZN"])
    try:
        response = await client.get("/api/v1/watchlist/status")
    finally:
        del app.dependency_overrides[get_watchlist_service]
    returned = {e["symbol"] for e in response.json()["symbols"]}
    assert returned == {"GOOGL", "AMZN"}


@pytest.mark.asyncio
async def test_status_deterministic_output(client):
    """Same symbol always returns the same phase (deterministic mock)."""
    app.dependency_overrides[get_watchlist_service] = override_service(["AAPL"])
    try:
        r1 = await client.get("/api/v1/watchlist/status")
    finally:
        del app.dependency_overrides[get_watchlist_service]

    app.dependency_overrides[get_watchlist_service] = override_service(["AAPL"])
    try:
        r2 = await client.get("/api/v1/watchlist/status")
    finally:
        del app.dependency_overrides[get_watchlist_service]

    assert r1.json()["symbols"][0]["current_phase"] == r2.json()["symbols"][0]["current_phase"]
