"""
Real-time Signal Validation Pipeline Integration (Story 19.5)

Purpose:
--------
Integrates real-time pattern detection with the 5-stage validation pipeline.
Ensures all detected patterns meet rigorous quality standards before generating signals.

The 5 validation stages are:
1. Volume Validation - Pattern-specific volume requirements
2. Phase Validation - Correct Wyckoff phase for pattern type
3. Level Validation - Price interaction with key levels
4. Risk Validation - Portfolio heat and position sizing
5. Strategy Validation - BMAD campaign rules

Key Features:
-------------
- Early Exit: Stops validation at first failure
- Detailed Rejection Tracking: Captures specific stage and reason
- Audit Trail: Maintains complete validation history
- Event Emission: Emits SignalValidatedEvent or SignalRejectedEvent

Author: Story 19.5
"""

from uuid import UUID, uuid4

import structlog

from src.models.validation import (
    ValidationChain,
    ValidationContext,
    ValidationStage,
    ValidationStatus,
)
from src.pattern_engine.events import PatternDetectedEvent
from src.signal_generator.events import (
    SignalRejectedEvent,
    SignalValidatedEvent,
    ValidationAuditEntry,
)
from src.signal_generator.validation_chain import ValidationChainOrchestrator

logger = structlog.get_logger()


