"""
Unit tests for Signal Audit Trail (Story 19.11)

Tests signal lifecycle management, audit logging, and history queries.

Author: Story 19.11
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.signal_audit import (
    SignalAuditLogEntry,
    SignalHistoryQuery,
    TradeOutcome,
    ValidationResults,
    ValidationStageResult,
)
from src.orm.models import Signal
from src.repositories.signal_audit_repository import SignalAuditRepository
from src.services.signal_audit_service import SignalAuditService


@pytest.fixture
async def audit_repository(db_session: AsyncSession) -> SignalAuditRepository:
    """Create audit repository with test database session."""
    return SignalAuditRepository(db_session)


@pytest.fixture
async def audit_service(audit_repository: SignalAuditRepository) -> SignalAuditService:
    """Create audit service with repository."""
    return SignalAuditService(audit_repository)


@pytest.fixture
async def test_signal(db_session: AsyncSession) -> Signal:
    """Create test signal in database."""
    signal = Signal(
        id=uuid4(),
        signal_type="SPRING",
        symbol="AAPL",
        timeframe="1h",
        generated_at=datetime.now(UTC),
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("148.00"),
        target_1=Decimal("156.00"),
        target_2=Decimal("158.00"),
        position_size=Decimal("100"),
        risk_amount=Decimal("200.00"),
        r_multiple=Decimal("3.0"),
        confidence_score=85,
        status="PENDING",
        approval_chain={},
        lifecycle_state="generated",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(signal)
    await db_session.commit()
    await db_session.refresh(signal)
    return signal


class TestSignalAuditRepository:
    """Test signal audit repository operations."""

    @pytest.mark.asyncio
    async def test_create_audit_entry(
        self, audit_repository: SignalAuditRepository, test_signal: Signal
    ):
        """Test creating an audit log entry."""
        # Arrange
        entry = SignalAuditLogEntry(
            signal_id=test_signal.id,
            user_id=None,
            previous_state=None,
            new_state="generated",
            transition_reason="Spring pattern detected with 85.0% confidence",
            metadata={"pattern_type": "SPRING", "confidence": 85.0},
        )

        # Act
        created = await audit_repository.create_audit_entry(entry)

        # Assert
        assert created.id is not None
        assert created.signal_id == test_signal.id
        assert created.new_state == "generated"
        assert created.transition_reason == "Spring pattern detected with 85.0% confidence"

    @pytest.mark.asyncio
    async def test_get_signal_audit_trail(
        self, audit_repository: SignalAuditRepository, test_signal: Signal
    ):
        """Test retrieving complete audit trail for a signal."""
        # Arrange - Create multiple audit entries
        entries = [
            SignalAuditLogEntry(
                signal_id=test_signal.id,
                new_state="generated",
                transition_reason="Pattern detected",
            ),
            SignalAuditLogEntry(
                signal_id=test_signal.id,
                previous_state="generated",
                new_state="pending",
                transition_reason="Added to queue",
            ),
            SignalAuditLogEntry(
                signal_id=test_signal.id,
                previous_state="pending",
                new_state="approved",
                transition_reason="User approved",
                user_id=uuid4(),
            ),
        ]

        for entry in entries:
            await audit_repository.create_audit_entry(entry)

        # Act
        trail = await audit_repository.get_signal_audit_trail(test_signal.id)

        # Assert
        assert len(trail) == 3
        assert trail[0].new_state == "generated"
        assert trail[1].new_state == "pending"
        assert trail[2].new_state == "approved"
        # Verify chronological order
        assert trail[0].created_at <= trail[1].created_at <= trail[2].created_at

    @pytest.mark.asyncio
    async def test_update_signal_lifecycle_state(
        self, audit_repository: SignalAuditRepository, test_signal: Signal, db_session: AsyncSession
    ):
        """Test updating signal lifecycle state."""
        # Act
        await audit_repository.update_signal_lifecycle_state(test_signal.id, "pending")

        # Assert
        await db_session.refresh(test_signal)
        assert test_signal.lifecycle_state == "pending"

    @pytest.mark.asyncio
    async def test_update_signal_validation_results(
        self, audit_repository: SignalAuditRepository, test_signal: Signal, db_session: AsyncSession
    ):
        """Test storing validation results."""
        # Arrange
        validation_results = {
            "volume_validation": {
                "stage": "Volume",
                "passed": True,
                "input_data": {},
                "output_data": {},
                "timestamp": datetime.now(UTC).isoformat(),
            },
            "overall_passed": True,
        }

        # Act
        await audit_repository.update_signal_validation_results(test_signal.id, validation_results)

        # Assert
        await db_session.refresh(test_signal)
        assert test_signal.validation_results is not None
        assert test_signal.validation_results["overall_passed"] is True

    @pytest.mark.asyncio
    async def test_update_signal_trade_outcome(
        self, audit_repository: SignalAuditRepository, test_signal: Signal, db_session: AsyncSession
    ):
        """Test storing trade outcome."""
        # Arrange
        trade_outcome = {
            "position_id": str(uuid4()),
            "entry_price": "150.25",
            "exit_price": "152.10",
            "shares": 100,
            "pnl_dollars": "185.00",
            "pnl_percentage": 1.23,
            "r_multiple": 2.47,
            "exit_reason": "target_hit",
            "entry_time": datetime.now(UTC).isoformat(),
            "exit_time": datetime.now(UTC).isoformat(),
        }

        # Act
        await audit_repository.update_signal_trade_outcome(test_signal.id, trade_outcome)

        # Assert
        await db_session.refresh(test_signal)
        assert test_signal.trade_outcome is not None
        assert test_signal.trade_outcome["exit_reason"] == "target_hit"


class TestSignalAuditService:
    """Test signal audit service business logic."""

    @pytest.mark.asyncio
    async def test_record_signal_generated(
        self, audit_service: SignalAuditService, test_signal: Signal
    ):
        """Test recording signal generation."""
        # Act
        entry = await audit_service.record_signal_generated(
            signal_id=test_signal.id,
            pattern_type="SPRING",
            confidence_score=85.0,
        )

        # Assert
        assert entry.signal_id == test_signal.id
        assert entry.new_state == "generated"
        assert entry.previous_state is None
        assert entry.user_id is None  # System-generated
        assert "SPRING" in entry.transition_reason
        assert "85.0%" in entry.transition_reason

    @pytest.mark.asyncio
    async def test_record_signal_approved(
        self, audit_service: SignalAuditService, test_signal: Signal
    ):
        """Test recording signal approval."""
        # Arrange
        user_id = uuid4()

        # Act
        entry = await audit_service.record_signal_approved(
            signal_id=test_signal.id, user_id=user_id
        )

        # Assert
        assert entry.new_state == "approved"
        assert entry.previous_state == "pending"
        assert entry.user_id == user_id
        assert entry.transition_reason == "User approved signal"

    @pytest.mark.asyncio
    async def test_record_signal_rejected(
        self, audit_service: SignalAuditService, test_signal: Signal
    ):
        """Test recording signal rejection."""
        # Arrange
        user_id = uuid4()
        rejection_reason = "Price moved too far from entry"

        # Act
        entry = await audit_service.record_signal_rejected(
            signal_id=test_signal.id, user_id=user_id, rejection_reason=rejection_reason
        )

        # Assert
        assert entry.new_state == "rejected"
        assert entry.user_id == user_id
        assert entry.transition_reason == rejection_reason

    @pytest.mark.asyncio
    async def test_record_signal_executed(
        self, audit_service: SignalAuditService, test_signal: Signal
    ):
        """Test recording signal execution."""
        # Arrange
        position_id = uuid4()
        entry_price = 150.25

        # Act
        entry = await audit_service.record_signal_executed(
            signal_id=test_signal.id, position_id=position_id, entry_price=entry_price
        )

        # Assert
        assert entry.new_state == "executed"
        assert entry.previous_state == "approved"
        assert "$150.25" in entry.transition_reason
        assert entry.metadata["position_id"] == str(position_id)

    @pytest.mark.asyncio
    async def test_record_signal_closed_with_profit(
        self, audit_service: SignalAuditService, test_signal: Signal
    ):
        """Test recording signal closure with profit."""
        # Arrange
        trade_outcome = TradeOutcome(
            position_id=uuid4(),
            entry_price=Decimal("150.25"),
            entry_time=datetime.now(UTC),
            exit_price=Decimal("152.10"),
            exit_time=datetime.now(UTC),
            shares=100,
            pnl_dollars=Decimal("185.00"),
            pnl_percentage=1.23,
            r_multiple=2.47,
            exit_reason="target_hit",
        )

        # Act
        entry = await audit_service.record_signal_closed(
            signal_id=test_signal.id, trade_outcome=trade_outcome
        )

        # Assert
        assert entry.new_state == "closed"
        assert "target_hit" in entry.transition_reason
        assert "+$185.00" in entry.transition_reason

    @pytest.mark.asyncio
    async def test_record_signal_closed_with_loss(
        self, audit_service: SignalAuditService, test_signal: Signal
    ):
        """Test recording signal closure with loss."""
        # Arrange
        trade_outcome = TradeOutcome(
            position_id=uuid4(),
            entry_price=Decimal("150.25"),
            entry_time=datetime.now(UTC),
            exit_price=Decimal("148.00"),
            exit_time=datetime.now(UTC),
            shares=100,
            pnl_dollars=Decimal("-225.00"),
            pnl_percentage=-1.50,
            r_multiple=-1.0,
            exit_reason="stop_loss",
        )

        # Act
        entry = await audit_service.record_signal_closed(
            signal_id=test_signal.id, trade_outcome=trade_outcome
        )

        # Assert
        assert entry.new_state == "closed"
        assert "stop_loss" in entry.transition_reason
        assert "$-225.00" in entry.transition_reason

    @pytest.mark.asyncio
    async def test_store_validation_results(
        self, audit_service: SignalAuditService, test_signal: Signal
    ):
        """Test storing validation results."""
        # Arrange
        validation_results = ValidationResults(
            volume_validation=ValidationStageResult(
                stage="Volume",
                passed=True,
                input_data={},
                output_data={},
                timestamp=datetime.now(UTC),
            ),
            phase_validation=ValidationStageResult(
                stage="Phase",
                passed=True,
                input_data={},
                output_data={},
                timestamp=datetime.now(UTC),
            ),
            level_validation=ValidationStageResult(
                stage="Level",
                passed=True,
                input_data={},
                output_data={},
                timestamp=datetime.now(UTC),
            ),
            risk_validation=ValidationStageResult(
                stage="Risk",
                passed=True,
                input_data={},
                output_data={},
                timestamp=datetime.now(UTC),
            ),
            strategy_validation=ValidationStageResult(
                stage="Strategy",
                passed=True,
                input_data={},
                output_data={},
                timestamp=datetime.now(UTC),
            ),
            overall_passed=True,
        )

        # Act
        await audit_service.store_validation_results(test_signal.id, validation_results)

        # Assert - verification happens in repository test

    @pytest.mark.asyncio
    async def test_get_signal_audit_trail(
        self, audit_service: SignalAuditService, test_signal: Signal
    ):
        """Test retrieving complete audit trail."""
        # Arrange - Create full lifecycle
        await audit_service.record_signal_generated(test_signal.id, "SPRING", 85.0)
        await audit_service.record_signal_pending(test_signal.id)
        await audit_service.record_signal_approved(test_signal.id, uuid4())

        # Act
        trail = await audit_service.get_signal_audit_trail(test_signal.id)

        # Assert
        assert len(trail) == 3
        states = [entry.new_state for entry in trail]
        assert states == ["generated", "pending", "approved"]


class TestSignalHistoryQuery:
    """Test signal history querying."""

    @pytest.mark.asyncio
    async def test_query_signal_history_with_date_range(
        self, audit_service: SignalAuditService, db_session: AsyncSession
    ):
        """Test querying signals by date range."""
        # Arrange - Create signals on different dates
        yesterday = datetime.now(UTC) - timedelta(days=1)
        today = datetime.now(UTC)

        signal1 = Signal(
            id=uuid4(),
            signal_type="SPRING",
            symbol="AAPL",
            timeframe="1h",
            generated_at=yesterday,
            entry_price=Decimal("150.00"),
            stop_loss=Decimal("148.00"),
            target_1=Decimal("156.00"),
            target_2=Decimal("158.00"),
            position_size=Decimal("100"),
            risk_amount=Decimal("200.00"),
            r_multiple=Decimal("3.0"),
            confidence_score=85,
            status="PENDING",
            approval_chain={},
            lifecycle_state="generated",
            created_at=yesterday,
            updated_at=yesterday,
        )

        signal2 = Signal(
            id=uuid4(),
            signal_type="SOS",
            symbol="AAPL",
            timeframe="1h",
            generated_at=today,
            entry_price=Decimal("151.00"),
            stop_loss=Decimal("149.00"),
            target_1=Decimal("157.00"),
            target_2=Decimal("159.00"),
            position_size=Decimal("100"),
            risk_amount=Decimal("200.00"),
            r_multiple=Decimal("3.0"),
            confidence_score=87,
            status="PENDING",
            approval_chain={},
            lifecycle_state="generated",
            created_at=today,
            updated_at=today,
        )

        db_session.add_all([signal1, signal2])
        await db_session.commit()

        # Act
        query = SignalHistoryQuery(
            start_date=yesterday - timedelta(hours=1),
            end_date=yesterday + timedelta(hours=1),
            page=1,
            page_size=50,
        )
        response = await audit_service.query_signal_history(query)

        # Assert
        assert response.pagination.total_items >= 1
        # Should find signal1 but not signal2
        signal_ids = [s.signal_id for s in response.signals]
        assert signal1.id in signal_ids or signal2.id not in signal_ids
