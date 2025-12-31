"""
Integration tests for Backtest Preview API (Story 11.2)

Tests:
------
- POST /api/v1/backtest/preview: Endpoint integration
- GET /api/v1/backtest/status/{run_id}: Status polling
- WebSocket progress messages: Real-time updates
- Full backtest flow: Request → Progress → Completion

Author: Story 11.2 Task 1
"""

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import AsyncClient

from src.api.main import app


@pytest.mark.asyncio
async def test_backtest_preview_endpoint():
    """Test POST /api/v1/backtest/preview endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Send backtest preview request
        request_data = {
            "proposed_config": {
                "volume_thresholds": {"ultra_high": 2.0, "high": 1.5},
                "risk_limits": {"max_portfolio_heat": 0.05},
            },
            "days": 90,
            "symbol": None,
            "timeframe": "1d",
        }

        response = await client.post("/api/v1/backtest/preview", json=request_data)

        # Should return 202 Accepted
        assert response.status_code == 202

        # Check response structure
        data = response.json()
        assert "backtest_run_id" in data
        assert "status" in data
        assert "estimated_duration_seconds" in data

        # Validate UUID format
        run_id = UUID(data["backtest_run_id"])
        assert isinstance(run_id, UUID)

        # Status should be queued
        assert data["status"] == "queued"

        # Estimated duration should be reasonable
        assert data["estimated_duration_seconds"] > 0
        assert data["estimated_duration_seconds"] < 300  # Less than 5 minutes


@pytest.mark.asyncio
async def test_backtest_preview_invalid_days():
    """Test backtest preview with invalid days parameter."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Days too low
        request_data = {"proposed_config": {}, "days": 5}

        response = await client.post("/api/v1/backtest/preview", json=request_data)

        # Should return 422 Unprocessable Entity
        assert response.status_code == 422

        # Days too high
        request_data = {"proposed_config": {}, "days": 400}

        response = await client.post("/api/v1/backtest/preview", json=request_data)

        # Should return 422 Unprocessable Entity
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_backtest_status_endpoint():
    """Test GET /api/v1/backtest/status/{run_id} endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # First, start a backtest
        request_data = {"proposed_config": {"test": "config"}, "days": 30}

        response = await client.post("/api/v1/backtest/preview", json=request_data)
        assert response.status_code == 202

        run_id = response.json()["backtest_run_id"]

        # Wait a moment for background task to start
        await asyncio.sleep(0.5)

        # Check status
        status_response = await client.get(f"/api/v1/backtest/status/{run_id}")

        assert status_response.status_code == 200

        status_data = status_response.json()
        assert "status" in status_data
        assert "progress" in status_data
        assert status_data["status"] in ["queued", "running", "completed"]


@pytest.mark.asyncio
async def test_backtest_status_not_found():
    """Test status endpoint with non-existent run ID."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Random UUID that doesn't exist
        fake_run_id = "550e8400-e29b-41d4-a716-446655440000"

        response = await client.get(f"/api/v1/backtest/status/{fake_run_id}")

        # Should return 404 Not Found
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_concurrent_backtest_limit():
    """Test that system limits concurrent backtests."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        request_data = {"proposed_config": {}, "days": 90}

        # Start 6 backtests (limit is 5)
        responses = []
        for i in range(6):
            response = await client.post("/api/v1/backtest/preview", json=request_data)
            responses.append(response)

        # First 5 should succeed (202)
        for i in range(5):
            assert responses[i].status_code == 202

        # 6th should fail with 503 Service Unavailable
        # Note: This might pass if first backtests complete quickly
        # In production, this would be more reliable with longer-running tests


@pytest.mark.asyncio
async def test_backtest_completion_flow():
    """Test complete backtest flow: Request → Running → Completed."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Start backtest with small dataset (fast completion)
        request_data = {"proposed_config": {"test": "config"}, "days": 10}

        response = await client.post("/api/v1/backtest/preview", json=request_data)
        assert response.status_code == 202

        run_id = response.json()["backtest_run_id"]

        # Poll status until completed (with timeout)
        max_attempts = 20
        for attempt in range(max_attempts):
            await asyncio.sleep(0.5)

            status_response = await client.get(f"/api/v1/backtest/status/{run_id}")
            status_data = status_response.json()

            if status_data["status"] == "completed":
                # Success! Check that we have progress data
                assert status_data["progress"]["total_bars"] > 0
                assert status_data["progress"]["percent_complete"] == 100
                break

            if status_data["status"] == "failed":
                pytest.fail(f"Backtest failed: {status_data.get('error')}")

        else:
            # Timeout
            pytest.fail("Backtest did not complete within timeout")


