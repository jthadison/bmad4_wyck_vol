"""
Pipeline Stages Package.

Provides pipeline stages for the analysis pipeline.

Story 18.10.1: Pipeline Base Class and Context (AC1)
Story 18.10.2: Volume, Range, and Phase Analysis Stages (AC1-5)
Story 18.10.3: Pattern Detection and Validation Stages (AC1-5)
Story 18.10.4: Signal Generation and Risk Assessment Stages (AC1-5)
"""

from src.orchestrator.stages.base import PipelineStage
from src.orchestrator.stages.pattern_detection_stage import (
    DetectorRegistry,
    PatternDetectionStage,
)
from src.orchestrator.stages.phase_detection_stage import PhaseDetectionStage
from src.orchestrator.stages.range_detection_stage import RangeDetectionStage
from src.orchestrator.stages.risk_assessment_stage import RiskAssessmentStage
from src.orchestrator.stages.signal_generation_stage import SignalGenerationStage
from src.orchestrator.stages.validation_stage import ValidationResults, ValidationStage
from src.orchestrator.stages.volume_analysis_stage import VolumeAnalysisStage

__all__ = [
    "PipelineStage",
    "DetectorRegistry",
    "PatternDetectionStage",
    "PhaseDetectionStage",
    "RangeDetectionStage",
    "RiskAssessmentStage",
    "SignalGenerationStage",
    "ValidationResults",
    "ValidationStage",
    "VolumeAnalysisStage",
]
