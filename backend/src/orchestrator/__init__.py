"""
Orchestrator module for coordinating Wyckoff pattern detection pipeline.

This module provides the MasterOrchestrator class that coordinates all detectors
and validators through a 7-stage pipeline: Data -> Volume -> Range -> Phase ->
Pattern -> Risk -> Signal.

Components:
- MasterOrchestrator: Main orchestrator coordinating all detectors
- EventBus: In-memory event bus for detector coordination
- OrchestratorContainer: Dependency injection container
- PipelineStage: Abstract base class for pipeline stages
- OrchestratorCache: TTL-based caching for intermediate results

Story 8.1: Master Orchestrator Architecture
"""

from src.orchestrator.cache import OrchestratorCache
from src.orchestrator.config import OrchestratorConfig
from src.orchestrator.container import OrchestratorContainer
from src.orchestrator.event_bus import EventBus
from src.orchestrator.events import (
    BarIngestedEvent,
    Event,
    PatternDetectedEvent,
    PhaseDetectedEvent,
    RangeDetectedEvent,
    VolumeAnalyzedEvent,
)
from src.orchestrator.master_orchestrator import MasterOrchestrator
from src.orchestrator.pipeline_stage import PipelineStage, StageResult
from src.orchestrator.service import (
    analyze_symbol,
    analyze_symbols,
    get_orchestrator,
    get_orchestrator_health,
    orchestrator_lifespan,
    reset_orchestrator,
)

__all__ = [
    "MasterOrchestrator",
    "EventBus",
    "OrchestratorContainer",
    "OrchestratorCache",
    "OrchestratorConfig",
    "PipelineStage",
    "StageResult",
    "Event",
    "BarIngestedEvent",
    "VolumeAnalyzedEvent",
    "RangeDetectedEvent",
    "PhaseDetectedEvent",
    "PatternDetectedEvent",
    # Service functions
    "get_orchestrator",
    "reset_orchestrator",
    "analyze_symbol",
    "analyze_symbols",
    "get_orchestrator_health",
    "orchestrator_lifespan",
]
