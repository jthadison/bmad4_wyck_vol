"""
Integration Tests for Backtest Report API Endpoints (Story 12.6B Task 22)

Purpose:
--------
End-to-end tests for HTML, PDF, and CSV report generation API endpoints.
Tests full request/response cycle including database retrieval and error cases.

Coverage Target: 90%+

Author: Story 12.6B Task 22
"""

import csv
from datetime import UTC, datetime
from decimal import Decimal
from io import StringIO
from uuid import UUID, uuid4

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from src.api.main import app
from src.models.backtest import (
    BacktestConfig,
    BacktestCostSummary,
    BacktestMetrics,
    BacktestResult,
    BacktestTrade,
    EquityCurvePoint,
)

# ==========================================================================================
# Fixtures
# ==========================================================================================


@pytest.fixture
def test_client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def sample_backtest_result_minimal():
    """Create minimal backtest result for testing."""
    config = BacktestConfig(
        symbol="AAPL",
        start_date=datetime(2024, 1, 1).date(),
        end_date=datetime(2024, 12, 31).date(),
        initial_capital=Decimal("100000"),
        position_size_pct=Decimal("10"),
        max_positions=3,
        risk_per_trade_pct=Decimal("2"),
    )

    # Create simple equity curve
    equity_curve = [
        EquityCurvePoint(
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            equity_value=Decimal("100000"),
            portfolio_value=Decimal("100000"),
            cash=Decimal("30000"),
            positions_value=Decimal("70000"),
        ),
        EquityCurvePoint(
            timestamp=datetime(2024, 6, 1, tzinfo=UTC),
            equity_value=Decimal("105000"),
            portfolio_value=Decimal("105000"),
            cash=Decimal("31500"),
            positions_value=Decimal("73500"),
        ),
        EquityCurvePoint(
            timestamp=datetime(2024, 12, 31, tzinfo=UTC),
            equity_value=Decimal("110000"),
            portfolio_value=Decimal("110000"),
            cash=Decimal("33000"),
            positions_value=Decimal("77000"),
        ),
    ]

    # Create sample trades
    trades = [
        BacktestTrade(
            trade_id=uuid4(),
            position_id=uuid4(),
            symbol="AAPL",
            entry_timestamp=datetime(2024, 3, 1, tzinfo=UTC),
            exit_timestamp=datetime(2024, 3, 15, tzinfo=UTC),
            entry_price=Decimal("150.00"),
            exit_price=Decimal("157.50"),
            quantity=100,
            side="LONG",
            realized_pnl=Decimal("735.00"),  # 750 - 10 - 5
            commission=Decimal("10.00"),
            slippage=Decimal("5.00"),
            gross_pnl=Decimal("750.00"),
            pattern_type="SPRING",
            r_multiple=Decimal("2.5"),
        ),
    ]

    # Simple metrics
    metrics = BacktestMetrics(
        total_trades=1,
        winning_trades=1,
        losing_trades=0,
        win_rate=Decimal("1.0"),
        total_pnl=Decimal("750.00"),  # 0.75% of 100000
        total_return_pct=Decimal("0.0075"),  # 0.75% as decimal
        final_equity=Decimal("100750.00"),
        max_drawdown=Decimal("0"),
        sharpe_ratio=Decimal("2.0"),
        cagr=Decimal("0.05"),  # 5% as decimal
        avg_r_multiple=Decimal("2.5"),
        profit_factor=Decimal("999"),
    )

    # Cost summary
    cost_summary = BacktestCostSummary(
        total_commission_paid=Decimal("10.00"),
        total_slippage_cost=Decimal("5.00"),
        total_transaction_costs=Decimal("15.00"),
        cost_as_pct_of_total_pnl=Decimal("0.02"),  # 2% as decimal
        avg_commission_per_trade=Decimal("10.00"),
        avg_slippage_per_trade=Decimal("5.00"),
    )

    return BacktestResult(
        backtest_run_id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        start_date=config.start_date,
        end_date=config.end_date,
        config=config,
        equity_curve=equity_curve,
        trades=trades,
        metrics=metrics,
        cost_summary=cost_summary,
        look_ahead_bias_check=True,
        execution_time_seconds=12.5,
    )


# ==========================================================================================
# Test GET /api/v1/backtest/results/{backtest_run_id}/report/html (Task 22.3)
# ==========================================================================================


@pytest.mark.asyncio
async def test_get_html_report_success(test_client, sample_backtest_result_minimal, monkeypatch):
    """Test successful HTML report generation via API."""

    # Mock repository to return our sample result
    class MockRepository:
        async def get_result(self, backtest_run_id: UUID):
            if backtest_run_id == sample_backtest_result_minimal.backtest_run_id:
                return sample_backtest_result_minimal
            return None

    def mock_get_repository(*args, **kwargs):
        return MockRepository()

    monkeypatch.setattr(
        "src.api.routes.backtest.BacktestRepository", lambda session: MockRepository()
    )

    # Make request
    backtest_id = str(sample_backtest_result_minimal.backtest_run_id)
    response = test_client.get(f"/api/v1/backtest/results/{backtest_id}/report/html")

    # Verify response
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"

    html = response.text
    assert html
    assert len(html) > 500

    # Parse HTML
    soup = BeautifulSoup(html, "html.parser")
    assert soup.find("html")
    assert "AAPL" in html
    assert "2024-01-01" in html


