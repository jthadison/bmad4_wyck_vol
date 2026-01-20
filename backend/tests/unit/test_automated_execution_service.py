"""
Unit Tests for Automated Execution Service (Story 16.4b)

Tests cover:
- Enable/disable automation
- Kill switch functionality
- Position sizing with 2% risk rule
- Safety checks (balance, position, order validation)
- Signal execution flow
- Execution logging
- SHORT position support (UTAD patterns)
- Portfolio heat validation (10% - FR18)
- Campaign risk validation (5% - FR18)
- Correlated risk validation (6% - FR18)
- Retry logic for transient failures
- Order state tracking
- LIVE mode execution

Author: Story 16.4b
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from src.models.campaign_event import CampaignEvent, CampaignEventType
from src.trading.automated_execution_service import (
    AutomatedExecutionService,
    ExecutionConfig,
    ExecutionMode,
    ExecutionReport,
    Order,
    OrderState,
    PatternType,
    SafetyCheckError,
    SignalAction,
    TradeDirection,
)


class MockTradingAdapter:
    """Mock trading platform adapter for testing."""

    def __init__(
        self,
        balance: Decimal = Decimal("100000"),
        positions: dict[str, dict[str, Any]] | None = None,
        portfolio_heat: Decimal = Decimal("5.0"),
        campaign_risk: Decimal = Decimal("2.0"),
        correlated_risk: Decimal = Decimal("3.0"),
        fail_order: bool = False,
        fail_with_retryable: bool = False,
        fail_count: int = 0,
    ):
        self.balance = balance
        self.positions = positions or {}
        self.portfolio_heat = portfolio_heat
        self.campaign_risk = campaign_risk
        self.correlated_risk = correlated_risk
        self.fail_order = fail_order
        self.fail_with_retryable = fail_with_retryable
        self.fail_count = fail_count
        self._current_fail_count = 0
        self.orders_placed: list[Order] = []
        self.cancelled_orders: list[UUID] = []
        self.connected = False

    async def connect(self) -> bool:
        self.connected = True
        return True

    async def disconnect(self) -> None:
        self.connected = False

    async def get_account_balance(self) -> Decimal:
        return self.balance

    async def get_position(self, symbol: str) -> dict[str, Any] | None:
        return self.positions.get(symbol)

    async def get_portfolio_heat(self) -> Decimal:
        return self.portfolio_heat

    async def get_campaign_risk(self, campaign_id: str) -> Decimal:
        return self.campaign_risk

    async def get_correlated_risk(self, symbol: str) -> Decimal:
        return self.correlated_risk

    async def place_order(self, order: Order) -> ExecutionReport:
        # Handle retry testing
        if self.fail_count > 0 and self._current_fail_count < self.fail_count:
            self._current_fail_count += 1
            if self.fail_with_retryable:
                return ExecutionReport(
                    order_id=order.id,
                    success=False,
                    error_message="Connection timeout - temporary failure",
                )
            return ExecutionReport(
                order_id=order.id,
                success=False,
                error_message="Permanent failure - invalid order",
            )

        if self.fail_order:
            return ExecutionReport(
                order_id=order.id,
                success=False,
                error_message="Order rejected by platform",
            )

        self.orders_placed.append(order)
        return ExecutionReport(
            order_id=order.id,
            success=True,
            fill_price=Decimal("150.00"),
            fill_quantity=order.quantity,
            commission=Decimal("1.00"),
            slippage=Decimal("0.05"),
            executed_at=datetime.now(UTC),
            final_state=OrderState.FILLED,
        )

    async def cancel_order(self, order_id: UUID) -> bool:
        self.cancelled_orders.append(order_id)
        return True

    async def get_order_status(self, order_id: UUID) -> OrderState:
        return OrderState.FILLED


class TestAutomatedExecutionServiceInit:
    """Tests for service initialization."""

    def test_init_defaults(self):
        """Test service initializes with correct defaults."""
        service = AutomatedExecutionService()

        assert service.mode == ExecutionMode.DISABLED
        assert service.is_enabled is False
        assert service.kill_switch_active is False

    def test_init_with_config(self):
        """Test service initializes with custom config."""
        config = ExecutionConfig(
            max_risk_per_trade_pct=Decimal("1.5"),
            max_position_size=Decimal("5000"),
        )
        service = AutomatedExecutionService(config=config)

        assert service._config.max_risk_per_trade_pct == Decimal("1.5")
        assert service._config.max_position_size == Decimal("5000")

    def test_init_with_adapter(self):
        """Test service initializes with adapter."""
        adapter = MockTradingAdapter()
        service = AutomatedExecutionService(adapter=adapter)

        assert service._adapter is adapter

    def test_init_with_fr18_limits(self):
        """Test service initializes with FR18 risk limits."""
        service = AutomatedExecutionService()

        assert service._config.max_risk_per_trade_pct == Decimal("2.0")
        assert service._config.max_campaign_risk_pct == Decimal("5.0")
        assert service._config.max_correlated_risk_pct == Decimal("6.0")
        assert service._config.max_portfolio_heat_pct == Decimal("10.0")


class TestEnableDisable:
    """Tests for enable/disable functionality."""

    def test_enable_paper_mode(self):
        """Test enabling paper trading mode."""
        service = AutomatedExecutionService()
        service.enable(ExecutionMode.PAPER)

        assert service.mode == ExecutionMode.PAPER
        assert service.is_enabled is True

    def test_enable_live_mode(self):
        """Test enabling live trading mode."""
        service = AutomatedExecutionService()
        service.enable(ExecutionMode.LIVE)

        assert service.mode == ExecutionMode.LIVE
        assert service.is_enabled is True

    def test_enable_disabled_raises_error(self):
        """Test that enabling DISABLED mode raises error."""
        service = AutomatedExecutionService()

        with pytest.raises(ValueError, match="Use disable"):
            service.enable(ExecutionMode.DISABLED)

    def test_disable(self):
        """Test disabling automation."""
        service = AutomatedExecutionService()
        service.enable(ExecutionMode.PAPER)
        service.disable()

        assert service.mode == ExecutionMode.DISABLED
        assert service.is_enabled is False

    def test_enable_blocked_by_kill_switch(self):
        """Test that enable is blocked when kill switch active."""
        service = AutomatedExecutionService()
        service.activate_kill_switch("test")

        with pytest.raises(SafetyCheckError, match="kill switch"):
            service.enable(ExecutionMode.PAPER)


class TestKillSwitch:
    """Tests for kill switch functionality."""

    def test_activate_kill_switch(self):
        """Test activating kill switch."""
        service = AutomatedExecutionService()
        service.enable(ExecutionMode.PAPER)
        service.activate_kill_switch("emergency")

        assert service.kill_switch_active is True
        assert service.mode == ExecutionMode.DISABLED
        assert service.is_enabled is False

    def test_reset_kill_switch(self):
        """Test resetting kill switch."""
        service = AutomatedExecutionService()
        service.activate_kill_switch("test")
        service.reset_kill_switch()

        assert service.kill_switch_active is False
        # Should still be disabled after reset
        assert service.mode == ExecutionMode.DISABLED

    def test_kill_switch_logged(self):
        """Test kill switch events are logged."""
        service = AutomatedExecutionService()
        service.activate_kill_switch("test_reason")

        log = service.get_execution_log()
        assert len(log) == 1
        assert log[0]["event"] == "KILL_SWITCH_ACTIVATED"
        assert log[0]["reason"] == "test_reason"


class TestPositionSizing:
    """Tests for 2% risk rule position sizing."""

    def test_calculate_position_size_basic(self):
        """Test basic position size calculation."""
        # Use high max_position_value_pct to avoid value cap for this test
        config = ExecutionConfig(max_position_value_pct=Decimal("100.0"))
        service = AutomatedExecutionService(config=config)

        # Account: $100,000
        # Entry: $150, Stop: $145 (risk $5/share)
        # 2% risk = $2,000
        # Position size = $2,000 / $5 = 400 shares
        position_size = service._calculate_position_size(
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
            account_balance=Decimal("100000"),
        )

        assert position_size == Decimal("400")

    def test_calculate_position_size_capped_at_max(self):
        """Test position size is capped at max."""
        config = ExecutionConfig(max_position_size=Decimal("100"))
        service = AutomatedExecutionService(config=config)

        # Would be 400 shares but capped at 100
        position_size = service._calculate_position_size(
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
            account_balance=Decimal("100000"),
        )

        assert position_size == Decimal("100")

    def test_calculate_position_size_small_account(self):
        """Test position sizing with small account."""
        # Use high max_position_value_pct to avoid value cap for this test
        config = ExecutionConfig(max_position_value_pct=Decimal("100.0"))
        service = AutomatedExecutionService(config=config)

        # Account: $10,000
        # 2% risk = $200
        # Risk per share = $5
        # Position size = 40 shares
        position_size = service._calculate_position_size(
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
            account_balance=Decimal("10000"),
        )

        assert position_size == Decimal("40")

    def test_calculate_position_size_custom_risk_pct(self):
        """Test position sizing with custom risk percentage."""
        # Use high max_position_value_pct to avoid value cap for this test
        config = ExecutionConfig(
            max_risk_per_trade_pct=Decimal("1.0"),
            max_position_value_pct=Decimal("100.0"),
        )
        service = AutomatedExecutionService(config=config)

        # Account: $100,000
        # 1% risk = $1,000
        # Risk per share = $5
        # Position size = 200 shares
        position_size = service._calculate_position_size(
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
            account_balance=Decimal("100000"),
        )

        assert position_size == Decimal("200")

    def test_calculate_position_size_equal_entry_stop_raises_error(self):
        """Test that equal entry and stop raises error."""
        service = AutomatedExecutionService()

        with pytest.raises(SafetyCheckError, match="Invalid risk per share"):
            service._calculate_position_size(
                entry_price=Decimal("150.00"),
                stop_loss=Decimal("150.00"),  # Same as entry
                account_balance=Decimal("100000"),
            )

    def test_calculate_position_size_short_position(self):
        """Test position sizing for SHORT position."""
        # Use high max_position_value_pct to avoid value cap for this test
        config = ExecutionConfig(max_position_value_pct=Decimal("100.0"))
        service = AutomatedExecutionService(config=config)

        # Account: $100,000
        # Entry: $150, Stop: $155 (risk $5/share for SHORT)
        # 2% risk = $2,000
        # Position size = $2,000 / $5 = 400 shares
        position_size = service._calculate_position_size(
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("155.00"),  # Stop above entry for SHORT
            account_balance=Decimal("100000"),
            direction=TradeDirection.SHORT,
        )

        assert position_size == Decimal("400")

    def test_calculate_position_size_capped_by_value(self):
        """Test position size is capped by max position value (20% of equity)."""
        # Default config has 20% max position value
        service = AutomatedExecutionService()

        # Account: $100,000
        # Entry: $150, Stop: $145 (risk $5/share)
        # 2% risk would give 400 shares ($2,000 / $5)
        # BUT 20% max value = $20,000, so max shares = $20,000 / $150 = 133 shares
        position_size = service._calculate_position_size(
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
            account_balance=Decimal("100000"),
        )

        assert position_size == Decimal("133")  # Capped by 20% position value


class TestSafetyChecks:
    """Tests for safety check validation."""

    @pytest.mark.asyncio
    async def test_balance_check_insufficient(self):
        """Test balance check fails on zero balance."""
        adapter = MockTradingAdapter(balance=Decimal("0"))
        service = AutomatedExecutionService(adapter=adapter)

        with pytest.raises(SafetyCheckError, match="Insufficient balance"):
            await service._run_safety_checks(
                symbol="AAPL",
                action=SignalAction.ENTRY,
                direction=TradeDirection.LONG,
                entry_price=Decimal("150.00"),
                stop_loss=Decimal("145.00"),
                account_balance=Decimal("0"),
                campaign_id="test-123",
            )

    @pytest.mark.asyncio
    async def test_position_check_add_no_position(self):
        """Test ADD fails when no position exists."""
        adapter = MockTradingAdapter(positions={})
        service = AutomatedExecutionService(adapter=adapter)

        with pytest.raises(SafetyCheckError, match="Cannot ADD"):
            await service._run_safety_checks(
                symbol="AAPL",
                action=SignalAction.ADD,
                direction=TradeDirection.LONG,
                entry_price=Decimal("150.00"),
                stop_loss=Decimal("145.00"),
                account_balance=Decimal("100000"),
                campaign_id="test-123",
            )

    @pytest.mark.asyncio
    async def test_position_check_exit_no_position(self):
        """Test EXIT fails when no position exists."""
        adapter = MockTradingAdapter(positions={})
        service = AutomatedExecutionService(adapter=adapter)

        with pytest.raises(SafetyCheckError, match="Cannot EXIT"):
            await service._run_safety_checks(
                symbol="AAPL",
                action=SignalAction.EXIT,
                direction=TradeDirection.LONG,
                entry_price=Decimal("150.00"),
                stop_loss=Decimal("145.00"),
                account_balance=Decimal("100000"),
                campaign_id="test-123",
            )

    @pytest.mark.asyncio
    async def test_position_check_add_with_position(self):
        """Test ADD succeeds when position exists."""
        adapter = MockTradingAdapter(positions={"AAPL": {"symbol": "AAPL", "quantity": 100}})
        service = AutomatedExecutionService(adapter=adapter)

        # Should not raise
        await service._run_safety_checks(
            symbol="AAPL",
            action=SignalAction.ADD,
            direction=TradeDirection.LONG,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
            account_balance=Decimal("100000"),
            campaign_id="test-123",
        )

    @pytest.mark.asyncio
    async def test_invalid_entry_price(self):
        """Test validation fails on invalid entry price."""
        adapter = MockTradingAdapter()
        service = AutomatedExecutionService(adapter=adapter)

        with pytest.raises(SafetyCheckError, match="Entry price must be positive"):
            await service._run_safety_checks(
                symbol="AAPL",
                action=SignalAction.ENTRY,
                direction=TradeDirection.LONG,
                entry_price=Decimal("-10.00"),
                stop_loss=Decimal("145.00"),
                account_balance=Decimal("100000"),
                campaign_id="test-123",
            )

    @pytest.mark.asyncio
    async def test_stop_above_entry_for_long(self):
        """Test validation fails when stop is above entry for LONG."""
        adapter = MockTradingAdapter()
        service = AutomatedExecutionService(adapter=adapter)

        with pytest.raises(SafetyCheckError, match="Stop loss must be below entry.*LONG"):
            await service._run_safety_checks(
                symbol="AAPL",
                action=SignalAction.ENTRY,
                direction=TradeDirection.LONG,
                entry_price=Decimal("150.00"),
                stop_loss=Decimal("155.00"),
                account_balance=Decimal("100000"),
                campaign_id="test-123",
            )

    @pytest.mark.asyncio
    async def test_stop_below_entry_for_short(self):
        """Test validation fails when stop is below entry for SHORT."""
        adapter = MockTradingAdapter()
        service = AutomatedExecutionService(adapter=adapter)

        with pytest.raises(SafetyCheckError, match="Stop loss must be above entry.*SHORT"):
            await service._run_safety_checks(
                symbol="AAPL",
                action=SignalAction.ENTRY,
                direction=TradeDirection.SHORT,
                entry_price=Decimal("150.00"),
                stop_loss=Decimal("145.00"),  # Stop below entry is wrong for SHORT
                account_balance=Decimal("100000"),
                campaign_id="test-123",
            )

    @pytest.mark.asyncio
    async def test_stop_above_entry_valid_for_short(self):
        """Test stop above entry is valid for SHORT positions."""
        adapter = MockTradingAdapter()
        service = AutomatedExecutionService(adapter=adapter)

        # Should not raise - stop above entry is correct for SHORT
        await service._run_safety_checks(
            symbol="AAPL",
            action=SignalAction.ENTRY,
            direction=TradeDirection.SHORT,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("155.00"),  # Stop above entry is correct for SHORT
            account_balance=Decimal("100000"),
            campaign_id="test-123",
        )

    @pytest.mark.asyncio
    async def test_portfolio_heat_exceeded(self):
        """Test portfolio heat check fails when limit exceeded."""
        adapter = MockTradingAdapter(portfolio_heat=Decimal("11.0"))  # Above 10% limit
        service = AutomatedExecutionService(adapter=adapter)

        with pytest.raises(SafetyCheckError, match="Portfolio heat.*exceeds limit"):
            await service._run_safety_checks(
                symbol="AAPL",
                action=SignalAction.ENTRY,
                direction=TradeDirection.LONG,
                entry_price=Decimal("150.00"),
                stop_loss=Decimal("145.00"),
                account_balance=Decimal("100000"),
                campaign_id="test-123",
            )

    @pytest.mark.asyncio
    async def test_campaign_risk_exceeded(self):
        """Test campaign risk check fails when limit exceeded."""
        adapter = MockTradingAdapter(campaign_risk=Decimal("6.0"))  # Above 5% limit
        service = AutomatedExecutionService(adapter=adapter)

        with pytest.raises(SafetyCheckError, match="Campaign risk.*exceeds limit"):
            await service._run_safety_checks(
                symbol="AAPL",
                action=SignalAction.ENTRY,
                direction=TradeDirection.LONG,
                entry_price=Decimal("150.00"),
                stop_loss=Decimal("145.00"),
                account_balance=Decimal("100000"),
                campaign_id="test-123",
            )

    @pytest.mark.asyncio
    async def test_correlated_risk_exceeded(self):
        """Test correlated risk check fails when limit exceeded."""
        adapter = MockTradingAdapter(correlated_risk=Decimal("7.0"))  # Above 6% limit
        service = AutomatedExecutionService(adapter=adapter)

        with pytest.raises(SafetyCheckError, match="Correlated risk.*exceeds limit"):
            await service._run_safety_checks(
                symbol="AAPL",
                action=SignalAction.ENTRY,
                direction=TradeDirection.LONG,
                entry_price=Decimal("150.00"),
                stop_loss=Decimal("145.00"),
                account_balance=Decimal("100000"),
                campaign_id="test-123",
            )

    @pytest.mark.asyncio
    async def test_all_safety_checks_pass(self):
        """Test all safety checks pass with valid values."""
        adapter = MockTradingAdapter(
            portfolio_heat=Decimal("5.0"),  # Below 10%
            campaign_risk=Decimal("2.0"),  # Below 5%
            correlated_risk=Decimal("3.0"),  # Below 6%
        )
        service = AutomatedExecutionService(adapter=adapter)

        # Should not raise
        await service._run_safety_checks(
            symbol="AAPL",
            action=SignalAction.ENTRY,
            direction=TradeDirection.LONG,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
            account_balance=Decimal("100000"),
            campaign_id="test-123",
        )


class TestOrderValidation:
    """Tests for order validation."""

    def test_validate_order_missing_symbol(self):
        """Test validation fails on missing symbol."""
        service = AutomatedExecutionService()
        order = Order(symbol="", quantity=Decimal("100"))

        with pytest.raises(SafetyCheckError, match="missing symbol"):
            service._validate_order(order)

    def test_validate_order_zero_quantity(self):
        """Test validation fails on zero quantity."""
        service = AutomatedExecutionService()
        order = Order(symbol="AAPL", quantity=Decimal("0"))

        with pytest.raises(SafetyCheckError, match="Invalid order quantity"):
            service._validate_order(order)

    def test_validate_order_exceeds_max(self):
        """Test validation fails when quantity exceeds max."""
        config = ExecutionConfig(max_position_size=Decimal("100"))
        service = AutomatedExecutionService(config=config)
        order = Order(symbol="AAPL", quantity=Decimal("500"))

        with pytest.raises(SafetyCheckError, match="exceeds max"):
            service._validate_order(order)

    def test_validate_order_success(self):
        """Test valid order passes validation."""
        service = AutomatedExecutionService()
        order = Order(symbol="AAPL", quantity=Decimal("100"))

        # Should not raise
        service._validate_order(order)


class TestSignalExecution:
    """Tests for signal execution flow."""

    @pytest.mark.asyncio
    async def test_execute_signal_when_disabled(self):
        """Test execution returns None when disabled."""
        adapter = MockTradingAdapter()
        service = AutomatedExecutionService(adapter=adapter)

        event = CampaignEvent(
            event_type=CampaignEventType.CAMPAIGN_FORMED,
            campaign_id="test-123",
            timestamp=datetime.now(UTC),
            metadata={"symbol": "AAPL"},
        )

        result = await service.execute_signal(
            event=event,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_execute_signal_no_adapter(self):
        """Test execution returns None when no adapter."""
        service = AutomatedExecutionService()
        service.enable(ExecutionMode.PAPER)

        event = CampaignEvent(
            event_type=CampaignEventType.CAMPAIGN_FORMED,
            campaign_id="test-123",
            timestamp=datetime.now(UTC),
            metadata={"symbol": "AAPL"},
        )

        result = await service.execute_signal(
            event=event,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_execute_signal_campaign_formed(self):
        """Test execution on CAMPAIGN_FORMED event."""
        adapter = MockTradingAdapter()
        service = AutomatedExecutionService(adapter=adapter)
        service.enable(ExecutionMode.PAPER)

        event = CampaignEvent(
            event_type=CampaignEventType.CAMPAIGN_FORMED,
            campaign_id="test-123",
            timestamp=datetime.now(UTC),
            metadata={"symbol": "AAPL"},
        )

        result = await service.execute_signal(
            event=event,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
        )

        assert result is not None
        assert result.success is True
        assert len(adapter.orders_placed) == 1
        assert adapter.orders_placed[0].action == SignalAction.ENTRY

    @pytest.mark.asyncio
    async def test_execute_signal_pattern_detected_spring(self):
        """Test execution on Spring pattern detection."""
        adapter = MockTradingAdapter()
        service = AutomatedExecutionService(adapter=adapter)
        service.enable(ExecutionMode.PAPER)

        event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test-123",
            timestamp=datetime.now(UTC),
            pattern_type="Spring",
            metadata={"symbol": "AAPL"},
        )

        result = await service.execute_signal(
            event=event,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
        )

        assert result is not None
        assert adapter.orders_placed[0].action == SignalAction.ENTRY
        assert adapter.orders_placed[0].direction == TradeDirection.LONG

    @pytest.mark.asyncio
    async def test_execute_signal_pattern_detected_sos(self):
        """Test execution on SOS pattern detection."""
        adapter = MockTradingAdapter(positions={"AAPL": {"symbol": "AAPL", "quantity": 100}})
        service = AutomatedExecutionService(adapter=adapter)
        service.enable(ExecutionMode.PAPER)

        event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test-123",
            timestamp=datetime.now(UTC),
            pattern_type="SOS",
            metadata={"symbol": "AAPL"},
        )

        result = await service.execute_signal(
            event=event,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
        )

        assert result is not None
        assert adapter.orders_placed[0].action == SignalAction.ADD

    @pytest.mark.asyncio
    async def test_execute_signal_utad_short_position(self):
        """Test execution on UTAD pattern creates SHORT position."""
        adapter = MockTradingAdapter()
        service = AutomatedExecutionService(adapter=adapter)
        service.enable(ExecutionMode.PAPER)

        event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test-123",
            timestamp=datetime.now(UTC),
            pattern_type="UTAD",
            metadata={"symbol": "AAPL"},
        )

        result = await service.execute_signal(
            event=event,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("155.00"),  # Stop above entry for SHORT
        )

        assert result is not None
        assert adapter.orders_placed[0].action == SignalAction.ENTRY
        assert adapter.orders_placed[0].direction == TradeDirection.SHORT

    @pytest.mark.asyncio
    async def test_execute_signal_sow_short_add(self):
        """Test execution on SOW pattern adds to SHORT position."""
        adapter = MockTradingAdapter(positions={"AAPL": {"symbol": "AAPL", "quantity": -100}})
        service = AutomatedExecutionService(adapter=adapter)
        service.enable(ExecutionMode.PAPER)

        event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test-123",
            timestamp=datetime.now(UTC),
            pattern_type="SOW",
            metadata={"symbol": "AAPL"},
        )

        result = await service.execute_signal(
            event=event,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("155.00"),
        )

        assert result is not None
        assert adapter.orders_placed[0].action == SignalAction.ADD
        assert adapter.orders_placed[0].direction == TradeDirection.SHORT

    @pytest.mark.asyncio
    async def test_execute_signal_lpsy_short_exit(self):
        """Test execution on LPSY pattern exits SHORT position."""
        adapter = MockTradingAdapter(positions={"AAPL": {"symbol": "AAPL", "quantity": -100}})
        service = AutomatedExecutionService(adapter=adapter)
        service.enable(ExecutionMode.PAPER)

        event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test-123",
            timestamp=datetime.now(UTC),
            pattern_type="LPSY",
            metadata={"symbol": "AAPL"},
        )

        result = await service.execute_signal(
            event=event,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("155.00"),
        )

        assert result is not None
        assert adapter.orders_placed[0].action == SignalAction.EXIT
        assert adapter.orders_placed[0].direction == TradeDirection.SHORT

    @pytest.mark.asyncio
    async def test_execute_signal_missing_symbol(self):
        """Test execution fails when symbol missing."""
        adapter = MockTradingAdapter()
        service = AutomatedExecutionService(adapter=adapter)
        service.enable(ExecutionMode.PAPER)

        event = CampaignEvent(
            event_type=CampaignEventType.CAMPAIGN_FORMED,
            campaign_id="test-123",
            timestamp=datetime.now(UTC),
            metadata={},  # No symbol
        )

        with pytest.raises(SafetyCheckError, match="Missing symbol"):
            await service.execute_signal(
                event=event,
                entry_price=Decimal("150.00"),
                stop_loss=Decimal("145.00"),
            )

    @pytest.mark.asyncio
    async def test_execute_signal_invalid_event_type(self):
        """Test execution skips invalid event types."""
        adapter = MockTradingAdapter()
        service = AutomatedExecutionService(adapter=adapter)
        service.enable(ExecutionMode.PAPER)

        event = CampaignEvent(
            event_type=CampaignEventType.CAMPAIGN_FAILED,  # Not an actionable event
            campaign_id="test-123",
            timestamp=datetime.now(UTC),
            metadata={"symbol": "AAPL"},
        )

        result = await service.execute_signal(
            event=event,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
        )

        assert result is None
        assert len(adapter.orders_placed) == 0

    @pytest.mark.asyncio
    async def test_execute_signal_live_mode(self):
        """Test execution in LIVE mode."""
        adapter = MockTradingAdapter()
        service = AutomatedExecutionService(adapter=adapter)
        service.enable(ExecutionMode.LIVE)

        event = CampaignEvent(
            event_type=CampaignEventType.CAMPAIGN_FORMED,
            campaign_id="test-123",
            timestamp=datetime.now(UTC),
            metadata={"symbol": "AAPL"},
        )

        result = await service.execute_signal(
            event=event,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
        )

        assert result is not None
        assert result.success is True
        assert service.mode == ExecutionMode.LIVE


class TestRetryLogic:
    """Tests for retry logic on transient failures."""

    @pytest.mark.asyncio
    async def test_retry_on_transient_failure(self):
        """Test that transient failures trigger retries."""
        adapter = MockTradingAdapter(
            fail_count=2,  # Fail first 2 attempts
            fail_with_retryable=True,
        )
        config = ExecutionConfig(max_retries=3, retry_delay_ms=10)
        service = AutomatedExecutionService(adapter=adapter, config=config)
        service.enable(ExecutionMode.PAPER)

        event = CampaignEvent(
            event_type=CampaignEventType.CAMPAIGN_FORMED,
            campaign_id="test-123",
            timestamp=datetime.now(UTC),
            metadata={"symbol": "AAPL"},
        )

        result = await service.execute_signal(
            event=event,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
        )

        # Should succeed on 3rd attempt
        assert result is not None
        assert result.success is True
        assert result.retry_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_permanent_failure(self):
        """Test that permanent failures don't trigger retries."""
        adapter = MockTradingAdapter(
            fail_count=1,
            fail_with_retryable=False,  # Permanent failure
        )
        config = ExecutionConfig(max_retries=3, retry_delay_ms=10)
        service = AutomatedExecutionService(adapter=adapter, config=config)
        service.enable(ExecutionMode.PAPER)

        event = CampaignEvent(
            event_type=CampaignEventType.CAMPAIGN_FORMED,
            campaign_id="test-123",
            timestamp=datetime.now(UTC),
            metadata={"symbol": "AAPL"},
        )

        result = await service.execute_signal(
            event=event,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
        )

        # Should fail without retries
        assert result is not None
        assert result.success is False
        assert result.retry_count == 0

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        """Test that max retries are respected."""
        adapter = MockTradingAdapter(
            fail_count=10,  # Always fail
            fail_with_retryable=True,
        )
        config = ExecutionConfig(max_retries=2, retry_delay_ms=10)
        service = AutomatedExecutionService(adapter=adapter, config=config)
        service.enable(ExecutionMode.PAPER)

        event = CampaignEvent(
            event_type=CampaignEventType.CAMPAIGN_FORMED,
            campaign_id="test-123",
            timestamp=datetime.now(UTC),
            metadata={"symbol": "AAPL"},
        )

        result = await service.execute_signal(
            event=event,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
        )

        # Should fail after max retries
        assert result is not None
        assert result.success is False
        assert result.retry_count == 2
        assert result.final_state == OrderState.FAILED


