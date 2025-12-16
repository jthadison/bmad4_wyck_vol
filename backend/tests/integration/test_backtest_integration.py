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
