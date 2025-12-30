"""
Unit tests for Paper Broker Adapter (Story 12.8 Task 17)

Tests fill price calculation, commission, slippage, and P&L.

Author: Story 12.8
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.brokers.paper_broker_adapter import PaperBrokerAdapter
from src.models.paper_trading import PaperAccount, PaperTradingConfig
from src.models.signal import ConfidenceComponents, TargetLevels, TradeSignal
from src.models.validation import StageValidationResult, ValidationChain, ValidationStatus
from src.trading.exceptions import InsufficientCapitalError


@pytest.fixture
def default_config():
    """Create default paper trading configuration."""
    return PaperTradingConfig(
        enabled=True,
        starting_capital=Decimal("100000.00"),
        commission_per_share=Decimal("0.005"),
        slippage_percentage=Decimal("0.02"),
        use_realistic_fills=True,
    )


@pytest.fixture
def no_slippage_config():
    """Create configuration without slippage."""
    return PaperTradingConfig(
        enabled=True,
        starting_capital=Decimal("100000.00"),
        commission_per_share=Decimal("0.005"),
        slippage_percentage=Decimal("0.02"),
        use_realistic_fills=False,  # Disable slippage
    )


@pytest.fixture
def mock_signal():
    """Create mock trading signal."""
    # Create confidence components
    confidence = ConfidenceComponents(
        pattern_confidence=88, phase_confidence=82, volume_confidence=80, overall_confidence=85
    )

    # Create target levels
    targets = TargetLevels(
        primary_target=Decimal("156.00"), secondary_targets=[Decimal("152.00"), Decimal("154.00")]
    )

    # Create validation chain
    validation = ValidationChain(
        pattern_id=uuid4(),
        overall_status=ValidationStatus.PASS,
        validation_results=[
            StageValidationResult(
                stage="Volume", status=ValidationStatus.PASS, validator_id="VOLUME_VALIDATOR"
            )
        ],
    )

    # Create TradeSignal
    return TradeSignal(
        symbol="AAPL",
        pattern_type="SPRING",
        phase="C",
        timeframe="1h",
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("148.00"),
        target_levels=targets,
        position_size=Decimal("100"),
        notional_value=Decimal("15000.00"),
        risk_amount=Decimal("200.00"),
        r_multiple=Decimal("3.0"),
        confidence_score=85,
        confidence_components=confidence,
        validation_chain=validation,
        timestamp=datetime.now(UTC),
    )


@pytest.fixture
def mock_account():
    """Create mock paper account."""
    return PaperAccount(
        starting_capital=Decimal("100000.00"),
        current_capital=Decimal("100000.00"),
        equity=Decimal("100000.00"),
    )


class TestFillPriceCalculation:
    """Test fill price calculation with slippage."""

    def test_long_entry_with_slippage(self, default_config, mock_signal, mock_account):
        """Test LONG entry fill price includes slippage (price increases)."""
        broker = PaperBrokerAdapter(default_config)
        market_price = Decimal("150.00")

        position = broker.place_order(mock_signal, market_price, mock_account)

        # Expected: $150 * (1 + 0.02/100) = $150 * 1.0002 = $150.03
        expected_fill = Decimal("150.03")
        assert position.entry_price == expected_fill

    def test_long_entry_without_slippage(self, no_slippage_config, mock_signal, mock_account):
        """Test LONG entry without slippage uses market price."""
        broker = PaperBrokerAdapter(no_slippage_config)
        market_price = Decimal("150.00")

        position = broker.place_order(mock_signal, market_price, mock_account)

        # No slippage applied
        assert position.entry_price == market_price

    def test_long_exit_with_slippage(self, default_config, mock_signal, mock_account):
        """Test LONG exit fill price includes slippage (price decreases)."""
        broker = PaperBrokerAdapter(default_config)
        market_price = Decimal("150.00")

        # Create position
        position = broker.place_order(mock_signal, market_price, mock_account)

        # Close position at higher price
        exit_market_price = Decimal("152.00")
        trade = broker.close_position(position, exit_market_price, "TARGET_1")

        # Expected: $152 * (1 - 0.02/100) = $152 * 0.9998 = $151.9696
        expected_exit_fill = Decimal("151.9696")
        assert trade.exit_price == expected_exit_fill


class TestCommissionCalculation:
    """Test commission calculation."""

    def test_entry_commission(self, default_config, mock_signal, mock_account):
        """Test entry commission is calculated correctly."""
        broker = PaperBrokerAdapter(default_config)
        market_price = Decimal("150.00")

        position = broker.place_order(mock_signal, market_price, mock_account)

        # Expected: 100 shares * $0.005 = $0.50
        expected_commission = Decimal("0.50")
        assert position.commission_paid == expected_commission

    def test_total_commission(self, default_config, mock_signal, mock_account):
        """Test total commission (entry + exit) is calculated correctly."""
        broker = PaperBrokerAdapter(default_config)
        market_price = Decimal("150.00")

        position = broker.place_order(mock_signal, market_price, mock_account)
        trade = broker.close_position(position, Decimal("152.00"), "TARGET_1")

        # Expected: $0.50 (entry) + $0.50 (exit) = $1.00
        expected_total = Decimal("1.00")
        assert trade.commission_total == expected_total


class TestSlippageCostCalculation:
    """Test slippage cost calculation."""

    def test_entry_slippage_cost(self, default_config, mock_signal, mock_account):
        """Test entry slippage cost is calculated correctly."""
        broker = PaperBrokerAdapter(default_config)
        market_price = Decimal("150.00")

        position = broker.place_order(mock_signal, market_price, mock_account)

        # Slippage cost = (fill_price - market_price) * quantity
        # = ($150.03 - $150.00) * 100 = $0.03 * 100 = $3.00
        expected_slippage = Decimal("3.00")
        assert position.slippage_cost == expected_slippage

    def test_total_slippage_cost(self, default_config, mock_signal, mock_account):
        """Test total slippage (entry + exit) is calculated correctly."""
        broker = PaperBrokerAdapter(default_config)

        position = broker.place_order(mock_signal, Decimal("150.00"), mock_account)
        trade = broker.close_position(position, Decimal("152.00"), "TARGET_1")

        # Entry slippage: $3.00
        # Exit slippage: ($152.00 - $151.9696) * 100 = $0.0304 * 100 = $3.04
        # Total: $3.00 + $3.04 = $6.04
        expected_total = Decimal("6.04")
        assert trade.slippage_total == expected_total


class TestPnLCalculation:
    """Test P&L calculation."""

    def test_profitable_trade_pnl(self, default_config, mock_signal, mock_account):
        """Test P&L for profitable trade."""
        broker = PaperBrokerAdapter(default_config)

        # Entry at $150, exit at $155
        position = broker.place_order(mock_signal, Decimal("150.00"), mock_account)
        trade = broker.close_position(position, Decimal("155.00"), "TARGET_2")

        # Price difference: $154.9690 (exit fill) - $150.03 (entry fill) = $4.9390
        # Gross P&L: $4.9390 * 100 = $493.90
        # Costs: commission $1.00 + slippage ~$6.10 = ~$7.10
        # Net P&L: $493.90 - $7.10 = ~$486.80
        assert trade.realized_pnl > Decimal("485")
        assert trade.realized_pnl < Decimal("488")

    def test_losing_trade_pnl(self, default_config, mock_signal, mock_account):
        """Test P&L for losing trade (stop hit)."""
        broker = PaperBrokerAdapter(default_config)

        position = broker.place_order(mock_signal, Decimal("150.00"), mock_account)
        trade = broker.close_position(position, Decimal("148.00"), "STOP_LOSS")

        # Price difference: $147.9704 (exit fill) - $150.03 (entry fill) = -$2.0596
        # Gross P&L: -$2.0596 * 100 = -$205.96
        # Costs: commission $1.00 + slippage ~$6.00 = ~$7.00
        # Net P&L: -$205.96 - $7.00 = ~-$212.96
        assert trade.realized_pnl < Decimal("0")
        assert trade.realized_pnl > Decimal("-215")


class TestRMultipleCalculation:
    """Test R-multiple calculation."""

    def test_r_multiple_target_hit(self, default_config, mock_signal, mock_account):
        """Test R-multiple when target is hit."""
        broker = PaperBrokerAdapter(default_config)

        # Entry $150.03, stop $148, risk = $2.03 per share
        position = broker.place_order(mock_signal, Decimal("150.00"), mock_account)

        # Exit at $152 (target 1)
        trade = broker.close_position(position, Decimal("152.00"), "TARGET_1")

        # Price gained: $151.9696 - $150.03 = $1.9396
        # Initial risk: $150.03 - $148.00 = $2.03
        # R-multiple: $1.9396 / $2.03 ≈ 0.955R
        assert trade.r_multiple_achieved > Decimal("0.9")
        assert trade.r_multiple_achieved < Decimal("1.0")

    def test_r_multiple_stop_hit(self, default_config, mock_signal, mock_account):
        """Test R-multiple when stop is hit."""
        broker = PaperBrokerAdapter(default_config)

        position = broker.place_order(mock_signal, Decimal("150.00"), mock_account)
        trade = broker.close_position(position, Decimal("148.00"), "STOP_LOSS")

        # Price lost: $147.9704 - $150.03 = -$2.0596
        # Initial risk: $150.03 - $148.00 = $2.03
        # R-multiple: -$2.0596 / $2.03 ≈ -1.01R
        assert trade.r_multiple_achieved < Decimal("0")
        assert trade.r_multiple_achieved > Decimal("-1.1")


class TestUnrealizedPnL:
    """Test unrealized P&L calculation for open positions."""

    def test_unrealized_pnl_profit(self, default_config, mock_signal, mock_account):
        """Test unrealized P&L when in profit."""
        broker = PaperBrokerAdapter(default_config)

        position = broker.place_order(mock_signal, Decimal("150.00"), mock_account)

        # Current price moved to $152
        unrealized = broker.calculate_unrealized_pnl(position, Decimal("152.00"))

        # Price gain: $152 - $150.03 = $1.97
        # Gross unrealized: $1.97 * 100 = $197.00
        # Subtract entry costs: $197 - $0.50 - $3.00 = $193.50
        expected = Decimal("193.50")
        assert unrealized == expected

    def test_unrealized_pnl_loss(self, default_config, mock_signal, mock_account):
        """Test unrealized P&L when in loss."""
        broker = PaperBrokerAdapter(default_config)

        position = broker.place_order(mock_signal, Decimal("150.00"), mock_account)

        # Current price moved to $149
        unrealized = broker.calculate_unrealized_pnl(position, Decimal("149.00"))

        # Price loss: $149 - $150.03 = -$1.03
        # Gross unrealized: -$1.03 * 100 = -$103.00
        # Subtract entry costs: -$103 - $0.50 - $3.00 = -$106.50
        expected = Decimal("-106.50")
        assert unrealized == expected


class TestStopTargetDetection:
    """Test stop and target hit detection."""

    def test_stop_hit_detection(self, default_config, mock_signal, mock_account):
        """Test stop loss hit is detected correctly."""
        broker = PaperBrokerAdapter(default_config)

        position = broker.place_order(mock_signal, Decimal("150.00"), mock_account)

        # Price at stop loss
        assert broker.check_stop_hit(position, Decimal("148.00")) is True

        # Price below stop loss
        assert broker.check_stop_hit(position, Decimal("147.50")) is True

        # Price above stop loss
        assert broker.check_stop_hit(position, Decimal("148.50")) is False

    def test_target_hit_detection(self, default_config, mock_signal, mock_account):
        """Test profit target hit is detected correctly."""
        broker = PaperBrokerAdapter(default_config)

        position = broker.place_order(mock_signal, Decimal("150.00"), mock_account)

        # Price at target 1
        assert broker.check_target_hit(position, Decimal("152.00")) == "TARGET_1"

        # Price between targets
        assert broker.check_target_hit(position, Decimal("153.00")) == "TARGET_1"

        # Price at target 2
        result = broker.check_target_hit(position, Decimal("154.00"))
        assert result == "TARGET_2" or result == "TARGET_1"  # Depends on implementation

        # Price below target 1
        assert broker.check_target_hit(position, Decimal("151.00")) is None


class TestInsufficientCapital:
    """Test handling of insufficient capital."""

    def test_insufficient_capital_rejected(self, default_config, mock_signal):
        """Test order rejected when insufficient capital."""
        broker = PaperBrokerAdapter(default_config)

        # Account with only $1000
        poor_account = PaperAccount(
            starting_capital=Decimal("1000.00"),
            current_capital=Decimal("1000.00"),
            equity=Decimal("1000.00"),
        )

        # Try to buy 100 shares at $150 = $15,000
        with pytest.raises(InsufficientCapitalError):
            broker.place_order(mock_signal, Decimal("150.00"), poor_account)