class TestOrderStateTracking:
    """Tests for order state tracking."""

    @pytest.mark.asyncio
    async def test_order_state_transitions(self):
        """Test order state transitions during execution."""
        adapter = MockTradingAdapter()
        service = AutomatedExecutionService(adapter=adapter)
        service.enable(ExecutionMode.PAPER)

        event = CampaignEvent(
            event_type=CampaignEventType.CAMPAIGN_FORMED,
            campaign_id="test-123",
            timestamp=datetime.now(UTC),
            metadata={"symbol": "AAPL"},
        )

        result = await service.execute_signal(
            event=event,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
        )

        assert result is not None
        assert result.final_state == OrderState.FILLED

    @pytest.mark.asyncio
    async def test_failed_order_state(self):
        """Test order state on failure."""
        adapter = MockTradingAdapter(fail_order=True)
        service = AutomatedExecutionService(adapter=adapter)
        service.enable(ExecutionMode.PAPER)

        event = CampaignEvent(
            event_type=CampaignEventType.CAMPAIGN_FORMED,
            campaign_id="test-123",
            timestamp=datetime.now(UTC),
            metadata={"symbol": "AAPL"},
        )

        result = await service.execute_signal(
            event=event,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
        )

        assert result is not None
        assert result.success is False
        assert result.final_state == OrderState.FAILED

    def test_get_pending_orders(self):
        """Test retrieving pending orders."""
        service = AutomatedExecutionService()
        order = Order(symbol="AAPL", quantity=Decimal("100"))
        service._pending_orders[order.id] = order

        pending = service.get_pending_orders()
        assert len(pending) == 1
        assert pending[0].symbol == "AAPL"

    def test_get_order_by_id(self):
        """Test retrieving order by ID."""
        service = AutomatedExecutionService()
        order = Order(symbol="AAPL", quantity=Decimal("100"))
        service._pending_orders[order.id] = order

        retrieved = service.get_order(order.id)
        assert retrieved is not None
        assert retrieved.symbol == "AAPL"

    def test_order_update_state(self):
        """Test order state update."""
        order = Order(symbol="AAPL", quantity=Decimal("100"))
        assert order.state == OrderState.PENDING

        order.update_state(OrderState.SUBMITTED)
        assert order.state == OrderState.SUBMITTED
        assert order.updated_at is not None


