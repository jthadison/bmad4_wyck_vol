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
from datetime import date, timedelta
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
from src.models.creek_level import CreekLevel
from src.models.forex import ForexSession, get_forex_session
from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import PhaseClassification, WyckoffPhase
from src.models.trading_range import RangeStatus, TradingRange
from src.pattern_engine.detectors.lps_detector import detect_lps
from src.pattern_engine.detectors.sos_detector import detect_sos_breakout
from src.pattern_engine.detectors.spring_detector import SpringDetector
from src.pattern_engine.intraday_volume_analyzer import IntradayVolumeAnalyzer
from src.pattern_engine.volume_analyzer import calculate_volume_ratio

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
        self.intraday_volume = None  # Will be set per-timeframe
        self.spring_detector = None  # Will be set per-timeframe
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

        # Initialize volume analyzer and pattern detectors based on timeframe
        is_intraday = timeframe_code in ["1m", "5m", "15m", "1h"]

        if is_intraday:
            # Intraday: Use IntradayVolumeAnalyzer with session filtering
            self.intraday_volume = IntradayVolumeAnalyzer(asset_type="forex")
            session_filter = True
            print("[OK] Pattern detectors initialized (intraday mode):")
            print("     - IntradayVolumeAnalyzer enabled")
            print("     - Session filtering: ENABLED")
        else:
            # Daily: Standard volume analysis, no session filtering
            self.intraday_volume = None
            session_filter = False
            print("[OK] Pattern detectors initialized (standard mode):")
            print("     - Standard volume analysis")
            print("     - Session filtering: DISABLED")

        # Initialize SpringDetector with timeframe-specific config
        self.spring_detector = SpringDetector(
            timeframe=timeframe_code,
            intraday_volume_analyzer=self.intraday_volume,
            session_filter_enabled=session_filter,
            session_confidence_scoring_enabled=session_filter,
        )

        # Create timeframe-optimized campaign detector
        self.campaign_detector = create_timeframe_optimized_detector(timeframe_code)
        self.current_timeframe = timeframe_code

        print("     - SpringDetector ready")
        print(f"     - Campaign detector: {'Intraday' if is_intraday else 'Standard'} mode")

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

        # FR6.7: Update trade exit reasons from strategy context
        if hasattr(engine, "strategy_context") and "exit_reasons" in engine.strategy_context:
            exit_reasons = engine.strategy_context["exit_reasons"]
            for i, trade in enumerate(result.trades):
                if i < len(exit_reasons):
                    trade.exit_reason = exit_reasons[i]

        # FR6.7: Print exit analysis for educational insights
        self._print_exit_analysis(result.trades)

        return result

    def _intraday_wyckoff_strategy(self, bar: OHLCVBar, context: dict) -> Optional[str]:
        """
        Intraday-optimized Wyckoff pattern detection strategy using real detectors.

        Integrates:
        - Real SpringDetector, SOSDetector, LPSDetector pattern detection
        - Campaign-based position management
        - Session-aware volume analysis for intraday timeframes
        - Phase D entry logic (SOS breakouts in active campaigns)

        Args:
            bar: Current bar
            context: Strategy context with bar history

        Returns:
            "BUY", "SELL", or None
        """
        # Initialize context
        if "bars" not in context:
            context["bars"] = []
            context["position"] = False
            context["entry_price"] = None
            context["last_sos"] = None
            context["volume_analysis"] = {}
            context["exit_reasons"] = []  # FR6.7: Track exit reasons for analysis

        context["bars"].append(bar)

        # Need at least 50 bars for pattern analysis
        if len(context["bars"]) < 50:
            return None

        bars_list = context["bars"]
        current_index = len(bars_list) - 1

        # Detect current session
        session = get_forex_session(bar.timestamp)

        # Session filtering for intraday: Avoid low-liquidity periods
        is_intraday = self.current_timeframe in ["15m", "1h"]
        if is_intraday and session == ForexSession.ASIAN and not context["position"]:
            return None  # Don't enter new positions during Asian session

        # Calculate volume ratio for current bar
        if self.intraday_volume and is_intraday:
            volume_ratio = self.intraday_volume.calculate_session_relative_volume(
                bars=bars_list, index=current_index, session=session
            )
        else:
            volume_ratio = calculate_volume_ratio(bars_list, current_index)

        context["volume_analysis"][bar.timestamp] = {"volume_ratio": Decimal(str(volume_ratio))}

        # Build dynamic trading range from recent 50 bars
        trading_range = self._build_trading_range(bars_list, current_index)

        # Detect patterns using real detectors
        # 1. Spring Detection
        try:
            spring_history = self.spring_detector.detect_all_springs(
                range=trading_range,
                bars=bars_list[max(0, current_index - 50) : current_index + 1],
                phase=WyckoffPhase.C,  # Springs occur in Phase C
            )
            if spring_history.best_spring:
                self.campaign_detector.add_pattern(spring_history.best_spring)
        except Exception:
            pass  # Pattern detection may fail if conditions aren't met

        # 2. SOS Breakout Detection
        try:
            phase_classification = PhaseClassification(phase=WyckoffPhase.D, confidence=85)
            sos = detect_sos_breakout(
                range=trading_range,
                bars=bars_list[max(0, current_index - 50) : current_index + 1],
                volume_analysis=context["volume_analysis"],
                phase=phase_classification,
                symbol=self.symbol,
                timeframe=self.current_timeframe,
                session_filter_enabled=is_intraday,
                session_confidence_scoring_enabled=is_intraday,
            )
            if sos:
                self.campaign_detector.add_pattern(sos)
                context["last_sos"] = sos
        except Exception:
            pass

        # 3. LPS Detection (if SOS exists)
        if context["last_sos"]:
            try:
                lps = detect_lps(
                    range=trading_range,
                    sos=context["last_sos"],
                    bars=bars_list[max(0, current_index - 50) : current_index + 1],
                    volume_analysis=context["volume_analysis"],
                    timeframe=self.current_timeframe,
                    session_filter_enabled=is_intraday,
                    session_confidence_scoring_enabled=is_intraday,
                )
                if lps:
                    self.campaign_detector.add_pattern(lps)
            except Exception:
                pass

        # Trading Logic: Enter on Phase D SOS in active campaign
        active_campaigns = self.campaign_detector.get_active_campaigns()

        if not context["position"] and active_campaigns:
            for campaign in active_campaigns:
                if campaign.current_phase == WyckoffPhase.D:
                    # Check if we have a fresh SOS in last 5 bars
                    if context["last_sos"] and (
                        current_index
                        - bars_list.index(
                            next(
                                (
                                    b
                                    for b in bars_list
                                    if b.timestamp == context["last_sos"].timestamp
                                ),
                                bars_list[-1],
                            )
                        )
                        < 5
                    ):
                        context["position"] = True
                        context["entry_price"] = bar.close
                        context["entry_bar_index"] = current_index
                        return "BUY"

        # FR6.5: Wyckoff-based multi-tier exit logic (Story 13.6)
        if context["position"] and context["entry_price"]:
            should_exit, exit_reason = self._wyckoff_exit_logic(
                bar=bar, context=context, active_campaigns=active_campaigns
            )

            if should_exit:
                context["position"] = False
                context["entry_price"] = None
                context["exit_reasons"].append(exit_reason)  # FR6.7: Track exit reason
                return "SELL"

        return None

    def _build_trading_range(self, bars: list[OHLCVBar], current_index: int) -> TradingRange:
        """
        Build dynamic trading range from recent bars for pattern detection.

        Uses last 50 bars to establish Ice (resistance) and Creek (support) levels.

        Args:
            bars: Historical bars
            current_index: Current bar index

        Returns:
            TradingRange with Ice/Creek levels for pattern detection
        """
        from src.models.pivot import Pivot, PivotType
        from src.models.price_cluster import PriceCluster

        lookback_bars = bars[max(0, current_index - 50) : current_index + 1]

        if not lookback_bars:
            # Fallback: use current bar
            lookback_bars = [bars[current_index]]

        # Calculate range boundaries
        highs = [b.high for b in lookback_bars]
        lows = [b.low for b in lookback_bars]

        range_high = max(highs)
        range_low = min(lows)

        # Calculate range metrics
        range_width = range_high - range_low
        range_width_pct = (range_width / range_low).quantize(Decimal("0.0001"))  # 4 decimal places
        midpoint = (range_high + range_low) / Decimal("2")

        # Create minimal pivot objects for clusters (need at least 2)
        # Find bars with highest and lowest prices
        high_bars_indices = [i for i, h in enumerate(highs) if h == range_high]
        low_bars_indices = [i for i, low_price in enumerate(lows) if low_price == range_low]

        # Create resistance pivots (HIGH pivots - price must match bar.high)
        resistance_pivots = []
        for i in high_bars_indices[:2]:  # Take up to 2 pivots
            resistance_pivots.append(
                Pivot(
                    bar=lookback_bars[i],
                    index=max(0, current_index - 50) + i,
                    price=lookback_bars[i].high,  # Must match bar.high for HIGH pivot
                    timestamp=lookback_bars[i].timestamp,
                    type=PivotType.HIGH,
                    strength=5,
                )
            )

        # Ensure we have at least 2 pivots (duplicate if needed)
        if len(resistance_pivots) == 1:
            resistance_pivots.append(resistance_pivots[0])
        if not resistance_pivots:  # If no pivots found, create default ones
            resistance_pivots = [
                Pivot(
                    bar=lookback_bars[-1],
                    index=current_index,
                    price=lookback_bars[-1].high,
                    timestamp=lookback_bars[-1].timestamp,
                    type=PivotType.HIGH,
                    strength=5,
                ),
                Pivot(
                    bar=lookback_bars[-1],
                    index=current_index,
                    price=lookback_bars[-1].high,
                    timestamp=lookback_bars[-1].timestamp,
                    type=PivotType.HIGH,
                    strength=5,
                ),
            ]

        # Create support pivots (LOW pivots - price must match bar.low)
        support_pivots = []
        for i in low_bars_indices[:2]:  # Take up to 2 pivots
            support_pivots.append(
                Pivot(
                    bar=lookback_bars[i],
                    index=max(0, current_index - 50) + i,
                    price=lookback_bars[i].low,  # Must match bar.low for LOW pivot
                    timestamp=lookback_bars[i].timestamp,
                    type=PivotType.LOW,
                    strength=5,
                )
            )

        # Ensure we have at least 2 pivots (duplicate if needed)
        if len(support_pivots) == 1:
            support_pivots.append(support_pivots[0])
        if not support_pivots:  # If no pivots found, create default ones
            support_pivots = [
                Pivot(
                    bar=lookback_bars[-1],
                    index=current_index,
                    price=lookback_bars[-1].low,
                    timestamp=lookback_bars[-1].timestamp,
                    type=PivotType.LOW,
                    strength=5,
                ),
                Pivot(
                    bar=lookback_bars[-1],
                    index=current_index,
                    price=lookback_bars[-1].low,
                    timestamp=lookback_bars[-1].timestamp,
                    type=PivotType.LOW,
                    strength=5,
                ),
            ]

        # Create price clusters
        # Calculate resistance cluster metrics
        res_prices = [p.price for p in resistance_pivots]
        res_avg = sum(res_prices) / len(res_prices)
        res_min = min(res_prices)
        res_max = max(res_prices)

        resistance_cluster = PriceCluster(
            pivots=resistance_pivots,
            average_price=res_avg,
            min_price=res_min,
            max_price=res_max,
            price_range=res_max - res_min,
            touch_count=len(resistance_pivots),
            cluster_type=PivotType.HIGH,
            std_deviation=Decimal("0"),
            timestamp_range=(resistance_pivots[0].timestamp, resistance_pivots[-1].timestamp),
        )

        # Calculate support cluster metrics
        sup_prices = [p.price for p in support_pivots]
        sup_avg = sum(sup_prices) / len(sup_prices)
        sup_min = min(sup_prices)
        sup_max = max(sup_prices)

        support_cluster = PriceCluster(
            pivots=support_pivots,
            average_price=sup_avg,
            min_price=sup_min,
            max_price=sup_max,
            price_range=sup_max - sup_min,
            touch_count=len(support_pivots),
            cluster_type=PivotType.LOW,
            std_deviation=Decimal("0"),
            timestamp_range=(support_pivots[0].timestamp, support_pivots[-1].timestamp),
        )

        # Create Creek level (support) at range low with all required fields
        creek = CreekLevel(
            price=range_low,
            absolute_low=range_low,
            min_rally_height_pct=Decimal("2.0"),
            bars_since_formation=len(lookback_bars),
            touch_count=2,  # Minimum 2 touches required
            touch_details=[],
            strength_score=50,  # Neutral strength
            strength_rating="MODERATE",
            last_test_timestamp=lookback_bars[-1].timestamp,
            first_test_timestamp=lookback_bars[0].timestamp,
            hold_duration=len(lookback_bars),
            confidence="MEDIUM",
            volume_trend="FLAT",
        )

        # Create trading range with all required fields
        return TradingRange(
            symbol=self.symbol,
            timeframe=self.current_timeframe,
            support_cluster=support_cluster,
            resistance_cluster=resistance_cluster,
            support=range_low,
            resistance=range_high,
            midpoint=midpoint,
            range_width=range_width,
            range_width_pct=max(range_width_pct, Decimal("0.03")),  # Ensure minimum 3%
            start_index=max(0, current_index - 50),
            end_index=current_index,
            duration=max(len(lookback_bars), 10),  # Ensure minimum 10 bars
            creek=creek,
            status=RangeStatus.ACTIVE,
        )

    def _detect_volume_divergence(self, bars: list[OHLCVBar], context: dict) -> bool:
        """
        Detect volume divergence (new price highs with declining volume).

        FR6.3: Volume divergence detection for exit signals.

        Args:
            bars: Historical bars
            context: Strategy context with volume analysis

        Returns:
            True if 2+ consecutive divergences detected, False otherwise

        Logic:
            - Track last 5 price highs and their volumes
            - Count consecutive new highs with lower volume
            - 2+ divergences = distribution signal (exit)
        """
        if "divergence_tracking" not in context:
            context["divergence_tracking"] = []

        # Need at least 10 bars for analysis
        if len(bars) < 10:
            return False

        # Track price highs and volumes
        tracking = context["divergence_tracking"]
        current_bar = bars[-1]

        # Check if current bar is a new high (higher than last 5 bars)
        recent_highs = [b.high for b in bars[-6:-1]] if len(bars) >= 6 else []
        if not recent_highs:
            return False

        is_new_high = current_bar.high > max(recent_highs)

        if is_new_high:
            # Get current volume ratio
            current_volume_ratio = (
                context["volume_analysis"]
                .get(current_bar.timestamp, {})
                .get("volume_ratio", Decimal("1.0"))
            )

            # Add to tracking list
            tracking.append({"price": current_bar.high, "volume_ratio": current_volume_ratio})

            # Keep only last 5 highs
            if len(tracking) > 5:
                tracking.pop(0)

            # Count consecutive divergences
            divergence_count = 0
            for i in range(1, len(tracking)):
                if (
                    tracking[i]["price"] > tracking[i - 1]["price"]
                    and tracking[i]["volume_ratio"] < tracking[i - 1]["volume_ratio"]
                ):
                    divergence_count += 1

            # 2+ consecutive divergences = distribution signal
            if divergence_count >= 2:
                return True

        return False

    def _wyckoff_exit_logic(
        self,
        bar: OHLCVBar,
        context: dict,
        active_campaigns: list,
    ) -> tuple[bool, str]:
        """
        Wyckoff-based exit logic with multi-tier priority.

        FR6.2-FR6.6: Multi-tier exit strategy with structural signals.

        Args:
            bar: Current bar
            context: Strategy context
            active_campaigns: List of active campaigns

        Returns:
            Tuple (should_exit: bool, exit_reason: str)

        Exit Priority (Story 13.6 FR6.5):
            1. Support Invalidation (Creek break) - FAILED pattern
            2. Jump Level Target - PROFIT TARGET
            3. UTAD (Phase E completion) - DISTRIBUTION
            4. Volume Divergence - DISTRIBUTION
            5. Time Limit (50 bars) - SAFETY

        Educational Note:
            Wyckoff exits focus on structural signals (Jump, UTAD, divergence)
            rather than arbitrary percentages. The pattern tells us when to exit.
        """
        if not context["position"] or not context["entry_price"]:
            return (False, "NO_POSITION")

        if not active_campaigns:
            return (False, "NO_ACTIVE_CAMPAIGN")

        campaign = active_campaigns[0]  # Primary campaign
        bars_list = context["bars"]
        current_index = len(bars_list) - 1

        # FR6.4: Priority 1 - Support Invalidation (Creek break)
        if campaign.support_level and bar.close < campaign.support_level:
            return (
                True,
                f"SUPPORT_BREAK (close ${bar.close} < Creek ${campaign.support_level})",
            )

        # FR6.1: Priority 2 - Jump Level Target (measured move)
        if campaign.jump_level and bar.high >= campaign.jump_level:
            return (True, f"JUMP_LEVEL_HIT (high ${bar.high} >= Jump ${campaign.jump_level})")

        # FR6.2: Priority 3 - UTAD (Phase E completion signal)
        if campaign.resistance_level:
            from src.pattern_engine.detectors.utad_detector import UTADDetector

            utad_detector = UTADDetector(max_penetration_pct=Decimal("5.0"))

            # Build minimal trading range for UTAD detection
            trading_range = self._build_trading_range(bars_list, current_index)

            utad = utad_detector.detect_utad(
                trading_range=trading_range,
                bars=bars_list[max(0, current_index - 50) : current_index + 1],
                ice_level=campaign.resistance_level,
            )

            if utad and utad.confidence >= 70:
                return (
                    True,
                    f"UTAD_DETECTED (penetration {utad.penetration_pct:.2f}%, "
                    f"volume {utad.volume_ratio:.2f}x, confidence {utad.confidence})",
                )

        # FR6.3: Priority 4 - Volume Divergence (distribution signal)
        if self._detect_volume_divergence(bars_list, context):
            return (True, "VOLUME_DIVERGENCE (2+ consecutive new highs with declining volume)")

        # Priority 5 - Time Limit (safety backstop)
        bars_in_position = current_index - context.get("entry_bar_index", current_index)
        if bars_in_position >= 50:
            return (True, f"TIME_LIMIT ({bars_in_position} bars in position)")

        return (False, "HOLD")

    def _print_exit_analysis(self, trades: list) -> None:
        """
        Print exit reason analysis for educational purposes.

        FR6.7: Exit reason tracking and reporting.

        Args:
            trades: List of completed trades with exit metadata

        Output:
            - Exit reason distribution (count and percentage)
            - Average profit per exit reason
            - Educational insights on Wyckoff exit effectiveness
        """
        if not trades:
            print("\n[EXIT ANALYSIS] - No trades to analyze")
            return

        print("\n" + "=" * 60)
        print("[EXIT ANALYSIS] - Wyckoff Exit Performance")
        print("=" * 60)

        # Count exit reasons
        exit_reasons = {}
        exit_profits = {}

        for trade in trades:
            reason = getattr(trade, "exit_reason", "UNKNOWN")
            profit_pct = ((trade.exit_price - trade.entry_price) / trade.entry_price) * 100

            if reason not in exit_reasons:
                exit_reasons[reason] = 0
                exit_profits[reason] = []

            exit_reasons[reason] += 1
            exit_profits[reason].append(profit_pct)

        # Print distribution
        total_trades = len(trades)
        print(f"\nTotal Exits: {total_trades}\n")
        print(f"{'Exit Reason':<40} {'Count':<8} {'%':<8} {'Avg Profit %':<12}")
        print("-" * 70)

        for reason in sorted(exit_reasons.keys()):
            count = exit_reasons[reason]
            pct = (count / total_trades) * 100
            avg_profit = sum(exit_profits[reason]) / len(exit_profits[reason])

            print(f"{reason:<40} {count:<8} {pct:<7.1f}% {avg_profit:>+11.2f}%")

        # Educational insights
        print("\n" + "=" * 60)
        print("[EDUCATIONAL INSIGHTS]")
        print("=" * 60)

        jump_exits = exit_reasons.get("JUMP_LEVEL_HIT", 0) + sum(
            v for k, v in exit_reasons.items() if "JUMP" in k
        )
        utad_exits = sum(v for k, v in exit_reasons.items() if "UTAD" in k)
        divergence_exits = sum(v for k, v in exit_reasons.items() if "DIVERGENCE" in k)
        support_breaks = sum(v for k, v in exit_reasons.items() if "SUPPORT" in k)

        structural_exits = jump_exits + utad_exits + divergence_exits
        structural_pct = (structural_exits / total_trades) * 100

        print(f"\nStructural Exits (Jump/UTAD/Divergence): {structural_pct:.1f}%")
        print(f"  - Jump Level: {jump_exits} exits")
        print(f"  - UTAD: {utad_exits} exits")
        print(f"  - Volume Divergence: {divergence_exits} exits")
        print(f"\nSupport Invalidations: {support_breaks} exits")
        print(
            f"\nWyckoff Principle: {structural_pct:.1f}% of exits were based on "
            f"market structure, not arbitrary stops."
        )

    def _print_campaign_summary(self, timeframe: str):
        """
        Print comprehensive campaign analysis after backtest.

        Shows:
        - Total campaigns detected
        - Completion/failure rates
        - Pattern distribution (Springs, SOS, LPS counts)
        - Session distribution (for intraday timeframes)
        - Average campaign metrics
        """
        if not self.campaign_detector:
            return

        all_campaigns = self.campaign_detector.campaigns

        if not all_campaigns:
            print("\n[CAMPAIGN ANALYSIS] - No campaigns detected")
            return

        from src.backtesting.intraday_campaign_detector import CampaignState

        completed = [c for c in all_campaigns if c.state == CampaignState.COMPLETED]
        failed = [c for c in all_campaigns if c.state == CampaignState.FAILED]
        active = [c for c in all_campaigns if c.state == CampaignState.ACTIVE]
        forming = [c for c in all_campaigns if c.state == CampaignState.FORMING]

        print(f"\n[CAMPAIGN ANALYSIS] - {timeframe}")
        print(f"  Total Campaigns: {len(all_campaigns)}")

        if len(all_campaigns) > 0:
            print(f"  Completed: {len(completed)} ({len(completed)/len(all_campaigns)*100:.1f}%)")
            print(f"  Failed: {len(failed)} ({len(failed)/len(all_campaigns)*100:.1f}%)")
            print(f"  Active: {len(active)} ({len(active)/len(all_campaigns)*100:.1f}%)")
            print(f"  Forming: {len(forming)} ({len(forming)/len(all_campaigns)*100:.1f}%)")

        # Pattern distribution
        all_patterns = [p for c in all_campaigns for p in c.patterns]

        if all_patterns:
            from src.models.lps import LPS
            from src.models.sos_breakout import SOSBreakout
            from src.models.spring import Spring

            springs = [p for p in all_patterns if isinstance(p, Spring)]
            soss = [p for p in all_patterns if isinstance(p, SOSBreakout)]
            lpss = [p for p in all_patterns if isinstance(p, LPS)]

            print("\n  Pattern Quality:")
            print(f"    - Springs: {len(springs)} detected")
            print(f"    - SOS: {len(soss)} detected")
            print(f"    - LPS: {len(lpss)} detected")

            # Session distribution (if intraday)
            if timeframe in ["1m", "5m", "15m", "1h"]:
                sessions = {}
                for pattern in all_patterns:
                    session = get_forex_session(pattern.timestamp)
                    session_name = session.name if hasattr(session, "name") else str(session)
                    sessions[session_name] = sessions.get(session_name, 0) + 1

                if sessions:
                    print("\n  Session Distribution:")
                    for session_name, count in sorted(
                        sessions.items(), key=lambda x: x[1], reverse=True
                    ):
                        pct = count / len(all_patterns) * 100
                        print(f"    - {session_name}: {count} patterns ({pct:.1f}%)")

        # Campaign strength metrics
        if completed:
            avg_patterns = sum(len(c.patterns) for c in completed) / len(completed)
            avg_strength = sum(c.strength_score for c in completed) / len(completed)

            print("\n  Campaign Metrics (Completed):")
            print(f"    - Avg Patterns/Campaign: {avg_patterns:.1f}")
            print(f"    - Avg Strength Score: {avg_strength:.2f}")

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

        # Print enhanced campaign summary
        self._print_campaign_summary(timeframe)

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
