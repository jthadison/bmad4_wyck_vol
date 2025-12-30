"""
Paper Trading Service (Story 12.8 Task 3)

Core business logic for paper trading mode including position management,
risk validation, and performance tracking.

Author: Story 12.8
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional

import structlog

from src.brokers.paper_broker_adapter import PaperBrokerAdapter
from src.models.backtest import BacktestResult
from src.models.paper_trading import PaperAccount, PaperPosition
from src.models.signal import TradeSignal
from src.repositories.paper_account_repository import PaperAccountRepository
from src.repositories.paper_position_repository import PaperPositionRepository
from src.repositories.paper_trade_repository import PaperTradeRepository
from src.trading.exceptions import (
    PaperAccountNotFoundError,
    RiskLimitExceededError,
)

logger = structlog.get_logger(__name__)


class PaperTradingService:
    """
    Service for managing paper trading operations.

    Handles position lifecycle, risk validation, and performance metrics.
    """

    def __init__(
        self,
        account_repo: PaperAccountRepository,
        position_repo: PaperPositionRepository,
        trade_repo: PaperTradeRepository,
        broker_adapter: PaperBrokerAdapter,
    ):
        """
        Initialize paper trading service.

        Args:
            account_repo: Repository for account operations
            position_repo: Repository for position operations
            trade_repo: Repository for trade operations
            broker_adapter: Mock broker for order execution
        """
        self.account_repo = account_repo
        self.position_repo = position_repo
        self.trade_repo = trade_repo
        self.broker = broker_adapter

    async def execute_signal(
        self, signal: TradeSignal, market_price: Decimal
    ) -> Optional[PaperPosition]:
        """
        Execute a trading signal in paper mode.

        Validates risk limits before placing order.

        Args:
            signal: Trading signal to execute
            market_price: Current market price

        Returns:
            PaperPosition if executed, None if rejected

        Raises:
            ValueError: If risk limits exceeded or insufficient capital
        """
        # Get account
        account = await self.account_repo.get_account()
        if not account:
            raise PaperAccountNotFoundError()

        # Calculate position risk
        position_risk_pct = self._calculate_position_risk_pct(signal, market_price, account)

        # Validate per-trade risk limit (2% max - FR18)
        if position_risk_pct > Decimal("2.0"):
            logger.warning(
                "paper_signal_rejected_risk",
                signal_id=str(signal.id),
                symbol=signal.symbol,
                position_risk_pct=float(position_risk_pct),
                limit_pct=2.0,
                reason="per_trade_risk_exceeded",
            )
            raise RiskLimitExceededError(
                limit_type="per_trade_risk",
                limit_value=Decimal("2.0"),
                actual_value=position_risk_pct,
                symbol=signal.symbol,
            )

        # Validate portfolio heat limit (10% max - FR18)
        new_heat = account.current_heat + position_risk_pct
        if new_heat > Decimal("10.0"):
            logger.warning(
                "paper_signal_rejected_heat",
                signal_id=str(signal.id),
                symbol=signal.symbol,
                current_heat=float(account.current_heat),
                new_heat=float(new_heat),
                limit_pct=10.0,
                reason="portfolio_heat_exceeded",
            )
            raise RiskLimitExceededError(
                limit_type="portfolio_heat",
                limit_value=Decimal("10.0"),
                actual_value=new_heat,
                symbol=signal.symbol,
            )

        # Place order via broker
        position = self.broker.place_order(signal, market_price, account)

        # Save position
        saved_position = await self.position_repo.save_position(position)

        # Update account
        account.current_capital -= (
            position.entry_price * position.quantity + position.commission_paid
        )
        account.current_heat = await self._calculate_current_heat(account)
        account.updated_at = datetime.now(UTC)
        await self.account_repo.update_account(account)

        logger.info(
            "paper_signal_executed",
            signal_id=str(signal.id),
            position_id=str(position.id),
            symbol=signal.symbol,
            quantity=float(position.quantity),
            entry_price=float(position.entry_price),
            position_risk_pct=float(position_risk_pct),
            new_heat=float(account.current_heat),
        )

        return saved_position

    async def update_positions(self) -> int:
        """
        Update all open positions with current market prices.

        Checks for stop/target hits and closes positions automatically.
        Called by background task on every bar.

        Returns:
            Number of positions updated
        """
        # Get all open positions
        positions = await self.position_repo.list_open_positions()

        if not positions:
            logger.debug("no_open_paper_positions")
            return 0

        logger.debug("updating_paper_positions", count=len(positions))

        # Get account
        account = await self.account_repo.get_account()
        if not account:
            logger.error("paper_account_not_found_during_update")
            return

        for position in positions:
            # TODO: Fetch current market price from MarketDataService
            # For now, use position.current_price as placeholder
            current_price = position.current_price

            # Check if stop hit
            if self.broker.check_stop_hit(position, current_price):
                logger.info(
                    "paper_stop_hit",
                    position_id=str(position.id),
                    symbol=position.symbol,
                    current_price=float(current_price),
                    stop_loss=float(position.stop_loss),
                )
                await self._close_position(position, current_price, "STOP_LOSS", account)
                continue

            # Check if target hit
            target_hit = self.broker.check_target_hit(position, current_price)
            if target_hit:
                logger.info(
                    "paper_target_hit",
                    position_id=str(position.id),
                    symbol=position.symbol,
                    current_price=float(current_price),
                    target_hit=target_hit,
                )
                await self._close_position(position, current_price, target_hit, account)
                continue

            # Update unrealized P&L
            position.current_price = current_price
            position.unrealized_pnl = self.broker.calculate_unrealized_pnl(position, current_price)
            position.updated_at = datetime.now(UTC)
            await self.position_repo.update_position(position)

        # Update account with total unrealized P&L
        await self._update_account_metrics(account)

        return len(positions)

    async def calculate_performance_metrics(self) -> dict:
        """
        Calculate comprehensive performance metrics for paper trading.

        Returns:
            Dict with win_rate, avg_r, max_drawdown, sharpe_ratio, etc.
        """
        account = await self.account_repo.get_account()
        if not account:
            return {}

        trades, total = await self.trade_repo.list_trades(limit=10000, offset=0)

        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "average_r_multiple": 0.0,
                "total_realized_pnl": 0.0,
                "max_drawdown": 0.0,
            }

        # Calculate metrics
        winning_trades = [t for t in trades if t.realized_pnl > Decimal("0")]
        losing_trades = [t for t in trades if t.realized_pnl <= Decimal("0")]

        win_rate = (len(winning_trades) / len(trades) * 100) if trades else Decimal("0")

        avg_r_multiple = (
            (sum(t.r_multiple_achieved for t in trades) / len(trades)) if trades else Decimal("0")
        )

        total_pnl = sum(t.realized_pnl for t in trades)

        return {
            "total_trades": len(trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": float(win_rate),
            "average_r_multiple": float(avg_r_multiple),
            "total_realized_pnl": float(total_pnl),
            "max_drawdown": float(account.max_drawdown),
            "current_equity": float(account.equity),
            "starting_capital": float(account.starting_capital),
            "return_pct": float(
                (account.equity - account.starting_capital) / account.starting_capital * 100
            ),
        }

    async def compare_to_backtest(self, backtest_result: BacktestResult) -> dict:
        """
        Compare paper trading performance to backtest results.

        Flags deviations > 10% as warnings, > 20% as errors.

        Args:
            backtest_result: Backtest result to compare against

        Returns:
            Dict with comparison metrics and warnings/errors
        """
        paper_metrics = await self.calculate_performance_metrics()

        # Extract backtest metrics
        backtest_metrics = {
            "win_rate": float(backtest_result.summary.get("win_rate", 0)),
            "average_r_multiple": float(backtest_result.summary.get("average_r_multiple", 0)),
            "max_drawdown": float(backtest_result.risk_metrics.get("max_drawdown", 0)),
        }

        # Calculate deltas
        deltas = {}
        warnings = []
        errors = []

        for metric in ["win_rate", "average_r_multiple", "max_drawdown"]:
            paper_value = paper_metrics.get(metric, 0)
            backtest_value = backtest_metrics.get(metric, 0)

            if backtest_value > 0:
                delta_pct = abs((paper_value - backtest_value) / backtest_value * 100)
            else:
                delta_pct = 0

            deltas[metric] = {
                "paper": paper_value,
                "backtest": backtest_value,
                "delta_pct": delta_pct,
            }

            if delta_pct > 20:
                errors.append(f"{metric}: {delta_pct:.1f}% deviation")
            elif delta_pct > 10:
                warnings.append(f"{metric}: {delta_pct:.1f}% deviation")

        status = "ERROR" if errors else "WARNING" if warnings else "OK"

        logger.info(
            "paper_backtest_comparison",
            status=status,
            warnings=warnings,
            errors=errors,
        )

        return {
            "status": status,
            "deltas": deltas,
            "warnings": warnings,
            "errors": errors,
            "paper_metrics": paper_metrics,
            "backtest_metrics": backtest_metrics,
        }

    async def validate_live_trading_eligibility(self) -> dict:
        """
        Validate if ready for live trading (3-month requirement).

        Criteria:
        - Duration >= 90 days
        - Trade count >= 20
        - Win rate > 50%
        - Avg R-multiple > 1.5R

        Returns:
            Dict with eligibility status and progress
        """
        account = await self.account_repo.get_account()
        if not account or not account.paper_trading_start_date:
            return {
                "eligible": False,
                "reason": "Paper trading not started",
                "days_completed": 0,
                "days_remaining": 90,
                "progress_pct": 0,
                "checks": {},
            }

        # Calculate duration
        now = datetime.now(UTC)
        days_completed = (now - account.paper_trading_start_date).days

        # Run checks
        checks = {
            "duration": days_completed >= 90,
            "trade_count": account.total_trades >= 20,
            "win_rate": account.win_rate > Decimal("50.0"),
            "avg_r_multiple": account.average_r_multiple > Decimal("1.5"),
        }

        eligible = all(checks.values())
        progress_pct = min(100, (days_completed / 90) * 100)

        return {
            "eligible": eligible,
            "days_completed": days_completed,
            "days_remaining": max(0, 90 - days_completed),
            "progress_pct": progress_pct,
            "checks": {k: v for k, v in checks.items()},
            "account_metrics": {
                "total_trades": account.total_trades,
                "win_rate": float(account.win_rate),
                "average_r_multiple": float(account.average_r_multiple),
            },
        }

    # Private helper methods

    def _calculate_position_risk_pct(
        self, signal: TradeSignal, market_price: Decimal, account: PaperAccount
    ) -> Decimal:
        """Calculate position risk as percentage of account equity."""
        quantity = signal.position_size
        stop_loss = signal.stop_loss

        # Risk per share
        risk_per_share = market_price - stop_loss

        # Total risk
        total_risk = risk_per_share * quantity

        # Risk as percentage of equity
        if account.equity > Decimal("0"):
            risk_pct = (total_risk / account.equity) * Decimal("100")
        else:
            risk_pct = Decimal("100")  # Treat zero equity as 100% risk

        return risk_pct

    async def _calculate_current_heat(self, account: PaperAccount) -> Decimal:
        """Calculate current portfolio heat from open positions."""
        positions = await self.position_repo.list_open_positions()

        if not positions or account.equity <= Decimal("0"):
            return Decimal("0")

        total_risk = Decimal("0")
        for pos in positions:
            risk_per_share = pos.entry_price - pos.stop_loss
            position_risk = risk_per_share * pos.quantity
            total_risk += position_risk

        heat_pct = (total_risk / account.equity) * Decimal("100")
        return heat_pct

    async def _close_position(
        self,
        position: PaperPosition,
        market_price: Decimal,
        exit_reason: str,
        account: PaperAccount,
    ) -> None:
        """Close position and update account."""
        # Create trade via broker
        trade = self.broker.close_position(position, market_price, exit_reason)

        # Save trade
        await self.trade_repo.save_trade(trade)

        # Update position status
        position.status = exit_reason
        position.current_price = market_price
        position.updated_at = datetime.now(UTC)
        await self.position_repo.update_position(position)

        # Update account
        account.current_capital += trade.exit_price * trade.quantity - trade.commission_total
        account.total_realized_pnl += trade.realized_pnl
        account.total_commission_paid += trade.commission_total
        account.total_slippage_cost += trade.slippage_total
        account.total_trades += 1

        if trade.realized_pnl > Decimal("0"):
            account.winning_trades += 1
        else:
            account.losing_trades += 1

        # Recalculate metrics
        await self._update_account_metrics(account)

    async def _update_account_metrics(self, account: PaperAccount) -> None:
        """Recalculate and update account performance metrics."""
        # Calculate win rate
        if account.total_trades > 0:
            account.win_rate = (
                Decimal(str(account.winning_trades)) / Decimal(str(account.total_trades))
            ) * Decimal("100")
        else:
            account.win_rate = Decimal("0")

        # Calculate average R-multiple
        trades, _ = await self.trade_repo.list_trades(limit=10000, offset=0)
        if trades:
            total_r = sum(t.r_multiple_achieved for t in trades)
            account.average_r_multiple = total_r / len(trades)
        else:
            account.average_r_multiple = Decimal("0")

        # Calculate total unrealized P&L from open positions
        positions = await self.position_repo.list_open_positions()
        account.total_unrealized_pnl = sum(p.unrealized_pnl for p in positions)

        # Calculate equity
        account.equity = account.current_capital + account.total_unrealized_pnl

        # Calculate current heat
        account.current_heat = await self._calculate_current_heat(account)

        # Update max drawdown (simplified - track peak equity)
        # TODO: Implement proper drawdown tracking with equity curve

        account.updated_at = datetime.now(UTC)
        await self.account_repo.update_account(account)