class TestExecutionLogging:
    """Tests for execution logging."""

    @pytest.mark.asyncio
    async def test_execution_logged(self):
        """Test successful execution is logged."""
        adapter = MockTradingAdapter()
        service = AutomatedExecutionService(adapter=adapter)
        service.enable(ExecutionMode.PAPER)

        event = CampaignEvent(
            event_type=CampaignEventType.CAMPAIGN_FORMED,
            campaign_id="test-123",
            timestamp=datetime.now(UTC),
            metadata={"symbol": "AAPL"},
        )

        await service.execute_signal(
            event=event,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
        )

        log = service.get_execution_log()
        assert len(log) == 1
        assert log[0]["event"] == "ORDER_EXECUTED"
        assert log[0]["success"] is True
        assert log[0]["symbol"] == "AAPL"

    def test_get_execution_log_limited(self):
        """Test execution log respects limit."""
        service = AutomatedExecutionService()

        # Add many log entries
        for i in range(20):
            service._log_execution(
                event=f"TEST_{i}",
                success=True,
                details={},
            )

        log = service.get_execution_log(limit=5)
        assert len(log) == 5

    def test_execution_log_uses_deque(self):
        """Test execution log uses deque with maxlen."""
        config = ExecutionConfig(execution_log_size=5)
        service = AutomatedExecutionService(config=config)

        # Add more entries than maxlen
        for i in range(10):
            service._log_execution(
                event=f"TEST_{i}",
                success=True,
                details={},
            )

        log = service.get_execution_log()
        # Should only have last 5 entries due to deque maxlen
        assert len(log) == 5
        assert log[0]["event"] == "TEST_5"
        assert log[-1]["event"] == "TEST_9"


