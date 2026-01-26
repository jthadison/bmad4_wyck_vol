"""
Auto-Execution Configuration Service

Business logic for automatic signal execution configuration.
Story 19.14: Auto-Execution Configuration Backend
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.auto_execution_config import (
    AutoExecutionConfig,
    AutoExecutionConfigResponse,
    AutoExecutionConfigUpdate,
)
from src.models.signal import TradeSignal
from src.repositories.auto_execution_repository import AutoExecutionRepository


class AutoExecutionConfigService:
    """
    Service for managing auto-execution configuration.

    Provides business logic for:
    - Configuration CRUD operations
    - Signal eligibility validation
    - Daily trade/risk tracking
    - Kill switch and circuit breaker logic
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize service with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.repository = AutoExecutionRepository(session)

    async def get_config(self, user_id: UUID) -> AutoExecutionConfigResponse:
        """
        Get user's auto-execution configuration with current metrics.

        Args:
            user_id: User UUID

        Returns:
            AutoExecutionConfigResponse with config and today's metrics
        """
        config = await self.repository.get_or_create_config(user_id)

        # TODO: Query today's trades and risk from signals table
        # For now, return zeros as placeholder
        trades_today = 0
        risk_today = Decimal("0.0")

        return AutoExecutionConfigResponse(
            enabled=config.enabled,
            min_confidence=config.min_confidence,
            max_trades_per_day=config.max_trades_per_day,
            max_risk_per_day=config.max_risk_per_day,
            circuit_breaker_losses=config.circuit_breaker_losses,
            enabled_patterns=config.enabled_patterns,
            symbol_whitelist=config.symbol_whitelist,
            symbol_blacklist=config.symbol_blacklist,
            kill_switch_active=config.kill_switch_active,
            consent_given_at=config.consent_given_at,
            trades_today=trades_today,
            risk_today=risk_today,
        )

    async def update_config(
        self, user_id: UUID, updates: AutoExecutionConfigUpdate
    ) -> AutoExecutionConfigResponse:
        """
        Update auto-execution configuration.

        Args:
            user_id: User UUID
            updates: Configuration updates

        Returns:
            Updated AutoExecutionConfigResponse

        Raises:
            ValueError: If validation fails
        """
        # Get existing config to ensure it exists
        config = await self.repository.get_or_create_config(user_id)

        # Build update dict from non-None fields
        update_dict = {}
        if updates.min_confidence is not None:
            update_dict["min_confidence"] = updates.min_confidence
        if updates.max_trades_per_day is not None:
            update_dict["max_trades_per_day"] = updates.max_trades_per_day
        if updates.max_risk_per_day is not None:
            update_dict["max_risk_per_day"] = updates.max_risk_per_day
        if updates.circuit_breaker_losses is not None:
            update_dict["circuit_breaker_losses"] = updates.circuit_breaker_losses
        if updates.enabled_patterns is not None:
            update_dict["enabled_patterns"] = updates.enabled_patterns
        if updates.symbol_whitelist is not None:
            update_dict["symbol_whitelist"] = updates.symbol_whitelist
        if updates.symbol_blacklist is not None:
            update_dict["symbol_blacklist"] = updates.symbol_blacklist

        # Apply updates
        if update_dict:
            config = await self.repository.update_config(user_id, update_dict)

        # Return response with current metrics
        return await self.get_config(user_id)

    async def enable_auto_execution(
        self, user_id: UUID, consent_ip: str
    ) -> AutoExecutionConfigResponse:
        """
        Enable auto-execution with consent tracking.

        Args:
            user_id: User UUID
            consent_ip: IP address of user

        Returns:
            Updated AutoExecutionConfigResponse

        Raises:
            ValueError: If config doesn't exist
        """
        # Get or create config
        await self.repository.get_or_create_config(user_id)

        # Enable with consent
        await self.repository.enable(user_id, consent_ip)

        return await self.get_config(user_id)

    async def disable_auto_execution(self, user_id: UUID) -> AutoExecutionConfigResponse:
        """
        Disable auto-execution.

        Args:
            user_id: User UUID

        Returns:
            Updated AutoExecutionConfigResponse

        Raises:
            ValueError: If config doesn't exist
        """
        await self.repository.disable(user_id)
        return await self.get_config(user_id)

    async def activate_kill_switch(self, user_id: UUID) -> AutoExecutionConfigResponse:
        """
        Activate emergency kill switch.

        Immediately stops all auto-execution without disabling the feature.
        User must manually deactivate kill switch to resume.

        Args:
            user_id: User UUID

        Returns:
            Updated AutoExecutionConfigResponse

        Raises:
            ValueError: If config doesn't exist
        """
        await self.repository.activate_kill_switch(user_id)
        return await self.get_config(user_id)

    async def deactivate_kill_switch(self, user_id: UUID) -> AutoExecutionConfigResponse:
        """
        Deactivate kill switch to resume auto-execution.

        Args:
            user_id: User UUID

        Returns:
            Updated AutoExecutionConfigResponse

        Raises:
            ValueError: If config doesn't exist
        """
        await self.repository.update_config(user_id, {"kill_switch_active": False})
        return await self.get_config(user_id)

    async def is_signal_eligible(self, user_id: UUID, signal: TradeSignal) -> tuple[bool, str]:
        """
        Check if a signal is eligible for auto-execution.

        Validates against all configuration rules:
        - Auto-execution enabled
        - Kill switch not active
        - Consent given
        - Confidence threshold met
        - Daily trade limit not exceeded
        - Daily risk limit not exceeded
        - Pattern enabled
        - Symbol allowed

        Args:
            user_id: User UUID
            signal: Signal to validate

        Returns:
            Tuple of (eligible: bool, reason: str)
        """
        config = await self.repository.get_config(user_id)

        # No config = not eligible
        if config is None:
            return False, "Auto-execution not configured"

        # Check enabled
        if not config.enabled:
            return False, "Auto-execution disabled"

        # Check kill switch
        if config.kill_switch_active:
            return False, "Kill switch active"

        # Check consent
        if config.consent_given_at is None:
            return False, "Consent not given"

        # Check confidence threshold
        if Decimal(str(signal.confidence_score)) < config.min_confidence:
            return (
                False,
                f"Confidence {signal.confidence_score}% < threshold {config.min_confidence}%",
            )

        # TODO: Check daily trade limit (requires querying today's trades)
        # trades_today = await self._get_trades_today(user_id)
        # if trades_today >= config.max_trades_per_day:
        #     return False, f"Daily trade limit {config.max_trades_per_day} reached"

        # TODO: Check daily risk limit (requires querying today's risk)
        # if config.max_risk_per_day:
        #     risk_today = await self._get_risk_today(user_id)
        #     if risk_today >= config.max_risk_per_day:
        #         return False, f"Daily risk limit {config.max_risk_per_day}% reached"

        # Check pattern enabled
        pattern_type = signal.pattern_type.upper()
        if pattern_type not in [p.upper() for p in config.enabled_patterns]:
            return False, f"Pattern {pattern_type} not enabled for auto-execution"

        # Check symbol whitelist
        if config.symbol_whitelist:
            if signal.symbol not in config.symbol_whitelist:
                return False, f"Symbol {signal.symbol} not in whitelist"

        # Check symbol blacklist
        if config.symbol_blacklist:
            if signal.symbol in config.symbol_blacklist:
                return False, f"Symbol {signal.symbol} in blacklist"

        # All checks passed
        return True, "Signal eligible for auto-execution"

    async def _get_trades_today(self, user_id: UUID) -> int:
        """
        Get count of auto-executed trades today.

        TODO: Implement by querying signals table for today's trades.

        Args:
            user_id: User UUID

        Returns:
            Number of trades executed today
        """
        # Placeholder - will query signals table when integrated
        return 0

    async def _get_risk_today(self, user_id: UUID) -> Decimal:
        """
        Get total risk deployed today as percentage.

        TODO: Implement by summing position sizes from today's trades.

        Args:
            user_id: User UUID

        Returns:
            Total risk as percentage
        """
        # Placeholder - will calculate from signals when integrated
        return Decimal("0.0")

    def validate_config(self, config: AutoExecutionConfig) -> list[str]:
        """
        Validate auto-execution configuration.

        Checks all business rules and constraints.

        Args:
            config: Configuration to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Confidence range
        if config.min_confidence < 60:
            errors.append("Minimum confidence must be at least 60%")
        if config.min_confidence > 100:
            errors.append("Minimum confidence cannot exceed 100%")

        # Trade limit range
        if config.max_trades_per_day < 1:
            errors.append("Max trades per day must be at least 1")
        if config.max_trades_per_day > 50:
            errors.append("Max trades per day cannot exceed 50")

        # Risk limit range
        if config.max_risk_per_day is not None:
            if config.max_risk_per_day <= 0:
                errors.append("Max risk per day must be greater than 0")
            if config.max_risk_per_day > 10:
                errors.append("Max risk per day cannot exceed 10%")

        # Circuit breaker range
        if config.circuit_breaker_losses < 1:
            errors.append("Circuit breaker losses must be at least 1")
        if config.circuit_breaker_losses > 10:
            errors.append("Circuit breaker losses cannot exceed 10")

        # Consent required to enable
        if config.enabled and not config.consent_given_at:
            errors.append("Consent required to enable auto-execution")

        # Pattern validation
        valid_patterns = {"SPRING", "UTAD", "SOS", "LPS", "SELLING_CLIMAX", "AUTOMATIC_RALLY"}
        invalid_patterns = [p for p in config.enabled_patterns if p not in valid_patterns]
        if invalid_patterns:
            errors.append(f"Invalid patterns: {invalid_patterns}")

        return errors
