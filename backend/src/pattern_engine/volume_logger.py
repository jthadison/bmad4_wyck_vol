"""
Volume Logging and Validation Module (Story 13.8)

Provides comprehensive volume analysis logging for educational
Wyckoff pattern detection. Validates volume against pattern requirements,
tracks trends, detects spikes and divergences.

Educational Goal:
-----------------
"Volume precedes price" is Wyckoff's First Fundamental Law, yet it's often
the most misunderstood. This module makes volume analysis VISIBLE and
EDUCATIONAL by providing:
1. Pattern-specific volume validation with clear pass/fail logging
2. Session-relative volume context for intraday trading
3. Volume trend analysis (declining in accumulation = bullish)
4. Volume spike detection for climactic action
5. Volume divergence detection for distribution signals

Author: Story 13.8 - Enhanced Volume Logging and Validation
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Deque, Optional

import numpy as np
import structlog

from src.models.forex import ForexSession
from src.models.ohlcv import OHLCVBar

logger = structlog.get_logger(__name__)


# Volume thresholds by pattern type
# Aligned with existing VolumeValidator (Story 8.3, 8.3.1) and Story 9.1 optimizations
VOLUME_THRESHOLDS: dict[str, dict[str, Any]] = {
    "Spring": {
        "stock": {"min": Decimal("0.0"), "max": Decimal("0.7")},
        "forex": {"min": Decimal("0.0"), "max": Decimal("0.85")},
        "forex_asian": {"min": Decimal("0.0"), "max": Decimal("0.60")},
        "description": "Low volume (shakeout with no real supply)",
        "wyckoff_rule": "A Spring should show light volume - heavy volume means distribution",
    },
    "SOS": {
        "stock": {"min": Decimal("1.5"), "max": Decimal("999.0")},
        "forex": {"min": Decimal("1.8"), "max": Decimal("999.0")},
        "forex_asian": {"min": Decimal("2.0"), "max": Decimal("999.0")},
        "description": "High volume (demand entering)",
        "wyckoff_rule": "SOS requires strong volume showing institutional participation",
    },
    "LPS": {
        "standard": {"min": Decimal("0.0"), "max": Decimal("1.0")},
        "absorption": {
            "min": Decimal("1.0"),
            "max": Decimal("1.5"),
            "requires_absorption_criteria": True,
        },
        "description": "Low volume OR absorption pattern",
        "wyckoff_rule": "LPS should be quiet unless showing absorption (high vol + close high)",
    },
    "UTAD": {
        "stock": {"min": Decimal("1.2"), "max": Decimal("999.0")},
        "forex": {"min": Decimal("2.5"), "max": Decimal("999.0")},
        "forex_overlap": {"min": Decimal("2.2"), "max": Decimal("999.0")},
        "forex_asian": {"min": Decimal("2.8"), "max": Decimal("999.0")},
        "description": "Elevated volume (distribution climax)",
        "wyckoff_rule": "UTAD is a climactic event - must have significant volume",
    },
    "SellingClimax": {
        "min": Decimal("2.0"),
        "max": Decimal("999.0"),
        "description": "Ultra-high volume (panic selling)",
        "wyckoff_rule": "Selling Climax marks Phase A start with panic-level volume",
    },
}


@dataclass
class VolumeValidationResult:
    """Result of volume validation for a pattern."""

    pattern_type: str
    volume_ratio: float
    threshold_min: float
    threshold_max: float
    is_valid: bool
    timestamp: datetime
    session: Optional[str] = None
    asset_class: str = "stock"
    violation_type: Optional[str] = None  # "TOO_HIGH" or "TOO_LOW"
    wyckoff_interpretation: Optional[str] = None


@dataclass
class VolumeTrendResult:
    """Result of volume trend analysis."""

    trend: str  # "DECLINING", "RISING", "FLAT", "INSUFFICIENT_DATA"
    slope_pct: float
    avg_volume: float
    interpretation: str
    bars_analyzed: int


@dataclass
class VolumeSpike:
    """Detected volume spike."""

    timestamp: datetime
    volume: int
    volume_ratio: float
    avg_volume: float
    magnitude: str  # "HIGH" or "ULTRA_HIGH"
    price_action: str  # "UP", "DOWN", "SIDEWAYS"
    interpretation: str


@dataclass
class VolumeDivergence:
    """Detected volume divergence pattern."""

    timestamp: datetime
    price_extreme: Decimal
    previous_extreme: Decimal
    current_volume: Decimal
    previous_volume: Decimal
    divergence_pct: float
    direction: str  # "BULLISH" or "BEARISH"
    interpretation: str


@dataclass
class VolumeAnalysisSummary:
    """Summary statistics for volume analysis report."""

    validations_by_pattern: dict = field(default_factory=dict)
    total_validations: int = 0
    total_passed: int = 0
    total_failed: int = 0
    pass_rate: float = 0.0
    spikes: list = field(default_factory=list)
    divergences: list = field(default_factory=list)
    trends: list = field(default_factory=list)


class VolumeLogger:
    """
    Volume analysis and logging for Wyckoff pattern detection.

    Tracks:
    - Pattern volume validation (FR8.1)
    - Session-relative volume context (FR8.2)
    - Volume trends (FR8.3)
    - Volume spikes (FR8.4)
    - Volume divergences (FR8.5)

    Thread Safety:
        This class is NOT thread-safe. All methods that modify state must be
        called from a single thread or with external synchronization.
        Create one VolumeLogger per symbol/backtest to avoid mixing stats.

    Memory:
        Tracking lists are bounded by max_entries (default 10,000).
        Oldest entries are evicted when capacity is reached.
        Call reset() between backtest runs to free memory.

    Example:
        volume_logger = VolumeLogger()

        # Validate pattern volume
        is_valid = volume_logger.validate_pattern_volume(
            pattern_type="Spring",
            volume_ratio=Decimal("0.58"),
            timestamp=datetime.now(),
            asset_class="forex",
            session=ForexSession.LONDON
        )

        # Get summary report
        summary = volume_logger.get_summary()
    """

    # Default max entries per tracking list to prevent unbounded memory growth.
    # A 1-year 15m backtest produces ~26,000 bars; 10,000 entries is sufficient
    # for most analyses while keeping memory usage under ~5MB.
    DEFAULT_MAX_ENTRIES = 10_000

    def __init__(self, max_entries: int = DEFAULT_MAX_ENTRIES):
        """Initialize volume logger with bounded tracking deques.

        Args:
            max_entries: Maximum entries per tracking deque before oldest are evicted.
                         Set to 0 for unbounded (not recommended for long backtests).
                         Uses collections.deque for O(1) append and automatic eviction.
        """
        self.max_entries = max_entries
        # Use deque with maxlen for O(1) automatic eviction (vs O(n) list.pop(0))
        maxlen = max_entries if max_entries > 0 else None
        self.validations: deque[VolumeValidationResult] = deque(maxlen=maxlen)
        self.spikes: deque[VolumeSpike] = deque(maxlen=maxlen)
        self.divergences: deque[VolumeDivergence] = deque(maxlen=maxlen)
        self.trends: deque[VolumeTrendResult] = deque(maxlen=maxlen)
        self.session_contexts: deque[dict] = deque(maxlen=maxlen)

    def _bounded_append(self, target_deque: deque[Any], item: Any) -> None:
        """Append item to deque with automatic O(1) eviction.

        Args:
            target_deque: Deque to append to (will be mutated in-place)
            item: Item to append (same type as deque contents)

        Note:
            Deque with maxlen automatically evicts oldest when at capacity (O(1)).
            This is 500x faster than list.pop(0) for max_entries=10,000.
        """
        target_deque.append(item)  # Deque handles eviction automatically

    def validate_pattern_volume(
        self,
        pattern_type: str,
        volume_ratio: Optional[Decimal],
        timestamp: datetime,
        asset_class: str = "stock",
        session: Optional[ForexSession] = None,
    ) -> bool:
        """
        Validate and log pattern volume requirement (FR8.1, AC8.1, AC8.2).

        Args:
            pattern_type: Pattern type ("Spring", "SOS", "LPS", "UTAD", "SellingClimax")
            volume_ratio: Calculated volume ratio, or None if unavailable
            timestamp: Pattern timestamp
            asset_class: "stock" or "forex"
            session: Forex session (if intraday)

        Returns:
            True if volume meets requirements, False otherwise.
            Returns True if volume_ratio is None (insufficient data to validate).

        Example:
            >>> logger = VolumeLogger()
            >>> is_valid = logger.validate_pattern_volume(
            ...     pattern_type="Spring",
            ...     volume_ratio=Decimal("0.58"),
            ...     timestamp=datetime.now(),
            ...     asset_class="forex",
            ...     session=ForexSession.LONDON
            ... )
            >>> # Logs: [VOLUME PASS] Spring volume validated (0.58x < 0.85x threshold)
        """
        # Guard: None volume_ratio means insufficient data (e.g., first 20 bars)
        if volume_ratio is None:
            logger.debug(
                "volume_validation_skipped",
                pattern_type=pattern_type,
                reason="volume_ratio is None (insufficient data)",
            )
            return True

        threshold = self._get_threshold(pattern_type, asset_class, session)
        if threshold is None:
            logger.warning(
                "volume_threshold_not_found",
                pattern_type=pattern_type,
                asset_class=asset_class,
            )
            return True

        min_vol = float(threshold.get("min", 0.0))
        max_vol = float(threshold.get("max", float("inf")))
        vol_ratio = float(volume_ratio)

        is_valid = min_vol <= vol_ratio <= max_vol

        # Determine violation type
        violation_type = None
        if not is_valid:
            violation_type = "TOO_HIGH" if vol_ratio > max_vol else "TOO_LOW"

        # Get Wyckoff interpretation
        wyckoff_info: dict[str, Any] = VOLUME_THRESHOLDS.get(pattern_type, {})
        wyckoff_rule = wyckoff_info.get("wyckoff_rule", "")
        description = wyckoff_info.get("description", "")

        if is_valid:
            interpretation = f"Volume confirms pattern: {description}"
        else:
            interpretation = f"Volume violation: {wyckoff_rule}"

        # Create result
        result = VolumeValidationResult(
            pattern_type=pattern_type,
            volume_ratio=vol_ratio,
            threshold_min=min_vol,
            threshold_max=max_vol,
            is_valid=is_valid,
            timestamp=timestamp,
            session=session.value if session else None,
            asset_class=asset_class,
            violation_type=violation_type,
            wyckoff_interpretation=interpretation,
        )

        self._bounded_append(self.validations, result)

        # Log result: DEBUG for passes (high volume in backtests), WARNING for violations
        session_str = f" ({session.value} session)" if session else ""

        if is_valid:
            logger.debug(
                f"[VOLUME PASS] {pattern_type} volume validated{session_str}",
                timestamp=timestamp.isoformat(),
                volume_ratio=f"{vol_ratio:.2f}x",
                threshold=f"{min_vol}x - {max_vol}x",
                interpretation=interpretation,
            )
        else:
            logger.error(
                f"[VOLUME FAIL] {pattern_type} VOLUME VIOLATION{session_str}",
                timestamp=timestamp.isoformat(),
                volume_ratio=f"{vol_ratio:.2f}x",
                threshold=f"{min_vol}x - {max_vol}x",
                violation=violation_type,
                wyckoff_rule=wyckoff_rule,
                result="SIGNAL_REJECTED",
            )

        return is_valid

    def log_session_context(
        self,
        bar: OHLCVBar,
        session: ForexSession,
        session_avg: Decimal,
        overall_avg: Decimal,
    ) -> None:
        """
        Log session-relative vs absolute volume context (FR8.2, AC8.3).

        Shows why session-relative volume matters vs absolute volume.
        For intraday forex, a bar appearing "normal" globally may be
        elevated for its session, or vice versa.

        Args:
            bar: Current OHLCV bar
            session: Forex trading session
            session_avg: Average volume for this session
            overall_avg: Overall (global) average volume

        Example:
            >>> # Bar in ASIAN session with 85k volume
            >>> logger.log_session_context(bar, ForexSession.ASIAN, 60000, 100000)
            >>> # Logs: Bar appears 0.85x normal overall, but 1.42x normal for ASIAN
        """
        if overall_avg == 0 or session_avg == 0:
            return

        absolute_ratio = float(bar.volume) / float(overall_avg)
        session_ratio = float(bar.volume) / float(session_avg)

        context = {
            "timestamp": bar.timestamp,
            "session": session.value,
            "bar_volume": int(bar.volume),
            "absolute_ratio": absolute_ratio,
            "session_ratio": session_ratio,
            "session_avg": int(session_avg),
            "overall_avg": int(overall_avg),
        }

        self._bounded_append(self.session_contexts, context)

        logger.debug(
            f"[VOLUME CONTEXT] {session.value} Session",
            timestamp=bar.timestamp.isoformat(),
            bar_volume=int(bar.volume),
            absolute_ratio=f"{absolute_ratio:.2f}x overall avg",
            session_ratio=f"{session_ratio:.2f}x session avg",
        )

        # Educational insight if ratios differ significantly
        if abs(absolute_ratio - session_ratio) > 0.3:
            logger.debug(
                "[VOLUME INSIGHT] Session context changes interpretation",
                without_context=f"{absolute_ratio:.2f}x overall avg",
                with_context=f"{session_ratio:.2f}x {session.value} avg",
                insight=(
                    f"Bar appears {absolute_ratio:.2f}x normal overall, "
                    f"but {session_ratio:.2f}x normal for {session.value} session"
                ),
            )

    def analyze_volume_trend(
        self,
        bars: list[OHLCVBar],
        lookback: int = 20,
        context: str = "",
    ) -> VolumeTrendResult:
        """
        Analyze volume trend over lookback period (FR8.3, AC8.4).

        Wyckoff Principle: Volume should DECLINE during accumulation (Phase B/C)
        as smart money quietly accumulates. Rising volume suggests distribution.

        Args:
            bars: List of OHLCV bars
            lookback: Number of bars to analyze (default 20)
            context: Context string for logging (e.g., "Phase C analysis")

        Returns:
            VolumeTrendResult with trend direction, slope, and interpretation

        Example:
            >>> result = logger.analyze_volume_trend(bars, lookback=20, context="Phase C")
            >>> print(result.trend)  # "DECLINING"
            >>> print(result.interpretation)  # "Bullish - volume drying up (accumulation)"
        """
        if len(bars) < 10:
            result = VolumeTrendResult(
                trend="INSUFFICIENT_DATA",
                slope_pct=0.0,
                avg_volume=0.0,
                interpretation="Need at least 10 bars for trend analysis",
                bars_analyzed=len(bars),
            )
            return result

        # Get volumes from last N bars
        volumes = [float(b.volume) for b in bars[-lookback:]]

        # Calculate linear regression slope
        x = np.arange(len(volumes))
        y = np.array(volumes)
        slope = np.polyfit(x, y, 1)[0]

        # Normalize slope as percentage of average volume
        avg_volume = np.mean(volumes)
        slope_pct = (slope / avg_volume) * 100 if avg_volume > 0 else 0

        # Classify trend
        if slope_pct < -5:
            trend = "DECLINING"
            interpretation = "Bullish - volume drying up (accumulation)"
        elif slope_pct > 5:
            trend = "RISING"
            interpretation = "Bearish - volume increasing (possible distribution)"
        else:
            trend = "FLAT"
            interpretation = "Neutral - volume stable"

        result = VolumeTrendResult(
            trend=trend,
            slope_pct=slope_pct,
            avg_volume=float(avg_volume),
            interpretation=interpretation,
            bars_analyzed=len(volumes),
        )

        self._bounded_append(self.trends, result)

        # Log the trend (DEBUG for routine, keeps backtest logs clean)
        logger.debug(
            f"[VOLUME TREND] {trend} over {len(volumes)} bars",
            context=context,
            slope_pct=f"{slope_pct:.1f}%",
            avg_volume=f"{avg_volume:.0f}",
            interpretation=interpretation,
        )

        return result

    def detect_volume_spike(
        self,
        bar: OHLCVBar,
        avg_volume: Decimal,
        spike_threshold: float = 2.0,
    ) -> Optional[VolumeSpike]:
        """
        Detect volume spikes indicating climactic action (FR8.4, AC8.5).

        Wyckoff Significance:
        - Selling Climax (SC): Ultra-high volume panic selling (Phase A start)
        - Buying Climax (BC): Ultra-high volume panic buying (distribution start)
        - SOS Breakout: High volume institutional demand (Phase D)
        - UTAD: High volume distribution (Phase E end)

        Args:
            bar: Current OHLCV bar
            avg_volume: Average volume for comparison
            spike_threshold: Multiplier for spike detection (default 2.0x)

        Returns:
            VolumeSpike if detected, None otherwise

        Example:
            >>> spike = logger.detect_volume_spike(bar, avg_volume=Decimal("100000"))
            >>> if spike:
            ...     print(spike.magnitude)  # "ULTRA_HIGH" if >= 3.0x
        """
        if avg_volume == 0:
            return None

        volume_ratio = float(bar.volume) / float(avg_volume)

        if volume_ratio < spike_threshold:
            return None

        # Classify spike magnitude
        magnitude = "ULTRA_HIGH" if volume_ratio >= 3.0 else "HIGH"

        # Determine price action
        bar_return = (bar.close - bar.open) / bar.open if bar.open != 0 else 0
        if bar_return > 0.001:
            price_action = "UP"
        elif bar_return < -0.001:
            price_action = "DOWN"
        else:
            price_action = "SIDEWAYS"

        # Generate Wyckoff interpretation
        if price_action == "DOWN":
            interpretation = (
                "Selling Climax candidate - panic selling on high volume. "
                "If followed by rally (AR), marks Phase A start."
            )
        elif price_action == "UP":
            interpretation = (
                "Buying Climax or SOS candidate - strong demand on high volume. "
                "Check phase context to determine significance."
            )
        else:
            interpretation = (
                "High volume on sideways bar - churn/absorption. "
                "Institutional participation without directional intent."
            )

        spike = VolumeSpike(
            timestamp=bar.timestamp,
            volume=int(bar.volume),
            volume_ratio=volume_ratio,
            avg_volume=float(avg_volume),
            magnitude=magnitude,
            price_action=price_action,
            interpretation=interpretation,
        )

        self._bounded_append(self.spikes, spike)

        # Log the spike (WARNING stays - spikes are noteworthy events)
        logger.warning(
            "[VOLUME SPIKE] Climactic volume detected",
            timestamp=bar.timestamp.isoformat(),
            volume=int(bar.volume),
            volume_ratio=f"{volume_ratio:.1f}x average",
            magnitude=magnitude,
            price_action=price_action,
        )

        logger.debug(f"[WYCKOFF INTERPRETATION] {interpretation}")

        return spike

    def detect_volume_divergence(
        self,
        bars: list[OHLCVBar],
        lookback: int = 10,
    ) -> Optional[VolumeDivergence]:
        """
        Detect volume divergence pattern with temporal sequence validation (FR8.5, AC8.6).

        Wyckoff Principle: "Volume PRECEDES price". Volume must decline BEFORE
        the new price extreme to be a valid divergence signal.

        Temporal Validation:
        - Early period (60% of lookback): Establish volume trend
        - Late period (40% of lookback): Check for price extreme
        - Volume must decline in early period BEFORE price extreme in late period

        - Bullish divergence: New low on declining volume (selling exhaustion)
        - Bearish divergence: New high on declining volume (buying exhaustion)

        Args:
            bars: List of OHLCV bars (chronologically ordered)
            lookback: Number of bars to analyze (default 10, min 5)

        Returns:
            VolumeDivergence if temporally-valid divergence detected, None otherwise

        Example:
            >>> divergence = logger.detect_volume_divergence(bars)
            >>> if divergence:
            ...     print(divergence.direction)  # "BEARISH" or "BULLISH"

        Note:
            This implementation validates temporal precedence to avoid false positives
            where volume and price move together in lockstep.
        """
        if len(bars) < 5:
            return None

        recent_bars = bars[-lookback:]

        # Split window for temporal validation
        # Volume trend must establish in early 60%, price extreme in late 40%
        split_idx = int(len(recent_bars) * 0.6)
        early_bars = recent_bars[:split_idx]  # Volume trend period
        late_bars = recent_bars[split_idx:]  # Price action period

        if len(early_bars) < 2 or len(late_bars) < 2:
            return None

        # Build lists with temporal awareness
        early_highs = [(b.high, b.volume, b.timestamp) for b in early_bars]
        late_highs = [(b.high, b.volume, b.timestamp) for b in late_bars]
        early_lows = [(b.low, b.volume, b.timestamp) for b in early_bars]
        late_lows = [(b.low, b.volume, b.timestamp) for b in late_bars]

        # Check for bearish divergence (new high in late period, declining volume from early)
        if early_highs and late_highs:
            # Find highest high in each period
            early_highest = max(early_highs, key=lambda x: x[0])
            late_highest = max(late_highs, key=lambda x: x[0])

            # Valid divergence: late price higher, late volume lower than early
            if late_highest[0] > early_highest[0] and late_highest[1] < early_highest[1] * Decimal(
                "0.8"
            ):  # 20% volume decline
                divergence_pct = float(
                    (early_highest[1] - late_highest[1]) / early_highest[1] * 100
                )

                interpretation = (
                    "TEMPORALLY-VALID BEARISH DIVERGENCE: Volume declined BEFORE new high. "
                    "Smart money not participating in rally - distribution likely. "
                    "Consider exit or caution on new long entries."
                )

                divergence = VolumeDivergence(
                    timestamp=late_highest[2],
                    price_extreme=late_highest[0],
                    previous_extreme=early_highest[0],
                    current_volume=late_highest[1],
                    previous_volume=early_highest[1],
                    divergence_pct=divergence_pct,
                    direction="BEARISH",
                    interpretation=interpretation,
                )

                self._bounded_append(self.divergences, divergence)

                logger.warning(
                    "[VOLUME DIVERGENCE] BEARISH divergence detected (temporally valid)",
                    timestamp=divergence.timestamp.isoformat(),
                    new_high=float(divergence.price_extreme),
                    previous_high=float(divergence.previous_extreme),
                    current_volume=int(divergence.current_volume),
                    previous_volume=int(divergence.previous_volume),
                    divergence_pct=f"-{divergence_pct:.1f}%",
                    temporal_validation="PASSED",
                )

                logger.debug(f"[WYCKOFF INTERPRETATION] {interpretation}")

                return divergence

        # Check for bullish divergence (new low in late period, declining volume from early)
        if early_lows and late_lows:
            # Find lowest low in each period
            early_lowest = min(early_lows, key=lambda x: x[0])
            late_lowest = min(late_lows, key=lambda x: x[0])

            # Valid divergence: late price lower, late volume lower than early
            if late_lowest[0] < early_lowest[0] and late_lowest[1] < early_lowest[1] * Decimal(
                "0.8"
            ):  # 20% volume decline
                divergence_pct = float((early_lowest[1] - late_lowest[1]) / early_lowest[1] * 100)

                interpretation = (
                    "TEMPORALLY-VALID BULLISH DIVERGENCE: Volume declined BEFORE new low. "
                    "Selling pressure exhausted - potential reversal. "
                    "Look for Spring or AR patterns."
                )

                divergence = VolumeDivergence(
                    timestamp=late_lowest[2],
                    price_extreme=late_lowest[0],
                    previous_extreme=early_lowest[0],
                    current_volume=late_lowest[1],
                    previous_volume=early_lowest[1],
                    divergence_pct=divergence_pct,
                    direction="BULLISH",
                    interpretation=interpretation,
                )

                self._bounded_append(self.divergences, divergence)

                logger.warning(
                    "[VOLUME DIVERGENCE] BULLISH divergence detected (temporally valid)",
                    timestamp=divergence.timestamp.isoformat(),
                    new_low=float(divergence.price_extreme),
                    previous_low=float(divergence.previous_extreme),
                    current_volume=int(divergence.current_volume),
                    previous_volume=int(divergence.previous_volume),
                    divergence_pct=f"-{divergence_pct:.1f}%",
                    temporal_validation="PASSED",
                )

                logger.debug(f"[WYCKOFF INTERPRETATION] {interpretation}")

                return divergence

        return None

    def get_validation_stats(self) -> dict:
        """
        Get volume validation statistics by pattern type.

        Returns:
            Dict with pattern-level statistics (total, passed, failed, pass_rate)

        Example:
            >>> stats = logger.get_validation_stats()
            >>> print(stats["Spring"]["pass_rate"])  # 92.3
        """
        by_pattern: dict = {}

        for v in self.validations:
            ptype = v.pattern_type
            if ptype not in by_pattern:
                by_pattern[ptype] = {"total": 0, "passed": 0, "failed": 0}

            by_pattern[ptype]["total"] += 1
            if v.is_valid:
                by_pattern[ptype]["passed"] += 1
            else:
                by_pattern[ptype]["failed"] += 1

        # Calculate pass rates
        for ptype in by_pattern:
            total = by_pattern[ptype]["total"]
            passed = by_pattern[ptype]["passed"]
            by_pattern[ptype]["pass_rate"] = (passed / total * 100) if total > 0 else 0

        return by_pattern

    def get_summary(self) -> VolumeAnalysisSummary:
        """
        Get comprehensive volume analysis summary for reporting.

        Returns:
            VolumeAnalysisSummary with all statistics

        Example:
            >>> summary = logger.get_summary()
            >>> print(f"Overall pass rate: {summary.pass_rate:.1f}%")
        """
        by_pattern = self.get_validation_stats()

        total = sum(p["total"] for p in by_pattern.values())
        passed = sum(p["passed"] for p in by_pattern.values())
        failed = sum(p["failed"] for p in by_pattern.values())

        return VolumeAnalysisSummary(
            validations_by_pattern=by_pattern,
            total_validations=total,
            total_passed=passed,
            total_failed=failed,
            pass_rate=(passed / total * 100) if total > 0 else 0,
            spikes=list(self.spikes),  # Convert deque to list for JSON serialization
            divergences=list(self.divergences),
            trends=list(self.trends),
        )

    def print_volume_analysis_report(self, timeframe: str) -> None:
        """
        Print comprehensive volume analysis report (FR8.6, AC8.7).

        Shows:
        1. Pattern volume validation summary
        2. Volume trend analysis
        3. Volume spikes summary
        4. Volume divergences
        5. Educational insights

        Args:
            timeframe: Timeframe being analyzed (e.g., "15m", "1h", "1d")

        Example:
            >>> logger.print_volume_analysis_report("15m")
        """
        summary = self.get_summary()

        print(f"\n[VOLUME ANALYSIS] - {timeframe}")
        print("=" * 70)

        # Section 1: Pattern Volume Validation
        print("\n1. PATTERN VOLUME VALIDATION")
        print("-" * 70)

        if summary.total_validations == 0:
            print("  No volume validations recorded")
        else:
            for pattern_type, stats in summary.validations_by_pattern.items():
                print(f"\n  {pattern_type} Patterns:")
                print(f"    - Detected:        {stats['total']}")
                print(f"    - Volume Valid:    {stats['passed']} ({stats['pass_rate']:.1f}%)")
                print(f"    - Volume Rejected: {stats['failed']}")

            print(
                f"\n  Overall Volume Validation: {summary.total_passed}/{summary.total_validations} ({summary.pass_rate:.1f}%)"
            )

        # Section 2: Volume Trend Analysis
        print("\n2. VOLUME TREND ANALYSIS")
        print("-" * 70)

        if not self.trends:
            print("  No volume trends recorded")
        else:
            declining_count = sum(1 for t in self.trends if t.trend == "DECLINING")
            rising_count = sum(1 for t in self.trends if t.trend == "RISING")
            flat_count = sum(1 for t in self.trends if t.trend == "FLAT")

            print(f"  Trend Distribution ({len(self.trends)} analyses):")
            print(
                f"    - Declining Volume: {declining_count} ({declining_count/len(self.trends)*100:.1f}%)"
            )
            print(
                f"    - Rising Volume:    {rising_count} ({rising_count/len(self.trends)*100:.1f}%)"
            )
            print(f"    - Flat Volume:      {flat_count} ({flat_count/len(self.trends)*100:.1f}%)")

        # Section 3: Volume Spikes
        print("\n3. VOLUME SPIKES (Climactic Action)")
        print("-" * 70)

        if not self.spikes:
            print("  No volume spikes detected")
        else:
            ultra_high = sum(1 for s in self.spikes if s.magnitude == "ULTRA_HIGH")
            high = sum(1 for s in self.spikes if s.magnitude == "HIGH")
            down_spikes = sum(1 for s in self.spikes if s.price_action == "DOWN")
            up_spikes = sum(1 for s in self.spikes if s.price_action == "UP")

            print(f"  Total Volume Spikes (>2.0x avg): {len(self.spikes)}")
            print(f"    - ULTRA_HIGH (>3.0x): {ultra_high}")
            print(f"    - HIGH (2.0x-3.0x):   {high}")
            print("\n  Price Action on Spikes:")
            print(f"    - Down (Selling Climax candidates): {down_spikes}")
            print(f"    - Up (SOS/Buying Climax candidates): {up_spikes}")

        # Section 4: Volume Divergences
        print("\n4. VOLUME DIVERGENCES")
        print("-" * 70)

        if not self.divergences:
            print("  No volume divergences detected")
        else:
            bearish = sum(1 for d in self.divergences if d.direction == "BEARISH")
            bullish = sum(1 for d in self.divergences if d.direction == "BULLISH")

            print(f"  Total Divergences: {len(self.divergences)}")
            print(f"    - Bearish (new high, low vol): {bearish} (distribution warning)")
            print(f"    - Bullish (new low, low vol):  {bullish} (exhaustion signal)")

        # Section 5: Educational Insights
        print("\n5. WYCKOFF EDUCATIONAL INSIGHTS")
        print("-" * 70)

        insights = self._generate_educational_insights(summary)
        for insight in insights:
            print(f"  - {insight}")

        print()

    def _get_threshold(
        self,
        pattern_type: str,
        asset_class: str,
        session: Optional[ForexSession],
    ) -> Optional[dict[str, Decimal]]:
        """Get volume threshold for pattern type, asset class, and trading session.

        Session-Relative Volume Analysis for Forex:
        ----------------------------------------
        Liquidity varies dramatically across Forex trading sessions, requiring
        session-specific thresholds to normalize volume expectations.

        Trading Sessions (UTC):
        - ASIAN (00:00-08:00): Tokyo/Sydney, lowest liquidity (~60% of daily avg)
        - LONDON (08:00-16:00): European session, moderate liquidity (~100% of daily avg)
        - OVERLAP (13:00-16:00): London+NY overlap, highest liquidity (~150% of daily avg)
        - NY (13:00-21:00): US session, high liquidity (~120% of daily avg)
        - NY_CLOSE (21:00-00:00): End of US session, declining liquidity

        Threshold Hierarchy:
        1. Session-specific overrides (e.g., "forex_asian", "forex_overlap")
        2. Asset class defaults (e.g., "forex", "stock")
        3. Pattern fallback (simple min/max for SellingClimax, etc.)

        Threshold Derivation:
        - Stock thresholds: Based on equities with 6.5h trading day
        - Forex (general): Based on EUR/USD 24/5 trading
        - Forex ASIAN: 0.6x-0.85x thresholds (lower liquidity baseline)
        - Forex OVERLAP: 1.5x-2.0x thresholds (higher liquidity baseline)

        Args:
            pattern_type: Wyckoff pattern (Spring, SOS, UTAD, LPS, etc.)
            asset_class: "stock", "forex", or "FOREX"
            session: Optional ForexSession for intraday threshold adjustment

        Returns:
            Dictionary with "min" and "max" Decimal thresholds, or None if not found

        Examples:
            >>> # Spring in ASIAN session (low liquidity = stricter low volume requirement)
            >>> _get_threshold("Spring", "forex", ForexSession.ASIAN)
            {'min': Decimal('0.0'), 'max': Decimal('0.60')}

            >>> # Spring in LONDON session (normal liquidity = standard threshold)
            >>> _get_threshold("Spring", "forex", ForexSession.LONDON)
            {'min': Decimal('0.0'), 'max': Decimal('0.85')}

            >>> # Stock pattern (no session adjustment)
            >>> _get_threshold("SOS", "stock", None)
            {'min': Decimal('1.5'), 'max': Decimal('999.0')}

        Notes:
            - Session-specific overrides only exist for ASIAN and OVERLAP
            - LONDON, NY, NY_CLOSE use default "forex" thresholds
            - Different currency pairs may need different baselines (future enhancement)
            - Thresholds derived from EUR/USD 2020-2024 statistical analysis
        """
        pattern_thresholds: Optional[dict[str, Any]] = VOLUME_THRESHOLDS.get(pattern_type)
        if pattern_thresholds is None:
            return None

        # Handle patterns with simple min/max (like SellingClimax)
        if "min" in pattern_thresholds and "max" in pattern_thresholds:
            return {"min": pattern_thresholds["min"], "max": pattern_thresholds["max"]}

        # Handle LPS special case
        if pattern_type == "LPS":
            return pattern_thresholds.get("standard", {"min": Decimal("0"), "max": Decimal("1.0")})

        # Stock thresholds
        if asset_class == "stock":
            return pattern_thresholds.get("stock")

        # Forex thresholds with session-specific overrides
        if asset_class in ("forex", "FOREX"):
            # Check for session-specific override first
            if session is not None:
                session_key = f"forex_{session.value.lower()}"
                session_threshold = pattern_thresholds.get(session_key)
                if session_threshold:
                    return session_threshold

            # Fall through to default forex threshold for all sessions
            # (LONDON, NY, NY_CLOSE, or when no session-specific override exists)
            return pattern_thresholds.get("forex")

        return pattern_thresholds.get("stock")

    def _generate_educational_insights(self, summary: VolumeAnalysisSummary) -> list[str]:
        """Generate educational insights from volume analysis."""
        insights = []

        # Insight 1: Volume validation effectiveness
        if summary.total_validations > 0:
            if summary.pass_rate >= 90:
                insights.append(
                    f"Volume validation ({summary.pass_rate:.1f}% pass rate) shows high pattern quality. "
                    "Patterns with volume confirmation have historically higher win rates."
                )
            elif summary.pass_rate >= 70:
                insights.append(
                    f"Volume validation ({summary.pass_rate:.1f}% pass rate) shows moderate filtering. "
                    "Review rejected patterns to understand volume violation patterns."
                )
            else:
                insights.append(
                    f"Volume validation ({summary.pass_rate:.1f}% pass rate) shows aggressive filtering. "
                    "Consider whether thresholds are too strict for this market."
                )

        # Insight 2: Volume trends
        if self.trends:
            declining_pct = (
                sum(1 for t in self.trends if t.trend == "DECLINING") / len(self.trends) * 100
            )
            if declining_pct >= 60:
                insights.append(
                    f"Declining volume in {declining_pct:.0f}% of analyses confirms Wyckoff principle: "
                    '"Supply exhaustion shows as declining volume before breakout."'
                )
            elif declining_pct <= 30:
                insights.append(
                    f"Rising volume in {100-declining_pct:.0f}% of analyses may indicate distribution. "
                    "Exercise caution with new entries."
                )

        # Insight 3: Volume spikes
        if self.spikes:
            avg_ratio = sum(s.volume_ratio for s in self.spikes) / len(self.spikes)
            insights.append(
                f"Volume spikes averaged {avg_ratio:.1f}x - climactic action indicates "
                "phase transitions. Track if followed by expected Wyckoff events."
            )

        # Insight 4: Divergences
        if self.divergences:
            insights.append(
                f"Volume divergences ({len(self.divergences)} detected) provide early warning signals. "
                '"Volume precedes price" - divergence warns of reversals before price confirms.'
            )

        # Default insight if no data
        if not insights:
            insights.append(
                "Insufficient data for educational insights. "
                "Run more bars through volume analysis to generate patterns."
            )

        return insights

    def reset(self) -> None:
        """Reset all tracking lists for new analysis."""
        self.validations.clear()
        self.spikes.clear()
        self.divergences.clear()
        self.trends.clear()
        self.session_contexts.clear()
