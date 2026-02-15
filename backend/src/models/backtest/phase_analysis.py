"""
Phase Analysis Models (Story 13.7, Task #12)

Pydantic models for phase detection analysis reporting.
Matches frontend TypeScript interfaces in frontend/src/types/backtest.ts:401-509

Author: Backend Developer 2, Story 13.7
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

# ==========================================================================================
# Phase Distribution Models (FR7.8)
# ==========================================================================================


class PhaseDistribution(BaseModel):
    """
    Phase distribution data tracking time spent in each Wyckoff phase.

    Corresponds to TypeScript interface: PhaseDistribution
    """

    phase: Literal["A", "B", "C", "D", "E", "UNKNOWN"] = Field(
        ..., description="Wyckoff phase identifier"
    )
    bar_count: int = Field(..., ge=0, description="Number of bars in this phase")
    percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of total bars (0-100)")
    hours: float = Field(..., ge=0.0, description="Duration in hours")
    description: str = Field(..., description="Human-readable phase description")

    model_config = {"json_encoders": {float: lambda v: round(v, 2)}}


# ==========================================================================================
# Pattern-Phase Alignment Models (FR7.8)
# ==========================================================================================


class PatternPhaseAlignment(BaseModel):
    """
    Pattern-phase alignment statistics tracking how well patterns align with expected phases.

    Corresponds to TypeScript interface: PatternPhaseAlignment
    """

    pattern_type: str = Field(..., description="Pattern type (SPRING, SOS, LPS, etc.)")
    expected_phases: list[str] = Field(..., description="Expected Wyckoff phases for this pattern")
    aligned_count: int = Field(..., ge=0, description="Patterns detected in correct phase")
    total_count: int = Field(..., ge=0, description="Total patterns detected")
    alignment_rate: float = Field(..., ge=0.0, le=100.0, description="Alignment percentage (0-100)")

    model_config = {"json_encoders": {float: lambda v: round(v, 2)}}


# ==========================================================================================
# Campaign Phase Progression Models (FR7.3, FR7.8)
# ==========================================================================================


class CampaignPhaseTransition(BaseModel):
    """
    Individual phase transition within a campaign timeline.

    Corresponds to TypeScript interface: CampaignPhaseTransition
    """

    from_phase: Optional[str] = Field(None, description="Starting phase (null for campaign start)")
    to_phase: str = Field(..., description="Target phase")
    timestamp: str = Field(..., description="Transition timestamp (ISO 8601)")
    bar_index: int = Field(..., ge=0, description="Bar index when transition occurred")
    trigger_pattern: Optional[str] = Field(None, description="Pattern that caused transition")
    is_valid: bool = Field(..., description="Whether transition follows Wyckoff rules")

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class CampaignPhaseProgression(BaseModel):
    """
    Complete phase timeline for a single Wyckoff campaign.

    Corresponds to TypeScript interface: CampaignPhaseProgression
    """

    campaign_id: str = Field(..., description="Campaign identifier")
    campaign_type: Literal["ACCUMULATION", "DISTRIBUTION"] = Field(..., description="Campaign type")
    start_timestamp: str = Field(..., description="Campaign start (ISO 8601)")
    end_timestamp: Optional[str] = Field(
        None, description="Campaign end (ISO 8601, null if IN_PROGRESS)"
    )
    total_bars: int = Field(..., ge=0, description="Total bars in campaign")
    total_hours: float = Field(..., ge=0.0, description="Total duration in hours")

    # Phase breakdown
    phase_durations: dict[str, int] = Field(
        default_factory=dict, description="Phase -> bar count mapping"
    )
    phase_percentages: dict[str, float] = Field(
        default_factory=dict, description="Phase -> percentage mapping"
    )

    # Timeline
    transitions: list[CampaignPhaseTransition] = Field(
        default_factory=list, description="Phase transition timeline"
    )
    invalid_transitions: int = Field(default=0, ge=0, description="Count of invalid transitions")

    # Quality metrics
    quality_score: float = Field(
        ..., ge=0.0, le=100.0, description="Campaign quality score (0-100)"
    )
    followed_wyckoff_sequence: bool = Field(
        ..., description="Whether campaign followed valid sequence"
    )
    completion_stage: str = Field(..., description="Campaign completion stage description")

    model_config = {"json_encoders": {float: lambda v: round(v, 2)}}


# ==========================================================================================
# Wyckoff Insights Models (FR7.8)
# ==========================================================================================


class WyckoffInsight(BaseModel):
    """
    Educational interpretations of phase analysis patterns.

    Corresponds to TypeScript interface: WyckoffInsight
    """

    category: Literal["DURATION", "ALIGNMENT", "STRUCTURE", "QUALITY"] = Field(
        ..., description="Insight category"
    )
    observation: str = Field(..., description="Factual observation about the data")
    interpretation: str = Field(..., description="Wyckoff methodology interpretation")
    significance: Literal["HIGH", "MEDIUM", "LOW"] = Field(
        ..., description="Insight significance level"
    )


# ==========================================================================================
# Detection Quality Models (Devils-advocate feedback)
# ==========================================================================================


class DetectionQuality(BaseModel):
    """
    Phase detection confidence distribution.

    Tracks the quality of phase detection across confidence levels.
    Used to display warnings when fallback detection is too prevalent.

    Corresponds to TypeScript interface: DetectionQuality
    """

    high_confidence_bars: int = Field(..., ge=0, description="Bars with phase confidence >= 80%")
    medium_confidence_bars: int = Field(
        ..., ge=0, description="Bars with 60% <= phase confidence < 80%"
    )
    low_confidence_bars: int = Field(
        ..., ge=0, description="Bars with phase confidence < 60% (fallback detection)"
    )
    fallback_percentage: float = Field(
        ..., ge=0.0, le=100.0, description="Percentage of bars using fallback detection (0-100)"
    )

    model_config = {"json_encoders": {float: lambda v: round(v, 2)}}


# ==========================================================================================
# Comprehensive Phase Analysis Report (FR7.8)
# ==========================================================================================


class PhaseAnalysisReport(BaseModel):
    """
    Comprehensive phase detection analysis for backtest results.

    This is the main model that gets added to BacktestResult.
    Corresponds to TypeScript interface: PhaseAnalysisReport
    """

    # Overall phase distribution
    total_bars_analyzed: int = Field(..., ge=0, description="Total bars analyzed in backtest")
    phase_distributions: list[PhaseDistribution] = Field(
        default_factory=list, description="Time spent in each phase"
    )

    # Pattern-phase alignment
    pattern_alignments: list[PatternPhaseAlignment] = Field(
        default_factory=list, description="Pattern-phase alignment statistics"
    )
    overall_alignment_rate: float = Field(
        ..., ge=0.0, le=100.0, description="Overall alignment percentage (0-100)"
    )
    total_aligned_patterns: int = Field(..., ge=0, description="Total patterns in correct phase")
    total_patterns: int = Field(..., ge=0, description="Total patterns detected")
    invalid_patterns_rejected: int = Field(
        ..., ge=0, description="Patterns rejected due to phase mismatch"
    )

    # Campaign phase progressions
    campaign_progressions: list[CampaignPhaseProgression] = Field(
        default_factory=list, description="Per-campaign phase timelines"
    )

    # Wyckoff insights
    insights: list[WyckoffInsight] = Field(
        default_factory=list, description="Auto-generated Wyckoff educational insights"
    )

    # Detection quality (Devils-advocate feedback)
    detection_quality: DetectionQuality = Field(
        ..., description="Phase detection confidence distribution"
    )

    # Summary statistics
    avg_phase_confidence: float = Field(
        ..., ge=0.0, le=100.0, description="Average phase detection confidence (0-100)"
    )
    phase_transition_errors: int = Field(
        ..., ge=0, description="Invalid phase transitions detected"
    )

    model_config = {"json_encoders": {float: lambda v: round(v, 2)}}


# ==========================================================================================
# Helper Constants
# ==========================================================================================

# Phase descriptions for reporting
PHASE_DESCRIPTIONS: dict[str, str] = {
    "A": "Climactic selling action",
    "B": "Range building, accumulation",
    "C": "Testing phase, spring detection",
    "D": "Breakout initiation, early markup",
    "E": "Markup continuation",
    "UNKNOWN": "Ambiguous market structure",
}

# Expected phases for each pattern type (from phase_validator.py)
PATTERN_EXPECTED_PHASES: dict[str, list[str]] = {
    "SPRING": ["C"],
    "SOS": ["D", "E"],
    "LPS": ["D", "E"],
    "SECONDARY_TEST": ["B"],
    "SELLING_CLIMAX": ["A"],
    "AUTOMATIC_RALLY": ["A", "B"],
}
