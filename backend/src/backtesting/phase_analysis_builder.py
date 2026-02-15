"""
Phase Analysis Builder (Story 13.7 FR7.8)

Builds PhaseAnalysisReport from backtest execution data including:
- Phase time distributions
- Pattern-phase alignment rates
- Campaign phase progressions
- Wyckoff methodology insights
"""

from collections import defaultdict
from datetime import datetime
from typing import TypedDict

from src.models.backtest.phase_analysis import (
    CampaignPhaseProgression,
    CampaignPhaseTransition,
    PatternPhaseAlignment,
    PhaseAnalysisReport,
    PhaseDetectionQuality,
    PhaseDistribution,
    WyckoffInsight,
)
from src.models.wyckoff import WyckoffPhase


# Story 13.7 P1-002: Campaign data contract for PhaseAnalysisBuilder
class CampaignData(TypedDict, total=False):
    """
    Type definition for campaign data expected by PhaseAnalysisBuilder.

    Used to provide type safety when building campaign phase progressions
    from backtest execution data.

    Required Fields:
    ----------------
    campaign_id : str
        Unique campaign identifier

    Optional Fields:
    ----------------
    campaign_type : str
        Campaign type (ACCUMULATION or DISTRIBUTION), defaults to "ACCUMULATION"
    symbol : str
        Trading symbol, defaults to ""
    start_date : str
        ISO 8601 datetime (UTC), defaults to ""
    end_date : str | None
        ISO 8601 datetime (UTC) or None if ongoing
    status : str
        Campaign status (COMPLETED, FAILED, IN_PROGRESS), defaults to "IN_PROGRESS"
    total_patterns : int
        Number of patterns detected in campaign, defaults to 0
    """

    campaign_id: str  # Required
    campaign_type: str
    symbol: str
    start_date: str
    end_date: str | None
    status: str
    total_patterns: int


# Story 13.7 AC7.14: Pattern-phase expectations from phase_validator.py
PATTERN_PHASE_EXPECTATIONS = {
    "SPRING": ["C"],
    "SOS": ["D", "E"],
    "LPS": ["D", "E"],
    "UTAD": ["C", "D"],
    "SC": ["A"],
    "AR": ["A"],
}