class RealtimeSignalValidator:
    """
    Validates detected patterns through the 5-stage validation pipeline.

    Wraps the existing ValidationChainOrchestrator and provides event-driven
    integration for real-time pattern detection.

    Features:
    ---------
    - Converts PatternDetectedEvent to ValidationContext
    - Executes 5-stage validation chain
    - Emits SignalValidatedEvent on success
    - Emits SignalRejectedEvent on failure
    - Maintains detailed audit trail

    Parameters:
    -----------
    orchestrator : ValidationChainOrchestrator
        Validation chain with all 5 validators configured

    Example Usage:
    --------------
    >>> from src.signal_generator.validation_chain import create_default_validation_chain
    >>> orchestrator = create_default_validation_chain()
    >>> validator = RealtimeSignalValidator(orchestrator)
    >>>
    >>> # When pattern detected
    >>> pattern_event = PatternDetectedEvent(...)
    >>> result = await validator.validate_pattern(pattern_event, volume_analysis, ...)
    >>>
    >>> if isinstance(result, SignalValidatedEvent):
    ...     print(f"Signal validated: {result.signal_id}")
    ... else:
    ...     print(f"Signal rejected at {result.rejection_stage}: {result.rejection_reason}")
    """

    def __init__(self, orchestrator: ValidationChainOrchestrator) -> None:
        """
        Initialize validator with validation chain orchestrator.

        Parameters:
        -----------
        orchestrator : ValidationChainOrchestrator
            Configured validation chain with all 5 validators
        """
        self.orchestrator = orchestrator

    async def validate_pattern(
        self,
        pattern_event: PatternDetectedEvent,
        volume_analysis: dict,
        phase_info: dict | None = None,
        trading_range: dict | None = None,
        portfolio_context: dict | None = None,
        market_context: dict | None = None,
    ) -> SignalValidatedEvent | SignalRejectedEvent:
        """
        Validate a detected pattern through the 5-stage pipeline.

        Workflow:
        ---------
        1. Convert PatternDetectedEvent to ValidationContext
        2. Execute validation chain
        3. Build audit trail from validation results
        4. Emit SignalValidatedEvent or SignalRejectedEvent

        Parameters:
        -----------
        pattern_event : PatternDetectedEvent
            Pattern detected by real-time detector
        volume_analysis : dict
            Volume analysis data (REQUIRED)
        phase_info : dict | None
            Phase detection data (optional)
        trading_range : dict | None
            Trading range levels (optional)
        portfolio_context : dict | None
            Portfolio state for risk validation (optional)
        market_context : dict | None
            Market data for strategy validation (optional)

        Returns:
        --------
        SignalValidatedEvent | SignalRejectedEvent
            Validation result event with audit trail

        Example:
        --------
        >>> result = await validator.validate_pattern(
        ...     pattern_event=spring_event,
        ...     volume_analysis={"ratio": 0.5, "average": 1000000},
        ...     phase_info={"phase": "C", "duration": 15},
        ...     trading_range={"creek": 100.0, "ice": 105.0},
        ...     portfolio_context={"heat": 0.08, "positions": 3}
        ... )
        """
        signal_id = uuid4()

        logger.info(
            "realtime_validation_started",
            signal_id=str(signal_id),
            pattern_id=str(pattern_event.event_id),
            symbol=pattern_event.symbol,
            pattern_type=pattern_event.pattern_type.value,
        )

        # Convert PatternDetectedEvent to ValidationContext
        context = self._create_validation_context(
            pattern_event=pattern_event,
            volume_analysis=volume_analysis,
            phase_info=phase_info,
            trading_range=trading_range,
            portfolio_context=portfolio_context,
            market_context=market_context,
        )

        # Execute validation chain
        validation_chain: ValidationChain = await self.orchestrator.run_validation_chain(context)

        # Build audit trail
        audit_trail = self._build_audit_trail(signal_id, validation_chain)

        # Check validation result
        if validation_chain.is_valid:
            # Validation passed - emit success event
            event = SignalValidatedEvent(
                signal_id=signal_id,
                pattern_id=pattern_event.event_id,
                symbol=pattern_event.symbol,
                pattern_type=pattern_event.pattern_type.value,
                confidence=pattern_event.confidence,
                validation_metadata=self._extract_validation_metadata(validation_chain),
                audit_trail=audit_trail,
            )

            logger.info(
                "signal_validated",
                signal_id=str(signal_id),
                pattern_id=str(pattern_event.event_id),
                symbol=pattern_event.symbol,
                pattern_type=pattern_event.pattern_type.value,
                confidence=pattern_event.confidence,
            )

            return event
        else:
            # Validation failed - emit rejection event
            event = SignalRejectedEvent(
                pattern_id=pattern_event.event_id,
                symbol=pattern_event.symbol,
                pattern_type=pattern_event.pattern_type.value,
                rejection_stage=self._map_stage_to_enum(
                    validation_chain.rejection_stage or "Unknown"
                ),
                rejection_reason=validation_chain.rejection_reason or "Unknown rejection",
                rejection_details=self._extract_rejection_details(validation_chain),
                audit_trail=audit_trail,
            )

            logger.warning(
                "signal_rejected",
                pattern_id=str(pattern_event.event_id),
                symbol=pattern_event.symbol,
                pattern_type=pattern_event.pattern_type.value,
                rejection_stage=validation_chain.rejection_stage,
                rejection_reason=validation_chain.rejection_reason,
            )

            return event

    def _create_validation_context(
        self,
        pattern_event: PatternDetectedEvent,
        volume_analysis: dict,
        phase_info: dict | None,
        trading_range: dict | None,
        portfolio_context: dict | None,
        market_context: dict | None,
    ) -> ValidationContext:
        """
        Convert PatternDetectedEvent to ValidationContext.

        Parameters:
        -----------
        pattern_event : PatternDetectedEvent
            Pattern detected event
        volume_analysis : dict
            Volume analysis data
        phase_info : dict | None
            Phase information
        trading_range : dict | None
            Trading range levels
        portfolio_context : dict | None
            Portfolio state
        market_context : dict | None
            Market data

        Returns:
        --------
        ValidationContext
            Context for validation chain
        """
        # Convert pattern event to dict for pattern field
        pattern_data = {
            "id": pattern_event.event_id,
            "pattern_type": pattern_event.pattern_type.value,
            "confidence": pattern_event.confidence,
            "phase": pattern_event.phase,
            "levels": pattern_event.levels,
            "bar_data": pattern_event.bar_data,
            "metadata": pattern_event.metadata,
        }

        return ValidationContext(
            pattern=pattern_data,
            symbol=pattern_event.symbol,
            timeframe=pattern_event.metadata.get("timeframe", "unknown"),
            volume_analysis=volume_analysis,
            phase_info=phase_info,
            trading_range=trading_range,
            portfolio_context=portfolio_context,
            market_context=market_context,
        )

    def _build_audit_trail(self, signal_id: UUID, validation_chain: ValidationChain) -> list[dict]:
        """
        Build audit trail from validation chain results.

        Parameters:
        -----------
        signal_id : UUID
            Signal identifier
        validation_chain : ValidationChain
            Completed validation chain

        Returns:
        --------
        list[dict]
            List of audit entry dictionaries
        """
        audit_entries = []

        for result in validation_chain.validation_results:
            entry = ValidationAuditEntry(
                signal_id=signal_id,
                timestamp=result.timestamp,
                stage=self._map_stage_to_enum(result.stage),
                passed=result.status == ValidationStatus.PASS,
                reason=result.reason,
                input_data=result.metadata or {},
                output_data={
                    "status": result.status,  # ValidationStatus is str enum
                    "validator_id": result.validator_id,
                },
            )
            audit_entries.append(entry.model_dump())

        return audit_entries

    def _extract_validation_metadata(self, validation_chain: ValidationChain) -> dict:
        """
        Extract validation metadata from chain results.

        Parameters:
        -----------
        validation_chain : ValidationChain
            Completed validation chain

        Returns:
        --------
        dict
            Aggregated validation metadata
        """
        metadata = {
            "overall_status": validation_chain.overall_status,  # ValidationStatus is str enum
            "stages_executed": len(validation_chain.validation_results),
            "warnings": validation_chain.warnings,
        }

        # Add stage-specific metadata
        for result in validation_chain.validation_results:
            if result.metadata:
                metadata[f"{result.stage.lower()}_metadata"] = result.metadata

        return metadata

    def _extract_rejection_details(self, validation_chain: ValidationChain) -> dict:
        """
        Extract detailed rejection information.

        Parameters:
        -----------
        validation_chain : ValidationChain
            Completed validation chain

        Returns:
        --------
        dict
            Rejection details
        """
        details = {
            "rejection_stage": validation_chain.rejection_stage,
            "rejection_reason": validation_chain.rejection_reason,
            "stages_executed": len(validation_chain.validation_results),
        }

        # Find the failed stage and add its metadata
        for result in validation_chain.validation_results:
            if result.status == ValidationStatus.FAIL:
                details["failed_stage_metadata"] = result.metadata or {}
                details["validator_id"] = result.validator_id
                break

        return details

    def _map_stage_to_enum(self, stage_name: str) -> ValidationStage:
        """
        Map stage name string to ValidationStage enum.

        Parameters:
        -----------
        stage_name : str
            Stage name (e.g., "Volume", "Phase")

        Returns:
        --------
        ValidationStage
            Enum value, or ValidationStage.UNKNOWN if unrecognized
        """
        stage_map = {
            "Volume": ValidationStage.VOLUME,
            "Phase": ValidationStage.PHASE,
            "Levels": ValidationStage.LEVELS,
            "Risk": ValidationStage.RISK,
            "Strategy": ValidationStage.STRATEGY,
        }

        result = stage_map.get(stage_name)
        if result is None:
            logger.warning(
                "unknown_validation_stage_encountered",
                stage_name=stage_name,
                defaulting_to="Unknown",
            )
            return ValidationStage.UNKNOWN

        return result
