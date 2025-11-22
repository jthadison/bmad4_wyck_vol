"""
Unit tests for Phase Completion Validator - Story 7.9

Tests phase prerequisite validation for Wyckoff patterns:
- Spring prerequisites (PS, SC, AR)
- SOS prerequisites (Spring + Test of Spring)
- LPS prerequisites (SOS required first)
- UTAD prerequisites (Distribution Phase A-B-C)
- Volume quality validation
- Sequence validation
- STRICT vs PERMISSIVE modes
- Confidence scoring

Author: Story 7.9
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.ohlcv import OHLCVBar
from src.models.phase_validation import (
    PermissiveModeControls,
    VolumeQuality,
    VolumeThresholds,
    WyckoffEvent,
    WyckoffEventType,
)
from src.models.pivot import Pivot, PivotType
from src.models.price_cluster import PriceCluster
from src.models.trading_range import TradingRange
from src.risk_management.phase_validator import (
    validate_comparative_volume,
    validate_event_sequence,
    validate_lps_prerequisites,
    validate_phase_prerequisites,
    validate_sos_prerequisites,
    validate_spring_prerequisites,
    validate_utad_prerequisites,
)

# ============================================================================
# Test Fixtures
# ============================================================================


def create_wyckoff_event(
    event_type: WyckoffEventType,
    timestamp: datetime,
    price: Decimal = Decimal("100.00"),
    volume_ratio: Decimal = Decimal("1.0"),
    volume_quality: VolumeQuality = VolumeQuality.AVERAGE,
    confidence: float = 0.85,
    meets_threshold: bool = True,
) -> WyckoffEvent:
    """Helper to create WyckoffEvent for testing."""
    return WyckoffEvent(
        event_type=event_type,
        timestamp=timestamp,
        price_level=price,
        volume_ratio=volume_ratio,
        volume_quality=volume_quality,
        confidence=confidence,
        meets_volume_threshold=meets_threshold,
    )


def _create_ohlcv_bar(
    symbol: str,
    timestamp: datetime,
    price: Decimal,
    index: int,
    pivot_type: PivotType,
) -> OHLCVBar:
    """Create an OHLCVBar suitable for pivot creation."""
    # For LOW pivot, the price is the low; for HIGH pivot, the price is the high
    if pivot_type == PivotType.LOW:
        return OHLCVBar(
            symbol=symbol,
            timeframe="1d",
            timestamp=timestamp,
            open=price + Decimal("1.00"),
            high=price + Decimal("2.00"),
            low=price,
            close=price + Decimal("0.50"),
            volume=1000000,
            spread=Decimal("2.00"),
        )
    else:
        return OHLCVBar(
            symbol=symbol,
            timeframe="1d",
            timestamp=timestamp,
            open=price - Decimal("1.00"),
            high=price,
            low=price - Decimal("2.00"),
            close=price - Decimal("0.50"),
            volume=1000000,
            spread=Decimal("2.00"),
        )


def _create_pivots(
    pivot_type: PivotType,
    base_price: Decimal,
    base_timestamp: datetime,
    symbol: str = "TEST",
) -> list[Pivot]:
    """Create valid Pivot objects for PriceCluster."""
    pivots = []
    for i, idx in enumerate([10, 20, 30]):
        timestamp = base_timestamp + timedelta(days=i * 5)
        # Vary price slightly for realism
        price = base_price + Decimal(str(i * 0.5))
        bar = _create_ohlcv_bar(symbol, timestamp, price, idx, pivot_type)
        pivot = Pivot(
            bar=bar,
            price=bar.low if pivot_type == PivotType.LOW else bar.high,
            type=pivot_type,
            strength=5,
            timestamp=timestamp,
            index=idx,
        )
        pivots.append(pivot)
    return pivots


def _create_price_cluster(
    pivot_type: PivotType,
    base_price: Decimal,
    base_timestamp: datetime,
    symbol: str = "TEST",
) -> PriceCluster:
    """Create a valid PriceCluster with properly initialized Pivots."""
    pivots = _create_pivots(pivot_type, base_price, base_timestamp, symbol)
    prices = [p.price for p in pivots]
    avg_price = sum(prices) / len(prices)
    min_price = min(prices)
    max_price = max(prices)
    price_range = max_price - min_price

    # Calculate std deviation - round to 8 decimal places to fit within max_digits=18
    variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
    std_dev = round(variance ** Decimal("0.5"), 8)

    return PriceCluster(
        pivots=pivots,
        average_price=round(avg_price, 8),
        min_price=round(min_price, 8),
        max_price=round(max_price, 8),
        price_range=round(price_range, 8),
        touch_count=len(pivots),
        cluster_type=pivot_type,
        std_deviation=std_dev,
        timestamp_range=(pivots[0].timestamp, pivots[-1].timestamp),
    )


def create_trading_range_with_events(events: list[WyckoffEvent]) -> TradingRange:
    """Helper to create TradingRange with event_history."""
    base_timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    support_cluster = _create_price_cluster(PivotType.LOW, Decimal("95.00"), base_timestamp, "TEST")
    resistance_cluster = _create_price_cluster(
        PivotType.HIGH, Decimal("105.00"), base_timestamp, "TEST"
    )

    tr = TradingRange(
        id=uuid4(),
        symbol="TEST",
        timeframe="1d",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=Decimal("95.00"),
        resistance=Decimal("105.00"),
        midpoint=Decimal("100.00"),
        range_width=Decimal("10.00"),
        range_width_pct=Decimal("0.105"),
        start_index=0,
        end_index=50,
        duration=51,
        event_history=events,
    )
    return tr


@pytest.fixture
def base_timestamp():
    """Base timestamp for event creation."""
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def complete_phase_ab_events(base_timestamp):
    """Complete Phase A-B events for Spring validation."""
    return [
        create_wyckoff_event(
            WyckoffEventType.PS,
            base_timestamp,
            Decimal("96.00"),
            Decimal("1.3"),
            VolumeQuality.AVERAGE,
        ),
        create_wyckoff_event(
            WyckoffEventType.SC,
            base_timestamp + timedelta(days=2),
            Decimal("94.00"),
            Decimal("2.5"),  # Climactic volume
            VolumeQuality.CLIMACTIC,
        ),
        create_wyckoff_event(
            WyckoffEventType.AR,
            base_timestamp + timedelta(days=5),
            Decimal("103.00"),
            Decimal("1.2"),  # Diminishing volume
            VolumeQuality.AVERAGE,
        ),
    ]


@pytest.fixture
def complete_phase_c_events(complete_phase_ab_events, base_timestamp):
    """Complete Phase C events for SOS validation."""
    return complete_phase_ab_events + [
        create_wyckoff_event(
            WyckoffEventType.SPRING,
            base_timestamp + timedelta(days=15),
            Decimal("93.50"),
            Decimal("0.6"),  # Low volume
            VolumeQuality.LOW,
        ),
        create_wyckoff_event(
            WyckoffEventType.TEST_OF_SPRING,
            base_timestamp + timedelta(days=17),
            Decimal("94.00"),
            Decimal("0.4"),  # Even lower volume
            VolumeQuality.DRIED_UP,
        ),
    ]


@pytest.fixture
def complete_phase_d_events(complete_phase_c_events, base_timestamp):
    """Complete Phase D events for LPS validation."""
    return complete_phase_c_events + [
        create_wyckoff_event(
            WyckoffEventType.SOS,
            base_timestamp + timedelta(days=25),
            Decimal("106.00"),
            Decimal("1.8"),  # Strong volume
            VolumeQuality.HIGH,
        ),
    ]


# ============================================================================
# Test: Spring Prerequisite Validation (AC 1, 8, 11, 12)
# ============================================================================


class TestSpringPrerequisiteValidation:
    """Tests for validate_spring_prerequisites function."""

    def test_spring_with_complete_phase_ab_passes(self, complete_phase_ab_events, base_timestamp):
        """Test Spring with complete Phase A-B (PS, SC, AR) passes validation."""
        trading_range = create_trading_range_with_events(complete_phase_ab_events)

        result = validate_spring_prerequisites(trading_range)

        assert result.is_valid is True
        assert result.pattern_type == "SPRING"
        assert result.phase_complete is True
        assert len(result.missing_prerequisites) == 0
        assert "PS" in result.prerequisite_events
        assert "SC" in result.prerequisite_events
        assert "AR" in result.prerequisite_events
        assert result.rejection_reason is None

    def test_spring_missing_sc_fails(self, base_timestamp):
        """Test Spring with missing SC fails validation."""
        events = [
            create_wyckoff_event(
                WyckoffEventType.PS,
                base_timestamp,
                Decimal("96.00"),
                Decimal("1.3"),
            ),
            # No SC event
            create_wyckoff_event(
                WyckoffEventType.AR,
                base_timestamp + timedelta(days=5),
                Decimal("103.00"),
                Decimal("1.2"),
            ),
        ]
        trading_range = create_trading_range_with_events(events)

        result = validate_spring_prerequisites(trading_range)

        assert result.is_valid is False
        assert "SC" in result.missing_prerequisites
        assert result.rejection_reason is not None
        assert "SC" in result.rejection_reason

    def test_spring_missing_all_prerequisites_fails(self, base_timestamp):
        """Test Spring with no Phase A-B events fails."""
        trading_range = create_trading_range_with_events([])

        result = validate_spring_prerequisites(trading_range)

        assert result.is_valid is False
        assert "PS" in result.missing_prerequisites
        assert "SC" in result.missing_prerequisites
        assert "AR" in result.missing_prerequisites
        assert result.prerequisite_confidence_score == 0.0

    def test_spring_sc_without_climactic_volume_fails(self, base_timestamp):
        """Test Spring fails when SC volume is below climactic threshold (AC 11)."""
        events = [
            create_wyckoff_event(
                WyckoffEventType.PS,
                base_timestamp,
                Decimal("96.00"),
                Decimal("1.3"),
            ),
            create_wyckoff_event(
                WyckoffEventType.SC,
                base_timestamp + timedelta(days=2),
                Decimal("94.00"),
                Decimal("1.5"),  # NOT climactic (needs >= 2.0)
                VolumeQuality.HIGH,
                meets_threshold=False,
            ),
            create_wyckoff_event(
                WyckoffEventType.AR,
                base_timestamp + timedelta(days=5),
                Decimal("103.00"),
                Decimal("1.2"),
            ),
        ]
        trading_range = create_trading_range_with_events(events)

        result = validate_spring_prerequisites(trading_range)

        assert result.is_valid is False
        assert "SC volume" in result.rejection_reason
        assert "climactic" in result.rejection_reason.lower()

    def test_spring_ar_with_high_volume_fails(self, base_timestamp):
        """Test Spring fails when AR volume exceeds diminishing threshold (AC 11)."""
        events = [
            create_wyckoff_event(
                WyckoffEventType.PS,
                base_timestamp,
                Decimal("96.00"),
                Decimal("1.3"),
            ),
            create_wyckoff_event(
                WyckoffEventType.SC,
                base_timestamp + timedelta(days=2),
                Decimal("94.00"),
                Decimal("2.5"),
                VolumeQuality.CLIMACTIC,
            ),
            create_wyckoff_event(
                WyckoffEventType.AR,
                base_timestamp + timedelta(days=5),
                Decimal("103.00"),
                Decimal("1.8"),  # Too high (needs <= 1.5)
                VolumeQuality.HIGH,
                meets_threshold=False,
            ),
        ]
        trading_range = create_trading_range_with_events(events)

        result = validate_spring_prerequisites(trading_range)

        assert result.is_valid is False
        assert "AR volume" in result.rejection_reason


# ============================================================================
# Test: SOS Prerequisite Validation (AC 2, 8, 11, 12)
# ============================================================================


class TestSOSPrerequisiteValidation:
    """Tests for validate_sos_prerequisites function."""

    def test_sos_with_complete_phase_c_passes(self, complete_phase_c_events, base_timestamp):
        """Test SOS with complete Phase C (Spring + Test of Spring) passes."""
        trading_range = create_trading_range_with_events(complete_phase_c_events)

        result = validate_sos_prerequisites(trading_range)

        assert result.is_valid is True
        assert result.pattern_type == "SOS"
        assert "SPRING" in result.prerequisite_events
        assert "TEST_OF_SPRING" in result.prerequisite_events
        assert result.rejection_reason is None

    def test_sos_with_spring_but_no_test_fails(self, complete_phase_ab_events, base_timestamp):
        """Test SOS with Spring but no Test of Spring fails (AC 2)."""
        events = complete_phase_ab_events + [
            create_wyckoff_event(
                WyckoffEventType.SPRING,
                base_timestamp + timedelta(days=15),
                Decimal("93.50"),
                Decimal("0.6"),
                VolumeQuality.LOW,
            ),
            # No TEST_OF_SPRING event
        ]
        trading_range = create_trading_range_with_events(events)

        result = validate_sos_prerequisites(trading_range)

        assert result.is_valid is False
        assert "TEST_OF_SPRING" in result.missing_prerequisites
        assert "TEST_OF_SPRING" in result.rejection_reason

    def test_sos_without_prior_spring_fails(self, complete_phase_ab_events, base_timestamp):
        """Test SOS fails without prior Spring (jump the creek = false breakout)."""
        events = complete_phase_ab_events + [
            # No SPRING event
            create_wyckoff_event(
                WyckoffEventType.TEST_OF_SPRING,
                base_timestamp + timedelta(days=17),
                Decimal("94.00"),
                Decimal("0.4"),
                VolumeQuality.DRIED_UP,
            ),
        ]
        trading_range = create_trading_range_with_events(events)

        result = validate_sos_prerequisites(trading_range)

        assert result.is_valid is False
        assert "SPRING" in result.missing_prerequisites

    def test_sos_test_volume_higher_than_spring_fails(
        self, complete_phase_ab_events, base_timestamp
    ):
        """Test SOS fails when Test of Spring volume >= Spring volume (AC 12)."""
        events = complete_phase_ab_events + [
            create_wyckoff_event(
                WyckoffEventType.SPRING,
                base_timestamp + timedelta(days=15),
                Decimal("93.50"),
                Decimal("0.6"),  # Spring volume
                VolumeQuality.LOW,
            ),
            create_wyckoff_event(
                WyckoffEventType.TEST_OF_SPRING,
                base_timestamp + timedelta(days=17),
                Decimal("94.00"),
                Decimal("0.8"),  # Higher than Spring - VIOLATION
                VolumeQuality.LOW,
            ),
        ]
        trading_range = create_trading_range_with_events(events)

        result = validate_sos_prerequisites(trading_range)

        assert result.is_valid is False
        assert "Volume violation" in result.rejection_reason
        assert "TEST_OF_SPRING" in result.rejection_reason


# ============================================================================
# Test: LPS Prerequisite Validation (AC 3, 8)
# ============================================================================


class TestLPSPrerequisiteValidation:
    """Tests for validate_lps_prerequisites function."""

    def test_lps_with_prior_sos_passes(self, complete_phase_d_events):
        """Test LPS with prior SOS breakout passes."""
        trading_range = create_trading_range_with_events(complete_phase_d_events)

        result = validate_lps_prerequisites(trading_range)

        assert result.is_valid is True
        assert result.pattern_type == "LPS"
        assert "SOS" in result.prerequisite_events

    def test_lps_without_sos_fails(self, complete_phase_c_events):
        """Test LPS without prior SOS fails - 'LPS requires SOS breakout first'."""
        # Phase C complete but no SOS
        trading_range = create_trading_range_with_events(complete_phase_c_events)

        result = validate_lps_prerequisites(trading_range)

        assert result.is_valid is False
        assert "SOS" in result.missing_prerequisites
        assert "LPS requires SOS" in result.rejection_reason or "SOS" in result.rejection_reason


# ============================================================================
# Test: UTAD Prerequisite Validation (AC 4, 8)
# ============================================================================


class TestUTADPrerequisiteValidation:
    """Tests for validate_utad_prerequisites function."""

    def test_utad_with_complete_distribution_passes(self, base_timestamp):
        """Test UTAD with complete Distribution Phase A-B-C passes."""
        events = [
            create_wyckoff_event(
                WyckoffEventType.PSY,
                base_timestamp,
                Decimal("104.00"),
                Decimal("1.5"),
                VolumeQuality.HIGH,
            ),
            create_wyckoff_event(
                WyckoffEventType.BC,
                base_timestamp + timedelta(days=3),
                Decimal("108.00"),
                Decimal("2.5"),  # Climactic
                VolumeQuality.CLIMACTIC,
            ),
            create_wyckoff_event(
                WyckoffEventType.AR,
                base_timestamp + timedelta(days=6),
                Decimal("102.00"),
                Decimal("1.2"),
            ),
            create_wyckoff_event(
                WyckoffEventType.LPSY,
                base_timestamp + timedelta(days=15),
                Decimal("106.00"),
                Decimal("0.7"),  # Weak rally
                VolumeQuality.LOW,
            ),
        ]
        trading_range = create_trading_range_with_events(events)

        result = validate_utad_prerequisites(trading_range)

        assert result.is_valid is True
        assert result.pattern_type == "UTAD"
        assert "PSY" in result.prerequisite_events
        assert "BC" in result.prerequisite_events
        assert "LPSY" in result.prerequisite_events

    def test_utad_incomplete_distribution_fails(self, base_timestamp):
        """Test UTAD with incomplete Distribution phase fails."""
        events = [
            create_wyckoff_event(
                WyckoffEventType.PSY,
                base_timestamp,
                Decimal("104.00"),
                Decimal("1.5"),
            ),
            # Missing BC, AR, LPSY
        ]
        trading_range = create_trading_range_with_events(events)

        result = validate_utad_prerequisites(trading_range)

        assert result.is_valid is False
        assert "BC" in result.missing_prerequisites
        assert "LPSY" in result.missing_prerequisites


# ============================================================================
# Test: Event Sequence Validation (AC 8)
# ============================================================================


class TestEventSequenceValidation:
    """Tests for validate_event_sequence function."""

    def test_events_in_correct_order_valid(self, base_timestamp):
        """Test events in correct chronological order passes."""
        events = [
            create_wyckoff_event(WyckoffEventType.PS, base_timestamp),
            create_wyckoff_event(WyckoffEventType.SC, base_timestamp + timedelta(days=2)),
            create_wyckoff_event(WyckoffEventType.AR, base_timestamp + timedelta(days=5)),
        ]

        is_valid, violations = validate_event_sequence(events, ["PS", "SC", "AR"])

        assert is_valid is True
        assert len(violations) == 0

    def test_events_in_wrong_order_detected(self, base_timestamp):
        """Test events in wrong order - AR before SC detected."""
        events = [
            create_wyckoff_event(WyckoffEventType.PS, base_timestamp),
            create_wyckoff_event(
                WyckoffEventType.AR,
                base_timestamp + timedelta(days=2),  # AR before SC
            ),
            create_wyckoff_event(
                WyckoffEventType.SC,
                base_timestamp + timedelta(days=5),  # SC after AR
            ),
        ]

        is_valid, violations = validate_event_sequence(events, ["PS", "SC", "AR"])

        assert is_valid is False
        assert len(violations) > 0
        assert "AR" in violations[0] and "SC" in violations[0]


# ============================================================================
# Test: Volume Quality Validation (AC 11, 12)
# ============================================================================


class TestVolumeQualityValidation:
    """Tests for volume threshold validation."""

    def test_sc_climactic_volume_passes(self):
        """Test SC with volume_ratio >= 2.0 passes volume check."""
        thresholds = VolumeThresholds()

        assert thresholds.validate_volume_for_event(WyckoffEventType.SC, Decimal("2.0")) is True
        assert thresholds.validate_volume_for_event(WyckoffEventType.SC, Decimal("2.5")) is True

    def test_sc_non_climactic_volume_fails(self):
        """Test SC with volume_ratio < 2.0 fails volume check."""
        thresholds = VolumeThresholds()

        assert thresholds.validate_volume_for_event(WyckoffEventType.SC, Decimal("1.9")) is False
        assert thresholds.validate_volume_for_event(WyckoffEventType.SC, Decimal("1.5")) is False

    def test_spring_low_volume_passes(self):
        """Test Spring with volume_ratio <= 1.0 passes (low supply)."""
        thresholds = VolumeThresholds()

        assert thresholds.validate_volume_for_event(WyckoffEventType.SPRING, Decimal("0.5")) is True
        assert thresholds.validate_volume_for_event(WyckoffEventType.SPRING, Decimal("1.0")) is True

    def test_spring_high_volume_fails(self):
        """Test Spring with volume_ratio > 1.0 fails (too much supply)."""
        thresholds = VolumeThresholds()

        assert (
            thresholds.validate_volume_for_event(WyckoffEventType.SPRING, Decimal("1.1")) is False
        )
        assert (
            thresholds.validate_volume_for_event(WyckoffEventType.SPRING, Decimal("1.5")) is False
        )

    def test_sos_strong_volume_passes(self):
        """Test SOS with volume_ratio >= 1.5 passes (strong demand)."""
        thresholds = VolumeThresholds()

        assert thresholds.validate_volume_for_event(WyckoffEventType.SOS, Decimal("1.5")) is True
        assert thresholds.validate_volume_for_event(WyckoffEventType.SOS, Decimal("2.0")) is True

    def test_sos_weak_volume_fails(self):
        """Test SOS with volume_ratio < 1.5 fails (insufficient demand)."""
        thresholds = VolumeThresholds()

        assert thresholds.validate_volume_for_event(WyckoffEventType.SOS, Decimal("1.4")) is False

    def test_lps_drying_volume_passes(self):
        """Test LPS with volume_ratio <= 1.2 passes (drying up)."""
        thresholds = VolumeThresholds()

        assert thresholds.validate_volume_for_event(WyckoffEventType.LPS, Decimal("1.0")) is True
        assert thresholds.validate_volume_for_event(WyckoffEventType.LPS, Decimal("1.2")) is True

    def test_comparative_volume_st_less_than_sc(self, base_timestamp):
        """Test comparative volume: ST volume < SC volume."""
        events = [
            create_wyckoff_event(
                WyckoffEventType.SC,
                base_timestamp,
                volume_ratio=Decimal("2.5"),
            ),
            create_wyckoff_event(
                WyckoffEventType.ST,
                base_timestamp + timedelta(days=5),
                volume_ratio=Decimal("1.5"),  # Lower than SC
            ),
        ]

        is_valid, violations = validate_comparative_volume(events, [("ST", "SC")])

        assert is_valid is True
        assert len(violations) == 0

    def test_comparative_volume_st_higher_than_sc_fails(self, base_timestamp):
        """Test comparative volume fails when ST volume >= SC volume."""
        events = [
            create_wyckoff_event(
                WyckoffEventType.SC,
                base_timestamp,
                volume_ratio=Decimal("2.0"),
            ),
            create_wyckoff_event(
                WyckoffEventType.ST,
                base_timestamp + timedelta(days=5),
                volume_ratio=Decimal("2.0"),  # Equal to SC - VIOLATION
            ),
        ]

        is_valid, violations = validate_comparative_volume(events, [("ST", "SC")])

        assert is_valid is False
        assert "ST" in violations[0] and "SC" in violations[0]


# ============================================================================
# Test: Prerequisite Confidence Score (AC 14)
# ============================================================================


class TestPrerequisiteConfidenceScore:
    """Tests for prerequisite_confidence_score calculation."""

    def test_all_events_perfect_volume_score_high(self, complete_phase_ab_events):
        """Test all events present with good volume → score near 1.0."""
        trading_range = create_trading_range_with_events(complete_phase_ab_events)

        result = validate_spring_prerequisites(trading_range)

        assert result.is_valid is True
        assert result.prerequisite_confidence_score >= 0.7

    def test_missing_critical_event_score_zero(self, base_timestamp):
        """Test missing critical event (SC, Spring) → score 0.0."""
        events = [
            create_wyckoff_event(
                WyckoffEventType.PS,
                base_timestamp,
            ),
            # Missing SC - critical event
            create_wyckoff_event(
                WyckoffEventType.AR,
                base_timestamp + timedelta(days=5),
            ),
        ]
        trading_range = create_trading_range_with_events(events)

        result = validate_spring_prerequisites(trading_range)

        assert result.is_valid is False
        assert result.prerequisite_confidence_score == 0.0


# ============================================================================
# Test: Validation Modes (AC 7, 13, 15)
# ============================================================================


class TestValidationModes:
    """Tests for STRICT vs PERMISSIVE validation modes."""

    def test_strict_mode_missing_prerequisites_rejected(self, base_timestamp):
        """Test STRICT mode (default) rejects when prerequisites missing."""
        events = [
            create_wyckoff_event(WyckoffEventType.PS, base_timestamp),
            # Missing SC, AR
        ]
        trading_range = create_trading_range_with_events(events)

        result = validate_phase_prerequisites(
            pattern_type="SPRING",
            trading_range=trading_range,
            mode="STRICT",
        )

        assert result.is_valid is False
        assert result.validation_mode == "STRICT"
        assert result.rejection_reason is not None

    def test_permissive_mode_missing_prerequisites_warning(self, base_timestamp):
        """Test PERMISSIVE mode allows entry with warning when prerequisites missing."""
        events = [
            create_wyckoff_event(WyckoffEventType.PS, base_timestamp),
            # Missing SC, AR
        ]
        trading_range = create_trading_range_with_events(events)

        result = validate_phase_prerequisites(
            pattern_type="SPRING",
            trading_range=trading_range,
            mode="PERMISSIVE",
        )

        assert result.is_valid is True  # Allowed in PERMISSIVE
        assert result.validation_mode == "PERMISSIVE"
        assert result.warning_level is not None
        assert result.permissive_controls_applied is True

    def test_strict_is_default_mode(self, complete_phase_ab_events):
        """Test STRICT is default mode when not specified (AC 15)."""
        trading_range = create_trading_range_with_events(complete_phase_ab_events)

        result = validate_phase_prerequisites(
            pattern_type="SPRING",
            trading_range=trading_range,
            # mode not specified - should default to STRICT
        )

        assert result.validation_mode == "STRICT"

    def test_permissive_mode_controls_config(self):
        """Test PERMISSIVE mode risk controls configuration (AC 13)."""
        controls = PermissiveModeControls()

        assert controls.max_position_size_multiplier == Decimal("0.5")  # 50%
        assert controls.stop_distance_multiplier == Decimal("0.75")  # 25% tighter
        assert controls.allow_scaling is False
        assert controls.daily_warning_entry_limit == 2


# ============================================================================
# Test: Unified Validator Routing
# ============================================================================


class TestUnifiedValidatorRouting:
    """Tests for validate_phase_prerequisites routing."""

    def test_routes_spring_to_spring_validator(self, complete_phase_ab_events):
        """Test SPRING pattern routes to Spring validator."""
        trading_range = create_trading_range_with_events(complete_phase_ab_events)

        result = validate_phase_prerequisites(
            pattern_type="SPRING",
            trading_range=trading_range,
        )

        assert result.pattern_type == "SPRING"

    def test_routes_sos_to_sos_validator(self, complete_phase_c_events):
        """Test SOS pattern routes to SOS validator."""
        trading_range = create_trading_range_with_events(complete_phase_c_events)

        result = validate_phase_prerequisites(
            pattern_type="SOS",
            trading_range=trading_range,
        )

        assert result.pattern_type == "SOS"

    def test_routes_lps_to_lps_validator(self, complete_phase_d_events):
        """Test LPS pattern routes to LPS validator."""
        trading_range = create_trading_range_with_events(complete_phase_d_events)

        result = validate_phase_prerequisites(
            pattern_type="LPS",
            trading_range=trading_range,
        )

        assert result.pattern_type == "LPS"

    def test_unknown_pattern_returns_passing(self, complete_phase_ab_events):
        """Test unknown pattern type returns passing validation."""
        trading_range = create_trading_range_with_events(complete_phase_ab_events)

        result = validate_phase_prerequisites(
            pattern_type="UNKNOWN",
            trading_range=trading_range,
        )

        assert result.is_valid is True
        assert result.pattern_type == "UNKNOWN"

    def test_accepts_pattern_type_enum(self, complete_phase_ab_events):
        """Test accepts PatternType enum as input."""
        from src.models.risk_allocation import PatternType

        trading_range = create_trading_range_with_events(complete_phase_ab_events)

        result = validate_phase_prerequisites(
            pattern_type=PatternType.SPRING,
            trading_range=trading_range,
        )

        assert result.pattern_type == "SPRING"


# ============================================================================
# Test: TradingRange Event History Methods
# ============================================================================


class TestTradingRangeEventHistory:
    """Tests for TradingRange.event_history helper methods."""

    def test_add_wyckoff_event_maintains_order(self, base_timestamp):
        """Test add_wyckoff_event maintains chronological order."""
        trading_range = create_trading_range_with_events([])

        # Add events out of order
        event_ar = create_wyckoff_event(WyckoffEventType.AR, base_timestamp + timedelta(days=5))
        event_ps = create_wyckoff_event(WyckoffEventType.PS, base_timestamp)
        event_sc = create_wyckoff_event(WyckoffEventType.SC, base_timestamp + timedelta(days=2))

        trading_range.add_wyckoff_event(event_ar)
        trading_range.add_wyckoff_event(event_ps)
        trading_range.add_wyckoff_event(event_sc)

        # Should be sorted by timestamp
        assert trading_range.event_history[0].event_type == WyckoffEventType.PS
        assert trading_range.event_history[1].event_type == WyckoffEventType.SC
        assert trading_range.event_history[2].event_type == WyckoffEventType.AR

    def test_get_events_by_type(self, base_timestamp):
        """Test get_events_by_type returns matching events."""
        events = [
            create_wyckoff_event(WyckoffEventType.PS, base_timestamp),
            create_wyckoff_event(WyckoffEventType.SC, base_timestamp + timedelta(days=2)),
            create_wyckoff_event(WyckoffEventType.AR, base_timestamp + timedelta(days=5)),
        ]
        trading_range = create_trading_range_with_events(events)

        sc_events = trading_range.get_events_by_type("SC")

        assert len(sc_events) == 1
        assert sc_events[0].event_type == WyckoffEventType.SC

    def test_has_event(self, base_timestamp):
        """Test has_event returns correct boolean."""
        events = [
            create_wyckoff_event(WyckoffEventType.PS, base_timestamp),
            create_wyckoff_event(WyckoffEventType.SC, base_timestamp + timedelta(days=2)),
        ]
        trading_range = create_trading_range_with_events(events)

        assert trading_range.has_event("PS") is True
        assert trading_range.has_event("SC") is True
        assert trading_range.has_event("AR") is False
        assert trading_range.has_event("SPRING") is False
