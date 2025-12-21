"""
Liquidity Calculator for Backtesting (Story 12.5 Task 3).

Calculates average dollar volume to determine liquidity classification
for slippage calculations. Uses rolling 20-bar average for smoothing.

Author: Story 12.5 Task 3
"""

from decimal import Decimal

import pandas as pd
import structlog

from src.models.backtest import SlippageConfig
from src.models.ohlcv import OHLCVBar

logger = structlog.get_logger(__name__)


class LiquidityCalculator:
    """
    Calculate liquidity metrics for slippage determination.

    Implements rolling average dollar volume calculation to classify
    stocks as high-liquidity or low-liquidity for slippage modeling.

    AC3: avg_volume > $1M = high liquidity (0.02% slippage)
         avg_volume < $1M = low liquidity (0.05% slippage)

    Methods:
        calculate_avg_dollar_volume: Calculate 20-bar rolling average
        is_high_liquidity: Determine if stock is high liquidity
        get_base_slippage_pct: Get base slippage percentage from liquidity

    Example:
        calculator = LiquidityCalculator()
        bars = [...]  # List of OHLCVBar objects
        avg_volume = calculator.calculate_avg_dollar_volume(bars, lookback=20)
        is_liquid = calculator.is_high_liquidity(
            avg_volume,
            Decimal("1000000")
        )
        # is_liquid = True if avg_volume >= $1M, False otherwise

    Author: Story 12.5 Task 3
    """

    def calculate_avg_dollar_volume(self, bars: list[OHLCVBar], lookback: int = 20) -> Decimal:
        """
        Calculate rolling average dollar volume for liquidity assessment.

        Uses pandas for vectorized calculation:
        dollar_volume = close * volume
        avg_dollar_volume = rolling(lookback).mean()

        Subtask 3.2: Calculate rolling 20-bar average using pandas vectorization
        Subtask 3.7: Use Decimal type throughout (NOT float)

        Args:
            bars: List of OHLCV bars (historical data)
            lookback: Rolling window size (default 20 bars)

        Returns:
            Most recent average dollar volume as Decimal

        Edge cases:
            - If fewer than lookback bars available, use available bars
            - If no bars provided, return Decimal("0")
            - If all bars have zero volume, return Decimal("0")

        Example:
            bars = [
                OHLCVBar(close=100, volume=10000, ...),
                OHLCVBar(close=101, volume=12000, ...),
                ...  # 18 more bars
            ]
            avg = calculator.calculate_avg_dollar_volume(bars, lookback=20)
            # avg ≈ Decimal("1050000") (average of close * volume)

        Author: Story 12.5 Subtask 3.2
        """
        if not bars:
            logger.warning("No bars provided for liquidity calculation")
            return Decimal("0")

        # Convert to pandas DataFrame for vectorized operations
        df = pd.DataFrame([{"close": float(bar.close), "volume": bar.volume} for bar in bars])

        # Calculate dollar volume (close * volume)
        df["dollar_volume"] = df["close"] * df["volume"]

        # Calculate rolling average
        # Use min_periods=1 to handle cases with fewer than lookback bars
        df["avg_dollar_volume"] = df["dollar_volume"].rolling(window=lookback, min_periods=1).mean()

        # Get most recent average dollar volume
        most_recent_avg = df["avg_dollar_volume"].iloc[-1]

        # Convert to Decimal for financial precision
        result = Decimal(str(most_recent_avg))

        logger.debug(
            "Calculated average dollar volume",
            lookback=lookback,
            bars_count=len(bars),
            avg_dollar_volume=float(result),
        )

        return result

    def is_high_liquidity(self, avg_dollar_volume: Decimal, threshold: Decimal) -> bool:
        """
        Determine if stock is high liquidity based on average dollar volume.

        Subtask 3.3: Return True if avg_dollar_volume >= threshold

        Args:
            avg_dollar_volume: Average dollar volume (from calculate_avg_dollar_volume)
            threshold: Liquidity threshold (default $1M from SlippageConfig)

        Returns:
            True if high liquidity (avg >= threshold), False otherwise

        Example:
            is_liquid = calculator.is_high_liquidity(
                Decimal("5000000"),  # $5M avg volume
                Decimal("1000000")   # $1M threshold
            )
            # is_liquid = True (AAPL, MSFT, etc.)

            is_liquid = calculator.is_high_liquidity(
                Decimal("500000"),   # $500K avg volume
                Decimal("1000000")   # $1M threshold
            )
            # is_liquid = False (small-cap stock)

        Author: Story 12.5 Subtask 3.3
        """
        is_liquid = avg_dollar_volume >= threshold

        logger.debug(
            "Liquidity classification",
            avg_dollar_volume=float(avg_dollar_volume),
            threshold=float(threshold),
            is_high_liquidity=is_liquid,
        )

        return is_liquid

    def get_base_slippage_pct(self, avg_dollar_volume: Decimal, config: SlippageConfig) -> Decimal:
        """
        Get base slippage percentage based on liquidity.

        Subtask 3.4: If high_liquidity: return config.high_liquidity_slippage_pct (0.02%)
                     If low_liquidity: return config.low_liquidity_slippage_pct (0.05%)

        Args:
            avg_dollar_volume: Average dollar volume
            config: Slippage configuration with liquidity thresholds

        Returns:
            Base slippage percentage (Decimal)

        Example:
            High liquidity stock ($5M avg volume):
                slippage = get_base_slippage_pct(Decimal("5000000"), config)
                # slippage = Decimal("0.0002") = 0.02%

            Low liquidity stock ($500K avg volume):
                slippage = get_base_slippage_pct(Decimal("500000"), config)
                # slippage = Decimal("0.0005") = 0.05%

        Author: Story 12.5 Subtask 3.4
        """
        if self.is_high_liquidity(avg_dollar_volume, config.high_liquidity_threshold):
            base_slippage = config.high_liquidity_slippage_pct
            liquidity_level = "high"
        else:
            base_slippage = config.low_liquidity_slippage_pct
            liquidity_level = "low"

        logger.debug(
            "Base slippage determined",
            avg_dollar_volume=float(avg_dollar_volume),
            liquidity_level=liquidity_level,
            base_slippage_pct=float(base_slippage),
        )

        return base_slippage
