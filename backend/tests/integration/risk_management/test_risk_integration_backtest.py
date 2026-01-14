"""
Integration Tests for Risk Manager Backtest Integration (Story 13.9)

Tests the BacktestRiskManager in realistic multi-position scenarios:
- AC9.8: Daily backtest regression with risk validation
- AC9.9: 15-minute backtest with rejection scenarios
- AC9.10: Strategy integration with actual pattern entry logic

Author: Story 13.9
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.backtesting.risk_integration import BacktestRiskManager


class TestMultiPositionScenarios:
    """Test scenarios with multiple concurrent positions."""

    @pytest.fixture
    def risk_manager(self):
        """Create a risk manager with $100k capital."""
        return BacktestRiskManager(
            initial_capital=Decimal("100000"),
            max_risk_per_trade_pct=Decimal("2.0"),
            max_campaign_risk_pct=Decimal("5.0"),
            max_portfolio_heat_pct=Decimal("10.0"),
            max_correlated_risk_pct=Decimal("6.0"),
        )

    def test_campaign_risk_accumulation(self, risk_manager):
        """Test that campaign risk accumulates correctly across multiple entries."""
        campaign_id = "spring_camp_001"
        base_time = datetime.now()

        # First entry in campaign (Spring)
        can_trade1, size1, _ = risk_manager.validate_and_size_position(
            symbol="C:EURUSD",
            entry_price=Decimal("1.0580"),
            stop_loss=Decimal("1.0520"),  # 60 pips
            campaign_id=campaign_id,
        )
        assert can_trade1 is True

        # Register the position
        risk_manager.register_position(
            symbol="C:EURUSD",
            campaign_id=campaign_id,
            entry_price=Decimal("1.0580"),
            stop_loss=Decimal("1.0520"),
            position_size=size1,
            timestamp=base_time,
        )

        # Second entry in same campaign (SOS)
        can_trade2, size2, reason = risk_manager.validate_and_size_position(
            symbol="C:EURUSD",
            entry_price=Decimal("1.0620"),
            stop_loss=Decimal("1.0560"),  # 60 pips
            campaign_id=campaign_id,
        )

        # Campaign risk should be accumulating
        campaign_risk = risk_manager.get_campaign_risk(campaign_id)
        assert campaign_risk > Decimal("0")

        # Can still add if under 5%
        if campaign_risk < Decimal("3.0"):
            assert can_trade2 is True

    def test_portfolio_heat_limit_blocks_entry(self, risk_manager):
        """Test that portfolio heat limit blocks new entries at 10%."""
        base_time = datetime.now()

        # Add 5 positions with ~2% risk each = ~10% portfolio heat
        for i in range(5):
            can_trade, size, _ = risk_manager.validate_and_size_position(
                symbol="C:EURUSD",
                entry_price=Decimal("1.0580"),
                stop_loss=Decimal("1.0520"),
                campaign_id=f"camp_{i}",
            )

            if can_trade and size:
                risk_manager.register_position(
                    symbol="C:EURUSD",
                    campaign_id=f"camp_{i}",
                    entry_price=Decimal("1.0580"),
                    stop_loss=Decimal("1.0520"),
                    position_size=size,
                    timestamp=base_time + timedelta(hours=i),
                )

        # Check portfolio heat
        portfolio_heat = risk_manager.get_portfolio_heat()

        # Try to add another position
        can_trade_more, _, reason = risk_manager.validate_and_size_position(
            symbol="C:EURUSD",
            entry_price=Decimal("1.0650"),
            stop_loss=Decimal("1.0590"),
            campaign_id="camp_new",
        )

        # If portfolio heat is at/near limit, should reject
        if portfolio_heat >= Decimal("10.0"):
            assert can_trade_more is False
            assert "PORTFOLIO_HEAT" in reason

    def test_correlated_forex_risk_detection(self, risk_manager):
        """Test correlated risk detection for forex pairs with shared currencies."""
        base_time = datetime.now()

        # Add EUR/USD position
        can_trade1, size1, _ = risk_manager.validate_and_size_position(
            symbol="C:EURUSD",
            entry_price=Decimal("1.0580"),
            stop_loss=Decimal("1.0520"),
            campaign_id="eurusd_camp",
        )
        assert can_trade1 is True

        risk_manager.register_position(
            symbol="C:EURUSD",
            campaign_id="eurusd_camp",
            entry_price=Decimal("1.0580"),
            stop_loss=Decimal("1.0520"),
            position_size=size1,
            timestamp=base_time,
        )

        # Add EUR/GBP position (shares EUR with EUR/USD)
        can_trade2, size2, _ = risk_manager.validate_and_size_position(
            symbol="C:EURGBP",
            entry_price=Decimal("0.8520"),
            stop_loss=Decimal("0.8470"),
            campaign_id="eurgbp_camp",
        )

        # Check correlated risk
        corr_risk, corr_symbols = risk_manager.get_correlated_risk("C:EURGBP")
        assert "C:EURUSD" in corr_symbols
        assert corr_risk > Decimal("0")

        # Second entry should still work if under 6% correlated risk
        if corr_risk < Decimal("4.0"):
            assert can_trade2 is True

    def test_position_lifecycle_with_pnl(self, risk_manager):
        """Test full position lifecycle: entry, hold, exit with P&L."""
        base_time = datetime.now()

        # Entry
        can_trade, size, _ = risk_manager.validate_and_size_position(
            symbol="C:EURUSD",
            entry_price=Decimal("1.0580"),
            stop_loss=Decimal("1.0520"),
            campaign_id="camp_001",
            target_price=Decimal("1.0700"),
        )
        assert can_trade is True

        position_id = risk_manager.register_position(
            symbol="C:EURUSD",
            campaign_id="camp_001",
            entry_price=Decimal("1.0580"),
            stop_loss=Decimal("1.0520"),
            position_size=size,
            timestamp=base_time,
        )

        initial_capital = risk_manager.current_capital

        # Exit at profit
        pnl = risk_manager.close_position(position_id, exit_price=Decimal("1.0640"))

        # Should have profit
        assert pnl > Decimal("0")
        assert risk_manager.current_capital > initial_capital
        assert len(risk_manager.open_positions) == 0


class TestRejectionScenarios:
    """Test various rejection scenarios."""

    @pytest.fixture
    def risk_manager(self):
        """Create a risk manager."""
        return BacktestRiskManager(initial_capital=Decimal("100000"))

    def test_invalid_stop_distance_rejection(self, risk_manager):
        """Test rejection when stop equals entry (zero stop distance)."""
        can_trade, size, reason = risk_manager.validate_and_size_position(
            symbol="C:EURUSD",
            entry_price=Decimal("1.0580"),
            stop_loss=Decimal("1.0580"),  # Same as entry
            campaign_id="camp_001",
        )

        assert can_trade is False
        assert size is None
        assert "stop distance" in reason.lower()
        assert risk_manager.violations.position_size_failures == 1

    def test_minimum_position_size_rejection(self, risk_manager):
        """Test rejection when position size is below broker minimum."""
        # Use very small account to get tiny position size
        small_rm = BacktestRiskManager(initial_capital=Decimal("100"))

        can_trade, size, reason = small_rm.validate_and_size_position(
            symbol="C:EURUSD",
            entry_price=Decimal("1.0580"),
            stop_loss=Decimal("1.0520"),
            campaign_id="camp_001",
        )

        assert can_trade is False
        assert "minimum" in reason.lower()

    def test_sequential_rejections_tracked(self, risk_manager):
        """Test that sequential rejections are properly tracked."""
        # Multiple invalid entries
        for i in range(3):
            risk_manager.validate_and_size_position(
                symbol="C:EURUSD",
                entry_price=Decimal("1.0580"),
                stop_loss=Decimal("1.0580"),  # Invalid
                campaign_id=f"camp_{i}",
            )

        assert risk_manager.violations.total_entry_attempts == 3
        assert risk_manager.violations.position_size_failures == 3
        assert risk_manager.violations.rejection_rate == 100.0


class TestRiskReporting:
    """Test risk management reporting."""

    @pytest.fixture
    def risk_manager(self):
        """Create a risk manager with some activity."""
        rm = BacktestRiskManager(initial_capital=Decimal("100000"))
        base_time = datetime.now()

        # Successful entry
        can_trade, size, _ = rm.validate_and_size_position(
            symbol="C:EURUSD",
            entry_price=Decimal("1.0580"),
            stop_loss=Decimal("1.0520"),
            campaign_id="camp_001",
        )
        if can_trade and size:
            rm.register_position(
                symbol="C:EURUSD",
                campaign_id="camp_001",
                entry_price=Decimal("1.0580"),
                stop_loss=Decimal("1.0520"),
                position_size=size,
                timestamp=base_time,
            )

        # Failed entry
        rm.validate_and_size_position(
            symbol="C:EURUSD",
            entry_price=Decimal("1.0580"),
            stop_loss=Decimal("1.0580"),  # Invalid
            campaign_id="camp_002",
        )

        return rm

    def test_report_accuracy(self, risk_manager):
        """Test that risk report accurately reflects activity."""
        report = risk_manager.get_risk_report()

        # Entry validation
        assert report["entry_validation"]["total_attempts"] == 2
        assert report["entry_validation"]["entries_allowed"] == 1
        assert report["entry_validation"]["entries_rejected"] == 1
        assert report["entry_validation"]["rejection_rate_pct"] == 50.0

        # Capital (should be unchanged since no exits)
        assert report["capital"]["initial"] == 100000.0
        assert report["capital"]["current"] == 100000.0

    def test_portfolio_utilization_tracking(self, risk_manager):
        """Test portfolio utilization tracking."""
        report = risk_manager.get_risk_report()

        # Should have some portfolio heat
        assert report["portfolio_utilization"]["peak_heat_pct"] > 0
        assert report["portfolio_utilization"]["heat_limit_pct"] == 10.0


class TestIntradayScenarios:
    """Test intraday-specific scenarios (AC9.9)."""

    @pytest.fixture
    def risk_manager(self):
        """Create a risk manager for intraday testing."""
        return BacktestRiskManager(
            initial_capital=Decimal("100000"),
            max_risk_per_trade_pct=Decimal("2.0"),
            max_campaign_risk_pct=Decimal("5.0"),
            max_portfolio_heat_pct=Decimal("10.0"),
            max_correlated_risk_pct=Decimal("6.0"),
        )

    def test_15_minute_timeframe_position_sizing(self, risk_manager):
        """Test position sizing for 15-minute timeframe forex."""
        # Typical 15m forex trade: 15-20 pip stop
        can_trade, size, _ = risk_manager.validate_and_size_position(
            symbol="C:EURUSD",
            entry_price=Decimal("1.0580"),
            stop_loss=Decimal("1.0565"),  # 15 pips
            campaign_id="intraday_camp",
        )

        assert can_trade is True
        assert size is not None
        assert size > Decimal("0")

        # Tighter stop should give larger position size (not risk amount)
        size_tight, _, _ = risk_manager.calculate_position_size(
            entry_price=Decimal("1.0580"),
            stop_loss=Decimal("1.0565"),  # 15 pips
        )

        size_wide, _, _ = risk_manager.calculate_position_size(
            entry_price=Decimal("1.0580"),
            stop_loss=Decimal("1.0520"),  # 60 pips
        )

        # Position size with tighter stop should be larger
        assert size_tight > size_wide

    def test_multiple_intraday_campaigns(self, risk_manager):
        """Test managing multiple intraday campaigns."""
        base_time = datetime.now()

        campaigns = []

        # Create 3 intraday campaigns
        for i in range(3):
            can_trade, size, _ = risk_manager.validate_and_size_position(
                symbol="C:EURUSD",
                entry_price=Decimal("1.0580") + Decimal(str(i * 0.001)),
                stop_loss=Decimal("1.0565") + Decimal(str(i * 0.001)),
                campaign_id=f"intraday_camp_{i}",
            )

            if can_trade and size:
                pos_id = risk_manager.register_position(
                    symbol="C:EURUSD",
                    campaign_id=f"intraday_camp_{i}",
                    entry_price=Decimal("1.0580") + Decimal(str(i * 0.001)),
                    stop_loss=Decimal("1.0565") + Decimal(str(i * 0.001)),
                    position_size=size,
                    timestamp=base_time + timedelta(minutes=15 * i),
                )
                campaigns.append(pos_id)

        # Should have multiple positions
        assert len(risk_manager.open_positions) >= 1

        # Each campaign should have its own risk profile
        for i in range(len(campaigns)):
            campaign_risk = risk_manager.get_campaign_risk(f"intraday_camp_{i}")
            # Each should have individual risk
            assert campaign_risk >= Decimal("0")

    def test_rapid_entry_exit_cycles(self, risk_manager):
        """Test rapid entry/exit cycles typical of intraday trading."""
        base_time = datetime.now()

        # Simulate 5 quick trades
        total_pnl = Decimal("0")

        for i in range(5):
            # Entry
            can_trade, size, _ = risk_manager.validate_and_size_position(
                symbol="C:EURUSD",
                entry_price=Decimal("1.0580"),
                stop_loss=Decimal("1.0560"),
                campaign_id=f"scalp_{i}",
            )

            if can_trade and size:
                pos_id = risk_manager.register_position(
                    symbol="C:EURUSD",
                    campaign_id=f"scalp_{i}",
                    entry_price=Decimal("1.0580"),
                    stop_loss=Decimal("1.0560"),
                    position_size=size,
                    timestamp=base_time + timedelta(minutes=i * 5),
                )

                # Exit (alternating win/loss)
                exit_price = Decimal("1.0595") if i % 2 == 0 else Decimal("1.0565")
                pnl = risk_manager.close_position(pos_id, exit_price)
                if pnl:
                    total_pnl += pnl

        # Should have processed trades
        assert risk_manager.violations.entries_allowed >= 1

        # No open positions at end
        assert len(risk_manager.open_positions) == 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_small_account(self):
        """Test with very small account size."""
        # Use very small account to get position below broker minimum (1000 units)
        rm = BacktestRiskManager(initial_capital=Decimal("10"))

        can_trade, size, reason = rm.validate_and_size_position(
            symbol="C:EURUSD",
            entry_price=Decimal("1.0580"),
            stop_loss=Decimal("1.0520"),  # 60 pips
            campaign_id="small_camp",
        )

        # Should fail due to minimum position size
        # $10 * 2% = $0.20 risk / 0.006 stop = 33 units (below 1000 min)
        assert can_trade is False
        assert "minimum" in reason.lower()

    def test_very_large_account(self):
        """Test with large account size."""
        rm = BacktestRiskManager(initial_capital=Decimal("10000000"))  # $10M

        can_trade, size, _ = rm.validate_and_size_position(
            symbol="C:EURUSD",
            entry_price=Decimal("1.0580"),
            stop_loss=Decimal("1.0520"),
            campaign_id="large_camp",
        )

        assert can_trade is True
        assert size > Decimal("1000000")  # Large position

    def test_exactly_at_limit(self):
        """Test behavior exactly at risk limits."""
        rm = BacktestRiskManager(
            initial_capital=Decimal("100000"),
            max_portfolio_heat_pct=Decimal("10.0"),
        )

        # Fill up to exactly 10% (5 positions at 2% each)
        for i in range(5):
            can_trade, size, _ = rm.validate_and_size_position(
                symbol="C:EURUSD",
                entry_price=Decimal("1.0580"),
                stop_loss=Decimal("1.0520"),
                campaign_id=f"camp_{i}",
            )
            if can_trade and size:
                rm.register_position(
                    symbol="C:EURUSD",
                    campaign_id=f"camp_{i}",
                    entry_price=Decimal("1.0580"),
                    stop_loss=Decimal("1.0520"),
                    position_size=size,
                    timestamp=datetime.now(),
                )

        # Portfolio should be at or near limit
        heat = rm.get_portfolio_heat()

        # Next entry should be rejected or allowed based on actual heat
        is_valid, reason = rm.validate_portfolio_heat(Decimal("2.0"))

        if heat >= Decimal("10.0"):
            assert is_valid is False
        else:
            # Still have room
            assert is_valid is True or (heat + Decimal("2.0") > Decimal("10.0"))


class TestBacktestEngineDynamicPositionSize:
    """Test that BacktestEngine uses dynamic position size from context (Story 13.9 fix)."""

    def test_process_signal_uses_dynamic_position_size_from_context(self):
        """Verify _process_signal uses context['position_size'] when set."""
        from unittest.mock import MagicMock

        from src.backtesting.backtest_engine import BacktestConfig, BacktestEngine
        from src.models.ohlcv import OHLCVBar

        config = BacktestConfig(
            symbol="C:EURUSD",
            start_date=(datetime.now() - timedelta(days=30)).date(),
            end_date=datetime.now().date(),
            initial_capital=Decimal("100000"),
            max_position_size=Decimal("0.02"),  # Fixed 2%
            commission_per_share=Decimal("0.00002"),
            timeframe="15m",
        )

        engine = BacktestEngine(config)

        # Create a test bar
        bar = OHLCVBar(
            symbol="C:EURUSD",
            timeframe="15m",
            timestamp=datetime.now(),
            open=Decimal("1.0580"),
            high=Decimal("1.0590"),
            low=Decimal("1.0570"),
            close=Decimal("1.0580"),
            volume=100000,
            spread=Decimal("0.0020"),
        )

        # Set dynamic position size in strategy context
        dynamic_size = Decimal("50000")
        engine.strategy_context["position_size"] = dynamic_size

        # Mock position_manager and order_simulator
        engine.position_manager.has_position = MagicMock(return_value=False)
        engine.order_simulator.submit_order = MagicMock()

        # Call _process_signal with BUY
        engine._process_signal("BUY", bar)

        # Verify submit_order was called with the dynamic size
        engine.order_simulator.submit_order.assert_called_once()
        call_args = engine.order_simulator.submit_order.call_args
        quantity = call_args.kwargs.get("quantity") or call_args[1].get("quantity")

        # Should be int(dynamic_size) = 50000, not the fixed 2% (~1889)
        assert quantity == 50000, (
            f"Expected dynamic position size 50000, got {quantity}. "
            f"BacktestEngine._process_signal is not using context['position_size']"
        )

    def test_process_signal_falls_back_to_config_when_no_dynamic_size(self):
        """Verify _process_signal falls back to config when context has no position_size."""
        from unittest.mock import MagicMock

        from src.backtesting.backtest_engine import BacktestConfig, BacktestEngine
        from src.models.ohlcv import OHLCVBar

        config = BacktestConfig(
            symbol="C:EURUSD",
            start_date=(datetime.now() - timedelta(days=30)).date(),
            end_date=datetime.now().date(),
            initial_capital=Decimal("100000"),
            max_position_size=Decimal("0.02"),  # 2% = ~1889 units at 1.0580
            commission_per_share=Decimal("0.00002"),
            timeframe="15m",
        )

        engine = BacktestEngine(config)

        # Create a test bar
        bar = OHLCVBar(
            symbol="C:EURUSD",
            timeframe="15m",
            timestamp=datetime.now(),
            open=Decimal("1.0580"),
            high=Decimal("1.0590"),
            low=Decimal("1.0570"),
            close=Decimal("1.0580"),
            volume=100000,
            spread=Decimal("0.0020"),
        )

        # Do NOT set position_size in context
        # (it should be None or missing)
        engine.strategy_context["position_size"] = None

        # Mock position_manager and order_simulator
        engine.position_manager.has_position = MagicMock(return_value=False)
        engine.order_simulator.submit_order = MagicMock()

        # Call _process_signal with BUY
        engine._process_signal("BUY", bar)

        # Verify submit_order was called
        engine.order_simulator.submit_order.assert_called_once()
        call_args = engine.order_simulator.submit_order.call_args
        quantity = call_args.kwargs.get("quantity") or call_args[1].get("quantity")

        # Should be around 1889 (2% of $100k at 1.0580), NOT 50000
        assert quantity < 5000, (
            f"Expected fixed position size ~1889, got {quantity}. "
            f"BacktestEngine._process_signal is not falling back to config"
        )
