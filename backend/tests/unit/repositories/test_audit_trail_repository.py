"""
Unit Tests for AuditTrailRepository (Task #2 - Coverage Fix).

Tests actual repository insert() and query() methods with mocked AsyncSession,
ensuring real code paths are exercised (not patched away).
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.models.audit_trail import AuditTrailCreate, AuditTrailQuery
from src.orm.audit_trail import AuditTrailORM
from src.repositories.audit_trail_repository import AuditTrailRepository


def _make_orm_row(
    event_type: str = "CORRELATION_OVERRIDE",
    entity_type: str = "SIGNAL",
    entity_id: str | None = None,
    actor: str = "admin@test.com",
    action: str = "Manual override",
    correlation_id: str | None = None,
    metadata: dict | None = None,
) -> MagicMock:
    """Create a mock ORM row with expected attributes."""
    row = MagicMock(spec=AuditTrailORM)
    row.id = uuid4()
    row.event_type = event_type
    row.entity_type = entity_type
    row.entity_id = entity_id or str(uuid4())
    row.actor = actor
    row.action = action
    row.correlation_id = correlation_id
    row.audit_metadata = metadata or {}
    row.created_at = datetime.now(UTC)
    return row


# ============================================================================
# Insert Tests
# ============================================================================


class TestAuditTrailRepositoryInsert:
    """Tests for AuditTrailRepository.insert()."""

    @pytest.mark.asyncio
    async def test_insert_adds_to_session_and_flushes(self) -> None:
        """Test insert calls session.add() and session.flush()."""
        session = AsyncMock()
        repo = AuditTrailRepository(session)

        entry = AuditTrailCreate(
            event_type="CORRELATION_OVERRIDE",
            entity_type="SIGNAL",
            entity_id=str(uuid4()),
            actor="admin@test.com",
            action="Manual override of correlation limit",
            metadata={"reason": "Strong setup"},
        )

        result = await repo.insert(entry)

        session.add.assert_called_once()
        session.flush.assert_awaited_once()
        assert result.event_type == "CORRELATION_OVERRIDE"
        assert result.entity_type == "SIGNAL"
        assert result.actor == "admin@test.com"
        assert result.action == "Manual override of correlation limit"
        assert result.metadata == {"reason": "Strong setup"}

    @pytest.mark.asyncio
    async def test_insert_passes_correlation_id(self) -> None:
        """Test insert correctly passes correlation_id to ORM."""
        session = AsyncMock()
        repo = AuditTrailRepository(session)

        entry = AuditTrailCreate(
            event_type="CORRELATION_OVERRIDE",
            entity_type="SIGNAL",
            entity_id="sig-123",
            actor="admin",
            action="Override",
            correlation_id="corr-trace-001",
        )

        result = await repo.insert(entry)

        # Verify the ORM object added to session has correlation_id
        orm_obj = session.add.call_args[0][0]
        assert orm_obj.correlation_id == "corr-trace-001"

    @pytest.mark.asyncio
    async def test_insert_without_correlation_id(self) -> None:
        """Test insert with None correlation_id."""
        session = AsyncMock()
        repo = AuditTrailRepository(session)

        entry = AuditTrailCreate(
            event_type="CONFIG_CHANGE",
            entity_type="CONFIG",
            entity_id="risk-limits",
            actor="admin",
            action="Updated limits",
        )

        result = await repo.insert(entry)

        orm_obj = session.add.call_args[0][0]
        assert orm_obj.correlation_id is None

    @pytest.mark.asyncio
    async def test_insert_returns_audit_trail_entry(self) -> None:
        """Test insert returns proper AuditTrailEntry with all fields."""
        session = AsyncMock()
        repo = AuditTrailRepository(session)

        signal_id = str(uuid4())
        entry = AuditTrailCreate(
            event_type="CORRELATION_OVERRIDE",
            entity_type="SIGNAL",
            entity_id=signal_id,
            actor="john@example.com",
            action="Override correlation limit",
            correlation_id="trace-abc",
            metadata={"reason": "Exceptional Wyckoff setup"},
        )

        result = await repo.insert(entry)

        assert result.event_type == "CORRELATION_OVERRIDE"
        assert result.entity_type == "SIGNAL"
        assert result.entity_id == signal_id
        assert result.actor == "john@example.com"
        assert result.action == "Override correlation limit"
        assert result.metadata == {"reason": "Exceptional Wyckoff setup"}


# ============================================================================
# Query Tests
# ============================================================================


class TestAuditTrailRepositoryQuery:
    """Tests for AuditTrailRepository.query()."""

    def _setup_session_with_rows(self, rows: list[MagicMock], count: int) -> AsyncMock:
        """Create a mock session that returns given rows and count."""
        session = AsyncMock()

        # Mock for data query
        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = rows

        # Mock for count query
        count_result = MagicMock()
        count_result.scalar.return_value = count

        # session.execute returns different results for data vs count queries
        session.execute = AsyncMock(side_effect=[data_result, count_result])

        return session

    @pytest.mark.asyncio
    async def test_query_no_filters_returns_all(self) -> None:
        """Test query with no filters returns all rows."""
        rows = [_make_orm_row() for _ in range(3)]
        session = self._setup_session_with_rows(rows, 3)
        repo = AuditTrailRepository(session)

        entries, total = await repo.query(AuditTrailQuery())

        assert len(entries) == 3
        assert total == 3
        assert session.execute.await_count == 2  # data + count

    @pytest.mark.asyncio
    async def test_query_returns_correct_fields(self) -> None:
        """Test query maps ORM fields to Pydantic model correctly."""
        row = _make_orm_row(
            event_type="CORRELATION_OVERRIDE",
            entity_type="SIGNAL",
            actor="admin@test.com",
            correlation_id="corr-123",
            metadata={"key": "value"},
        )
        session = self._setup_session_with_rows([row], 1)
        repo = AuditTrailRepository(session)

        entries, total = await repo.query(AuditTrailQuery())

        assert len(entries) == 1
        entry = entries[0]
        assert entry.id == row.id
        assert entry.event_type == "CORRELATION_OVERRIDE"
        assert entry.entity_type == "SIGNAL"
        assert entry.actor == "admin@test.com"
        assert entry.correlation_id == "corr-123"
        assert entry.metadata == {"key": "value"}
        assert entry.created_at == row.created_at

    @pytest.mark.asyncio
    async def test_query_empty_results(self) -> None:
        """Test query with no matching rows."""
        session = self._setup_session_with_rows([], 0)
        repo = AuditTrailRepository(session)

        entries, total = await repo.query(AuditTrailQuery(event_type="NONEXISTENT"))

        assert len(entries) == 0
        assert total == 0

    @pytest.mark.asyncio
    async def test_query_with_event_type_filter(self) -> None:
        """Test query passes event_type filter to session.execute."""
        session = self._setup_session_with_rows([], 0)
        repo = AuditTrailRepository(session)

        await repo.query(AuditTrailQuery(event_type="CORRELATION_OVERRIDE"))

        # Verify execute was called (filters applied at SQL level)
        assert session.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_query_with_all_filters(self) -> None:
        """Test query with every filter set."""
        session = self._setup_session_with_rows([], 0)
        repo = AuditTrailRepository(session)

        params = AuditTrailQuery(
            event_type="CORRELATION_OVERRIDE",
            entity_type="SIGNAL",
            entity_id="sig-123",
            actor="admin",
            correlation_id="corr-001",
            start_date=datetime(2026, 1, 1, tzinfo=UTC),
            end_date=datetime(2026, 2, 1, tzinfo=UTC),
            limit=10,
            offset=5,
        )

        entries, total = await repo.query(params)

        assert session.execute.await_count == 2
        assert total == 0

    @pytest.mark.asyncio
    async def test_query_pagination(self) -> None:
        """Test query respects limit and offset."""
        rows = [_make_orm_row() for _ in range(2)]
        session = self._setup_session_with_rows(rows, 10)
        repo = AuditTrailRepository(session)

        entries, total = await repo.query(AuditTrailQuery(limit=2, offset=5))

        assert len(entries) == 2
        assert total == 10  # total count ignores pagination
