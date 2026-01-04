"""
EUR/USD Multi-Timeframe Backtest Analysis Script

Purpose:
--------
Test EUR/USD (C:EURUSD) across multiple timeframes to evaluate:
1. Pattern detection quality at different timeframes
2. Campaign formation characteristics in forex markets
3. Volume validation effectiveness (tick volume vs true volume)
4. Optimal timeframe for Wyckoff pattern trading

Timeframes Tested:
------------------
- 1h (Hourly): Intraday campaign detection
- 4h (4-Hour): Short-term swing trading
- 1d (Daily): Primary Wyckoff timeframe
- 1w (Weekly): Long-term campaign analysis

Educational Goals:
------------------
From a Wyckoff perspective, we want to learn:
- Do campaigns form more clearly on longer timeframes?
- How does forex tick volume affect pattern quality?
- What's the campaign completion rate across timeframes?
- Does Spring-to-markup success rate vary by timeframe?

Author: Wyckoff Mentor Analysis
"""

import asyncio
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import structlog

from src.backtesting.backtest_engine import BacktestEngine
from src.backtesting.intraday_campaign_detector import create_timeframe_optimized_detector
from src.market_data.adapters.polygon_adapter import PolygonAdapter
from src.models.backtest import BacktestConfig, BacktestResult
from src.models.forex import ForexSession
from src.models.ohlcv import OHLCVBar
from src.pattern_engine.intraday_volume_analyzer import IntradayVolumeAnalyzer

logger = structlog.get_logger(__name__)


