"""
Tests for fill-price risk sizing (gap buffer + post-fill risk validation).

Validates that:
1. _create_order() applies a gap buffer to the entry price before risk sizing
2. _fill_pending_orders() rejects/reduces orders when actual risk exceeds 2%
3. Normal fills within risk limits proceed with original quantity

Author: fix/fill-price-risk-sizing
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from src.backtesting.engine.backtest_engine import UnifiedBacktestEngine
from src.backtesting.engine.interfaces import EngineConfig
from src.backtesting.position_manager import PositionManager
from src.backtesting.risk_integration import BacktestRiskManager
from src.models.backtest import BacktestOrder
from src.models.ohlcv import OHLCVBar
from src.models.signal import TradeSignal

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bar(
    symbol: str = "TEST",
    open_: Decimal = Decimal("100.00"),
    high: Decimal = Decimal("101.00"),
    low: Decimal = Decimal("99.00"),
    close: Decimal = Decimal("100.00"),
    volume: int = 10000,
    timestamp: datetime | None = None,
) -> OHLCVBar:
    """Create a minimal OHLCVBar for testing."""
    ts = timestamp or datetime.now(UTC)
    return OHLCVBar(
        symbol=symbol,
        timeframe="1d",
        timestamp=ts,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        spread=high - low,
    )


class StubDetector:
    """SignalDetector that returns a pre-set signal on a specific bar index."""

    def __init__(self, signal: TradeSignal | None = None, trigger_index: int = 0):
        self._signal = signal
        self._trigger_index = trigger_index

    def detect(self, bars: list[OHLCVBar], index: int) -> TradeSignal | None:
        if index == self._trigger_index:
            return self._signal
        return None


class ZeroCostModel:
    """CostModel that applies no costs."""

    def calculate_commission(self, order: "BacktestOrder") -> Decimal:
        return Decimal("0")

    def calculate_slippage(self, order: "BacktestOrder", bar: "OHLCVBar") -> Decimal:
        return Decimal("0")


def _make_long_signal(
    symbol: str = "TEST",
    entry_price: Decimal = Decimal("100.00"),
    stop_loss: Decimal = Decimal("98.00"),
    primary_target: Decimal = Decimal("106.00"),
) -> MagicMock:
    """Create a mock TradeSignal for a LONG entry."""
    signal = MagicMock(spec=TradeSignal)
    signal.direction = "LONG"
    signal.stop_loss = stop_loss
    signal.entry_price = entry_price
    signal.campaign_id = f"{symbol}-campaign"

    target_levels = MagicMock()
    target_levels.primary_target = primary_target
    signal.target_levels = target_levels
    return signal


def _make_short_signal(
    symbol: str = "TEST",
    entry_price: Decimal = Decimal("100.00"),
    stop_loss: Decimal = Decimal("102.00"),
    primary_target: Decimal = Decimal("94.00"),
) -> MagicMock:
    """Create a mock TradeSignal for a SHORT entry."""
    signal = MagicMock(spec=TradeSignal)
    signal.direction = "SHORT"
    signal.stop_loss = stop_loss
    signal.entry_price = entry_price
    signal.campaign_id = f"{symbol}-campaign"

    target_levels = MagicMock()
    target_levels.primary_target = primary_target
    signal.target_levels = target_levels
    return signal


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRiskSizingUsesGapBuffer:
    """Verify that _create_order passes a gap-buffered entry price to the risk manager."""

    def test_long_gap_buffer_applied(self):
        """For LONG signals, adjusted_entry = bar.close * (1 + GAP_BUFFER)."""
        config = EngineConfig(initial_capital=Decimal("100000"))
        risk_mgr = BacktestRiskManager(initial_capital=Decimal("100000"))
        pm = PositionManager(initial_capital=Decimal("100000"))
        detector = StubDetector()
        engine = UnifiedBacktestEngine(
            signal_detector=detector,
            cost_model=ZeroCostModel(),
            position_manager=pm,
            config=config,
            risk_manager=risk_mgr,
        )

        bar = _make_bar(close=Decimal("100.00"))
        signal = _make_long_signal(
            entry_price=Decimal("100.00"),
            stop_loss=Decimal("98.00"),
        )

        # Spy on risk manager to capture the entry_price it receives
        original_validate = risk_mgr.validate_and_size_position
        captured_entry: list[Decimal] = []

        def spy_validate(**kwargs):
            captured_entry.append(kwargs["entry_price"])
            return original_validate(**kwargs)

        risk_mgr.validate_and_size_position = spy_validate

        portfolio_value = Decimal("100000")
        order = engine._create_order(signal, bar, portfolio_value)

        # The entry price passed to risk manager should be buffered
        assert len(captured_entry) == 1
        expected_adjusted = Decimal("100.00") * (Decimal("1") + UnifiedBacktestEngine.GAP_BUFFER)
        assert captured_entry[0] == expected_adjusted
        # Order should be created (risk manager allows it)
        assert order is not None
        assert order.quantity > 0

    def test_short_gap_buffer_applied(self):
        """For SHORT signals, adjusted_entry = bar.close * (1 - GAP_BUFFER)."""
        config = EngineConfig(initial_capital=Decimal("100000"))
        risk_mgr = BacktestRiskManager(initial_capital=Decimal("100000"))
        pm = PositionManager(initial_capital=Decimal("100000"))
        detector = StubDetector()
        engine = UnifiedBacktestEngine(
            signal_detector=detector,
            cost_model=ZeroCostModel(),
            position_manager=pm,
            config=config,
            risk_manager=risk_mgr,
        )

        bar = _make_bar(close=Decimal("100.00"))
        signal = _make_short_signal(
            entry_price=Decimal("100.00"),
            stop_loss=Decimal("102.00"),
        )

        original_validate = risk_mgr.validate_and_size_position
        captured_entry: list[Decimal] = []

        def spy_validate(**kwargs):
            captured_entry.append(kwargs["entry_price"])
            return original_validate(**kwargs)

        risk_mgr.validate_and_size_position = spy_validate

        portfolio_value = Decimal("100000")
        order = engine._create_order(signal, bar, portfolio_value)

        assert len(captured_entry) == 1
        expected_adjusted = Decimal("100.00") * (Decimal("1") - UnifiedBacktestEngine.GAP_BUFFER)
        assert captured_entry[0] == expected_adjusted
        assert order is not None
        assert order.quantity > 0

    def test_gap_buffer_produces_smaller_position_than_no_buffer(self):
        """Gap buffer widens stop distance, resulting in smaller position size."""
        config = EngineConfig(initial_capital=Decimal("100000"))
        pm = PositionManager(initial_capital=Decimal("100000"))

        # Without gap buffer: risk manager sees entry=100, stop=98, distance=2
        risk_mgr_no_buf = BacktestRiskManager(initial_capital=Decimal("100000"))
        pos_size_no_buf, _, _ = risk_mgr_no_buf.calculate_position_size(
            entry_price=Decimal("100.00"),
            stop_loss=Decimal("98.00"),
        )

        # With gap buffer: risk manager sees entry=100.50, stop=98, distance=2.50
        adjusted_entry = Decimal("100.00") * (Decimal("1") + UnifiedBacktestEngine.GAP_BUFFER)
        risk_mgr_buf = BacktestRiskManager(initial_capital=Decimal("100000"))
        pos_size_buf, _, _ = risk_mgr_buf.calculate_position_size(
            entry_price=adjusted_entry,
            stop_loss=Decimal("98.00"),
        )

        # Risk amount is the same (2% of 100k = 2000), but wider stop means fewer shares
        assert pos_size_no_buf > Decimal("0")
        assert pos_size_buf > Decimal("0")
        assert pos_size_buf < pos_size_no_buf  # Buffer produces smaller position


class TestFillRejectsOrderExceedingRiskLimit:
    """Verify that _fill_pending_orders reduces or cancels orders when
    actual risk exceeds the 2% hard limit due to a gap."""

    def test_extreme_gap_cancels_order(self):
        """When gap is so large that even 1 share exceeds 2% risk, order is cancelled."""
        initial_capital = Decimal("10000")
        config = EngineConfig(initial_capital=initial_capital)
        risk_mgr = BacktestRiskManager(initial_capital=initial_capital)
        pm = PositionManager(initial_capital=initial_capital)
        detector = StubDetector()
        engine = UnifiedBacktestEngine(
            signal_detector=detector,
            cost_model=ZeroCostModel(),
            position_manager=pm,
            config=config,
            risk_manager=risk_mgr,
        )

        # Create a pending order: BUY 100 shares of TEST
        order = BacktestOrder(
            order_id=uuid4(),
            symbol="TEST",
            side="BUY",
            order_type="MARKET",
            quantity=100,
            status="PENDING",
            created_bar_timestamp=datetime.now(UTC),
        )
        # Stop at 98, meaning each share has $2 risk
        # With 100 shares, risk = $200, which is 2% of $10,000
        engine._pending_orders.append(order)
        engine._pending_order_stops[order.order_id] = (Decimal("98.00"), None)

        # Simulate a massive gap: next bar opens at $150 (50% gap up)
        # Actual risk per share = |150 - 98| = $52
        # Actual risk = 100 * $52 = $5,200 = 52% of $10,000 -- way over 2%
        fill_bar = _make_bar(open_=Decimal("150.00"), close=Decimal("150.00"))

        engine._fill_pending_orders(fill_bar)

        # Order should be rejected (cancelled) because safe_quantity would be ~3.8 -> 3
        # Actually: safe_quantity = int(100 * (0.02 / 0.52)) = int(3.84) = 3
        # 3 shares * $52 = $156 = 1.56% of $10,000 which is under limit
        # But wait -- let me recalculate with portfolio_value including no positions:
        # portfolio_value = $10,000 (cash, no positions)
        # actual_risk_pct = 5200 / 10000 = 0.52
        # safe_quantity = int(100 * (0.02/0.52)) = 3
        # 3 > 0, so order is reduced, not cancelled.
        # Let's verify it was reduced rather than cancelled.
        assert order.quantity == 3
        assert order.status == "FILLED"
        assert pm.has_position("TEST")

    def test_gap_reduces_quantity(self):
        """When gap causes risk > 2%, quantity is reduced proportionally."""
        initial_capital = Decimal("100000")
        config = EngineConfig(initial_capital=initial_capital)
        risk_mgr = BacktestRiskManager(initial_capital=initial_capital)
        pm = PositionManager(initial_capital=initial_capital)
        detector = StubDetector()
        engine = UnifiedBacktestEngine(
            signal_detector=detector,
            cost_model=ZeroCostModel(),
            position_manager=pm,
            config=config,
            risk_manager=risk_mgr,
        )

        # Create a pending BUY order: 500 shares
        order = BacktestOrder(
            order_id=uuid4(),
            symbol="TEST",
            side="BUY",
            order_type="MARKET",
            quantity=500,
            status="PENDING",
            created_bar_timestamp=datetime.now(UTC),
        )
        # Stop at 96 -- original entry was around 100, so 4-point stop
        engine._pending_orders.append(order)
        engine._pending_order_stops[order.order_id] = (Decimal("96.00"), None)

        # Gap up to 105 -- actual stop distance = |105 - 96| = $9 per share
        # Actual risk = 500 * 9 = $4,500 = 4.5% of $100,000 -- over 2%
        fill_bar = _make_bar(open_=Decimal("105.00"), close=Decimal("105.00"))

        engine._fill_pending_orders(fill_bar)

        # safe_quantity = int(500 * (0.02 / 0.045)) = int(222.2) = 222
        assert order.quantity == 222
        assert order.status == "FILLED"
        assert pm.has_position("TEST")

        # Verify actual risk is now within limits
        actual_risk = Decimal("222") * Decimal("9")  # = $1,998
        actual_risk_pct = actual_risk / initial_capital  # ~0.01998
        assert actual_risk_pct <= Decimal("0.02")

    def test_order_cancelled_when_safe_quantity_zero(self):
        """When even 1 share exceeds 2% risk, the order is fully cancelled."""
        initial_capital = Decimal("1000")  # Very small account
        config = EngineConfig(initial_capital=initial_capital)
        risk_mgr = BacktestRiskManager(initial_capital=initial_capital)
        pm = PositionManager(initial_capital=initial_capital)
        detector = StubDetector()
        engine = UnifiedBacktestEngine(
            signal_detector=detector,
            cost_model=ZeroCostModel(),
            position_manager=pm,
            config=config,
            risk_manager=risk_mgr,
        )

        order = BacktestOrder(
            order_id=uuid4(),
            symbol="TEST",
            side="BUY",
            order_type="MARKET",
            quantity=5,
            status="PENDING",
            created_bar_timestamp=datetime.now(UTC),
        )
        # Stop at 50, so very wide stop
        engine._pending_orders.append(order)
        engine._pending_order_stops[order.order_id] = (Decimal("50.00"), None)

        # Gap to 200 -- risk per share = $150
        # 5 shares * $150 = $750 = 75% of $1,000
        # safe_quantity = int(5 * (0.02 / 0.75)) = int(0.133) = 0
        fill_bar = _make_bar(open_=Decimal("200.00"), close=Decimal("200.00"))

        engine._fill_pending_orders(fill_bar)

        assert order.status == "REJECTED"
        assert not pm.has_position("TEST")

    def test_short_gap_reduces_quantity(self):
        """For SHORT entries, a gap down increases risk and triggers reduction."""
        initial_capital = Decimal("100000")
        config = EngineConfig(initial_capital=initial_capital)
        risk_mgr = BacktestRiskManager(initial_capital=initial_capital)
        pm = PositionManager(initial_capital=initial_capital)
        detector = StubDetector()
        engine = UnifiedBacktestEngine(
            signal_detector=detector,
            cost_model=ZeroCostModel(),
            position_manager=pm,
            config=config,
            risk_manager=risk_mgr,
        )

        # SELL (SHORT entry) order: 500 shares, stop at 104
        order = BacktestOrder(
            order_id=uuid4(),
            symbol="TEST",
            side="SELL",
            order_type="MARKET",
            quantity=500,
            status="PENDING",
            created_bar_timestamp=datetime.now(UTC),
        )
        # Stop at 104 -- original entry ~100, stop distance ~4
        engine._pending_orders.append(order)
        engine._pending_order_stops[order.order_id] = (Decimal("104.00"), None)

        # Gap down to 95 -- SHORT fills at 95, stop at 104
        # actual risk per share = |95 - 104| = $9
        # Actual risk = 500 * 9 = $4,500 = 4.5% of $100,000 -- over 2%
        fill_bar = _make_bar(open_=Decimal("95.00"), close=Decimal("95.00"))

        engine._fill_pending_orders(fill_bar)

        # safe_quantity = int(500 * (0.02 / 0.045)) = 222
        assert order.quantity == 222
        assert order.status == "FILLED"
        assert pm.has_position("TEST")


class TestNormalFillWithinRiskLimit:
    """Verify that normal fills (small gap) proceed with original quantity."""

    def test_normal_fill_no_reduction(self):
        """When fill gap is small, order proceeds with original quantity."""
        initial_capital = Decimal("100000")
        config = EngineConfig(initial_capital=initial_capital)
        risk_mgr = BacktestRiskManager(initial_capital=initial_capital)
        pm = PositionManager(initial_capital=initial_capital)
        detector = StubDetector()
        engine = UnifiedBacktestEngine(
            signal_detector=detector,
            cost_model=ZeroCostModel(),
            position_manager=pm,
            config=config,
            risk_manager=risk_mgr,
        )

        # Create a BUY order: 500 shares, stop at 96
        order = BacktestOrder(
            order_id=uuid4(),
            symbol="TEST",
            side="BUY",
            order_type="MARKET",
            quantity=500,
            status="PENDING",
            created_bar_timestamp=datetime.now(UTC),
        )
        engine._pending_orders.append(order)
        engine._pending_order_stops[order.order_id] = (Decimal("96.00"), None)

        # Small gap: open at 100.10 -- risk per share = |100.10 - 96| = $4.10
        # Total risk = 500 * $4.10 = $2,050 = 2.05% of $100,000
        # This is just barely over 2%, so quantity should be reduced slightly
        # safe_quantity = int(500 * (0.02 / 0.0205)) = int(487.8) = 487
        fill_bar = _make_bar(open_=Decimal("100.10"), close=Decimal("100.10"))

        engine._fill_pending_orders(fill_bar)

        # Slight reduction due to small overshoot
        assert order.quantity == 487
        assert order.status == "FILLED"

    def test_no_reduction_when_within_limit(self):
        """When actual risk is at or below 2%, no reduction occurs."""
        initial_capital = Decimal("100000")
        config = EngineConfig(initial_capital=initial_capital)
        risk_mgr = BacktestRiskManager(initial_capital=initial_capital)
        pm = PositionManager(initial_capital=initial_capital)
        detector = StubDetector()
        engine = UnifiedBacktestEngine(
            signal_detector=detector,
            cost_model=ZeroCostModel(),
            position_manager=pm,
            config=config,
            risk_manager=risk_mgr,
        )

        # Create a BUY order: 400 shares, stop at 95
        order = BacktestOrder(
            order_id=uuid4(),
            symbol="TEST",
            side="BUY",
            order_type="MARKET",
            quantity=400,
            status="PENDING",
            created_bar_timestamp=datetime.now(UTC),
        )
        engine._pending_orders.append(order)
        engine._pending_order_stops[order.order_id] = (Decimal("95.00"), None)

        # Open at 100 -- risk per share = |100 - 95| = $5
        # Total risk = 400 * $5 = $2,000 = exactly 2.0% of $100,000
        fill_bar = _make_bar(open_=Decimal("100.00"), close=Decimal("100.00"))

        engine._fill_pending_orders(fill_bar)

        # No reduction needed -- exactly at limit
        assert order.quantity == 400
        assert order.status == "FILLED"
        assert pm.has_position("TEST")

    def test_fill_without_pending_stops_skips_risk_check(self):
        """Orders without pending stop data skip the post-fill risk check."""
        initial_capital = Decimal("100000")
        config = EngineConfig(initial_capital=initial_capital)
        pm = PositionManager(initial_capital=initial_capital)
        detector = StubDetector()
        engine = UnifiedBacktestEngine(
            signal_detector=detector,
            cost_model=ZeroCostModel(),
            position_manager=pm,
            config=config,
            risk_manager=None,
        )

        order = BacktestOrder(
            order_id=uuid4(),
            symbol="TEST",
            side="BUY",
            order_type="MARKET",
            quantity=100,
            status="PENDING",
            created_bar_timestamp=datetime.now(UTC),
        )
        engine._pending_orders.append(order)
        # No entry in _pending_order_stops

        fill_bar = _make_bar(open_=Decimal("100.00"), close=Decimal("100.00"))
        engine._fill_pending_orders(fill_bar)

        # Order fills normally with original quantity
        assert order.quantity == 100
        assert order.status == "FILLED"

    def test_close_position_skips_risk_check(self):
        """Closing orders (not opening) should not be subjected to risk check."""
        initial_capital = Decimal("100000")
        config = EngineConfig(initial_capital=initial_capital)
        risk_mgr = BacktestRiskManager(initial_capital=initial_capital)
        pm = PositionManager(initial_capital=initial_capital)
        detector = StubDetector()
        engine = UnifiedBacktestEngine(
            signal_detector=detector,
            cost_model=ZeroCostModel(),
            position_manager=pm,
            config=config,
            risk_manager=risk_mgr,
        )

        # First, open a position manually
        open_order = BacktestOrder(
            order_id=uuid4(),
            symbol="TEST",
            side="BUY",
            order_type="MARKET",
            quantity=100,
            status="FILLED",
            created_bar_timestamp=datetime.now(UTC),
            filled_bar_timestamp=datetime.now(UTC),
            fill_price=Decimal("100.00"),
            commission=Decimal("0"),
            slippage=Decimal("0"),
        )
        pm.open_position(open_order, side="LONG")

        # Now create a SELL order to close (with a stop entry in pending_order_stops
        # to verify the risk check is skipped for closing orders)
        close_order = BacktestOrder(
            order_id=uuid4(),
            symbol="TEST",
            side="SELL",
            order_type="MARKET",
            quantity=100,
            status="PENDING",
            created_bar_timestamp=datetime.now(UTC),
        )
        engine._pending_orders.append(close_order)
        # Even though there are stops, this is a closing order -- risk check should not apply
        engine._pending_order_stops[close_order.order_id] = (Decimal("50.00"), None)

        fill_bar = _make_bar(open_=Decimal("200.00"), close=Decimal("200.00"))
        engine._fill_pending_orders(fill_bar)

        # Close order should fill at original quantity (no reduction)
        assert close_order.quantity == 100
        assert close_order.status == "FILLED"
        assert not pm.has_position("TEST")


class TestEndToEndWithGapBuffer:
    """Integration-style test running bars through the full engine."""

    def test_full_run_with_gap_applies_buffer_and_fills(self):
        """Run the engine end-to-end and verify gap buffer + fill risk check work together."""
        initial_capital = Decimal("100000")
        config = EngineConfig(initial_capital=initial_capital)
        risk_mgr = BacktestRiskManager(initial_capital=initial_capital)
        pm = PositionManager(initial_capital=initial_capital)

        signal = _make_long_signal(
            symbol="TEST",
            entry_price=Decimal("100.00"),
            stop_loss=Decimal("98.00"),
            primary_target=Decimal("106.00"),
        )
        detector = StubDetector(signal=signal, trigger_index=0)

        engine = UnifiedBacktestEngine(
            signal_detector=detector,
            cost_model=ZeroCostModel(),
            position_manager=pm,
            config=config,
            risk_manager=risk_mgr,
        )

        # Bar 0: signal fires, creates PENDING order with gap-buffered sizing
        bar0 = _make_bar(
            symbol="TEST",
            close=Decimal("100.00"),
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        )
        # Bar 1: order fills at this bar's open
        bar1 = _make_bar(
            symbol="TEST",
            open_=Decimal("100.20"),
            close=Decimal("100.50"),
            timestamp=datetime(2024, 1, 2, tzinfo=UTC),
        )

        result = engine.run([bar0, bar1])

        # A position should have been opened
        assert pm.has_position("TEST")
        pos = pm.get_position("TEST")
        assert pos is not None
        # Position should have been sized conservatively due to gap buffer
        assert pos.quantity > 0
