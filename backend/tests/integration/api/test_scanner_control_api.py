"""
Integration Tests for Scanner Control API (Story 20.5a)

Tests for:
- POST /api/v1/scanner/start - Start the background scanner
- POST /api/v1/scanner/stop - Stop the background scanner
- GET /api/v1/scanner/status - Get current scanner control status
- GET /api/v1/scanner/history - Get scan history records
- PATCH /api/v1/scanner/config - Update scanner configuration

Author: Story 20.5a (Scanner Control API)
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.main import app
from src.api.routes.scanner import set_scanner_service
from src.database import get_db
from src.models.scanner_persistence import ScanCycleStatus
from src.orm.scanner import ScannerConfigORM, ScannerHistoryORM

# Test constants
DEFAULT_SCAN_INTERVAL = 300
DEFAULT_BATCH_SIZE = 10
TEST_NEXT_SCAN_SECONDS = 180
TEST_SYMBOLS_COUNT = 12


@pytest.fixture
def mock_scanner_service():
    """Provide a mock SignalScannerService for testing."""
    mock = MagicMock()
    mock.is_running = False
    mock.start = AsyncMock()
    mock.stop = AsyncMock()
    mock.get_status = MagicMock(
        return_value=MagicMock(
            is_running=False,
            current_state="stopped",
            last_cycle_at=None,
            next_scan_in_seconds=None,
            scan_interval_seconds=DEFAULT_SCAN_INTERVAL,
            symbols_count=0,
        )
    )
    return mock


@asynccontextmanager
async def create_test_client(db_session: AsyncSession, scanner_service):
    """
    Helper to create async HTTP client with overrides.

    Reduces duplication in tests that need custom db session setup.
    """
    set_scanner_service(scanner_service)

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def scanner_control_client(db_session: AsyncSession, mock_scanner_service) -> AsyncClient:
    """
    Provide async HTTP client with mocked scanner service.

    Sets up the scanner service singleton and overrides database dependency.
    """
    async with create_test_client(db_session, mock_scanner_service) as client:
        yield client


@pytest.fixture
async def db_with_scanner_config(db_session: AsyncSession) -> AsyncSession:
    """Provide database session with scanner config seeded."""
    config = ScannerConfigORM(
        id=uuid4(),
        scan_interval_seconds=DEFAULT_SCAN_INTERVAL,
        batch_size=DEFAULT_BATCH_SIZE,
        session_filter_enabled=True,
        is_running=False,
        last_cycle_at=None,
        updated_at=datetime.now(UTC),
    )
    db_session.add(config)
    await db_session.commit()
    return db_session


@pytest.fixture
async def scanner_client_with_config(
    db_with_scanner_config: AsyncSession, mock_scanner_service
) -> AsyncClient:
    """
    Provide async HTTP client with scanner config in database.
    """
    async with create_test_client(db_with_scanner_config, mock_scanner_service) as client:
        yield client


@pytest.mark.asyncio
class TestStartScanner:
    """Test POST /api/v1/scanner/start endpoint (AC1)."""

    async def test_starts_scanner_when_stopped(
        self, scanner_client_with_config: AsyncClient, mock_scanner_service
    ):
        """Should start scanner and return 200 with started status."""
        mock_scanner_service.is_running = False

        response = await scanner_client_with_config.post("/api/v1/scanner/start")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert data["message"] == "Scanner started successfully"
        assert data["is_running"] is True
        mock_scanner_service.start.assert_called_once()

    async def test_idempotent_when_already_running(
        self, scanner_client_with_config: AsyncClient, mock_scanner_service
    ):
        """Should return already_running status when scanner is running."""
        mock_scanner_service.is_running = True

        response = await scanner_client_with_config.post("/api/v1/scanner/start")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "already_running"
        assert data["message"] == "Scanner is already running"
        assert data["is_running"] is True
        mock_scanner_service.start.assert_not_called()


@pytest.mark.asyncio
class TestStopScanner:
    """Test POST /api/v1/scanner/stop endpoint (AC2)."""

    async def test_stops_scanner_when_running(
        self, scanner_client_with_config: AsyncClient, mock_scanner_service
    ):
        """Should stop scanner and return 200 with stopped status."""
        mock_scanner_service.is_running = True

        response = await scanner_client_with_config.post("/api/v1/scanner/stop")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "stopped"
        assert data["message"] == "Scanner stopped successfully"
        assert data["is_running"] is False
        mock_scanner_service.stop.assert_called_once()

    async def test_idempotent_when_already_stopped(
        self, scanner_client_with_config: AsyncClient, mock_scanner_service
    ):
        """Should return already_stopped status when scanner is not running."""
        mock_scanner_service.is_running = False

        response = await scanner_client_with_config.post("/api/v1/scanner/stop")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "already_stopped"
        assert data["message"] == "Scanner is already stopped"
        assert data["is_running"] is False
        mock_scanner_service.stop.assert_not_called()


@pytest.mark.asyncio
class TestGetScannerStatus:
    """Test GET /api/v1/scanner/status endpoint (AC3)."""

    async def test_returns_status_when_running(
        self, scanner_client_with_config: AsyncClient, mock_scanner_service
    ):
        """Should return complete status when scanner is running."""
        last_cycle = datetime(2024, 1, 15, 10, 30, tzinfo=UTC)
        mock_scanner_service.is_running = True
        mock_scanner_service.get_status.return_value = MagicMock(
            is_running=True,
            current_state="waiting",
            last_cycle_at=last_cycle,
            next_scan_in_seconds=TEST_NEXT_SCAN_SECONDS,
            scan_interval_seconds=DEFAULT_SCAN_INTERVAL,
            symbols_count=TEST_SYMBOLS_COUNT,
        )

        response = await scanner_client_with_config.get("/api/v1/scanner/status")

        assert response.status_code == 200
        data = response.json()
        assert data["is_running"] is True
        assert data["current_state"] == "waiting"
        assert data["next_scan_in_seconds"] == TEST_NEXT_SCAN_SECONDS
        assert data["scan_interval_seconds"] == DEFAULT_SCAN_INTERVAL
        assert data["session_filter_enabled"] is True

    async def test_returns_status_when_stopped(
        self, scanner_client_with_config: AsyncClient, mock_scanner_service
    ):
        """Should return status with null next_scan when stopped."""
        mock_scanner_service.is_running = False
        mock_scanner_service.get_status.return_value = MagicMock(
            is_running=False,
            current_state="stopped",
            last_cycle_at=None,
            next_scan_in_seconds=None,
            scan_interval_seconds=DEFAULT_SCAN_INTERVAL,
            symbols_count=0,
        )

        response = await scanner_client_with_config.get("/api/v1/scanner/status")

        assert response.status_code == 200
        data = response.json()
        assert data["is_running"] is False
        assert data["current_state"] == "stopped"
        assert data["next_scan_in_seconds"] is None


@pytest.mark.asyncio
class TestGetScannerHistory:
    """Test GET /api/v1/scanner/history endpoint (AC4)."""

    async def test_returns_empty_history(
        self, scanner_client_with_config: AsyncClient, mock_scanner_service
    ):
        """Should return empty list when no history exists."""
        response = await scanner_client_with_config.get("/api/v1/scanner/history")

        assert response.status_code == 200
        assert response.json() == []

    async def test_returns_history_records(
        self,
        db_with_scanner_config: AsyncSession,
        mock_scanner_service,
    ):
        """Should return history records ordered by cycle_started_at descending."""
        # Add history records
        for i in range(3):
            history = ScannerHistoryORM(
                id=uuid4(),
                cycle_started_at=datetime(2024, 1, 15, 10 + i, 0, tzinfo=UTC),
                cycle_ended_at=datetime(2024, 1, 15, 10 + i, 5, tzinfo=UTC),
                symbols_scanned=10,
                signals_generated=i,
                errors_count=0,
                status=ScanCycleStatus.COMPLETED.value,
            )
            db_with_scanner_config.add(history)
        await db_with_scanner_config.commit()

        async with create_test_client(db_with_scanner_config, mock_scanner_service) as client:
            response = await client.get("/api/v1/scanner/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        # Check each record has required fields
        for record in data:
            assert "id" in record
            assert "cycle_started_at" in record
            assert "cycle_ended_at" in record
            assert "symbols_scanned" in record
            assert "signals_generated" in record
            assert "errors_count" in record
            assert "status" in record

        # Verify descending order (newest first)
        assert data[0]["signals_generated"] == 2
        assert data[1]["signals_generated"] == 1
        assert data[2]["signals_generated"] == 0

    async def test_respects_limit_parameter(
        self,
        db_with_scanner_config: AsyncSession,
        mock_scanner_service,
    ):
        """Should respect limit query parameter."""
        # Add 10 history records
        for i in range(10):
            history = ScannerHistoryORM(
                id=uuid4(),
                cycle_started_at=datetime(2024, 1, 15, i, 0, tzinfo=UTC),
                cycle_ended_at=datetime(2024, 1, 15, i, 5, tzinfo=UTC),
                symbols_scanned=10,
                signals_generated=0,
                errors_count=0,
                status=ScanCycleStatus.COMPLETED.value,
            )
            db_with_scanner_config.add(history)
        await db_with_scanner_config.commit()

        async with create_test_client(db_with_scanner_config, mock_scanner_service) as client:
            response = await client.get("/api/v1/scanner/history?limit=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5

    async def test_returns_all_when_limit_exceeds_count(
        self,
        db_with_scanner_config: AsyncSession,
        mock_scanner_service,
    ):
        """Should return all records when limit exceeds available."""
        # Add 5 history records
        for i in range(5):
            history = ScannerHistoryORM(
                id=uuid4(),
                cycle_started_at=datetime(2024, 1, 15, i, 0, tzinfo=UTC),
                cycle_ended_at=datetime(2024, 1, 15, i, 5, tzinfo=UTC),
                symbols_scanned=10,
                signals_generated=0,
                errors_count=0,
                status=ScanCycleStatus.COMPLETED.value,
            )
            db_with_scanner_config.add(history)
        await db_with_scanner_config.commit()

        async with create_test_client(db_with_scanner_config, mock_scanner_service) as client:
            response = await client.get("/api/v1/scanner/history?limit=100")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5


@pytest.mark.asyncio
class TestPatchScannerConfig:
    """Test PATCH /api/v1/scanner/config endpoint (AC5, AC6)."""

    async def test_updates_config_when_stopped(
        self, scanner_client_with_config: AsyncClient, mock_scanner_service
    ):
        """Should update configuration when scanner is stopped."""
        mock_scanner_service.is_running = False

        response = await scanner_client_with_config.patch(
            "/api/v1/scanner/config",
            json={
                "scan_interval_seconds": 600,
                "batch_size": 20,
                "session_filter_enabled": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["scan_interval_seconds"] == 600
        assert data["batch_size"] == 20
        assert data["session_filter_enabled"] is False

    async def test_rejects_when_running(
        self, scanner_client_with_config: AsyncClient, mock_scanner_service
    ):
        """Should return 409 when scanner is running."""
        mock_scanner_service.is_running = True

        response = await scanner_client_with_config.patch(
            "/api/v1/scanner/config",
            json={"scan_interval_seconds": 600},
        )

        assert response.status_code == 409
        assert "running" in response.json()["detail"].lower()

    async def test_validates_scan_interval_minimum(
        self, scanner_client_with_config: AsyncClient, mock_scanner_service
    ):
        """Should return 422 when scan_interval_seconds < 60."""
        mock_scanner_service.is_running = False

        response = await scanner_client_with_config.patch(
            "/api/v1/scanner/config",
            json={"scan_interval_seconds": 30},
        )

        assert response.status_code == 422

    async def test_validates_scan_interval_maximum(
        self, scanner_client_with_config: AsyncClient, mock_scanner_service
    ):
        """Should return 422 when scan_interval_seconds > 3600."""
        mock_scanner_service.is_running = False

        response = await scanner_client_with_config.patch(
            "/api/v1/scanner/config",
            json={"scan_interval_seconds": 7200},
        )

        assert response.status_code == 422

    async def test_validates_batch_size_minimum(
        self, scanner_client_with_config: AsyncClient, mock_scanner_service
    ):
        """Should return 422 when batch_size < 1."""
        mock_scanner_service.is_running = False

        response = await scanner_client_with_config.patch(
            "/api/v1/scanner/config",
            json={"batch_size": 0},
        )

        assert response.status_code == 422

    async def test_validates_batch_size_maximum(
        self, scanner_client_with_config: AsyncClient, mock_scanner_service
    ):
        """Should return 422 when batch_size > 50."""
        mock_scanner_service.is_running = False

        response = await scanner_client_with_config.patch(
            "/api/v1/scanner/config",
            json={"batch_size": 100},
        )

        assert response.status_code == 422


@pytest.mark.asyncio
class TestScannerServiceNotInitialized:
    """Test behavior when scanner service is not initialized."""

    async def test_returns_503_when_service_not_set(self, db_with_scanner_config: AsyncSession):
        """Should return 503 when scanner service is not initialized."""
        # Clear any existing scanner service
        from src.api.routes import scanner as scanner_module

        scanner_module._scanner_service = None

        async def override_get_db():
            yield db_with_scanner_config

        app.dependency_overrides[get_db] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/scanner/start")

        app.dependency_overrides.clear()

        assert response.status_code == 503
        assert "not initialized" in response.json()["detail"].lower()


@pytest.mark.asyncio
class TestOpenAPISchema:
    """Test OpenAPI schema includes scanner control endpoints."""

    async def test_scanner_control_endpoints_in_schema(
        self, scanner_client_with_config: AsyncClient
    ):
        """Scanner control endpoints should be in OpenAPI schema."""
        response = await scanner_client_with_config.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        paths = schema.get("paths", {})

        # Check all scanner control endpoints are present
        assert "/api/v1/scanner/start" in paths
        assert "post" in paths["/api/v1/scanner/start"]

        assert "/api/v1/scanner/stop" in paths
        assert "post" in paths["/api/v1/scanner/stop"]

        assert "/api/v1/scanner/status" in paths
        assert "get" in paths["/api/v1/scanner/status"]

        assert "/api/v1/scanner/history" in paths
        assert "get" in paths["/api/v1/scanner/history"]

        assert "/api/v1/scanner/config" in paths
        assert "patch" in paths["/api/v1/scanner/config"]

    async def test_response_models_in_schema(self, scanner_client_with_config: AsyncClient):
        """Response models should be in OpenAPI schema."""
        response = await scanner_client_with_config.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        schemas = schema.get("components", {}).get("schemas", {})

        assert "ScannerActionResponse" in schemas
        assert "ScannerControlStatusResponse" in schemas
        assert "ScannerHistoryResponse" in schemas
        assert "ScannerConfigUpdateRequest" in schemas
