"""
Unit Tests for Backtest Report Generator (Story 12.6B Task 21)

Purpose:
--------
Tests all report generation methods including HTML, PDF, and CSV exports.
Validates report structure, data integrity, and error handling.

Coverage Target: 90%+

Author: Story 12.6B Task 21
"""

import csv
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import StringIO
from uuid import uuid4

import pytest
from bs4 import BeautifulSoup

from src.backtesting.backtest_report_generator import BacktestReportGenerator
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
def sample_backtest_config():
    """Create sample backtest configuration."""
    return BacktestConfig(
        symbol="AAPL",
        start_date=datetime(2024, 1, 1).date(),
        end_date=datetime(2024, 12, 31).date(),
        initial_capital=Decimal("100000"),
        position_size_pct=Decimal("10"),
        max_positions=3,
        risk_per_trade_pct=Decimal("2"),
    )


@pytest.fixture
def sample_equity_curve():
    """Create sample equity curve with 10 data points."""
    equity_curve = []
    base_equity = Decimal("100000")

    for i in range(10):
        # Simulate growth with some volatility
        growth_factor = Decimal(str(1 + (i * 0.01)))  # 1% growth per point
        volatility = Decimal(str((-1) ** i * 0.005))  # +/- 0.5% volatility

        equity_value = base_equity * (growth_factor + volatility)
        cash = equity_value * Decimal("0.3")  # 30% cash
        positions_value = equity_value * Decimal("0.7")  # 70% in positions

        point = EquityCurvePoint(
            timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i * 10),
            equity_value=equity_value,
            portfolio_value=equity_value,
            cash=cash,
            positions_value=positions_value,
        )
        equity_curve.append(point)

    return equity_curve


@pytest.fixture
def sample_trades():
    """Create sample trades (mix of winners and losers)."""
    trades = []
    base_date = datetime(2024, 1, 1, tzinfo=UTC)

    # Create 5 winning trades and 3 losing trades
    for i in range(8):
        is_winner = i < 5  # First 5 are winners

        entry_price = Decimal("150.00")
        exit_price = Decimal("157.50") if is_winner else Decimal("145.00")
        quantity = 100  # int type

        realized_pnl = (exit_price - entry_price) * quantity
        commission = Decimal("10.00")
        slippage = Decimal("5.00")
        gross_pnl = (exit_price - entry_price) * quantity

        trade = BacktestTrade(
            trade_id=uuid4(),
            position_id=uuid4(),
            symbol="AAPL",
            entry_timestamp=base_date + timedelta(days=i * 10),
            exit_timestamp=base_date + timedelta(days=i * 10 + 5),
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            side="LONG",
            realized_pnl=realized_pnl - commission - slippage,
            commission=commission,
            slippage=slippage,
            gross_pnl=gross_pnl,
            pattern_type="SPRING" if is_winner else "UTAD",
            r_multiple=Decimal("2.5") if is_winner else Decimal("-1.0"),
        )
        trades.append(trade)

    return trades


@pytest.fixture
def sample_cost_summary():
    """Create sample transaction cost summary."""
    return BacktestCostSummary(
        total_trades=8,  # 8 trades total
        total_commission_paid=Decimal("80.00"),  # 8 trades * $10
        total_slippage_cost=Decimal("40.00"),  # 8 trades * $5
        total_transaction_costs=Decimal("120.00"),  # commission + slippage
        cost_as_pct_of_total_pnl=Decimal("0.055"),  # 5.5% as decimal
        avg_commission_per_trade=Decimal("10.00"),
        avg_slippage_per_trade=Decimal("5.00"),
        avg_transaction_cost_per_trade=Decimal("15.00"),  # $10 + $5
        gross_avg_r_multiple=Decimal("1.50"),  # Before costs
        net_avg_r_multiple=Decimal("1.25"),  # After costs
        r_multiple_degradation=Decimal("0.25"),  # gross - net
    )


