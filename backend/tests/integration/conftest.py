"""
Shared fixtures for integration tests.

Provides database session and FastAPI test client fixtures
for integration tests across all modules.
"""

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.main import app
from src.database import async_session_maker


@pytest.fixture(scope="module")
def event_loop():
    """Create event loop for async tests (Windows compatibility)."""
    import sys

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_session() -> AsyncSession:
    """Provide a database session for tests."""
    async with async_session_maker() as session:
        yield session


@pytest.fixture
async def async_client() -> AsyncClient:
    """Provide an async HTTP client for API tests."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
