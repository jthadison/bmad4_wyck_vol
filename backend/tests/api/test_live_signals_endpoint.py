"""
Tests for Live Signals API Endpoint (Story 25.12).

Covers all 7 Acceptance Criteria:
- AC1: Endpoint exists and returns 200
- AC2: Returns only recent signals (time window filter)
- AC3: Since timestamp parameter works
- AC4: Symbol filter works
- AC5: Window capped at 300 seconds (returns 400)
- AC6: Returns same schema as /api/v1/signals
- AC7: Authentication required
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import quote
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.signal import ConfidenceComponents, TargetLevels, TradeSignal
from src.models.validation import ValidationChain
from src.repositories.signal_repository import SignalRepository


@pytest.fixture
async def seed_live_signals(db_session: AsyncSession) -> list[TradeSignal]:
    """
    Seed database with signals at controlled timestamps for testing.

    Creates signals with varying created_at timestamps to test time-window logic.
    """
    repo = SignalRepository(db_session=db_session)
    now = datetime.now(UTC)

    signals = []

    # Signal 1: Created 5 seconds ago (inside 30s window)
    signal_1 = TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        pattern_type="SPRING",
        phase="C",
        timeframe="1d",
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("145.00"),
        target_levels=TargetLevels(primary_target=Decimal("170.00")),
        position_size=Decimal("100"),
        risk_amount=Decimal("500.00"),
        r_multiple=Decimal("4.0"),
        confidence_score=85,
        confidence_components=ConfidenceComponents(
            pattern_confidence=88,
            phase_confidence=82,
            volume_confidence=80,
            overall_confidence=85,
        ),
        validation_chain=ValidationChain(
            pattern_id=uuid4(),
            validation_results=[],
            overall_status="PASS",
        ),
        status="APPROVED",
        timestamp=now - timedelta(seconds=5),
        created_at=now - timedelta(seconds=5),
        notional_value=Decimal("15000.00"),  # entry_price * position_size
    )
    await repo.save_signal(signal_1)
    signals.append(signal_1)

    # Signal 2: Created 60 seconds ago (outside 30s window)
    signal_2 = TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        pattern_type="LPS",
        phase="E",
        timeframe="1d",
        entry_price=Decimal("151.00"),
        stop_loss=Decimal("146.00"),
        target_levels=TargetLevels(primary_target=Decimal("171.00")),
        position_size=Decimal("100"),
        risk_amount=Decimal("500.00"),
        r_multiple=Decimal("4.0"),
        confidence_score=82,
        confidence_components=ConfidenceComponents(
            pattern_confidence=85,
            phase_confidence=80,
            volume_confidence=78,
            overall_confidence=82,
        ),
        validation_chain=ValidationChain(
            pattern_id=uuid4(),
            validation_results=[],
            overall_status="PASS",
        ),
        status="APPROVED",
        timestamp=now - timedelta(seconds=60),
        created_at=now - timedelta(seconds=60),
        notional_value=Decimal("15100.00"),  # entry_price * position_size
    )
    await repo.save_signal(signal_2)
    signals.append(signal_2)

    # Signal 3: Created 10 seconds ago, TSLA (for symbol filter test)
    signal_3 = TradeSignal(
        id=uuid4(),
        symbol="TSLA",
        pattern_type="SOS",
        phase="D",
        timeframe="1d",
        entry_price=Decimal("200.00"),
        stop_loss=Decimal("195.00"),
        target_levels=TargetLevels(primary_target=Decimal("220.00")),
        position_size=Decimal("50"),
        risk_amount=Decimal("250.00"),
        r_multiple=Decimal("4.0"),
        confidence_score=80,
        confidence_components=ConfidenceComponents(
            pattern_confidence=82,
            phase_confidence=80,
            volume_confidence=78,
            overall_confidence=80,
        ),
        validation_chain=ValidationChain(
            pattern_id=uuid4(),
            validation_results=[],
            overall_status="PASS",
        ),
        status="APPROVED",
        timestamp=now - timedelta(seconds=10),
        created_at=now - timedelta(seconds=10),
        notional_value=Decimal("10000.00"),  # entry_price * position_size
    )
    await repo.save_signal(signal_3)
    signals.append(signal_3)

    # Signal 4: Created 3 seconds ago, REJECTED status (should not appear)
    signal_4 = TradeSignal(
        id=uuid4(),
        symbol="MSFT",
        pattern_type="SPRING",
        phase="C",
        timeframe="1d",
        entry_price=Decimal("300.00"),
        stop_loss=Decimal("295.00"),
        target_levels=TargetLevels(primary_target=Decimal("320.00")),
        position_size=Decimal("30"),
        risk_amount=Decimal("150.00"),
        r_multiple=Decimal("4.0"),
        confidence_score=75,
        confidence_components=ConfidenceComponents(
            pattern_confidence=78,
            phase_confidence=75,
            volume_confidence=72,
            overall_confidence=75,
        ),
        validation_chain=ValidationChain(
            pattern_id=uuid4(),
            validation_results=[],
            overall_status="FAIL",
        ),
        status="REJECTED",
        timestamp=now - timedelta(seconds=3),
        created_at=now - timedelta(seconds=3),
        notional_value=Decimal("9000.00"),  # entry_price * position_size
    )
    await repo.save_signal(signal_4)
    signals.append(signal_4)

    return signals


@pytest.mark.asyncio
async def test_ac1_endpoint_exists_and_returns_200(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    """
    AC1: Endpoint exists and returns 200.

    Given an authenticated client
    When GET /api/v1/signals/live is called with no parameters
    Then HTTP 200 is returned
    And the response body is a JSON list (possibly empty)
    """
    response = await async_client.get("/api/v1/signals/live", headers=auth_headers)

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_ac2_returns_only_recent_signals(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    seed_live_signals: list[TradeSignal],
) -> None:
    """
    AC2: Returns only recent signals.

    Given a signal created 60 seconds ago (outside 30s window)
    And a signal created 5 seconds ago (inside 30s window)
    When GET /api/v1/signals/live?window_seconds=30 is called
    Then only the 5-second-old signal is returned
    And the 60-second-old signal is not in the response
    """
    response = await async_client.get(
        "/api/v1/signals/live?window_seconds=30",
        headers=auth_headers,
    )

    assert response.status_code == 200
    signals = response.json()

    # Should only get signals from last 30 seconds (signal_1 at -5s, signal_3 at -10s)
    # signal_2 at -60s should be excluded
    assert len(signals) == 2
    symbols = {s["symbol"] for s in signals}
    assert symbols == {"AAPL", "TSLA"}  # signal_1 and signal_3

    # Verify 60-second-old signal is NOT present
    patterns = {s["pattern_type"] for s in signals}
    assert "LPS" not in patterns  # signal_2 is LPS and outside window


@pytest.mark.asyncio
async def test_ac3_since_timestamp_parameter_works(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    seed_live_signals: list[TradeSignal],
) -> None:
    """
    AC3: Since timestamp parameter works.

    Given a client last polled at timestamp T
    And signals exist both before and after T
    When GET /api/v1/signals/live?since=T is called (ISO 8601 format)
    Then only signals with created_at > T are returned
    And signals with created_at <= T are excluded
    """
    # Set since to 7 seconds ago (should get signal_1 at -5s, not signal_3 at -10s)
    since_timestamp = datetime.now(UTC) - timedelta(seconds=7)
    since_iso = quote(since_timestamp.isoformat())

    response = await async_client.get(
        f"/api/v1/signals/live?since={since_iso}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    signals = response.json()

    # Should only get signal_1 (created 5s ago)
    assert len(signals) == 1
    assert signals[0]["symbol"] == "AAPL"
    assert signals[0]["pattern_type"] == "SPRING"


@pytest.mark.asyncio
async def test_ac4_symbol_filter_works(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    seed_live_signals: list[TradeSignal],
) -> None:
    """
    AC4: Symbol filter works.

    Given approved signals exist for both AAPL and TSLA in the last 30 seconds
    When GET /api/v1/signals/live?symbol=AAPL is called
    Then only AAPL signals are returned
    And no TSLA signals appear in the response
    """
    response = await async_client.get(
        "/api/v1/signals/live?symbol=AAPL",
        headers=auth_headers,
    )

    assert response.status_code == 200
    signals = response.json()

    # Should only get AAPL signal(s)
    assert len(signals) >= 1
    for signal in signals:
        assert signal["symbol"] == "AAPL"

    # Verify no TSLA
    symbols = {s["symbol"] for s in signals}
    assert "TSLA" not in symbols


@pytest.mark.asyncio
async def test_ac5_window_capped_at_300_seconds(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    """
    AC5: Window capped at 300 seconds.

    Given window_seconds = 600 in the query parameter
    When GET /api/v1/signals/live?window_seconds=600 is called
    Then HTTP 400 is returned
    And the error message contains "Maximum window is 300 seconds"
    """
    response = await async_client.get(
        "/api/v1/signals/live?window_seconds=600",
        headers=auth_headers,
    )

    assert response.status_code == 400
    error_detail = response.json()["detail"]
    assert "Maximum window is 300 seconds" in error_detail


@pytest.mark.asyncio
async def test_ac6_returns_same_schema_as_signals_endpoint(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    seed_live_signals: list[TradeSignal],
) -> None:
    """
    AC6: Returns same schema as /api/v1/signals.

    Given live signals exist in the database
    When GET /api/v1/signals/live is called
    Then the response uses the same TradeSignal schema
    And all required fields are present
    And campaign_id is included in the response (may be null)
    """
    response = await async_client.get("/api/v1/signals/live", headers=auth_headers)

    assert response.status_code == 200
    signals = response.json()
    assert len(signals) >= 1

    # Verify required fields match TradeSignal schema
    signal = signals[0]
    required_fields = [
        "id",
        "symbol",
        "pattern_type",
        "phase",
        "timeframe",
        "entry_price",
        "stop_loss",
        "target_levels",
        "position_size",
        "risk_amount",
        "r_multiple",
        "confidence_score",
        "status",
        "timestamp",
        "created_at",
    ]
    for field in required_fields:
        assert field in signal, f"Missing required field: {field}"

    # Verify campaign_id is present (even if null)
    assert "campaign_id" in signal


@pytest.mark.asyncio
async def test_ac7_authentication_required(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """
    AC7: Authentication required.

    Given a request with no Authorization header
    When GET /api/v1/signals/live is called
    Then HTTP 401 or 403 is returned (FastAPI HTTPBearer returns 403)
    And no signal data is returned
    """
    # Call without auth headers
    response = await async_client.get("/api/v1/signals/live")

    # HTTPBearer security returns 403 when no credentials provided
    # (401 is returned when credentials are invalid)
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_since_and_window_both_provided_uses_more_restrictive(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    seed_live_signals: list[TradeSignal],
) -> None:
    """
    Edge case: When both since and window_seconds are provided,
    the more restrictive (later) timestamp should be used.

    Given signals at -5s, -10s, -60s
    When since=100s ago AND window_seconds=30
    Then effective_since = max(since, now-30s) = now-30s (more restrictive)
    And only signals from last 30s are returned
    """
    # since=100s ago (less restrictive), window=30s (more restrictive)
    since_timestamp = datetime.now(UTC) - timedelta(seconds=100)
    since_iso = quote(since_timestamp.isoformat())

    response = await async_client.get(
        f"/api/v1/signals/live?since={since_iso}&window_seconds=30",
        headers=auth_headers,
    )

    assert response.status_code == 200
    signals = response.json()

    # Should use window_seconds=30 (more restrictive)
    # Should get signal_1 (-5s) and signal_3 (-10s), NOT signal_2 (-60s)
    assert len(signals) == 2


@pytest.mark.asyncio
async def test_since_more_restrictive_than_window(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    seed_live_signals: list[TradeSignal],
) -> None:
    """
    Edge case: When since is more restrictive than window_seconds.

    Given signals at -5s, -10s, -60s
    When since=7s ago AND window_seconds=300 (5 min)
    Then effective_since = max(since, now-300s) = since (more restrictive)
    And only signals newer than 7s ago are returned
    """
    # since=7s ago (more restrictive), window=300s (less restrictive)
    since_timestamp = datetime.now(UTC) - timedelta(seconds=7)
    since_iso = quote(since_timestamp.isoformat())

    response = await async_client.get(
        f"/api/v1/signals/live?since={since_iso}&window_seconds=300",
        headers=auth_headers,
    )

    assert response.status_code == 200
    signals = response.json()

    # Should use since=7s ago (more restrictive)
    # Should get only signal_1 (-5s), NOT signal_3 (-10s) or signal_2 (-60s)
    assert len(signals) == 1
    assert signals[0]["pattern_type"] == "SPRING"


@pytest.mark.asyncio
async def test_only_approved_signals_returned(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    seed_live_signals: list[TradeSignal],
) -> None:
    """
    Verify that only signals with status=APPROVED are returned.

    Given signals with APPROVED and REJECTED status
    When GET /api/v1/signals/live is called
    Then only APPROVED signals are in the response
    """
    response = await async_client.get("/api/v1/signals/live", headers=auth_headers)

    assert response.status_code == 200
    signals = response.json()

    # Verify all returned signals are APPROVED
    for signal in signals:
        assert signal["status"] == "APPROVED"

    # Verify REJECTED signal is not present
    symbols = {s["symbol"] for s in signals}
    assert "MSFT" not in symbols  # signal_4 is MSFT and REJECTED


@pytest.mark.asyncio
async def test_empty_result_when_no_signals_in_window(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    seed_live_signals: list[TradeSignal],
) -> None:
    """
    Verify endpoint returns empty list when no signals match the time window.

    Given signals older than 1 second
    When window_seconds=1 is specified
    Then an empty list is returned
    """
    response = await async_client.get(
        "/api/v1/signals/live?window_seconds=1",
        headers=auth_headers,
    )

    assert response.status_code == 200
    signals = response.json()
    assert signals == []


@pytest.mark.asyncio
async def test_since_excludes_signal_at_exact_timestamp(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    """
    AC3 STRICT >: Signal created at EXACTLY the since timestamp must be EXCLUDED.

    This verifies the fix for the blocking issue where >= was incorrectly used.
    Per AC3: "only signals with created_at > T are returned"

    With >=, polling clients would receive duplicate signals on every poll.
    With > (correct), signals are delivered exactly once.

    Given a signal created at timestamp T
    When GET /api/v1/signals/live?since=T is called
    Then the signal at timestamp T is EXCLUDED (created_at > T, not >=)
    """
    from src.models.signal import ConfidenceComponents, TargetLevels, TradeSignal
    from src.models.validation import ValidationChain
    from src.repositories.signal_repository import SignalRepository

    repo = SignalRepository(db_session=db_session)
    exact_timestamp = datetime.now(UTC) - timedelta(seconds=10)

    # Create a signal at EXACTLY the since timestamp
    signal_at_exact_time = TradeSignal(
        id=uuid4(),
        symbol="TEST",
        pattern_type="SPRING",
        phase="C",
        timeframe="1d",
        entry_price=Decimal("100.00"),
        stop_loss=Decimal("95.00"),
        target_levels=TargetLevels(primary_target=Decimal("120.00")),
        position_size=Decimal("100"),
        risk_amount=Decimal("500.00"),
        r_multiple=Decimal("4.0"),
        confidence_score=85,
        confidence_components=ConfidenceComponents(
            pattern_confidence=88,
            phase_confidence=82,
            volume_confidence=80,
            overall_confidence=85,
        ),
        validation_chain=ValidationChain(
            pattern_id=uuid4(),
            validation_results=[],
            overall_status="PASS",
        ),
        status="APPROVED",
        timestamp=exact_timestamp,
        created_at=exact_timestamp,  # EXACTLY at the since timestamp
        notional_value=Decimal("10000.00"),
    )
    await repo.save_signal(signal_at_exact_time)

    # Query with since = exact_timestamp (should EXCLUDE the signal at that exact time)
    since_iso = quote(exact_timestamp.isoformat())
    response = await async_client.get(
        f"/api/v1/signals/live?since={since_iso}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    signals = response.json()

    # AC3: created_at > T (strict greater-than)
    # The signal at EXACTLY timestamp T should be EXCLUDED
    test_signal_ids = [s["id"] for s in signals if s["symbol"] == "TEST"]
    assert len(test_signal_ids) == 0, (
        f"Signal at exact timestamp {exact_timestamp.isoformat()} was incorrectly included. "
        "AC3 requires strict > (not >=) to prevent duplicate delivery on polling."
    )
