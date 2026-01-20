"""
Unit Tests for Automated Execution Service (Story 16.4b)

Tests cover:
- Enable/disable automation
- Kill switch functionality
- Position sizing with 2% risk rule
- Safety checks (balance, position, order validation)
- Signal execution flow
- Execution logging

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
    SafetyCheckError,
    SignalAction,
)


class MockTradingAdapter:
    """Mock trading platform adapter for testing."""

    def __init__(
        self,
        balance: Decimal = Decimal("100000"),
        positions: dict[str, dict[str, Any]] | None = None,
    ):
        self.balance = balance
        self.positions = positions or {}
        self.orders_placed: list[Order] = []
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

    async def place_order(self, order: Order) -> ExecutionReport:
        self.orders_placed.append(order)
        return ExecutionReport(
            order_id=order.id,
            success=True,
            fill_price=Decimal("150.00"),
            fill_quantity=order.quantity,
            commission=Decimal("1.00"),
            slippage=Decimal("0.05"),
            executed_at=datetime.now(UTC),
        )

    async def cancel_order(self, order_id: UUID) -> bool:
        return True


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
        service = AutomatedExecutionService()

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
        service = AutomatedExecutionService()

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
        config = ExecutionConfig(max_risk_per_trade_pct=Decimal("1.0"))
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

    def test_calculate_position_size_invalid_stop_raises_error(self):
        """Test that stop above entry raises error."""
        service = AutomatedExecutionService()

        with pytest.raises(SafetyCheckError, match="Invalid risk per share"):
            service._calculate_position_size(
                entry_price=Decimal("150.00"),
                stop_loss=Decimal("155.00"),  # Stop above entry
                account_balance=Decimal("100000"),
            )


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
                entry_price=Decimal("150.00"),
                stop_loss=Decimal("145.00"),
                account_balance=Decimal("0"),
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
                entry_price=Decimal("150.00"),
                stop_loss=Decimal("145.00"),
                account_balance=Decimal("100000"),
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
                entry_price=Decimal("150.00"),
                stop_loss=Decimal("145.00"),
                account_balance=Decimal("100000"),
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
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("145.00"),
            account_balance=Decimal("100000"),
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
                entry_price=Decimal("-10.00"),
                stop_loss=Decimal("145.00"),
                account_balance=Decimal("100000"),
            )

    @pytest.mark.asyncio
    async def test_stop_above_entry(self):
        """Test validation fails when stop is above entry."""
        adapter = MockTradingAdapter()
        service = AutomatedExecutionService(adapter=adapter)

        with pytest.raises(SafetyCheckError, match="Stop loss must be below entry"):
            await service._run_safety_checks(
                symbol="AAPL",
                action=SignalAction.ENTRY,
                entry_price=Decimal("150.00"),
                stop_loss=Decimal("155.00"),
                account_balance=Decimal("100000"),
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


class TestDetermineAction:
    """Tests for action determination from events."""

    def test_campaign_formed_returns_entry(self):
        """Test CAMPAIGN_FORMED maps to ENTRY action."""
        service = AutomatedExecutionService()
        event = CampaignEvent(
            event_type=CampaignEventType.CAMPAIGN_FORMED,
            campaign_id="test",
            timestamp=datetime.now(UTC),
        )

        action = service._determine_action(event)
        assert action == SignalAction.ENTRY

    def test_spring_pattern_returns_entry(self):
        """Test Spring pattern maps to ENTRY action."""
        service = AutomatedExecutionService()
        event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test",
            timestamp=datetime.now(UTC),
            pattern_type="Spring",
        )

        action = service._determine_action(event)
        assert action == SignalAction.ENTRY

    def test_sos_pattern_returns_add(self):
        """Test SOS pattern maps to ADD action."""
        service = AutomatedExecutionService()
        event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test",
            timestamp=datetime.now(UTC),
            pattern_type="SOS",
        )

        action = service._determine_action(event)
        assert action == SignalAction.ADD

    def test_lps_pattern_returns_exit(self):
        """Test LPS pattern maps to EXIT action."""
        service = AutomatedExecutionService()
        event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test",
            timestamp=datetime.now(UTC),
            pattern_type="LPS",
        )

        action = service._determine_action(event)
        assert action == SignalAction.EXIT

    def test_unknown_pattern_returns_none(self):
        """Test unknown pattern returns None."""
        service = AutomatedExecutionService()
        event = CampaignEvent(
            event_type=CampaignEventType.PATTERN_DETECTED,
            campaign_id="test",
            timestamp=datetime.now(UTC),
            pattern_type="UNKNOWN",
        )

        action = service._determine_action(event)
        assert action is None
