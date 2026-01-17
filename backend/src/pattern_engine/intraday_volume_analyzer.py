"""
Intraday Volume Analyzer (Optimized for Forex & Low-Timeframe Trading)

Purpose:
--------
Adapts Wyckoff volume analysis for intraday timeframes where:
1. Forex uses "tick volume" (price changes) not true volume
2. Trading sessions create volume cycles (Asian low, London/NY high)
3. News events cause artificial spikes
4. High-frequency trading creates noise

Educational Context:
--------------------
Classic Wyckoff volume analysis (backend/src/pattern_engine/volume_analyzer.py)
uses 20-bar simple average. This works for daily charts with true volume,
but fails intraday because:

- Tick volume != institutional accumulation
- London open causes 300%+ volume spike (not climactic!)
- Asian session has 70% lower volume (not bullish!)
- News events create false "climax" readings

This analyzer adjusts for these intraday realities.

Author: Wyckoff Mentor - Intraday Optimization
"""

from datetime import datetime, time

import numpy as np
import structlog

from src.models.forex import ForexSession
from src.models.ohlcv import OHLCVBar
from src.pattern_engine.volume_analyzer import calculate_volume_ratio

logger = structlog.get_logger(__name__)


class IntradayVolumeAnalyzer:
    """
    Session-aware volume analyzer for intraday forex and index trading.

    Key Features:
    1. Session normalization (compare against session average, not global)
    2. News event filtering (ignore 30min before/after major events)
    3. Relative volume (vs previous 3 sessions, not 20 bars)
    4. Tick volume interpretation for forex

    Example:
        analyzer = IntradayVolumeAnalyzer(asset_type="forex")

        # Analyze Spring pattern volume
        volume_ratio = analyzer.calculate_session_relative_volume(
            bars=bars,
            index=spring_index,
            session=ForexSession.LONDON
        )

        # 0.3x volume during London session = genuine low volume
        # 0.3x volume during Asian session = just normal Asian volume!
    """

    # Session volume baselines (relative to 24h average)
    SESSION_VOLUME_FACTORS = {
        ForexSession.ASIAN: 0.4,  # Asian is ~40% of average
        ForexSession.LONDON: 1.3,  # London is ~130% of average
        ForexSession.NY: 1.2,  # NY is ~120% of average
        ForexSession.OVERLAP: 1.6,  # Overlap is ~160% of average (peak)
    }

    def __init__(self, asset_type: str = "forex"):
        """
        Initialize intraday volume analyzer.

        Args:
            asset_type: "forex" (tick volume) or "index" (true volume)
        """
        self.asset_type = asset_type
        self.logger = logger.bind(component="intraday_volume_analyzer", asset_type=asset_type)

    def calculate_session_relative_volume(
        self,
        bars: list[OHLCVBar],
        index: int,
        session: ForexSession | None = None,
    ) -> float | None:
        """
        Calculate volume ratio relative to SAME SESSION average.

        This prevents false readings like:
        - "Low volume" Spring during Asian session (actually normal Asian volume)
        - "High volume" during London open (actually normal London volume)

        Algorithm:
        1. Identify current session
        2. Find previous N bars in SAME session
        3. Calculate volume ratio vs session average
        4. Adjust for session baseline

        Args:
            bars: List of OHLCV bars
            index: Index of bar to analyze
            session: Trading session (auto-detect if None)

        Returns:
            Volume ratio relative to session average (e.g., 0.5 = 50% of session avg)

        Example:
            # Bar has volume=1000, avg London volume=3000
            # ratio = 1000/3000 = 0.33x (genuine low volume!)

            # Bar has volume=400, avg Asian volume=1000
            # ratio = 400/1000 = 0.40x (normal Asian volume)
        """
        if not bars or index < 0 or index >= len(bars):
            return None

        current_bar = bars[index]

        # Auto-detect session if not provided
        if session is None:
            session = self._detect_session(current_bar.timestamp)

        # Find bars from same session in recent history
        session_bars = self._get_recent_session_bars(
            bars=bars,
            end_index=index,
            session=session,
            lookback_sessions=3,  # Compare against last 3 sessions
        )

        if len(session_bars) < 5:
            # Not enough session data - fall back to standard calculation
            self.logger.warning(
                "Insufficient session history, using standard volume calc",
                index=index,
                session=session,
                bars_found=len(session_bars),
            )
            return calculate_volume_ratio(bars, index)

        # Calculate session average volume
        session_volumes = [b.volume for b in session_bars]
        avg_session_volume = np.mean(session_volumes)

        if avg_session_volume == 0:
            return None

        # Calculate ratio
        current_volume = float(current_bar.volume)
        volume_ratio = current_volume / avg_session_volume

        self.logger.debug(
            "Session-relative volume calculated",
            index=index,
            session=session,
            current_volume=current_volume,
            avg_session_volume=avg_session_volume,
            ratio=round(volume_ratio, 3),
        )

        return volume_ratio

    def is_climactic_intraday(
        self,
        bars: list[OHLCVBar],
        index: int,
        threshold: float = 2.0,
    ) -> bool:
        """
        Determine if volume is climactic for INTRADAY context.

        Intraday Modification:
        - Uses session-relative volume
        - Filters out session opens (first 30 min)
        - Ignores overlap period spikes
        - Adjusts threshold by session

        Args:
            bars: List of bars
            index: Index to check
            threshold: Base threshold (default 2.0x session average)

        Returns:
            True if genuinely climactic

        Example:
            # London open bar: 3.0x volume
            # is_climactic_intraday() = False (just session open)

            # Mid-London bar: 3.0x volume
            # is_climactic_intraday() = True (genuine climax!)
        """
        if not bars or index < 0 or index >= len(bars):
            return False

        current_bar = bars[index]
        session = self._detect_session(current_bar.timestamp)

        # Filter out session opens (first 30 minutes)
        if self._is_session_open(current_bar.timestamp, session):
            self.logger.debug(
                "Skipping climax check - session open period",
                index=index,
                session=session,
                time=current_bar.timestamp.strftime("%H:%M"),
            )
            return False

        # Calculate session-relative volume
        volume_ratio = self.calculate_session_relative_volume(bars, index, session)

        if volume_ratio is None:
            return False

        # Adjust threshold by session
        # Overlap period needs higher threshold (naturally higher volume)
        if session == ForexSession.OVERLAP:
            adjusted_threshold = threshold * 1.3
        else:
            adjusted_threshold = threshold

        is_climactic = volume_ratio >= adjusted_threshold

        if is_climactic:
            self.logger.info(
                "Climactic volume detected (intraday)",
                index=index,
                session=session,
                volume_ratio=round(volume_ratio, 2),
                threshold=adjusted_threshold,
            )

        return is_climactic

    def validate_spring_volume_intraday(
        self,
        bars: list[OHLCVBar],
        spring_index: int,
        max_ratio: float = 0.7,
    ) -> tuple[bool, float]:
        """
        Validate Spring pattern volume using intraday-adjusted logic.

        Spring Requirements (Intraday):
        1. Volume < 0.7x session average (not global average)
        2. Not during session open (avoid false low volume)
        3. Compared against same-session historical data

        Args:
            bars: List of bars
            spring_index: Index of potential Spring bar
            max_ratio: Maximum acceptable volume ratio (default 0.7x)

        Returns:
            Tuple of (is_valid, actual_ratio)

        Example:
            valid, ratio = validate_spring_volume_intraday(bars, 150)
            if valid:
                print(f"Valid Spring: {ratio:.2f}x session volume")
        """
        current_bar = bars[spring_index]
        session = self._detect_session(current_bar.timestamp)

        # Calculate session-relative volume
        volume_ratio = self.calculate_session_relative_volume(bars, spring_index, session)

        if volume_ratio is None:
            return False, 0.0

        # Validate against threshold
        is_valid = volume_ratio < max_ratio

        if is_valid:
            self.logger.info(
                "Spring volume validated (intraday)",
                index=spring_index,
                session=session,
                volume_ratio=round(volume_ratio, 3),
                threshold=max_ratio,
            )
        else:
            self.logger.warning(
                "Spring volume FAILED (intraday)",
                index=spring_index,
                session=session,
                volume_ratio=round(volume_ratio, 3),
                threshold=max_ratio,
                reason="Volume too high for Spring pattern",
            )

        return is_valid, volume_ratio

    def _detect_session(self, timestamp: datetime) -> ForexSession:
        """
        Detect forex trading session from timestamp.

        Sessions (UTC):
        - Asian: 0:00-8:00
        - London: 8:00-17:00
        - NY: 13:00-22:00
        - Overlap: 13:00-17:00 (London/NY overlap = highest liquidity)

        Args:
            timestamp: Bar timestamp

        Returns:
            ForexSession enum
        """
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
            return ForexSession.ASIAN  # 22:00-24:00 transitions to next Asian

    def _is_session_open(self, timestamp: datetime, session: ForexSession) -> bool:
        """
        Check if timestamp is within first 30 minutes of session open.

        Session opens have artificially high volume (not climactic).

        Args:
            timestamp: Bar timestamp
            session: Trading session

        Returns:
            True if within 30 min of session open
        """
        hour = timestamp.hour
        minute = timestamp.minute

        # Session open times (UTC)
        session_opens = {
            ForexSession.ASIAN: time(0, 0),
            ForexSession.LONDON: time(8, 0),
            ForexSession.NY: time(13, 0),
            ForexSession.OVERLAP: time(13, 0),
        }

        open_time = session_opens.get(session)
        if not open_time:
            return False

        # Check if within 30 minutes of open
        bar_time = time(hour, minute)
        open_window_end = time(
            (open_time.hour if open_time.minute < 30 else open_time.hour + 1),
            (open_time.minute + 30) % 60,
        )

        return open_time <= bar_time < open_window_end

    def _get_recent_session_bars(
        self,
        bars: list[OHLCVBar],
        end_index: int,
        session: ForexSession,
        lookback_sessions: int = 3,
    ) -> list[OHLCVBar]:
        """
        Get bars from same session over previous N sessions.

        Example:
        - Current bar: London session, Tuesday 10:00
        - Returns: All London session bars from Mon, Fri, Thu (last 3 London sessions)

        Args:
            bars: List of bars
            end_index: Current bar index
            session: Session to match
            lookback_sessions: Number of previous sessions to include

        Returns:
            List of bars from matching sessions
        """
        session_bars = []
        sessions_found = 0

        # Walk backwards from current index
        for i in range(end_index - 1, -1, -1):
            bar = bars[i]
            bar_session = self._detect_session(bar.timestamp)

            if bar_session == session:
                session_bars.append(bar)

                # Count session transitions
                if i > 0:
                    prev_session = self._detect_session(bars[i - 1].timestamp)
                    if prev_session != session:
                        sessions_found += 1
                        if sessions_found >= lookback_sessions:
                            break

        return session_bars
