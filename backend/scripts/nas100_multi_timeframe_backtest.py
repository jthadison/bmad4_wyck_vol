"""
NAS100 (Nasdaq-100) Multi-Timeframe Backtest Analysis Script

Purpose:
--------
Test NAS100 (Nasdaq-100 Technology Index) across multiple timeframes to evaluate:
1. Pattern detection quality with TRUE VOLUME in high-volatility tech stocks
2. Campaign formation characteristics in tech-heavy indices
3. Higher volatility impact on Wyckoff pattern reliability
4. Optimal timeframe for tech index trading vs DOW industrials

Timeframes Tested:
------------------
- 15m (15-Minute): Active day trading (high volatility)
- 1h (Hourly): Primary intraday campaign detection
- 1d (Daily): Classic Wyckoff timeframe

Key Differences vs US30:
-----------------------
1. HIGHER VOLATILITY: Tech stocks = wider daily ranges (3-5% vs 1-2% DOW)
2. MOMENTUM BIAS: NAS100 trends stronger/longer (FANG stocks dominate)
3. GAP BEHAVIOR: More frequent/larger overnight gaps (tech news driven)
4. VOLUME PATTERNS: Higher intraday volume variance (algo/HFT activity)
5. SENTIMENT DRIVEN: More reactive to macro/Fed/earnings events

Educational Goals:
------------------
From a Wyckoff perspective, we want to learn:
- Does higher volatility improve or degrade pattern quality?
- How does tech momentum affect campaign completion rates?
- Are NAS100 Spring patterns more/less reliable than DOW?
- Impact of algo trading on TRUE VOLUME analysis
- Does session performance differ (tech-heavy = West Coast influence)?

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
from src.pattern_engine.intraday_volume_analyzer import IntradayVolumeAnalyzer

logger = structlog.get_logger(__name__)


class NAS100MultiTimeframeBacktest:
    """
    Multi-timeframe backtest orchestrator for NAS100 (Nasdaq-100).

    Tests Wyckoff pattern detection in high-volatility tech environment
    with TRUE VOLUME analysis.
    """

    TIMEFRAMES = {
        "15m": {"multiplier": 15, "timespan": "minute", "days": 30, "name": "15-Minute"},
        "1h": {"multiplier": 1, "timespan": "hour", "days": 90, "name": "Hourly"},
        "1d": {"multiplier": 1, "timespan": "day", "days": 365, "name": "Daily"},
    }

    # Market sessions (US/Eastern Time) - SAME as US30
    SESSION_HOURS = {
        "OPENING": (9.5, 10.0),  # 9:30-10:00 (EXTREME volatility on NAS100)
        "CORE": (10.0, 15.0),  # 10:00-15:00 (best liquidity)
        "POWER": (15.0, 16.0),  # 15:00-16:00 (closing action)
    }

    def __init__(self):
        """Initialize backtest orchestrator."""
        self.symbol = "I:NDX"  # Nasdaq-100 Index
        self.adapter = PolygonAdapter()
        self.campaign_detector = None
        self.intraday_volume = IntradayVolumeAnalyzer(asset_type="index")  # TRUE VOLUME
        self.results = {}
        self.current_timeframe = None
        self.session_stats = {}

    async def run_all_timeframes(self) -> dict[str, BacktestResult]:
        """Run backtests across all timeframes."""
        print("=" * 80)
        print("NAS100 (NASDAQ-100) MULTI-TIMEFRAME WYCKOFF BACKTEST")
        print("=" * 80)
        print(f"Symbol: {self.symbol}")
        print("Asset Type: TECH INDEX (High Volatility, True Volume)")
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
        """Run backtest for a single timeframe."""
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

        # Create campaign detector with NAS100-optimized thresholds
        self.campaign_detector = self._create_campaign_detector(timeframe_code)
        self.current_timeframe = timeframe_code
        self.session_stats[timeframe_code] = {"OPENING": [], "CORE": [], "POWER": []}

        print("[OK] Using HIGH-VOLATILITY optimized detector for NAS100")

        # Configure backtest
        config = BacktestConfig(
            symbol=self.symbol,
            start_date=start_date,
            end_date=end_date,
            initial_capital=Decimal("100000"),
            max_position_size=Decimal("0.015"),  # 1.5% (vs 2% DOW - higher vol)
            commission_per_share=Decimal("0.0001"),
            timeframe=timeframe_code,
        )

        print("Running backtest with Wyckoff campaign strategy...")
        engine = BacktestEngine(config)

        result = engine.run(
            bars=bars,
            strategy_func=self._wyckoff_campaign_strategy,
            avg_volume=Decimal("500000000"),  # NAS100 higher volume than DOW
        )

        print(f"[OK] Backtest complete: {len(result.trades)} trades executed")

        return result

    def _create_campaign_detector(self, timeframe: str) -> IntradayCampaignDetector:
        """
        Create campaign detector with NAS100-optimized parameters.

        NAS100 requires WIDER thresholds due to higher volatility:
        - Spring penetration: 1.5-2x DOW thresholds
        - Volume thresholds: SAME (institutional behavior universal)
        - Session filtering: MORE CRITICAL (opening gaps extreme)
        """
        # NAS100 has ~2x volatility of DOW = wider thresholds needed
        if timeframe == "15m":
            spring_config = {
                "creek_threshold": Decimal("0.012"),  # 1.2% (vs 0.8% DOW)
                "ice_threshold": Decimal("0.022"),  # 2.2% (vs 1.5% DOW)
                "max_penetration": Decimal("0.045"),  # 4.5% (vs 3.0% DOW)
            }
        elif timeframe == "1h":
            spring_config = {
                "creek_threshold": Decimal("0.022"),  # 2.2% (vs 1.5% DOW)
                "ice_threshold": Decimal("0.038"),  # 3.8% (vs 2.5% DOW)
                "max_penetration": Decimal("0.075"),  # 7.5% (vs 5.0% DOW)
            }
        else:  # 1d
            spring_config = {
                "creek_threshold": Decimal("0.030"),  # 3.0% (vs 2.0% DOW)
                "ice_threshold": Decimal("0.045"),  # 4.5% (vs 3.0% DOW)
                "max_penetration": Decimal("0.090"),  # 9.0% (vs 6.0% DOW)
            }

        # Volume thresholds SAME (institutional behavior universal)
        return IntradayCampaignDetector(
            campaign_window_hours=48,
            max_pattern_gap_hours=48,
            min_patterns_for_active=2,
            expiration_hours=72,
            max_concurrent_campaigns=3,
            max_portfolio_heat_pct=40.0,
        )

    def _wyckoff_campaign_strategy(self, bar: OHLCVBar, context: dict) -> Optional[str]:
        """
        Wyckoff campaign strategy optimized for NAS100 volatility.

        Key adjustments vs US30:
        - Wider stop losses (2.5-3% vs 2%)
        - Tighter trailing stops (momentum can reverse fast)
        - More aggressive session filtering (opening gaps deadly)
        """
        if "bars" not in context:
            context["bars"] = []
            context["position"] = False
            context["entry_price"] = None
            context["stop_loss"] = None
            context["campaign_entry"] = None

        context["bars"].append(bar)

        if len(context["bars"]) < 50:
            return None

        session = self._detect_market_session(bar.timestamp)

        # NAS100: AVOID OPENING SESSION (gaps can be 2-3%)
        if self.current_timeframe in ["15m", "1h"]:
            if session == "OPENING" and not context["position"]:
                return None

        # Entry logic
        if not context["position"]:
            spring_signal = self._detect_campaign_entry(context["bars"], bar, session)

            if spring_signal:
                context["position"] = True
                context["entry_price"] = bar.close
                # NAS100: Wider stop (2.5% vs 2% DOW)
                context["stop_loss"] = bar.close * Decimal("0.975")
                context["campaign_entry"] = len(context["bars"])

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

            if context["entry_price"]:
                gain_pct = (bar.close - context["entry_price"]) / context["entry_price"]

                # NAS100: Higher profit target (4% vs 3% DOW - momentum)
                if gain_pct > Decimal("0.04"):
                    context["position"] = False
                    return "SELL"

                # Aggressive trailing stop (NAS100 reverses fast)
                if gain_pct > Decimal("0.02"):  # After 2% gain
                    trailing_stop = bar.close * Decimal("0.98")  # 2% trailing
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
        """Detect US market session."""
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
        """
        Detect Spring-based campaign entry for NAS100.

        Same logic as US30 but with awareness of higher volatility.
        """
        index = len(bars) - 1

        if index < 20:
            return False

        # Volume analysis
        recent_volume = [b.volume for b in bars[max(0, index - 20) : index]]
        avg_volume = sum(recent_volume) / len(recent_volume) if recent_volume else Decimal("1")
        volume_ratio = float(current_bar.volume / avg_volume) if avg_volume > 0 else 1.0

        # Spring criterion: LOW volume
        if volume_ratio >= 0.7:
            return False

        # Check for new low
        recent_lows = [b.low for b in bars[max(0, index - 20) : index]]
        min_recent_low = min(recent_lows) if recent_lows else current_bar.low

        # New low or test
        if current_bar.low <= min_recent_low * Decimal("1.003"):  # Within 0.3% (wider than DOW)
            # Bullish reversal
            bar_range = current_bar.high - current_bar.low
            if bar_range > 0:
                close_position = (current_bar.close - current_bar.low) / bar_range
                if close_position > Decimal("0.5"):
                    # Session filter
                    if session in ["CORE", "POWER", None]:
                        return True

        return False

    def _print_timeframe_summary(self, timeframe: str, result: BacktestResult):
        """Print summary statistics."""
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
        print("COMPARATIVE ANALYSIS - ALL TIMEFRAMES (NAS100)")
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

        # Highlights
        print("\n" + "=" * 100)
        print("NAS100 PERFORMANCE HIGHLIGHTS")
        print("=" * 100)

        if self.results:
            best_return = max(self.results.items(), key=lambda x: x[1].summary.total_return_pct)
            best_sharpe = max(
                self.results.items(), key=lambda x: x[1].summary.sharpe_ratio or Decimal("-999")
            )

            print(
                f"\n[+] Most Profitable: {self.TIMEFRAMES[best_return[0]]['name']} "
                f"({best_return[1].summary.total_return_pct:.2f}%)"
            )
            print(
                f"[+] Best Risk-Adjusted: {self.TIMEFRAMES[best_sharpe[0]]['name']} "
                f"(Sharpe: {best_sharpe[1].summary.sharpe_ratio:.2f})"
            )

            print("\n[NAS100 CHARACTERISTICS]:")
            print("  • 2x volatility of DOW = wider price thresholds needed")
            print("  • Stronger momentum = higher profit targets possible")
            print("  • Tech-driven gaps = opening session MORE dangerous")
            print("  • Algo/HFT activity = session filtering CRITICAL")


async def main():
    """Main execution function."""
    backtest = NAS100MultiTimeframeBacktest()

    try:
        results = await backtest.run_all_timeframes()
        backtest.print_comparative_analysis()

        print("\n" + "=" * 80)
        print("NAS100 BACKTEST COMPLETE")
        print("=" * 80)
        print(f"Results generated for {len(results)} timeframes")
        print("High-volatility tech index analyzed with TRUE VOLUME")

    except Exception as e:
        print(f"\n[ERROR] Backtest execution failed: {str(e)}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())