@pytest.fixture
def sample_backtest_result(
    sample_backtest_config,
    sample_equity_curve,
    sample_trades,
    sample_cost_summary,
):
    """Create complete backtest result with all data."""
    # Calculate metrics from trades
    total_trades = len(sample_trades)
    winning_trades = sum(1 for t in sample_trades if t.realized_pnl > 0)
    losing_trades = total_trades - winning_trades

    total_pnl = sum(t.realized_pnl for t in sample_trades)
    final_equity = Decimal("100000") + total_pnl

    metrics = BacktestMetrics(
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate=Decimal(str(winning_trades / total_trades)),
        total_pnl=total_pnl,
        total_return_pct=(total_pnl / Decimal("100000")),
        final_equity=final_equity,
        max_drawdown=Decimal("0.085"),  # 8.5% drawdown (positive magnitude)
        sharpe_ratio=Decimal("1.85"),
        cagr=Decimal("0.125"),  # 12.5% as decimal
        avg_r_multiple=Decimal("1.25"),
        profit_factor=Decimal("2.10"),
    )

    return BacktestResult(
        backtest_run_id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        start_date=sample_backtest_config.start_date,
        end_date=sample_backtest_config.end_date,
        config=sample_backtest_config,
        equity_curve=sample_equity_curve,
        trades=sample_trades,
        summary=metrics,
        cost_summary=sample_cost_summary,
        look_ahead_bias_check=True,
        execution_time_seconds=45.2,
        created_at=datetime.now(UTC),
    )


# ==========================================================================================
# Test HTML Report Generation (Task 21.2)
# ==========================================================================================


def test_generate_html_report(sample_backtest_result):
    """Test HTML report generation with all sections."""
    generator = BacktestReportGenerator()
    html = generator.generate_html_report(sample_backtest_result)

    # Verify HTML is not empty
    assert html
    assert len(html) > 1000  # Should be substantial

    # Parse HTML for validation
    soup = BeautifulSoup(html, "html.parser")

    # Verify document structure
    assert soup.find("html")
    assert soup.find("head")
    assert soup.find("body")
    assert soup.find("title")

    # Verify title contains symbol and dates
    title = soup.find("title").text
    assert "AAPL" in title
    assert "2024-01-01" in title
    assert "2024-12-31" in title

    # Verify header section exists
    header_info = soup.find("div", class_="header-info")
    assert header_info
    assert "AAPL" in header_info.text
    assert "$100,000" in header_info.text

    # Verify summary metrics section
    metrics_grid = soup.find("div", class_="metrics-grid")
    assert metrics_grid
    metric_cards = soup.find_all("div", class_="metric-card")
    assert len(metric_cards) >= 8  # At least 8 key metrics

    # Verify equity curve chart canvas exists
    canvas = soup.find("canvas", id="equityCurveChart")
    assert canvas

    # Verify Chart.js script is included
    scripts = soup.find_all("script")
    chart_js_loaded = any("chart.js" in str(script) for script in scripts)
    assert chart_js_loaded

    # Verify Chart.js initialization script exists
    chart_init_script = any("equityCurveChart" in str(script) for script in scripts)
    assert chart_init_script

    # Verify trade list table exists
    tables = soup.find_all("table")
    assert len(tables) >= 1  # At least trade list table

    trade_table = None
    for table in tables:
        if "Entry Date" in table.text:
            trade_table = table
            break
    assert trade_table

    # Verify trade rows exist (8 trades)
    trade_rows = trade_table.find("tbody").find_all("tr")
    assert len(trade_rows) == 8

    # Verify transaction cost section (Story 12.5)
    cost_section = soup.find(string=lambda text: text and "Transaction Cost" in text)
    assert cost_section

    # Verify footer exists
    footer = soup.find("div", class_="footer")
    assert footer
    assert "45.2" in footer.text  # Execution time
    assert "PASSED" in footer.text  # Look-ahead bias check


