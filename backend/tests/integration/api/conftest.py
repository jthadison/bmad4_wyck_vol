"""
Shared fixtures for integration API tests.

Provides mocks for background tasks that would make real external API calls.
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_auto_ingest():
    """Mock out the auto-ingest background task to prevent real Yahoo Finance calls during tests."""
    with patch(
        "src.api.routes.scanner._auto_ingest_symbol_data",
        new_callable=AsyncMock,
    ):
        yield
