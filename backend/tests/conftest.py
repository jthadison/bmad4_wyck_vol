"""
Pytest configuration and fixtures for backend tests.

Provides shared fixtures for database sessions, authentication, and test clients.
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.main import app
from src.auth.token_service import TokenService
from src.config import settings
from src.database import Base, get_db

# =============================
# Database Fixtures
# =============================


@pytest.fixture(scope="session")
def event_loop():
    """
    Create event loop for async tests.

    Uses session scope to avoid creating new loop for each test.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """
    Create test database engine.

    Uses in-memory SQLite for fast tests. Override with TEST_DATABASE_URL
    environment variable for integration tests with real database.
    """
    # Use in-memory SQLite for unit tests
    test_db_url = getattr(settings, "test_database_url", "sqlite+aiosqlite:///:memory:")

    engine = create_async_engine(
        test_db_url,
        echo=False,
        future=True,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide database session for tests.

    Each test gets a fresh session that's rolled back after the test.
    """
    session_maker = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Provide async HTTP client for API testing.

    Overrides the database dependency to use test database.
    """

    # Override database dependency
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Clean up
    app.dependency_overrides.clear()


# =============================
# Authentication Fixtures
# =============================


@pytest.fixture
def token_service() -> TokenService:
    """
    Provide TokenService instance for tests.

    Uses settings from config for consistency with production behavior.
    """
    return TokenService(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_token_expire_minutes=settings.jwt_access_token_expire_minutes,
        refresh_token_expire_days=settings.jwt_refresh_token_expire_days,
    )


@pytest.fixture
def test_user_id() -> UUID:
    """
    Provide test user ID.

    Generates a new UUID for each test to ensure isolation.
    """
    return uuid4()


@pytest.fixture
def test_user_id_2() -> UUID:
    """
    Provide second test user ID for isolation tests.

    Used to verify that User A cannot access User B's data.
    """
    return uuid4()


@pytest.fixture
def auth_token(token_service: TokenService, test_user_id: UUID) -> str:
    """
    Generate valid JWT access token for test user.

    Creates a real token using the TokenService, allowing tests to verify
    the full authentication flow including token decoding.

    Returns:
        str: JWT access token
    """
    access_token, _ = token_service.create_token_pair(test_user_id)
    return access_token


@pytest.fixture
def auth_token_2(token_service: TokenService, test_user_id_2: UUID) -> str:
    """
    Generate valid JWT access token for second test user.

    Used for user isolation tests.

    Returns:
        str: JWT access token for second user
    """
    access_token, _ = token_service.create_token_pair(test_user_id_2)
    return access_token


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    """
    Provide authentication headers with Bearer token.

    Use this fixture to make authenticated API requests in tests.

    Example:
        ```python
        async def test_get_campaigns(async_client, auth_headers):
            response = await async_client.get("/api/v1/campaigns", headers=auth_headers)
            assert response.status_code == 200
        ```

    Returns:
        dict: Headers dictionary with Authorization header
    """
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def auth_headers_2(auth_token_2: str) -> dict[str, str]:
    """
    Provide authentication headers for second test user.

    Used for user isolation tests.

    Returns:
        dict: Headers dictionary with Authorization header for second user
    """
    return {"Authorization": f"Bearer {auth_token_2}"}


# =============================
# Mock Data Fixtures
# =============================


@pytest.fixture
def mock_campaign_data(test_user_id: UUID) -> dict[str, Any]:
    """
    Provide mock campaign data for tests.

    Returns a dictionary with campaign attributes that can be used
    to create CampaignModel instances in tests.
    """
    from datetime import UTC, datetime
    from decimal import Decimal

    return {
        "id": uuid4(),
        "user_id": test_user_id,
        "symbol": "AAPL",
        "timeframe": "1D",
        "trading_range_id": uuid4(),
        "status": "ACTIVE",
        "total_allocation": Decimal("10000.00"),
        "current_risk": Decimal("3000.00"),
        "created_at": datetime.now(UTC),
    }


@pytest.fixture
def mock_trading_range_data() -> dict[str, Any]:
    """
    Provide mock trading range data for tests.

    Returns a dictionary with trading range attributes.
    """
    from datetime import UTC, datetime
    from decimal import Decimal

    return {
        "id": uuid4(),
        "symbol": "AAPL",
        "timeframe": "1D",
        "range_low": Decimal("148.00"),
        "range_high": Decimal("156.00"),
        "start_timestamp": datetime.now(UTC),
        "status": "ACTIVE",
    }


@pytest.fixture
def mock_position_data() -> dict[str, Any]:
    """
    Provide mock position data for tests.

    Returns a dictionary with position attributes.
    """
    from datetime import UTC, datetime
    from decimal import Decimal

    return {
        "id": uuid4(),
        "signal_id": uuid4(),
        "entry_pattern": "SPRING",
        "entry_price": Decimal("150.00"),
        "shares": 20,
        "position_size": Decimal("3000.00"),
        "stop_loss": Decimal("148.50"),
        "status": "FILLED",
        "created_at": datetime.now(UTC),
    }


# =============================
# Pytest Configuration
# =============================


def pytest_configure(config):
    """
    Configure pytest with custom markers.
    """
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
