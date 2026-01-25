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
    config.addinivalue_line("markers", "extended: mark test as extended backtest for CI only")


# =============================
# Story 12.10: New Mock and Fixture Additions
# =============================


@pytest.fixture
def mock_data_feed():
    """
    Provide MockPolygonAdapter instance for testing.

    Returns a mock data feed that returns fixture OHLCV data
    without making actual API calls.
    """
    from tests.mocks.mock_polygon_adapter import MockPolygonAdapter

    return MockPolygonAdapter()


@pytest.fixture
def mock_broker():
    """
    Provide MockBrokerAdapter instance for testing.

    Returns a mock broker that simulates order submission/fills
    without making actual broker API calls.
    """
    from tests.mocks.mock_broker_adapter import MockBrokerAdapter

    return MockBrokerAdapter()


@pytest.fixture
def sample_ohlcv_bars():
    """
    Provide sample OHLCV bar fixtures for testing.

    Returns a dictionary of fixture scenarios:
    - spring_pattern: 100 bars with Spring pattern at bar 50
    - sos_pattern: 100 bars with SOS pattern at bar 60
    - utad_pattern: 100 bars with UTAD pattern at bar 70
    - false_spring: 100 bars with false Spring (high-volume breakdown)
    """
    from tests.fixtures.ohlcv_bars import (
        false_spring_bars,
        sos_pattern_bars,
        spring_pattern_bars,
        utad_pattern_bars,
    )

    return {
        "spring_pattern": spring_pattern_bars(),
        "sos_pattern": sos_pattern_bars(),
        "utad_pattern": utad_pattern_bars(),
        "false_spring": false_spring_bars(),
    }


@pytest.fixture
def edge_case_bars():
    """
    Provide edge case OHLCV bar fixtures for testing.

    Returns a dictionary of edge case scenarios:
    - zero_volume: Bar with volume = 0
    - gap_up: Bar with gap up from previous close
    - gap_down: Bar with gap down from previous close
    - extreme_spread: Bar with spread > 5x average
    - missing_bars: Sequence with missing timestamps
    - doji: Bar with open == close
    - narrow_spread: Bar with very narrow spread
    - extreme_volume: Bar with volume > 10x average
    """
    from tests.fixtures.edge_cases import (
        doji_bar,
        extreme_spread_bar,
        extreme_volume_bar,
        gap_down_bar,
        gap_up_bar,
        missing_bars_sequence,
        narrow_spread_bar,
        zero_volume_bar,
    )

    return {
        "zero_volume": zero_volume_bar(),
        "gap_up": gap_up_bar(),
        "gap_down": gap_down_bar(),
        "extreme_spread": extreme_spread_bar(),
        "missing_bars": missing_bars_sequence(),
        "doji": doji_bar(),
        "narrow_spread": narrow_spread_bar(),
        "extreme_volume": extreme_volume_bar(),
    }


@pytest.fixture
def test_db():
    """
    Provide test database session (alias for db_session).

    This is an alias fixture for consistency with pytest-postgresql naming.
    """
    # Return the db_session fixture
    # Note: This will be overridden in integration tests that use PostgreSQL
    return None  # Placeholder - use db_session directly


# =============================
# Issue #232: TradeSignal Factory Fixtures
# =============================