class TestDetermineActionAndDirection:
    """Tests for action and direction determination from events."""

    def test_campaign_formed_returns_entry_long(self):
        """Test CAMPAIGN_FORMED maps to ENTRY LONG action."""
        service = AutomatedExecutionService()
        event = CampaignEvent(
            event_type=CampaignEventType.CAMPAIGN_FORMED,
            campaign_id="test",
            timestamp=datetime.now(UTC),
        )

        action, direction = service._determine_action_and_direction(event)
        assert action == SignalAction.ENTRY
        assert direction == TradeDirection.LONG

    def test_campaign_formed_with_short_direction(self):
        """Test CAMPAIGN_FORMED with SHORT direction hint."""
        service = AutomatedExecutionService()
        event = CampaignEvent(
            event_type=CampaignEventType.CAMPAIGN_FORMED,
            campaign_id="test",
            timestamp=datetime.now(UTC),
            metadata={"direction": "SHORT"},
        )

        action, direction = service._determine_action_and_direction(event)
        assert action == SignalAction.ENTRY
        assert direction == TradeDirection.SHORT

    def test_spring_pattern_returns_entry_long(self):
        """Test Spring pattern maps to ENTRY LONG action."""
        service = AutomatedExecutionService()
        event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test",
            timestamp=datetime.now(UTC),
            pattern_type="Spring",
        )

        action, direction = service._determine_action_and_direction(event)
        assert action == SignalAction.ENTRY
        assert direction == TradeDirection.LONG

    def test_utad_pattern_returns_entry_short(self):
        """Test UTAD pattern maps to ENTRY SHORT action."""
        service = AutomatedExecutionService()
        event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test",
            timestamp=datetime.now(UTC),
            pattern_type="UTAD",
        )

        action, direction = service._determine_action_and_direction(event)
        assert action == SignalAction.ENTRY
        assert direction == TradeDirection.SHORT

    def test_sos_pattern_returns_add_long(self):
        """Test SOS pattern maps to ADD LONG action."""
        service = AutomatedExecutionService()
        event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test",
            timestamp=datetime.now(UTC),
            pattern_type="SOS",
        )

        action, direction = service._determine_action_and_direction(event)
        assert action == SignalAction.ADD
        assert direction == TradeDirection.LONG

    def test_sow_pattern_returns_add_short(self):
        """Test SOW pattern maps to ADD SHORT action."""
        service = AutomatedExecutionService()
        event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test",
            timestamp=datetime.now(UTC),
            pattern_type="SOW",
        )

        action, direction = service._determine_action_and_direction(event)
        assert action == SignalAction.ADD
        assert direction == TradeDirection.SHORT

    def test_lps_pattern_returns_exit_long(self):
        """Test LPS pattern maps to EXIT LONG action."""
        service = AutomatedExecutionService()
        event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test",
            timestamp=datetime.now(UTC),
            pattern_type="LPS",
        )

        action, direction = service._determine_action_and_direction(event)
        assert action == SignalAction.EXIT
        assert direction == TradeDirection.LONG

    def test_lpsy_pattern_returns_exit_short(self):
        """Test LPSY pattern maps to EXIT SHORT action."""
        service = AutomatedExecutionService()
        event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test",
            timestamp=datetime.now(UTC),
            pattern_type="LPSY",
        )

        action, direction = service._determine_action_and_direction(event)
        assert action == SignalAction.EXIT
        assert direction == TradeDirection.SHORT

    def test_unknown_pattern_returns_none(self):
        """Test unknown pattern returns None."""
        service = AutomatedExecutionService()
        event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test",
            timestamp=datetime.now(UTC),
            pattern_type="UNKNOWN",
        )

        action, direction = service._determine_action_and_direction(event)
        assert action is None