class PhaseAnalysisBuilder:
    """Builds phase analysis reports from backtest execution data."""

    def __init__(self):
        self.phase_bars = defaultdict(int)  # phase -> bar count
        self.phase_confidence_sum = 0.0
        self.phase_confidence_count = 0
        self.high_confidence_bars = 0
        self.medium_confidence_bars = 0
        self.low_confidence_bars = 0
        self.fallback_bars = 0
        self.total_bars = 0
        self.phase_transition_errors = 0

        # Pattern tracking
        self.pattern_counts = defaultdict(int)  # pattern_type -> count
        self.aligned_patterns = defaultdict(int)  # pattern_type -> aligned count

        # Campaign tracking
        self.campaign_transitions = defaultdict(list)  # campaign_id -> [(from, to, timestamp, idx)]

    def record_bar_phase(
        self, phase: WyckoffPhase | None, confidence: float, is_fallback: bool = False
    ) -> None:
        """Record phase classification for a single bar."""
        self.total_bars += 1

        if phase:
            self.phase_bars[phase.name] += 1

        if confidence >= 80:
            self.high_confidence_bars += 1
        elif confidence >= 60:
            self.medium_confidence_bars += 1
        else:
            self.low_confidence_bars += 1

        if is_fallback:
            self.fallback_bars += 1

        self.phase_confidence_sum += confidence
        self.phase_confidence_count += 1

    def record_pattern(
        self, pattern_type: str, detected_phase: str | None, is_aligned: bool
    ) -> None:
        """Record pattern detection and phase alignment."""
        self.pattern_counts[pattern_type] += 1
        if is_aligned:
            self.aligned_patterns[pattern_type] += 1

    def record_phase_transition(
        self,
        campaign_id: str,
        from_phase: str | None,
        to_phase: str,
        timestamp: datetime,
        bar_index: int,
    ) -> None:
        """Record a phase transition for a campaign."""
        self.campaign_transitions[campaign_id].append((from_phase, to_phase, timestamp, bar_index))

    def record_transition_error(self) -> None:
        """Record an invalid phase transition."""
        self.phase_transition_errors += 1

    def build_report(
        self, campaigns: list[CampaignData], timeframe_hours: float = 24.0
    ) -> PhaseAnalysisReport:
        """Build complete phase analysis report.

        Args:
            campaigns: List of campaign data conforming to CampaignData TypedDict contract
            timeframe_hours: Hours per bar for time calculations (default 24 for daily)

        Returns:
            Complete PhaseAnalysisReport with all analysis sections
        """
        # Calculate phase distributions
        phase_distributions = self._build_phase_distributions(timeframe_hours)

        # Calculate pattern-phase alignments
        pattern_alignments = self._build_pattern_alignments()

        # Build campaign progressions
        campaign_progressions = self._build_campaign_progressions(campaigns)

        # Generate Wyckoff insights
        insights = self._generate_insights(phase_distributions, pattern_alignments)

        # Calculate overall metrics
        total_patterns = sum(self.pattern_counts.values())
        total_aligned = sum(self.aligned_patterns.values())
        overall_alignment_rate = (
            (total_aligned / total_patterns * 100) if total_patterns > 0 else 0.0
        )
        avg_phase_confidence = (
            self.phase_confidence_sum / self.phase_confidence_count
            if self.phase_confidence_count > 0
            else 0.0
        )

        detection_quality = PhaseDetectionQuality(
            high_confidence_bars=self.high_confidence_bars,
            medium_confidence_bars=self.medium_confidence_bars,
            low_confidence_bars=self.low_confidence_bars,
            fallback_percentage=(
                (self.fallback_bars / self.total_bars * 100) if self.total_bars > 0 else 0.0
            ),
        )

        return PhaseAnalysisReport(
            total_bars_analyzed=self.total_bars,
            phase_distributions=phase_distributions,
            pattern_alignments=pattern_alignments,
            campaign_progressions=campaign_progressions,
            insights=insights,
            overall_alignment_rate=overall_alignment_rate,
            total_aligned_patterns=total_aligned,
            total_patterns=total_patterns,
            invalid_patterns_rejected=total_patterns - total_aligned,
            avg_phase_confidence=avg_phase_confidence,
            phase_transition_errors=self.phase_transition_errors,
            detection_quality=detection_quality,
        )

    def _build_phase_distributions(self, timeframe_hours: float) -> list[PhaseDistribution]:
        """Build phase distribution analysis."""
        distributions = []
        for phase_name, bar_count in self.phase_bars.items():
            percentage = (bar_count / self.total_bars * 100) if self.total_bars > 0 else 0.0
            hours = bar_count * timeframe_hours
            distributions.append(
                PhaseDistribution(
                    phase=phase_name, bar_count=bar_count, hours=hours, percentage=percentage
                )
            )

        # Sort by phase order: A, B, C, D, E
        phase_order = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}
        distributions.sort(key=lambda d: phase_order.get(d.phase, 99))
        return distributions

    def _build_pattern_alignments(self) -> list[PatternPhaseAlignment]:
        """Build pattern-phase alignment statistics."""
        alignments = []
        for pattern_type in self.pattern_counts.keys():
            total_count = self.pattern_counts[pattern_type]
            aligned_count = self.aligned_patterns.get(pattern_type, 0)
            alignment_rate = (aligned_count / total_count * 100) if total_count > 0 else 0.0
            expected_phases = PATTERN_PHASE_EXPECTATIONS.get(pattern_type, [])

            alignments.append(
                PatternPhaseAlignment(
                    pattern_type=pattern_type,
                    expected_phases=expected_phases,
                    aligned_count=aligned_count,
                    total_count=total_count,
                    alignment_rate=alignment_rate,
                )
            )

        # Sort by alignment rate (lowest first to highlight issues)
        alignments.sort(key=lambda a: a.alignment_rate)
        return alignments

    def _build_campaign_progressions(
        self, campaigns: list[CampaignData]
    ) -> list[CampaignPhaseProgression]:
        """
        Build campaign phase progression tracking.

        Parameters:
        -----------
        campaigns : list[CampaignData]
            List of campaign dictionaries conforming to CampaignData TypedDict contract

        Returns:
        --------
        list[CampaignPhaseProgression]
            Campaign phase progression models for reporting
        """
        progressions = []
        for campaign in campaigns:
            campaign_id = campaign.get("campaign_id", "")
            transitions_data = self.campaign_transitions.get(campaign_id, [])

            # Build transitions list
            transitions = []
            phase_sequence = []
            for from_phase, to_phase, timestamp, bar_index in transitions_data:
                transitions.append(
                    CampaignPhaseTransition(
                        from_phase=from_phase,
                        to_phase=to_phase,
                        timestamp=timestamp.isoformat()
                        if isinstance(timestamp, datetime)
                        else timestamp,
                        bar_index=bar_index,
                    )
                )
                if to_phase not in phase_sequence:
                    phase_sequence.append(to_phase)

            completion_stage = phase_sequence[-1] if phase_sequence else "A"

            progressions.append(
                CampaignPhaseProgression(
                    campaign_id=campaign_id,
                    campaign_type=campaign.get("campaign_type", "ACCUMULATION"),
                    symbol=campaign.get("symbol", ""),
                    start_date=campaign.get("start_date", ""),
                    end_date=campaign.get("end_date"),
                    status=campaign.get("status", "IN_PROGRESS"),
                    phase_sequence=phase_sequence,
                    transitions=transitions,
                    completion_stage=completion_stage,
                    total_patterns=campaign.get("total_patterns", 0),
                )
            )

        return progressions

    def _generate_insights(
        self, distributions: list[PhaseDistribution], alignments: list[PatternPhaseAlignment]
    ) -> list[WyckoffInsight]:
        """Generate Wyckoff methodology insights."""
        insights = []

        # Insight: Low phase confidence
        if self.phase_confidence_count > 0:
            avg_confidence = self.phase_confidence_sum / self.phase_confidence_count
            if avg_confidence < 70:
                insights.append(
                    WyckoffInsight(
                        category="QUALITY",
                        observation=f"Average phase confidence is {avg_confidence:.1f}%, below ideal threshold of 70%",
                        interpretation="Review market structure clarity - choppy or sideways markets reduce phase detection confidence",
                        significance="MEDIUM",
                    )
                )

        # Insight: Poor pattern alignment
        for alignment in alignments:
            if alignment.alignment_rate < 80 and alignment.total_count >= 5:
                insights.append(
                    WyckoffInsight(
                        category="ALIGNMENT",
                        observation=f"{alignment.pattern_type} alignment rate is {alignment.alignment_rate:.1f}% "
                        f"({alignment.aligned_count}/{alignment.total_count} aligned)",
                        interpretation=f"Review {alignment.pattern_type} detection logic - patterns should appear in phases {alignment.expected_phases}",
                        significance="MEDIUM",
                    )
                )

        # Insight: Phase transition errors
        if self.phase_transition_errors > 0:
            insights.append(
                WyckoffInsight(
                    category="STRUCTURE",
                    observation=f"Detected {self.phase_transition_errors} invalid phase transitions",
                    interpretation="Review phase transition validation logic in phase_validator.py",
                    significance="HIGH",
                )
            )

        # Insight: Excessive fallback usage
        if self.total_bars > 0:
            fallback_pct = (self.fallback_bars / self.total_bars) * 100
            if fallback_pct > 30:
                insights.append(
                    WyckoffInsight(
                        category="QUALITY",
                        observation=f"Fallback phase detection used for {fallback_pct:.1f}% of bars",
                        interpretation="High fallback usage indicates unclear market structure or detector issues",
                        significance="MEDIUM",
                    )
                )

        # Add positive insight if everything looks good
        if not insights:
            insights.append(
                WyckoffInsight(
                    category="QUALITY",
                    observation="Phase detection quality is excellent with high alignment rates and confidence",
                    interpretation="Continue monitoring - current detection parameters are well-calibrated for this market",
                    significance="LOW",
                )
            )

        return insights
