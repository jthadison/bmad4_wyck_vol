"""
Backtest Report Generator (Story 12.6B Task 3)

Purpose:
--------
Generates comprehensive HTML, PDF, and CSV reports for backtest results.
Provides professional formatted reports with charts, metrics, and trade analysis.

Features:
---------
- Jinja2-based HTML templating
- Equity curve visualization with Chart.js
- Monthly returns heatmap
- Drawdown analysis
- Pattern performance breakdown
- Transaction cost analysis
- CSV trade list export
- PDF generation via WeasyPrint

Usage:
------
    from backtesting.backtest_report_generator import BacktestReportGenerator

    generator = BacktestReportGenerator()

    # Generate HTML report
    html = generator.generate_html_report(backtest_result)

    # Generate PDF report
    pdf_bytes = generator.generate_pdf_report(backtest_result)

    # Generate CSV trade list
    csv = generator.generate_csv_trade_list(backtest_result.trades)

Author: Story 12.6B Task 3
"""

from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
from io import StringIO
from pathlib import Path
from typing import Any

import structlog
from jinja2 import Environment, FileSystemLoader

from src.models.backtest import BacktestResult, BacktestTrade

logger = structlog.get_logger(__name__)


class BacktestReportGenerator:
    """
    Generates comprehensive reports for backtest results (Story 12.6B Task 3).

    Creates professional HTML, PDF, and CSV reports with:
    - Summary metrics (total return, CAGR, Sharpe ratio, max drawdown, win rate)
    - Equity curve chart
    - Monthly returns heatmap
    - Drawdown analysis
    - Transaction cost breakdown (Story 12.5)
    - Trade list with all details
    """

    def __init__(self):
        """Initialize report generator with Jinja2 environment."""
        self.logger = logger.bind(component="backtest_report_generator")

        # Set up Jinja2 environment
        templates_dir = Path(__file__).parent / "templates"
        templates_dir.mkdir(exist_ok=True)

        self.jinja_env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)

        # Register custom filters
        self.jinja_env.filters["percentage"] = self._format_percentage
        self.jinja_env.filters["decimal"] = self._format_decimal
        self.jinja_env.filters["currency"] = self._format_currency

    def generate_html_report(self, backtest_result: BacktestResult) -> str:
        """
        Generate HTML report from BacktestResult (Task 3.5).

        Args:
            backtest_result: Complete backtest result with all data

        Returns:
            str: Complete HTML report as string

        Example:
            >>> generator = BacktestReportGenerator()
            >>> html = generator.generate_html_report(result)
            >>> with open("report.html", "w") as f:
            ...     f.write(html)
        """
        self.logger.info(
            "Generating HTML report",
            backtest_run_id=str(backtest_result.backtest_run_id),
            symbol=backtest_result.symbol,
        )

        # Prepare data for template
        context = self._prepare_template_context(backtest_result)

        # Render template
        template = self.jinja_env.get_template("backtest_report.html")
        html = template.render(**context)

        self.logger.info(
            "HTML report generated",
            html_length=len(html),
            backtest_run_id=str(backtest_result.backtest_run_id),
        )

        return html

    def generate_pdf_report(self, backtest_result: BacktestResult) -> bytes:
        """
        Generate PDF report from BacktestResult (Task 4.3).

        Converts HTML report to PDF using WeasyPrint.

        Args:
            backtest_result: Complete backtest result with all data

        Returns:
            bytes: PDF report as bytes

        Example:
            >>> generator = BacktestReportGenerator()
            >>> pdf_bytes = generator.generate_pdf_report(result)
            >>> with open("report.pdf", "wb") as f:
            ...     f.write(pdf_bytes)
        """
        self.logger.info(
            "Generating PDF report",
            backtest_run_id=str(backtest_result.backtest_run_id),
        )

        # Generate HTML first
        html = self.generate_html_report(backtest_result)

        # Import WeasyPrint (only when needed)
        try:
            from weasyprint import HTML
        except ImportError as e:
            self.logger.error("WeasyPrint not installed", error=str(e))
            raise ImportError(
                "WeasyPrint is required for PDF generation. " "Install with: poetry add weasyprint"
            ) from e

        # Convert HTML to PDF
        pdf_file = HTML(string=html).write_pdf()

        self.logger.info(
            "PDF report generated",
            pdf_size=len(pdf_file),
            backtest_run_id=str(backtest_result.backtest_run_id),
        )

        return pdf_file

    def generate_csv_trade_list(self, trades: list[BacktestTrade]) -> str:
        """
        Generate CSV trade list export (Task 5.2).

        Args:
            trades: List of backtest trades

        Returns:
            str: CSV formatted trade list

        Example:
            >>> generator = BacktestReportGenerator()
            >>> csv = generator.generate_csv_trade_list(result.trades)
            >>> with open("trades.csv", "w") as f:
            ...     f.write(csv)
        """
        self.logger.info("Generating CSV trade list", trade_count=len(trades))

        # Define CSV columns
        columns = [
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

        # Create CSV in memory
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=columns)

        # Write header
        writer.writeheader()

        # Write trade data
        for trade in trades:
            # Calculate net P&L (realized - commission - slippage)
            net_pnl = (
                trade.realized_pnl
                - (trade.commission or Decimal("0"))
                - (trade.slippage or Decimal("0"))
            )

            writer.writerow(
                {
                    "trade_id": str(trade.trade_id),
                    "position_id": str(trade.position_id),
                    "symbol": trade.symbol,
                    "pattern_type": trade.pattern_type or "",
                    "entry_timestamp": trade.entry_timestamp.isoformat(),
                    "entry_price": f"{trade.entry_price:.2f}",
                    "exit_timestamp": trade.exit_timestamp.isoformat()
                    if trade.exit_timestamp
                    else "",
                    "exit_price": f"{trade.exit_price:.2f}" if trade.exit_price else "",
                    "quantity": str(trade.quantity),
                    "side": trade.side,
                    "realized_pnl": f"{trade.realized_pnl:.2f}",
                    "commission": f"{trade.commission:.2f}" if trade.commission else "0.00",
                    "slippage": f"{trade.slippage:.2f}" if trade.slippage else "0.00",
                    "net_pnl": f"{net_pnl:.2f}",
                    "r_multiple": f"{trade.r_multiple:.2f}" if trade.r_multiple else "0.00",
                    "gross_pnl": f"{trade.gross_pnl:.2f}" if trade.gross_pnl else "0.00",
                    "gross_r_multiple": f"{trade.gross_r_multiple:.2f}"
                    if trade.gross_r_multiple
                    else "0.00",
                }
            )

        csv_content = output.getvalue()

        self.logger.info(
            "CSV trade list generated",
            trade_count=len(trades),
            csv_length=len(csv_content),
        )

        return csv_content

    def _prepare_template_context(self, result: BacktestResult) -> dict[str, Any]:
        """
        Prepare data for Jinja2 template rendering (Task 3.4).

        Converts BacktestResult to template-friendly format with:
        - Formatted dates and decimals
        - Chart data (equity curve, monthly returns)
        - Metric summaries
        - Transaction cost breakdown

        Args:
            result: BacktestResult to prepare

        Returns:
            dict: Template context with all data
        """
        # Extract metrics
        metrics = result.summary

        # Prepare equity curve chart data (ensure JSON serializable - TEST-001 fix)
        # Note: Using "data" instead of "values" to avoid Jinja2 dict.values() method conflict
        equity_labels = []
        equity_data = []
        for point in result.equity_curve:
            equity_labels.append(point.timestamp.strftime("%Y-%m-%d"))
            equity_data.append(float(point.equity_value))

        equity_chart_data = {
            "labels": equity_labels,
            "data": equity_data,
        }

        # Calculate monthly returns for heatmap
        monthly_returns = self._calculate_monthly_returns(result.equity_curve)

        # Identify top drawdowns
        drawdown_periods = self._calculate_drawdown_periods(result.equity_curve)

        # Transaction cost summary (Story 12.5)
        cost_breakdown = None
        if result.cost_summary:
            cost_breakdown = {
                "total_commission": float(result.cost_summary.total_commission_paid),
                "total_slippage": float(result.cost_summary.total_slippage_cost),
                "total_costs": float(result.cost_summary.total_transaction_costs),
                "cost_as_pct_of_pnl": float(result.cost_summary.cost_as_pct_of_total_pnl)
                * 100,  # Convert to percentage
                "avg_commission_per_trade": float(result.cost_summary.avg_commission_per_trade),
                "avg_slippage_per_trade": float(result.cost_summary.avg_slippage_per_trade),
            }

        # Prepare context
        context = {
            # Header info
            "symbol": result.symbol,
            "start_date": result.start_date.strftime("%Y-%m-%d"),
            "end_date": result.end_date.strftime("%Y-%m-%d"),
            "initial_capital": float(result.config.initial_capital),
            "backtest_run_id": str(result.backtest_run_id),
            "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            # Summary metrics
            "metrics": {
                "total_return_pct": float(metrics.total_return_pct),
                "cagr": float(metrics.cagr) if metrics.cagr else 0.0,
                "sharpe_ratio": float(metrics.sharpe_ratio) if metrics.sharpe_ratio else 0.0,
                "max_drawdown_pct": float(metrics.max_drawdown),
                "win_rate": float(metrics.win_rate),
                "total_trades": metrics.total_trades,
                "winning_trades": metrics.winning_trades,
                "losing_trades": metrics.losing_trades,
                "avg_r_multiple": float(metrics.avg_r_multiple) if metrics.avg_r_multiple else 0.0,
                "profit_factor": float(metrics.profit_factor) if metrics.profit_factor else 0.0,
                "total_pnl": float(metrics.total_return_pct)
                * float(result.config.initial_capital)
                / 100.0,
                "final_equity": float(result.config.initial_capital)
                * (1 + float(metrics.total_return_pct)),
            },
            # Charts
            "equity_curve_data": equity_chart_data,
            "monthly_returns": monthly_returns,
            "drawdown_periods": drawdown_periods,
            # Transaction costs
            "cost_breakdown": cost_breakdown,
            # Trades
            "trades": [self._format_trade_for_template(t) for t in result.trades],
            # Execution metadata
            "execution_time_seconds": result.execution_time_seconds,
            "look_ahead_bias_check": result.look_ahead_bias_check,
        }

        return context

    def _format_trade_for_template(self, trade: BacktestTrade) -> dict[str, Any]:
        """Format trade for template display."""
        net_pnl = (
            trade.realized_pnl
            - (trade.commission or Decimal("0"))
            - (trade.slippage or Decimal("0"))
        )

        return {
            "entry_date": trade.entry_timestamp.strftime("%Y-%m-%d %H:%M"),
            "exit_date": trade.exit_timestamp.strftime("%Y-%m-%d %H:%M")
            if trade.exit_timestamp
            else "",
            "symbol": trade.symbol,
            "pattern_type": trade.pattern_type or "N/A",
            "side": trade.side,
            "quantity": float(trade.quantity),
            "entry_price": float(trade.entry_price),
            "exit_price": float(trade.exit_price) if trade.exit_price else 0.0,
            "pnl": float(trade.realized_pnl),
            "net_pnl": float(net_pnl),
            "r_multiple": float(trade.r_multiple) if trade.r_multiple else 0.0,
            "commission": float(trade.commission) if trade.commission else 0.0,
            "slippage": float(trade.slippage) if trade.slippage else 0.0,
        }

    def _calculate_monthly_returns(self, equity_curve: list) -> list[dict[str, Any]]:
        """Calculate monthly returns for heatmap."""
        if not equity_curve:
            return []

        # Group equity points by year-month
        monthly_data: dict[tuple[int, int], list[float]] = {}

        for point in equity_curve:
            year_month = (point.timestamp.year, point.timestamp.month)
            if year_month not in monthly_data:
                monthly_data[year_month] = []
            monthly_data[year_month].append(float(point.equity_value))

        # Calculate return for each month
        monthly_returns = []
        sorted_months = sorted(monthly_data.keys())

        for i, (year, month) in enumerate(sorted_months):
            values = monthly_data[(year, month)]
            start_value = values[0]
            end_value = values[-1]

            # Calculate return
            if start_value > 0:
                return_pct = ((end_value - start_value) / start_value) * 100
            else:
                return_pct = 0.0

            monthly_returns.append(
                {
                    "year": year,
                    "month": month,
                    "month_label": f"{year}-{month:02d}",
                    "return_pct": round(return_pct, 2),
                }
            )

        return monthly_returns

    def _calculate_drawdown_periods(self, equity_curve: list) -> list[dict[str, Any]]:
        """Calculate top drawdown periods."""
        if not equity_curve:
            return []

        drawdowns = []
        peak_value = 0.0
        peak_date = None

        for point in equity_curve:
            equity = float(point.equity_value)

            # Update peak
            if equity > peak_value:
                peak_value = equity
                peak_date = point.timestamp

            # Calculate drawdown from peak
            if peak_value > 0:
                drawdown_pct = ((equity - peak_value) / peak_value) * 100

                if drawdown_pct < -1.0:  # Only record significant drawdowns
                    drawdowns.append(
                        {
                            "peak_date": peak_date.strftime("%Y-%m-%d") if peak_date else "",
                            "trough_date": point.timestamp.strftime("%Y-%m-%d"),
                            "peak_value": round(peak_value, 2),
                            "trough_value": round(equity, 2),
                            "drawdown_pct": round(abs(drawdown_pct), 2),
                        }
                    )

        # Return top 5 worst drawdowns
        drawdowns.sort(key=lambda x: x["drawdown_pct"], reverse=True)
        return drawdowns[:5]

    # Template filter methods
    def _format_percentage(self, value: float | Decimal) -> str:
        """Format value as percentage."""
        return f"{float(value):.2f}%"

    def _format_decimal(self, value: float | Decimal, places: int = 2) -> str:
        """Format value as decimal."""
        return f"{float(value):.{places}f}"

    def _format_currency(self, value: float | Decimal) -> str:
        """Format value as currency."""
        return f"${float(value):,.2f}"
