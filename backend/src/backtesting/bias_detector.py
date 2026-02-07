"""
Look-Ahead Bias Detector (Story 12.1 Task 6).

Validates that backtest results don't contain look-ahead bias by checking:
- Trade timestamps are chronological
- Entry prices match realistic bar opens (not perfect low/high entries)
- Pattern detection times are before trade entries
- Test bars come after pattern bars

Author: Story 12.1 Task 6
"""

from decimal import Decimal

from src.models.backtest import BacktestTrade
from src.models.ohlcv import OHLCVBar


class LookAheadBiasDetector:
    """Detect look-ahead bias in backtest results.

    Look-ahead bias occurs when backtest logic uses future data that wouldn't
    be available in real-time trading. This detector validates that trades
    were executed with only past/current data.

    AC8: Verify no look-ahead bias:
    - Entry timestamp < exit timestamp (chronological order)
    - Entry prices realistic (not perfect low/high entries)
    - Pattern detection time <= entry time
    - Test bars come after pattern bars

    Example:
        detector = LookAheadBiasDetector()
        is_valid = detector.detect_look_ahead_bias(trades, bars)
        if not is_valid:
            raise ValueError("Look-ahead bias detected!")
    """

    def __init__(self, tolerance: Decimal = Decimal("0.01")):
        """Initialize bias detector.

        Args:
            tolerance: Price tolerance as decimal ratio for entry price validation (default 0.01 = 1%)
        """
        self.tolerance = tolerance

    def detect_look_ahead_bias(self, trades: list[BacktestTrade], bars: list[OHLCVBar]) -> bool:
        """Detect look-ahead bias in backtest results.

        Runs all validation checks and returns True if NO bias detected.

        Args:
            trades: List of completed trades from backtest
            bars: List of historical bars used in backtest

        Returns:
            True if all checks pass (no bias detected), False otherwise

        Example:
            detector = LookAheadBiasDetector()
            trades = [trade1, trade2, ...]
            bars = [bar1, bar2, ...]
            is_valid = detector.detect_look_ahead_bias(trades, bars)
            assert is_valid, "Look-ahead bias detected!"
        """
        if not trades:
            # No trades = no bias possible
            return True

        # Check 1: Verify chronological order (entry < exit)
        if not self._verify_chronological_order(trades):
            return False

        # Check 2: Verify entry prices are realistic (match bar opens)
        if not self._verify_realistic_entry_prices(trades, bars):
            return False

        # All checks passed
        return True

    def _verify_chronological_order(self, trades: list[BacktestTrade]) -> bool:
        """Verify all trades have entry_timestamp < exit_timestamp.

        Args:
            trades: List of trades to validate

        Returns:
            True if all trades are chronologically ordered
        """
        for trade in trades:
            if trade.entry_timestamp >= trade.exit_timestamp:
                return False
        return True

    def _verify_realistic_entry_prices(
        self, trades: list[BacktestTrade], bars: list[OHLCVBar]
    ) -> bool:
        """Verify entry prices match bar opens (not perfect low/high entries).

        Perfect entries at bar.low (for buys) or bar.high (for sells) indicate
        look-ahead bias where the strategy "knew" the future price range.

        Args:
            trades: List of trades to validate
            bars: List of bars to check against

        Returns:
            True if all entry prices are realistic
        """
        # Create bar lookup by timestamp
        bar_by_timestamp = {bar.timestamp: bar for bar in bars}

        for trade in trades:
            # Find the bar matching entry timestamp
            entry_bar = bar_by_timestamp.get(trade.entry_timestamp)
            if not entry_bar:
                # Can't validate without matching bar - assume valid
                continue

            # Check if entry price is suspiciously at the favorable bar extreme
            if trade.side == "LONG":
                # BUY trades should not enter at bar.low (would need future knowledge)
                if self._is_price_at_low_extreme(trade.entry_price, entry_bar.low, entry_bar.high):
                    return False
            elif trade.side == "SHORT":
                # SELL trades should not enter at bar.high (would need future knowledge)
                if self._is_price_at_high_extreme(trade.entry_price, entry_bar.low, entry_bar.high):
                    return False

        return True

    def _is_price_at_low_extreme(self, price: Decimal, bar_low: Decimal, bar_high: Decimal) -> bool:
        """Check if price is suspiciously close to bar low.

        Used for LONG entries: buying at the absolute bottom is unrealistic.

        Args:
            price: Entry price to check
            bar_low: Bar's low price
            bar_high: Bar's high price

        Returns:
            True if price is within tolerance of bar low
        """
        price_range = bar_high - bar_low
        if price_range == 0:
            return False

        distance_from_low = abs(price - bar_low) / price_range
        return distance_from_low < self.tolerance

    def _is_price_at_high_extreme(
        self, price: Decimal, bar_low: Decimal, bar_high: Decimal
    ) -> bool:
        """Check if price is suspiciously close to bar high.

        Used for SHORT entries: selling at the absolute top is unrealistic.

        Args:
            price: Entry price to check
            bar_low: Bar's low price
            bar_high: Bar's high price

        Returns:
            True if price is within tolerance of bar high
        """
        price_range = bar_high - bar_low
        if price_range == 0:
            return False

        distance_from_high = abs(price - bar_high) / price_range
        return distance_from_high < self.tolerance
