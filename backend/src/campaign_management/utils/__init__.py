"""
Campaign Management Utilities Package (Story 18.5)

Provides shared utility functions for campaign management:
- Campaign ID generation and parsing
- Position creation from signals

This module extracts duplicate utility code from campaign_manager.py
and service.py into reusable shared functions.
"""

from .campaign_id import generate_campaign_id, parse_campaign_id
from .position_factory import create_position_from_signal

__all__ = [
    "generate_campaign_id",
    "parse_campaign_id",
    "create_position_from_signal",
]