def test_html_report_no_trades():
    """Test HTML report generation with no trades (edge case)."""
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

    result = BacktestResult(
        backtest_run_id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        start_date=config.start_date,
        end_date=config.end_date,
        config=config,
        equity_curve=[],
        trades=[],
        summary=metrics,
        cost_summary=None,
        look_ahead_bias_check=False,
        execution_time_seconds=10.0,
    )

    generator = BacktestReportGenerator()
    html = generator.generate_html_report(result)

    # Should still generate valid HTML
    assert html
    soup = BeautifulSoup(html, "html.parser")
    assert soup.find("html")

    # Verify "0 trades" appears
    assert "0 trades" in html.lower()


def test_html_report_no_cost_summary():
    """Test HTML report without transaction cost summary."""
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
        total_trades=1,
        winning_trades=1,
        losing_trades=0,
        win_rate=Decimal("1.0"),
        total_pnl=Decimal("500"),
        total_return_pct=Decimal("0.5"),
        final_equity=Decimal("100500"),
        max_drawdown=Decimal("0"),
        sharpe_ratio=Decimal("2.0"),
        cagr=Decimal("5.0"),
        avg_r_multiple=Decimal("2.0"),
        profit_factor=Decimal("999"),
    )

    result = BacktestResult(
        backtest_run_id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        start_date=config.start_date,
        end_date=config.end_date,
        config=config,
        equity_curve=[],
        trades=[],
        summary=metrics,
        cost_summary=None,  # No cost summary
        look_ahead_bias_check=True,
        execution_time_seconds=10.0,
    )

    generator = BacktestReportGenerator()
    html = generator.generate_html_report(result)

    # Should generate without cost section
    assert html
    # Cost section should NOT appear
    assert "Transaction Cost" not in html


# ==========================================================================================
# Test PDF Report Generation (Task 21.3)
# ==========================================================================================


def test_generate_pdf_report(sample_backtest_result):
    """Test PDF report generation."""
    # WeasyPrint requires system libraries (gobject-2.0-0) that may not be available
    # The OSError occurs during import when system libraries are missing
    try:
        import weasyprint  # noqa: F401
    except ImportError:
        pytest.skip("WeasyPrint not installed")
    except OSError as e:
        pytest.skip(f"WeasyPrint system libraries unavailable: {e}")

    generator = BacktestReportGenerator()
    pdf_bytes = generator.generate_pdf_report(sample_backtest_result)

    # Verify PDF is generated
    assert pdf_bytes
    assert len(pdf_bytes) > 1000  # Should be substantial

    # Verify PDF magic number (PDF files start with %PDF)
    assert pdf_bytes[:4] == b"%PDF"


def test_generate_pdf_report_missing_weasyprint(sample_backtest_result, monkeypatch):
    """Test PDF generation when WeasyPrint is not installed."""
    import builtins

    # Save original import
    original_import = builtins.__import__

    # Mock WeasyPrint import to raise ImportError
    def mock_import(name, *args, **kwargs):
        if name == "weasyprint":
            raise ImportError("WeasyPrint not found")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    generator = BacktestReportGenerator()

    with pytest.raises(ImportError, match="WeasyPrint is required"):
        generator.generate_pdf_report(sample_backtest_result)


# ==========================================================================================
# Test CSV Export (Task 21.4)
# ==========================================================================================


def test_generate_csv_trade_list(sample_trades):
    """Test CSV trade list generation."""
    generator = BacktestReportGenerator()
    csv_content = generator.generate_csv_trade_list(sample_trades)

    # Verify CSV is not empty
    assert csv_content
    assert len(csv_content) > 100

    # Parse CSV
    reader = csv.DictReader(StringIO(csv_content))
    rows = list(reader)

    # Verify row count matches trade count
    assert len(rows) == len(sample_trades)

    # Verify all expected columns exist
    expected_columns = [
        "trade_id",
        "position_id",
        "symbol",
        "pattern_type",
        "entry_timestamp",
        "entry_price",
        "exit_timestamp",
        "exit_price",
        "quantity",
        "side",
        "realized_pnl",
        "commission",
        "slippage",
        "net_pnl",
        "r_multiple",
        "gross_pnl",
        "gross_r_multiple",
    ]

    assert set(reader.fieldnames) == set(expected_columns)

    # Verify first row data integrity
    first_row = rows[0]
    first_trade = sample_trades[0]

    assert first_row["symbol"] == first_trade.symbol
    assert first_row["side"] == first_trade.side
    assert first_row["pattern_type"] == first_trade.pattern_type

    # Verify decimal formatting (2 decimal places for P&L)
    assert "." in first_row["realized_pnl"]
    decimal_places = len(first_row["realized_pnl"].split(".")[1])
    assert decimal_places == 2

    # Verify price formatting (2 decimal places for prices)
    assert "." in first_row["entry_price"]
    price_decimal_places = len(first_row["entry_price"].split(".")[1])
    assert price_decimal_places == 2


