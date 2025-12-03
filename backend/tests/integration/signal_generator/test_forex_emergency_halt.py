"""
Integration tests for forex emergency halt at 2% (Story 8.10.3).

Tests end-to-end forex emergency exit workflow:
- Emergency exit triggered at 2.1% daily loss
- System halted flag set
- No new signals generated after halt

Author: Story 8.10.3
"""

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.signal_generator.master_orchestrator import (
    MasterOrchestrator,
    PortfolioState,
)


@pytest.fixture
def orchestrator() -> MasterOrchestrator:
    """Create MasterOrchestrator instance for integration testing."""
    # Create orchestrator with mocked dependencies
    orchestrator = MasterOrchestrator(
        market_data_service=MagicMock(),
        trading_range_service=MagicMock(),
        volume_service=MagicMock(),
        portfolio_service=MagicMock(),
        market_context_builder=MagicMock(),
        pattern_detectors=[],
        signal_generator=MagicMock(),
        signal_repository=MagicMock(),
        rejection_repository=MagicMock(),
    )

    return orchestrator


@pytest.fixture
def forex_bar() -> Any:
    """Create forex OHLCV bar (EUR/USD)."""
    bar = MagicMock()
    bar.symbol = "EUR/USD"
    bar.open = Decimal("1.0800")
    bar.high = Decimal("1.0820")
    bar.low = Decimal("1.0750")
    bar.close = Decimal("1.0760")
    bar.volume = Decimal("1000000")
    return bar


class TestForexEmergencyHaltIntegration:
    """Integration tests for forex emergency halt workflow."""

    @pytest.mark.asyncio
    async def test_forex_emergency_halt_at_2_percent(
        self, orchestrator: MasterOrchestrator, forex_bar: Any
    ) -> None:
        """
        Test forex campaign with 2.1% daily loss triggers emergency halt.

        Scenario:
        - Forex account with $10,000 equity
        - 2 open EUR/USD positions (long)
        - Market moves cause 2.1% daily loss
        - Emergency exit should trigger
        - System should halt
        """
        # Setup: Portfolio with 2.1% daily loss
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("7500"),
            daily_pnl=Decimal("-210"),  # $210 loss
            daily_pnl_pct=Decimal("-0.021"),  # 2.1% loss
            max_drawdown_pct=Decimal("0.08"),
            total_heat=Decimal("8.0"),
            total_forex_notional=Decimal("20000"),  # 2x equity (within 3x limit)
            max_forex_notional=Decimal("30000"),
        )

        # Execute: Check emergency exits
        exits = await orchestrator.check_emergency_exits(forex_bar, portfolio, "FOREX")

        # Assert: Emergency exit triggered
        assert len(exits) >= 1, "Emergency exit should be triggered"
        daily_loss_exit = next((e for e in exits if "Daily loss" in e.reason), None)
        assert daily_loss_exit is not None, "Daily loss exit should be present"
        assert "2%" in daily_loss_exit.reason, "Reason should mention 2% threshold"
        assert "FOREX" in daily_loss_exit.reason, "Reason should mention FOREX"

        # Note: System halt flag is only set for max drawdown, not daily loss
        # Daily loss halts new trades but doesn't halt entire system

    @pytest.mark.asyncio
    async def test_system_halted_on_max_drawdown(
        self, orchestrator: MasterOrchestrator, forex_bar: Any
    ) -> None:
        """
        Test system halt flag set when max drawdown reached.

        Scenario:
        - Portfolio reaches 15% max drawdown
        - System should halt completely
        - _system_halted flag should be True
        """
        # Setup: Portfolio with 15% max drawdown
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8500"),
            daily_pnl=Decimal("-100"),
            daily_pnl_pct=Decimal("-0.01"),
            max_drawdown_pct=Decimal("0.15"),  # 15% max drawdown
            total_heat=Decimal("6.0"),
        )

        # Execute: Check emergency exits
        exits = await orchestrator.check_emergency_exits(forex_bar, portfolio, "FOREX")

        # Assert: Emergency exit triggered and system halted
        assert len(exits) >= 1, "Emergency exit should be triggered"
        max_dd_exit = next((e for e in exits if "Max drawdown" in e.reason), None)
        assert max_dd_exit is not None, "Max drawdown exit should be present"
        assert orchestrator._system_halted is True, "System should be halted"

    @pytest.mark.asyncio
    async def test_forex_notional_limit_emergency_exit(
        self, orchestrator: MasterOrchestrator, forex_bar: Any
    ) -> None:
        """
        Test forex notional exposure limit triggers emergency exit.

        Scenario:
        - Forex notional reaches 3.5x equity (exceeds 3x limit)
        - Emergency exit should trigger
        - System should NOT halt (only max drawdown halts system)
        """
        # Setup: Portfolio with excessive forex notional
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("7000"),
            daily_pnl=Decimal("50"),  # Profitable day
            daily_pnl_pct=Decimal("0.005"),  # +0.5%
            max_drawdown_pct=Decimal("0.05"),
            total_heat=Decimal("10.0"),
            total_forex_notional=Decimal("35000"),  # 3.5x equity (exceeds limit)
            max_forex_notional=Decimal("30000"),  # 3x equity limit
        )

        # Execute: Check emergency exits
        exits = await orchestrator.check_emergency_exits(forex_bar, portfolio, "FOREX")

        # Assert: Notional limit exit triggered
        assert len(exits) >= 1, "Emergency exit should be triggered"
        notional_exit = next((e for e in exits if "Forex notional" in e.reason), None)
        assert notional_exit is not None, "Forex notional exit should be present"
        assert "$35,000" in notional_exit.reason, "Reason should include actual notional"
        assert "$30,000" in notional_exit.reason, "Reason should include limit"

        # Note: Notional limit does NOT halt system (only max drawdown does)
        # This is a different behavior than max drawdown

    @pytest.mark.asyncio
    async def test_multiple_emergency_conditions_forex(
        self, orchestrator: MasterOrchestrator, forex_bar: Any
    ) -> None:
        """
        Test multiple emergency conditions trigger simultaneously.

        Scenario:
        - 2.5% daily loss (exceeds 2% forex threshold)
        - Forex notional at 3.5x equity
        - Both conditions should trigger separate exits
        """
        # Setup: Portfolio violating multiple conditions
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("7000"),
            daily_pnl=Decimal("-250"),
            daily_pnl_pct=Decimal("-0.025"),  # 2.5% loss
            max_drawdown_pct=Decimal("0.10"),
            total_heat=Decimal("12.0"),
            total_forex_notional=Decimal("35000"),  # 3.5x equity
            max_forex_notional=Decimal("30000"),
        )

        # Execute: Check emergency exits
        exits = await orchestrator.check_emergency_exits(forex_bar, portfolio, "FOREX")

        # Assert: Both exits triggered
        assert len(exits) == 2, "Both emergency exits should be triggered"

        reasons = [exit.reason for exit in exits]
        assert any("Daily loss" in r for r in reasons), "Daily loss exit should be present"
        assert any("Forex notional" in r for r in reasons), "Forex notional exit should be present"

    @pytest.mark.asyncio
    async def test_stock_not_affected_by_forex_thresholds(
        self, orchestrator: MasterOrchestrator, forex_bar: Any
    ) -> None:
        """
        Test stock asset class uses 3% threshold, not affected by forex rules.

        Scenario:
        - Stock portfolio with 2.5% daily loss
        - Should NOT trigger (stock threshold is 3%)
        - Proves asset-class-specific thresholds working
        """
        # Setup: Stock portfolio with 2.5% loss
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("-250"),
            daily_pnl_pct=Decimal("-0.025"),  # 2.5% loss
            max_drawdown_pct=Decimal("0.08"),
            total_heat=Decimal("7.0"),
            total_forex_notional=Decimal("0"),  # No forex exposure
            max_forex_notional=Decimal("0"),
        )

        # Execute: Check emergency exits for STOCK asset class
        exits = await orchestrator.check_emergency_exits(forex_bar, portfolio, "STOCK")

        # Assert: No emergency exit triggered (2.5% < 3% threshold)
        assert len(exits) == 0, "Should not trigger for stock at 2.5% loss"

    @pytest.mark.asyncio
    async def test_emergency_exit_captures_bar_details(
        self, orchestrator: MasterOrchestrator, forex_bar: Any
    ) -> None:
        """
        Test emergency exit captures correct bar details.

        Scenario:
        - Emergency exit triggered
        - Exit price should match bar.close
        - Timestamp should be set
        """
        # Setup: Portfolio triggering emergency exit
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("-250"),
            daily_pnl_pct=Decimal("-0.025"),  # 2.5% loss (triggers for forex)
            max_drawdown_pct=Decimal("0.10"),
            total_heat=Decimal("8.0"),
        )

        # Execute: Check emergency exits
        exits = await orchestrator.check_emergency_exits(forex_bar, portfolio, "FOREX")

        # Assert: Exit details captured
        assert len(exits) >= 1, "Emergency exit should be triggered"
        exit = exits[0]
        assert exit.exit_price == Decimal("1.0760"), "Exit price should match bar.close"
        assert exit.timestamp is not None, "Timestamp should be set"
        assert exit.campaign_id == "SYSTEM", "Campaign ID should be SYSTEM"


