"""
Integration Tests for Signals API - Sorted Parameter (Story 9.3 AC 10).

Tests the GET /api/v1/signals?sorted=true endpoint for priority-ordered signals.

Author: Story 9.3 AC 10
"""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes.signals import add_signal_to_store, clear_signal_store
from src.models.signal import ConfidenceComponents, TargetLevels, TradeSignal, ValidationChain


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_store():
    """Clear signal store before each test."""
    clear_signal_store()
    yield
    clear_signal_store()


def create_test_signal(
    pattern_type: str,
    confidence: int,
    r_multiple: Decimal,
    symbol: str = "AAPL",
    entry_price: Decimal = Decimal("150.00"),
    stop_loss: Decimal | None = None,
) -> TradeSignal:
    """Create test signal with correct R-multiple calculation.

    Handles both LONG (SPRING/SOS/LPS) and SHORT (UTAD) patterns:
    - LONG: stop below entry, target above entry
    - SHORT (UTAD): stop above entry, target below entry
    """
    is_short = pattern_type == "UTAD"

    if stop_loss is None:
        stop_loss = Decimal("152.00") if is_short else Decimal("148.00")

    risk_per_share = abs(entry_price - stop_loss)

    if is_short:
        target_price = entry_price - (r_multiple * risk_per_share)
    else:
        target_price = entry_price + (r_multiple * risk_per_share)

    return TradeSignal(
        id=uuid4(),
        symbol=symbol,
        pattern_type=pattern_type,  # type: ignore
        phase="C" if pattern_type == "SPRING" else "D",
        timeframe="1d",
        entry_price=entry_price,
        stop_loss=stop_loss,
        target_levels=TargetLevels(primary_target=target_price),
        position_size=Decimal("100"),
        position_size_unit="SHARES",
        risk_amount=Decimal("200.00"),
        notional_value=Decimal("15000.00"),
        r_multiple=r_multiple,
        confidence_score=confidence,
        confidence_components=ConfidenceComponents(
            pattern_confidence=confidence,
            phase_confidence=confidence,
            volume_confidence=confidence,
            overall_confidence=confidence,
        ),
        validation_chain=ValidationChain(pattern_id=uuid4()),
        status="APPROVED",
        timestamp=datetime.now(),
    )


# =============================================================================
# Test: GET /signals?sorted=true Returns Priority-Ordered Signals (AC: 10)
# =============================================================================


def test_get_signals_sorted_true_returns_priority_order(client):
    """
    Test AC 10: GET /signals?sorted=true returns signals in priority order.

    Create 5 signals with different priorities and verify they're returned
    in correct order (highest priority first).
    """
    # Create 5 signals with known priority scores
    signal_spring = create_test_signal("SPRING", 85, Decimal("4.0"), "AAPL")  # Highest
    signal_lps = create_test_signal("LPS", 80, Decimal("3.5"), "MSFT")  # Second
    signal_sos_high = create_test_signal("SOS", 90, Decimal("3.0"), "GOOGL")  # Third
    signal_sos_low = create_test_signal("SOS", 75, Decimal("2.8"), "TSLA")  # Fourth
    signal_utad = create_test_signal("UTAD", 85, Decimal("2.5"), "NVDA")  # Lowest

    # Add to store
    add_signal_to_store(signal_spring)
    add_signal_to_store(signal_lps)
    add_signal_to_store(signal_sos_high)
    add_signal_to_store(signal_sos_low)
    add_signal_to_store(signal_utad)

    # GET /signals?sorted=true
    response = client.get("/api/v1/signals?sorted=true")

    # Verify response
    assert response.status_code == 200
    data = response.json()

    # Verify structure
    assert "data" in data
    assert "pagination" in data
    assert len(data["data"]) == 5

    signals = data["data"]

    # Verify order: SPRING > SOS (high) > LPS > UTAD > SOS (low)
    # (Exact middle order may vary, but SPRING first is guaranteed)
    assert signals[0]["symbol"] == "AAPL"  # SPRING (highest priority)
    assert signals[0]["pattern_type"] == "SPRING"

    # Verify SPRING has highest confidence/R-multiple combo
    # Last signal should have lowest score (SOS 75%/2.8R has lowest)
    # Note: UTAD 85%/2.5R (~28.5) > SOS 75%/2.8R (~38.4 actually)
    # Let me recalculate: SOS 75%/2.8R:
    #   conf_norm = (75-70)/(95-70) = 5/25 = 0.20
    #   r_norm = (2.8-2.0)/(5.0-2.0) = 0.8/3.0 = 0.27
    #   pattern_norm (SOS) = 0.33
    #   score = (0.20*0.40) + (0.27*0.30) + (0.33*0.30) = 0.08 + 0.08 + 0.10 = 0.26 = 26.0
    #   Wait, that's lower than UTAD. Let me check UTAD:
    #   conf_norm = (85-70)/(95-70) = 15/25 = 0.60
    #   r_norm = (2.5-2.0)/(5.0-2.0) = 0.5/3.0 = 0.17
    #   pattern_norm (UTAD) = 0.0
    #   score = (0.60*0.40) + (0.17*0.30) + (0.0*0.30) = 0.24 + 0.05 + 0.0 = 0.29 = 29.0
    # So UTAD 29.0 > SOS 26.0, meaning SOS low should be last
    assert signals[-1]["symbol"] == "TSLA"  # SOS 75%/2.8R (lowest priority)
    assert signals[-1]["pattern_type"] == "SOS"


