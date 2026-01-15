"""
Unit tests for position factory utility (Story 18.5)

Tests cover:
- Position creation from signal with allocation plan
- Field mapping correctness
- Decimal precision preservation
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from src.campaign_management.utils.position_factory import create_position_from_signal
from src.models.allocation import AllocationPlan
from src.models.signal import (
    ConfidenceComponents,
    TargetLevels,
    TradeSignal,
)
from src.models.validation import ValidationChain


def create_test_signal(
    entry_price: Decimal = Decimal("150.00"),
    stop_loss: Decimal = Decimal("148.00"),
    position_size: Decimal = Decimal("100"),
    risk_amount: Decimal = Decimal("200.00"),
    pattern_type: str = "SPRING",
) -> TradeSignal:
    """Create a test TradeSignal with default values."""
    # Calculate notional value for stocks: entry_price * position_size
    notional = entry_price * position_size

    # Target at 156.00, entry at 150.00, stop at 148.00
    # R-multiple = (156-150) / (150-148) = 6/2 = 3.0
    target = Decimal("156.00")
    r_mult = (target - entry_price) / (entry_price - stop_loss)

    return TradeSignal(
        id=uuid4(),
        symbol="AAPL",
        asset_class="STOCK",
        pattern_type=pattern_type,  # type: ignore
        phase="C",
        timeframe="1h",
        entry_price=entry_price,
        stop_loss=stop_loss,
        target_levels=TargetLevels(primary_target=target),
        position_size=position_size,
        position_size_unit="SHARES",
        notional_value=notional,
        risk_amount=risk_amount,
        r_multiple=r_mult,
        confidence_score=85,
        confidence_components=ConfidenceComponents(
            pattern_confidence=88,
            phase_confidence=82,
            volume_confidence=80,
            overall_confidence=85,
        ),
        validation_chain=ValidationChain(
            pattern_id=uuid4(),
        ),
        timestamp=datetime.now(UTC),
    )


def create_test_allocation_plan(
    actual_risk_pct: Decimal = Decimal("2.0"),
    approved: bool = True,
) -> AllocationPlan:
    """Create a test AllocationPlan with default values."""
    return AllocationPlan(
        id=uuid4(),
        campaign_id=uuid4(),
        signal_id=uuid4(),
        pattern_type="SPRING",
        bmad_allocation_pct=Decimal("0.40"),
        target_risk_pct=Decimal("2.0"),
        actual_risk_pct=actual_risk_pct,
        position_size_shares=Decimal("100"),
        allocation_used=Decimal("2.0"),
        remaining_budget=Decimal("3.0"),
        is_rebalanced=False,
        approved=approved,
    )


class TestCreatePositionFromSignal:
    """Tests for create_position_from_signal function."""

    def test_creates_position_with_correct_signal_id(self):
        """Should create position with signal_id from signal."""
        signal = create_test_signal()
        allocation = create_test_allocation_plan()

        position = create_position_from_signal(signal, allocation)

        assert position.signal_id == signal.id

    def test_creates_position_with_correct_pattern_type(self):
        """Should create position with pattern_type from signal."""
        signal = create_test_signal(pattern_type="SOS")
        allocation = create_test_allocation_plan()

        position = create_position_from_signal(signal, allocation)

        assert position.pattern_type == "SOS"

    def test_creates_position_with_correct_entry_date(self):
        """Should create position with entry_date from signal timestamp."""
        signal = create_test_signal()
        allocation = create_test_allocation_plan()

        position = create_position_from_signal(signal, allocation)

        assert position.entry_date == signal.timestamp

    def test_creates_position_with_correct_entry_price(self):
        """Should create position with entry_price from signal."""
        signal = create_test_signal(entry_price=Decimal("155.50"))
        allocation = create_test_allocation_plan()

        position = create_position_from_signal(signal, allocation)

        assert position.entry_price == Decimal("155.50")

    def test_creates_position_with_correct_shares(self):
        """Should create position with shares from signal position_size."""
        signal = create_test_signal(position_size=Decimal("250"))
        allocation = create_test_allocation_plan()

        position = create_position_from_signal(signal, allocation)

        assert position.shares == Decimal("250")

    def test_creates_position_with_correct_stop_loss(self):
        """Should create position with stop_loss from signal."""
        signal = create_test_signal(stop_loss=Decimal("145.00"))
        allocation = create_test_allocation_plan()

        position = create_position_from_signal(signal, allocation)

        assert position.stop_loss == Decimal("145.00")

    def test_creates_position_with_correct_target_price(self):
        """Should create position with target_price from signal's primary target."""
        signal = create_test_signal()
        allocation = create_test_allocation_plan()

        position = create_position_from_signal(signal, allocation)

        assert position.target_price == signal.target_levels.primary_target

    def test_creates_position_with_current_price_equals_entry(self):
        """Should set current_price to entry_price initially."""
        signal = create_test_signal(entry_price=Decimal("150.25"))
        allocation = create_test_allocation_plan()

        position = create_position_from_signal(signal, allocation)

        assert position.current_price == position.entry_price

    def test_creates_position_with_zero_pnl(self):
        """Should set current_pnl to zero initially."""
        signal = create_test_signal()
        allocation = create_test_allocation_plan()

        position = create_position_from_signal(signal, allocation)

        assert position.current_pnl == Decimal("0.00")

    def test_creates_position_with_open_status(self):
        """Should set status to OPEN."""
        signal = create_test_signal()
        allocation = create_test_allocation_plan()

        position = create_position_from_signal(signal, allocation)

        assert position.status == "OPEN"

    def test_creates_position_with_allocation_from_plan(self):
        """Should use allocation_percent from allocation plan."""
        signal = create_test_signal()
        allocation = create_test_allocation_plan(actual_risk_pct=Decimal("1.5"))

        position = create_position_from_signal(signal, allocation)

        assert position.allocation_percent == Decimal("1.5")

    def test_creates_position_with_risk_amount_from_signal(self):
        """Should use risk_amount from signal."""
        signal = create_test_signal(risk_amount=Decimal("300.00"))
        allocation = create_test_allocation_plan()

        position = create_position_from_signal(signal, allocation)

        assert position.risk_amount == Decimal("300.00")