@pytest.fixture
def create_test_trade_signal():
    """
    Provide factory function to create valid TradeSignal instances.

    Creates TradeSignal instances with all required fields populated,
    suitable for use in unit tests.

    Usage:
        ```python
        def test_something(create_test_trade_signal):
            signal = create_test_trade_signal(pattern_type="SPRING")
            signal2 = create_test_trade_signal(
                pattern_type="SOS",
                confidence_score=82,
                phase="D"
            )
        ```

    Returns:
        Callable that creates TradeSignal instances with sensible defaults
    """
    from datetime import UTC, datetime
    from decimal import Decimal

    from src.models.signal import (
        ConfidenceComponents,
        TargetLevels,
        TradeSignal,
    )
    from src.models.validation import ValidationChain

    def _create_signal(
        symbol: str = "AAPL",
        pattern_type: str = "SPRING",
        phase: str = "C",
        timeframe: str = "1d",
        entry_price: Decimal | None = None,
        stop_loss: Decimal | None = None,
        primary_target: Decimal | None = None,
        position_size: Decimal | None = None,
        risk_amount: Decimal | None = None,
        confidence_score: int = 85,
        asset_class: str = "STOCK",
        **kwargs,
    ) -> TradeSignal:
        """
        Create a valid TradeSignal with sensible defaults.

        All prices are set to create valid entry/stop/target relationships.
        """
        # Default prices based on pattern type
        if entry_price is None:
            entry_price = Decimal("150.00")
        if stop_loss is None:
            stop_loss = Decimal("148.00")
        if primary_target is None:
            primary_target = Decimal("156.00")
        if position_size is None:
            position_size = Decimal("100") if asset_class == "STOCK" else Decimal("0.10")
        if risk_amount is None:
            risk_amount = Decimal("200.00")

        # Calculate r_multiple
        r_multiple = (primary_target - entry_price) / (entry_price - stop_loss)

        # Calculate notional_value
        notional_value = position_size * entry_price

        # Create confidence components that match the overall score
        # Formula: overall = pattern*0.5 + phase*0.3 + volume*0.2
        # ConfidenceComponents requires overall_confidence >= 70
        effective_score = max(confidence_score, 70)

        # Use the overall score to derive components
        pattern_confidence = min(effective_score + 5, 100)
        phase_confidence = max(effective_score - 2, 70)
        volume_confidence = max(effective_score - 3, 70)
        # Recalculate to ensure it matches
        calculated_overall = int(
            pattern_confidence * 0.5 + phase_confidence * 0.3 + volume_confidence * 0.2
        )
        # Ensure minimum of 70 for ConfidenceComponents validation
        calculated_overall = max(calculated_overall, 70)

        confidence_components = ConfidenceComponents(
            pattern_confidence=pattern_confidence,
            phase_confidence=phase_confidence,
            volume_confidence=volume_confidence,
            overall_confidence=calculated_overall,
        )

        # Build kwargs for TradeSignal
        signal_kwargs = {
            "id": uuid4(),
            "symbol": symbol,
            "asset_class": asset_class,
            "pattern_type": pattern_type,
            "phase": phase,
            "timeframe": timeframe,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "target_levels": TargetLevels(primary_target=primary_target),
            "position_size": position_size,
            "position_size_unit": "SHARES" if asset_class == "STOCK" else "LOTS",
            "notional_value": notional_value,
            "risk_amount": risk_amount,
            "r_multiple": r_multiple,
            "confidence_score": calculated_overall,
            "confidence_components": confidence_components,
            "validation_chain": ValidationChain(pattern_id=uuid4()),
            "timestamp": datetime.now(UTC),
        }

        # Add forex-specific fields
        if asset_class == "FOREX":
            signal_kwargs["leverage"] = Decimal("50.0")
            signal_kwargs["margin_requirement"] = notional_value / Decimal("50.0")

        # Override with any additional kwargs
        signal_kwargs.update(kwargs)

        return TradeSignal(**signal_kwargs)

    return _create_signal


# =============================
# Story 19.2: Bar Window Test Fixtures
# =============================


@pytest.fixture
def create_test_bar():
    """
    Provide factory function to create test OHLCVBar instances.

    Returns a callable that generates OHLCVBar instances with sequential
    timestamps for testing bar window management.

    Usage:
        ```python
        def test_something(create_test_bar):
            bar = create_test_bar("AAPL", 0)  # First bar
            bar2 = create_test_bar("AAPL", 1)  # Second bar (1 minute later)
        ```

    Returns:
        Callable[[str, int], OHLCVBar]: Factory function that takes symbol and index
    """
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    from src.models.ohlcv import OHLCVBar

    def _create_bar(symbol: str, index: int) -> OHLCVBar:
        """
        Create a test OHLCVBar for testing.

        Args:
            symbol: Stock symbol
            index: Bar index (used to generate unique timestamps)

        Returns:
            OHLCVBar instance
        """
        # Start at Jan 1, 2024, 9:30 AM and add 1 minute per index
        base_timestamp = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)
        timestamp = base_timestamp + timedelta(minutes=index)

        return OHLCVBar(
            id=uuid4(),
            symbol=symbol,
            timeframe="1m",
            timestamp=timestamp,
            open=Decimal("150.00"),
            high=Decimal("151.00"),
            low=Decimal("149.00"),
            close=Decimal("150.50"),
            volume=1000000,
            spread=Decimal("2.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
            created_at=datetime.now(UTC),
        )

    return _create_bar
