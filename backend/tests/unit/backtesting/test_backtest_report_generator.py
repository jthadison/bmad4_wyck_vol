"""
Unit tests for BacktestReportGenerator (Story 12.8 Task 7).

Tests HTML, PDF, and CSV report generation with comprehensive coverage
of all calculation methods and template preparation logic.

Author: Story 12.8 Task 7
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

# Check if weasyprint is available
try:
    import weasyprint  # noqa: F401

    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError):
    WEASYPRINT_AVAILABLE = False

from src.backtesting.backtest_report_generator import BacktestReportGenerator
from src.models.backtest import (
    BacktestConfig,
    BacktestCostSummary,
    BacktestMetrics,
    BacktestResult,
    BacktestTrade,
    EquityCurvePoint,
)


def make_backtest_trade(
    symbol="AAPL", pattern=None, entry_date=None, exit_date=None, pnl=Decimal("200.00"), **kwargs
):
    """Helper to create BacktestTrade with defaults."""
    entry_date = entry_date or datetime(2024, 1, 1, tzinfo=UTC)
    exit_date = exit_date or (entry_date + timedelta(days=3))

    # Extract values from kwargs or use defaults
    entry_price = kwargs.pop("entry_price", Decimal("150.00"))
    exit_price = kwargs.pop("exit_price", Decimal("152.00"))
    commission = kwargs.pop("commission", Decimal("5.00"))
    slippage = kwargs.pop("slippage", Decimal("2.00"))
    r_multiple = kwargs.pop("r_multiple", Decimal("2.0"))

    # Convert None to Decimal("0") for optional fields
    if commission is None:
        commission = Decimal("0")
    if slippage is None:
        slippage = Decimal("0")
    if r_multiple is None:
        r_multiple = Decimal("0")

    return BacktestTrade(
        trade_id=uuid4(),
        position_id=uuid4(),
        symbol=symbol,
        pattern_type=pattern,
        entry_timestamp=entry_date,
        entry_price=entry_price,
        exit_timestamp=exit_date,
        exit_price=exit_price,
        quantity=100,
        side="LONG",
        realized_pnl=pnl,
        commission=commission,
        slippage=slippage,
        r_multiple=r_multiple,
        gross_pnl=pnl + Decimal("7.00"),  # Add back costs
        gross_r_multiple=Decimal("2.1"),
        **kwargs,
    )


def make_equity_point(timestamp, equity_value, portfolio_value=None):
    """Helper to create EquityCurvePoint."""
    equity_dec = Decimal(str(equity_value))
    portfolio_dec = Decimal(str(portfolio_value)) if portfolio_value else equity_dec

    return EquityCurvePoint(
        timestamp=timestamp,
        equity_value=equity_dec,
        portfolio_value=portfolio_dec,
        cash=equity_dec / 2,
        positions_value=equity_dec / 2,
    )


def make_backtest_config(initial_capital=Decimal("100000.00"), symbol="AAPL"):
    """Helper to create BacktestConfig."""
    from datetime import date

    return BacktestConfig(
        symbol=symbol,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        initial_capital=initial_capital,
        commission_rate=Decimal("0.001"),
        slippage_rate=Decimal("0.0005"),
        position_sizing="FIXED_PERCENTAGE",
        risk_per_trade=Decimal("0.02"),
        max_positions=5,
    )


def make_backtest_metrics(
    total_return_pct=Decimal("15.50"),
    win_rate=Decimal("0.65"),
    total_trades=10,
):
    """Helper to create BacktestMetrics."""
    return BacktestMetrics(
        total_return_pct=total_return_pct,
        cagr=Decimal("18.25"),
        sharpe_ratio=Decimal("1.85"),
        max_drawdown=Decimal("0.0850"),
        win_rate=win_rate,
        total_trades=total_trades,
        winning_trades=int(total_trades * float(win_rate)),
        losing_trades=total_trades - int(total_trades * float(win_rate)),
        avg_r_multiple=Decimal("1.75"),
        profit_factor=Decimal("2.25"),
        avg_trade_duration_hours=Decimal("72.50"),
    )


def make_backtest_result(
    symbol="AAPL",
    trades=None,
    equity_curve=None,
    metrics=None,
    config=None,
    cost_summary=None,
):
    """Helper to create BacktestResult."""
    from datetime import date

    trades = trades or []
    equity_curve = equity_curve or []
    metrics = metrics or make_backtest_metrics(total_trades=len(trades))
    config = config or make_backtest_config()

    return BacktestResult(
        backtest_run_id=uuid4(),
        symbol=symbol,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        config=config,
        summary=metrics,
        trades=trades,
        equity_curve=equity_curve,
        cost_summary=cost_summary,
        execution_time_seconds=12.345,
        look_ahead_bias_check=True,
        pattern_performance=[],
        monthly_returns=[],
        drawdown_periods=[],
        risk_metrics=None,
        campaign_performance=[],
    )


@pytest.fixture
def generator():
    """Create report generator instance."""
    return BacktestReportGenerator()


class TestHTMLReportGeneration:
    """Test HTML report generation."""

    def test_generate_html_with_minimal_data(self, generator):
        """Test HTML generation with minimal backtest result."""
        result = make_backtest_result(symbol="AAPL")

        html = generator.generate_html_report(result)

        assert isinstance(html, str)
        assert len(html) > 0
        assert "AAPL" in html
        assert "Backtest Report" in html or "backtest" in html.lower()

    def test_generate_html_with_complete_data(self, generator):
        """Test HTML generation with complete backtest result."""
        # Create comprehensive test data
        trades = [
            make_backtest_trade(pattern="SPRING", pnl=Decimal("300.00")),
            make_backtest_trade(pattern="SOS", pnl=Decimal("-100.00")),
            make_backtest_trade(pattern="LPS", pnl=Decimal("250.00")),
        ]

        equity_curve = [
            make_equity_point(datetime(2024, 1, 1, tzinfo=UTC), 100000),
            make_equity_point(datetime(2024, 6, 1, tzinfo=UTC), 107500),
            make_equity_point(datetime(2024, 12, 31, tzinfo=UTC), 115500),
        ]

        cost_summary = BacktestCostSummary(
            total_trades=3,
            total_commission_paid=Decimal("15.00"),
            total_slippage_cost=Decimal("6.00"),
            total_transaction_costs=Decimal("21.00"),
            cost_as_pct_of_total_pnl=Decimal("0.0467"),
            avg_commission_per_trade=Decimal("5.00"),
            avg_slippage_per_trade=Decimal("2.00"),
            avg_transaction_cost_per_trade=Decimal("7.00"),
            gross_avg_r_multiple=Decimal("2.10"),
            net_avg_r_multiple=Decimal("2.00"),
            r_multiple_degradation=Decimal("0.10"),
        )

        result = make_backtest_result(
            symbol="TSLA",
            trades=trades,
            equity_curve=equity_curve,
            metrics=make_backtest_metrics(total_trades=len(trades)),
            cost_summary=cost_summary,
        )

        html = generator.generate_html_report(result)

        # Verify essential content
        assert "TSLA" in html
        assert len(html) > 1000  # Should be substantial report

    @patch(
        "src.backtesting.backtest_report_generator.BacktestReportGenerator._prepare_template_context"
    )
    def test_generate_html_calls_prepare_context(self, mock_prepare, generator):
        """Test that HTML generation calls _prepare_template_context."""
        result = make_backtest_result()
        mock_prepare.return_value = {
            "symbol": "AAPL",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000.0,
            "backtest_run_id": str(uuid4()),
            "generated_at": "2024-12-29 00:00:00 UTC",
            "metrics": {
                "total_return_pct": 15.5,
                "cagr": 18.25,
                "sharpe_ratio": 1.85,
                "max_drawdown_pct": 0.085,
                "win_rate": 0.65,
                "total_trades": 10,
                "winning_trades": 6,
                "losing_trades": 4,
                "avg_r_multiple": 1.75,
                "profit_factor": 2.25,
                "total_pnl": 15500.0,
                "final_equity": 115500.0,
            },
            "equity_curve_data": {"labels": [], "data": []},
            "monthly_returns": [],
            "drawdown_periods": [],
            "cost_breakdown": None,
            "trades": [],
            "execution_time_seconds": 12.345,
            "look_ahead_bias_check": True,
        }

        generator.generate_html_report(result)

        mock_prepare.assert_called_once_with(result)


class TestPDFReportGeneration:
    """Test PDF report generation."""

    @pytest.mark.skipif(not WEASYPRINT_AVAILABLE, reason="WeasyPrint not installed")
    @patch("weasyprint.HTML")
    def test_generate_pdf_success(self, mock_html_class, generator):
        """Test successful PDF generation."""
        # Mock WeasyPrint
        mock_html_instance = MagicMock()
        mock_html_instance.write_pdf.return_value = b"PDF_CONTENT"
        mock_html_class.return_value = mock_html_instance

        result = make_backtest_result()

        pdf_bytes = generator.generate_pdf_report(result)

        assert pdf_bytes == b"PDF_CONTENT"
        mock_html_class.assert_called_once()
        mock_html_instance.write_pdf.assert_called_once()

    @pytest.mark.skipif(not WEASYPRINT_AVAILABLE, reason="WeasyPrint not installed")
    def test_generate_pdf_weasyprint_not_installed(self, generator):
        """Test PDF generation fails gracefully if WeasyPrint not installed."""
        # Patch the import to raise ImportError
        with patch("builtins.__import__", side_effect=ImportError("No module named 'weasyprint'")):
            result = make_backtest_result()

            with pytest.raises(ImportError, match="WeasyPrint is required"):
                generator.generate_pdf_report(result)


class TestCSVTradeListGeneration:
    """Test CSV trade list generation."""

    def test_generate_csv_empty_trades(self, generator):
        """Test CSV generation with empty trades list."""
        csv = generator.generate_csv_trade_list([])

        assert isinstance(csv, str)
        # Should have header row
        assert "trade_id" in csv
        assert "symbol" in csv
        assert "realized_pnl" in csv

    def test_generate_csv_with_trades(self, generator):
        """Test CSV generation with multiple trades."""
        trades = [
            make_backtest_trade(
                symbol="AAPL",
                pattern="SPRING",
                pnl=Decimal("300.00"),
                entry_date=datetime(2024, 1, 1, tzinfo=UTC),
            ),
            make_backtest_trade(
                symbol="TSLA",
                pattern="SOS",
                pnl=Decimal("-100.00"),
                entry_date=datetime(2024, 2, 1, tzinfo=UTC),
            ),
        ]

        csv = generator.generate_csv_trade_list(trades)

        # Verify CSV structure
        lines = csv.strip().split("\n")
        assert len(lines) == 3  # Header + 2 trades

        # Verify header
        header = lines[0]
        assert "trade_id" in header
        assert "symbol" in header
        assert "pattern_type" in header
        assert "realized_pnl" in header
        assert "commission" in header
        assert "net_pnl" in header

        # Verify data rows contain expected values
        assert "AAPL" in csv
        assert "TSLA" in csv
        assert "SPRING" in csv
        assert "SOS" in csv

    def test_generate_csv_net_pnl_calculation(self, generator):
        """Test that CSV correctly calculates net P&L."""
        trade = make_backtest_trade(
            pnl=Decimal("300.00"),
            commission=Decimal("5.00"),
            slippage=Decimal("2.00"),
        )

        csv = generator.generate_csv_trade_list([trade])

        # Net P&L = 300 - 5 - 2 = 293
        lines = csv.strip().split("\n")
        data_row = lines[1]
        assert "293.00" in data_row

    def test_generate_csv_decimal_formatting(self, generator):
        """Test CSV decimal formatting (2 decimal places)."""
        trade = make_backtest_trade(
            entry_price=Decimal("150.123"),
            exit_price=Decimal("152.789"),
            pnl=Decimal("278.66"),
        )

        csv = generator.generate_csv_trade_list([trade])

        # Prices should be rounded to 2 decimal places
        assert "150.12" in csv
        assert "152.79" in csv
        assert "278.66" in csv

    def test_generate_csv_iso_date_format(self, generator):
        """Test CSV uses ISO 8601 date format."""
        entry_date = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        exit_date = datetime(2024, 1, 18, 14, 45, 0, tzinfo=UTC)

        trade = make_backtest_trade(entry_date=entry_date, exit_date=exit_date)

        csv = generator.generate_csv_trade_list([trade])

        # Should contain ISO formatted dates
        assert "2024-01-15T10:30:00" in csv
        assert "2024-01-18T14:45:00" in csv


class TestTemplateContextPreparation:
    """Test _prepare_template_context method."""

    def test_prepare_context_basic_structure(self, generator):
        """Test context contains all required keys."""
        result = make_backtest_result()

        context = generator._prepare_template_context(result)

        # Verify all required keys present
        assert "symbol" in context
        assert "start_date" in context
        assert "end_date" in context
        assert "initial_capital" in context
        assert "backtest_run_id" in context
        assert "generated_at" in context
        assert "metrics" in context
        assert "equity_curve_data" in context
        assert "monthly_returns" in context
        assert "drawdown_periods" in context
        assert "cost_breakdown" in context
        assert "trades" in context
        assert "execution_time_seconds" in context
        assert "look_ahead_bias_check" in context

    def test_prepare_context_metrics_conversion(self, generator):
        """Test metrics are converted to float for template."""
        metrics = make_backtest_metrics(
            total_return_pct=Decimal("15.50"),
            win_rate=Decimal("0.65"),
        )
        result = make_backtest_result(metrics=metrics)

        context = generator._prepare_template_context(result)

        metrics_dict = context["metrics"]
        assert isinstance(metrics_dict["total_return_pct"], float)
        assert metrics_dict["total_return_pct"] == 15.50
        assert isinstance(metrics_dict["win_rate"], float)
        assert metrics_dict["win_rate"] == 0.65

    def test_prepare_context_equity_curve_data(self, generator):
        """Test equity curve data prepared correctly."""
        equity_curve = [
            make_equity_point(datetime(2024, 1, 1, tzinfo=UTC), 100000),
            make_equity_point(datetime(2024, 6, 1, tzinfo=UTC), 107500),
            make_equity_point(datetime(2024, 12, 31, tzinfo=UTC), 115500),
        ]
        result = make_backtest_result(equity_curve=equity_curve)

        context = generator._prepare_template_context(result)

        chart_data = context["equity_curve_data"]
        assert "labels" in chart_data
        assert "data" in chart_data
        assert len(chart_data["labels"]) == 3
        assert len(chart_data["data"]) == 3
        assert chart_data["labels"][0] == "2024-01-01"
        assert chart_data["data"][0] == 100000.0
        assert chart_data["data"][-1] == 115500.0

    def test_prepare_context_with_cost_summary(self, generator):
        """Test cost breakdown when cost_summary provided."""
        cost_summary = BacktestCostSummary(
            total_trades=3,
            total_commission_paid=Decimal("15.00"),
            total_slippage_cost=Decimal("6.00"),
            total_transaction_costs=Decimal("21.00"),
            cost_as_pct_of_total_pnl=Decimal("0.0467"),
            avg_commission_per_trade=Decimal("5.00"),
            avg_slippage_per_trade=Decimal("2.00"),
            avg_transaction_cost_per_trade=Decimal("7.00"),
            gross_avg_r_multiple=Decimal("2.10"),
            net_avg_r_multiple=Decimal("2.00"),
            r_multiple_degradation=Decimal("0.10"),
        )
        result = make_backtest_result(cost_summary=cost_summary)

        context = generator._prepare_template_context(result)

        cost_breakdown = context["cost_breakdown"]
        assert cost_breakdown is not None
        assert cost_breakdown["total_commission"] == 15.0
        assert cost_breakdown["total_slippage"] == 6.0
        assert cost_breakdown["total_costs"] == 21.0
        assert cost_breakdown["cost_as_pct_of_pnl"] == 4.67  # Converted to percentage

    def test_prepare_context_without_cost_summary(self, generator):
        """Test cost breakdown is None when no cost_summary."""
        result = make_backtest_result(cost_summary=None)

        context = generator._prepare_template_context(result)

        assert context["cost_breakdown"] is None

    def test_prepare_context_trades_formatting(self, generator):
        """Test trades are formatted correctly for template."""
        trade = make_backtest_trade(
            pattern="SPRING",
            pnl=Decimal("300.00"),
            commission=Decimal("5.00"),
            slippage=Decimal("2.00"),
        )
        result = make_backtest_result(trades=[trade])

        context = generator._prepare_template_context(result)

        formatted_trades = context["trades"]
        assert len(formatted_trades) == 1

        formatted_trade = formatted_trades[0]
        assert formatted_trade["pattern_type"] == "SPRING"
        assert formatted_trade["pnl"] == 300.0
        assert formatted_trade["net_pnl"] == 293.0  # 300 - 5 - 2


class TestMonthlyReturnsCalculation:
    """Test _calculate_monthly_returns method."""

    def test_calculate_monthly_returns_empty_curve(self, generator):
        """Test with empty equity curve."""
        result = generator._calculate_monthly_returns([])

        assert result == []

    def test_calculate_monthly_returns_single_month(self, generator):
        """Test with single month data."""
        equity_curve = [
            make_equity_point(datetime(2024, 1, 1, tzinfo=UTC), 100000),
            make_equity_point(datetime(2024, 1, 15, tzinfo=UTC), 105000),
            make_equity_point(datetime(2024, 1, 31, tzinfo=UTC), 107000),
        ]

        result = generator._calculate_monthly_returns(equity_curve)

        assert len(result) == 1
        monthly = result[0]
        assert monthly["year"] == 2024
        assert monthly["month"] == 1
        assert monthly["month_label"] == "2024-01"
        # Return: (107000 - 100000) / 100000 * 100 = 7%
        assert monthly["return_pct"] == 7.0

    def test_calculate_monthly_returns_multiple_months(self, generator):
        """Test with multiple months."""
        equity_curve = [
            make_equity_point(datetime(2024, 1, 1, tzinfo=UTC), 100000),
            make_equity_point(datetime(2024, 1, 31, tzinfo=UTC), 105000),
            make_equity_point(datetime(2024, 2, 1, tzinfo=UTC), 105000),
            make_equity_point(datetime(2024, 2, 28, tzinfo=UTC), 103000),
        ]

        result = generator._calculate_monthly_returns(equity_curve)

        assert len(result) == 2
        # January: +5%
        assert result[0]["return_pct"] == 5.0
        # February: -1.9% (approx)
        assert -2.0 < result[1]["return_pct"] < -1.8


class TestDrawdownPeriodsCalculation:
    """Test _calculate_drawdown_periods method."""

    def test_calculate_drawdown_empty_curve(self, generator):
        """Test with empty equity curve."""
        result = generator._calculate_drawdown_periods([])

        assert result == []

    def test_calculate_drawdown_no_drawdowns(self, generator):
        """Test with always rising equity curve."""
        equity_curve = [
            make_equity_point(datetime(2024, 1, 1, tzinfo=UTC), 100000),
            make_equity_point(datetime(2024, 2, 1, tzinfo=UTC), 105000),
            make_equity_point(datetime(2024, 3, 1, tzinfo=UTC), 110000),
        ]

        result = generator._calculate_drawdown_periods(equity_curve)

        # No significant drawdowns (>1%)
        assert len(result) == 0

    def test_calculate_drawdown_single_drawdown(self, generator):
        """Test with single drawdown period."""
        equity_curve = [
            make_equity_point(datetime(2024, 1, 1, tzinfo=UTC), 100000),  # Peak
            make_equity_point(datetime(2024, 1, 15, tzinfo=UTC), 95000),  # -5% drawdown
            make_equity_point(datetime(2024, 2, 1, tzinfo=UTC), 101000),  # Recovery
        ]

        result = generator._calculate_drawdown_periods(equity_curve)

        assert len(result) == 1
        dd = result[0]
        assert dd["peak_date"] == "2024-01-01"
        assert dd["trough_date"] == "2024-01-15"
        assert dd["peak_value"] == 100000.0
        assert dd["trough_value"] == 95000.0
        assert dd["drawdown_pct"] == 5.0

    def test_calculate_drawdown_returns_top_5(self, generator):
        """Test that only top 5 drawdowns returned."""
        # Create 7 drawdown periods by oscillating equity
        equity_curve = []
        base_date = datetime(2024, 1, 1, tzinfo=UTC)

        for i in range(15):
            value = 100000 + (i % 2) * 5000 - (i // 2) * 2000
            equity_curve.append(make_equity_point(base_date + timedelta(days=i * 10), value))

        result = generator._calculate_drawdown_periods(equity_curve)

        # Should return at most 5
        assert len(result) <= 5


class TestTemplateFilters:
    """Test Jinja2 template filter methods."""

    def test_format_percentage(self, generator):
        """Test percentage formatting."""
        assert generator._format_percentage(15.5) == "15.50%"
        assert generator._format_percentage(Decimal("8.75")) == "8.75%"
        assert generator._format_percentage(0.0) == "0.00%"

    def test_format_decimal(self, generator):
        """Test decimal formatting."""
        assert generator._format_decimal(15.5) == "15.50"
        assert generator._format_decimal(15.5, places=3) == "15.500"
        assert generator._format_decimal(Decimal("8.7567"), places=2) == "8.76"

    def test_format_currency(self, generator):
        """Test currency formatting."""
        assert generator._format_currency(1000.50) == "$1,000.50"
        assert generator._format_currency(Decimal("100000.00")) == "$100,000.00"
        assert generator._format_currency(0.0) == "$0.00"


class TestFormatTradeForTemplate:
    """Test _format_trade_for_template method."""

    def test_format_trade_complete_data(self, generator):
        """Test formatting trade with all fields."""
        trade = make_backtest_trade(
            symbol="AAPL",
            pattern="SPRING",
            entry_date=datetime(2024, 1, 1, 10, 30, tzinfo=UTC),
            exit_date=datetime(2024, 1, 5, 14, 45, tzinfo=UTC),
            pnl=Decimal("300.00"),
        )

        result = generator._format_trade_for_template(trade)

        assert result["symbol"] == "AAPL"
        assert result["pattern_type"] == "SPRING"
        assert result["entry_date"] == "2024-01-01 10:30"
        assert result["exit_date"] == "2024-01-05 14:45"
        assert result["pnl"] == 300.0
        assert result["net_pnl"] == 293.0  # 300 - 5 - 2
        assert result["side"] == "LONG"

    def test_format_trade_missing_pattern(self, generator):
        """Test formatting trade without pattern."""
        trade = make_backtest_trade(pattern=None)

        result = generator._format_trade_for_template(trade)

        assert result["pattern_type"] == "N/A"

    def test_format_trade_missing_optional_fields(self, generator):
        """Test formatting trade with None values for optional fields."""
        trade = make_backtest_trade(
            commission=None,
            slippage=None,
            r_multiple=None,
        )

        result = generator._format_trade_for_template(trade)

        assert result["commission"] == 0.0
        assert result["slippage"] == 0.0
        assert result["r_multiple"] == 0.0
        # Net PnL calculation with None values
        assert result["net_pnl"] == result["pnl"]
