"""
Shared utilities module for cross-cutting concerns.

This module contains reusable validation helpers and utilities used across
multiple modules to eliminate code duplication (DRY principle).

Story 18.1: Extract Duplicate Validation Logic
"""

from src.shared.validation_helpers import validate_level_calculator_inputs

__all__ = ["validate_level_calculator_inputs"]
