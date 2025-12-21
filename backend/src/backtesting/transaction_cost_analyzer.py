"""
Transaction Cost Analyzer for Backtesting (Story 12.5 Task 8).

Analyzes transaction costs at both trade-level and backtest-level to provide
detailed cost breakdowns and calculate gross vs net performance metrics.

AC8: Backtest report shows commission/slippage per trade
AC10: Validate realistic cost impact on R-multiples

Author: Story 12.5 Task 8
"""

from decimal import ROUND_HALF_UP, Decimal

import structlog

from src.models.backtest import (
    BacktestCostSummary,
    BacktestResult,
    BacktestTrade,
    TransactionCostReport,
)

logger = structlog.get_logger(__name__)


class TransactionCostAnalyzer:
    """
    Analyze transaction costs at trade and backtest levels.

    Provides detailed cost breakdowns showing the impact of commissions
    and slippage on trading performance, including R-multiple degradation.

    Methods:
        analyze_trade_costs: Analyze costs for a single trade
        analyze_backtest_costs: Aggregate costs across all trades

    Example:
        analyzer = TransactionCostAnalyzer()

        # Analyze single trade
        trade = BacktestTrade(
            entry_commission=Decimal("5.00"),
            exit_commission=Decimal("5.00"),
            entry_slippage=Decimal("2.00"),
            exit_slippage=Decimal("2.00"),
            gross_pnl=Decimal("250.00"),
            gross_r_multiple=Decimal("2.5"),
            ...
        )
        trade_report = analyzer.analyze_trade_costs(trade)
        # trade_report shows net_pnl = $236.00, net_r_multiple = 2.36R

        # Analyze full backtest
        backtest_result = BacktestResult(trades=[...], ...)
        cost_summary = analyzer.analyze_backtest_costs(backtest_result)
        # cost_summary shows avg costs, R-multiple degradation, etc.

    Author: Story 12.5 Task 8
    """

    def analyze_trade_costs(self, trade: BacktestTrade) -> TransactionCostReport:
        """
        Analyze transaction costs for a single trade.

        Subtask 8.2: Calculate total commission (entry + exit)
        Subtask 8.3: Calculate total slippage (entry + exit)
        Subtask 8.4: Calculate total transaction costs
        Subtask 8.5: Calculate net P&L (gross_pnl - transaction_costs)
        Subtask 8.6: Calculate net R-multiple (gross_r_multiple - transaction_cost_r_multiple)
        Subtask 8.7: Return TransactionCostReport with all metrics

        Args:
            trade: Backtest trade with commission/slippage fields populated

        Returns:
            TransactionCostReport with detailed cost breakdown

        Example:
            Trade with $10 total costs on $100 risk (1R):
                gross_pnl = $250 (2.5R)
                total_costs = $14 ($5+$5 commission, $2+$2 slippage)
                net_pnl = $236
                transaction_cost_r_multiple = 0.14R ($14 / $100 risk)
                net_r_multiple = 2.36R (2.5R - 0.14R)

        Author: Story 12.5 Subtask 8.2-8.7
        """
        # Subtask 8.2: Total commission
        total_commission = trade.entry_commission + trade.exit_commission

        # Subtask 8.3: Total slippage
        total_slippage = trade.entry_slippage + trade.exit_slippage

        # Subtask 8.4: Total transaction costs
        total_transaction_costs = total_commission + total_slippage

        # Subtask 8.5: Net P&L
        net_pnl = trade.gross_pnl - total_transaction_costs

        # Calculate transaction costs as percentage of gross P&L
        # Handle edge case where gross_pnl is zero or negative
        if trade.gross_pnl > Decimal("0"):
            transaction_cost_pct = (total_transaction_costs / trade.gross_pnl) * Decimal("100")
        else:
            transaction_cost_pct = Decimal("0")

        # Calculate transaction cost in R-multiples
        # Transaction cost R-multiple = total_costs / initial_risk
        # We can derive this from: gross_r_multiple = gross_pnl / initial_risk
        # Therefore: initial_risk = gross_pnl / gross_r_multiple
        if trade.gross_r_multiple != Decimal("0"):
            initial_risk = trade.gross_pnl / trade.gross_r_multiple
            transaction_cost_r_multiple = total_transaction_costs / initial_risk
        else:
            # Edge case: gross_r_multiple is zero (breakeven or invalid trade)
            transaction_cost_r_multiple = Decimal("0")

        # Subtask 8.6: Net R-multiple
        net_r_multiple = trade.gross_r_multiple - transaction_cost_r_multiple

        # Subtask 8.7: Create report
        # Quantize values to match Pydantic decimal_places constraints
        report = TransactionCostReport(
            trade_id=trade.trade_id,
            entry_commission=trade.entry_commission.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            exit_commission=trade.exit_commission.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            total_commission=total_commission.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            entry_slippage=trade.entry_slippage.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            exit_slippage=trade.exit_slippage.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            total_slippage=total_slippage.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            total_transaction_costs=total_transaction_costs.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            transaction_cost_pct=transaction_cost_pct.quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            ),
            transaction_cost_r_multiple=transaction_cost_r_multiple.quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            ),
            gross_pnl=trade.gross_pnl.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            net_pnl=net_pnl.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            gross_r_multiple=trade.gross_r_multiple.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            net_r_multiple=net_r_multiple.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        )

        logger.debug(
            "Trade costs analyzed",
            trade_id=str(trade.trade_id),
            total_commission=float(total_commission),
            total_slippage=float(total_slippage),
            total_transaction_costs=float(total_transaction_costs),
            gross_pnl=float(trade.gross_pnl),
            net_pnl=float(net_pnl),
            gross_r_multiple=float(trade.gross_r_multiple),
            net_r_multiple=float(net_r_multiple),
            transaction_cost_r_multiple=float(transaction_cost_r_multiple),
        )

        return report

    def analyze_backtest_costs(self, backtest_result: BacktestResult) -> BacktestCostSummary:
        """
        Analyze aggregate transaction costs across all trades in a backtest.

        Subtask 8.8: Sum all commissions across trades
        Subtask 8.8: Sum all slippage across trades
        Subtask 8.8: Calculate total transaction costs
        Subtask 8.8: Calculate average costs per trade
        Subtask 8.8: Calculate gross vs net average R-multiple
        Subtask 8.8: Calculate R-multiple degradation
        Subtask 8.8: Return BacktestCostSummary

        Args:
            backtest_result: Complete backtest result with trades

        Returns:
            BacktestCostSummary with aggregate cost metrics

        Example:
            Backtest with 100 trades:
                total_commission = $1,000
                total_slippage = $400
                total_transaction_costs = $1,400
                avg_commission_per_trade = $10
                avg_slippage_per_trade = $4
                gross_avg_r_multiple = 2.5R
                net_avg_r_multiple = 2.36R
                r_multiple_degradation = 0.14R (5.6% impact)

        Author: Story 12.5 Subtask 8.8
        """
        if not backtest_result.trades:
            logger.warning("No trades in backtest result - returning zero cost summary")
            return BacktestCostSummary(
                total_trades=0,
                total_commission_paid=Decimal("0"),
                total_slippage_cost=Decimal("0"),
                total_transaction_costs=Decimal("0"),
                avg_commission_per_trade=Decimal("0"),
                avg_slippage_per_trade=Decimal("0"),
                avg_transaction_cost_per_trade=Decimal("0"),
                cost_as_pct_of_total_pnl=Decimal("0"),
                gross_avg_r_multiple=Decimal("0"),
                net_avg_r_multiple=Decimal("0"),
                r_multiple_degradation=Decimal("0"),
            )

        total_trades = len(backtest_result.trades)

        # Sum all commissions
        total_commission_paid = sum(
            (trade.entry_commission + trade.exit_commission) for trade in backtest_result.trades
        )

        # Sum all slippage
        total_slippage_cost = sum(
            (trade.entry_slippage + trade.exit_slippage) for trade in backtest_result.trades
        )

        # Total transaction costs
        total_transaction_costs = total_commission_paid + total_slippage_cost

        # Average costs per trade
        avg_commission_per_trade = total_commission_paid / Decimal(total_trades)
        avg_slippage_per_trade = total_slippage_cost / Decimal(total_trades)
        avg_transaction_cost_per_trade = total_transaction_costs / Decimal(total_trades)

        # Calculate gross vs net average R-multiple
        total_gross_pnl = sum(trade.gross_pnl for trade in backtest_result.trades)
        total_net_pnl = total_gross_pnl - total_transaction_costs

        # Calculate cost as percentage of total P&L
        if total_gross_pnl > Decimal("0"):
            cost_as_pct_of_total_pnl = (total_transaction_costs / total_gross_pnl) * Decimal("100")
        else:
            cost_as_pct_of_total_pnl = Decimal("0")

        # Gross average R-multiple
        gross_avg_r_multiple = sum(
            trade.gross_r_multiple for trade in backtest_result.trades
        ) / Decimal(total_trades)

        # Net average R-multiple
        # Calculate by analyzing each trade's net R-multiple
        net_r_multiples = []
        for trade in backtest_result.trades:
            trade_report = self.analyze_trade_costs(trade)
            net_r_multiples.append(trade_report.net_r_multiple)

        net_avg_r_multiple = sum(net_r_multiples) / Decimal(total_trades)

        # R-multiple degradation
        r_multiple_degradation = gross_avg_r_multiple - net_avg_r_multiple

        # Quantize values to match Pydantic decimal_places constraints
        summary = BacktestCostSummary(
            total_trades=total_trades,
            total_commission_paid=total_commission_paid.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            total_slippage_cost=total_slippage_cost.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            total_transaction_costs=total_transaction_costs.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            avg_commission_per_trade=avg_commission_per_trade.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            avg_slippage_per_trade=avg_slippage_per_trade.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            avg_transaction_cost_per_trade=avg_transaction_cost_per_trade.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            cost_as_pct_of_total_pnl=cost_as_pct_of_total_pnl.quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            ),
            gross_avg_r_multiple=gross_avg_r_multiple.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            net_avg_r_multiple=net_avg_r_multiple.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            r_multiple_degradation=r_multiple_degradation.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
        )

        logger.info(
            "Backtest costs analyzed",
            total_trades=total_trades,
            total_commission_paid=float(total_commission_paid),
            total_slippage_cost=float(total_slippage_cost),
            total_transaction_costs=float(total_transaction_costs),
            avg_commission_per_trade=float(avg_commission_per_trade),
            avg_slippage_per_trade=float(avg_slippage_per_trade),
            avg_transaction_cost_per_trade=float(avg_transaction_cost_per_trade),
            cost_as_pct_of_total_pnl=float(cost_as_pct_of_total_pnl),
            gross_avg_r_multiple=float(gross_avg_r_multiple),
            net_avg_r_multiple=float(net_avg_r_multiple),
            r_multiple_degradation=float(r_multiple_degradation),
        )

        return summary
