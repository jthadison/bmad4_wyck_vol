"""
Regime Performance Analyzer (Story 16.7b)

Analyzes campaign performance by market regime to identify optimal trading conditions
and provide statistics on win rate, R-multiple, and success rate across different
market environments (ranging, trending, volatile, etc.).

Author: Developer Agent (Story 16.7b Implementation)
"""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from statistics import mean
from typing import Any, Optional

import structlog

from src.backtesting.intraday_campaign_detector import (
    REGIME_QUALITY_THRESHOLDS,
    REGIME_STATS_CACHE_TTL_SECONDS,
    Campaign,
    CampaignState,
    ExitReason,
    IntradayCampaignDetector,
)
from src.models.market_context import MarketRegime

# Story 16.7b: Named constants for regime transition analysis
WIN_RATE_DROP_WARNING_THRESHOLD = 0.10  # 10% drop triggers warning
MIN_CAMPAIGNS_FOR_STATISTICS = 5  # Minimum campaigns for statistical significance
UNDERPERFORMING_WIN_RATE_THRESHOLD = 0.5  # Below 50% triggers caution
HIGH_VOLATILITY_POOR_PERFORMANCE_THRESHOLD = 0.4  # Below 40% in high vol is poor

logger = structlog.get_logger(__name__)


class RegimePerformanceAnalyzer:
    """
    Analyze campaign success by market regime (Story 16.7b).

    Provides statistics on campaign performance segmented by market regime,
    enabling identification of optimal entry conditions and regime-specific
    win rates.

    Features:
        - Success rate by regime
        - Win rate analysis per regime
        - Average R-multiple by regime
        - Optimal entry regime identification
        - Regime transition warnings
        - Cached statistics (1 hour TTL)

    Cache Invalidation:
        Statistics are cached for 1 hour (REGIME_STATS_CACHE_TTL_SECONDS).
        The cache does NOT automatically invalidate when campaigns change.
        Consumers MUST call `invalidate_cache()` after modifying campaigns
        to ensure fresh statistics are computed on the next request.

    Example:
        >>> analyzer = RegimePerformanceAnalyzer(detector)
        >>> stats = analyzer.get_regime_statistics()
        >>> # Returns: {MarketRegime.SIDEWAYS: {"win_rate": 0.72, ...}, ...}

        >>> report = analyzer.get_regime_performance_report()
        >>> # Returns full report with optimal regime identified

        >>> # After adding new campaigns, invalidate cache:
        >>> analyzer.invalidate_cache()
    """

    def __init__(
        self,
        detector: IntradayCampaignDetector,
        cache_ttl_seconds: int = REGIME_STATS_CACHE_TTL_SECONDS,
    ):
        """
        Initialize regime performance analyzer.

        Args:
            detector: IntradayCampaignDetector to analyze campaigns from
            cache_ttl_seconds: Cache TTL for statistics (default: 1 hour)
        """
        self.detector = detector
        self.cache_ttl_seconds = cache_ttl_seconds

        # Statistics cache
        self._stats_cache: Optional[dict[MarketRegime, dict[str, Any]]] = None
        self._cache_timestamp: Optional[datetime] = None

        self.logger = logger.bind(component="regime_performance_analyzer")

    def _is_cache_valid(self) -> bool:
        """Check if statistics cache is still valid."""
        if self._stats_cache is None or self._cache_timestamp is None:
            return False

        age = datetime.now(UTC) - self._cache_timestamp
        return age < timedelta(seconds=self.cache_ttl_seconds)

    def _get_campaigns_by_regime(self, regime: MarketRegime) -> list[Campaign]:
        """
        Get all completed campaigns for a specific regime.

        Args:
            regime: Market regime to filter by

        Returns:
            List of completed campaigns with the specified regime
        """
        completed_campaigns = [
            c for c in self.detector.campaigns if c.state == CampaignState.COMPLETED
        ]

        return [c for c in completed_campaigns if c.market_regime == regime]

    def _calculate_win_rate(self, campaigns: list[Campaign]) -> float:
        """
        Calculate win rate for a list of campaigns.

        A win is defined as R-multiple > 0 (profit).

        Args:
            campaigns: List of campaigns to analyze

        Returns:
            Win rate as decimal (0.0-1.0), or 0.0 if no campaigns
        """
        if not campaigns:
            return 0.0

        wins = sum(1 for c in campaigns if c.r_multiple is not None and c.r_multiple > 0)
        return wins / len(campaigns)

    def _calculate_avg_r_multiple(self, campaigns: list[Campaign]) -> float:
        """
        Calculate average R-multiple for campaigns.

        Args:
            campaigns: List of campaigns to analyze

        Returns:
            Average R-multiple, or 0.0 if no campaigns
        """
        r_multiples = [float(c.r_multiple) for c in campaigns if c.r_multiple is not None]

        if not r_multiples:
            return 0.0

        return mean(r_multiples)

    def _calculate_success_rate(self, campaigns: list[Campaign]) -> float:
        """
        Calculate success rate (campaigns reaching target).

        Success is defined as:
        - R-multiple >= 2.0 (reached 2R target), OR
        - Exit reason is TARGET_HIT or PHASE_E

        Args:
            campaigns: List of campaigns to analyze

        Returns:
            Success rate as decimal (0.0-1.0)
        """
        if not campaigns:
            return 0.0

        successes = sum(
            1
            for c in campaigns
            if (c.r_multiple is not None and c.r_multiple >= Decimal("2.0"))
            or c.exit_reason in [ExitReason.TARGET_HIT, ExitReason.PHASE_E]
        )

        return successes / len(campaigns)

    def get_regime_statistics(self) -> dict[MarketRegime, dict[str, Any]]:
        """
        Calculate statistics for all market regimes (Story 16.7b).

        Returns cached statistics if available and valid.

        Returns:
            Dictionary mapping regime to statistics:
            {
                MarketRegime.SIDEWAYS: {
                    "total_campaigns": 50,
                    "win_rate": 0.72,
                    "avg_r_multiple": 1.85,
                    "success_rate": 0.64,
                },
                ...
            }

        Example:
            >>> stats = analyzer.get_regime_statistics()
            >>> stats[MarketRegime.SIDEWAYS]["win_rate"]
            0.72
        """
        # Return cached stats if valid
        if self._is_cache_valid():
            self.logger.debug("Returning cached regime statistics")
            return self._stats_cache  # type: ignore[return-value]

        stats: dict[MarketRegime, dict[str, Any]] = {}

        for regime in MarketRegime:
            campaigns = self._get_campaigns_by_regime(regime)

            stats[regime] = {
                "total_campaigns": len(campaigns),
                "win_rate": self._calculate_win_rate(campaigns),
                "avg_r_multiple": self._calculate_avg_r_multiple(campaigns),
                "success_rate": self._calculate_success_rate(campaigns),
            }

        # Update cache
        self._stats_cache = stats
        self._cache_timestamp = datetime.now(UTC)

        self.logger.info(
            "Regime statistics calculated",
            regimes_analyzed=len(stats),
            total_campaigns=sum(s["total_campaigns"] for s in stats.values()),
        )

        return stats

    def get_optimal_regime(self) -> Optional[MarketRegime]:
        """
        Identify the optimal market regime for trading.

        Optimal regime is defined as highest win rate among regimes
        with at least 5 completed campaigns (statistical significance).

        Returns:
            Best performing MarketRegime, or None if insufficient data

        Example:
            >>> optimal = analyzer.get_optimal_regime()
            >>> # Returns: MarketRegime.SIDEWAYS (if best performing)
        """
        stats = self.get_regime_statistics()

        # Filter regimes with sufficient data for statistical significance
        valid_regimes = {
            regime: data
            for regime, data in stats.items()
            if data["total_campaigns"] >= MIN_CAMPAIGNS_FOR_STATISTICS
        }

        if not valid_regimes:
            self.logger.warning("Insufficient data to identify optimal regime")
            return None

        # Find regime with highest win rate
        optimal = max(valid_regimes.items(), key=lambda x: x[1]["win_rate"])

        self.logger.info(
            "Optimal regime identified",
            regime=optimal[0].value,
            win_rate=optimal[1]["win_rate"],
            campaigns=optimal[1]["total_campaigns"],
        )

        return optimal[0]

    def get_regime_transition_warning(
        self,
        current_regime: MarketRegime,
        new_regime: MarketRegime,
    ) -> Optional[str]:
        """
        Generate warning message for regime transitions (Story 16.7b).

        Warns when transitioning from optimal to suboptimal regime,
        or when entering high-risk regime.

        Args:
            current_regime: Current market regime
            new_regime: New market regime detected

        Returns:
            Warning message string, or None if transition is acceptable

        Example:
            >>> warning = analyzer.get_regime_transition_warning(
            ...     MarketRegime.SIDEWAYS, MarketRegime.HIGH_VOLATILITY
            ... )
            >>> # Returns: "High volatility detected. Tightening quality..."
        """
        if current_regime == new_regime:
            return None

        stats = self.get_regime_statistics()
        current_win_rate = stats[current_regime]["win_rate"]
        new_win_rate = stats[new_regime]["win_rate"]

        warnings: list[str] = []

        # Warn on significant win rate drop
        if new_win_rate < current_win_rate - WIN_RATE_DROP_WARNING_THRESHOLD:
            warnings.append(
                f"Regime change from {current_regime.value} to {new_regime.value} "
                f"may reduce win rate by {(current_win_rate - new_win_rate) * 100:.1f}%"
            )

        # Specific regime warnings
        if new_regime == MarketRegime.HIGH_VOLATILITY:
            warnings.append(
                "High volatility detected. Volume requirements increased by 20%. "
                "Consider reducing position sizes."
            )
        elif new_regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
            trending_threshold = REGIME_QUALITY_THRESHOLDS.get(new_regime, 0.8)
            warnings.append(
                f"Strong {new_regime.value.lower()} detected. Quality threshold "
                f"increased to {trending_threshold}. Wyckoff patterns may be less reliable."
            )

        if not warnings:
            return None

        return " ".join(warnings)

    def get_regime_performance_report(self) -> dict[str, Any]:
        """
        Generate comprehensive regime performance report (Story 16.7b).

        Returns full report suitable for dashboard display or API response.

        Returns:
            Report dictionary with structure:
            {
                "generated_at": "2026-01-21T...",
                "total_campaigns_analyzed": 150,
                "optimal_regime": "SIDEWAYS",
                "regime_statistics": {...},
                "recommendations": [...],
            }

        Example:
            >>> report = analyzer.get_regime_performance_report()
            >>> print(report["optimal_regime"])
            "SIDEWAYS"
        """
        stats = self.get_regime_statistics()
        optimal = self.get_optimal_regime()

        total_campaigns = sum(s["total_campaigns"] for s in stats.values())

        # Generate recommendations
        recommendations: list[str] = []

        if optimal:
            recommendations.append(
                f"Optimal regime for entries: {optimal.value} "
                f"(win rate: {stats[optimal]['win_rate']:.1%})"
            )

        # Identify underperforming regimes
        for regime, data in stats.items():
            if (
                data["total_campaigns"] >= MIN_CAMPAIGNS_FOR_STATISTICS
                and data["win_rate"] < UNDERPERFORMING_WIN_RATE_THRESHOLD
            ):
                recommendations.append(
                    f"Caution in {regime.value}: Win rate below 50% "
                    f"({data['win_rate']:.1%}). Consider avoiding entries."
                )

        # Check for high-volatility performance
        high_vol_stats = stats.get(MarketRegime.HIGH_VOLATILITY, {})
        if high_vol_stats.get("total_campaigns", 0) >= 3:
            if high_vol_stats.get("win_rate", 0) < HIGH_VOLATILITY_POOR_PERFORMANCE_THRESHOLD:
                recommendations.append(
                    "High volatility regime showing poor results. "
                    "Consider pausing trading during volatile periods."
                )

        report: dict[str, Any] = {
            "generated_at": datetime.now(UTC).isoformat(),
            "total_campaigns_analyzed": total_campaigns,
            "optimal_regime": optimal.value if optimal else None,
            "regime_statistics": {regime.value: data for regime, data in stats.items()},
            "recommendations": recommendations,
        }

        self.logger.info(
            "Regime performance report generated",
            total_campaigns=total_campaigns,
            optimal_regime=optimal.value if optimal else None,
            recommendations_count=len(recommendations),
        )

        return report

    def export_to_json(self) -> str:
        """
        Export regime statistics to JSON format.

        Returns:
            JSON string of regime performance report

        Example:
            >>> json_report = analyzer.export_to_json()
            >>> with open("regime_report.json", "w") as f:
            ...     f.write(json_report)
        """
        report = self.get_regime_performance_report()
        return json.dumps(report, indent=2)

    def export_to_csv(self) -> str:
        """
        Export regime statistics to CSV format.

        Returns:
            CSV string with regime statistics

        Example:
            >>> csv_data = analyzer.export_to_csv()
            >>> with open("regime_stats.csv", "w") as f:
            ...     f.write(csv_data)
        """
        stats = self.get_regime_statistics()

        lines = ["regime,total_campaigns,win_rate,avg_r_multiple,success_rate"]

        for regime, data in stats.items():
            line = (
                f"{regime.value},"
                f"{data['total_campaigns']},"
                f"{data['win_rate']:.4f},"
                f"{data['avg_r_multiple']:.4f},"
                f"{data['success_rate']:.4f}"
            )
            lines.append(line)

        return "\n".join(lines)

    def invalidate_cache(self) -> None:
        """
        Invalidate statistics cache.

        Call when campaigns change to force fresh calculation.
        """
        self._stats_cache = None
        self._cache_timestamp = None
        self.logger.debug("Regime statistics cache invalidated")

    def filter_campaigns_by_regime(
        self,
        regime: MarketRegime,
        include_forming: bool = False,
    ) -> list[Campaign]:
        """
        Filter campaigns by market regime (Story 16.7b - Reporting API).

        Args:
            regime: Market regime to filter by
            include_forming: Include FORMING campaigns (default: False)

        Returns:
            List of campaigns matching the specified regime

        Example:
            >>> sideways_campaigns = analyzer.filter_campaigns_by_regime(
            ...     MarketRegime.SIDEWAYS
            ... )
        """
        campaigns = self.detector.campaigns

        if not include_forming:
            campaigns = [c for c in campaigns if c.state != CampaignState.FORMING]

        return [c for c in campaigns if c.market_regime == regime]
