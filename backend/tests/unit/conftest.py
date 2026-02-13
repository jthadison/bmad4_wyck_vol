"""
Unit test conftest - minimal setup for isolated unit tests.

Prevents the root conftest from interfering with async mock behavior
by not importing the full FastAPI app.
"""

import asyncio
import sys

import pytest


@pytest.fixture(autouse=True)
def _reset_event_loop_policy():
    """Ensure consistent event loop policy for unit tests."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    yield
