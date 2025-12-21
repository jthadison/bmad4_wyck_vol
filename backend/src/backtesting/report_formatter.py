"""
Backtest Report Formatter (Story 12.5 Task 10).

Formats backtest results with detailed commission and slippage breakdowns
into human-readable reports and structured data for frontend visualization.

AC8: Backtest report shows commission/slippage per trade
AC10: Display R-multiple degradation prominently

Author: Story 12.5 Task 10
"""

from decimal import Decimal
from typing import Any

import structlog

from src.models.backtest import BacktestResult, BacktestTrade, TransactionCostReport

logger = structlog.get_logger(__name__)


class BacktestReportFormatter:
    """
    Format backtest results with cost analysis for reports and visualization.

    Provides multiple output formats:
    - Human-readable text summary
    - Structured JSON for frontend charts
    - Per-trade cost breakdown tables
    - Cost summary with R-multiple degradation

    Methods:
        format_cost_summary: Format aggregate cost summary
        format_trade_costs: Format per-trade cost breakdown
        format_full_report: Combine all sections into complete report
        to_json: Convert report to JSON for frontend

    Example:
        formatter = BacktestReportFormatter()
        backtest_result = BacktestResult(...)

        # Get full report
        report = formatter.format_full_report(backtest_result)
        print(report)

        # Get JSON for frontend
        report_json = formatter.to_json(backtest_result)
        # Use in API response

    Author: Story 12.5 Task 10
    """

    def format_cost_summary(self, backtest_result: BacktestResult) -> str:
        """
        Format aggregate cost summary with R-multiple degradation.

        Subtask 10.2: Display total commission paid
        Subtask 10.2: Display total slippage cost
        Subtask 10.2: Display gross vs net average R-multiple
        Subtask 10.2: Highlight R-multiple degradation prominently

        Args:
            backtest_result: Complete backtest result with cost_summary

        Returns:
            Formatted cost summary string

        Example output:
            ========== TRANSACTION COST SUMMARY ==========
            Total Trades: 100
            Total Commission Paid: $1,000.00
            Total Slippage Cost: $400.00
            Total Transaction Costs: $1,400.00

            Average per Trade:
              Commission: $10.00
              Slippage: $4.00
              Total Cost: $14.00

            Performance Impact:
              Gross Avg R-Multiple: 2.50R
              Net Avg R-Multiple: 2.36R
              R-Multiple Degradation: 0.14R (5.6% impact) ⚠️

        Author: Story 12.5 Subtask 10.2
        """
        if not backtest_result.cost_summary:
            return "No cost summary available (no trades executed)"

        summary = backtest_result.cost_summary

        # Calculate degradation percentage
        if summary.gross_avg_r_multiple != Decimal("0"):
            degradation_pct = (
                summary.r_multiple_degradation / summary.gross_avg_r_multiple
            ) * Decimal("100")
        else:
            degradation_pct = Decimal("0")

        report = f"""
========== TRANSACTION COST SUMMARY ==========
Total Trades: {summary.total_trades}
Total Commission Paid: ${summary.total_commission_paid:,.2f}
Total Slippage Cost: ${summary.total_slippage_cost:,.2f}
Total Transaction Costs: ${summary.total_transaction_costs:,.2f}

Average per Trade:
  Commission: ${summary.avg_commission_per_trade:,.2f}
  Slippage: ${summary.avg_slippage_per_trade:,.2f}
  Total Cost: ${summary.avg_transaction_cost_per_trade:,.2f}

Performance Impact:
  Gross Avg R-Multiple: {summary.gross_avg_r_multiple:.2f}R
  Net Avg R-Multiple: {summary.net_avg_r_multiple:.2f}R
  R-Multiple Degradation: {summary.r_multiple_degradation:.2f}R ({degradation_pct:.1f}% impact) ⚠️

Cost as % of Total P&L: {summary.cost_as_pct_of_total_pnl:.1f}%
==============================================
"""

        return report.strip()

    def format_trade_costs(self, trade: BacktestTrade, trade_report: TransactionCostReport) -> str:
        """
        Format per-trade cost breakdown.

        Subtask 10.3: Display entry commission and slippage
        Subtask 10.3: Display exit commission and slippage
        Subtask 10.3: Display total transaction costs
        Subtask 10.3: Display gross vs net P&L
        Subtask 10.3: Display gross vs net R-multiple

        Args:
            trade: Backtest trade
            trade_report: Transaction cost report for the trade

        Returns:
            Formatted trade cost breakdown string

        Example output:
            Trade #abc-123-def | BUY 100 @ $150.00 → SELL @ $155.00
            -----------------------------------------------------------
            Entry Costs:
              Commission: $5.00
              Slippage: $2.00
            Exit Costs:
              Commission: $5.00
              Slippage: $2.00
            Total Transaction Costs: $14.00 (0.14R)

            Performance:
              Gross P&L: $250.00 (2.50R)
              Net P&L: $236.00 (2.36R)
              Cost Impact: $14.00 (5.6% of gross P&L)

        Author: Story 12.5 Subtask 10.3
        """
        trade_id_short = str(trade.trade_id)[:8]

        report = f"""
Trade #{trade_id_short} | {trade.side} {trade.quantity} @ ${trade.entry_price:.2f} → ${trade.exit_price:.2f}
-----------------------------------------------------------
Entry Costs:
  Commission: ${trade.entry_commission:,.2f}
  Slippage: ${trade.entry_slippage:,.2f}
Exit Costs:
  Commission: ${trade.exit_commission:,.2f}
  Slippage: ${trade.exit_slippage:,.2f}
Total Transaction Costs: ${trade_report.total_transaction_costs:,.2f} ({trade_report.transaction_cost_r_multiple:.2f}R)

Performance:
  Gross P&L: ${trade_report.gross_pnl:,.2f} ({trade_report.gross_r_multiple:.2f}R)
  Net P&L: ${trade_report.net_pnl:,.2f} ({trade_report.net_r_multiple:.2f}R)
  Cost Impact: ${trade_report.total_transaction_costs:,.2f} ({trade_report.transaction_cost_pct:.1f}% of gross P&L)
"""

        return report.strip()

    def format_full_report(self, backtest_result: BacktestResult) -> str:
        """
        Format complete backtest report with cost analysis.

        Subtask 10.4: Combine cost summary and sample trade breakdowns
        Subtask 10.4: Include configuration details
        Subtask 10.4: Add warnings if R-multiple degradation is high (>10%)

        Args:
            backtest_result: Complete backtest result

        Returns:
            Full formatted report string

        Example output:
            ============== BACKTEST REPORT ==============
            Backtest ID: abc-123-def
            Start Capital: $100,000.00
            Total Trades: 100

            Configuration:
              Commission: PER_SHARE ($0.005/share, Interactive Brokers Retail)
              Slippage: LIQUIDITY_BASED (High: 0.02%, Low: 0.05%)
              Market Impact: Enabled

            [Cost Summary Section]

            Sample Trade Breakdowns (First 5 Trades):
            [Trade 1 Details]
            [Trade 2 Details]
            ...

            ⚠️ WARNING: R-multiple degradation exceeds 10% - Consider:
              - Reducing position sizes to minimize market impact
              - Using limit orders instead of market orders
              - Trading more liquid instruments

        Author: Story 12.5 Subtask 10.4
        """
        from src.backtesting.transaction_cost_analyzer import TransactionCostAnalyzer

        cost_analyzer = TransactionCostAnalyzer()

        # Header
        report_lines = [
            "=" * 60,
            "BACKTEST REPORT WITH TRANSACTION COST ANALYSIS",
            "=" * 60,
            f"Backtest ID: {backtest_result.backtest_run_id}",
            f"Start Capital: ${backtest_result.start_capital:,.2f}",
            f"Total Trades: {len(backtest_result.trades)}",
            "",
        ]

        # Configuration
        report_lines.append("Configuration:")
        if backtest_result.config.commission_config:
            comm = backtest_result.config.commission_config
            report_lines.append(
                f"  Commission: {comm.commission_type} "
                f"(${comm.commission_per_share}/share, {comm.broker_name})"
            )
        if backtest_result.config.slippage_config:
            slip = backtest_result.config.slippage_config
            report_lines.append(
                f"  Slippage: {slip.slippage_model} "
                f"(High: {float(slip.high_liquidity_slippage_pct)*100:.2f}%, "
                f"Low: {float(slip.low_liquidity_slippage_pct)*100:.2f}%)"
            )
            report_lines.append(
                f"  Market Impact: {'Enabled' if slip.market_impact_enabled else 'Disabled'}"
            )

        report_lines.append("")

        # Cost Summary
        report_lines.append(self.format_cost_summary(backtest_result))
        report_lines.append("")

        # Sample Trade Breakdowns (first 5 trades)
        if backtest_result.trades:
            report_lines.append("Sample Trade Breakdowns (First 5 Trades):")
            report_lines.append("=" * 60)
            for i, trade in enumerate(backtest_result.trades[:5]):
                trade_report = cost_analyzer.analyze_trade_costs(trade)
                report_lines.append(self.format_trade_costs(trade, trade_report))
                report_lines.append("")

        # Warnings
        if backtest_result.cost_summary:
            degradation_pct = (
                backtest_result.cost_summary.r_multiple_degradation
                / backtest_result.cost_summary.gross_avg_r_multiple
                * Decimal("100")
            )
            if degradation_pct > Decimal("10"):
                report_lines.append("⚠️  WARNING: High R-Multiple Degradation Detected! ⚠️")
                report_lines.append(f"R-multiple degradation: {degradation_pct:.1f}%")
                report_lines.append("")
                report_lines.append("Consider:")
                report_lines.append("  - Reducing position sizes to minimize market impact")
                report_lines.append("  - Using limit orders instead of market orders")
                report_lines.append("  - Trading more liquid instruments")
                report_lines.append("  - Reviewing commission structure with broker")

        report_lines.append("=" * 60)

        return "\n".join(report_lines)

    def to_json(self, backtest_result: BacktestResult) -> dict[str, Any]:
        """
        Convert backtest result to JSON for frontend visualization.

        Subtask 10.5: Structure data for charts and tables
        Subtask 10.5: Include cost summary metrics
        Subtask 10.5: Include per-trade cost data
        Subtask 10.6: Return JSON-serializable dict

        Args:
            backtest_result: Complete backtest result

        Returns:
            JSON-serializable dict with all cost data

        Example output:
            {
                "backtest_run_id": "abc-123-def",
                "total_trades": 100,
                "start_capital": 100000.00,
                "cost_summary": {
                    "total_commission": 1000.00,
                    "total_slippage": 400.00,
                    "gross_avg_r_multiple": 2.50,
                    "net_avg_r_multiple": 2.36,
                    "r_multiple_degradation": 0.14,
                    ...
                },
                "trades": [
                    {
                        "trade_id": "...",
                        "entry_commission": 5.00,
                        "exit_commission": 5.00,
                        "gross_pnl": 250.00,
                        "net_pnl": 236.00,
                        ...
                    },
                    ...
                ]
            }

        Author: Story 12.5 Subtask 10.5, 10.6
        """
        from src.backtesting.transaction_cost_analyzer import TransactionCostAnalyzer

        cost_analyzer = TransactionCostAnalyzer()

        # Build JSON structure
        result = {
            "backtest_run_id": str(backtest_result.backtest_run_id),
            "total_trades": len(backtest_result.trades),
            "start_capital": float(backtest_result.start_capital),
        }

        # Cost summary
        if backtest_result.cost_summary:
            summary = backtest_result.cost_summary
            result["cost_summary"] = {
                "total_trades": summary.total_trades,
                "total_commission_paid": float(summary.total_commission_paid),
                "total_slippage_cost": float(summary.total_slippage_cost),
                "total_transaction_costs": float(summary.total_transaction_costs),
                "avg_commission_per_trade": float(summary.avg_commission_per_trade),
                "avg_slippage_per_trade": float(summary.avg_slippage_per_trade),
                "avg_transaction_cost_per_trade": float(summary.avg_transaction_cost_per_trade),
                "cost_as_pct_of_total_pnl": float(summary.cost_as_pct_of_total_pnl),
                "gross_avg_r_multiple": float(summary.gross_avg_r_multiple),
                "net_avg_r_multiple": float(summary.net_avg_r_multiple),
                "r_multiple_degradation": float(summary.r_multiple_degradation),
                "degradation_pct": float(
                    summary.r_multiple_degradation / summary.gross_avg_r_multiple * 100
                    if summary.gross_avg_r_multiple != 0
                    else 0
                ),
            }

        # Per-trade cost data
        trades_data = []
        for trade in backtest_result.trades:
            trade_report = cost_analyzer.analyze_trade_costs(trade)
            trades_data.append(
                {
                    "trade_id": str(trade.trade_id),
                    "entry_timestamp": trade.entry_timestamp.isoformat(),
                    "exit_timestamp": trade.exit_timestamp.isoformat(),
                    "side": trade.side,
                    "quantity": trade.quantity,
                    "entry_price": float(trade.entry_price),
                    "exit_price": float(trade.exit_price),
                    "entry_commission": float(trade.entry_commission),
                    "exit_commission": float(trade.exit_commission),
                    "total_commission": float(trade_report.total_commission),
                    "entry_slippage": float(trade.entry_slippage),
                    "exit_slippage": float(trade.exit_slippage),
                    "total_slippage": float(trade_report.total_slippage),
                    "total_transaction_costs": float(trade_report.total_transaction_costs),
                    "transaction_cost_pct": float(trade_report.transaction_cost_pct),
                    "transaction_cost_r_multiple": float(trade_report.transaction_cost_r_multiple),
                    "gross_pnl": float(trade_report.gross_pnl),
                    "net_pnl": float(trade_report.net_pnl),
                    "gross_r_multiple": float(trade_report.gross_r_multiple),
                    "net_r_multiple": float(trade_report.net_r_multiple),
                }
            )

        result["trades"] = trades_data

        # Configuration
        config_data = {}
        if backtest_result.config.commission_config:
            comm = backtest_result.config.commission_config
            config_data["commission"] = {
                "type": comm.commission_type,
                "per_share": float(comm.commission_per_share),
                "broker": comm.broker_name,
                "min_commission": float(comm.min_commission),
            }
        if backtest_result.config.slippage_config:
            slip = backtest_result.config.slippage_config
            config_data["slippage"] = {
                "model": slip.slippage_model,
                "high_liquidity_pct": float(slip.high_liquidity_slippage_pct) * 100,
                "low_liquidity_pct": float(slip.low_liquidity_slippage_pct) * 100,
                "market_impact_enabled": slip.market_impact_enabled,
            }

        result["config"] = config_data

        logger.debug(
            "Backtest report JSON generated",
            backtest_run_id=str(backtest_result.backtest_run_id),
            total_trades=len(backtest_result.trades),
        )

        return result
