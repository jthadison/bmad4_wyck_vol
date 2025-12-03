"""
Unit tests for asset-class-aware emergency exits (Story 8.10.3).

Tests emergency exit conditions with asset-class-specific thresholds:
- Forex: 2% daily loss limit
- Stocks: 3% daily loss limit
- Forex: 3x notional exposure limit
- Universal: 15% max drawdown

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
    """Create MasterOrchestrator instance for testing."""
    # Create orchestrator with minimal dependencies (mocked)
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
def mock_bar() -> Any:
    """Create mock OHLCV bar."""
    bar = MagicMock()
    bar.close = Decimal("100.00")
    return bar


class TestForexDailyLossThreshold:
    """Test forex 2% daily loss threshold vs stock 3% threshold."""

    @pytest.mark.asyncio
    async def test_forex_daily_loss_below_threshold(
        self, orchestrator: MasterOrchestrator, mock_bar: Any
    ) -> None:
        """Test forex with 1.9% loss does not trigger emergency exit."""
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("-190"),
            daily_pnl_pct=Decimal("-0.019"),  # 1.9% loss
            max_drawdown_pct=Decimal("0.05"),
            total_heat=Decimal("5.0"),
        )

        exits = await orchestrator.check_emergency_exits(mock_bar, portfolio, "FOREX")

        assert len(exits) == 0, "Should not trigger emergency exit below 2% threshold"

    @pytest.mark.asyncio
    async def test_forex_daily_loss_at_threshold(
        self, orchestrator: MasterOrchestrator, mock_bar: Any
    ) -> None:
        """Test forex with exactly 2.0% loss triggers emergency exit."""
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("-200"),
            daily_pnl_pct=Decimal("-0.020"),  # Exactly 2.0% loss
            max_drawdown_pct=Decimal("0.05"),
            total_heat=Decimal("5.0"),
        )

        exits = await orchestrator.check_emergency_exits(mock_bar, portfolio, "FOREX")

        assert len(exits) == 1, "Should trigger emergency exit at 2% threshold"
        assert "2%" in exits[0].reason, "Reason should mention 2% threshold"
        assert "FOREX" in exits[0].reason, "Reason should mention FOREX asset class"

    @pytest.mark.asyncio
    async def test_forex_daily_loss_above_threshold(
        self, orchestrator: MasterOrchestrator, mock_bar: Any
    ) -> None:
        """Test forex with 2.1% loss triggers emergency exit."""
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("-210"),
            daily_pnl_pct=Decimal("-0.021"),  # 2.1% loss
            max_drawdown_pct=Decimal("0.05"),
            total_heat=Decimal("5.0"),
        )

        exits = await orchestrator.check_emergency_exits(mock_bar, portfolio, "FOREX")

        assert len(exits) == 1, "Should trigger emergency exit above 2% threshold"
        assert "2%" in exits[0].reason, "Reason should mention 2% threshold"
        assert "FOREX" in exits[0].reason, "Reason should mention FOREX asset class"
        assert exits[0].exit_price == Decimal("100.00"), "Should capture exit price"

    @pytest.mark.asyncio
    async def test_stock_daily_loss_below_threshold(
        self, orchestrator: MasterOrchestrator, mock_bar: Any
    ) -> None:
        """Test stock with 2.5% loss does not trigger emergency exit."""
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("-250"),
            daily_pnl_pct=Decimal("-0.025"),  # 2.5% loss
            max_drawdown_pct=Decimal("0.05"),
            total_heat=Decimal("5.0"),
        )

        exits = await orchestrator.check_emergency_exits(mock_bar, portfolio, "STOCK")

        assert len(exits) == 0, "Should not trigger emergency exit below 3% threshold"

    @pytest.mark.asyncio
    async def test_stock_daily_loss_at_threshold(
        self, orchestrator: MasterOrchestrator, mock_bar: Any
    ) -> None:
        """Test stock with exactly 3.0% loss triggers emergency exit."""
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("-300"),
            daily_pnl_pct=Decimal("-0.030"),  # Exactly 3.0% loss
            max_drawdown_pct=Decimal("0.05"),
            total_heat=Decimal("5.0"),
        )

        exits = await orchestrator.check_emergency_exits(mock_bar, portfolio, "STOCK")

        assert len(exits) == 1, "Should trigger emergency exit at 3% threshold"
        assert "3%" in exits[0].reason, "Reason should mention 3% threshold"
        assert "STOCK" in exits[0].reason, "Reason should mention STOCK asset class"

    @pytest.mark.asyncio
    async def test_stock_daily_loss_above_threshold(
        self, orchestrator: MasterOrchestrator, mock_bar: Any
    ) -> None:
        """Test stock with 3.1% loss triggers emergency exit."""
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("-310"),
            daily_pnl_pct=Decimal("-0.031"),  # 3.1% loss
            max_drawdown_pct=Decimal("0.05"),
            total_heat=Decimal("5.0"),
        )

        exits = await orchestrator.check_emergency_exits(mock_bar, portfolio, "STOCK")

        assert len(exits) == 1, "Should trigger emergency exit above 3% threshold"
        assert "3%" in exits[0].reason, "Reason should mention 3% threshold"
        assert "STOCK" in exits[0].reason, "Reason should mention STOCK asset class"
        assert exits[0].exit_price == Decimal("100.00"), "Should capture exit price"


class TestForexNotionalLimit:
    """Test forex notional exposure limit (3x equity)."""

    @pytest.mark.asyncio
    async def test_forex_notional_within_limit(
        self, orchestrator: MasterOrchestrator, mock_bar: Any
    ) -> None:
        """Test forex notional at 2.5x equity (within 3x limit)."""
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("0"),
            daily_pnl_pct=Decimal("0"),
            max_drawdown_pct=Decimal("0.05"),
            total_heat=Decimal("5.0"),
            total_forex_notional=Decimal("25000"),  # 2.5x equity
            max_forex_notional=Decimal("30000"),  # 3x equity limit
        )

        exits = await orchestrator.check_emergency_exits(mock_bar, portfolio, "FOREX")

        assert len(exits) == 0, "Should not trigger exit within 3x limit"

    @pytest.mark.asyncio
    async def test_forex_notional_at_limit(
        self, orchestrator: MasterOrchestrator, mock_bar: Any
    ) -> None:
        """Test forex notional exactly at 3x equity limit."""
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("0"),
            daily_pnl_pct=Decimal("0"),
            max_drawdown_pct=Decimal("0.05"),
            total_heat=Decimal("5.0"),
            total_forex_notional=Decimal("30000"),  # Exactly 3x equity
            max_forex_notional=Decimal("30000"),
        )

        exits = await orchestrator.check_emergency_exits(mock_bar, portfolio, "FOREX")

        # At limit should not trigger (only > triggers)
        assert len(exits) == 0, "Should not trigger exit at exactly 3x limit"

    @pytest.mark.asyncio
    async def test_forex_notional_exceeds_limit(
        self, orchestrator: MasterOrchestrator, mock_bar: Any
    ) -> None:
        """Test forex notional at 3.5x equity (exceeds 3x limit)."""
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("0"),
            daily_pnl_pct=Decimal("0"),
            max_drawdown_pct=Decimal("0.05"),
            total_heat=Decimal("5.0"),
            total_forex_notional=Decimal("35000"),  # 3.5x equity
            max_forex_notional=Decimal("30000"),  # 3x equity limit
        )

        exits = await orchestrator.check_emergency_exits(mock_bar, portfolio, "FOREX")

        assert len(exits) == 1, "Should trigger exit when exceeding 3x limit"
        assert "Forex notional" in exits[0].reason, "Reason should mention forex notional"
        assert "$35,000" in exits[0].reason, "Reason should include actual notional"
        assert "$30,000" in exits[0].reason, "Reason should include limit"

    @pytest.mark.asyncio
    async def test_stock_notional_check_skipped(
        self, orchestrator: MasterOrchestrator, mock_bar: Any
    ) -> None:
        """Test forex notional check is skipped for STOCK asset class."""
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("0"),
            daily_pnl_pct=Decimal("0"),
            max_drawdown_pct=Decimal("0.05"),
            total_heat=Decimal("5.0"),
            total_forex_notional=Decimal("35000"),  # Would exceed if checked
            max_forex_notional=Decimal("30000"),
        )

        exits = await orchestrator.check_emergency_exits(mock_bar, portfolio, "STOCK")

        # No exits for stock, even with high forex notional
        assert len(exits) == 0, "Should not check forex notional for STOCK asset class"


class TestMaxDrawdown:
    """Test max drawdown check (universal for all asset classes)."""

    @pytest.mark.asyncio
    async def test_max_drawdown_below_threshold_forex(
        self, orchestrator: MasterOrchestrator, mock_bar: Any
    ) -> None:
        """Test forex with 14% drawdown does not trigger."""
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("0"),
            daily_pnl_pct=Decimal("0"),
            max_drawdown_pct=Decimal("0.14"),  # 14%
            total_heat=Decimal("5.0"),
        )

        exits = await orchestrator.check_emergency_exits(mock_bar, portfolio, "FOREX")

        assert len(exits) == 0, "Should not trigger below 15% threshold"
        assert orchestrator._system_halted is False, "System should not be halted"

    @pytest.mark.asyncio
    async def test_max_drawdown_at_threshold_stock(
        self, orchestrator: MasterOrchestrator, mock_bar: Any
    ) -> None:
        """Test stock with exactly 15% drawdown triggers system halt."""
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("0"),
            daily_pnl_pct=Decimal("0"),
            max_drawdown_pct=Decimal("0.15"),  # Exactly 15%
            total_heat=Decimal("5.0"),
        )

        exits = await orchestrator.check_emergency_exits(mock_bar, portfolio, "STOCK")

        assert len(exits) == 1, "Should trigger exit at 15% threshold"
        assert "Max drawdown" in exits[0].reason, "Reason should mention max drawdown"
        assert "15%" in exits[0].reason, "Reason should mention 15% limit"
        assert "STOCK" in exits[0].reason, "Reason should mention asset class"
        assert orchestrator._system_halted is True, "System should be halted"

    @pytest.mark.asyncio
    async def test_max_drawdown_above_threshold_forex(
        self, orchestrator: MasterOrchestrator, mock_bar: Any
    ) -> None:
        """Test forex with 18% drawdown triggers system halt."""
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("0"),
            daily_pnl_pct=Decimal("0"),
            max_drawdown_pct=Decimal("0.18"),  # 18%
            total_heat=Decimal("5.0"),
        )

        exits = await orchestrator.check_emergency_exits(mock_bar, portfolio, "FOREX")

        assert len(exits) == 1, "Should trigger exit above 15% threshold"
        assert "Max drawdown" in exits[0].reason, "Reason should mention max drawdown"
        assert "FOREX" in exits[0].reason, "Reason should mention asset class"
        assert orchestrator._system_halted is True, "System should be halted"


class TestMultipleEmergencyConditions:
    """Test scenarios where multiple emergency conditions trigger."""

    @pytest.mark.asyncio
    async def test_forex_daily_loss_and_notional_both_trigger(
        self, orchestrator: MasterOrchestrator, mock_bar: Any
    ) -> None:
        """Test forex with both daily loss and notional violations."""
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("-250"),
            daily_pnl_pct=Decimal("-0.025"),  # 2.5% loss (exceeds 2%)
            max_drawdown_pct=Decimal("0.10"),
            total_heat=Decimal("5.0"),
            total_forex_notional=Decimal("35000"),  # Exceeds 3x limit
            max_forex_notional=Decimal("30000"),
        )

        exits = await orchestrator.check_emergency_exits(mock_bar, portfolio, "FOREX")

        assert len(exits) == 2, "Should trigger both daily loss and notional exits"
        reasons = [exit.reason for exit in exits]
        assert any("Daily loss" in r for r in reasons), "Should have daily loss exit"
        assert any("Forex notional" in r for r in reasons), "Should have notional exit"

    @pytest.mark.asyncio
    async def test_max_drawdown_and_daily_loss_both_trigger(
        self, orchestrator: MasterOrchestrator, mock_bar: Any
    ) -> None:
        """Test stock with both max drawdown and daily loss violations."""
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("-350"),
            daily_pnl_pct=Decimal("-0.035"),  # 3.5% loss
            max_drawdown_pct=Decimal("0.16"),  # 16% drawdown
            total_heat=Decimal("5.0"),
        )

        exits = await orchestrator.check_emergency_exits(mock_bar, portfolio, "STOCK")

        assert len(exits) == 2, "Should trigger both max drawdown and daily loss exits"
        reasons = [exit.reason for exit in exits]
        assert any("Daily loss" in r for r in reasons), "Should have daily loss exit"
        assert any("Max drawdown" in r for r in reasons), "Should have max drawdown exit"
        assert orchestrator._system_halted is True, "System should be halted"


class TestCryptoAssetClass:
    """Test CRYPTO asset class uses 3% daily loss threshold."""

    @pytest.mark.asyncio
    async def test_crypto_uses_3_percent_threshold(
        self, orchestrator: MasterOrchestrator, mock_bar: Any
    ) -> None:
        """Test crypto with 2.5% loss does not trigger (uses 3% like stocks)."""
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("-250"),
            daily_pnl_pct=Decimal("-0.025"),  # 2.5% loss
            max_drawdown_pct=Decimal("0.05"),
            total_heat=Decimal("5.0"),
        )

        exits = await orchestrator.check_emergency_exits(mock_bar, portfolio, "CRYPTO")

        assert len(exits) == 0, "Should not trigger below 3% threshold"

    @pytest.mark.asyncio
    async def test_crypto_triggers_at_3_percent(
        self, orchestrator: MasterOrchestrator, mock_bar: Any
    ) -> None:
        """Test crypto with 3.1% loss triggers emergency exit."""
        portfolio = PortfolioState(
            total_equity=Decimal("10000"),
            available_equity=Decimal("8000"),
            daily_pnl=Decimal("-310"),
            daily_pnl_pct=Decimal("-0.031"),  # 3.1% loss
            max_drawdown_pct=Decimal("0.05"),
            total_heat=Decimal("5.0"),
        )

        exits = await orchestrator.check_emergency_exits(mock_bar, portfolio, "CRYPTO")

        assert len(exits) == 1, "Should trigger exit above 3% threshold"
        assert "3%" in exits[0].reason, "Reason should mention 3% threshold"
        assert "CRYPTO" in exits[0].reason, "Reason should mention CRYPTO asset class"
