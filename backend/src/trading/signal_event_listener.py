"""
Signal Event Listener for Paper Trading (Story 12.8 Task 6)

Subscribes to SignalGeneratedEvent from orchestrator and routes signals
to paper trading or live trading based on configuration.

Author: Story 12.8
"""

from datetime import UTC
from decimal import Decimal

import structlog

from src.orchestrator.events import SignalGeneratedEvent
from src.trading.signal_router import SignalRouter

logger = structlog.get_logger(__name__)


class SignalEventListener:
    """
    Event listener for orchestrator signal events.

    Subscribes to SignalGeneratedEvent and routes signals to paper trading
    or live trading execution services.
    """

    def __init__(self, signal_router: SignalRouter):
        """
        Initialize signal event listener.

        Args:
            signal_router: SignalRouter instance for execution routing
        """
        self.signal_router = signal_router
        logger.info("signal_event_listener_initialized")

    async def on_signal_generated(self, event: SignalGeneratedEvent) -> None:
        """
        Handle SignalGeneratedEvent from orchestrator.

        Converts event to TradeSignal and routes to appropriate execution service.

        Args:
            event: SignalGeneratedEvent from orchestrator
        """
        try:
            # Convert event to TradeSignal
            # Note: The event contains basic signal data, but we need the full
            # TradeSignal object to execute. For now, we'll reconstruct it from
            # the event data.

            # TODO: This is a temporary solution. Ideally, the event should
            # contain the full TradeSignal object or we should fetch it from
            # a signal repository.

            from datetime import datetime
            from uuid import UUID

            from src.models.signal import (
                ConfidenceComponents,
                TargetLevels,
                TradeSignal,
            )
            from src.models.validation import (
                StageValidationResult,
                ValidationChain,
                ValidationStatus,
            )

            # Create simplified TradeSignal from event data
            # Using entry_price as market price for execution
            market_price = Decimal(str(event.entry_price))

            # Create target levels (using target_price as primary)
            targets = TargetLevels(
                primary_target=Decimal(str(event.target_price)),
                secondary_targets=[],
            )

            # Create minimal confidence components
            confidence = ConfidenceComponents(
                pattern_confidence=event.confidence_score,
                phase_confidence=event.confidence_score,
                volume_confidence=event.confidence_score,
                overall_confidence=event.confidence_score,
            )

            # Create minimal validation chain
            validation = ValidationChain(
                pattern_id=UUID(str(event.signal_id)),
                overall_status=ValidationStatus.PASS,
                validation_results=[
                    StageValidationResult(
                        stage="Risk",
                        status=ValidationStatus.PASS,
                        validator_id="ORCHESTRATOR",
                    )
                ],
            )

            # Create TradeSignal
            signal = TradeSignal(
                id=UUID(str(event.signal_id)),
                symbol=event.symbol,
                pattern_type=event.pattern_type,
                phase="C",  # Default to Phase C for now
                timeframe=event.timeframe,
                entry_price=Decimal(str(event.entry_price)),
                stop_loss=Decimal(str(event.stop_price)),
                target_levels=targets,
                position_size=Decimal(str(event.position_size)),
                notional_value=Decimal(str(event.position_size)) * market_price,
                risk_amount=Decimal(str(event.risk_amount)),
                r_multiple=Decimal(str(event.r_multiple)),
                confidence_score=event.confidence_score,
                confidence_components=confidence,
                validation_chain=validation,
                timestamp=datetime.now(UTC),
                created_at=datetime.now(UTC),
            )

            # Route signal to execution
            execution_mode = await self.signal_router.route_signal(signal, market_price)

            if execution_mode:
                logger.info(
                    "signal_routed_successfully",
                    signal_id=str(event.signal_id),
                    symbol=event.symbol,
                    execution_mode=execution_mode,
                )
            else:
                logger.warning(
                    "signal_not_routed",
                    signal_id=str(event.signal_id),
                    symbol=event.symbol,
                    reason="no_execution_mode_available",
                )

        except Exception as e:
            logger.error(
                "signal_event_handling_failed",
                signal_id=str(event.signal_id),
                symbol=event.symbol,
                error=str(e),
                error_type=type(e).__name__,
            )
            # Don't re-raise - we don't want to break the orchestrator pipeline


def register_signal_listener(event_bus, signal_router: SignalRouter) -> None:
    """
    Register signal event listener with orchestrator event bus.

    Args:
        event_bus: Orchestrator event bus instance
        signal_router: SignalRouter instance for execution routing
    """
    listener = SignalEventListener(signal_router)

    # Subscribe to SignalGeneratedEvent
    event_bus.subscribe("SignalGeneratedEvent", listener.on_signal_generated)

    logger.info("signal_listener_registered_with_event_bus")
