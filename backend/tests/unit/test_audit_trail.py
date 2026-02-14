"""
Unit Tests for Audit Trail Persistence (Task #2).

Tests:
- Pydantic model validation (AuditTrailCreate, AuditTrailEntry, AuditTrailQuery)
- ORM model field mapping
- Repository insert and query logic (with mocked session)
- Correlation override audit persistence
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError

from src.models.audit_trail import (
    AuditTrailCreate,
    AuditTrailEntry,
    AuditTrailQuery,
    AuditTrailResponse,
)
from src.orm.audit_trail import AuditTrailORM

# ============================================================================
# Pydantic Model Tests
# ============================================================================


class TestAuditTrailCreate:
    """Tests for AuditTrailCreate Pydantic model."""

    def test_valid_creation(self) -> None:
        """Test valid audit trail create model."""
        entry = AuditTrailCreate(
            event_type="CORRELATION_OVERRIDE",
            entity_type="SIGNAL",
            entity_id=str(uuid4()),
            actor="john.doe@example.com",
            action="Manual override of correlation limit",
            metadata={"reason": "Strong Wyckoff setup"},
        )
        assert entry.event_type == "CORRELATION_OVERRIDE"
        assert entry.entity_type == "SIGNAL"
        assert entry.actor == "john.doe@example.com"
        assert entry.metadata["reason"] == "Strong Wyckoff setup"

    def test_default_empty_metadata(self) -> None:
        """Test default empty metadata dict."""
        entry = AuditTrailCreate(
            event_type="CONFIG_CHANGE",
            entity_type="CONFIG",
            entity_id="risk-limits",
            actor="admin",
            action="Updated risk limits",
        )
        assert entry.metadata == {}

    def test_with_correlation_id(self) -> None:
        """Test creation with optional correlation_id."""
        entry = AuditTrailCreate(
            event_type="CORRELATION_OVERRIDE",
            entity_type="SIGNAL",
            entity_id="abc-123",
            actor="admin",
            action="Override",
            correlation_id="corr-trace-001",
        )
        assert entry.correlation_id == "corr-trace-001"

    def test_correlation_id_defaults_none(self) -> None:
        """Test correlation_id defaults to None when omitted."""
        entry = AuditTrailCreate(
            event_type="CONFIG_CHANGE",
            entity_type="CONFIG",
            entity_id="risk-limits",
            actor="admin",
            action="Updated",
        )
        assert entry.correlation_id is None

    def test_max_length_validation(self) -> None:
        """Test max_length constraints."""
        with pytest.raises(Exception):
            AuditTrailCreate(
                event_type="X" * 51,  # exceeds 50
                entity_type="SIGNAL",
                entity_id="123",
                actor="admin",
                action="test",
            )


class TestAuditTrailEntry:
    """Tests for AuditTrailEntry Pydantic model."""

    def test_from_attributes(self) -> None:
        """Test from_attributes config for ORM compatibility."""
        now = datetime.now(UTC)
        entry = AuditTrailEntry(
            id=uuid4(),
            event_type="CORRELATION_OVERRIDE",
            entity_type="SIGNAL",
            entity_id=str(uuid4()),
            actor="admin",
            action="Manual override",
            metadata={},
            created_at=now,
        )
        assert isinstance(entry.id, UUID)
        assert entry.created_at == now

    def test_utc_enforcement_naive_datetime(self) -> None:
        """Test that naive datetimes get UTC timezone."""
        naive = datetime(2026, 2, 13, 10, 0, 0)
        entry = AuditTrailEntry(
            id=uuid4(),
            event_type="TEST",
            entity_type="TEST",
            entity_id="123",
            actor="admin",
            action="test",
            created_at=naive,
        )
        assert entry.created_at.tzinfo is not None

    def test_utc_enforcement_iso_string(self) -> None:
        """Test ISO string parsing with UTC enforcement."""
        entry = AuditTrailEntry(
            id=uuid4(),
            event_type="TEST",
            entity_type="TEST",
            entity_id="123",
            actor="admin",
            action="test",
            created_at="2026-02-13T10:00:00Z",
        )
        assert entry.created_at.tzinfo is not None


class TestAuditTrailQuery:
    """Tests for AuditTrailQuery model."""

    def test_defaults(self) -> None:
        """Test default query parameters."""
        query = AuditTrailQuery()
        assert query.limit == 50
        assert query.offset == 0
        assert query.event_type is None
        assert query.entity_type is None

    def test_all_filters(self) -> None:
        """Test query with all filters including correlation_id."""
        query = AuditTrailQuery(
            event_type="CORRELATION_OVERRIDE",
            entity_type="SIGNAL",
            entity_id="abc-123",
            actor="admin",
            correlation_id="corr-trace-001",
            start_date=datetime(2026, 1, 1, tzinfo=UTC),
            end_date=datetime(2026, 2, 1, tzinfo=UTC),
            limit=100,
            offset=50,
        )
        assert query.event_type == "CORRELATION_OVERRIDE"
        assert query.correlation_id == "corr-trace-001"
        assert query.limit == 100
        assert query.offset == 50


class TestAuditTrailResponse:
    """Tests for AuditTrailResponse model."""

    def test_empty_response(self) -> None:
        """Test empty response."""
        response = AuditTrailResponse(data=[], total_count=0, limit=50, offset=0)
        assert len(response.data) == 0
        assert response.total_count == 0


# ============================================================================
# ORM Model Tests
# ============================================================================


class TestAuditTrailORM:
    """Tests for AuditTrailORM SQLAlchemy model."""

    def test_tablename(self) -> None:
        """Test table name mapping."""
        assert AuditTrailORM.__tablename__ == "audit_trail"

    def test_column_names(self) -> None:
        """Test expected columns exist."""
        columns = {c.name for c in AuditTrailORM.__table__.columns}
        expected = {
            "id",
            "event_type",
            "entity_type",
            "entity_id",
            "actor",
            "action",
            "correlation_id",
            "metadata",
            "created_at",
        }
        assert expected == columns

    def test_metadata_column_mapping(self) -> None:
        """Test audit_metadata Python attr maps to 'metadata' DB column."""
        col = AuditTrailORM.__table__.c.metadata
        assert col.name == "metadata"

    def test_correlation_id_column_nullable(self) -> None:
        """Test correlation_id column is nullable."""
        col = AuditTrailORM.__table__.c.correlation_id
        assert col.nullable is True


# ============================================================================
# Override Function Tests
# ============================================================================


class TestOverrideCorrelationLimitWithAudit:
    """Tests for override_correlation_limit with audit persistence."""

    @pytest.mark.asyncio
    async def test_override_without_session_returns_true(self) -> None:
        """Test override returns True without database session (backward compat)."""
        from src.risk_management.correlation import override_correlation_limit

        result = await override_correlation_limit(
            signal_id=uuid4(),
            approver="admin@test.com",
            reason="Test override",
            session=None,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_override_with_session_persists_audit(self) -> None:
        """Test override persists to audit trail when session provided."""
        from src.risk_management.correlation import override_correlation_limit

        mock_session = AsyncMock()

        with patch(
            "src.repositories.audit_trail_repository.AuditTrailRepository.insert",
            new_callable=AsyncMock,
        ) as mock_insert:
            signal_id = uuid4()
            result = await override_correlation_limit(
                signal_id=signal_id,
                approver="admin@test.com",
                reason="Exceptional setup",
                session=mock_session,
            )

            assert result is True
            mock_insert.assert_called_once()
            call_args = mock_insert.call_args[0][0]
            assert call_args.event_type == "CORRELATION_OVERRIDE"
            assert call_args.entity_type == "SIGNAL"
            assert call_args.entity_id == str(signal_id)
            assert call_args.actor == "admin@test.com"
            assert call_args.metadata["reason"] == "Exceptional setup"

    @pytest.mark.asyncio
    async def test_override_fails_on_operational_error(self) -> None:
        """Test override returns False when DB write fails with OperationalError."""
        from src.risk_management.correlation import override_correlation_limit

        mock_session = AsyncMock()

        with patch(
            "src.repositories.audit_trail_repository.AuditTrailRepository.insert",
            new_callable=AsyncMock,
            side_effect=OperationalError("connection lost", params=None, orig=Exception()),
        ):
            result = await override_correlation_limit(
                signal_id=uuid4(),
                approver="admin@test.com",
                reason="Test override",
                session=mock_session,
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_override_fails_on_integrity_error(self) -> None:
        """Test override returns False when DB write fails with IntegrityError."""
        from src.risk_management.correlation import override_correlation_limit

        mock_session = AsyncMock()

        with patch(
            "src.repositories.audit_trail_repository.AuditTrailRepository.insert",
            new_callable=AsyncMock,
            side_effect=IntegrityError("duplicate key", params=None, orig=Exception()),
        ):
            result = await override_correlation_limit(
                signal_id=uuid4(),
                approver="admin@test.com",
                reason="Test override",
                session=mock_session,
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_override_fails_on_unexpected_exception(self) -> None:
        """Test override returns False on any unexpected DB exception."""
        from src.risk_management.correlation import override_correlation_limit

        mock_session = AsyncMock()

        with patch(
            "src.repositories.audit_trail_repository.AuditTrailRepository.insert",
            new_callable=AsyncMock,
            side_effect=RuntimeError("unexpected failure"),
        ):
            result = await override_correlation_limit(
                signal_id=uuid4(),
                approver="admin@test.com",
                reason="Test override",
                session=mock_session,
            )
            assert result is False
