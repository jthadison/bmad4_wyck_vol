"""
Unit Tests for Enhanced Slippage Calculator (Story 12.5 Task 15.2).

Tests slippage calculation with liquidity and market impact modeling.

Author: Story 12.5 Task 15
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.slippage_calculator_enhanced import EnhancedSlippageCalculator
from src.models.backtest import BacktestOrder, SlippageConfig
from src.models.ohlcv import OHLCVBar


class TestEnhancedSlippageCalculator:
    """Unit tests for EnhancedSlippageCalculator."""

    @pytest.fixture
    def calculator(self):
        """Create EnhancedSlippageCalculator instance."""
        return EnhancedSlippageCalculator()

    @pytest.fixture
    def slippage_config(self):
        """Create default SlippageConfig."""
        return SlippageConfig(
            slippage_model="LIQUIDITY_BASED",
            high_liquidity_threshold=Decimal("1000000"),  # $1M
            high_liquidity_slippage_pct=Decimal("0.0002"),  # 0.02%
            low_liquidity_slippage_pct=Decimal("0.0005"),  # 0.05%
            market_impact_enabled=True,
            market_impact_threshold_pct=Decimal("0.10"),  # 10%
            market_impact_per_increment_pct=Decimal("0.0001"),  # 0.01%
        )

    @pytest.fixture
    def sample_order(self):
        """Create sample BacktestOrder."""
        return BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=1000,
            created_bar_timestamp=datetime.now(UTC),
            fill_price=Decimal("150.00"),
            status="FILLED",
        )

    @pytest.fixture
    def high_liquidity_bars(self):
        """Create high liquidity historical bars ($5M avg volume)."""
        bars = []
        for i in range(20):
            bar = OHLCVBar(
                symbol="AAPL",
                timeframe="5m",
                timestamp=datetime.now(UTC),
                open=Decimal("150.00"),
                high=Decimal("152.00"),
                low=Decimal("149.00"),
                close=Decimal("151.00"),
                volume=33000,  # 33K volume * $150 = $5M dollar volume
                spread=Decimal("3.00"),  # high - low
            )
            bars.append(bar)
        return bars

    @pytest.fixture
    def low_liquidity_bars(self):
        """Create low liquidity historical bars ($500K avg volume)."""
        bars = []
        for i in range(20):
            bar = OHLCVBar(
                symbol="AAPL",
                timeframe="5m",
                timestamp=datetime.now(UTC),
                open=Decimal("50.00"),
                high=Decimal("51.00"),
                low=Decimal("49.00"),
                close=Decimal("50.00"),
                volume=10000,  # 10K volume * $50 = $500K dollar volume
                spread=Decimal("2.00"),  # high - low
            )
            bars.append(bar)
        return bars

    # Subtask 15.2.1: Test high liquidity slippage (0.02%)
    def test_high_liquidity_slippage(
        self, calculator, sample_order, high_liquidity_bars, slippage_config
    ):
        """Test slippage calculation for high liquidity stock."""
        fill_bar = high_liquidity_bars[-1]

        slippage_pct, breakdown = calculator.calculate_slippage(
            sample_order, fill_bar, high_liquidity_bars, slippage_config
        )

        # High liquidity: 0.02% base slippage
        # No market impact (1000 shares / 33000 volume = 3%, below 10% threshold)
        assert slippage_pct == Decimal("0.0002")
        assert breakdown.base_slippage_pct == Decimal("0.0002")
        assert breakdown.market_impact_slippage_pct == Decimal("0")
        assert breakdown.total_slippage_pct == Decimal("0.0002")

    # Subtask 15.2.2: Test low liquidity slippage (0.05%)
    def test_low_liquidity_slippage(
        self, calculator, sample_order, low_liquidity_bars, slippage_config
    ):
        """Test slippage calculation for low liquidity stock."""
        fill_bar = low_liquidity_bars[-1]

        slippage_pct, breakdown = calculator.calculate_slippage(
            sample_order, fill_bar, low_liquidity_bars, slippage_config
        )

        # Low liquidity: 0.05% base slippage
        assert breakdown.base_slippage_pct == Decimal("0.0005")

    # Subtask 15.2.3: Test market impact slippage
    def test_market_impact_slippage(self, calculator, slippage_config, high_liquidity_bars):
        """Test market impact slippage for large order."""
        # Large order: 10,000 shares (30% of bar volume)
        large_order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=10000,
            created_bar_timestamp=datetime.now(UTC),
            fill_price=Decimal("150.00"),
            status="FILLED",
        )

        fill_bar = high_liquidity_bars[-1]

        slippage_pct, breakdown = calculator.calculate_slippage(
            large_order, fill_bar, high_liquidity_bars, slippage_config
        )

        # Volume participation: 10,000 / 33,000 = 30%
        # Excess over 10% threshold: 20%
        # Increments: 2 (20% / 10%)
        # Market impact: 2 * 0.01% = 0.02%
        # Total: 0.02% (base) + 0.02% (market impact) = 0.04%
        assert breakdown.volume_participation_pct > Decimal("0.10")
        assert breakdown.market_impact_slippage_pct > Decimal("0")
        assert breakdown.total_slippage_pct > breakdown.base_slippage_pct

    # Subtask 15.2.4: Test slippage application to price (BUY)
    def test_apply_slippage_to_price_buy(self, calculator):
        """Test applying slippage to BUY order."""
        base_price = Decimal("100.00")
        slippage_pct = Decimal("0.0002")  # 0.02%

        fill_price = calculator.apply_slippage_to_price(base_price, slippage_pct, "BUY")

        # BUY: price increases (worse for buyer)
        # $100 * (1 + 0.0002) = $100.02
        assert fill_price == Decimal("100.02")

    # Subtask 15.2.5: Test slippage application to price (SELL)
    def test_apply_slippage_to_price_sell(self, calculator):
        """Test applying slippage to SELL order."""
        base_price = Decimal("100.00")
        slippage_pct = Decimal("0.0002")  # 0.02%

        fill_price = calculator.apply_slippage_to_price(base_price, slippage_pct, "SELL")

        # SELL: price decreases (worse for seller)
        # $100 * (1 - 0.0002) = $99.98
        assert fill_price == Decimal("99.98")

    # Subtask 15.2.6: Test slippage breakdown structure
    def test_slippage_breakdown_structure(
        self, calculator, sample_order, high_liquidity_bars, slippage_config
    ):
        """Test slippage breakdown contains all required fields."""
        fill_bar = high_liquidity_bars[-1]

        slippage_pct, breakdown = calculator.calculate_slippage(
            sample_order, fill_bar, high_liquidity_bars, slippage_config
        )

        assert breakdown.order_id == sample_order.order_id
        assert breakdown.bar_volume == fill_bar.volume
        assert breakdown.bar_avg_dollar_volume > Decimal("0")
        assert breakdown.order_quantity == sample_order.quantity
        assert breakdown.order_value > Decimal("0")
        assert breakdown.volume_participation_pct >= Decimal("0")
        assert breakdown.base_slippage_pct > Decimal("0")
        assert breakdown.market_impact_slippage_pct >= Decimal("0")
        assert (
            breakdown.total_slippage_pct
            == breakdown.base_slippage_pct + breakdown.market_impact_slippage_pct
        )
        assert breakdown.slippage_dollar_amount > Decimal("0")
        assert breakdown.slippage_model_used == "LIQUIDITY_BASED"

    # Subtask 15.2.7: Test zero volume edge case
    def test_zero_volume_edge_case(self, calculator, sample_order, slippage_config):
        """Test edge case with zero bar volume."""
        zero_volume_bar = OHLCVBar(
            symbol="AAPL",
            timeframe="5m",
            timestamp=datetime.now(UTC),
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.00"),
            volume=0,  # Zero volume
            spread=Decimal("2.00"),
        )

        # Create historical bars with some volume
        historical_bars = []
        for i in range(20):
            bar = OHLCVBar(
                symbol="AAPL",
                timeframe="5m",
                timestamp=datetime.now(UTC),
                open=Decimal("100.00"),
                high=Decimal("101.00"),
                low=Decimal("99.00"),
                close=Decimal("100.00"),
                volume=10000,
                spread=Decimal("2.00"),
            )
            historical_bars.append(bar)

        slippage_pct, breakdown = calculator.calculate_slippage(
            sample_order, zero_volume_bar, historical_bars, slippage_config
        )

        # Should handle gracefully (volume participation = 0%)
        assert breakdown.volume_participation_pct == Decimal("0")
        assert breakdown.market_impact_slippage_pct == Decimal("0")

    # Subtask 15.2.8: Test market impact disabled
    def test_market_impact_disabled(self, calculator, slippage_config, high_liquidity_bars):
        """Test slippage calculation with market impact disabled."""
        # Large order but market impact disabled
        large_order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=10000,
            created_bar_timestamp=datetime.now(UTC),
            fill_price=Decimal("150.00"),
            status="FILLED",
        )

        # Disable market impact
        config_no_impact = SlippageConfig(
            slippage_model="LIQUIDITY_BASED",
            high_liquidity_threshold=Decimal("1000000"),
            high_liquidity_slippage_pct=Decimal("0.0002"),
            low_liquidity_slippage_pct=Decimal("0.0005"),
            market_impact_enabled=False,  # Disabled
        )

        fill_bar = high_liquidity_bars[-1]

        slippage_pct, breakdown = calculator.calculate_slippage(
            large_order, fill_bar, high_liquidity_bars, config_no_impact
        )

        # Only base slippage, no market impact
        assert breakdown.market_impact_slippage_pct == Decimal("0")
        assert breakdown.total_slippage_pct == breakdown.base_slippage_pct

    # Subtask 15.2.9: Test realistic scenario (AAPL-like stock)
    def test_realistic_aapl_scenario(self, calculator, slippage_config):
        """Test realistic scenario with AAPL-like liquidity."""
        # AAPL: ~$50M daily dollar volume, $180 price
        # Avg bar (5-min): $50M / 78 bars = ~$640K per bar
        aapl_bars = []
        for i in range(20):
            bar = OHLCVBar(
                symbol="AAPL",
                timeframe="5m",
                timestamp=datetime.now(UTC),
                open=Decimal("180.00"),
                high=Decimal("181.00"),
                low=Decimal("179.00"),
                close=Decimal("180.00"),
                volume=3500,  # 3500 * $180 = $630K
                spread=Decimal("2.00"),
            )
            aapl_bars.append(bar)

        # Small retail order: 100 shares
        order = BacktestOrder(
            order_id=uuid4(),
            symbol="AAPL",
            order_type="MARKET",
            side="BUY",
            quantity=100,
            created_bar_timestamp=datetime.now(UTC),
            fill_price=Decimal("180.00"),
            status="FILLED",
        )

        fill_bar = aapl_bars[-1]

        slippage_pct, breakdown = calculator.calculate_slippage(
            order, fill_bar, aapl_bars, slippage_config
        )

        # Should be low liquidity (< $1M), 0.05% base slippage
        # Volume participation: 100 / 3500 = 2.86% (below 10% threshold)
        # No market impact
        assert breakdown.base_slippage_pct == Decimal("0.0005")  # 0.05%
        assert breakdown.market_impact_slippage_pct == Decimal("0")
        assert breakdown.total_slippage_pct == Decimal("0.0005")

        # Dollar slippage: $18,000 order * 0.0005 = $9
        expected_slippage = Decimal("180.00") * Decimal("100") * Decimal("0.0005")
        assert breakdown.slippage_dollar_amount == expected_slippage
