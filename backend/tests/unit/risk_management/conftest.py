"""Pytest configuration for risk management tests."""

from pathlib import Path

import pytest

from src.risk_management.risk_allocator import RiskAllocator


@pytest.fixture
def allocator():
    """Create RiskAllocator instance with default configuration."""
    # Get absolute path to config file
    backend_dir = Path(__file__).parent.parent.parent.parent
    config_path = backend_dir / "config" / "risk_allocation.yaml"
    return RiskAllocator(config_path=str(config_path))