def test_generate_csv_empty_trades():
    """Test CSV generation with no trades."""
    generator = BacktestReportGenerator()
    csv_content = generator.generate_csv_trade_list([])

    # Should still have headers
    assert csv_content
    reader = csv.DictReader(StringIO(csv_content))
    rows = list(reader)

    assert len(rows) == 0  # No data rows
    assert reader.fieldnames  # But headers exist


def test_csv_net_pnl_calculation(sample_trades):
    """Test that net P&L is calculated correctly (realized - commission - slippage)."""
    generator = BacktestReportGenerator()
    csv_content = generator.generate_csv_trade_list(sample_trades)

    reader = csv.DictReader(StringIO(csv_content))
    rows = list(reader)

    for row, trade in zip(rows, sample_trades, strict=False):
        expected_net_pnl = (
            trade.realized_pnl
            - (trade.commission or Decimal("0"))
            - (trade.slippage or Decimal("0"))
        )

        actual_net_pnl = Decimal(row["net_pnl"])

        assert abs(actual_net_pnl - expected_net_pnl) < Decimal("0.01")


# ==========================================================================================
# Test Helper Methods
# ==========================================================================================


def test_calculate_monthly_returns(sample_equity_curve):
    """Test monthly returns calculation."""
    generator = BacktestReportGenerator()
    monthly_returns = generator._calculate_monthly_returns(sample_equity_curve)

    # Should have at least one month
    assert monthly_returns
    assert len(monthly_returns) >= 1

    # Verify structure
    first_month = monthly_returns[0]
    assert "year" in first_month
    assert "month" in first_month
    assert "month_label" in first_month
    assert "return_pct" in first_month

    # Verify label format
    assert first_month["month_label"] == "2024-01"


def test_calculate_drawdown_periods(sample_equity_curve):
    """Test drawdown period calculation."""
    generator = BacktestReportGenerator()
    drawdowns = generator._calculate_drawdown_periods(sample_equity_curve)

    # May or may not have drawdowns depending on equity curve
    if drawdowns:
        # Verify structure
        first_dd = drawdowns[0]
        assert "peak_date" in first_dd
        assert "trough_date" in first_dd
        assert "peak_value" in first_dd
        assert "trough_value" in first_dd
        assert "drawdown_pct" in first_dd

        # Verify drawdown is negative
        assert first_dd["drawdown_pct"] > 0  # Stored as absolute value

        # Verify sorted by drawdown size (worst first)
        if len(drawdowns) > 1:
            assert drawdowns[0]["drawdown_pct"] >= drawdowns[1]["drawdown_pct"]


def test_format_percentage():
    """Test percentage formatting filter."""
    generator = BacktestReportGenerator()

    assert generator._format_percentage(12.5) == "12.50%"
    assert generator._format_percentage(Decimal("0.5")) == "0.50%"
    assert generator._format_percentage(100) == "100.00%"


def test_format_currency():
    """Test currency formatting filter."""
    generator = BacktestReportGenerator()

    assert generator._format_currency(1000) == "$1,000.00"
    assert generator._format_currency(Decimal("12345.67")) == "$12,345.67"
    assert generator._format_currency(-500) == "$-500.00"


def test_format_decimal():
    """Test decimal formatting filter."""
    generator = BacktestReportGenerator()

    assert generator._format_decimal(12.3456, 2) == "12.35"
    assert generator._format_decimal(Decimal("1.999"), 2) == "2.00"
    assert generator._format_decimal(100, 4) == "100.0000"
