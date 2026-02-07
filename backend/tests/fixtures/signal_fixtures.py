"""
Test Fixtures for Trade Signals (Story 8.8)

Provides realistic TradeSignal and RejectedSignal fixtures for unit
and integration testing.

Fixtures:
---------
- valid_spring_signal(): STOCK - Spring pattern with all FR22 fields
- valid_sos_signal(): STOCK - SOS pattern with secondary targets
- valid_forex_signal(): FOREX - EUR/USD Spring with leverage
- rejected_signal_portfolio_heat(): Rejected at Risk stage
- rejected_signal_low_r_multiple(): Rejected due to R < minimum
- mock_validation_chain(): ValidationChain with all stages PASS

Author: Story 8.8
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from src.models.signal import (
    ConfidenceComponents,
    RejectedSignal,
    TargetLevels,
    TradeSignal,
)
from src.models.validation import (
    StageValidationResult,
    ValidationChain,
    ValidationStatus,
)


def mock_validation_chain(
    pattern_id: UUID | None = None,
    overall_status: ValidationStatus = ValidationStatus.PASS,
    rejection_stage: str | None = None,
    rejection_reason: str | None = None,
    volume_metadata: dict | None = None,
    phase_metadata: dict | None = None,
    levels_metadata: dict | None = None,
    risk_metadata: dict | None = None,
) -> ValidationChain:
    """
    Create mock ValidationChain for testing.

    Parameters:
    -----------
    pattern_id : UUID | None
        Pattern ID (generates new UUID if None)
    overall_status : ValidationStatus
        Overall validation status (default PASS)
    rejection_stage : str | None
        Stage where validation failed (for FAIL status)
    rejection_reason : str | None
        Rejection reason (for FAIL status)
    volume_metadata : dict | None
        Override volume stage metadata (merged with SPRING defaults)
    phase_metadata : dict | None
        Override phase stage metadata (merged with defaults)
    levels_metadata : dict | None
        Override levels stage metadata (merged with defaults)
    risk_metadata : dict | None
        Override risk stage metadata (merged with defaults)

    Returns:
    --------
    ValidationChain
        Mock validation chain with all 5 stages
    """
    if pattern_id is None:
        pattern_id = uuid4()

    chain = ValidationChain(pattern_id=pattern_id)

    # Add Volume validation
    default_volume_meta = {
        "volume_ratio": "0.55",
        "threshold": "0.70",
        "pattern_type": "SPRING",
    }
    vol_meta = {**default_volume_meta, **(volume_metadata or {})}
    chain.add_result(
        StageValidationResult(
            stage="Volume",
            status=ValidationStatus.PASS,
            validator_id="VOLUME_VALIDATOR",
            metadata=vol_meta,
        )
    )

    # Add Phase validation
    default_phase_meta: dict = {"phase": "C", "confidence": 85}
    ph_meta = {**default_phase_meta, **(phase_metadata or {})}
    chain.add_result(
        StageValidationResult(
            stage="Phase",
            status=ValidationStatus.PASS,
            validator_id="PHASE_VALIDATOR",
            metadata=ph_meta,
        )
    )

    # Add Levels validation
    default_levels_meta = {
        "entry_price": "150.00",
        "stop_loss": "148.00",
        "target_price": "156.00",
    }
    lvl_meta = {**default_levels_meta, **(levels_metadata or {})}
    chain.add_result(
        StageValidationResult(
            stage="Levels",
            status=ValidationStatus.PASS,
            validator_id="LEVEL_VALIDATOR",
            metadata=lvl_meta,
        )
    )

    # Add Risk validation - may fail here
    if rejection_stage == "Risk":
        chain.add_result(
            StageValidationResult(
                stage="Risk",
                status=ValidationStatus.FAIL,
                reason=rejection_reason or "Risk validation failed",
                validator_id="RISK_VALIDATOR",
                metadata={"portfolio_heat": "12%", "max_heat": "10%"},
            )
        )
    else:
        default_risk_meta = {
            "position_size": "100",
            "risk_amount": "200.00",
            "r_multiple": "3.0",
            "portfolio_heat": "5%",
        }
        rsk_meta = {**default_risk_meta, **(risk_metadata or {})}
        chain.add_result(
            StageValidationResult(
                stage="Risk",
                status=ValidationStatus.PASS,
                validator_id="RISK_VALIDATOR",
                metadata=rsk_meta,
            )
        )

    # Add Strategy validation
    if rejection_stage not in ["Risk"]:  # Only add if we haven't failed yet
        chain.add_result(
            StageValidationResult(
                stage="Strategy",
                status=ValidationStatus.PASS,
                validator_id="STRATEGY_VALIDATOR",
                metadata={"strategy_alignment": True},
            )
        )

    chain.completed_at = datetime.now(UTC)
    return chain


def valid_spring_signal() -> TradeSignal:
    """
    Valid Spring signal on AAPL (STOCK).

    All FR22 fields populated with realistic values.
    All validations PASS.

    Returns:
    --------
    TradeSignal
        Complete Spring signal ready for execution
    """
    pattern_id = uuid4()
    validation_chain = mock_validation_chain(pattern_id=pattern_id)

    return TradeSignal(
        id=uuid4(),
        asset_class="STOCK",
        symbol="AAPL",
        pattern_type="SPRING",
        phase="C",
        timeframe="1h",
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("148.00"),
        target_levels=TargetLevels(
            primary_target=Decimal("156.00"),
            secondary_targets=[Decimal("152.00"), Decimal("154.00")],
            trailing_stop_activation=Decimal("154.00"),
            trailing_stop_offset=Decimal("1.00"),
        ),
        position_size=Decimal("100"),
        position_size_unit="SHARES",
        leverage=None,
        margin_requirement=None,
        notional_value=Decimal("15000.00"),  # 100 shares × $150
        risk_amount=Decimal("200.00"),  # 100 shares × $2 risk
        r_multiple=Decimal("3.0"),  # ($156-$150) / ($150-$148) = 3.0
        confidence_score=85,
        confidence_components=ConfidenceComponents(
            pattern_confidence=88, phase_confidence=82, volume_confidence=80, overall_confidence=85
        ),
        campaign_id="AAPL-2024-03-13-C",
        validation_chain=validation_chain,
        status="APPROVED",
        pattern_data={
            "pattern_bar_timestamp": "2024-03-13T10:30:00Z",
            "test_bar_timestamp": "2024-03-13T11:30:00Z",
            "trading_range_id": str(uuid4()),
        },
        volume_analysis={
            "volume_ratio": "0.55",
            "average_volume": 50000000,
            "test_volume_ratio": "0.40",
        },
        timestamp=datetime(2024, 3, 13, 14, 30, 0, tzinfo=UTC),
        schema_version=1,
    )


def valid_sos_signal() -> TradeSignal:
    """
    Valid SOS signal on MSFT (STOCK).

    Direct SOS entry (no LPS) with higher volume requirement.

    Returns:
    --------
    TradeSignal
        Complete SOS signal
    """
    pattern_id = uuid4()
    validation_chain = mock_validation_chain(pattern_id=pattern_id)

    return TradeSignal(
        id=uuid4(),
        asset_class="STOCK",
        symbol="MSFT",
        pattern_type="SOS",
        phase="D",
        timeframe="1d",
        entry_price=Decimal("380.00"),
        stop_loss=Decimal("375.00"),
        target_levels=TargetLevels(
            primary_target=Decimal("400.00"),
            secondary_targets=[Decimal("385.00"), Decimal("390.00"), Decimal("395.00")],
            trailing_stop_activation=None,
            trailing_stop_offset=None,
        ),
        position_size=Decimal("50"),
        position_size_unit="SHARES",
        leverage=None,
        margin_requirement=None,
        notional_value=Decimal("19000.00"),  # 50 shares × $380
        risk_amount=Decimal("250.00"),  # 50 shares × $5 risk
        r_multiple=Decimal("4.0"),  # ($400-$380) / ($380-$375) = 4.0
        confidence_score=88,
        confidence_components=ConfidenceComponents(
            pattern_confidence=90, phase_confidence=85, volume_confidence=88, overall_confidence=88
        ),
        campaign_id="MSFT-2024-03-14-D",
        validation_chain=validation_chain,
        status="APPROVED",
        pattern_data={
            "pattern_bar_timestamp": "2024-03-14T20:00:00Z",
            "test_bar_timestamp": None,
            "trading_range_id": str(uuid4()),
        },
        volume_analysis={
            "volume_ratio": "2.2",
            "average_volume": 30000000,
        },
        timestamp=datetime(2024, 3, 14, 20, 30, 0, tzinfo=UTC),
        schema_version=1,
    )


def valid_forex_signal() -> TradeSignal:
    """
    Valid Forex signal on EUR/USD (FOREX).

    Spring pattern with leverage and margin requirements.

    Returns:
    --------
    TradeSignal
        Complete Forex signal with leverage
    """
    pattern_id = uuid4()
    validation_chain = mock_validation_chain(pattern_id=pattern_id)

    return TradeSignal(
        id=uuid4(),
        asset_class="FOREX",
        symbol="EUR/USD",
        pattern_type="SPRING",
        phase="C",
        timeframe="4h",
        entry_price=Decimal("1.08500"),
        stop_loss=Decimal("1.08200"),
        target_levels=TargetLevels(
            primary_target=Decimal("1.09400"),
            secondary_targets=[Decimal("1.08800"), Decimal("1.09100")],
            trailing_stop_activation=None,
            trailing_stop_offset=None,
        ),
        position_size=Decimal("0.5"),  # 0.5 standard lots = 50,000 units
        position_size_unit="LOTS",
        leverage=Decimal("50.0"),  # 50:1 leverage
        margin_requirement=Decimal("1085.00"),  # 50,000 × 1.085 / 50
        notional_value=Decimal("54250.00"),  # 50,000 units × 1.085
        risk_amount=Decimal("150.00"),  # 50,000 × 0.003 (30 pips risk)
        r_multiple=Decimal("3.0"),  # (1.094-1.085) / (1.085-1.082) = 3.0
        confidence_score=82,
        confidence_components=ConfidenceComponents(
            pattern_confidence=85, phase_confidence=80, volume_confidence=78, overall_confidence=82
        ),
        campaign_id="EURUSD-2024-03-15-C",
        validation_chain=validation_chain,
        status="APPROVED",
        pattern_data={
            "pattern_bar_timestamp": "2024-03-15T08:00:00Z",
            "test_bar_timestamp": "2024-03-15T12:00:00Z",
            "trading_range_id": str(uuid4()),
        },
        volume_analysis={
            "tick_volume_ratio": "0.75",
            "average_tick_volume": 12000,
            "session": "LONDON",
        },
        timestamp=datetime(2024, 3, 15, 12, 30, 0, tzinfo=UTC),
        schema_version=1,
    )


def valid_utad_signal() -> TradeSignal:
    """
    Valid UTAD signal on SPY (STOCK) - SHORT direction.

    UTAD (Upthrust After Distribution) is a SHORT pattern where
    price breaks above Ice, fails, and reverses down.
    Stop is above entry, target is below entry.

    Entry=450.00, Stop=453.00 (above), Target=441.00 (below)
    R = (450-441)/(453-450) = 9/3 = 3.0

    Returns:
    --------
    TradeSignal
        Complete UTAD signal for SHORT trade
    """
    pattern_id = uuid4()
    validation_chain = mock_validation_chain(
        pattern_id=pattern_id,
        volume_metadata={"volume_ratio": "1.80", "threshold": "1.50", "pattern_type": "UTAD"},
        phase_metadata={"phase": "D", "confidence": 85},
        levels_metadata={"entry_price": "450.00", "stop_loss": "453.00", "target_price": "441.00"},
        risk_metadata={"risk_amount": "300.00"},
    )

    return TradeSignal(
        id=uuid4(),
        asset_class="STOCK",
        symbol="SPY",
        pattern_type="UTAD",
        phase="D",
        timeframe="1h",
        entry_price=Decimal("450.00"),
        stop_loss=Decimal("453.00"),  # Above entry for SHORT
        target_levels=TargetLevels(
            primary_target=Decimal("441.00"),  # Below entry for SHORT
            secondary_targets=[Decimal("447.00"), Decimal("444.00")],
            trailing_stop_activation=Decimal("444.00"),
            trailing_stop_offset=Decimal("1.00"),
        ),
        position_size=Decimal("100"),
        position_size_unit="SHARES",
        leverage=None,
        margin_requirement=None,
        notional_value=Decimal("45000.00"),  # 100 shares x $450
        risk_amount=Decimal("300.00"),  # 100 shares x $3 risk
        r_multiple=Decimal("3.0"),  # (450-441) / (453-450) = 3.0
        confidence_score=85,
        confidence_components=ConfidenceComponents(
            pattern_confidence=88, phase_confidence=82, volume_confidence=80, overall_confidence=85
        ),
        campaign_id="SPY-2024-03-13-D",
        validation_chain=validation_chain,
        status="APPROVED",
        pattern_data={
            "pattern_bar_timestamp": "2024-03-13T10:30:00Z",
            "test_bar_timestamp": "2024-03-13T11:30:00Z",
            "trading_range_id": str(uuid4()),
        },
        volume_analysis={
            "volume_ratio": "1.80",
            "average_volume": 80000000,
        },
        timestamp=datetime(2024, 3, 13, 14, 30, 0, tzinfo=UTC),
        schema_version=1,
    )


def rejected_signal_portfolio_heat() -> RejectedSignal:
    """
    Signal rejected at Risk stage due to portfolio heat.

    Pattern passed Volume, Phase, and Levels validation,
    but failed Risk validation because adding the position
    would exceed 10% portfolio heat limit.

    Returns:
    --------
    RejectedSignal
        Rejected signal with partial validation chain
    """
    pattern_id = uuid4()
    validation_chain = mock_validation_chain(
        pattern_id=pattern_id,
        overall_status=ValidationStatus.FAIL,
        rejection_stage="Risk",
        rejection_reason="Portfolio heat would be 12.5% (exceeds 10.0% limit)",
    )

    return RejectedSignal(
        id=uuid4(),
        pattern_id=pattern_id,
        symbol="TSLA",
        pattern_type="SPRING",
        rejection_stage="Risk",
        rejection_reason="Portfolio heat would be 12.5% (exceeds 10.0% limit)",
        validation_chain=validation_chain,
        timestamp=datetime(2024, 3, 13, 15, 0, 0, tzinfo=UTC),
        schema_version=1,
    )


def rejected_signal_low_r_multiple() -> RejectedSignal:
    """
    Signal rejected at Risk stage due to insufficient R-multiple.

    Pattern has R=2.5 which is below the minimum R=3.0 threshold
    for Spring patterns.

    Returns:
    --------
    RejectedSignal
        Rejected signal due to low R-multiple
    """
    pattern_id = uuid4()
    validation_chain = mock_validation_chain(
        pattern_id=pattern_id,
        overall_status=ValidationStatus.FAIL,
        rejection_stage="Risk",
        rejection_reason="R-multiple 2.5 below minimum 3.0 for SPRING pattern",
    )

    return RejectedSignal(
        id=uuid4(),
        pattern_id=pattern_id,
        symbol="NVDA",
        pattern_type="SPRING",
        rejection_stage="Risk",
        rejection_reason="R-multiple 2.5 below minimum 3.0 for SPRING pattern",
        validation_chain=validation_chain,
        timestamp=datetime(2024, 3, 13, 16, 0, 0, tzinfo=UTC),
        schema_version=1,
    )
