"""
Unit tests for Regression Testing API endpoints (Story 12.7 Task 11).

Tests all 6 regression testing endpoints:
- POST /api/v1/backtest/regression
- GET /api/v1/backtest/regression/{test_id}
- GET /api/v1/backtest/regression
- POST /api/v1/backtest/regression/{test_id}/establish-baseline
- GET /api/v1/backtest/regression/baseline/current
- GET /api/v1/backtest/regression/baseline/history

Author: Story 12.7 Task 11 Subtask 11.17
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.api.main import app
from src.models.backtest import (
    BacktestConfig,
    BacktestMetrics,
    RegressionBaseline,
    RegressionTestConfig,
    RegressionTestResult,
)

client = TestClient(app)


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def sample_backtest_config():
    """Sample BacktestConfig for testing."""
    from src.models.backtest import CommissionConfig, SlippageConfig

    return BacktestConfig(
        initial_capital=Decimal("100000.00"),
        position_size_pct=Decimal("0.10"),
        max_positions=5,
        commission_config=CommissionConfig(
            commission_type="per_share",
            commission_rate=Decimal("0.0050"),
        ),
        slippage_config=SlippageConfig(
            slippage_type="percentage",
            slippage_rate=Decimal("0.0010"),
        ),
    )


@pytest.fixture
def sample_regression_config(sample_backtest_config):
    """Sample RegressionTestConfig for testing."""
    return RegressionTestConfig(
        symbols=["AAPL", "MSFT", "GOOGL"],
        start_date=date(2020, 1, 1),
        end_date=date(2023, 12, 31),
        backtest_config=sample_backtest_config,
        degradation_thresholds={
            "win_rate": Decimal("5.0"),
            "average_r_multiple": Decimal("10.0"),
            "profit_factor": Decimal("15.0"),
        },
    )


@pytest.fixture
def sample_regression_result():
    """Sample RegressionTestResult for testing."""
    test_id = uuid4()
    return RegressionTestResult(
        test_id=test_id,
        codebase_version="abc123",
        config={
            "symbols": ["AAPL", "MSFT", "GOOGL"],
            "start_date": "2020-01-01",
            "end_date": "2023-12-31",
        },
        aggregate_metrics=BacktestMetrics(
            total_signals=100,
            total_trades=100,
            winning_trades=65,
            losing_trades=35,
            win_rate=Decimal("0.6500"),
            average_r_multiple=Decimal("1.8000"),
            profit_factor=Decimal("2.5000"),
            max_drawdown=Decimal("0.1500"),
            sharpe_ratio=Decimal("1.5000"),
        ),
        per_symbol_results={
            "AAPL": {
                "total_trades": 35,
                "win_rate": Decimal("0.6571"),
                "average_r_multiple": Decimal("1.7500"),
            },
            "MSFT": {
                "total_trades": 33,
                "win_rate": Decimal("0.6364"),
                "average_r_multiple": Decimal("1.9000"),
            },
            "GOOGL": {
                "total_trades": 32,
                "win_rate": Decimal("0.6563"),
                "average_r_multiple": Decimal("1.7500"),
            },
        },
        baseline_comparison=None,
        regression_detected=False,
        degraded_metrics=[],
        status="PASS",
        execution_time_seconds=45.5,
        test_run_time=datetime(2024, 1, 15, 2, 0, 0, tzinfo=UTC),
    )


@pytest.fixture
def sample_regression_baseline():
    """Sample RegressionBaseline for testing."""
    baseline_id = uuid4()
    test_id = uuid4()
    return RegressionBaseline(
        baseline_id=baseline_id,
        test_id=test_id,
        version="abc123",
        metrics=BacktestMetrics(
            total_signals=100,
            total_trades=100,
            winning_trades=65,
            losing_trades=35,
            win_rate=Decimal("0.6500"),
            average_r_multiple=Decimal("1.8000"),
            profit_factor=Decimal("2.5000"),
            max_drawdown=Decimal("0.1500"),
            sharpe_ratio=Decimal("1.5000"),
        ),
        per_symbol_metrics={
            "AAPL": {
                "total_trades": 35,
                "win_rate": Decimal("0.6571"),
                "average_r_multiple": Decimal("1.7500"),
            },
            "MSFT": {
                "total_trades": 33,
                "win_rate": Decimal("0.6364"),
                "average_r_multiple": Decimal("1.9000"),
            },
            "GOOGL": {
                "total_trades": 32,
                "win_rate": Decimal("0.6563"),
                "average_r_multiple": Decimal("1.7500"),
            },
        },
        established_at=datetime(2024, 1, 15, 2, 0, 0, tzinfo=UTC),
        is_current=True,
    )


# ==============================================================================
# POST /api/v1/backtest/regression - Run Regression Test
# ==============================================================================


class TestRunRegressionTest:
    """Test POST /api/v1/backtest/regression endpoint."""

    def test_run_regression_test_success(self, sample_regression_config):
        """Test successful regression test submission."""
        with patch("src.api.routes.backtest.RegressionTestEngine") as mock_engine:
            response = client.post(
                "/api/v1/backtest/regression",
                json=sample_regression_config.model_dump(mode="json"),
            )

            assert response.status_code == status.HTTP_202_ACCEPTED
            data = response.json()
            assert "test_id" in data
            assert data["status"] == "RUNNING"

    def test_run_regression_test_empty_symbols(self):
        """Test rejection of config with empty symbols."""
        config = {
            "symbols": [],
            "start_date": "2020-01-01",
            "end_date": "2023-12-31",
        }
        response = client.post("/api/v1/backtest/regression", json=config)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "at least one symbol" in response.json()["detail"]

    def test_run_regression_test_invalid_date_range(self):
        """Test rejection of invalid date range."""
        config = {
            "symbols": ["AAPL"],
            "start_date": "2023-12-31",
            "end_date": "2020-01-01",
        }
        response = client.post("/api/v1/backtest/regression", json=config)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "start_date must be before end_date" in response.json()["detail"]

    def test_run_regression_test_concurrent_limit(self, sample_regression_config):
        """Test concurrent test limit enforcement."""
        from src.api.routes.backtest import regression_test_runs

        # Fill up with 3 running tests
        for i in range(3):
            regression_test_runs[uuid4()] = {
                "status": "RUNNING",
                "created_at": datetime.now(UTC),
            }

        try:
            response = client.post(
                "/api/v1/backtest/regression",
                json=sample_regression_config.model_dump(mode="json"),
            )

            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert "Too many concurrent" in response.json()["detail"]
        finally:
            # Clean up
            regression_test_runs.clear()


# ==============================================================================
# GET /api/v1/backtest/regression/{test_id} - Get Test Result
# ==============================================================================


class TestGetRegressionTestResult:
    """Test GET /api/v1/backtest/regression/{test_id} endpoint."""

    def test_get_result_running(self):
        """Test getting status of running test."""
        from src.api.routes.backtest import regression_test_runs

        test_id = uuid4()
        regression_test_runs[test_id] = {
            "status": "RUNNING",
            "created_at": datetime.now(UTC),
        }

        try:
            response = client.get(f"/api/v1/backtest/regression/{test_id}")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "RUNNING"
        finally:
            regression_test_runs.clear()

    def test_get_result_failed(self):
        """Test getting status of failed test."""
        from src.api.routes.backtest import regression_test_runs

        test_id = uuid4()
        regression_test_runs[test_id] = {
            "status": "FAILED",
            "error": "Database connection failed",
            "created_at": datetime.now(UTC),
        }

        try:
            response = client.get(f"/api/v1/backtest/regression/{test_id}")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "FAILED"
            assert data["error"] == "Database connection failed"
        finally:
            regression_test_runs.clear()

    def test_get_result_completed(self, sample_regression_result):
        """Test getting completed test result from database."""
        test_id = sample_regression_result.test_id

        with patch("src.api.routes.backtest.RegressionTestRepository") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.get_result = AsyncMock(return_value=sample_regression_result)
            mock_repo_class.return_value = mock_repo

            response = client.get(f"/api/v1/backtest/regression/{test_id}")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["test_id"] == str(test_id)
            assert data["status"] == "PASS"
            assert data["regression_detected"] is False

    def test_get_result_not_found(self):
        """Test 404 for non-existent test."""
        test_id = uuid4()

        with patch("src.api.routes.backtest.RegressionTestRepository") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.get_result = AsyncMock(return_value=None)
            mock_repo_class.return_value = mock_repo

            response = client.get(f"/api/v1/backtest/regression/{test_id}")

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"]


# ==============================================================================
# GET /api/v1/backtest/regression - List Test Results
# ==============================================================================


class TestListRegressionTestResults:
    """Test GET /api/v1/backtest/regression endpoint."""

    def test_list_results_default_pagination(self, sample_regression_result):
        """Test listing results with default pagination."""
        with patch("src.api.routes.backtest.RegressionTestRepository") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.list_results = AsyncMock(return_value=[sample_regression_result])
            mock_repo_class.return_value = mock_repo

            response = client.get("/api/v1/backtest/regression")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 1
            assert data[0]["test_id"] == str(sample_regression_result.test_id)

    def test_list_results_custom_pagination(self):
        """Test custom limit and offset."""
        with patch("src.api.routes.backtest.RegressionTestRepository") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.list_results = AsyncMock(return_value=[])
            mock_repo_class.return_value = mock_repo

            response = client.get("/api/v1/backtest/regression?limit=20&offset=10")

            assert response.status_code == status.HTTP_200_OK
            # Verify repository was called with correct params
            mock_repo.list_results.assert_called_once()
            call_kwargs = mock_repo.list_results.call_args.kwargs
            assert call_kwargs["limit"] == 20
            assert call_kwargs["offset"] == 10

    def test_list_results_status_filter(self):
        """Test filtering by status."""
        with patch("src.api.routes.backtest.RegressionTestRepository") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.list_results = AsyncMock(return_value=[])
            mock_repo_class.return_value = mock_repo

            response = client.get("/api/v1/backtest/regression?status_filter=FAIL")

            assert response.status_code == status.HTTP_200_OK
            # Verify filter was passed
            call_kwargs = mock_repo.list_results.call_args.kwargs
            assert call_kwargs["status_filter"] == "FAIL"

    def test_list_results_invalid_status_filter(self):
        """Test rejection of invalid status filter."""
        response = client.get("/api/v1/backtest/regression?status_filter=INVALID")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "status_filter must be one of" in response.json()["detail"]

    def test_list_results_max_limit_enforcement(self):
        """Test that limit > 100 is capped at 100."""
        with patch("src.api.routes.backtest.RegressionTestRepository") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.list_results = AsyncMock(return_value=[])
            mock_repo_class.return_value = mock_repo

            response = client.get("/api/v1/backtest/regression?limit=200")

            assert response.status_code == status.HTTP_200_OK
            # Verify limit was capped
            call_kwargs = mock_repo.list_results.call_args.kwargs
            assert call_kwargs["limit"] == 100


# ==============================================================================
# POST /api/v1/backtest/regression/{test_id}/establish-baseline
# ==============================================================================


class TestEstablishBaselineFromTest:
    """Test POST /api/v1/backtest/regression/{test_id}/establish-baseline endpoint."""

    def test_establish_baseline_success(self, sample_regression_result, sample_regression_baseline):
        """Test successful baseline establishment."""
        test_id = sample_regression_result.test_id

        with patch(
            "src.api.routes.backtest.RegressionTestRepository"
        ) as mock_test_repo_class, patch(
            "src.api.routes.backtest.RegressionBaselineRepository"
        ) as mock_baseline_repo_class, patch(
            "src.api.routes.backtest.RegressionTestEngine"
        ) as mock_engine_class:
            # Mock test repository
            mock_test_repo = MagicMock()
            mock_test_repo.get_result = AsyncMock(return_value=sample_regression_result)
            mock_test_repo_class.return_value = mock_test_repo

            # Mock baseline repository
            mock_baseline_repo = MagicMock()
            mock_baseline_repo_class.return_value = mock_baseline_repo

            # Mock engine
            mock_engine = MagicMock()
            mock_engine.establish_baseline = AsyncMock(return_value=sample_regression_baseline)
            mock_engine_class.return_value = mock_engine

            response = client.post(f"/api/v1/backtest/regression/{test_id}/establish-baseline")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["baseline_id"] == str(sample_regression_baseline.baseline_id)
            assert data["is_current"] is True

    def test_establish_baseline_test_not_found(self):
        """Test 404 when test doesn't exist."""
        test_id = uuid4()

        with patch("src.api.routes.backtest.RegressionTestRepository") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.get_result = AsyncMock(return_value=None)
            mock_repo_class.return_value = mock_repo

            response = client.post(f"/api/v1/backtest/regression/{test_id}/establish-baseline")

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"]

    def test_establish_baseline_test_not_pass(self, sample_regression_result):
        """Test rejection when test status is not PASS."""
        test_id = sample_regression_result.test_id
        # Modify result to have FAIL status
        failed_result = sample_regression_result.model_copy(update={"status": "FAIL"})

        with patch("src.api.routes.backtest.RegressionTestRepository") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.get_result = AsyncMock(return_value=failed_result)
            mock_repo_class.return_value = mock_repo

            response = client.post(f"/api/v1/backtest/regression/{test_id}/establish-baseline")

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Only PASS tests can be used" in response.json()["detail"]