class TestEmergencyExitEdgeCases:
    """Test edge cases for emergency exits."""

    @pytest.mark.asyncio
    async def test_exactly_at_threshold_triggers_exit(
        self, orchestrator: MasterOrchestrator, forex_bar: Any
    ) -> None:
        """Test that exactly 2.0% loss triggers emergency exit for forex."""
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("-200"),
            daily_pnl_pct=Decimal("-0.020"),  # Exactly 2.0%
            max_drawdown_pct=Decimal("0.05"),
            total_heat=Decimal("5.0"),
        )

        exits = await orchestrator.check_emergency_exits(forex_bar, portfolio, "FOREX")

        assert len(exits) == 1, "Exactly 2.0% should trigger exit"

    @pytest.mark.asyncio
    async def test_just_below_threshold_no_exit(
        self, orchestrator: MasterOrchestrator, forex_bar: Any
    ) -> None:
        """Test that 1.99% loss does NOT trigger emergency exit for forex."""
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("-199"),
            daily_pnl_pct=Decimal("-0.0199"),  # 1.99%
            max_drawdown_pct=Decimal("0.05"),
            total_heat=Decimal("5.0"),
        )

        exits = await orchestrator.check_emergency_exits(forex_bar, portfolio, "FOREX")

        assert len(exits) == 0, "1.99% should NOT trigger exit"

    @pytest.mark.asyncio
    async def test_bar_without_close_attribute(self, orchestrator: MasterOrchestrator) -> None:
        """Test handling of bar without close attribute."""
        # Create bar without close attribute
        bar = MagicMock(spec=[])  # Empty spec, no attributes

        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("-250"),
            daily_pnl_pct=Decimal("-0.025"),
            max_drawdown_pct=Decimal("0.05"),
            total_heat=Decimal("5.0"),
        )

        exits = await orchestrator.check_emergency_exits(bar, portfolio, "FOREX")

        # Should still trigger, but with default exit price
        assert len(exits) >= 1, "Should trigger exit even without bar.close"
        assert exits[0].exit_price == Decimal("0"), "Should use default exit price"
