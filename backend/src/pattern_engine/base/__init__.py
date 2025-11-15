"""
Base classes and interfaces for asset-class-aware pattern detection.

This package provides abstract base classes that enable the BMAD Wyckoff system
to support multiple asset classes (stocks, forex, futures, crypto) with different
volume data quality characteristics.
"""

from src.pattern_engine.base.confidence_scorer import ConfidenceScorer

__all__ = ["ConfidenceScorer"]
