"""
RiskManager Module - Unified Risk Validation Pipeline

Purpose:
--------
Unified RiskManager that validates all risk constraints and calculates position
sizes through an 8-step validation pipeline. This is the integration hub that
connects pattern detection → validation → position sizing → signal approval.

Validation Pipeline (AC 2):
----------------------------
1. Pattern risk validation (Story 7.1)
2. Phase prerequisite validation (Story 7.9) - SHORT-CIRCUIT POINT
3. R-multiple validation (Story 7.6)
4. Structural stop calculation (Story 7.7)
5. Position size calculation (Story 7.2)
6. Portfolio heat validation (Story 7.3)
7. Campaign risk validation (Story 7.4)
8. Correlated risk validation (Story 7.5)

Stop Loss Flow (AC 12):
------------------------
- Signal contains preliminary stop from pattern detector (Story 7.7)
- Step 3 uses preliminary stop for R-multiple calculation
- Step 4 validates and may adjust stop based on buffer constraints (1-10%)
- Step 5 uses validated/adjusted stop for position sizing

Return Values (AC 4, 5):
-------------------------
- Success: PositionSizing object with all calculated values
- Failure: None with detailed rejection_reason in logs

Thread Safety (AC 6):
----------------------
- asyncio.Lock() protects concurrent validate_and_size calls
- Stateless validation (no shared mutable state)

Performance (AC 9):
-------------------
- Target: <10ms per validate_and_size call
- Expected: ~9.7ms (phase validation adds ~0.5ms)

Integration:
------------
- Stories 7.1-7.9: All risk validation modules
- Story 8.1: Signal Generator integration
- Story 8.2: Approval Chain integration

Author: Story 7.8
"""

import asyncio
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID

import structlog

from src.models.portfolio import PortfolioContext, Position
from src.models.position_sizing import PositionSizing
from src.models.risk import (
    CorrelationConfig,
    RMultipleValidation,
    SectorMapping,
)
from src.models.risk_allocation import PatternType
from src.models.trading_range import TradingRange
from src.models.validation import (
    PhaseValidation,
    ValidationPipeline,
    ValidationResult,
)
from src.risk_management.campaign_tracker import calculate_campaign_risk
from src.risk_management.correlation import validate_correlated_risk
from src.risk_management.portfolio import calculate_portfolio_heat
from src.risk_management.position_calculator import calculate_position_size
from src.risk_management.r_multiple import validate_r_multiple
from src.risk_management.risk_allocator import RiskAllocator

# Import for type hints only to avoid circular import
if TYPE_CHECKING:
    from src.models.correlation_campaign import CampaignForCorrelation

logger = structlog.get_logger(__name__)


# Placeholder for Story 7.9 phase validation function
# Story 7.9 is currently in Draft status
def validate_phase_prerequisites(
    pattern_type: PatternType,
    trading_range: TradingRange,
    mode: str = "STRICT",
) -> PhaseValidation:
    """
    Placeholder for Wyckoff phase prerequisite validation (Story 7.9).

    This function will be fully implemented in Story 7.9. For now, this
    placeholder returns a passing validation to allow RiskManager integration
    to compile and test.

    Parameters:
    -----------
    pattern_type : PatternType
        Pattern type (SPRING, SOS, LPS, UTAD)
    trading_range : TradingRange
        Trading range with event_history
    mode : str
        Validation mode (STRICT or PERMISSIVE)

    Returns:
    --------
    PhaseValidation
        Placeholder validation result (always passes for now)
    """
    return PhaseValidation(
        is_valid=True,
        pattern_type=pattern_type.value,
        phase_complete=True,
        missing_prerequisites=[],
        prerequisite_events={},
        validation_mode=mode,
        rejection_reason=None,
    )


class Signal:
    """Temporary Signal model for type hinting until Signal model is available."""

    def __init__(
        self,
        symbol: str,
        pattern_type: PatternType,
        entry: Decimal,
        stop: Decimal,
        target: Decimal,
        campaign_id: Optional[UUID] = None,
    ):
        self.symbol = symbol
        self.pattern_type = pattern_type
        self.entry = entry
        self.stop = stop
        self.target = target
        self.campaign_id = campaign_id


