"""
Phase Analysis Models (Story 13.7 FR7.8)

Pydantic models for phase detection analysis reporting in backtests.
These match the TypeScript types in frontend/src/types/backtest.ts:401-505
"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class PhaseDistribution(BaseModel):
    """Time spent in each Wyckoff phase during backtest."""

    phase: str = Field(..., description="Phase name: A, B, C, D, E")
    bar_count: int = Field(..., ge=0, description="Number of bars in this phase")
    hours: float = Field(..., ge=0, description="Duration in hours")
    percentage: float = Field(..., ge=0, le=100, description="Percentage of total bars")


class PatternPhaseAlignment(BaseModel):
    """Pattern-phase alignment statistics (Story 13.7 AC7.16)."""

    pattern_type: str = Field(..., description="Pattern type: SPRING, SOS, LPS, etc.")
    expected_phases: list[str] = Field(..., description="Expected phases for this pattern")
    aligned_count: int = Field(..., ge=0, description="Count of aligned patterns")
    total_count: int = Field(..., ge=0, description="Total patterns of this type")
    alignment_rate: float = Field(..., ge=0, le=100, description="Alignment rate (0-100)")


class CampaignPhaseTransition(BaseModel):
    """Individual phase transition in a campaign."""

    from_phase: str | None = Field(None, description="Source phase (None if campaign start)")
    to_phase: str = Field(..., description="Destination phase")
    timestamp: str = Field(..., description="ISO 8601 datetime (UTC)")
    bar_index: int = Field(..., ge=0, description="Bar index when transition occurred")


class CampaignPhaseProgression(BaseModel):
    """Phase progression for a single campaign (Story 13.7 AC7.17)."""

    campaign_id: str = Field(..., description="Campaign unique identifier")
    campaign_type: str = Field(..., description="ACCUMULATION or DISTRIBUTION")
    symbol: str = Field(..., description="Trading symbol")
    start_date: str = Field(..., description="ISO 8601 datetime (UTC)")
    end_date: str | None = Field(None, description="ISO 8601 datetime (UTC) or null if ongoing")
    status: str = Field(..., description="COMPLETED, FAILED, or IN_PROGRESS")
    phase_sequence: list[str] = Field(..., description="Ordered list of phases: [A, B, C, D]")
    transitions: list[CampaignPhaseTransition] = Field(
        ..., description="Phase transitions with timestamps"
    )
    completion_stage: str = Field(..., description="Final phase reached")
    total_patterns: int = Field(..., ge=0, description="Patterns detected in campaign")


class WyckoffInsight(BaseModel):
    """Educational insight about phase detection quality (Story 13.7 AC7.18)."""

    category: Literal["DURATION", "ALIGNMENT", "STRUCTURE", "QUALITY"] = Field(
        ..., description="Insight category"
    )
    observation: str = Field(..., description="Factual observation about the data")
    interpretation: str = Field(..., description="Wyckoff methodology interpretation")
    significance: Literal["HIGH", "MEDIUM", "LOW"] = Field(..., description="Insight significance level")


class PhaseDetectionQuality(BaseModel):
    """Phase detection quality metrics."""

    high_confidence_bars: int = Field(..., ge=0, description="Bars with confidence >= 80%")
    medium_confidence_bars: int = Field(..., ge=0, description="Bars with 60-79% confidence")
    low_confidence_bars: int = Field(..., ge=0, description="Bars with < 60% confidence")
    fallback_percentage: float = Field(
        ..., ge=0, le=100, description="Percentage of bars using fallback detection"
    )


class PhaseAnalysisReport(BaseModel):
    """Complete phase analysis report (Story 13.7 FR7.8, AC7.15-7.18).

    Provides comprehensive analysis of phase detection effectiveness including:
    - Time spent in each phase
    - Pattern-phase alignment rates
    - Campaign progression tracking
    - Wyckoff methodology insights
    """

    total_bars_analyzed: int = Field(..., ge=0, description="Total bars in backtest")
    phase_distributions: list[PhaseDistribution] = Field(
        ..., description="Time distribution across phases"
    )
    pattern_alignments: list[PatternPhaseAlignment] = Field(
        ..., description="Pattern-phase alignment statistics"
    )
    campaign_progressions: list[CampaignPhaseProgression] = Field(
        ..., description="Campaign phase progressions"
    )
    insights: list[WyckoffInsight] = Field(..., description="Wyckoff methodology insights")
    overall_alignment_rate: float = Field(
        ..., ge=0, le=100, description="Overall pattern-phase alignment rate (0-100)"
    )
    total_aligned_patterns: int = Field(..., ge=0, description="Total aligned patterns")
    total_patterns: int = Field(..., ge=0, description="Total patterns detected")
    invalid_patterns_rejected: int = Field(..., ge=0, description="Patterns rejected due to misalignment")
    avg_phase_confidence: float = Field(..., ge=0, le=100, description="Average phase confidence")
    phase_transition_errors: int = Field(..., ge=0, description="Invalid phase transitions detected")
    detection_quality: PhaseDetectionQuality = Field(..., description="Phase detection quality metrics")
