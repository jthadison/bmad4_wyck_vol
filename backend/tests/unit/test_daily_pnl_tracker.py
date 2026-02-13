"""
Unit tests for DailyPnLTracker - Story 23.13
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from src.monitoring.daily_pnl_tracker import DailyPnLTracker


@pytest.fixture
def tracker() -> DailyPnLTracker:
    return DailyPnLTracker(threshold_pct=Decimal("-3.0"))


@pytest.mark.asyncio
async def test_initial_state(tracker: DailyPnLTracker) -> None:
    """Tracker starts at zero P&L."""
    assert tracker.get_daily_pnl() == Decimal("0")
    assert tracker.breach_fired is False


@pytest.mark.asyncio
async def test_pnl_accumulation(tracker: DailyPnLTracker) -> None:
    """P&L accumulates across multiple updates."""
    await tracker.update_pnl("AAPL", Decimal("-100"))
    await tracker.update_pnl("TSLA", Decimal("-200"))
    await tracker.update_pnl("AAPL", Decimal("-50"))

    assert tracker.get_daily_pnl() == Decimal("-350")


@pytest.mark.asyncio
async def test_pnl_accumulation_mixed(tracker: DailyPnLTracker) -> None:
    """Positive and negative P&L netted correctly."""
    await tracker.update_pnl("AAPL", Decimal("-500"))
    await tracker.update_pnl("TSLA", Decimal("300"))

    assert tracker.get_daily_pnl() == Decimal("-200")


@pytest.mark.asyncio
async def test_pnl_percentage(tracker: DailyPnLTracker) -> None:
    """Percentage calculation based on equity."""
    await tracker.update_pnl("AAPL", Decimal("-3000"))
    equity = Decimal("100000")
    pct = tracker.get_pnl_percentage(equity)
    assert pct == Decimal("-3")


@pytest.mark.asyncio
async def test_pnl_percentage_zero_equity(tracker: DailyPnLTracker) -> None:
    """Zero equity returns -100."""
    await tracker.update_pnl("AAPL", Decimal("-100"))
    assert tracker.get_pnl_percentage(Decimal("0")) == Decimal("-100")


@pytest.mark.asyncio
async def test_threshold_not_breached(tracker: DailyPnLTracker) -> None:
    """Below threshold loss does not trigger breach."""
    await tracker.update_pnl("AAPL", Decimal("-1000"))
    equity = Decimal("100000")
    assert tracker.check_threshold(equity) is False


@pytest.mark.asyncio
async def test_threshold_breached(tracker: DailyPnLTracker) -> None:
    """Loss at threshold triggers breach."""
    await tracker.update_pnl("AAPL", Decimal("-3000"))
    equity = Decimal("100000")
    assert tracker.check_threshold(equity) is True


@pytest.mark.asyncio
async def test_threshold_breached_beyond(tracker: DailyPnLTracker) -> None:
    """Loss beyond threshold triggers breach."""
    await tracker.update_pnl("AAPL", Decimal("-5000"))
    equity = Decimal("100000")
    assert tracker.check_threshold(equity) is True


@pytest.mark.asyncio
async def test_callback_on_breach() -> None:
    """Callback fires when threshold breached."""
    callback = AsyncMock()
    tracker = DailyPnLTracker(
        threshold_pct=Decimal("-3.0"),
        on_threshold_breach=callback,
    )
    await tracker.update_pnl("AAPL", Decimal("-3500"))
    equity = Decimal("100000")

    result = await tracker.check_and_notify(equity)

    assert result is True
    callback.assert_awaited_once()
    args = callback.call_args[0]
    assert args[0] == Decimal("-3.5")  # pnl_pct
    assert args[1] == Decimal("-3500")  # cumulative_pnl


@pytest.mark.asyncio
async def test_callback_fires_only_once() -> None:
    """Callback fires only once per day (until reset)."""
    callback = AsyncMock()
    tracker = DailyPnLTracker(
        threshold_pct=Decimal("-3.0"),
        on_threshold_breach=callback,
    )
    await tracker.update_pnl("AAPL", Decimal("-4000"))
    equity = Decimal("100000")

    await tracker.check_and_notify(equity)
    await tracker.check_and_notify(equity)

    assert callback.await_count == 1


@pytest.mark.asyncio
async def test_callback_error_handled() -> None:
    """Callback exceptions are caught and logged."""
    callback = AsyncMock(side_effect=RuntimeError("boom"))
    tracker = DailyPnLTracker(
        threshold_pct=Decimal("-3.0"),
        on_threshold_breach=callback,
    )
    await tracker.update_pnl("AAPL", Decimal("-4000"))

    # Should not raise
    result = await tracker.check_and_notify(Decimal("100000"))
    assert result is True


@pytest.mark.asyncio
async def test_reset(tracker: DailyPnLTracker) -> None:
    """Reset clears cumulative P&L and breach state."""
    await tracker.update_pnl("AAPL", Decimal("-5000"))
    await tracker.reset()

    assert tracker.get_daily_pnl() == Decimal("0")
    assert tracker.breach_fired is False
    assert tracker.get_symbol_pnl() == {}


@pytest.mark.asyncio
async def test_callback_fires_after_reset() -> None:
    """After reset, callback can fire again."""
    callback = AsyncMock()
    tracker = DailyPnLTracker(
        threshold_pct=Decimal("-3.0"),
        on_threshold_breach=callback,
    )
    await tracker.update_pnl("AAPL", Decimal("-4000"))
    await tracker.check_and_notify(Decimal("100000"))
    assert callback.await_count == 1

    await tracker.reset()
    await tracker.update_pnl("AAPL", Decimal("-4000"))
    await tracker.check_and_notify(Decimal("100000"))
    assert callback.await_count == 2


@pytest.mark.asyncio
async def test_configurable_threshold() -> None:
    """Custom threshold respected."""
    tracker = DailyPnLTracker(threshold_pct=Decimal("-5.0"))
    await tracker.update_pnl("AAPL", Decimal("-3000"))
    equity = Decimal("100000")

    assert tracker.check_threshold(equity) is False  # -3% < -5% threshold

    await tracker.update_pnl("TSLA", Decimal("-2000"))
    assert tracker.check_threshold(equity) is True  # -5% hits threshold


@pytest.mark.asyncio
async def test_symbol_pnl_breakdown(tracker: DailyPnLTracker) -> None:
    """Per-symbol breakdown tracked correctly."""
    await tracker.update_pnl("AAPL", Decimal("-100"))
    await tracker.update_pnl("TSLA", Decimal("-200"))
    await tracker.update_pnl("AAPL", Decimal("-50"))

    breakdown = tracker.get_symbol_pnl()
    assert breakdown["AAPL"] == Decimal("-150")
    assert breakdown["TSLA"] == Decimal("-200")


@pytest.mark.asyncio
async def test_no_callback_when_not_breached() -> None:
    """check_and_notify returns False when no breach."""
    callback = AsyncMock()
    tracker = DailyPnLTracker(
        threshold_pct=Decimal("-3.0"),
        on_threshold_breach=callback,
    )
    await tracker.update_pnl("AAPL", Decimal("-100"))

    result = await tracker.check_and_notify(Decimal("100000"))
    assert result is False
    callback.assert_not_awaited()
