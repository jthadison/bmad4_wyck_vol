"""
Pipeline Infrastructure Package.

Provides context, result, and coordination for pipeline stages.

Story 18.10.1: Pipeline Base Class and Context
Story 18.10.5: Services Extraction and Orchestrator Facade (AC4)
"""

from src.orchestrator.pipeline.context import PipelineContext, PipelineContextBuilder
from src.orchestrator.pipeline.coordinator import CoordinatorResult, PipelineCoordinator
from src.orchestrator.pipeline.result import PipelineResult

__all__ = [
    "CoordinatorResult",
    "PipelineContext",
    "PipelineContextBuilder",
    "PipelineCoordinator",
    "PipelineResult",
]
