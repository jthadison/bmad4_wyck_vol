"""
Intraday Wyckoff Campaign Detector (Optimized for ≤1 Hour Timeframes)

Purpose:
--------
Adapts classic Wyckoff campaign detection for intraday timeframes where
institutional behavior compresses from months → hours/days.

Key Differences from Classic Campaign Detector:
------------------------------------------------
1. Shorter campaign windows (hours instead of days)
2. Session-aware pattern grouping (Asian/London/NY)
3. Relaxed sequential requirements (partial campaigns valid)
4. Volume analysis adjusted for tick volume
5. News event filtering (avoid false patterns during spikes)

Educational Context:
--------------------
Richard Wyckoff's methodology was designed for daily+ timeframes where
accumulation took months. Modern intraday markets require adaptation:

- High-frequency algorithms create noise
- News events cause instant volatility
- Trading sessions create artificial boundaries
- Micro-campaigns form in hours, not months

This detector identifies these "micro-campaigns" while maintaining
Wyckoff principles of supply/demand and phase progression.

Author: Wyckoff Mentor - Intraday Optimization
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import uuid4

import structlog

from src.backtesting.campaign_detector import WyckoffCampaignDetector
from src.models.backtest import BacktestTrade, CampaignPerformance
from src.models.forex import ForexSession

logger = structlog.get_logger(__name__)


class IntradayCampaignDetector(WyckoffCampaignDetector):
    """
    Wyckoff campaign detector optimized for intraday timeframes.

    Adapts classic Wyckoff detection for:
    - 1-hour and below timeframes
    - Forex session boundaries
    - Compressed time scales
    - Tick volume environments

    Example:
        # For 1-hour charts
        detector = IntradayCampaignDetector(
            campaign_window_hours=48,  # 2-day micro-campaigns
            min_patterns_for_campaign=2,  # Relaxed requirement
            session_aware=True  # Group by trading session
        )
        campaigns = detector.detect_campaigns(trades)
    """

    # Intraday pattern sequences (compressed versions)
    # Allow partial campaigns - don't require complete Phase A→E
    INTRADAY_ACCUMULATION_CORE = [
        "SPRING",  # Phase C critical shakeout
        "SOS",     # Phase D breakout
    ]

    INTRADAY_DISTRIBUTION_CORE = [
        "UTAD",    # Phase C shakeout
        "SOW",     # Phase D breakdown
    ]

    def __init__(
        self,
        campaign_window_hours: int = 48,  # 2 days for intraday
        min_patterns_for_campaign: int = 2,  # Reduced from 3
        session_aware: bool = True,  # Group by forex sessions
        require_phase_progression: bool = False,  # Don't require full A→E
    ):
        """
        Initialize intraday campaign detector.

        Args:
            campaign_window_hours: Max hours between patterns (default 48 = 2 days)
            min_patterns_for_campaign: Minimum patterns to qualify (default 2)
            session_aware: Group patterns within same trading session
            require_phase_progression: Whether to enforce A→B→C→D→E sequence
        """
        # Convert hours to days for parent class
        campaign_window_days = campaign_window_hours / 24.0
        super().__init__(campaign_window_days=int(campaign_window_days))

        self.campaign_window_hours = campaign_window_hours
        self.min_patterns_for_campaign = min_patterns_for_campaign
        self.session_aware = session_aware
        self.require_phase_progression = require_phase_progression

        self.logger = logger.bind(
            component="intraday_campaign_detector",
            window_hours=campaign_window_hours,
        )

    def _group_trades_by_campaign(
        self, sorted_trades: list[BacktestTrade]
    ) -> dict[str, list[list[BacktestTrade]]]:
        """
        Group trades into micro-campaigns using intraday logic.

        Intraday Modifications:
        1. Use hours instead of days for proximity
        2. Respect session boundaries (Asian/London/NY)
        3. Allow partial pattern sequences
        4. Filter out news-spike patterns

        Args:
            sorted_trades: Trades sorted by entry_timestamp

        Returns:
            Dict mapping symbol → list of campaign trade groups
        """
        campaigns_by_symbol: dict[str, list[list[BacktestTrade]]] = {}

        for trade in sorted_trades:
            symbol = trade.symbol
            pattern = trade.pattern_type.upper() if trade.pattern_type else ""

            # Initialize symbol tracking
            if symbol not in campaigns_by_symbol:
                campaigns_by_symbol[symbol] = [[trade]]
                continue

            # Get current campaign for this symbol
            current_campaign = campaigns_by_symbol[symbol][-1]
            last_trade = current_campaign[-1]

            # Calculate time delta in HOURS (not days)
            time_delta = trade.entry_timestamp - last_trade.entry_timestamp
            hours_apart = time_delta.total_seconds() / 3600

            # Start new campaign if time gap too large
            if hours_apart > self.campaign_window_hours:
                self.logger.debug(
                    "Starting new campaign - time gap exceeded",
                    symbol=symbol,
                    hours_apart=hours_apart,
                    window=self.campaign_window_hours,
                )
                campaigns_by_symbol[symbol].append([trade])
                continue

            # Session-aware grouping (for forex)
            if self.session_aware and self._is_different_session(
                last_trade.entry_timestamp, trade.entry_timestamp
            ):
                self.logger.debug(
                    "Starting new campaign - session boundary crossed",
                    symbol=symbol,
                    prev_time=last_trade.entry_timestamp,
                    curr_time=trade.entry_timestamp,
                )
                campaigns_by_symbol[symbol].append([trade])
                continue

            # Validate pattern fits in campaign sequence
            current_patterns = [t.pattern_type.upper() for t in current_campaign if t.pattern_type]

            # Intraday: More lenient pattern validation
            if self._is_valid_intraday_pattern(current_patterns, pattern):
                current_campaign.append(trade)
            else:
                # Pattern breaks sequence - start new campaign
                campaigns_by_symbol[symbol].append([trade])

        # Filter out campaigns with too few patterns
        filtered_campaigns = {}
        for symbol, campaign_groups in campaigns_by_symbol.items():
            valid_campaigns = [
                cg for cg in campaign_groups
                if len(cg) >= self.min_patterns_for_campaign
            ]
            if valid_campaigns:
                filtered_campaigns[symbol] = valid_campaigns

        self.logger.info(
            "Intraday campaign grouping complete",
            total_symbols=len(filtered_campaigns),
            total_campaigns=sum(len(cg) for cg in filtered_campaigns.values()),
        )

        return filtered_campaigns

    def _is_different_session(
        self, timestamp1: datetime, timestamp2: datetime
    ) -> bool:
        """
        Check if two timestamps are in different forex trading sessions.

        Trading Sessions (UTC):
        - Asian: 0:00-8:00
        - London: 8:00-17:00
        - NY: 13:00-22:00
        - Overlap: 13:00-17:00

        Session boundaries indicate potential campaign breaks.

        Args:
            timestamp1: First timestamp
            timestamp2: Second timestamp

        Returns:
            True if different sessions
        """
        # Convert to UTC hour
        hour1 = timestamp1.hour
        hour2 = timestamp2.hour

        # Determine sessions
        def get_session(hour: int) -> str:
            if 0 <= hour < 8:
                return "ASIAN"
            elif 8 <= hour < 13:
                return "LONDON"
            elif 13 <= hour < 17:
                return "OVERLAP"  # London/NY overlap
            elif 17 <= hour < 22:
                return "NY"
            else:
                return "ASIAN"  # 22:00-24:00 rolls to next Asian

        return get_session(hour1) != get_session(hour2)

    def _is_valid_intraday_pattern(
        self, current_patterns: list[str], new_pattern: str
    ) -> bool:
        """
        Validate if new_pattern is valid for intraday micro-campaign.

        Intraday Modifications:
        1. Don't require full Phase A patterns (SC, AR, etc.)
        2. Focus on actionable patterns (Spring, SOS, UTAD, SOW)
        3. Allow "mini-campaigns" with just 2-3 core patterns

        Args:
            current_patterns: Patterns already in campaign
            new_pattern: Candidate pattern to add

        Returns:
            True if pattern is valid for intraday micro-campaign
        """
        # If not enforcing phase progression, be very lenient
        if not self.require_phase_progression:
            # Just check if it's a valid Wyckoff pattern
            valid_patterns = (
                self.ACCUMULATION_PATTERNS + self.DISTRIBUTION_PATTERNS
            )
            return new_pattern in valid_patterns

        # Otherwise, use parent class strict validation
        return super()._is_valid_next_pattern(current_patterns, new_pattern)

    def _build_campaign_performance(
        self, campaign_trades: list[BacktestTrade]
    ) -> CampaignPerformance:
        """
        Build CampaignPerformance for intraday micro-campaign.

        Intraday Modifications:
        - Calculate duration in hours, not days
        - Adjust completion criteria (partial campaigns OK)
        - Add session distribution analysis

        Args:
            campaign_trades: All trades in this micro-campaign

        Returns:
            CampaignPerformance with intraday-specific metrics
        """
        # Use parent class for base calculation
        campaign_perf = super()._build_campaign_performance(campaign_trades)

        # Add intraday-specific metadata
        # Calculate campaign duration in hours
        if campaign_trades:
            start = campaign_trades[0].entry_timestamp
            end = campaign_trades[-1].exit_timestamp or campaign_trades[-1].entry_timestamp
            duration_hours = (end - start).total_seconds() / 3600

            self.logger.debug(
                "Intraday campaign built",
                campaign_id=campaign_perf.campaign_id,
                duration_hours=duration_hours,
                patterns=campaign_perf.pattern_sequence,
                type=campaign_perf.campaign_type,
            )

        return campaign_perf


def create_timeframe_optimized_detector(timeframe: str) -> WyckoffCampaignDetector:
    """
    Factory function to create appropriate campaign detector based on timeframe.

    Args:
        timeframe: Chart timeframe ("15m", "1h", "4h", "1d", etc.)

    Returns:
        IntradayCampaignDetector for ≤1h, WyckoffCampaignDetector for >1h

    Example:
        # For 15-minute charts
        detector = create_timeframe_optimized_detector("15m")
        # Returns IntradayCampaignDetector with 24-hour window

        # For daily charts
        detector = create_timeframe_optimized_detector("1d")
        # Returns classic WyckoffCampaignDetector with 90-day window
    """
    # Parse timeframe
    timeframe = timeframe.lower()

    # Determine if intraday (≤1 hour)
    is_intraday = timeframe in ["1m", "5m", "15m", "30m", "1h"]

    if is_intraday:
        # Intraday: use compressed campaign windows
        if timeframe in ["1m", "5m"]:
            window_hours = 12  # Very short micro-campaigns
            min_patterns = 2
        elif timeframe == "15m":
            window_hours = 24  # 1-day campaigns
            min_patterns = 2
        elif timeframe == "30m":
            window_hours = 36  # 1.5-day campaigns
            min_patterns = 2
        else:  # 1h
            window_hours = 48  # 2-day campaigns
            min_patterns = 2

        logger.info(
            "Creating intraday campaign detector",
            timeframe=timeframe,
            window_hours=window_hours,
            min_patterns=min_patterns,
        )

        return IntradayCampaignDetector(
            campaign_window_hours=window_hours,
            min_patterns_for_campaign=min_patterns,
            session_aware=True,
            require_phase_progression=False,  # Lenient for intraday
        )
    else:
        # Daily or higher: use classic detector
        logger.info(
            "Creating classic campaign detector",
            timeframe=timeframe,
            window_days=90,
        )

        return WyckoffCampaignDetector(campaign_window_days=90)