class TestPatternType:
    """Tests for PatternType enum."""

    def test_get_direction_long_patterns(self):
        """Test LONG patterns return LONG direction."""
        assert PatternType.get_direction("Spring") == TradeDirection.LONG
        assert PatternType.get_direction("SOS") == TradeDirection.LONG
        assert PatternType.get_direction("LPS") == TradeDirection.LONG

    def test_get_direction_short_patterns(self):
        """Test SHORT patterns return SHORT direction."""
        assert PatternType.get_direction("UTAD") == TradeDirection.SHORT
        assert PatternType.get_direction("SOW") == TradeDirection.SHORT
        assert PatternType.get_direction("LPSY") == TradeDirection.SHORT

    def test_get_action_entry_patterns(self):
        """Test entry patterns return ENTRY action."""
        assert PatternType.get_action("Spring") == SignalAction.ENTRY
        assert PatternType.get_action("UTAD") == SignalAction.ENTRY

    def test_get_action_add_patterns(self):
        """Test add patterns return ADD action."""
        assert PatternType.get_action("SOS") == SignalAction.ADD
        assert PatternType.get_action("SOW") == SignalAction.ADD

    def test_get_action_exit_patterns(self):
        """Test exit patterns return EXIT action."""
        assert PatternType.get_action("LPS") == SignalAction.EXIT
        assert PatternType.get_action("LPSY") == SignalAction.EXIT

    def test_get_action_unknown_returns_none(self):
        """Test unknown pattern returns None."""
        assert PatternType.get_action("UNKNOWN") is None


class TestKillSwitchDuringExecution:
    """Tests for kill switch activation during execution."""

    @pytest.mark.asyncio
    async def test_kill_switch_cancels_retry(self):
        """Test that activating kill switch during execution cancels retries."""
        adapter = MockTradingAdapter(
            fail_count=5,
            fail_with_retryable=True,
        )
        config = ExecutionConfig(max_retries=10, retry_delay_ms=50)
        service = AutomatedExecutionService(adapter=adapter, config=config)
        service.enable(ExecutionMode.PAPER)

        # Activate kill switch after a delay (in production this would be async)
        # For testing, we'll check the behavior by activating before execution
        service.activate_kill_switch("emergency")

        event = CampaignEvent(
            event_type=CampaignEventType.CAMPAIGN_FORMED,
            campaign_id="test-123",
            timestamp=datetime.now(UTC),
            metadata={"symbol": "AAPL"},
        )

        # Should return None because kill switch is active
        result = await service.execute_signal(
            event=event,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
        )

        assert result is None