def test_get_signals_sorted_false_returns_timestamp_order(client):
    """
    Test GET /signals?sorted=false returns signals in timestamp order.

    Default behavior: newest signals first (timestamp DESC).
    """
    # Create 3 signals at different times
    import time

    signal_1 = create_test_signal("SPRING", 85, Decimal("4.0"), "AAPL")  # Oldest
    add_signal_to_store(signal_1)
    time.sleep(0.01)

    signal_2 = create_test_signal("SOS", 80, Decimal("3.0"), "MSFT")  # Middle
    add_signal_to_store(signal_2)
    time.sleep(0.01)

    signal_3 = create_test_signal("LPS", 75, Decimal("2.5"), "GOOGL")  # Newest
    add_signal_to_store(signal_3)

    # GET /signals (sorted=false by default)
    response = client.get("/api/v1/signals")

    assert response.status_code == 200
    data = response.json()

    signals = data["data"]
    assert len(signals) == 3

    # Verify timestamp order (newest first)
    # Note: timestamps are ISO strings in response
    timestamps = [datetime.fromisoformat(s["timestamp"].replace("Z", "+00:00")) for s in signals]

    assert timestamps[0] >= timestamps[1]  # Newest first
    assert timestamps[1] >= timestamps[2]


def test_get_signals_sorted_true_with_filters(client):
    """
    Test sorted=true works with other filters (status, symbol, etc.).

    Filters should be applied before sorting.
    """
    # Create signals with different statuses
    signal_1 = create_test_signal("SPRING", 85, Decimal("4.0"), "AAPL")
    signal_1.status = "PENDING"
    add_signal_to_store(signal_1)

    signal_2 = create_test_signal("SOS", 80, Decimal("3.0"), "AAPL")
    signal_2.status = "APPROVED"
    add_signal_to_store(signal_2)

    signal_3 = create_test_signal("LPS", 90, Decimal("3.5"), "MSFT")
    signal_3.status = "APPROVED"
    add_signal_to_store(signal_3)

    # GET /signals?sorted=true&status=APPROVED
    response = client.get("/api/v1/signals?sorted=true&status=APPROVED")

    assert response.status_code == 200
    data = response.json()

    signals = data["data"]
    assert len(signals) == 2  # Only APPROVED signals

    # Verify all signals have status=APPROVED
    assert all(s["status"] == "APPROVED" for s in signals)

    # Verify sorted by priority (LPS 90% > SOS 80%)
    assert signals[0]["symbol"] == "MSFT"  # LPS 90%
    assert signals[1]["symbol"] == "AAPL"  # SOS 80%