@pytest.mark.asyncio
async def test_get_html_report_not_found(test_client, monkeypatch):
    """Test HTML report for non-existent backtest."""

    # Mock repository to return None
    class MockRepository:
        async def get_result(self, backtest_run_id: UUID):
            return None

    monkeypatch.setattr(
        "src.api.routes.backtest.BacktestRepository", lambda session: MockRepository()
    )

    # Make request with random UUID
    random_id = str(uuid4())
    response = test_client.get(f"/api/v1/backtest/results/{random_id}/report/html")

    # Verify 404 error
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_html_report_generation_error(
    test_client, sample_backtest_result_minimal, monkeypatch
):
    """Test HTML report generation error handling."""

    # Mock repository to return result
    class MockRepository:
        async def get_result(self, backtest_run_id: UUID):
            return sample_backtest_result_minimal

    monkeypatch.setattr(
        "src.api.routes.backtest.BacktestRepository", lambda session: MockRepository()
    )

    # Mock report generator to raise exception
    class MockGenerator:
        def generate_html_report(self, result):
            raise ValueError("Template rendering failed")

    monkeypatch.setattr("src.api.routes.backtest.BacktestReportGenerator", lambda: MockGenerator())

    # Make request
    backtest_id = str(sample_backtest_result_minimal.backtest_run_id)
    response = test_client.get(f"/api/v1/backtest/results/{backtest_id}/report/html")

    # Verify 500 error
    assert response.status_code == 500
    assert "Failed to generate HTML report" in response.json()["detail"]


# ==========================================================================================
# Test GET /api/v1/backtest/results/{backtest_run_id}/report/pdf (Task 22.4)
# ==========================================================================================


@pytest.mark.asyncio
async def test_get_pdf_report_success(test_client, sample_backtest_result_minimal, monkeypatch):
    """Test successful PDF report generation via API."""
    pytest.importorskip("weasyprint", reason="WeasyPrint not installed")

    # Mock repository
    class MockRepository:
        async def get_result(self, backtest_run_id: UUID):
            if backtest_run_id == sample_backtest_result_minimal.backtest_run_id:
                return sample_backtest_result_minimal
            return None

    monkeypatch.setattr(
        "src.api.routes.backtest.BacktestRepository", lambda session: MockRepository()
    )

    # Make request
    backtest_id = str(sample_backtest_result_minimal.backtest_run_id)
    response = test_client.get(f"/api/v1/backtest/results/{backtest_id}/report/pdf")

    # Verify response
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert f"backtest_{backtest_id}.pdf" in response.headers["content-disposition"]

    # Verify PDF content
    pdf_bytes = response.content
    assert pdf_bytes
    assert len(pdf_bytes) > 100
    assert pdf_bytes[:4] == b"%PDF"  # PDF magic number


@pytest.mark.asyncio
async def test_get_pdf_report_not_found(test_client, monkeypatch):
    """Test PDF report for non-existent backtest."""

    # Mock repository to return None
    class MockRepository:
        async def get_result(self, backtest_run_id: UUID):
            return None

    monkeypatch.setattr(
        "src.api.routes.backtest.BacktestRepository", lambda session: MockRepository()
    )

    # Make request
    random_id = str(uuid4())
    response = test_client.get(f"/api/v1/backtest/results/{random_id}/report/pdf")

    # Verify 404 error
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_pdf_report_weasyprint_missing(
    test_client, sample_backtest_result_minimal, monkeypatch
):
    """Test PDF generation when WeasyPrint is not installed."""

    # Mock repository
    class MockRepository:
        async def get_result(self, backtest_run_id: UUID):
            return sample_backtest_result_minimal

    monkeypatch.setattr(
        "src.api.routes.backtest.BacktestRepository", lambda session: MockRepository()
    )

    # Mock report generator to raise ImportError
    class MockGenerator:
        def generate_pdf_report(self, result):
            raise ImportError("WeasyPrint is required")

    monkeypatch.setattr("src.api.routes.backtest.BacktestReportGenerator", lambda: MockGenerator())

    # Make request
    backtest_id = str(sample_backtest_result_minimal.backtest_run_id)
    response = test_client.get(f"/api/v1/backtest/results/{backtest_id}/report/pdf")

    # Verify 500 error with WeasyPrint message
    assert response.status_code == 500
    assert "WeasyPrint" in response.json()["detail"]


# ==========================================================================================
# Test GET /api/v1/backtest/results/{backtest_run_id}/trades/csv (Task 22.5)
# ==========================================================================================


