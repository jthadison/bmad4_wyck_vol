"""
Impact analysis service for configuration changes.

Analyzes how proposed configuration changes would affect signal generation
and performance based on historical pattern data.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.config import ImpactAnalysisResult, SystemConfiguration
from src.services.recommendation_service import RecommendationService


class ImpactAnalysisService:
    """Service for analyzing configuration change impact.

    Evaluates proposed configuration against historical pattern data
    to estimate impact on signal count and win rate.

    Example:
        >>> service = ImpactAnalysisService(session)
        >>> impact = await service.analyze_config_impact(current_config, proposed_config)
        >>> print(f"Signal delta: {impact.signal_count_delta}")
    """

    def __init__(self, session: AsyncSession):
        """Initialize service with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.recommendation_service = RecommendationService()

    async def analyze_config_impact(
        self, current: SystemConfiguration, proposed: SystemConfiguration
    ) -> ImpactAnalysisResult:
        """Analyze impact of proposed configuration changes.

        Queries last 90 days of pattern data, re-evaluates against both
        current and proposed configurations, calculates delta metrics.

        Args:
            current: Current system configuration
            proposed: Proposed system configuration

        Returns:
            ImpactAnalysisResult with metrics and recommendations

        Example:
            >>> impact = await service.analyze_config_impact(current, proposed)
            >>> print(f"{impact.signal_count_delta:+d} signals")
            >>> print(f"Win rate: {impact.proposed_win_rate:.1%}")
        """
        # Calculate date range (last 90 days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=90)

        # Get historical patterns from database
        patterns = await self._fetch_historical_patterns(start_date, end_date)

        # Re-evaluate patterns against current config
        current_signals = self._evaluate_patterns(patterns, current)

        # Re-evaluate patterns against proposed config
        proposed_signals = self._evaluate_patterns(patterns, proposed)

        # Calculate metrics
        signal_count_delta = len(proposed_signals) - len(current_signals)

        # Calculate win rates (if pattern outcome data available)
        current_win_rate = self._calculate_win_rate(current_signals)
        proposed_win_rate = self._calculate_win_rate(proposed_signals)

        win_rate_delta = None
        if current_win_rate is not None and proposed_win_rate is not None:
            win_rate_delta = proposed_win_rate - current_win_rate

        # Calculate confidence range (±3% for MVP)
        confidence_range = {}
        if proposed_win_rate is not None:
            confidence_range = {
                "min": max(Decimal("0.0"), proposed_win_rate - Decimal("0.03")),
                "max": min(Decimal("1.0"), proposed_win_rate + Decimal("0.03")),
            }

        # Generate recommendations
        recommendations = self.recommendation_service.generate_recommendations(
            current=current, proposed=proposed
        )

        # Assess risk impact
        risk_impact = self._assess_risk_impact(current, proposed)

        return ImpactAnalysisResult(
            signal_count_delta=signal_count_delta,
            current_signal_count=len(current_signals),
            proposed_signal_count=len(proposed_signals),
            current_win_rate=current_win_rate,
            proposed_win_rate=proposed_win_rate,
            win_rate_delta=win_rate_delta,
            confidence_range=confidence_range,
            recommendations=recommendations,
            risk_impact=risk_impact,
        )

    async def _fetch_historical_patterns(
        self, start_date: datetime, end_date: datetime
    ) -> list[dict]:
        """Fetch historical pattern data from database.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of pattern dictionaries with detection data
        """
        # Query patterns table for historical data
        # Note: cause_factor is stored in trading_ranges, not patterns table.
        # For impact analysis, we use the default cause_factor from pattern metadata
        # or assume the minimum (2.0) for patterns without range association.
        query = text(
            """
            SELECT
                id,
                symbol,
                pattern_type,
                detection_time,
                volume_ratio,
                confidence_score,
                metadata
            FROM patterns
            WHERE detection_time >= :start_date
              AND detection_time <= :end_date
            ORDER BY detection_time DESC
        """
        )

        result = await self.session.execute(query, {"start_date": start_date, "end_date": end_date})

        patterns = []
        for row in result.fetchall():
            # Extract cause_factor from metadata if available, otherwise use default 2.0
            metadata = row.metadata or {}
            cause_factor = metadata.get("cause_factor", 2.0) if isinstance(metadata, dict) else 2.0
            patterns.append(
                {
                    "id": str(row.id),
                    "symbol": row.symbol,
                    "pattern_type": row.pattern_type,
                    "detection_time": row.detection_time,
                    "volume_ratio": float(row.volume_ratio) if row.volume_ratio else 1.0,
                    "confidence_score": row.confidence_score,
                    "cause_factor": float(cause_factor),
                    "metadata": metadata,
                }
            )

        return patterns

    def _evaluate_patterns(self, patterns: list[dict], config: SystemConfiguration) -> list[dict]:
        """Evaluate which patterns would qualify under given configuration.

        Args:
            patterns: List of historical patterns
            config: Configuration to evaluate against

        Returns:
            List of patterns that would generate signals under this config
        """
        qualifying_patterns = []

        for pattern in patterns:
            if self._pattern_qualifies(pattern, config):
                qualifying_patterns.append(pattern)

        return qualifying_patterns

    def _pattern_qualifies(self, pattern: dict, config: SystemConfiguration) -> bool:
        """Check if a pattern qualifies under given configuration.

        Args:
            pattern: Pattern data dictionary
            config: Configuration to check against

        Returns:
            True if pattern qualifies, False otherwise
        """
        pattern_type = pattern["pattern_type"].lower()
        volume_ratio = Decimal(str(pattern["volume_ratio"]))
        confidence = pattern["confidence_score"]
        cause_factor = Decimal(str(pattern["cause_factor"]))

        # Check volume thresholds
        if pattern_type == "spring":
            if not (
                config.volume_thresholds.spring_volume_min
                <= volume_ratio
                <= config.volume_thresholds.spring_volume_max
            ):
                return False
            if confidence < config.pattern_confidence.min_spring_confidence:
                return False

        elif pattern_type == "sos":
            if volume_ratio < config.volume_thresholds.sos_volume_min:
                return False
            if confidence < config.pattern_confidence.min_sos_confidence:
                return False

        elif pattern_type == "lps":
            if volume_ratio < config.volume_thresholds.lps_volume_min:
                return False
            if confidence < config.pattern_confidence.min_lps_confidence:
                return False

        elif pattern_type == "utad":
            if volume_ratio > config.volume_thresholds.utad_volume_max:
                return False
            if confidence < config.pattern_confidence.min_utad_confidence:
                return False

        # Check cause factor (if applicable)
        if cause_factor > 0:
            if not (
                config.cause_factors.min_cause_factor
                <= cause_factor
                <= config.cause_factors.max_cause_factor
            ):
                return False

        return True

    def _calculate_win_rate(self, patterns: list[dict]) -> Optional[Decimal]:
        """Calculate win rate for a set of patterns.

        Args:
            patterns: List of patterns to analyze

        Returns:
            Win rate as Decimal or None if insufficient data

        Note:
            For MVP, returns estimated win rates based on pattern count.
            In production, would query actual trade outcomes.
        """
        if len(patterns) == 0:
            return None

        # MVP: Estimate win rate inversely proportional to volume
        # More signals (looser filters) = lower win rate
        # Fewer signals (stricter filters) = higher win rate

        # Baseline: 45 signals = 72% win rate
        # Formula: win_rate = 0.72 - (pattern_count - 45) * 0.001
        baseline_count = 45
        baseline_win_rate = Decimal("0.72")
        delta_per_signal = Decimal("0.001")

        signal_count = len(patterns)
        delta = (signal_count - baseline_count) * delta_per_signal
        win_rate = baseline_win_rate - Decimal(str(delta))

        # Clamp to reasonable range (0.50 to 0.85)
        win_rate = max(Decimal("0.50"), min(Decimal("0.85"), win_rate))

        return win_rate

    def _assess_risk_impact(
        self, current: SystemConfiguration, proposed: SystemConfiguration
    ) -> str:
        """Assess impact on risk profile.

        Args:
            current: Current configuration
            proposed: Proposed configuration

        Returns:
            Human-readable description of risk impact
        """
        impacts = []

        # Check if risk limits changed
        if proposed.risk_limits.max_risk_per_trade != current.risk_limits.max_risk_per_trade:
            delta = proposed.risk_limits.max_risk_per_trade - current.risk_limits.max_risk_per_trade
            if delta > 0:
                impacts.append(f"Increased per-trade risk by {delta}%")
            else:
                impacts.append(f"Reduced per-trade risk by {abs(delta)}%")

        if proposed.risk_limits.max_portfolio_heat != current.risk_limits.max_portfolio_heat:
            delta = proposed.risk_limits.max_portfolio_heat - current.risk_limits.max_portfolio_heat
            if delta > 0:
                impacts.append(f"Increased portfolio heat limit by {delta}%")
            else:
                impacts.append(f"Reduced portfolio heat limit by {abs(delta)}%")

        if len(impacts) == 0:
            return "No significant risk profile changes"

        return "; ".join(impacts)