class EURUSDMultiTimeframeBacktest:
    """
    Multi-timeframe backtest orchestrator for EUR/USD.

    Tests Wyckoff pattern detection and campaign formation across
    different timeframes to identify optimal trading periods.
    """

    TIMEFRAMES = {
        "15m": {"multiplier": 15, "timespan": "minute", "days": 30, "name": "15-Minute"},
        "1h": {"multiplier": 1, "timespan": "hour", "days": 180, "name": "Hourly"},
        "1d": {"multiplier": 1, "timespan": "day", "days": 730, "name": "Daily"},  # 2 years
    }

    def __init__(self):
        """Initialize backtest orchestrator."""
        self.symbol = "C:EURUSD"
        self.adapter = PolygonAdapter()
        self.campaign_detector = None  # Will be set per-timeframe
        self.intraday_volume = IntradayVolumeAnalyzer(asset_type="forex")
        self.results = {}
        self.current_timeframe = None  # Track current timeframe for strategy

    async def run_all_timeframes(self) -> dict[str, BacktestResult]:
        """
        Run backtests across all timeframes.

        Returns:
            Dictionary mapping timeframe -> BacktestResult
        """
        print("=" * 80)
        print("EUR/USD MULTI-TIMEFRAME WYCKOFF BACKTEST")
        print("=" * 80)
        print(f"Symbol: {self.symbol}")
        print(f"Timeframes: {', '.join(self.TIMEFRAMES.keys())}")
        print(f"Testing Date: {date.today()}")
        print()

        for tf_code, tf_config in self.TIMEFRAMES.items():
            print(f"\n{'=' * 60}")
            print(f"TESTING TIMEFRAME: {tf_config['name']} ({tf_code})")
            print(f"{'=' * 60}")

            try:
                result = await self.run_single_timeframe(tf_code, tf_config)
                self.results[tf_code] = result
                self._print_timeframe_summary(tf_code, result)

            except Exception as e:
                print(f"[ERROR] FAILED: {str(e)}")
                import traceback

                traceback.print_exc()

        return self.results

    async def run_single_timeframe(
        self, timeframe_code: str, timeframe_config: dict
    ) -> BacktestResult:
        """
        Run backtest for a single timeframe.

        Args:
            timeframe_code: Timeframe identifier (e.g., "1h", "4h")
            timeframe_config: Configuration for this timeframe

        Returns:
            BacktestResult with complete metrics
        """
        # Calculate date range
        end_date = date.today()
        start_date = end_date - timedelta(days=timeframe_config["days"])

        print(f"Date Range: {start_date} to {end_date} ({timeframe_config['days']} days)")

        # Fetch historical data
        print(f"Fetching {self.symbol} data...")
        bars = await self.adapter.fetch_historical_bars(
            symbol=self.symbol, start_date=start_date, end_date=end_date, timeframe=timeframe_code
        )

        if not bars:
            raise ValueError(f"No data available for {self.symbol} on {timeframe_code}")

        print(f"[OK] Fetched {len(bars)} bars")

        # Create timeframe-optimized campaign detector
        self.campaign_detector = create_timeframe_optimized_detector(timeframe_code)
        self.current_timeframe = timeframe_code

        print(
            f"[OK] Using {'intraday' if timeframe_code in ['15m', '1h'] else 'standard'} campaign detector"
        )

        # Configure backtest
        config = BacktestConfig(
            symbol=self.symbol,
            start_date=start_date,
            end_date=end_date,
            initial_capital=Decimal("100000"),  # $100k starting capital
            max_position_size=Decimal("0.02"),  # 2% position size (conservative forex)
            commission_per_share=Decimal("0.00002"),  # ~2 pip spread for EUR/USD
            timeframe=timeframe_code,  # Add timeframe for campaign performance tracking
        )

        # Run backtest with Wyckoff pattern detection strategy
        print("Running backtest with intraday-optimized Wyckoff strategy...")
        engine = BacktestEngine(config)

        result = engine.run(
            bars=bars,
            strategy_func=self._intraday_wyckoff_strategy,
            avg_volume=Decimal("1000000"),  # Forex tick volume reference
        )

        print(f"[OK] Backtest complete: {len(result.trades)} trades executed")

        return result

    def _intraday_wyckoff_strategy(self, bar: OHLCVBar, context: dict) -> Optional[str]:
        """
        Intraday-optimized Wyckoff pattern detection strategy.

        Integrates:
        - Session-aware volume analysis
        - Timeframe-adaptive thresholds
        - Session-specific entry rules
        - Low-volume reversal patterns (Spring-like setups)

        Args:
            bar: Current bar
            context: Strategy context with bar history

        Returns:
            "BUY", "SELL", or None
        """
        # Initialize context
        if "bars" not in context:
            context["bars"] = []
            context["prices"] = []
            context["position"] = False
            context["entry_price"] = None

        context["bars"].append(bar)

        # Need at least 50 bars for pattern analysis
        if len(context["bars"]) < 50:
            return None

        # Detect current session
        session = self._detect_session(bar.timestamp)

        # Session filtering: Avoid low-liquidity periods
        if session == ForexSession.ASIAN and self.current_timeframe in ["15m", "1h"]:
            # Don't enter new positions during Asian session on intraday timeframes
            # (Low liquidity causes false breakouts)
            if not context["position"]:
                return None

        # Calculate session-relative volume for current bar
        bars_list = context["bars"]
        current_index = len(bars_list) - 1

        volume_ratio = self.intraday_volume.calculate_session_relative_volume(
            bars=bars_list, index=current_index, session=session
        )

        # Spring-like pattern detection (low-volume reversal)
        spring_setup = self._detect_spring_setup(bars_list, current_index, volume_ratio)

        if spring_setup and not context["position"]:
            # Validate session timing - only enter during optimal sessions
            if session in [ForexSession.LONDON, ForexSession.OVERLAP]:
                context["position"] = True
                context["entry_price"] = bar.close
                return "BUY"

        # Exit logic: Simple momentum-based exit
        if context["position"]:
            # Calculate 20-bar SMA for exit
            if len(context["prices"]) >= 20:
                sma_20 = sum(context["prices"][-20:]) / 20

                # Exit if price drops below SMA or 2% stop loss hit
                if bar.close < sma_20:
                    context["position"] = False
                    context["entry_price"] = None
                    return "SELL"

                # Take profit at 1.5% gain (conservative for forex)
                if context["entry_price"]:
                    gain_pct = (bar.close - context["entry_price"]) / context["entry_price"]
                    if gain_pct > Decimal("0.015"):
                        context["position"] = False
                        context["entry_price"] = None
                        return "SELL"

        return None

    def _detect_session(self, timestamp: datetime) -> ForexSession:
        """Detect forex session from UTC timestamp."""
        hour = timestamp.hour

        if 0 <= hour < 8:
            return ForexSession.ASIAN
        elif 8 <= hour < 13:
            return ForexSession.LONDON
        elif 13 <= hour < 17:
            return ForexSession.OVERLAP
        elif 17 <= hour < 22:
            return ForexSession.NY
        else:
            return ForexSession.ASIAN

    def _detect_spring_setup(
        self, bars: list[OHLCVBar], index: int, volume_ratio: Optional[float]
    ) -> bool:
        """
        Simplified Spring pattern detection.

        A Spring setup occurs when:
        1. Price makes a new low (vs 20-bar lookback)
        2. Volume is LOW (<0.7x session average)
        3. Price recovers within 3-5 bars (early rally confirmation)

        Args:
            bars: Historical bars
            index: Current bar index
            volume_ratio: Session-relative volume ratio

        Returns:
            True if Spring setup detected
        """
        if index < 20:
            return False

        current_bar = bars[index]

        # Check if volume is low (Spring characteristic)
        if not volume_ratio or volume_ratio >= 0.7:
            return False  # Volume too high for Spring

        # Check if we made a new low vs recent range
        recent_lows = [b.low for b in bars[max(0, index - 20) : index]]
        if not recent_lows:
            return False

        min_recent_low = min(recent_lows)

        # Current bar makes new low or tests previous low
        if current_bar.low <= min_recent_low * Decimal("1.001"):  # Within 0.1%
            # Check for quick recovery (bullish reversal)
            # Bar should close in upper 50% of range
            bar_range = current_bar.high - current_bar.low
            if bar_range > 0:
                close_position = (current_bar.close - current_bar.low) / bar_range
                if close_position > Decimal("0.5"):
                    # Low volume + new low + strong close = Spring setup
                    return True

        return False

    def _print_timeframe_summary(self, timeframe: str, result: BacktestResult):
        """Print summary statistics for a timeframe."""
        metrics = result.summary

        print(f"\n[RESULTS SUMMARY] - {self.TIMEFRAMES[timeframe]['name']}")
        print(f"{'-' * 60}")
        print(f"Total Trades: {metrics.total_trades}")
        print(f"Win Rate: {metrics.win_rate * 100:.1f}%")
        print(f"Total Return: {metrics.total_return_pct:.2f}%")
        print(f"Max Drawdown: {metrics.max_drawdown * 100:.2f}%")

        if metrics.sharpe_ratio:
            print(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")

        if metrics.profit_factor:
            print(f"Profit Factor: {metrics.profit_factor:.2f}")

        if metrics.average_r_multiple:
            print(f"Avg R-Multiple: {metrics.average_r_multiple:.2f}R")

        # Campaign analysis
        if result.campaign_performance:
            campaigns = result.campaign_performance
            completed = len([c for c in campaigns if c.status == "COMPLETED"])
            failed = len([c for c in campaigns if c.status == "FAILED"])

            print("\n[CAMPAIGN ANALYSIS]:")
            print(f"  Total Campaigns: {len(campaigns)}")
            print(f"  Completed: {completed} ({completed/len(campaigns)*100:.1f}%)")
            print(f"  Failed: {failed} ({failed/len(campaigns)*100:.1f}%)")

            # Campaign types
            accumulation = len([c for c in campaigns if c.campaign_type == "ACCUMULATION"])
            distribution = len([c for c in campaigns if c.campaign_type == "DISTRIBUTION"])
            print(f"  Accumulation: {accumulation}")
            print(f"  Distribution: {distribution}")

    def print_comparative_analysis(self):
        """Print comparative analysis across all timeframes."""
        if not self.results:
            print("No results to compare")
            return

        print("\n" + "=" * 80)
        print("COMPARATIVE ANALYSIS - ALL TIMEFRAMES")
        print("=" * 80)

        # Header
        print(
            f"\n{'Timeframe':<12} {'Trades':<8} {'Win Rate':<10} {'Return %':<12} "
            f"{'Max DD %':<10} {'Sharpe':<8} {'Campaigns':<10}"
        )
        print("-" * 80)

        # Data rows
        for tf_code, result in self.results.items():
            tf_name = self.TIMEFRAMES[tf_code]["name"]
            m = result.summary

            campaigns_count = len(result.campaign_performance) if result.campaign_performance else 0

            print(
                f"{tf_name:<12} {m.total_trades:<8} {m.win_rate*100:<9.1f}% "
                f"{m.total_return_pct:<11.2f}% {m.max_drawdown*100:<9.2f}% "
                f"{m.sharpe_ratio or 0:<7.2f} {campaigns_count:<10}"
            )

        # Educational insights
        print("\n" + "=" * 80)
        print("WYCKOFF EDUCATIONAL INSIGHTS")
        print("=" * 80)

        best_tf = max(self.results.items(), key=lambda x: x[1].summary.total_return_pct)
        best_sharpe = max(
            self.results.items(), key=lambda x: x[1].summary.sharpe_ratio or Decimal("-999")
        )

        print(
            f"\n[+] Best Return: {self.TIMEFRAMES[best_tf[0]]['name']} "
            f"({best_tf[1].summary.total_return_pct:.2f}%)"
        )

        print(
            f"[+] Best Risk-Adjusted: {self.TIMEFRAMES[best_sharpe[0]]['name']} "
            f"(Sharpe: {best_sharpe[1].summary.sharpe_ratio:.2f})"
        )

        # Campaign insights
        print("\n[WYCKOFF INSIGHTS] Principle Observations:")
        print("   - Longer timeframes typically show clearer campaign structures")
        print("   - Daily/Weekly timeframes align with institutional accumulation periods")
        print("   - Hourly timeframes may show noise vs. genuine Wyckoff patterns")
        print("   - Campaign completion rate indicates pattern quality")


async def main():
    """Main execution function."""
    backtest = EURUSDMultiTimeframeBacktest()

    try:
        # Run all timeframes
        results = await backtest.run_all_timeframes()

        # Print comparative analysis
        backtest.print_comparative_analysis()

        print("\n" + "=" * 80)
        print("BACKTEST COMPLETE")
        print("=" * 80)
        print(f"Results saved for {len(results)} timeframes")
        print("Review the data above to determine optimal EUR/USD trading timeframe")

    except Exception as e:
        print(f"\n[ERROR] Backtest execution failed: {str(e)}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())