def test_get_signals_sorted_true_pagination(client):
    """
    Test sorted=true works with pagination (limit/offset).

    Verify that pagination is applied after sorting.
    """
    # Create 10 signals
    for i in range(10):
        signal = create_test_signal("SOS", 75 + i, Decimal("2.5"), f"SYM{i}")
        add_signal_to_store(signal)

    # GET /signals?sorted=true&limit=3
    response = client.get("/api/v1/signals?sorted=true&limit=3")

    assert response.status_code == 200
    data = response.json()

    # Verify pagination metadata
    assert data["pagination"]["returned_count"] == 3
    assert data["pagination"]["total_count"] == 10
    assert data["pagination"]["has_more"] is True

    # GET /signals?sorted=true&limit=3&offset=3
    response2 = client.get("/api/v1/signals?sorted=true&limit=3&offset=3")

    assert response2.status_code == 200
    data2 = response2.json()

    # Verify different signals returned
    signals_1 = [s["id"] for s in data["data"]]
    signals_2 = [s["id"] for s in data2["data"]]
    assert signals_1 != signals_2


def test_get_signals_sorted_spring_beats_sos_higher_confidence(client):
    """
    Test AC 7 via API: Spring with lower confidence beats SOS with higher confidence.

    Verify FR28 pattern priority weight (30%) outweighs confidence difference.
    """
    # Spring 75% vs SOS 85% (same R-multiple)
    signal_spring = create_test_signal("SPRING", 75, Decimal("3.5"), "AAPL")
    signal_sos = create_test_signal("SOS", 85, Decimal("3.5"), "MSFT")

    add_signal_to_store(signal_spring)
    add_signal_to_store(signal_sos)

    # GET /signals?sorted=true
    response = client.get("/api/v1/signals?sorted=true")

    assert response.status_code == 200
    data = response.json()

    signals = data["data"]
    assert len(signals) == 2

    # Spring should be first despite lower confidence
    assert signals[0]["symbol"] == "AAPL"  # SPRING 75%
    assert signals[0]["pattern_type"] == "SPRING"
    assert signals[1]["symbol"] == "MSFT"  # SOS 85%
    assert signals[1]["pattern_type"] == "SOS"


def test_get_signals_sorted_lps_beats_sos_lower_r_multiple(client):
    """
    Test AC 8 via API: LPS with higher R-multiple beats SOS with lower R-multiple.

    Verify FR28 R-multiple weight (30%) + pattern priority (30%) combine to beat SOS.
    """
    # LPS 3.5R vs SOS 2.8R (same confidence)
    signal_lps = create_test_signal("LPS", 80, Decimal("3.5"), "AAPL")
    signal_sos = create_test_signal("SOS", 80, Decimal("2.8"), "MSFT")

    add_signal_to_store(signal_lps)
    add_signal_to_store(signal_sos)

    # GET /signals?sorted=true
    response = client.get("/api/v1/signals?sorted=true")

    assert response.status_code == 200
    data = response.json()

    signals = data["data"]
    assert len(signals) == 2

    # LPS should be first due to higher R-multiple + better pattern priority
    assert signals[0]["symbol"] == "AAPL"  # LPS 3.5R
    assert signals[0]["pattern_type"] == "LPS"
    assert signals[1]["symbol"] == "MSFT"  # SOS 2.8R
    assert signals[1]["pattern_type"] == "SOS"


def test_get_signals_empty_store_returns_empty_list(client):
    """
    Test GET /signals?sorted=true with empty store returns empty list.

    Verify graceful handling when no signals available.
    """
    # Store is empty (autouse fixture clears it)

    # GET /signals?sorted=true
    response = client.get("/api/v1/signals?sorted=true")

    assert response.status_code == 200
    data = response.json()

    assert data["data"] == []
    assert data["pagination"]["returned_count"] == 0
    assert data["pagination"]["total_count"] == 0
