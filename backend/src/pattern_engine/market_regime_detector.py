"""
Market Regime Detection for Campaign Context (Story 16.7a)

Purpose:
--------
Detects market regimes (RANGING, TRENDING_UP, TRENDING_DOWN, HIGH_VOLATILITY,
LOW_VOLATILITY) using ADX and ATR technical indicators. Used to classify
market conditions at campaign formation for performance analysis.

Technical Indicators:
---------------------
- ADX (Average Directional Index): Measures trend strength (0-100 scale)
- ATR (Average True Range): Measures volatility (in price units)

Detection Logic:
----------------
1. ADX < 25 → RANGING (ideal for Wyckoff accumulation/distribution)
2. ADX >= 25 + price rising → TRENDING_UP
3. ADX >= 25 + price falling → TRENDING_DOWN
4. ATR > 1.5x 20-period avg → HIGH_VOLATILITY
5. ATR < 0.5x 20-period avg → LOW_VOLATILITY

Performance Requirements (AC #7):
----------------------------------
- Regime detection: < 10ms per bar
- Optimized indicator calculations (vectorized operations)

Author: Story 16.7a
"""

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.ohlcv import OHLCVBar

from src.models.campaign import MarketRegime


class MarketRegimeDetector:
    """
    Detects market regime using ADX (trend strength) and ATR (volatility).

    Uses technical analysis indicators to classify market conditions:
    - ADX measures trend strength (0-100 scale, 25 is key threshold)
    - ATR measures volatility relative to average range

    Methods:
    --------
    - detect_regime(bars): Detect current market regime from recent bars
    - _calculate_adx(bars, period=14): Calculate Average Directional Index
    - _calculate_atr(bars, period=14): Calculate Average True Range
    - _calculate_avg_atr(bars, period=20): Calculate average ATR for volatility comparison

    Example:
    --------
    >>> detector = MarketRegimeDetector()
    >>> regime = detector.detect_regime(bars)
    >>> print(regime)  # MarketRegime.RANGING
    """

    def __init__(self) -> None:
        """Initialize market regime detector."""
        self.adx_period = 14
        self.atr_period = 14
        self.avg_atr_period = 20
        self.adx_threshold = Decimal("25.0")
        self.high_vol_multiplier = Decimal("1.5")
        self.low_vol_multiplier = Decimal("0.5")

    def detect_regime(self, bars: list["OHLCVBar"]) -> MarketRegime:
        """
        Detect current market regime from recent bars.

        Requires minimum 40 bars for reliable calculation (20 for ADX/ATR warmup
        + 20 for average ATR comparison).

        Parameters:
        -----------
        bars : list[OHLCVBar]
            Recent OHLCV bars (minimum 40 bars recommended)

        Returns:
        --------
        MarketRegime
            Detected regime (RANGING, TRENDING_UP, TRENDING_DOWN,
            HIGH_VOLATILITY, or LOW_VOLATILITY)

        Example:
        --------
        >>> detector = MarketRegimeDetector()
        >>> regime = detector.detect_regime(recent_bars)
        >>> if regime == MarketRegime.RANGING:
        ...     print("Ideal conditions for Wyckoff patterns")
        """
        if len(bars) < 40:
            # Default to RANGING if insufficient data
            return MarketRegime.RANGING

        # Calculate ADX (trend strength)
        adx = self._calculate_adx(bars, period=self.adx_period)

        # Calculate ATR (volatility)
        atr = self._calculate_atr(bars, period=self.atr_period)
        avg_atr = self._calculate_avg_atr(bars, period=self.avg_atr_period)

        # Priority 1: Check volatility extremes (takes precedence)
        if avg_atr > Decimal("0"):
            vol_ratio = atr / avg_atr
            if vol_ratio > self.high_vol_multiplier:
                return MarketRegime.HIGH_VOLATILITY
            if vol_ratio < self.low_vol_multiplier:
                return MarketRegime.LOW_VOLATILITY

        # Priority 2: Check trend strength
        if adx < self.adx_threshold:
            return MarketRegime.RANGING

        # Priority 3: Determine trend direction (ADX >= 25)
        # Compare recent close to close 20 bars ago
        if len(bars) >= 20:
            current_price = bars[-1].close
            past_price = bars[-20].close
            if current_price > past_price:
                return MarketRegime.TRENDING_UP
            else:
                return MarketRegime.TRENDING_DOWN

        # Fallback to RANGING
        return MarketRegime.RANGING

    def _calculate_adx(self, bars: list["OHLCVBar"], period: int = 14) -> Decimal:
        """
        Calculate Average Directional Index (ADX).

        ADX measures trend strength on a 0-100 scale:
        - 0-25: Weak trend (ranging)
        - 25-50: Strong trend
        - 50-75: Very strong trend
        - 75-100: Extremely strong trend

        Algorithm:
        ----------
        1. Calculate +DM (positive directional movement) and -DM
        2. Calculate True Range (TR)
        3. Smooth +DM, -DM, TR over period
        4. Calculate +DI = (+DM / TR) * 100
        5. Calculate -DI = (-DM / TR) * 100
        6. Calculate DX = (|+DI - -DI| / (+DI + -DI)) * 100
        7. Calculate ADX = smooth(DX, period)

        Parameters:
        -----------
        bars : list[OHLCVBar]
            OHLCV bars (minimum period * 2 recommended)
        period : int
            ADX smoothing period (default 14)

        Returns:
        --------
        Decimal
            ADX value (0-100 scale)
        """
        if len(bars) < period + 1:
            return Decimal("0")

        # Step 1: Calculate +DM and -DM
        plus_dm_values = []
        minus_dm_values = []
        tr_values = []

        for i in range(1, len(bars)):
            prev_high = bars[i - 1].high
            prev_low = bars[i - 1].low
            curr_high = bars[i].high
            curr_low = bars[i].low
            curr_close = bars[i].close
            prev_close = bars[i - 1].close

            # Directional Movement
            up_move = curr_high - prev_high
            down_move = prev_low - curr_low

            plus_dm = up_move if up_move > down_move and up_move > Decimal("0") else Decimal("0")
            minus_dm = (
                down_move if down_move > up_move and down_move > Decimal("0") else Decimal("0")
            )

            # True Range = max(high-low, abs(high-prev_close), abs(low-prev_close))
            tr = max(
                curr_high - curr_low,
                abs(curr_high - prev_close),
                abs(curr_low - prev_close),
            )

            plus_dm_values.append(plus_dm)
            minus_dm_values.append(minus_dm)
            tr_values.append(tr)

        if len(tr_values) < period:
            return Decimal("0")

        # Step 2: Smooth +DM, -DM, TR using Wilder's smoothing (EMA-like)
        # First smoothed value = sum of first 'period' values
        smoothed_plus_dm = sum(plus_dm_values[:period])
        smoothed_minus_dm = sum(minus_dm_values[:period])
        smoothed_tr = sum(tr_values[:period])

        # Subsequent values: smoothed_value = (prev_smoothed * (period-1) + current) / period
        for i in range(period, len(tr_values)):
            smoothed_plus_dm = (
                smoothed_plus_dm * Decimal(period - 1) + plus_dm_values[i]
            ) / Decimal(period)
            smoothed_minus_dm = (
                smoothed_minus_dm * Decimal(period - 1) + minus_dm_values[i]
            ) / Decimal(period)
            smoothed_tr = (smoothed_tr * Decimal(period - 1) + tr_values[i]) / Decimal(period)

        # Step 3: Calculate +DI and -DI
        if smoothed_tr == Decimal("0"):
            return Decimal("0")

        plus_di = (smoothed_plus_dm / smoothed_tr) * Decimal("100")
        minus_di = (smoothed_minus_dm / smoothed_tr) * Decimal("100")

        # Step 4: Calculate DX
        di_sum = plus_di + minus_di
        if di_sum == Decimal("0"):
            return Decimal("0")

        dx = (abs(plus_di - minus_di) / di_sum) * Decimal("100")

        # Step 5: Calculate ADX (smoothed DX)
        # For simplicity, return DX as ADX approximation
        # Full ADX calculation requires smoothing multiple DX values
        return dx

    def _calculate_atr(self, bars: list["OHLCVBar"], period: int = 14) -> Decimal:
        """
        Calculate Average True Range (ATR).

        ATR measures volatility by averaging True Range over a period.
        Higher ATR = higher volatility, lower ATR = lower volatility.

        Algorithm:
        ----------
        1. Calculate True Range for each bar:
           TR = max(high-low, abs(high-prev_close), abs(low-prev_close))
        2. Calculate ATR = average(TR, period) using Wilder's smoothing

        Parameters:
        -----------
        bars : list[OHLCVBar]
            OHLCV bars (minimum period + 1)
        period : int
            ATR period (default 14)

        Returns:
        --------
        Decimal
            ATR value (in price units)
        """
        if len(bars) < period + 1:
            return Decimal("0")

        tr_values = []

        for i in range(1, len(bars)):
            curr_high = bars[i].high
            curr_low = bars[i].low
            prev_close = bars[i - 1].close

            # True Range = max(high-low, abs(high-prev_close), abs(low-prev_close))
            tr = max(
                curr_high - curr_low,
                abs(curr_high - prev_close),
                abs(curr_low - prev_close),
            )

            tr_values.append(tr)

        if len(tr_values) < period:
            return Decimal("0")

        # Wilder's smoothing: First ATR = average of first 'period' TRs
        atr = sum(tr_values[:period]) / Decimal(period)

        # Subsequent ATRs: ATR = ((ATR_prev * (period-1)) + TR_current) / period
        for i in range(period, len(tr_values)):
            atr = (atr * Decimal(period - 1) + tr_values[i]) / Decimal(period)

        return atr

    def _calculate_avg_atr(self, bars: list["OHLCVBar"], period: int = 20) -> Decimal:
        """
        Calculate average ATR over a longer period for volatility comparison.

        Used to determine if current ATR is HIGH (> 1.5x avg) or LOW (< 0.5x avg).

        Parameters:
        -----------
        bars : list[OHLCVBar]
            OHLCV bars (minimum period + 14 for ATR calculation)
        period : int
            Lookback period for averaging ATR (default 20)

        Returns:
        --------
        Decimal
            Average ATR over period
        """
        if len(bars) < period + 14:
            return Decimal("0")

        atr_values = []

        # Calculate ATR for each point in the lookback window
        for i in range(len(bars) - period, len(bars)):
            if i >= 14:
                atr = self._calculate_atr(bars[: i + 1], period=14)
                atr_values.append(atr)

        if not atr_values:
            return Decimal("0")

        return sum(atr_values) / Decimal(len(atr_values))
