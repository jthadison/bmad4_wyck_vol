"""
Auto-Execution Engine

Evaluates approved signals against user configuration rules and
automatically executes qualifying signals without manual intervention.

Story 19.16: Auto-Execution Engine

Flow:
1. Signal approved → Check auto-execution eligibility
2. Run all rule checks (confidence, pattern, symbol, limits)
3. If all pass → Auto-execute via paper trading
4. If any fail → Route to manual approval queue
5. Log and notify user of outcome
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID

import structlog

from src.models.auto_execution import (
    AutoExecutionBypassReason,
    AutoExecutionResult,
    CheckResult,
    ExecutionResult,
)
from src.models.auto_execution_config import AutoExecutionConfig
from src.models.signal import TradeSignal
from src.services.daily_counters import DailyCounters

if TYPE_CHECKING:
    from src.repositories.auto_execution_repository import AutoExecutionRepository
    from src.services.signal_notification_service import SignalNotificationService
    from src.trading.paper_trading_service import PaperTradingService

logger = structlog.get_logger(__name__)


class AutoExecutionEngine:
    """
    Engine for evaluating and executing signals automatically.

    Implements the rule evaluation chain:
    1. Auto-execution enabled?
    2. Kill switch inactive?
    3. Confidence threshold met?
    4. Pattern enabled?
    5. Symbol in whitelist (if configured)?
    6. Symbol not in blacklist?
    7. Daily trade limit OK?
    8. Daily risk limit OK?

    If all pass, executes via paper trading and notifies user.
    If any fail, routes to manual approval queue.
    """

    def __init__(
        self,
        config_repository: "AutoExecutionRepository",
        daily_counters: DailyCounters,
        paper_trading_service: Optional["PaperTradingService"] = None,
        notification_service: Optional["SignalNotificationService"] = None,
    ):
        """
        Initialize AutoExecutionEngine.

        Args:
            config_repository: Repository for auto-execution config
            daily_counters: Redis-based daily counters service
            paper_trading_service: Paper trading execution service
            notification_service: Signal notification delivery service
        """
        self.config_repo = config_repository
        self.counters = daily_counters
        self.paper_trading = paper_trading_service
        self.notification_service = notification_service

    async def evaluate_signal(
        self,
        user_id: UUID,
        signal: TradeSignal,
    ) -> AutoExecutionResult:
        """
        Evaluate if a signal qualifies for auto-execution.

        Runs all rule checks in sequence. Returns immediately on first failure.

        Args:
            user_id: User UUID
            signal: Approved signal to evaluate

        Returns:
            AutoExecutionResult indicating auto-execute or route to queue
        """
        # Get user's config
        config = await self.config_repo.get_config(user_id)

        if config is None:
            return AutoExecutionResult(
                auto_execute=False,
                reason="Auto-execution not configured",
                route_to_queue=True,
                bypass_reason=AutoExecutionBypassReason.DISABLED,
            )

        # Extract risk percentage from signal
        signal_risk_pct = self._extract_risk_percentage(signal)

        # Run checks in order
        checks = [
            ("enabled", self._check_enabled(config)),
            ("kill_switch", self._check_kill_switch(config)),
            ("consent", self._check_consent(config)),
            ("confidence", self._check_confidence(config, signal)),
            ("pattern", self._check_pattern(config, signal)),
            ("whitelist", self._check_symbol_whitelist(config, signal)),
            ("blacklist", self._check_symbol_blacklist(config, signal)),
            ("trade_limit", await self._check_daily_trade_limit(config, user_id)),
            ("risk_limit", await self._check_daily_risk_limit(config, user_id, signal_risk_pct)),
        ]

        for check_name, result in checks:
            if not result.passed:
                logger.info(
                    "auto_execution_bypassed",
                    user_id=str(user_id),
                    signal_id=str(signal.id),
                    symbol=signal.symbol,
                    check_failed=check_name,
                    reason=result.reason,
                )
                return AutoExecutionResult(
                    auto_execute=False,
                    reason=result.reason,
                    route_to_queue=True,
                    bypass_reason=self._map_check_to_bypass_reason(check_name),
                )

        # All checks passed
        logger.info(
            "auto_execution_approved",
            user_id=str(user_id),
            signal_id=str(signal.id),
            symbol=signal.symbol,
            pattern_type=signal.pattern_type,
            confidence=signal.confidence_score,
        )

        return AutoExecutionResult(
            auto_execute=True,
            reason=None,
            route_to_queue=False,
        )

    async def execute_signal(
        self,
        user_id: UUID,
        signal: TradeSignal,
    ) -> ExecutionResult:
        """
        Execute a signal via paper trading.

        Updates daily counters and sends notification on success.

        Args:
            user_id: User UUID
            signal: Signal to execute

        Returns:
            ExecutionResult with position details or error
        """
        if not self.paper_trading:
            return ExecutionResult(
                success=False,
                error="Paper trading service not available",
            )

        try:
            # Execute via paper trading
            # Use entry price as market price (paper trading)
            position = await self.paper_trading.execute_signal(
                signal=signal,
                market_price=signal.entry_price,
            )

            if position is None:
                return ExecutionResult(
                    success=False,
                    error="Position creation failed",
                )

            # Update daily counters
            await self.counters.increment_trades(user_id)

            signal_risk_pct = self._extract_risk_percentage(signal)
            await self.counters.add_risk(user_id, signal_risk_pct)

            # Log auto-execution
            logger.info(
                "auto_execution_completed",
                user_id=str(user_id),
                signal_id=str(signal.id),
                position_id=str(position.id),
                symbol=signal.symbol,
                pattern_type=signal.pattern_type,
                entry_price=float(position.entry_price),
                quantity=float(position.quantity),
                auto_executed=True,
            )

            # Send notification
            await self._notify_auto_execution(user_id, signal, position)

            return ExecutionResult(
                success=True,
                position_id=position.id,
                entry_price=position.entry_price,
                executed_at=datetime.now(UTC),
            )

        except Exception as e:
            logger.error(
                "auto_execution_failed",
                user_id=str(user_id),
                signal_id=str(signal.id),
                error=str(e),
                exc_info=True,
            )
            return ExecutionResult(
                success=False,
                error=str(e),
            )

    async def evaluate_and_execute(
        self,
        user_id: UUID,
        signal: TradeSignal,
    ) -> tuple[AutoExecutionResult, Optional[ExecutionResult]]:
        """
        Evaluate signal and execute if eligible.

        Convenience method that combines evaluate and execute.

        Args:
            user_id: User UUID
            signal: Approved signal

        Returns:
            Tuple of (AutoExecutionResult, ExecutionResult or None)
        """
        eval_result = await self.evaluate_signal(user_id, signal)

        if not eval_result.auto_execute:
            return eval_result, None

        exec_result = await self.execute_signal(user_id, signal)
        return eval_result, exec_result

    # =========================================================================
    # Rule Check Methods
    # =========================================================================

    def _check_enabled(self, config: AutoExecutionConfig) -> CheckResult:
        """Check if auto-execution is enabled."""
        if not config.enabled:
            return CheckResult(passed=False, reason="Auto-execution disabled")
        return CheckResult(passed=True)

    def _check_kill_switch(self, config: AutoExecutionConfig) -> CheckResult:
        """Check if kill switch is inactive."""
        if config.kill_switch_active:
            return CheckResult(passed=False, reason="Kill switch active")
        return CheckResult(passed=True)

    def _check_consent(self, config: AutoExecutionConfig) -> CheckResult:
        """Check if consent has been given."""
        if config.consent_given_at is None:
            return CheckResult(passed=False, reason="Consent not given")
        return CheckResult(passed=True)

    def _check_confidence(self, config: AutoExecutionConfig, signal: TradeSignal) -> CheckResult:
        """Check if signal meets confidence threshold."""
        signal_confidence = Decimal(str(signal.confidence_score))
        threshold = config.min_confidence

        if signal_confidence < threshold:
            return CheckResult(
                passed=False,
                reason=f"Confidence {signal.confidence_score}% below threshold {threshold}%",
            )
        return CheckResult(passed=True)

    def _check_pattern(self, config: AutoExecutionConfig, signal: TradeSignal) -> CheckResult:
        """Check if pattern type is enabled for auto-execution."""
        pattern_type = signal.pattern_type.upper()
        enabled_patterns = [p.upper() for p in config.enabled_patterns]

        if pattern_type not in enabled_patterns:
            return CheckResult(
                passed=False,
                reason=f"Pattern {pattern_type} not enabled for auto-execution",
            )
        return CheckResult(passed=True)

    def _check_symbol_whitelist(
        self, config: AutoExecutionConfig, signal: TradeSignal
    ) -> CheckResult:
        """Check if symbol is in whitelist (if whitelist is configured)."""
        if not config.symbol_whitelist:
            # No whitelist = all symbols allowed
            return CheckResult(passed=True)

        if signal.symbol not in config.symbol_whitelist:
            return CheckResult(
                passed=False,
                reason=f"Symbol {signal.symbol} not in whitelist",
            )
        return CheckResult(passed=True)

    def _check_symbol_blacklist(
        self, config: AutoExecutionConfig, signal: TradeSignal
    ) -> CheckResult:
        """Check if symbol is NOT in blacklist."""
        if not config.symbol_blacklist:
            # No blacklist = no symbols blocked
            return CheckResult(passed=True)

        if signal.symbol in config.symbol_blacklist:
            return CheckResult(
                passed=False,
                reason=f"Symbol {signal.symbol} is blacklisted",
            )
        return CheckResult(passed=True)

    async def _check_daily_trade_limit(
        self, config: AutoExecutionConfig, user_id: UUID
    ) -> CheckResult:
        """Check if daily trade limit allows another execution."""
        trades_today = await self.counters.get_trades_today(user_id)

        if trades_today >= config.max_trades_per_day:
            return CheckResult(
                passed=False,
                reason=f"Daily trade limit reached ({trades_today}/{config.max_trades_per_day})",
            )
        return CheckResult(passed=True)

    async def _check_daily_risk_limit(
        self,
        config: AutoExecutionConfig,
        user_id: UUID,
        signal_risk_pct: Decimal,
    ) -> CheckResult:
        """Check if daily risk limit allows this trade."""
        if config.max_risk_per_day is None:
            # No risk limit configured
            return CheckResult(passed=True)

        risk_today = await self.counters.get_risk_today(user_id)
        projected_risk = risk_today + signal_risk_pct

        if projected_risk > config.max_risk_per_day:
            return CheckResult(
                passed=False,
                reason=f"Daily risk limit exceeded ({risk_today}% + {signal_risk_pct}% > {config.max_risk_per_day}%)",
            )
        return CheckResult(passed=True)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _extract_risk_percentage(self, signal: TradeSignal) -> Decimal:
        """
        Extract risk percentage from signal.

        Looks in validation chain metadata or calculates from risk_amount.

        Args:
            signal: TradeSignal

        Returns:
            Risk percentage (e.g., 1.5 for 1.5%)
        """
        # Try to get from validation chain
        for result in signal.validation_chain.validation_results:
            if result.stage == "Risk" and result.metadata:
                if "risk_percentage" in result.metadata:
                    return Decimal(str(result.metadata["risk_percentage"]))

        # Default fallback - assume 1.5% if not found
        return Decimal("1.5")

    def _map_check_to_bypass_reason(self, check_name: str) -> AutoExecutionBypassReason:
        """Map check name to bypass reason enum."""
        mapping = {
            "enabled": AutoExecutionBypassReason.DISABLED,
            "kill_switch": AutoExecutionBypassReason.KILL_SWITCH,
            "consent": AutoExecutionBypassReason.NO_CONSENT,
            "confidence": AutoExecutionBypassReason.CONFIDENCE_TOO_LOW,
            "pattern": AutoExecutionBypassReason.PATTERN_NOT_ENABLED,
            "whitelist": AutoExecutionBypassReason.SYMBOL_NOT_IN_WHITELIST,
            "blacklist": AutoExecutionBypassReason.SYMBOL_BLACKLISTED,
            "trade_limit": AutoExecutionBypassReason.DAILY_TRADE_LIMIT,
            "risk_limit": AutoExecutionBypassReason.DAILY_RISK_LIMIT,
        }
        return mapping.get(check_name, AutoExecutionBypassReason.DISABLED)

    async def _notify_auto_execution(
        self,
        user_id: UUID,
        signal: TradeSignal,
        position,
    ) -> None:
        """
        Send notification about auto-execution.

        Args:
            user_id: User UUID
            signal: Executed signal
            position: Opened position
        """
        if not self.notification_service:
            logger.debug("notification_service_not_available")
            return

        try:
            # Use the notification service to send auto-execution notification
            # The notification service broadcasts via WebSocket
            await self.notification_service.notify_signal_approved(signal)

            logger.info(
                "auto_execution_notification_sent",
                user_id=str(user_id),
                signal_id=str(signal.id),
                symbol=signal.symbol,
                pattern_type=signal.pattern_type,
            )
        except Exception as e:
            logger.error(
                "auto_execution_notification_failed",
                user_id=str(user_id),
                signal_id=str(signal.id),
                error=str(e),
            )

    async def get_daily_status(self, user_id: UUID) -> dict:
        """
        Get current daily execution status for a user.

        Args:
            user_id: User UUID

        Returns:
            Dict with trades_today, risk_today, limits
        """
        config = await self.config_repo.get_config(user_id)
        counters = await self.counters.get_snapshot(user_id)

        return {
            "trades_today": counters.trades_today,
            "risk_today": float(counters.risk_today),
            "max_trades_per_day": config.max_trades_per_day if config else 10,
            "max_risk_per_day": float(config.max_risk_per_day)
            if config and config.max_risk_per_day
            else None,
            "date": counters.date,
        }
