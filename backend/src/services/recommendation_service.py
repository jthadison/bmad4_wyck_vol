"""
Recommendation service for configuration changes.

Provides rule-based AI recommendations (William's advice) about
proposed configuration changes.
"""

from decimal import Decimal

from src.models.config import Recommendation, SystemConfiguration


class RecommendationService:
    """Service for generating configuration change recommendations.

    Uses rule-based system (MVP) to provide contextual advice about
    proposed configuration changes.

    Example:
        >>> service = RecommendationService()
        >>> recommendations = service.generate_recommendations(current, proposed)
        >>> for rec in recommendations:
        ...     print(f"[{rec.severity}] {rec.message}")
    """

    def generate_recommendations(
        self, current: SystemConfiguration, proposed: SystemConfiguration
    ) -> list[Recommendation]:
        """Generate recommendations based on configuration changes.

        Args:
            current: Current configuration
            proposed: Proposed configuration

        Returns:
            List of Recommendation objects with severity and message

        Example:
            >>> recommendations = service.generate_recommendations(current, proposed)
            >>> warning_count = sum(1 for r in recommendations if r.severity == "WARNING")
        """
        recommendations = []

        # Check volume threshold changes
        recommendations.extend(self._check_volume_changes(current, proposed))

        # Check risk limit changes
        recommendations.extend(self._check_risk_changes(current, proposed))

        # Check cause factor changes
        recommendations.extend(self._check_cause_factor_changes(current, proposed))

        # Check confidence threshold changes
        recommendations.extend(self._check_confidence_changes(current, proposed))

        # Check for multiple relaxed thresholds
        if self._count_relaxed_thresholds(current, proposed) >= 3:
            recommendations.append(
                Recommendation(
                    severity="WARNING",
                    message="Multiple relaxed thresholds compound risk and may significantly increase false positives",
                    category="general",
                )
            )

        # Check for tightened criteria
        if self._count_tightened_thresholds(current, proposed) >= 3:
            recommendations.append(
                Recommendation(
                    severity="INFO",
                    message="Stricter criteria will reduce signal quantity but may improve quality",
                    category="general",
                )
            )

        return recommendations

    def _check_volume_changes(
        self, current: SystemConfiguration, proposed: SystemConfiguration
    ) -> list[Recommendation]:
        """Check volume threshold changes and generate recommendations."""
        recommendations = []

        # Spring volume min decreased
        if (
            proposed.volume_thresholds.spring_volume_min
            < current.volume_thresholds.spring_volume_min
        ):
            recommendations.append(
                Recommendation(
                    severity="WARNING",
                    message="Lowering spring volume threshold may increase false positives. Springs should show LACK of selling pressure.",
                    category="volume",
                )
            )

        # Spring volume max increased (approaching 1.0x)
        if (
            proposed.volume_thresholds.spring_volume_max
            > current.volume_thresholds.spring_volume_max
        ):
            if proposed.volume_thresholds.spring_volume_max >= Decimal("0.95"):
                recommendations.append(
                    Recommendation(
                        severity="CAUTION",
                        message="Spring volume approaching average (1.0x) violates Wyckoff principles. Springs require low volume.",
                        category="volume",
                    )
                )

        # SOS volume min decreased
        if proposed.volume_thresholds.sos_volume_min < current.volume_thresholds.sos_volume_min:
            recommendations.append(
                Recommendation(
                    severity="WARNING",
                    message="Lowering SOS volume requirement weakens demand confirmation. SOS should show strong buying pressure.",
                    category="volume",
                )
            )

        # LPS volume min decreased significantly
        if proposed.volume_thresholds.lps_volume_min < current.volume_thresholds.lps_volume_min:
            delta = (
                current.volume_thresholds.lps_volume_min - proposed.volume_thresholds.lps_volume_min
            )
            if delta >= Decimal("0.2"):
                recommendations.append(
                    Recommendation(
                        severity="INFO",
                        message="Significantly lowering LPS volume threshold will increase LPS signals but may reduce quality.",
                        category="volume",
                    )
                )

        return recommendations

    def _check_risk_changes(
        self, current: SystemConfiguration, proposed: SystemConfiguration
    ) -> list[Recommendation]:
        """Check risk limit changes and generate recommendations."""
        recommendations = []

        # Max risk per trade increased
        if proposed.risk_limits.max_risk_per_trade > current.risk_limits.max_risk_per_trade:
            recommendations.append(
                Recommendation(
                    severity="CAUTION",
                    message="Increasing risk per trade requires strict discipline and strong emotional control.",
                    category="risk",
                )
            )

        # Max portfolio heat increased
        if proposed.risk_limits.max_portfolio_heat > current.risk_limits.max_portfolio_heat:
            delta = proposed.risk_limits.max_portfolio_heat - current.risk_limits.max_portfolio_heat
            if delta >= Decimal("3.0"):
                recommendations.append(
                    Recommendation(
                        severity="CAUTION",
                        message="Higher portfolio heat increases drawdown risk. Ensure you can handle increased volatility.",
                        category="risk",
                    )
                )

        # Max campaign risk increased
        if proposed.risk_limits.max_campaign_risk > current.risk_limits.max_campaign_risk:
            recommendations.append(
                Recommendation(
                    severity="INFO",
                    message="Increased campaign risk allows more concurrent positions but increases correlated risk.",
                    category="risk",
                )
            )

        # Risk limits decreased (positive feedback)
        if (
            proposed.risk_limits.max_risk_per_trade < current.risk_limits.max_risk_per_trade
            or proposed.risk_limits.max_portfolio_heat < current.risk_limits.max_portfolio_heat
        ):
            recommendations.append(
                Recommendation(
                    severity="INFO",
                    message="Reducing risk limits is a conservative adjustment that will protect capital during drawdowns.",
                    category="risk",
                )
            )

        return recommendations

    def _check_cause_factor_changes(
        self, current: SystemConfiguration, proposed: SystemConfiguration
    ) -> list[Recommendation]:
        """Check cause factor changes and generate recommendations."""
        recommendations = []

        # Min cause factor decreased
        if proposed.cause_factors.min_cause_factor < current.cause_factors.min_cause_factor:
            if proposed.cause_factors.min_cause_factor < Decimal("2.0"):
                recommendations.append(
                    Recommendation(
                        severity="WARNING",
                        message="Cause factor below 2.0 violates Wyckoff methodology. Insufficient accumulation for reliable projections.",
                        category="cause",
                    )
                )
            else:
                recommendations.append(
                    Recommendation(
                        severity="INFO",
                        message="Lowering minimum cause factor will accept shorter accumulation periods with potentially less reliable projections.",
                        category="cause",
                    )
                )

        # Max cause factor decreased
        if proposed.cause_factors.max_cause_factor < current.cause_factors.max_cause_factor:
            recommendations.append(
                Recommendation(
                    severity="INFO",
                    message="Reducing maximum cause factor filters out extended accumulation patterns. May miss high-probability setups.",
                    category="cause",
                )
            )

        return recommendations

    def _check_confidence_changes(
        self, current: SystemConfiguration, proposed: SystemConfiguration
    ) -> list[Recommendation]:
        """Check pattern confidence threshold changes and generate recommendations."""
        recommendations = []

        # Spring confidence decreased
        if (
            proposed.pattern_confidence.min_spring_confidence
            < current.pattern_confidence.min_spring_confidence
        ):
            recommendations.append(
                Recommendation(
                    severity="WARNING",
                    message="Lower spring confidence threshold will increase signals but higher failure rates. Springs are critical entries.",
                    category="confidence",
                )
            )

        # SOS confidence decreased
        if (
            proposed.pattern_confidence.min_sos_confidence
            < current.pattern_confidence.min_sos_confidence
        ):
            recommendations.append(
                Recommendation(
                    severity="WARNING",
                    message="Lower SOS confidence threshold may increase false breakouts. SOS confirms strength.",
                    category="confidence",
                )
            )

        # Any confidence increased (positive)
        if (
            proposed.pattern_confidence.min_spring_confidence
            > current.pattern_confidence.min_spring_confidence
            or proposed.pattern_confidence.min_sos_confidence
            > current.pattern_confidence.min_sos_confidence
        ):
            recommendations.append(
                Recommendation(
                    severity="INFO",
                    message="Increasing confidence thresholds improves signal quality at the cost of fewer opportunities.",
                    category="confidence",
                )
            )

        return recommendations

    def _count_relaxed_thresholds(
        self, current: SystemConfiguration, proposed: SystemConfiguration
    ) -> int:
        """Count number of relaxed (loosened) thresholds.

        Args:
            current: Current configuration
            proposed: Proposed configuration

        Returns:
            Count of relaxed thresholds
        """
        count = 0

        # Volume thresholds relaxed
        if (
            proposed.volume_thresholds.spring_volume_min
            < current.volume_thresholds.spring_volume_min
        ):
            count += 1
        if proposed.volume_thresholds.sos_volume_min < current.volume_thresholds.sos_volume_min:
            count += 1

        # Confidence thresholds relaxed
        if (
            proposed.pattern_confidence.min_spring_confidence
            < current.pattern_confidence.min_spring_confidence
        ):
            count += 1
        if (
            proposed.pattern_confidence.min_sos_confidence
            < current.pattern_confidence.min_sos_confidence
        ):
            count += 1

        # Cause factor relaxed
        if proposed.cause_factors.min_cause_factor < current.cause_factors.min_cause_factor:
            count += 1

        return count

    def _count_tightened_thresholds(
        self, current: SystemConfiguration, proposed: SystemConfiguration
    ) -> int:
        """Count number of tightened (stricter) thresholds.

        Args:
            current: Current configuration
            proposed: Proposed configuration

        Returns:
            Count of tightened thresholds
        """
        count = 0

        # Volume thresholds tightened
        if (
            proposed.volume_thresholds.spring_volume_max
            < current.volume_thresholds.spring_volume_max
        ):
            count += 1
        if proposed.volume_thresholds.sos_volume_min > current.volume_thresholds.sos_volume_min:
            count += 1

        # Confidence thresholds tightened
        if (
            proposed.pattern_confidence.min_spring_confidence
            > current.pattern_confidence.min_spring_confidence
        ):
            count += 1
        if (
            proposed.pattern_confidence.min_sos_confidence
            > current.pattern_confidence.min_sos_confidence
        ):
            count += 1

        # Cause factor tightened
        if proposed.cause_factors.min_cause_factor > current.cause_factors.min_cause_factor:
            count += 1

        return count