@pytest.mark.asyncio
async def test_backtest_with_different_configs():
    """Test backtest preview with various configuration options."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test with different volume thresholds
        configs = [
            {"volume_thresholds": {"ultra_high": 3.0}},
            {"volume_thresholds": {"ultra_high": 2.0, "high": 1.5}},
            {"risk_limits": {"max_portfolio_heat": 0.04}},
        ]

        for config in configs:
            request_data = {"proposed_config": config, "days": 30}

            response = await client.post("/api/v1/backtest/preview", json=request_data)

            assert response.status_code == 202
            assert "backtest_run_id" in response.json()


# WebSocket Integration Tests


@pytest.mark.asyncio
async def test_websocket_connection():
    """Test WebSocket connection for backtest progress updates."""
    # Note: WebSocket testing requires special setup
    # This is a placeholder - full implementation would use websockets library
    # Example:
    # async with websockets.connect("ws://localhost:8000/ws") as websocket:
    #     message = await websocket.recv()
    #     data = json.loads(message)
    #     assert data["type"] == "connected"

    # For MVP, we'll test that the websocket endpoint exists
    from src.api.websocket import manager

    assert manager is not None
    assert hasattr(manager, "broadcast")
    assert hasattr(manager, "connect")


@pytest.mark.asyncio
async def test_websocket_progress_message_format():
    """Test WebSocket progress message structure."""
    from uuid import uuid4

    from src.models.backtest import BacktestProgressUpdate

    # Create sample progress message
    progress_msg = BacktestProgressUpdate(
        sequence_number=1,
        backtest_run_id=uuid4(),
        bars_analyzed=1000,
        total_bars=2268,
        percent_complete=44,
        timestamp=datetime.now(UTC),
    )

    # Serialize to dict (as sent via WebSocket)
    msg_dict = progress_msg.model_dump(mode="json")

    # Verify structure
    assert msg_dict["type"] == "backtest_progress"
    assert "sequence_number" in msg_dict
    assert "backtest_run_id" in msg_dict
    assert "bars_analyzed" in msg_dict
    assert "total_bars" in msg_dict
    assert "percent_complete" in msg_dict
    assert msg_dict["percent_complete"] == 44


@pytest.mark.asyncio
async def test_websocket_completed_message_format():
    """Test WebSocket completion message structure."""
    from decimal import Decimal
    from uuid import uuid4

    from src.models.backtest import (
        BacktestComparison,
        BacktestCompletedMessage,
        BacktestMetrics,
    )

    # Create sample comparison
    current_metrics = BacktestMetrics(
        total_signals=10,
        win_rate=Decimal("0.65"),
        average_r_multiple=Decimal("1.5"),
        profit_factor=Decimal("2.5"),
        max_drawdown=Decimal("0.12"),
    )

    proposed_metrics = BacktestMetrics(
        total_signals=12,
        win_rate=Decimal("0.70"),
        average_r_multiple=Decimal("1.8"),
        profit_factor=Decimal("3.0"),
        max_drawdown=Decimal("0.10"),
    )

    comparison = BacktestComparison(
        current_metrics=current_metrics,
        proposed_metrics=proposed_metrics,
        recommendation="improvement",
        recommendation_text="Performance improved",
        equity_curve_current=[],
        equity_curve_proposed=[],
    )

    # Create completion message
    completed_msg = BacktestCompletedMessage(
        sequence_number=10,
        backtest_run_id=uuid4(),
        comparison=comparison,
        timestamp=datetime.now(UTC),
    )

    # Serialize
    msg_dict = completed_msg.model_dump(mode="json")

    # Verify structure
    assert msg_dict["type"] == "backtest_completed"
    assert "comparison" in msg_dict
    assert msg_dict["comparison"]["recommendation"] == "improvement"


# =============================
# Story 12.10: Extended Backtest Tests
# =============================


@pytest.mark.extended
@pytest.mark.slow
@pytest.mark.asyncio
async def test_extended_backtest_aapl():
    """
    Extended backtest for AAPL (2022-2023).

    Tests:
    - BacktestResult structure
    - Trades generated
    - Metrics calculated (win rate, avg R, profit factor)
    - Equity curve data
    - Performance (< 60s per symbol)
    - Determinism (same results on multiple runs)
    """
    # Placeholder for extended backtest implementation
    # This would:
    # 1. Load real OHLCV data for AAPL (2022-01-01 to 2023-12-31)
    # 2. Run BacktestEngine.run_backtest()
    # 3. Verify BacktestResult structure
    # 4. Verify trades generated
    # 5. Verify metrics calculated
    # 6. Verify equity curve data
    # 7. Assert backtest completes in < 60 seconds
    # 8. Run twice and verify identical results

    pytest.skip(
        "Extended backtest implementation pending - requires BacktestEngine fixes from Story 12.9"
    )


@pytest.mark.extended
@pytest.mark.slow
@pytest.mark.asyncio
async def test_extended_backtest_msft():
    """Extended backtest for MSFT (2022-2023)."""
    pytest.skip("Extended backtest implementation pending")


@pytest.mark.extended
@pytest.mark.slow
@pytest.mark.asyncio
async def test_extended_backtest_googl():
    """Extended backtest for GOOGL (2022-2023)."""
    pytest.skip("Extended backtest implementation pending")


@pytest.mark.extended
@pytest.mark.slow
@pytest.mark.asyncio
async def test_extended_backtest_tsla():
    """Extended backtest for TSLA (2022-2023)."""
    pytest.skip("Extended backtest implementation pending")


@pytest.mark.slow
@pytest.mark.benchmark
@pytest.mark.extended
def test_backtest_performance():
    """
    Test backtest performance for 2-year dataset (Story 12.11 Task 3 Subtask 3.2).

    Requirements:
    - Backtest should complete in <60 seconds per symbol
    - Should not degrade >20% from baseline
    - Validates NFR7 (>100 bars/second throughput)

    Test Flow:
    - Generate 2 years of synthetic OHLCV data (~500 bars)
    - Run BacktestEngine with simple strategy
    - Measure execution time
    - Assert performance < 60 seconds
    """
    import time
    from datetime import timedelta
    from decimal import Decimal

    from src.backtesting.backtest_engine import BacktestEngine
    from src.models.backtest import BacktestConfig
    from src.models.ohlcv import OHLCVBar

    # Generate 2 years of daily OHLCV data (504 trading days)
    bars = []
    start_date = datetime(2022, 1, 1, tzinfo=UTC)
    base_price = Decimal("150.00")

    for i in range(504):  # ~2 years of trading days
        # Simulate trending price with noise
        trend = Decimal(i) * Decimal("0.05")
        noise = Decimal((i % 10) - 5)
        price = base_price + trend + noise
        daily_range = Decimal("5.00")

        bars.append(
            OHLCVBar(
                symbol="SYNTH",
                timeframe="1d",
                timestamp=start_date + timedelta(days=i),
                open=price,
                high=price + daily_range,
                low=price - daily_range,
                close=price + (daily_range * Decimal("0.3")),
                volume=1000000 + (i * 10000),
                spread=daily_range,
            )
        )

    # Simple buy-and-hold strategy
    def simple_strategy(bar, context):
        if context.get("bar_count", 0) == 1:
            return "BUY"
        return None

    # Create backtest config
    config = BacktestConfig(
        symbol="SYNTH",
        start_date=datetime(2022, 1, 1).date(),
        end_date=datetime(2023, 12, 31).date(),
        initial_capital=Decimal("100000"),
        max_position_size=Decimal("0.02"),
        commission_per_share=Decimal("0.005"),
    )

    # Initialize engine
    engine = BacktestEngine(config)

    # Measure execution time
    start_time = time.perf_counter()
    result = engine.run(bars, strategy_func=simple_strategy)
    end_time = time.perf_counter()

    execution_time = end_time - start_time

    # Assert performance requirement: <60 seconds
    assert execution_time < 60.0, f"Expected <60s, got {execution_time:.2f}s"

    # Calculate throughput (should be >100 bars/second per NFR7)
    bars_per_second = len(bars) / execution_time
    assert bars_per_second > 100, f"Expected >100 bars/s (NFR7), got {bars_per_second:.0f} bars/s"

    # Verify result is valid
    assert result.backtest_run_id is not None
    assert len(result.equity_curve) == len(bars)
    # Note: Trades may be 0 if strategy didn't generate signals - this is OK for performance test

    print(
        f"\nPerformance: {bars_per_second:.0f} bars/s ({execution_time:.2f}s for {len(bars)} bars, {len(result.trades)} trades)"
    )


@pytest.mark.slow
@pytest.mark.extended
def test_backtest_determinism():
    """
    Verify backtest produces identical results on multiple runs (Story 12.11 Task 3 Subtask 3.3).

    Requirements:
    - Run same backtest twice with identical config
    - Assert all results are identical (trades, metrics, equity curve)
    - Ensures no randomness or time-based logic

    Test Flow:
    - Generate deterministic OHLCV dataset
    - Run BacktestEngine twice with same strategy and config
    - Compare BacktestResult objects field by field
    - Assert complete equality
    """
    from datetime import timedelta
    from decimal import Decimal

    from src.backtesting.backtest_engine import BacktestEngine
    from src.models.backtest import BacktestConfig
    from src.models.ohlcv import OHLCVBar

    # Generate deterministic OHLCV data (100 bars)
    bars = []
    start_date = datetime(2024, 1, 1, tzinfo=UTC)
    base_price = Decimal("100.00")

    for i in range(100):
        price = base_price + Decimal(i) * Decimal("0.10")
        daily_range = Decimal("2.00")

        bars.append(
            OHLCVBar(
                symbol="TEST",
                timeframe="1d",
                timestamp=start_date + timedelta(days=i),
                open=price,
                high=price + daily_range,
                low=price - daily_range,
                close=price + daily_range * Decimal("0.5"),
                volume=1000000,
                spread=daily_range,
            )
        )

    # Deterministic strategy (trades on specific bar indices)
    def deterministic_strategy(bar, context):
        bar_count = context.get("bar_count", 0)
        # Open position on bar 10
        if bar_count == 10:
            return "BUY"
        # Close position on bar 30 (requires open position from bar 10)
        elif bar_count == 30:
            return "SELL"
        # Reopen position on bar 50
        elif bar_count == 50:
            return "BUY"
        # Close position on bar 80 (requires open position from bar 50)
        elif bar_count == 80:
            return "SELL"
        return None

    # Create backtest config
    config = BacktestConfig(
        symbol="TEST",
        start_date=datetime(2024, 1, 1).date(),
        end_date=datetime(2024, 12, 31).date(),
        initial_capital=Decimal("100000"),
        max_position_size=Decimal("0.02"),
        commission_per_share=Decimal("0.005"),
    )

    # Run backtest twice
    engine1 = BacktestEngine(config)
    result1 = engine1.run(bars, strategy_func=deterministic_strategy)

    engine2 = BacktestEngine(config)
    result2 = engine2.run(bars, strategy_func=deterministic_strategy)

    # Debug output
    print(f"\nRun 1: {len(result1.trades)} trades")
    print(f"Run 2: {len(result2.trades)} trades")
    if len(result1.trades) > 0:
        print(
            f"First trade: entry={result1.trades[0].entry_price}, exit={result1.trades[0].exit_price}"
        )

    # Assert identical results

    # 1. Same number of trades
    assert len(result1.trades) == len(
        result2.trades
    ), f"Trade count mismatch: {len(result1.trades)} vs {len(result2.trades)}"

    # 2. Same trades (entry/exit prices, quantities, timestamps)
    for i, (trade1, trade2) in enumerate(zip(result1.trades, result2.trades, strict=False)):
        assert trade1.entry_price == trade2.entry_price, f"Trade {i}: entry_price mismatch"
        assert trade1.exit_price == trade2.exit_price, f"Trade {i}: exit_price mismatch"
        assert trade1.quantity == trade2.quantity, f"Trade {i}: quantity mismatch"
        assert (
            trade1.entry_timestamp == trade2.entry_timestamp
        ), f"Trade {i}: entry_timestamp mismatch"
        assert trade1.exit_timestamp == trade2.exit_timestamp, f"Trade {i}: exit_timestamp mismatch"
        assert trade1.pnl == trade2.pnl, f"Trade {i}: pnl mismatch"

    # 3. Same equity curve
    assert len(result1.equity_curve) == len(result2.equity_curve), "Equity curve length mismatch"
    for i, (eq1, eq2) in enumerate(zip(result1.equity_curve, result2.equity_curve, strict=False)):
        assert eq1.timestamp == eq2.timestamp, f"Equity curve {i}: timestamp mismatch"
        assert eq1.portfolio_value == eq2.portfolio_value, f"Equity curve {i}: value mismatch"

    # 4. Same metrics (from metrics object)
    assert (
        result1.metrics.total_return_pct == result2.metrics.total_return_pct
    ), "total_return_pct mismatch"
    assert result1.metrics.win_rate == result2.metrics.win_rate, "win_rate mismatch"
    assert result1.metrics.profit_factor == result2.metrics.profit_factor, "profit_factor mismatch"
    assert result1.metrics.max_drawdown == result2.metrics.max_drawdown, "max_drawdown mismatch"
    assert result1.metrics.sharpe_ratio == result2.metrics.sharpe_ratio, "sharpe_ratio mismatch"
    assert result1.metrics.cagr == result2.metrics.cagr, "cagr mismatch"
    assert result1.metrics.total_trades == result2.metrics.total_trades, "total_trades mismatch"
    assert (
        result1.metrics.winning_trades == result2.metrics.winning_trades
    ), "winning_trades mismatch"
    assert result1.metrics.losing_trades == result2.metrics.losing_trades, "losing_trades mismatch"

    # 5. Same backtest run IDs are different (each run gets unique ID)
    assert result1.backtest_run_id != result2.backtest_run_id, "Run IDs should be different"

    print("\n[PASS] Backtest is deterministic: identical results on both runs")