# ==============================================================================
# GET /api/v1/backtest/regression/baseline/current
# ==============================================================================


class TestGetCurrentBaseline:
    """Test GET /api/v1/backtest/regression/baseline/current endpoint."""

    def test_get_current_baseline_success(self, sample_regression_baseline):
        """Test getting current baseline."""
        with patch("src.api.routes.backtest.RegressionBaselineRepository") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.get_current_baseline = AsyncMock(return_value=sample_regression_baseline)
            mock_repo_class.return_value = mock_repo

            response = client.get("/api/v1/backtest/regression/baseline/current")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["baseline_id"] == str(sample_regression_baseline.baseline_id)
            assert data["is_current"] is True

    def test_get_current_baseline_not_set(self):
        """Test 404 when no baseline is set."""
        with patch("src.api.routes.backtest.RegressionBaselineRepository") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.get_current_baseline = AsyncMock(return_value=None)
            mock_repo_class.return_value = mock_repo

            response = client.get("/api/v1/backtest/regression/baseline/current")

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "No current baseline set" in response.json()["detail"]


# ==============================================================================
# GET /api/v1/backtest/regression/baseline/history
# ==============================================================================


class TestListBaselineHistory:
    """Test GET /api/v1/backtest/regression/baseline/history endpoint."""

    def test_list_baseline_history_default_pagination(self, sample_regression_baseline):
        """Test listing baselines with default pagination."""
        with patch("src.api.routes.backtest.RegressionBaselineRepository") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.list_baselines = AsyncMock(return_value=[sample_regression_baseline])
            mock_repo_class.return_value = mock_repo

            response = client.get("/api/v1/backtest/regression/baseline/history")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 1
            assert data[0]["baseline_id"] == str(sample_regression_baseline.baseline_id)

    def test_list_baseline_history_custom_pagination(self):
        """Test custom limit and offset."""
        with patch("src.api.routes.backtest.RegressionBaselineRepository") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.list_baselines = AsyncMock(return_value=[])
            mock_repo_class.return_value = mock_repo

            response = client.get("/api/v1/backtest/regression/baseline/history?limit=20&offset=5")

            assert response.status_code == status.HTTP_200_OK
            # Verify repository was called with correct params
            mock_repo.list_baselines.assert_called_once()
            call_kwargs = mock_repo.list_baselines.call_args.kwargs
            assert call_kwargs["limit"] == 20
            assert call_kwargs["offset"] == 5

    def test_list_baseline_history_max_limit_enforcement(self):
        """Test that limit > 50 is capped at 50."""
        with patch("src.api.routes.backtest.RegressionBaselineRepository") as mock_repo_class:
            mock_repo = MagicMock()
            mock_repo.list_baselines = AsyncMock(return_value=[])
            mock_repo_class.return_value = mock_repo

            response = client.get("/api/v1/backtest/regression/baseline/history?limit=100")

            assert response.status_code == status.HTTP_200_OK
            # Verify limit was capped
            call_kwargs = mock_repo.list_baselines.call_args.kwargs
            assert call_kwargs["limit"] == 50
