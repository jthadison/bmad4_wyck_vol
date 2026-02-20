"""
Tests for Trade Journal API endpoints.

Tests CRUD operations, filtering, user isolation, and Wyckoff checklist.

Uses a custom in-memory SQLite fixture that only creates the journal_entries
table, bypassing the JSONB compatibility issue in the full Base.metadata.

Feature: P2-8 (Trade Journal)
"""

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.dependencies import get_db_session
from src.api.main import app
from src.auth.token_service import TokenService
from src.config import settings
from src.database import get_db
from src.models.journal import JournalEntryModel

pytestmark = pytest.mark.asyncio

# ---- Custom fixtures for journal tests ----


@pytest_asyncio.fixture(scope="function")
async def journal_db_engine():
    """
    Create in-memory SQLite engine with only the journal_entries table.

    Avoids JSONB incompatibility from other models in the full Base metadata.
    """
    # Create a minimal in-memory database with only the journal table
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )

    async with engine.begin() as conn:
        # Create only the journal_entries table
        await conn.run_sync(JournalEntryModel.__table__.create)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(JournalEntryModel.__table__.drop)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def journal_db_session(journal_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for journal tests."""
    session_maker = async_sessionmaker(
        journal_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def journal_client(journal_db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide async HTTP client with journal DB override."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield journal_db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_db_session] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def token_svc() -> TokenService:
    return TokenService(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_token_expire_minutes=settings.jwt_access_token_expire_minutes,
        refresh_token_expire_days=settings.jwt_refresh_token_expire_days,
    )


@pytest.fixture(scope="function")
def journal_auth_headers(token_svc: TokenService) -> dict[str, str]:
    user_id = uuid4()
    token, _ = token_svc.create_token_pair(user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def journal_auth_headers_2(token_svc: TokenService) -> dict[str, str]:
    user_id = uuid4()
    token, _ = token_svc.create_token_pair(user_id)
    return {"Authorization": f"Bearer {token}"}


# ---- Tests ----


class TestCreateJournalEntry:
    """Tests for POST /api/v1/journal."""

    async def test_create_minimal_entry(
        self, journal_client: AsyncClient, journal_auth_headers: dict
    ) -> None:
        """Create a journal entry with only required fields."""
        payload = {
            "symbol": "AAPL",
            "entry_type": "observation",
        }
        response = await journal_client.post(
            "/api/v1/journal", json=payload, headers=journal_auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert data["entry_type"] == "observation"
        assert data["checklist_score"] == 0

    async def test_create_full_entry(
        self, journal_client: AsyncClient, journal_auth_headers: dict
    ) -> None:
        """Create a journal entry with all fields."""
        payload = {
            "symbol": "SPY",
            "entry_type": "pre_trade",
            "notes": "Price has formed a clear Spring below the creek. Volume was low on the break.",
            "emotional_state": "disciplined",
            "wyckoff_checklist": {
                "phase_confirmed": True,
                "volume_confirmed": True,
                "creek_identified": True,
                "pattern_confirmed": True,
            },
        }
        response = await journal_client.post(
            "/api/v1/journal", json=payload, headers=journal_auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["symbol"] == "SPY"
        assert data["entry_type"] == "pre_trade"
        assert data["notes"] == payload["notes"]
        assert data["emotional_state"] == "disciplined"
        assert data["checklist_score"] == 4
        assert data["wyckoff_checklist"]["phase_confirmed"] is True

    async def test_create_entry_with_campaign_link(
        self, journal_client: AsyncClient, journal_auth_headers: dict
    ) -> None:
        """Create journal entry linked to a campaign."""
        campaign_id = str(uuid4())
        payload = {
            "symbol": "TSLA",
            "entry_type": "post_trade",
            "notes": "Trade worked out well - Spring held perfectly.",
            "campaign_id": campaign_id,
            "emotional_state": "confident",
        }
        response = await journal_client.post(
            "/api/v1/journal", json=payload, headers=journal_auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["campaign_id"] == campaign_id

    async def test_symbol_uppercased(
        self, journal_client: AsyncClient, journal_auth_headers: dict
    ) -> None:
        """Symbol should be stored in uppercase."""
        payload = {"symbol": "aapl", "entry_type": "observation"}
        response = await journal_client.post(
            "/api/v1/journal", json=payload, headers=journal_auth_headers
        )
        assert response.status_code == 201
        assert response.json()["symbol"] == "AAPL"

    async def test_requires_authentication(self, journal_client: AsyncClient) -> None:
        """Creating an entry without auth should return 401 or 403."""
        payload = {"symbol": "AAPL", "entry_type": "observation"}
        response = await journal_client.post("/api/v1/journal", json=payload)
        assert response.status_code in (401, 403)


class TestListJournalEntries:
    """Tests for GET /api/v1/journal."""

    async def test_list_empty(
        self, journal_client: AsyncClient, journal_auth_headers: dict
    ) -> None:
        """List should return empty results for new user."""
        response = await journal_client.get("/api/v1/journal", headers=journal_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []
        assert data["pagination"]["total_count"] == 0

    async def test_list_returns_own_entries(
        self, journal_client: AsyncClient, journal_auth_headers: dict
    ) -> None:
        """List should return entries created by the authenticated user."""
        for symbol in ["AAPL", "SPY"]:
            await journal_client.post(
                "/api/v1/journal",
                json={"symbol": symbol, "entry_type": "observation"},
                headers=journal_auth_headers,
            )

        response = await journal_client.get("/api/v1/journal", headers=journal_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total_count"] == 2
        assert len(data["data"]) == 2

    async def test_filter_by_symbol(
        self, journal_client: AsyncClient, journal_auth_headers: dict
    ) -> None:
        """Filter by symbol should return only matching entries."""
        for symbol in ["AAPL", "SPY", "AAPL"]:
            await journal_client.post(
                "/api/v1/journal",
                json={"symbol": symbol, "entry_type": "observation"},
                headers=journal_auth_headers,
            )

        response = await journal_client.get(
            "/api/v1/journal?symbol=AAPL", headers=journal_auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total_count"] == 2
        assert all(e["symbol"] == "AAPL" for e in data["data"])

    async def test_filter_by_entry_type(
        self, journal_client: AsyncClient, journal_auth_headers: dict
    ) -> None:
        """Filter by entry_type should return only matching entries."""
        await journal_client.post(
            "/api/v1/journal",
            json={"symbol": "AAPL", "entry_type": "pre_trade"},
            headers=journal_auth_headers,
        )
        await journal_client.post(
            "/api/v1/journal",
            json={"symbol": "SPY", "entry_type": "post_trade"},
            headers=journal_auth_headers,
        )

        response = await journal_client.get(
            "/api/v1/journal?entry_type=pre_trade", headers=journal_auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total_count"] == 1
        assert data["data"][0]["entry_type"] == "pre_trade"

    async def test_invalid_entry_type_returns_400(
        self, journal_client: AsyncClient, journal_auth_headers: dict
    ) -> None:
        """Invalid entry_type filter should return 400."""
        response = await journal_client.get(
            "/api/v1/journal?entry_type=bad_type", headers=journal_auth_headers
        )
        assert response.status_code == 400

    async def test_user_isolation(
        self,
        journal_client: AsyncClient,
        journal_auth_headers: dict,
        journal_auth_headers_2: dict,
    ) -> None:
        """User A should not see User B's entries."""
        # User 1 creates an entry
        await journal_client.post(
            "/api/v1/journal",
            json={"symbol": "AAPL", "entry_type": "observation"},
            headers=journal_auth_headers,
        )

        # User 2 should see 0 entries
        response = await journal_client.get("/api/v1/journal", headers=journal_auth_headers_2)
        assert response.status_code == 200
        assert response.json()["pagination"]["total_count"] == 0


class TestGetJournalEntry:
    """Tests for GET /api/v1/journal/{id}."""

    async def test_get_existing_entry(
        self, journal_client: AsyncClient, journal_auth_headers: dict
    ) -> None:
        """Should return full entry by ID."""
        create_resp = await journal_client.post(
            "/api/v1/journal",
            json={"symbol": "AAPL", "entry_type": "observation", "notes": "Test note"},
            headers=journal_auth_headers,
        )
        entry_id = create_resp.json()["id"]

        response = await journal_client.get(
            f"/api/v1/journal/{entry_id}", headers=journal_auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == entry_id
        assert data["notes"] == "Test note"

    async def test_get_nonexistent_returns_404(
        self, journal_client: AsyncClient, journal_auth_headers: dict
    ) -> None:
        """Fetching non-existent ID should return 404."""
        response = await journal_client.get(
            f"/api/v1/journal/{uuid4()}", headers=journal_auth_headers
        )
        assert response.status_code == 404

    async def test_get_other_user_entry_returns_404(
        self,
        journal_client: AsyncClient,
        journal_auth_headers: dict,
        journal_auth_headers_2: dict,
    ) -> None:
        """User B should not be able to fetch User A's entry."""
        create_resp = await journal_client.post(
            "/api/v1/journal",
            json={"symbol": "AAPL", "entry_type": "observation"},
            headers=journal_auth_headers,
        )
        entry_id = create_resp.json()["id"]

        response = await journal_client.get(
            f"/api/v1/journal/{entry_id}", headers=journal_auth_headers_2
        )
        assert response.status_code == 404


class TestUpdateJournalEntry:
    """Tests for PUT /api/v1/journal/{id}."""

    async def test_update_notes(
        self, journal_client: AsyncClient, journal_auth_headers: dict
    ) -> None:
        """Should update the notes field."""
        create_resp = await journal_client.post(
            "/api/v1/journal",
            json={"symbol": "AAPL", "entry_type": "pre_trade"},
            headers=journal_auth_headers,
        )
        entry_id = create_resp.json()["id"]

        response = await journal_client.put(
            f"/api/v1/journal/{entry_id}",
            json={"notes": "Updated notes after analysis"},
            headers=journal_auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["notes"] == "Updated notes after analysis"

    async def test_update_wyckoff_checklist(
        self, journal_client: AsyncClient, journal_auth_headers: dict
    ) -> None:
        """Should update the Wyckoff checklist and recompute score."""
        create_resp = await journal_client.post(
            "/api/v1/journal",
            json={"symbol": "AAPL", "entry_type": "pre_trade"},
            headers=journal_auth_headers,
        )
        entry_id = create_resp.json()["id"]

        response = await journal_client.put(
            f"/api/v1/journal/{entry_id}",
            json={
                "wyckoff_checklist": {
                    "phase_confirmed": True,
                    "volume_confirmed": True,
                    "creek_identified": False,
                    "pattern_confirmed": False,
                }
            },
            headers=journal_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["checklist_score"] == 2

    async def test_update_nonexistent_returns_404(
        self, journal_client: AsyncClient, journal_auth_headers: dict
    ) -> None:
        """Updating non-existent entry should return 404."""
        response = await journal_client.put(
            f"/api/v1/journal/{uuid4()}",
            json={"notes": "test"},
            headers=journal_auth_headers,
        )
        assert response.status_code == 404


class TestDeleteJournalEntry:
    """Tests for DELETE /api/v1/journal/{id}."""

    async def test_delete_entry(
        self, journal_client: AsyncClient, journal_auth_headers: dict
    ) -> None:
        """Should delete entry and return 204."""
        create_resp = await journal_client.post(
            "/api/v1/journal",
            json={"symbol": "AAPL", "entry_type": "observation"},
            headers=journal_auth_headers,
        )
        entry_id = create_resp.json()["id"]

        delete_resp = await journal_client.delete(
            f"/api/v1/journal/{entry_id}", headers=journal_auth_headers
        )
        assert delete_resp.status_code == 204

        get_resp = await journal_client.get(
            f"/api/v1/journal/{entry_id}", headers=journal_auth_headers
        )
        assert get_resp.status_code == 404

    async def test_delete_nonexistent_returns_404(
        self, journal_client: AsyncClient, journal_auth_headers: dict
    ) -> None:
        """Deleting non-existent entry should return 404."""
        response = await journal_client.delete(
            f"/api/v1/journal/{uuid4()}", headers=journal_auth_headers
        )
        assert response.status_code == 404


class TestCampaignJournalEntries:
    """Tests for GET /api/v1/journal/campaign/{campaign_id}."""

    async def test_get_campaign_entries(
        self, journal_client: AsyncClient, journal_auth_headers: dict
    ) -> None:
        """Should return all entries linked to a campaign."""
        campaign_id = str(uuid4())

        for entry_type in ["pre_trade", "post_trade"]:
            await journal_client.post(
                "/api/v1/journal",
                json={
                    "symbol": "AAPL",
                    "entry_type": entry_type,
                    "campaign_id": campaign_id,
                },
                headers=journal_auth_headers,
            )

        # Create 1 entry NOT linked to campaign
        await journal_client.post(
            "/api/v1/journal",
            json={"symbol": "SPY", "entry_type": "observation"},
            headers=journal_auth_headers,
        )

        response = await journal_client.get(
            f"/api/v1/journal/campaign/{campaign_id}", headers=journal_auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(e["campaign_id"] == campaign_id for e in data)

    async def test_empty_campaign_returns_empty_list(
        self, journal_client: AsyncClient, journal_auth_headers: dict
    ) -> None:
        """Campaign with no entries should return empty list."""
        response = await journal_client.get(
            f"/api/v1/journal/campaign/{uuid4()}", headers=journal_auth_headers
        )
        assert response.status_code == 200
        assert response.json() == []
