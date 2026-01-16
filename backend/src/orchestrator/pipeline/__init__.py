"""
Pipeline Infrastructure Package.

Provides context and result models for pipeline stages.

Story 18.10.1: Pipeline Base Class and Context
"""

from src.orchestrator.pipeline.context import PipelineContext, PipelineContextBuilder
from src.orchestrator.pipeline.result import PipelineResult

__all__ = [
    "PipelineContext",
    "PipelineContextBuilder",
    "PipelineResult",
]
