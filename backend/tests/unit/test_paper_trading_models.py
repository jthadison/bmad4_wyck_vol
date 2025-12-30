"""
Unit tests for Paper Trading Models (Story 12.8)

Tests Pydantic validation, decimal precision, and UTC timestamp handling.

Author: Story 12.8
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from src.models.paper_trading import (
    PaperAccount,
    PaperPosition,
    PaperTrade,
    PaperTradingConfig,
)


class TestPaperTradingConfig:
    """Test PaperTradingConfig model validation."""

    def test_default_values(self):
        """Test default configuration values."""
        config = PaperTradingConfig()

        assert config.enabled is False
        assert config.starting_capital == Decimal("100000.00")
        assert config.commission_per_share == Decimal("0.005")
        assert config.slippage_percentage == Decimal("0.02")
        assert config.use_realistic_fills is True
        assert isinstance(config.created_at, datetime)

    def test_custom_values(self):
        """Test custom configuration values."""
        config = PaperTradingConfig(
            enabled=True,
            starting_capital=Decimal("50000.00"),
            commission_per_share=Decimal("0.01"),
            slippage_percentage=Decimal("0.05"),
            use_realistic_fills=False,
        )

        assert config.enabled is True
        assert config.starting_capital == Decimal("50000.00")
        assert config.commission_per_share == Decimal("0.01")
        assert config.slippage_percentage == Decimal("0.05")
        assert config.use_realistic_fills is False

    def test_decimal_precision_validation(self):
        """Test decimal values are quantized to 8 decimal places."""
        config = PaperTradingConfig(
            starting_capital=Decimal("100000.123456789"),  # 9 decimal places
            commission_per_share=Decimal("0.005123456789"),
        )

        # Should be quantized to 8 decimal places
        assert config.starting_capital == Decimal("100000.12345679")
        assert config.commission_per_share == Decimal("0.00512346")

    def test_negative_starting_capital_rejected(self):
        """Test negative starting capital is rejected."""
        with pytest.raises(ValueError):
            PaperTradingConfig(starting_capital=Decimal("-1000"))

    def test_negative_commission_rejected(self):
        """Test negative commission is rejected."""
        with pytest.raises(ValueError):
            PaperTradingConfig(commission_per_share=Decimal("-0.01"))


class TestPaperPosition:
    """Test PaperPosition model validation."""

    def test_valid_position_creation(self):
        """Test creating a valid paper position."""
        signal_id = uuid4()
        position = PaperPosition(
            signal_id=signal_id,
            symbol="AAPL",
            entry_time=datetime.now(UTC),
            entry_price=Decimal("150.03"),
            quantity=Decimal("100"),
            stop_loss=Decimal("148.00"),
            target_1=Decimal("152.00"),
            target_2=Decimal("154.00"),
            current_price=Decimal("151.50"),
            unrealized_pnl=Decimal("147.00"),
            commission_paid=Decimal("0.50"),
            slippage_cost=Decimal("3.00"),
        )

        assert isinstance(position.id, UUID)
        assert position.signal_id == signal_id
        assert position.symbol == "AAPL"
        assert position.entry_price == Decimal("150.03")
        assert position.quantity == Decimal("100")
        assert position.status == "OPEN"
        assert position.unrealized_pnl == Decimal("147.00")

    def test_decimal_precision_validation(self):
        """Test decimal precision is enforced."""
        signal_id = uuid4()
        position = PaperPosition(
            signal_id=signal_id,
            symbol="AAPL",
            entry_time=datetime.now(UTC),
            entry_price=Decimal("150.123456789"),  # 9 decimal places
            quantity=Decimal("100"),
            stop_loss=Decimal("148.00"),
            target_1=Decimal("152.00"),
            target_2=Decimal("154.00"),
            current_price=Decimal("151.50"),
            unrealized_pnl=Decimal("147.00"),
            commission_paid=Decimal("0.50"),
            slippage_cost=Decimal("3.00"),
        )

        # Should be quantized to 8 decimal places
        assert position.entry_price == Decimal("150.12345679")

    def test_invalid_status_rejected(self):
        """Test invalid status values are rejected."""
        signal_id = uuid4()
        with pytest.raises(ValueError):
            PaperPosition(
                signal_id=signal_id,
                symbol="AAPL",
                entry_time=datetime.now(UTC),
                entry_price=Decimal("150.00"),
                quantity=Decimal("100"),
                stop_loss=Decimal("148.00"),
                target_1=Decimal("152.00"),
                target_2=Decimal("154.00"),
                current_price=Decimal("151.00"),
                unrealized_pnl=Decimal("100.00"),
                status="INVALID_STATUS",  # Invalid
                commission_paid=Decimal("0.50"),
                slippage_cost=Decimal("3.00"),
            )

    def test_zero_price_rejected(self):
        """Test zero prices are rejected."""
        signal_id = uuid4()
        with pytest.raises(ValueError):
            PaperPosition(
                signal_id=signal_id,
                symbol="AAPL",
                entry_time=datetime.now(UTC),
                entry_price=Decimal("0"),  # Invalid
                quantity=Decimal("100"),
                stop_loss=Decimal("148.00"),
                target_1=Decimal("152.00"),
                target_2=Decimal("154.00"),
                current_price=Decimal("151.00"),
                unrealized_pnl=Decimal("100.00"),
                commission_paid=Decimal("0.50"),
                slippage_cost=Decimal("3.00"),
            )

    def test_negative_quantity_rejected(self):
        """Test negative quantity is rejected."""
        signal_id = uuid4()
        with pytest.raises(ValueError):
            PaperPosition(
                signal_id=signal_id,
                symbol="AAPL",
                entry_time=datetime.now(UTC),
                entry_price=Decimal("150.00"),
                quantity=Decimal("-100"),  # Invalid
                stop_loss=Decimal("148.00"),
                target_1=Decimal("152.00"),
                target_2=Decimal("154.00"),
                current_price=Decimal("151.00"),
                unrealized_pnl=Decimal("100.00"),
                commission_paid=Decimal("0.50"),
                slippage_cost=Decimal("3.00"),
            )


class TestPaperTrade:
    """Test PaperTrade model validation."""

    def test_valid_trade_creation(self):
        """Test creating a valid paper trade."""
        position_id = uuid4()
        signal_id = uuid4()
        trade = PaperTrade(
            position_id=position_id,
            signal_id=signal_id,
            symbol="AAPL",
            entry_time=datetime.now(UTC),
            entry_price=Decimal("150.03"),
            exit_time=datetime.now(UTC),
            exit_price=Decimal("152.05"),
            quantity=Decimal("100"),
            realized_pnl=Decimal("198.50"),
            r_multiple_achieved=Decimal("1.52"),
            commission_total=Decimal("1.00"),
            slippage_total=Decimal("5.00"),
            exit_reason="TARGET_1",
        )

        assert isinstance(trade.id, UUID)
        assert trade.position_id == position_id
        assert trade.signal_id == signal_id
        assert trade.symbol == "AAPL"
        assert trade.realized_pnl == Decimal("198.50")
        assert trade.r_multiple_achieved == Decimal("1.52")
        assert trade.exit_reason == "TARGET_1"

    def test_all_exit_reasons_valid(self):
        """Test all valid exit reasons are accepted."""
        exit_reasons = ["STOP_LOSS", "TARGET_1", "TARGET_2", "MANUAL", "EXPIRED"]
        position_id = uuid4()
        signal_id = uuid4()

        for reason in exit_reasons:
            trade = PaperTrade(
                position_id=position_id,
                signal_id=signal_id,
                symbol="AAPL",
                entry_time=datetime.now(UTC),
                entry_price=Decimal("150.00"),
                exit_time=datetime.now(UTC),
                exit_price=Decimal("152.00"),
                quantity=Decimal("100"),
                realized_pnl=Decimal("200.00"),
                r_multiple_achieved=Decimal("1.50"),
                commission_total=Decimal("1.00"),
                slippage_total=Decimal("5.00"),
                exit_reason=reason,
            )
            assert trade.exit_reason == reason

    def test_invalid_exit_reason_rejected(self):
        """Test invalid exit reason is rejected."""
        position_id = uuid4()
        signal_id = uuid4()
        with pytest.raises(ValueError):
            PaperTrade(
                position_id=position_id,
                signal_id=signal_id,
                symbol="AAPL",
                entry_time=datetime.now(UTC),
                entry_price=Decimal("150.00"),
                exit_time=datetime.now(UTC),
                exit_price=Decimal("152.00"),
                quantity=Decimal("100"),
                realized_pnl=Decimal("200.00"),
                r_multiple_achieved=Decimal("1.50"),
                commission_total=Decimal("1.00"),
                slippage_total=Decimal("5.00"),
                exit_reason="INVALID_REASON",  # Invalid
            )

    def test_decimal_precision_validation(self):
        """Test decimal precision is enforced for all Decimal fields."""
        position_id = uuid4()
        signal_id = uuid4()
        trade = PaperTrade(
            position_id=position_id,
            signal_id=signal_id,
            symbol="AAPL",
            entry_time=datetime.now(UTC),
            entry_price=Decimal("150.123456789"),  # 9 decimal places
            exit_time=datetime.now(UTC),
            exit_price=Decimal("152.987654321"),  # 9 decimal places
            quantity=Decimal("100"),
            realized_pnl=Decimal("198.123456789"),
            r_multiple_achieved=Decimal("1.523456789"),
            commission_total=Decimal("1.123456789"),
            slippage_total=Decimal("5.987654321"),
            exit_reason="TARGET_1",
        )

        # All should be quantized to 8 decimal places
        assert trade.entry_price == Decimal("150.12345679")
        assert trade.exit_price == Decimal("152.98765432")
        assert trade.realized_pnl == Decimal("198.12345679")
        assert trade.r_multiple_achieved == Decimal("1.52345679")


class TestPaperAccount:
    """Test PaperAccount model validation."""

    def test_default_values(self):
        """Test default account values."""
        account = PaperAccount(
            starting_capital=Decimal("100000.00"),
            current_capital=Decimal("100000.00"),
            equity=Decimal("100000.00"),
        )

        assert account.starting_capital == Decimal("100000.00")
        assert account.total_realized_pnl == Decimal("0")
        assert account.total_unrealized_pnl == Decimal("0")
        assert account.total_commission_paid == Decimal("0")
        assert account.total_slippage_cost == Decimal("0")
        assert account.total_trades == 0
        assert account.winning_trades == 0
        assert account.losing_trades == 0
        assert account.win_rate == Decimal("0")
        assert account.average_r_multiple == Decimal("0")
        assert account.max_drawdown == Decimal("0")
        assert account.current_heat == Decimal("0")
        assert account.paper_trading_start_date is None

    def test_with_trading_activity(self):
        """Test account with trading activity."""
        account = PaperAccount(
            starting_capital=Decimal("100000.00"),
            current_capital=Decimal("98500.00"),
            equity=Decimal("99200.00"),
            total_realized_pnl=Decimal("500.00"),
            total_unrealized_pnl=Decimal("700.00"),
            total_commission_paid=Decimal("25.50"),
            total_slippage_cost=Decimal("74.50"),
            total_trades=15,
            winning_trades=9,
            losing_trades=6,
            win_rate=Decimal("60.00"),
            average_r_multiple=Decimal("1.75"),
            max_drawdown=Decimal("3.25"),
            current_heat=Decimal("8.50"),
            paper_trading_start_date=datetime(2025, 1, 1, tzinfo=UTC),
        )

        assert account.total_trades == 15
        assert account.winning_trades == 9
        assert account.losing_trades == 6
        assert account.win_rate == Decimal("60.00")
        assert account.average_r_multiple == Decimal("1.75")
        assert account.current_heat == Decimal("8.50")
        assert account.paper_trading_start_date is not None

    def test_win_rate_bounded(self):
        """Test win rate is bounded between 0 and 100."""
        with pytest.raises(ValueError):
            PaperAccount(
                starting_capital=Decimal("100000.00"),
                current_capital=Decimal("100000.00"),
                equity=Decimal("100000.00"),
                win_rate=Decimal("150.00"),  # Invalid: > 100
            )

    def test_current_heat_bounded(self):
        """Test current heat is bounded between 0 and 100."""
        with pytest.raises(ValueError):
            PaperAccount(
                starting_capital=Decimal("100000.00"),
                current_capital=Decimal("100000.00"),
                equity=Decimal("100000.00"),
                current_heat=Decimal("150.00"),  # Invalid: > 100
            )

    def test_negative_total_trades_rejected(self):
        """Test negative total trades is rejected."""
        with pytest.raises(ValueError):
            PaperAccount(
                starting_capital=Decimal("100000.00"),
                current_capital=Decimal("100000.00"),
                equity=Decimal("100000.00"),
                total_trades=-5,  # Invalid
            )

    def test_decimal_precision_validation(self):
        """Test decimal precision is enforced for all Decimal fields."""
        account = PaperAccount(
            starting_capital=Decimal("100000.123456789"),
            current_capital=Decimal("98500.987654321"),
            equity=Decimal("99200.555555555"),
            total_realized_pnl=Decimal("500.123456789"),
            total_unrealized_pnl=Decimal("700.987654321"),
        )

        # All should be quantized to 8 decimal places
        assert account.starting_capital == Decimal("100000.12345679")
        assert account.current_capital == Decimal("98500.98765432")
        assert account.equity == Decimal("99200.55555556")


class TestModelIntegration:
    """Test integration between models."""

    def test_position_to_trade_conversion(self):
        """Test creating a trade from a closed position."""
        signal_id = uuid4()

        # Create position
        position = PaperPosition(
            signal_id=signal_id,
            symbol="AAPL",
            entry_time=datetime.now(UTC),
            entry_price=Decimal("150.03"),
            quantity=Decimal("100"),
            stop_loss=Decimal("148.00"),
            target_1=Decimal("152.00"),
            target_2=Decimal("154.00"),
            current_price=Decimal("152.05"),
            unrealized_pnl=Decimal("202.00"),
            commission_paid=Decimal("0.50"),
            slippage_cost=Decimal("3.00"),
        )

        # Create corresponding trade
        trade = PaperTrade(
            position_id=position.id,
            signal_id=position.signal_id,
            symbol=position.symbol,
            entry_time=position.entry_time,
            entry_price=position.entry_price,
            exit_time=datetime.now(UTC),
            exit_price=Decimal("152.05"),
            quantity=position.quantity,
            realized_pnl=Decimal("198.50"),  # After exit costs
            r_multiple_achieved=Decimal("1.52"),
            commission_total=Decimal("1.00"),  # Entry + exit
            slippage_total=Decimal("5.00"),  # Entry + exit
            exit_reason="TARGET_1",
        )

        # Verify consistency
        assert trade.position_id == position.id
        assert trade.signal_id == position.signal_id
        assert trade.symbol == position.symbol
        assert trade.entry_time == position.entry_time
        assert trade.entry_price == position.entry_price
        assert trade.quantity == position.quantity

    def test_account_metrics_consistency(self):
        """Test account metrics are internally consistent."""
        account = PaperAccount(
            starting_capital=Decimal("100000.00"),
            current_capital=Decimal("98500.00"),
            equity=Decimal("99200.00"),
            total_realized_pnl=Decimal("500.00"),
            total_unrealized_pnl=Decimal("700.00"),
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            win_rate=Decimal("60.00"),
        )

        # Verify winning + losing = total
        assert account.winning_trades + account.losing_trades == account.total_trades

        # Verify equity = capital + unrealized
        expected_equity = account.current_capital + account.total_unrealized_pnl
        assert account.equity == expected_equity