class TestPositionFactoryIntegration:
    """Integration tests for position factory with different scenarios."""

    def test_spring_position_creation(self):
        """Should create correct position for Spring entry."""
        signal = create_test_signal(pattern_type="SPRING")
        allocation = create_test_allocation_plan(actual_risk_pct=Decimal("2.0"))

        position = create_position_from_signal(signal, allocation)

        assert position.pattern_type == "SPRING"
        assert position.allocation_percent == Decimal("2.0")

    def test_sos_position_creation(self):
        """Should create correct position for SOS entry."""
        signal = create_test_signal(pattern_type="SOS")
        allocation = create_test_allocation_plan(actual_risk_pct=Decimal("1.5"))

        position = create_position_from_signal(signal, allocation)

        assert position.pattern_type == "SOS"
        assert position.allocation_percent == Decimal("1.5")

    def test_lps_position_creation(self):
        """Should create correct position for LPS entry."""
        signal = create_test_signal(pattern_type="LPS")
        allocation = create_test_allocation_plan(actual_risk_pct=Decimal("1.5"))

        position = create_position_from_signal(signal, allocation)

        assert position.pattern_type == "LPS"
        assert position.allocation_percent == Decimal("1.5")

    def test_decimal_precision_preserved(self):
        """Should preserve Decimal precision for valid model constraints."""
        # Use values within CampaignPosition model constraints:
        # - allocation_percent: max_digits=5, decimal_places=2
        # - risk_amount: decimal_places=2
        # - shares: decimal_places=8, max_digits=18
        signal = create_test_signal(
            position_size=Decimal("100.12345678"),  # 8 decimal places OK
            risk_amount=Decimal("225.12"),  # 2 decimal places required
        )
        allocation = create_test_allocation_plan(actual_risk_pct=Decimal("1.75"))  # 5 digits max

        position = create_position_from_signal(signal, allocation)

        assert position.shares == Decimal("100.12345678")
        assert position.risk_amount == Decimal("225.12")
        assert position.allocation_percent == Decimal("1.75")
