"""
Orchestrator module for coordinating Wyckoff pattern detection pipeline.

This module provides the MasterOrchestrator class that coordinates all detectors
and validators through a 7-stage pipeline: Data -> Volume -> Range -> Phase ->
Pattern -> Risk -> Signal.

Components:
- MasterOrchestrator: Main orchestrator coordinating all detectors
- MasterOrchestratorFacade: Slim facade delegating to PipelineCoordinator
- EventBus: In-memory event bus for detector coordination
- OrchestratorContainer: Dependency injection container
- PipelineStage: Abstract base class for pipeline stages
- OrchestratorCache: TTL-based caching for intermediate results
- PipelineCoordinator: Coordinates stage execution

Services:
- ForexSessionService: Forex trading session detection
- PortfolioMonitor: Portfolio context building
- EmergencyExitService: Emergency exit handling

Story 8.1: Master Orchestrator Architecture
Story 18.10.5: Services Extraction and Orchestrator Facade
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
from src.orchestrator.orchestrator_facade import MasterOrchestratorFacade
from src.orchestrator.pipeline import PipelineContext, PipelineCoordinator, PipelineResult
from src.orchestrator.pipeline_stage import PipelineStage, StageResult
from src.orchestrator.service import (
    analyze_symbol,
    analyze_symbols,
    get_orchestrator,
    get_orchestrator_health,
    orchestrator_lifespan,
    reset_orchestrator,
)
from src.orchestrator.services import (
    EmergencyExitService,
    ForexSessionService,
    PortfolioMonitor,
)

__all__ = [
    # Core orchestrator
    "MasterOrchestrator",
    "MasterOrchestratorFacade",
    # Event bus
    "EventBus",
    # Container and config
    "OrchestratorContainer",
    "OrchestratorCache",
    "OrchestratorConfig",
    # Pipeline infrastructure
    "PipelineStage",
    "PipelineContext",
    "PipelineCoordinator",
    "PipelineResult",
    "StageResult",
    # Events
    "Event",
    "BarIngestedEvent",
    "VolumeAnalyzedEvent",
    "RangeDetectedEvent",
    "PhaseDetectedEvent",
    "PatternDetectedEvent",
    # Services
    "ForexSessionService",
    "PortfolioMonitor",
    "EmergencyExitService",
    # Service functions
    "get_orchestrator",
    "reset_orchestrator",
    "analyze_symbol",
    "analyze_symbols",
    "get_orchestrator_health",
    "orchestrator_lifespan",
]
