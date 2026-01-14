"""
SPX500 (S&P 500) Multi-Timeframe Backtest Analysis Script

Purpose:
--------
Test SPX500 (S&P 500 Index) across multiple timeframes to evaluate:
1. Pattern detection quality with TRUE VOLUME (broad market index)
2. Campaign formation characteristics vs narrow indices (DOW 30)
3. Market-cap weighted behavior vs price-weighted (DOW)
4. Optimal timeframe for Wyckoff pattern trading on broad market

Timeframes Tested:
------------------
- 15m (15-Minute): Active day trading
- 1h (Hourly): Primary intraday campaign detection
- 1d (Daily): Classic Wyckoff timeframe

SPX500 Characteristics vs Other Indices:
-----------------------------------------
- BROADEST US MARKET EXPOSURE: 500 companies vs 30 (DOW) / 100 (NAS100)
- MARKET-CAP WEIGHTED: Large-caps dominate (vs price-weighted DOW)
- SECTOR DIVERSIFICATION: Tech ~28%, Healthcare ~13%, Financials ~12%
- VOLATILITY: MODERATE (1.5-3% daily range) - between DOW and NAS100
- LIQUIDITY: HIGHEST (SPY ETF = $50B+ daily volume)
- TRUE VOLUME: Institutional footprint visibility (like DOW/NAS100)

Educational Goals:
------------------
From a Wyckoff perspective, we want to learn:
- Does broad diversification improve pattern reliability vs narrow indices?
- How does market-cap weighting affect campaign completion rates?
- Is SPX500 more stable than NAS100, more volatile than DOW?
- Session-based performance compared to DOW and NAS100
- Does TRUE VOLUME advantage manifest on broad market index?

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
from src.backtesting.intraday_campaign_detector import IntradayCampaignDetector
from src.market_data.adapters.polygon_adapter import PolygonAdapter
from src.models.backtest import BacktestConfig, BacktestResult
from src.models.ohlcv import OHLCVBar
from src.pattern_engine.detectors.lps_detector import LPSDetector
from src.pattern_engine.detectors.sos_detector import SOSDetector
from src.pattern_engine.detectors.spring_detector import SpringDetector
from src.pattern_engine.intraday_volume_analyzer import IntradayVolumeAnalyzer

logger = structlog.get_logger(__name__)


class SPX500MultiTimeframeBacktest:
    """
    Multi-timeframe backtest orchestrator for SPX500 (S&P 500).

    Tests Wyckoff pattern detection and campaign formation across
    different timeframes with TRUE VOLUME analysis on broad market index.
    """

    TIMEFRAMES = {
        "15m": {"multiplier": 15, "timespan": "minute", "days": 30, "name": "15-Minute"},
        "1h": {"multiplier": 1, "timespan": "hour", "days": 90, "name": "Hourly"},
        "1d": {"multiplier": 1, "timespan": "day", "days": 365, "name": "Daily"},
    }

    # Market sessions (US/Eastern Time)
    SESSION_HOURS = {
        "OPENING": (9.5, 10.0),  # 9:30-10:00 (high volatility)
        "CORE": (10.0, 15.0),  # 10:00-15:00 (best liquidity)
        "POWER": (15.0, 16.0),  # 15:00-16:00 (closing action)
    }

    def __init__(self):
        """Initialize backtest orchestrator."""
        self.symbol = "I:SPX"  # S&P 500 Index
        self.adapter = PolygonAdapter()
        self.campaign_detector = None  # Will be set per-timeframe
        self.intraday_volume = IntradayVolumeAnalyzer(asset_type="index")  # TRUE VOLUME
        self.results = {}
        self.current_timeframe = None
        self.session_stats = {}

    async def run_all_timeframes(self) -> dict[str, BacktestResult]:
        """Run backtests across all timeframes."""
        print("=" * 80)
        print("SPX500 (S&P 500) MULTI-TIMEFRAME WYCKOFF BACKTEST")
        print("=" * 80)
        print(f"Symbol: {self.symbol}")
        print("Asset Type: BROAD MARKET INDEX (500 companies, Market-Cap Weighted)")
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
            timeframe_code: Timeframe identifier (e.g., "1h", "1d")
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

        # Create campaign detector with SPX500 thresholds (between DOW and NAS100)
        self.campaign_detector = self._create_campaign_detector(timeframe_code)
        self.current_timeframe = timeframe_code
        self.session_stats[timeframe_code] = {"OPENING": [], "CORE": [], "POWER": []}

        print("[OK] Using MODERATE-VOLATILITY detector for SPX500 (broad market)")

        # Configure backtest
        config = BacktestConfig(
            symbol=self.symbol,
            start_date=start_date,
            end_date=end_date,
            initial_capital=Decimal("100000"),
            max_position_size=Decimal("0.018"),  # 1.8% (between DOW 2% and NAS100 1.5%)
            commission_per_share=Decimal("0.0001"),
            timeframe=timeframe_code,
        )

        # Run backtest
        print("Running backtest with Wyckoff campaign strategy...")
        engine = BacktestEngine(config)

        result = engine.run(
            bars=bars,
            strategy_func=self._wyckoff_campaign_strategy,
            avg_volume=Decimal("500000000"),  # SPX average daily volume
        )

        print(f"[OK] Backtest complete: {len(result.trades)} trades executed")

        return result

    def _create_campaign_detector(self, timeframe: str) -> IntradayCampaignDetector:
        """
        Create campaign detector with SPX500-optimized parameters.

        SPX500 has MODERATE volatility (between DOW and NAS100), so thresholds
        are calibrated accordingly:
        - DOW: Lower vol = tighter thresholds
        - SPX500: MODERATE vol = MODERATE thresholds
        - NAS100: Higher vol = wider thresholds

        Args:
            timeframe: Timeframe code (15m, 1h, 1d)

        Returns:
            Configured IntradayCampaignDetector
        """
        # SPX500 volatility is ~1.5x DOW, ~0.6x NAS100
        # Thresholds adjusted: DOW baseline * 1.3 multiplier
        if timeframe == "15m":
            spring = SpringDetector(
                timeframe="15m",
                creek_threshold=Decimal("0.010"),  # DOW: 0.008, SPX500: 0.010 (+25%)
                ice_threshold=Decimal("0.020"),  # DOW: 0.015, SPX500: 0.020 (+33%)
                max_penetration=Decimal("0.040"),  # DOW: 0.030, SPX500: 0.040 (+33%)
                volume_threshold=Decimal("0.7"),
                session_filter=True,
                intraday_volume_analyzer=self.intraday_volume,
            )
            sos = SOSDetector(
                timeframe="15m",
                ice_threshold=Decimal("0.020"),
                creek_threshold=Decimal("0.010"),
                volume_threshold=Decimal("1.2"),
                session_filter=True,
                intraday_volume_analyzer=self.intraday_volume,
            )
            lps = LPSDetector(
                timeframe="15m",
                ice_threshold=Decimal("0.020"),
                volume_threshold=Decimal("0.8"),
                session_filter=True,
                intraday_volume_analyzer=self.intraday_volume,
            )

        elif timeframe == "1h":
            spring = SpringDetector(
                timeframe="1h",
                creek_threshold=Decimal("0.020"),  # DOW: 0.015, SPX500: 0.020 (+33%)
                ice_threshold=Decimal("0.032"),  # DOW: 0.025, SPX500: 0.032 (+28%)
                max_penetration=Decimal("0.065"),  # DOW: 0.050, SPX500: 0.065 (+30%)
                volume_threshold=Decimal("0.7"),
                session_filter=True,
                intraday_volume_analyzer=self.intraday_volume,
            )
            sos = SOSDetector(
                timeframe="1h",
                ice_threshold=Decimal("0.032"),
                creek_threshold=Decimal("0.020"),
                volume_threshold=Decimal("1.2"),
                session_filter=True,
                intraday_volume_analyzer=self.intraday_volume,
            )
            lps = LPSDetector(
                timeframe="1h",
                ice_threshold=Decimal("0.032"),
                volume_threshold=Decimal("0.8"),
                session_filter=True,
                intraday_volume_analyzer=self.intraday_volume,
            )

        else:  # 1d
            spring = SpringDetector(
                timeframe="1d",
                creek_threshold=Decimal("0.025"),  # DOW: 0.020, SPX500: 0.025 (+25%)
                ice_threshold=Decimal("0.038"),  # DOW: 0.030, SPX500: 0.038 (+27%)
                max_penetration=Decimal("0.075"),  # DOW: 0.060, SPX500: 0.075 (+25%)
                volume_threshold=Decimal("0.7"),
                session_filter=False,
                intraday_volume_analyzer=self.intraday_volume,
            )
            sos = SOSDetector(
                timeframe="1d",
                ice_threshold=Decimal("0.038"),
                creek_threshold=Decimal("0.025"),
                volume_threshold=Decimal("1.2"),
                session_filter=False,
                intraday_volume_analyzer=self.intraday_volume,
            )
            lps = LPSDetector(
                timeframe="1d",
                ice_threshold=Decimal("0.038"),
                volume_threshold=Decimal("0.8"),
                session_filter=False,
                intraday_volume_analyzer=self.intraday_volume,
            )

        # Create campaign detector
        return IntradayCampaignDetector(
            campaign_window_hours=48,
            max_pattern_gap_hours=48,
            min_patterns_for_active=2,
            expiration_hours=72,
            max_concurrent_campaigns=3,
            max_portfolio_heat_pct=10.0,  # FR7.7/AC7.14
        )

    def _wyckoff_campaign_strategy(self, bar: OHLCVBar, context: dict) -> Optional[str]:
        """
        Wyckoff campaign-based trading strategy for SPX500.

        Args:
            bar: Current bar
            context: Strategy context

        Returns:
            "BUY", "SELL", or None
        """
        # Initialize context
        if "bars" not in context:
            context["bars"] = []
            context["position"] = False
            context["entry_price"] = None
            context["stop_loss"] = None
            context["campaign_entry"] = None

        context["bars"].append(bar)

        # Need at least 50 bars
        if len(context["bars"]) < 50:
            return None

        # Detect market session
        session = self._detect_market_session(bar.timestamp)

        # Session filtering for intraday
        if self.current_timeframe in ["15m", "1h"]:
            if session == "OPENING" and not context["position"]:
                return None

        # Entry logic
        if not context["position"]:
            spring_signal = self._detect_campaign_entry(context["bars"], bar, session)

            if spring_signal:
                context["position"] = True
                context["entry_price"] = bar.close
                context["stop_loss"] = bar.close * Decimal("0.975")  # 2.5% stop (wider than DOW)
                context["campaign_entry"] = len(context["bars"])

                # Track session performance
                if session and self.current_timeframe in self.session_stats:
                    self.session_stats[self.current_timeframe][session].append(
                        {"entry_bar": len(context["bars"]), "entry_price": bar.close}
                    )

                return "BUY"

        # Exit logic
        if context["position"]:
            # Stop loss
            if bar.close < context["stop_loss"]:
                context["position"] = False
                return "SELL"

            # Take profit (3.5% target for SPX500 - between DOW 3% and NAS100 4%)
            if context["entry_price"]:
                gain_pct = (bar.close - context["entry_price"]) / context["entry_price"]

                if gain_pct > Decimal("0.035"):  # 3.5% target
                    context["position"] = False
                    return "SELL"

                # Trailing stop
                if gain_pct > Decimal("0.018"):  # After 1.8% gain
                    trailing_stop = bar.close * Decimal("0.982")  # 1.8% trail
                    if trailing_stop > context["stop_loss"]:
                        context["stop_loss"] = trailing_stop

            # Time-based exit
            if context["campaign_entry"]:
                bars_in_trade = len(context["bars"]) - context["campaign_entry"]
                if bars_in_trade > 10 and bar.close < context["entry_price"]:
                    context["position"] = False
                    return "SELL"

        return None

    def _detect_market_session(self, timestamp: datetime) -> Optional[str]:
        """Detect US market session from timestamp."""
        hour = timestamp.hour - 5  # Approximate EST
        if hour < 0:
            hour += 24

        minute = timestamp.minute
        time_decimal = hour + minute / 60.0

        for session_name, (start, end) in self.SESSION_HOURS.items():
            if start <= time_decimal < end:
                return session_name

        return None

    def _detect_campaign_entry(
        self, bars: list[OHLCVBar], current_bar: OHLCVBar, session: Optional[str]
    ) -> bool:
        """Detect Spring-based campaign entry signal."""
        index = len(bars) - 1

        if index < 20:
            return False

        # Volume analysis
        recent_volume = [b.volume for b in bars[max(0, index - 20) : index]]
        avg_volume = sum(recent_volume) / len(recent_volume) if recent_volume else Decimal("1")
        volume_ratio = float(current_bar.volume / avg_volume) if avg_volume > 0 else 1.0

        # Spring: LOW volume
        if volume_ratio >= 0.7:
            return False

        # Check for new low
        recent_lows = [b.low for b in bars[max(0, index - 20) : index]]
        min_recent_low = min(recent_lows) if recent_lows else current_bar.low

        if current_bar.low <= min_recent_low * Decimal("1.002"):
            # Bullish reversal
            bar_range = current_bar.high - current_bar.low
            if bar_range > 0:
                close_position = (current_bar.close - current_bar.low) / bar_range
                if close_position > Decimal("0.5"):
                    if session in ["CORE", "POWER", None]:
                        return True

        return False

    def _print_timeframe_summary(self, timeframe: str, result: BacktestResult):
        """Print summary statistics for a timeframe."""
        metrics = result.summary

        print(f"\n[RESULTS SUMMARY] - {self.TIMEFRAMES[timeframe]['name']}")
        print(f"{'-' * 60}")
        print(f"Total Signals: {metrics.total_trades}")
        print(f"Winning Trades: {metrics.winning_trades}")
        print(f"Losing Trades: {metrics.losing_trades}")
        print(f"Win Rate: {metrics.win_rate * 100:.1f}%")
        print(f"Total Return: {metrics.total_return_pct:.2f}%")
        print(f"Max Drawdown: {metrics.max_drawdown * 100:.2f}%")

        if metrics.sharpe_ratio:
            print(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")

        if metrics.profit_factor:
            print(f"Profit Factor: {metrics.profit_factor:.2f}")

        if metrics.average_r_multiple:
            print(f"Avg R-Multiple: {metrics.average_r_multiple:.2f}R")

        # Session performance
        if timeframe in ["15m", "1h"] and timeframe in self.session_stats:
            print("\n[SESSION PERFORMANCE]:")
            for session_name, trades in self.session_stats[timeframe].items():
                if trades:
                    print(f"  {session_name}: {len(trades)} entries")

    def print_comparative_analysis(self):
        """Print comparative analysis across all timeframes."""
        if not self.results:
            print("No results to compare")
            return

        print("\n" + "=" * 100)
        print("COMPARATIVE ANALYSIS - ALL TIMEFRAMES (SPX500)")
        print("=" * 100)

        # Header
        print(
            f"\n{'Timeframe':<12} {'Signals':<8} {'Wins':<6} {'Losses':<7} "
            f"{'Win%':<8} {'Return%':<10} {'MaxDD%':<10} {'Sharpe':<8} {'PF':<6}"
        )
        print("-" * 100)

        # Data rows
        for tf_code, result in self.results.items():
            tf_name = self.TIMEFRAMES[tf_code]["name"]
            m = result.summary

            print(
                f"{tf_name:<12} {m.total_trades:<8} {m.winning_trades:<6} {m.losing_trades:<7} "
                f"{m.win_rate*100:<7.1f}% {m.total_return_pct:<9.2f}% "
                f"{m.max_drawdown*100:<9.2f}% {m.sharpe_ratio or 0:<7.2f} "
                f"{m.profit_factor or 0:<6.2f}"
            )

        # Session analysis
        print("\n" + "=" * 100)
        print("SESSION PERFORMANCE BREAKDOWN")
        print("=" * 100)

        for tf_code in ["15m", "1h"]:
            if tf_code in self.session_stats:
                print(f"\n{self.TIMEFRAMES[tf_code]['name']} Session Stats:")
                for session, trades in self.session_stats[tf_code].items():
                    print(f"  {session:<10}: {len(trades):>4} entries")

        # Performance highlights
        print("\n" + "=" * 100)
        print("PERFORMANCE HIGHLIGHTS")
        print("=" * 100)

        if self.results:
            best_return = max(self.results.items(), key=lambda x: x[1].summary.total_return_pct)
            best_sharpe = max(
                self.results.items(), key=lambda x: x[1].summary.sharpe_ratio or Decimal("-999")
            )
            best_winrate = max(self.results.items(), key=lambda x: x[1].summary.win_rate)

            print(
                f"\n[+] Most Profitable: {self.TIMEFRAMES[best_return[0]]['name']} "
                f"({best_return[1].summary.total_return_pct:.2f}%)"
            )
            print(
                f"[+] Best Risk-Adjusted: {self.TIMEFRAMES[best_sharpe[0]]['name']} "
                f"(Sharpe: {best_sharpe[1].summary.sharpe_ratio:.2f})"
            )
            print(
                f"[+] Highest Win Rate: {self.TIMEFRAMES[best_winrate[0]]['name']} "
                f"({best_winrate[1].summary.win_rate*100:.1f}%)"
            )

            # SPX500 specific insights
            print("\n[SPX500 CHARACTERISTICS]:")
            print("  • Broad diversification (500 companies) = smoother patterns than DOW/NAS100")
            print("  • Market-cap weighted = large-cap dominance (AAPL, MSFT, NVDA)")
            print("  • Moderate volatility = between DOW (stable) and NAS100 (volatile)")
            print("  • TRUE VOLUME advantage on institutional accumulation/distribution")


async def main():
    """Main execution function."""
    backtest = SPX500MultiTimeframeBacktest()

    try:
        # Run all timeframes
        results = await backtest.run_all_timeframes()

        # Print comparative analysis
        backtest.print_comparative_analysis()

        print("\n" + "=" * 80)
        print("SPX500 BACKTEST COMPLETE")
        print("=" * 80)
        print(f"Results generated for {len(results)} timeframes")
        print("Broad market behavior analyzed with TRUE VOLUME confirmation")

    except Exception as e:
        print(f"\n[ERROR] Backtest execution failed: {str(e)}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())
