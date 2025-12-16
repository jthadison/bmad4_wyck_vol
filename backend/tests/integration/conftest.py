"""
Shared fixtures for integration tests.

Provides integration-specific fixtures.
Database session and async client fixtures are inherited from parent conftest.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.notification_repository import NotificationRepository


@pytest.fixture
async def notification_repository(db_session: AsyncSession) -> NotificationRepository:
    """Provide a NotificationRepository instance for tests."""
    return NotificationRepository(db_session)