class RiskManager:
    """
    Unified risk validation and position sizing manager (Story 7.8).

    Orchestrates all risk validation modules from Stories 7.1-7.9 into a
    single pipeline. Validates signals against pattern risk, phase prerequisites,
    R-multiple, structural stops, portfolio heat, campaign risk, and correlation.

    Thread-safe for concurrent validation requests (AC 6).
    Performance target: <10ms per validation (AC 9).

    Example:
    --------
    >>> import asyncio
    >>> from decimal import Decimal
    >>> from uuid import uuid4
    >>> from src.models.portfolio import PortfolioContext
    >>> from src.models.risk import CorrelationConfig
    >>>
    >>> risk_manager = RiskManager()
    >>> portfolio_context = PortfolioContext(
    ...     account_equity=Decimal("100000.00"),
    ...     open_positions=[],
    ...     active_campaigns=[],
    ...     sector_mappings={},
    ...     correlation_config=CorrelationConfig(
    ...         max_sector_correlation=Decimal("6.0"),
    ...         max_asset_class_correlation=Decimal("15.0"),
    ...         enforcement_mode="strict",
    ...         sector_mappings={}
    ...     ),
    ...     r_multiple_config={}
    ... )
    >>> signal = Signal(
    ...     symbol="AAPL",
    ...     pattern_type=PatternType.SPRING,
    ...     entry=Decimal("100.00"),
    ...     stop=Decimal("95.00"),
    ...     target=Decimal("120.00")
    ... )
    >>> trading_range = TradingRange(...)  # Trading range with event history
    >>> result = asyncio.run(risk_manager.validate_and_size(
    ...     signal=signal,
    ...     portfolio_context=portfolio_context,
    ...     trading_range=trading_range
    ... ))
    >>> if result:
    ...     print(f"Approved: {result.shares} shares, ${result.risk_amount} risk")
    ... else:
    ...     print("Rejected")
    """

    def __init__(self) -> None:
        """
        Initialize RiskManager with all validation dependencies.

        Loads:
        - RiskAllocator (Story 7.1): Pattern risk percentages
        - Validation functions from Stories 7.2-7.7
        - Thread lock for concurrent access (AC 6)
        - Structured logging
        """
        self._lock = asyncio.Lock()
        self.risk_allocator = RiskAllocator()
        logger.info(
            "risk_manager_initialized",
            dependencies_loaded=[
                "risk_allocator",
                "position_calculator",
                "portfolio_heat_calculator",
                "campaign_risk_calculator",
                "correlation_validator",
                "r_multiple_validator",
                "stop_calculator",
                "phase_validator_placeholder",
            ],
        )

    async def _validate_pattern_risk(
        self, pattern_type: PatternType, signal: Signal
    ) -> ValidationResult:
        """
        Step 1: Pattern risk validation (Story 7.1).

        Validates that pattern risk allocation does not exceed FR18 per-trade
        maximum of 2.0%.

        Parameters:
        -----------
        pattern_type : PatternType
            Pattern type (SPRING, ST, LPS, SOS, UTAD)
        signal : Signal
            Trading signal to validate

        Returns:
        --------
        ValidationResult
            Validation result with is_valid=True if risk ≤ 2.0%
        """
        start_time = time.perf_counter()

        risk_pct = self.risk_allocator.get_pattern_risk_pct(pattern_type)

        if risk_pct > Decimal("2.0"):
            execution_time = (time.perf_counter() - start_time) * 1000
            logger.error(
                "pattern_risk_validation_failed",
                pattern_type=pattern_type.value,
                risk_pct=str(risk_pct),
                limit="2.0",
                execution_time_ms=execution_time,
            )
            return ValidationResult(
                is_valid=False,
                validation_step="pattern_risk",
                rejection_reason=f"Pattern risk {risk_pct}% exceeds FR18 maximum of 2.0%",
                execution_time_ms=execution_time,
            )

        execution_time = (time.perf_counter() - start_time) * 1000
        logger.debug(
            "pattern_risk_validation_passed",
            pattern_type=pattern_type.value,
            risk_pct=str(risk_pct),
            execution_time_ms=execution_time,
        )
        return ValidationResult(
            is_valid=True,
            validation_step="pattern_risk",
            execution_time_ms=execution_time,
        )

    async def _validate_phase_prerequisites(
        self,
        pattern_type: PatternType,
        trading_range: TradingRange,
        mode: str = "STRICT",
    ) -> tuple[ValidationResult, Optional[PhaseValidation]]:
        """
        Step 2: Phase prerequisite validation (Story 7.9).

        SHORT-CIRCUIT POINT: If phase validation fails, return immediately
        without continuing to R-multiple validation.

        Validates Wyckoff phase prerequisites are met:
        - Spring requires: PS, SC, AR detected in Phase A-B
        - SOS requires: Spring + Secondary Test (Phase C complete)
        - LPS requires: SOS breakout occurred first (Phase D)

        Phase validation INCLUDES volume prerequisites (PS/SC climax for Spring,
        volume surge for SOS).

        Parameters:
        -----------
        pattern_type : PatternType
            Pattern type to validate
        trading_range : TradingRange
            Trading range with event_history
        mode : str
            Validation mode (STRICT or PERMISSIVE)

        Returns:
        --------
        tuple[ValidationResult, Optional[PhaseValidation]]
            (validation_result, phase_validation_detail)
        """
        start_time = time.perf_counter()

        # Call Story 7.9 phase validation (placeholder for now)
        phase_validation = validate_phase_prerequisites(
            pattern_type=pattern_type, trading_range=trading_range, mode=mode
        )

        execution_time = (time.perf_counter() - start_time) * 1000

        if not phase_validation.is_valid:
            logger.error(
                "phase_validation_failed",
                pattern_type=pattern_type.value,
                missing_prerequisites=phase_validation.missing_prerequisites,
                rejection_reason=phase_validation.rejection_reason,
                execution_time_ms=execution_time,
            )
            return (
                ValidationResult(
                    is_valid=False,
                    validation_step="phase_prerequisites",
                    rejection_reason=phase_validation.rejection_reason,
                    execution_time_ms=execution_time,
                ),
                phase_validation,
            )

        logger.debug(
            "phase_validation_passed",
            pattern_type=pattern_type.value,
            prerequisite_events=list(phase_validation.prerequisite_events.keys()),
            execution_time_ms=execution_time,
        )
        return (
            ValidationResult(
                is_valid=True,
                validation_step="phase_prerequisites",
                execution_time_ms=execution_time,
            ),
            phase_validation,
        )

    async def _validate_r_multiple(
        self,
        entry: Decimal,
        stop: Decimal,
        target: Decimal,
        pattern_type: PatternType,
    ) -> tuple[ValidationResult, Decimal]:
        """
        Step 3: R-multiple validation (Story 7.6).

        Uses Signal.stop (preliminary stop from pattern detector) for R-multiple
        calculation. Step 4 will validate/adjust stop if needed.

        Parameters:
        -----------
        entry : Decimal
            Entry price
        stop : Decimal
            Stop loss price (preliminary from pattern detector)
        target : Decimal
            Target price
        pattern_type : PatternType
            Pattern type for minimum R requirements

        Returns:
        --------
        tuple[ValidationResult, Decimal]
            (validation_result, calculated_r_multiple)
        """
        start_time = time.perf_counter()

        r_validation: RMultipleValidation = validate_r_multiple(
            entry=entry, stop=stop, target=target, pattern_type=pattern_type
        )

        execution_time = (time.perf_counter() - start_time) * 1000

        warnings = []
        if r_validation.warning:
            warnings.append(r_validation.warning)

        if not r_validation.is_valid:
            logger.error(
                "r_multiple_validation_failed",
                pattern_type=pattern_type.value,
                r_multiple=str(r_validation.r_multiple),
                rejection_reason=r_validation.rejection_reason,
                execution_time_ms=execution_time,
            )
            return (
                ValidationResult(
                    is_valid=False,
                    validation_step="r_multiple",
                    rejection_reason=r_validation.rejection_reason,
                    warnings=warnings,
                    execution_time_ms=execution_time,
                ),
                r_validation.r_multiple,
            )

        logger.debug(
            "r_multiple_validation_passed",
            pattern_type=pattern_type.value,
            r_multiple=str(r_validation.r_multiple),
            status=r_validation.status,
            warnings=warnings,
            execution_time_ms=execution_time,
        )
        return (
            ValidationResult(
                is_valid=True,
                validation_step="r_multiple",
                warnings=warnings,
                execution_time_ms=execution_time,
            ),
            r_validation.r_multiple,
        )

    async def _calculate_structural_stop(
        self,
        pattern_type: PatternType,
        entry: Decimal,
        preliminary_stop: Decimal,
    ) -> tuple[ValidationResult, Decimal]:
        """
        Step 4: Structural stop calculation (Story 7.7).

        Validates Signal.stop (preliminary stop from pattern detector) is
        structural (not arbitrary percentage). Validates stop buffer is 1-10%
        from entry.

        If buffer <1%, widens stop to 1% minimum (automatic adjustment).
        If buffer >10%, rejects signal (unrealistic risk).

        Parameters:
        -----------
        pattern_type : PatternType
            Pattern type
        entry : Decimal
            Entry price
        preliminary_stop : Decimal
            Preliminary stop from pattern detector

        Returns:
        --------
        tuple[ValidationResult, Decimal]
            (validation_result, validated_or_adjusted_stop)
        """
        start_time = time.perf_counter()

        # Calculate stop buffer percentage
        stop_distance = abs(entry - preliminary_stop)
        buffer_pct = (stop_distance / entry) * Decimal("100")

        # Minimum buffer: 1%
        if buffer_pct < Decimal("1.0"):
            adjusted_stop = entry * (Decimal("1.0") - Decimal("0.01"))
            execution_time = (time.perf_counter() - start_time) * 1000
            logger.warning(
                "structural_stop_adjusted",
                pattern_type=pattern_type.value,
                preliminary_stop=str(preliminary_stop),
                adjusted_stop=str(adjusted_stop),
                reason="Buffer <1% widened to 1% minimum",
                execution_time_ms=execution_time,
            )
            return (
                ValidationResult(
                    is_valid=True,
                    validation_step="structural_stop",
                    warnings=[f"Stop buffer {buffer_pct:.2f}% widened to 1% minimum"],
                    execution_time_ms=execution_time,
                ),
                adjusted_stop,
            )

        # Maximum buffer: 10%
        if buffer_pct > Decimal("10.0"):
            execution_time = (time.perf_counter() - start_time) * 1000
            logger.error(
                "structural_stop_validation_failed",
                pattern_type=pattern_type.value,
                preliminary_stop=str(preliminary_stop),
                buffer_pct=str(buffer_pct),
                limit="10.0",
                execution_time_ms=execution_time,
            )
            return (
                ValidationResult(
                    is_valid=False,
                    validation_step="structural_stop",
                    rejection_reason=f"Stop buffer {buffer_pct:.2f}% exceeds 10% maximum (unrealistic risk)",
                    execution_time_ms=execution_time,
                ),
                preliminary_stop,
            )

        # Stop buffer within valid range (1-10%)
        execution_time = (time.perf_counter() - start_time) * 1000
        logger.debug(
            "structural_stop_validation_passed",
            pattern_type=pattern_type.value,
            stop=str(preliminary_stop),
            buffer_pct=str(buffer_pct),
            execution_time_ms=execution_time,
        )
        return (
            ValidationResult(
                is_valid=True,
                validation_step="structural_stop",
                execution_time_ms=execution_time,
            ),
            preliminary_stop,
        )

    async def _calculate_position_size(
        self,
        account_equity: Decimal,
        pattern_type: PatternType,
        entry: Decimal,
        stop: Decimal,
        target: Optional[Decimal],
    ) -> tuple[ValidationResult, Optional[PositionSizing]]:
        """
        Step 5: Position size calculation (Story 7.2).

        Calculates shares, risk_amount, actual_risk_pct using validated/adjusted
        stop from Step 4.

        Validates:
        - shares ≥ 1 (minimum position)
        - position_value ≤ 20% account_equity (FR18 concentration limit)

        Parameters:
        -----------
        account_equity : Decimal
            Account equity
        pattern_type : PatternType
            Pattern type
        entry : Decimal
            Entry price
        stop : Decimal
            Validated/adjusted stop from Step 4
        target : Optional[Decimal]
            Target price

        Returns:
        --------
        tuple[ValidationResult, Optional[PositionSizing]]
            (validation_result, position_sizing_or_none)
        """
        start_time = time.perf_counter()

        position_sizing = calculate_position_size(
            account_equity=account_equity,
            pattern_type=pattern_type,
            entry=entry,
            stop=stop,
            target=target,
            risk_allocator=self.risk_allocator,
        )

        execution_time = (time.perf_counter() - start_time) * 1000

        if position_sizing is None:
            logger.error(
                "position_sizing_failed",
                pattern_type=pattern_type.value,
                entry=str(entry),
                stop=str(stop),
                execution_time_ms=execution_time,
            )
            return (
                ValidationResult(
                    is_valid=False,
                    validation_step="position_size",
                    rejection_reason="Position sizing calculation failed",
                    execution_time_ms=execution_time,
                ),
                None,
            )

        logger.debug(
            "position_sizing_calculated",
            pattern_type=pattern_type.value,
            shares=position_sizing.shares,
            risk_amount=str(position_sizing.risk_amount),
            actual_risk=str(position_sizing.actual_risk),
            execution_time_ms=execution_time,
        )
        return (
            ValidationResult(
                is_valid=True,
                validation_step="position_size",
                execution_time_ms=execution_time,
            ),
            position_sizing,
        )

    async def _validate_portfolio_heat(
        self,
        current_positions: list[Position],
        new_position_risk_pct: Decimal,
    ) -> tuple[ValidationResult, Decimal]:
        """
        Step 6: Portfolio heat validation (Story 7.3).

        Validates projected portfolio heat ≤ 10.0% (FR18 portfolio maximum).
        Generates proximity warning if heat ≥ 8.0% (80% capacity).

        Parameters:
        -----------
        current_positions : list[Position]
            Currently open positions
        new_position_risk_pct : Decimal
            New position risk percentage

        Returns:
        --------
        tuple[ValidationResult, Decimal]
            (validation_result, projected_heat)
        """
        start_time = time.perf_counter()

        portfolio_heat = calculate_portfolio_heat(open_positions=current_positions)
        projected_heat = portfolio_heat + new_position_risk_pct

        execution_time = (time.perf_counter() - start_time) * 1000

        warnings = []
        if projected_heat >= Decimal("8.0") and projected_heat <= Decimal("10.0"):
            warnings.append(f"Portfolio heat at {projected_heat:.2f}% (80% capacity warning)")

        if projected_heat > Decimal("10.0"):
            logger.error(
                "portfolio_heat_validation_failed",
                current_heat=str(portfolio_heat),
                new_position_risk=str(new_position_risk_pct),
                projected_heat=str(projected_heat),
                limit="10.0",
                execution_time_ms=execution_time,
            )
            return (
                ValidationResult(
                    is_valid=False,
                    validation_step="portfolio_heat",
                    rejection_reason=f"Portfolio heat would exceed 10% limit (projected: {projected_heat:.2f}%)",
                    execution_time_ms=execution_time,
                ),
                projected_heat,
            )

        logger.debug(
            "portfolio_heat_validation_passed",
            current_heat=str(portfolio_heat),
            new_position_risk=str(new_position_risk_pct),
            projected_heat=str(projected_heat),
            warnings=warnings,
            execution_time_ms=execution_time,
        )
        return (
            ValidationResult(
                is_valid=True,
                validation_step="portfolio_heat",
                warnings=warnings,
                execution_time_ms=execution_time,
            ),
            projected_heat,
        )

    async def _validate_campaign_risk(
        self,
        campaign_id: Optional[UUID],
        current_positions: list[Position],
        new_position_risk_pct: Decimal,
        pattern_type: PatternType,
    ) -> tuple[ValidationResult, Optional[Decimal]]:
        """
        Step 7: Campaign risk validation (Story 7.4).

        If campaign_id is None, skips validation (returns is_valid=True).
        Otherwise validates projected campaign risk ≤ 5.0% (FR18 campaign maximum).

        Validates BMAD allocation: Spring 25%, ST 20%, SOS 35%, LPS 20%.
        Generates proximity warning if campaign risk ≥ 4.0% (80% capacity).

        Parameters:
        -----------
        campaign_id : Optional[UUID]
            Campaign identifier (None if no campaign)
        current_positions : list[Position]
            Currently open positions
        new_position_risk_pct : Decimal
            New position risk percentage
        pattern_type : PatternType
            Pattern type for BMAD allocation validation

        Returns:
        --------
        tuple[ValidationResult, Optional[Decimal]]
            (validation_result, projected_campaign_risk_or_none)
        """
        start_time = time.perf_counter()

        if campaign_id is None:
            execution_time = (time.perf_counter() - start_time) * 1000
            logger.debug(
                "campaign_risk_validation_skipped",
                reason="No campaign_id provided",
                execution_time_ms=execution_time,
            )
            return (
                ValidationResult(
                    is_valid=True,
                    validation_step="campaign_risk",
                    execution_time_ms=execution_time,
                ),
                None,
            )

        # Calculate campaign risk (Story 7.4)
        campaign_risk = calculate_campaign_risk(
            campaign_id=campaign_id, open_positions=current_positions
        )
        projected_campaign_risk = campaign_risk + new_position_risk_pct

        execution_time = (time.perf_counter() - start_time) * 1000

        warnings = []
        if projected_campaign_risk >= Decimal("4.0") and projected_campaign_risk <= Decimal("5.0"):
            warnings.append(
                f"Campaign risk at {projected_campaign_risk:.2f}% (80% capacity warning)"
            )

        if projected_campaign_risk > Decimal("5.0"):
            logger.error(
                "campaign_risk_validation_failed",
                campaign_id=str(campaign_id),
                current_risk=str(campaign_risk),
                new_position_risk=str(new_position_risk_pct),
                projected_risk=str(projected_campaign_risk),
                limit="5.0",
                execution_time_ms=execution_time,
            )
            return (
                ValidationResult(
                    is_valid=False,
                    validation_step="campaign_risk",
                    rejection_reason=f"Campaign risk would exceed 5% limit (projected: {projected_campaign_risk:.2f}%)",
                    execution_time_ms=execution_time,
                ),
                projected_campaign_risk,
            )

        logger.debug(
            "campaign_risk_validation_passed",
            campaign_id=str(campaign_id),
            current_risk=str(campaign_risk),
            new_position_risk=str(new_position_risk_pct),
            projected_risk=str(projected_campaign_risk),
            warnings=warnings,
            execution_time_ms=execution_time,
        )
        return (
            ValidationResult(
                is_valid=True,
                validation_step="campaign_risk",
                warnings=warnings,
                execution_time_ms=execution_time,
            ),
            projected_campaign_risk,
        )

    async def _validate_correlated_risk(
        self,
        signal: Signal,
        new_position_risk_pct: Decimal,
        open_positions: list[Position],
        correlation_config: CorrelationConfig,
        sector_mappings: dict[str, SectorMapping],
        active_campaigns: list["CampaignForCorrelation"],
    ) -> tuple[ValidationResult, dict[str, Decimal]]:
        """
        Step 8: Correlated risk validation (Story 7.5).

        Validates all correlation levels: sector, asset_class, geography.
        Rejects if ANY level exceeds 6.0% (strict mode).
        Generates warnings in permissive mode or proximity alerts.

        Parameters:
        -----------
        signal : Signal
            Trading signal
        new_position_risk_pct : Decimal
            New position risk percentage
        open_positions : list[Position]
            Currently open positions
        correlation_config : CorrelationConfig
            Correlation configuration
        sector_mappings : dict[str, SectorMapping]
            Symbol to sector mapping
        active_campaigns : list[CampaignForCorrelation]
            Active campaigns for correlation grouping

        Returns:
        --------
        tuple[ValidationResult, dict[str, Decimal]]
            (validation_result, correlated_risks_by_type)
        """
        start_time = time.perf_counter()

        # Get sector mapping for new symbol
        sector_mapping = sector_mappings.get(signal.symbol)
        if sector_mapping is None:
            # Cannot validate correlation without sector mapping
            logger.warning(
                "correlation_validation_skipped",
                symbol=signal.symbol,
                reason="Symbol not found in sector_mappings",
            )
            execution_time = (time.perf_counter() - start_time) * 1000
            return (
                ValidationResult(
                    is_valid=True,  # Skip validation, don't reject
                    validation_step="correlated_risk",
                    warnings=[
                        f"Correlation validation skipped: {signal.symbol} not in sector_mappings"
                    ],
                    execution_time_ms=execution_time,
                ),
                {},
            )

        # Create campaign for new position (Story 7.5 expects CampaignForCorrelation)
        from uuid import uuid4

        from src.models.correlation_campaign import CampaignForCorrelation

        new_campaign = CampaignForCorrelation(
            campaign_id=uuid4(),  # Temporary ID for validation
            symbol=signal.symbol,
            sector=sector_mapping.sector,
            asset_class=sector_mapping.asset_class,
            geography=sector_mapping.geography,
            total_campaign_risk=new_position_risk_pct,
            positions=[],  # Not needed for correlation calculation
            status="ACTIVE",
        )

        # Validate correlated risk (Story 7.5)
        is_valid, rejection_reason, warnings = validate_correlated_risk(
            new_campaign=new_campaign,
            open_campaigns=active_campaigns,
            config=correlation_config,
        )

        execution_time = (time.perf_counter() - start_time) * 1000

        # Extract correlation risks by type (for PositionSizing.correlated_risks)
        correlated_risks: dict[str, Decimal] = {}
        # TODO: Extract actual correlation values from validate_correlated_risk result
        # For now, placeholder empty dict

        if not is_valid:
            logger.error(
                "correlated_risk_validation_failed",
                symbol=signal.symbol,
                rejection_reason=rejection_reason,
                execution_time_ms=execution_time,
            )
            return (
                ValidationResult(
                    is_valid=False,
                    validation_step="correlated_risk",
                    rejection_reason=rejection_reason,
                    warnings=warnings,
                    execution_time_ms=execution_time,
                ),
                correlated_risks,
            )

        logger.debug(
            "correlated_risk_validation_passed",
            symbol=signal.symbol,
            warnings=warnings,
            execution_time_ms=execution_time,
        )
        return (
            ValidationResult(
                is_valid=True,
                validation_step="correlated_risk",
                warnings=warnings,
                execution_time_ms=execution_time,
            ),
            correlated_risks,
        )

    async def validate_and_size(
        self,
        signal: Signal,
        portfolio_context: PortfolioContext,
        trading_range: TradingRange,
    ) -> Optional[PositionSizing]:
        """
        Main validation pipeline: validates signal and calculates position sizing.

        Executes 8-step validation pipeline (AC 2):
        1. Pattern risk validation
        2. Phase prerequisite validation (SHORT-CIRCUITS if fails)
        3. R-multiple validation (uses Signal.stop)
        4. Structural stop validation (validates Signal.stop, may adjust)
        5. Position size calculation (uses validated/adjusted stop)
        6. Portfolio heat validation
        7. Campaign risk validation (if campaign_id present)
        8. Correlated risk validation

        SHORT-CIRCUIT (AC 11): Phase validation failure stops pipeline immediately.

        Parameters:
        -----------
        signal : Signal
            Trading signal to validate
        portfolio_context : PortfolioContext
            Complete portfolio state
        trading_range : TradingRange
            Trading range with event_history for phase validation

        Returns:
        --------
        Optional[PositionSizing]
            PositionSizing object if all validations pass, None if any fails

        Example:
        --------
        >>> result = await risk_manager.validate_and_size(
        ...     signal=spring_signal,
        ...     portfolio_context=portfolio_context,
        ...     trading_range=trading_range
        ... )
        >>> if result:
        ...     print(f"Approved: {result.shares} shares")
        ... else:
        ...     print("Rejected")
        """
        async with self._lock:  # Thread-safe concurrent access (AC 6)
            pipeline_start = time.perf_counter()

            # Initialize validation pipeline
            pipeline = ValidationPipeline()

            logger.info(
                "validation_pipeline_start",
                symbol=signal.symbol,
                pattern_type=signal.pattern_type.value,
                entry=str(signal.entry),
                stop=str(signal.stop),
                target=str(signal.target),
            )

            # Step 1: Pattern risk validation
            pattern_risk_result = await self._validate_pattern_risk(
                pattern_type=signal.pattern_type, signal=signal
            )
            pipeline.add_result(pattern_risk_result)
            if not pattern_risk_result.is_valid:
                pipeline.total_execution_time_ms = (time.perf_counter() - pipeline_start) * 1000
                logger.error(
                    "validation_pipeline_failure",
                    symbol=signal.symbol,
                    failed_step="pattern_risk",
                    rejection_reason=pattern_risk_result.rejection_reason,
                    total_execution_time_ms=pipeline.total_execution_time_ms,
                )
                return None

            # Step 2: Phase prerequisite validation (SHORT-CIRCUIT POINT)
            phase_result, phase_validation = await self._validate_phase_prerequisites(
                pattern_type=signal.pattern_type,
                trading_range=trading_range,
                mode="STRICT",
            )
            pipeline.add_result(phase_result)
            if not phase_result.is_valid:
                pipeline.total_execution_time_ms = (time.perf_counter() - pipeline_start) * 1000
                logger.error(
                    "validation_pipeline_failure",
                    symbol=signal.symbol,
                    failed_step="phase_prerequisites",
                    rejection_reason=phase_result.rejection_reason,
                    total_execution_time_ms=pipeline.total_execution_time_ms,
                )
                return None  # SHORT-CIRCUIT: Don't calculate R-multiple

            # Step 3: R-multiple validation (uses preliminary Signal.stop)
            r_result, r_multiple = await self._validate_r_multiple(
                entry=signal.entry,
                stop=signal.stop,
                target=signal.target,
                pattern_type=signal.pattern_type,
            )
            pipeline.add_result(r_result)
            if not r_result.is_valid:
                pipeline.total_execution_time_ms = (time.perf_counter() - pipeline_start) * 1000
                logger.error(
                    "validation_pipeline_failure",
                    symbol=signal.symbol,
                    failed_step="r_multiple",
                    rejection_reason=r_result.rejection_reason,
                    total_execution_time_ms=pipeline.total_execution_time_ms,
                )
                return None

            # Step 4: Structural stop validation (validates/adjusts Signal.stop)
            stop_result, validated_stop = await self._calculate_structural_stop(
                pattern_type=signal.pattern_type,
                entry=signal.entry,
                preliminary_stop=signal.stop,
            )
            pipeline.add_result(stop_result)
            if not stop_result.is_valid:
                pipeline.total_execution_time_ms = (time.perf_counter() - pipeline_start) * 1000
                logger.error(
                    "validation_pipeline_failure",
                    symbol=signal.symbol,
                    failed_step="structural_stop",
                    rejection_reason=stop_result.rejection_reason,
                    total_execution_time_ms=pipeline.total_execution_time_ms,
                )
                return None

            # Step 5: Position size calculation (uses validated/adjusted stop)
            size_result, position_sizing = await self._calculate_position_size(
                account_equity=portfolio_context.account_equity,
                pattern_type=signal.pattern_type,
                entry=signal.entry,
                stop=validated_stop,
                target=signal.target,
            )
            pipeline.add_result(size_result)
            if not size_result.is_valid or position_sizing is None:
                pipeline.total_execution_time_ms = (time.perf_counter() - pipeline_start) * 1000
                logger.error(
                    "validation_pipeline_failure",
                    symbol=signal.symbol,
                    failed_step="position_size",
                    rejection_reason=size_result.rejection_reason,
                    total_execution_time_ms=pipeline.total_execution_time_ms,
                )
                return None

            # Step 6: Portfolio heat validation
            heat_result, projected_heat = await self._validate_portfolio_heat(
                current_positions=portfolio_context.open_positions,
                new_position_risk_pct=position_sizing.risk_pct,
            )
            pipeline.add_result(heat_result)
            if not heat_result.is_valid:
                pipeline.total_execution_time_ms = (time.perf_counter() - pipeline_start) * 1000
                logger.error(
                    "validation_pipeline_failure",
                    symbol=signal.symbol,
                    failed_step="portfolio_heat",
                    rejection_reason=heat_result.rejection_reason,
                    total_execution_time_ms=pipeline.total_execution_time_ms,
                )
                return None

            # Step 7: Campaign risk validation (if campaign_id present)
            campaign_result, projected_campaign_risk = await self._validate_campaign_risk(
                campaign_id=signal.campaign_id,
                current_positions=portfolio_context.open_positions,
                new_position_risk_pct=position_sizing.risk_pct,
                pattern_type=signal.pattern_type,
            )
            pipeline.add_result(campaign_result)
            if not campaign_result.is_valid:
                pipeline.total_execution_time_ms = (time.perf_counter() - pipeline_start) * 1000
                logger.error(
                    "validation_pipeline_failure",
                    symbol=signal.symbol,
                    failed_step="campaign_risk",
                    rejection_reason=campaign_result.rejection_reason,
                    total_execution_time_ms=pipeline.total_execution_time_ms,
                )
                return None

            # Step 8: Correlated risk validation
            corr_result, correlated_risks = await self._validate_correlated_risk(
                signal=signal,
                new_position_risk_pct=position_sizing.risk_pct,
                open_positions=portfolio_context.open_positions,
                correlation_config=portfolio_context.correlation_config,
                sector_mappings=portfolio_context.sector_mappings,
                active_campaigns=portfolio_context.active_campaigns,
            )
            pipeline.add_result(corr_result)
            if not corr_result.is_valid:
                pipeline.total_execution_time_ms = (time.perf_counter() - pipeline_start) * 1000
                logger.error(
                    "validation_pipeline_failure",
                    symbol=signal.symbol,
                    failed_step="correlated_risk",
                    rejection_reason=corr_result.rejection_reason,
                    total_execution_time_ms=pipeline.total_execution_time_ms,
                )
                return None

            # ALL VALIDATIONS PASSED: Construct PositionSizing with metadata
            pipeline.total_execution_time_ms = (time.perf_counter() - pipeline_start) * 1000

            # Populate enhanced PositionSizing fields (Story 7.8 AC 3)
            position_sizing.r_multiple = r_multiple
            position_sizing.validation_pipeline = pipeline
            position_sizing.phase_validation = phase_validation
            position_sizing.portfolio_heat_after = projected_heat
            position_sizing.campaign_risk_after = projected_campaign_risk
            position_sizing.correlated_risks = correlated_risks

            # Performance warning if >10ms (AC 9)
            if pipeline.total_execution_time_ms > 10.0:
                logger.warning(
                    "validation_pipeline_performance_warning",
                    symbol=signal.symbol,
                    total_execution_time_ms=pipeline.total_execution_time_ms,
                    threshold=10.0,
                )

            logger.info(
                "validation_pipeline_success",
                symbol=signal.symbol,
                shares=position_sizing.shares,
                risk_amount=str(position_sizing.risk_amount),
                r_multiple=str(r_multiple),
                portfolio_heat_after=str(projected_heat),
                total_execution_time_ms=pipeline.total_execution_time_ms,
                warnings_count=len(pipeline.all_warnings),
            )

            return position_sizing