@pytest.mark.asyncio
async def test_get_trades_csv_success(test_client, sample_backtest_result_minimal, monkeypatch):
    """Test successful CSV trade list export via API."""

    # Mock repository
    class MockRepository:
        async def get_result(self, backtest_run_id: UUID):
            if backtest_run_id == sample_backtest_result_minimal.backtest_run_id:
                return sample_backtest_result_minimal
            return None

    monkeypatch.setattr(
        "src.api.routes.backtest.BacktestRepository", lambda session: MockRepository()
    )

    # Make request
    backtest_id = str(sample_backtest_result_minimal.backtest_run_id)
    response = test_client.get(f"/api/v1/backtest/results/{backtest_id}/trades/csv")

    # Verify response
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment" in response.headers["content-disposition"]
    assert f"backtest_{backtest_id}_trades.csv" in response.headers["content-disposition"]

    # Parse CSV
    csv_content = response.text
    assert csv_content

    reader = csv.DictReader(StringIO(csv_content))
    rows = list(reader)

    # Verify trade count
    assert len(rows) == len(sample_backtest_result_minimal.trades)

    # Verify columns exist
    expected_columns = [
        "trade_id",
        "symbol",
        "pattern_type",
        "entry_price",
        "exit_price",
        "realized_pnl",
        "commission",
        "slippage",
        "net_pnl",
        "r_multiple",
    ]

    for col in expected_columns:
        assert col in reader.fieldnames

    # Verify first row data
    first_row = rows[0]
    assert first_row["symbol"] == "AAPL"
    assert first_row["pattern_type"] == "SPRING"


@pytest.mark.asyncio
async def test_get_trades_csv_not_found(test_client, monkeypatch):
    """Test CSV export for non-existent backtest."""

    # Mock repository to return None
    class MockRepository:
        async def get_result(self, backtest_run_id: UUID):
            return None

    monkeypatch.setattr(
        "src.api.routes.backtest.BacktestRepository", lambda session: MockRepository()
    )

    # Make request
    random_id = str(uuid4())
    response = test_client.get(f"/api/v1/backtest/results/{random_id}/trades/csv")

    # Verify 404 error
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_trades_csv_empty_trades(test_client, monkeypatch):
    """Test CSV export with no trades."""

    # Create result with no trades
    config = BacktestConfig(
        symbol="AAPL",
        start_date=datetime(2024, 1, 1).date(),
        end_date=datetime(2024, 12, 31).date(),
        initial_capital=Decimal("100000"),
        position_size_pct=Decimal("10"),
        max_positions=3,
        risk_per_trade_pct=Decimal("2"),
    )

    metrics = BacktestMetrics(
        total_trades=0,
        winning_trades=0,
        losing_trades=0,
        win_rate=Decimal("0"),
        total_pnl=Decimal("0"),
        total_return_pct=Decimal("0"),
        final_equity=Decimal("100000"),
        max_drawdown=Decimal("0"),
        sharpe_ratio=Decimal("0"),
        cagr=Decimal("0"),
        avg_r_multiple=Decimal("0"),
        profit_factor=Decimal("0"),
    )

    empty_result = BacktestResult(
        backtest_run_id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        start_date=config.start_date,
        end_date=config.end_date,
        config=config,
        equity_curve=[],
        trades=[],  # No trades
        metrics=metrics,
        cost_summary=None,
        look_ahead_bias_check=False,
        execution_time_seconds=5.0,
    )

    # Mock repository
    class MockRepository:
        async def get_result(self, backtest_run_id: UUID):
            return empty_result

    monkeypatch.setattr(
        "src.api.routes.backtest.BacktestRepository", lambda session: MockRepository()
    )

    # Make request
    backtest_id = str(empty_result.backtest_run_id)
    response = test_client.get(f"/api/v1/backtest/results/{backtest_id}/trades/csv")

    # Should still return 200 with headers only
    assert response.status_code == 200

    csv_content = response.text
    reader = csv.DictReader(StringIO(csv_content))
    rows = list(reader)

    assert len(rows) == 0  # No data rows
    assert reader.fieldnames  # But headers exist


# ==========================================================================================
# Test Error Handling (Task 22.6)
# ==========================================================================================


@pytest.mark.asyncio
async def test_invalid_uuid_format(test_client):
    """Test API with invalid UUID format."""
    response = test_client.get("/api/v1/backtest/results/invalid-uuid/report/html")

    # Should return 422 validation error
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_concurrent_report_requests(test_client, sample_backtest_result_minimal, monkeypatch):
    """Test handling of concurrent report requests."""

    # Mock repository
    class MockRepository:
        async def get_result(self, backtest_run_id: UUID):
            return sample_backtest_result_minimal

    monkeypatch.setattr(
        "src.api.routes.backtest.BacktestRepository", lambda session: MockRepository()
    )

    backtest_id = str(sample_backtest_result_minimal.backtest_run_id)

    # Make multiple concurrent requests
    responses = [
        test_client.get(f"/api/v1/backtest/results/{backtest_id}/report/html") for _ in range(3)
    ]

    # All should succeed
    for response in responses:
        assert response.status_code == 200
