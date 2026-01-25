"""
Unit tests for Signal Approval Service (Story 19.9)

Tests signal approval queue operations including:
- Signal submission with queue size limits
- Signal approval with optimistic locking
- Signal rejection
- Signal expiration

Author: Story 19.9
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.models.signal_approval import (
    QueueEntryStatus,
    SignalApprovalConfig,
    SignalQueueEntry,
)
from src.services.signal_approval_service import SignalApprovalService


@pytest.fixture
def mock_repository():
    """Create a mock repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def signal_approval_config():
    """Create test configuration."""
    return SignalApprovalConfig(
        timeout_minutes=5,
        max_queue_size=10,
        expiration_check_interval_seconds=30,
    )


@pytest.fixture
def service(mock_repository, signal_approval_config):
    """Create service with mock dependencies."""
    return SignalApprovalService(
        repository=mock_repository,
        config=signal_approval_config,
    )


@pytest.fixture
def sample_signal():
    """Create a mock trade signal for testing."""
    mock_signal = MagicMock()
    mock_signal.id = uuid4()
    mock_signal.symbol = "AAPL"
    mock_signal.pattern_type = "SPRING"
    mock_signal.phase = "C"
    mock_signal.timeframe = "1H"
    mock_signal.asset_class = "STOCK"
    mock_signal.entry_price = Decimal("150.00")
    mock_signal.stop_loss = Decimal("148.00")
    mock_signal.target_levels = MagicMock()
    mock_signal.target_levels.primary_target = Decimal("155.00")
    mock_signal.position_size = Decimal("100")
    mock_signal.position_size_unit = "SHARES"
    mock_signal.risk_amount = Decimal("200.00")
    mock_signal.r_multiple = Decimal("2.5")
    mock_signal.confidence_score = 85.0
    mock_signal.timestamp = datetime.now(UTC)
    return mock_signal


@pytest.fixture
def sample_queue_entry():
    """Create a sample queue entry."""
    return SignalQueueEntry(
        id=uuid4(),
        signal_id=uuid4(),
        user_id=uuid4(),
        status=QueueEntryStatus.PENDING,
        submitted_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        signal_snapshot={
            "id": str(uuid4()),
            "symbol": "AAPL",
            "pattern_type": "SPRING",
            "phase": "C",
            "timeframe": "1H",
            "asset_class": "EQUITY",
            "entry_price": "150.00",
            "stop_loss": "148.00",
            "target_price": "155.00",
            "position_size": "100",
            "position_size_unit": "SHARES",
            "risk_amount": "200.00",
            "r_multiple": "2.5",
            "confidence_score": 85.0,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


class TestSignalSubmission:
    """Tests for signal submission."""

    @pytest.mark.asyncio
    async def test_submit_signal_success(self, service, mock_repository, sample_signal):
        """Test successful signal submission."""
        user_id = uuid4()
        mock_repository.count_pending_by_user.return_value = 0
        mock_repository.create.return_value = SignalQueueEntry(
            id=uuid4(),
            signal_id=sample_signal.id,
            user_id=user_id,
            status=QueueEntryStatus.PENDING,
            submitted_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            signal_snapshot={},
        )

        result = await service.submit_signal(sample_signal, user_id)

        assert result.signal_id == sample_signal.id
        assert result.user_id == user_id
        assert result.status == QueueEntryStatus.PENDING
        mock_repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_signal_queue_overflow(
        self, service, mock_repository, sample_signal, signal_approval_config
    ):
        """Test queue overflow handling - oldest signal is expired."""
        user_id = uuid4()
        oldest_entry = SignalQueueEntry(
            id=uuid4(),
            signal_id=uuid4(),
            user_id=user_id,
            status=QueueEntryStatus.PENDING,
            submitted_at=datetime.now(UTC) - timedelta(minutes=10),
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            signal_snapshot={},
        )

        mock_repository.count_pending_by_user.return_value = signal_approval_config.max_queue_size
        mock_repository.get_oldest_pending_by_user.return_value = oldest_entry
        mock_repository.update_status.return_value = oldest_entry
        mock_repository.create.return_value = SignalQueueEntry(
            id=uuid4(),
            signal_id=sample_signal.id,
            user_id=user_id,
            status=QueueEntryStatus.PENDING,
            submitted_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            signal_snapshot={},
        )

        result = await service.submit_signal(sample_signal, user_id)

        # Verify oldest was expired
        mock_repository.update_status.assert_called_once_with(
            oldest_entry.id, QueueEntryStatus.EXPIRED
        )
        # Verify new entry was created
        mock_repository.create.assert_called_once()
        assert result.status == QueueEntryStatus.PENDING

    @pytest.mark.asyncio
    async def test_submit_signal_custom_timeout(self, service, mock_repository, sample_signal):
        """Test signal submission with custom timeout."""
        user_id = uuid4()
        custom_timeout = 10
        mock_repository.count_pending_by_user.return_value = 0
        mock_repository.create.return_value = SignalQueueEntry(
            id=uuid4(),
            signal_id=sample_signal.id,
            user_id=user_id,
            status=QueueEntryStatus.PENDING,
            submitted_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(minutes=custom_timeout),
            signal_snapshot={},
        )

        await service.submit_signal(sample_signal, user_id, timeout_minutes=custom_timeout)

        # Verify create was called with correct expiration
        call_args = mock_repository.create.call_args
        entry = call_args[0][0]
        # Check that expires_at is approximately custom_timeout minutes from now
        expected_expiry = datetime.now(UTC) + timedelta(minutes=custom_timeout)
        assert abs((entry.expires_at - expected_expiry).total_seconds()) < 2


class TestSignalApproval:
    """Tests for signal approval."""

    @pytest.mark.asyncio
    async def test_approve_signal_success(self, service, mock_repository, sample_queue_entry):
        """Test successful signal approval."""
        user_id = sample_queue_entry.user_id
        approved_entry = SignalQueueEntry(
            **{
                **sample_queue_entry.model_dump(),
                "status": QueueEntryStatus.APPROVED,
                "approved_at": datetime.now(UTC),
                "approved_by": user_id,
            }
        )

        mock_repository.get_by_id.return_value = sample_queue_entry
        mock_repository.update_status.return_value = approved_entry

        result = await service.approve_signal(sample_queue_entry.id, user_id)

        assert result.status == QueueEntryStatus.APPROVED
        assert result.approved_at is not None
        assert "approved" in result.message.lower()

    @pytest.mark.asyncio
    async def test_approve_signal_not_found(self, service, mock_repository):
        """Test approval of non-existent signal."""
        mock_repository.get_by_id.return_value = None

        result = await service.approve_signal(uuid4(), uuid4())

        assert result.status == QueueEntryStatus.PENDING
        assert "not found" in result.message.lower()

    @pytest.mark.asyncio
    async def test_approve_signal_unauthorized(self, service, mock_repository, sample_queue_entry):
        """Test approval by unauthorized user."""
        different_user_id = uuid4()
        mock_repository.get_by_id.return_value = sample_queue_entry

        result = await service.approve_signal(sample_queue_entry.id, different_user_id)

        assert result.status == QueueEntryStatus.PENDING
        assert "not authorized" in result.message.lower()

    @pytest.mark.asyncio
    async def test_approve_signal_already_processed(
        self, service, mock_repository, sample_queue_entry
    ):
        """Test approval of already processed signal."""
        sample_queue_entry.status = QueueEntryStatus.APPROVED
        mock_repository.get_by_id.return_value = sample_queue_entry

        result = await service.approve_signal(sample_queue_entry.id, sample_queue_entry.user_id)

        assert result.status == QueueEntryStatus.APPROVED
        assert "already processed" in result.message.lower()

    @pytest.mark.asyncio
    async def test_approve_signal_expired(self, service, mock_repository, sample_queue_entry):
        """Test approval of expired signal."""
        sample_queue_entry.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        mock_repository.get_by_id.return_value = sample_queue_entry
        mock_repository.update_status.return_value = sample_queue_entry

        result = await service.approve_signal(sample_queue_entry.id, sample_queue_entry.user_id)

        assert result.status == QueueEntryStatus.EXPIRED
        assert "expired" in result.message.lower()

    @pytest.mark.asyncio
    async def test_approve_signal_concurrent_update(
        self, service, mock_repository, sample_queue_entry
    ):
        """Test concurrent approval returns appropriate message."""
        mock_repository.get_by_id.return_value = sample_queue_entry
        mock_repository.update_status.return_value = None  # Indicates update failed

        result = await service.approve_signal(sample_queue_entry.id, sample_queue_entry.user_id)

        assert result.status == QueueEntryStatus.PENDING
        assert "already processed" in result.message.lower()


class TestSignalRejection:
    """Tests for signal rejection."""

    @pytest.mark.asyncio
    async def test_reject_signal_success(self, service, mock_repository, sample_queue_entry):
        """Test successful signal rejection."""
        user_id = sample_queue_entry.user_id
        reason = "Price moved too far from entry"
        rejected_entry = SignalQueueEntry(
            **{
                **sample_queue_entry.model_dump(),
                "status": QueueEntryStatus.REJECTED,
                "rejection_reason": reason,
            }
        )

        mock_repository.get_by_id.return_value = sample_queue_entry
        mock_repository.update_status.return_value = rejected_entry

        result = await service.reject_signal(sample_queue_entry.id, user_id, reason)

        assert result.status == QueueEntryStatus.REJECTED
        assert result.rejection_reason == reason

    @pytest.mark.asyncio
    async def test_reject_signal_not_found(self, service, mock_repository):
        """Test rejection of non-existent signal."""
        mock_repository.get_by_id.return_value = None

        result = await service.reject_signal(uuid4(), uuid4(), "test reason")

        assert result.status == QueueEntryStatus.PENDING
        assert "not found" in result.message.lower()

    @pytest.mark.asyncio
    async def test_reject_signal_unauthorized(self, service, mock_repository, sample_queue_entry):
        """Test rejection by unauthorized user."""
        different_user_id = uuid4()
        mock_repository.get_by_id.return_value = sample_queue_entry

        result = await service.reject_signal(
            sample_queue_entry.id, different_user_id, "test reason"
        )

        assert result.status == QueueEntryStatus.PENDING
        assert "not authorized" in result.message.lower()


class TestPendingSignals:
    """Tests for pending signal retrieval."""

    @pytest.mark.asyncio
    async def test_get_pending_signals_success(self, service, mock_repository, sample_queue_entry):
        """Test retrieval of pending signals."""
        user_id = sample_queue_entry.user_id
        mock_repository.get_pending_by_user.return_value = [sample_queue_entry]

        result = await service.get_pending_signals(user_id)

        assert len(result) == 1
        assert result[0].queue_id == sample_queue_entry.id
        assert result[0].symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_get_pending_signals_filters_expired(
        self, service, mock_repository, sample_queue_entry
    ):
        """Test that expired signals are filtered out."""
        user_id = sample_queue_entry.user_id
        sample_queue_entry.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        mock_repository.get_pending_by_user.return_value = [sample_queue_entry]
        mock_repository.update_status.return_value = sample_queue_entry

        result = await service.get_pending_signals(user_id)

        assert len(result) == 0
        # Verify expired signal was updated
        mock_repository.update_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_pending_signals_empty(self, service, mock_repository):
        """Test retrieval when no pending signals."""
        user_id = uuid4()
        mock_repository.get_pending_by_user.return_value = []

        result = await service.get_pending_signals(user_id)

        assert len(result) == 0


class TestSignalExpiration:
    """Tests for signal expiration."""

    @pytest.mark.asyncio
    async def test_expire_stale_signals(self, service, mock_repository):
        """Test bulk expiration of stale signals."""
        mock_repository.expire_stale_entries.return_value = 5

        result = await service.expire_stale_signals()

        assert result == 5
        mock_repository.expire_stale_entries.assert_called_once()

    @pytest.mark.asyncio
    async def test_expire_stale_signals_none(self, service, mock_repository):
        """Test when no signals to expire."""
        mock_repository.expire_stale_entries.return_value = 0

        result = await service.expire_stale_signals()

        assert result == 0


class TestSignalSnapshot:
    """Tests for signal snapshot creation."""

    def test_create_signal_snapshot(self, service, sample_signal):
        """Test signal snapshot contains all required fields."""
        snapshot = service._create_signal_snapshot(sample_signal)

        assert snapshot["id"] == str(sample_signal.id)
        assert snapshot["symbol"] == "AAPL"
        assert snapshot["pattern_type"] == "SPRING"
        assert snapshot["phase"] == "C"
        assert snapshot["entry_price"] == "150.00"
        assert snapshot["stop_loss"] == "148.00"
        assert snapshot["target_price"] == "155.00"
        assert snapshot["position_size"] == "100"
        assert snapshot["confidence_score"] == 85.0


class TestConfidenceGrade:
    """Tests for confidence grade calculation."""

    @pytest.mark.asyncio
    async def test_confidence_grade_a_plus(self, service, mock_repository, sample_queue_entry):
        """Test A+ grade for score >= 90."""
        sample_queue_entry.signal_snapshot["confidence_score"] = 92
        mock_repository.get_pending_by_user.return_value = [sample_queue_entry]

        result = await service.get_pending_signals(sample_queue_entry.user_id)

        assert result[0].confidence_grade == "A+"

    @pytest.mark.asyncio
    async def test_confidence_grade_a(self, service, mock_repository, sample_queue_entry):
        """Test A grade for score >= 85."""
        sample_queue_entry.signal_snapshot["confidence_score"] = 87
        mock_repository.get_pending_by_user.return_value = [sample_queue_entry]

        result = await service.get_pending_signals(sample_queue_entry.user_id)

        assert result[0].confidence_grade == "A"

    @pytest.mark.asyncio
    async def test_confidence_grade_b_plus(self, service, mock_repository, sample_queue_entry):
        """Test B+ grade for score >= 80."""
        sample_queue_entry.signal_snapshot["confidence_score"] = 82
        mock_repository.get_pending_by_user.return_value = [sample_queue_entry]

        result = await service.get_pending_signals(sample_queue_entry.user_id)

        assert result[0].confidence_grade == "B+"

    @pytest.mark.asyncio
    async def test_confidence_grade_b(self, service, mock_repository, sample_queue_entry):
        """Test B grade for score >= 75."""
        sample_queue_entry.signal_snapshot["confidence_score"] = 77
        mock_repository.get_pending_by_user.return_value = [sample_queue_entry]

        result = await service.get_pending_signals(sample_queue_entry.user_id)

        assert result[0].confidence_grade == "B"

    @pytest.mark.asyncio
    async def test_confidence_grade_c(self, service, mock_repository, sample_queue_entry):
        """Test C grade for score < 75."""
        sample_queue_entry.signal_snapshot["confidence_score"] = 70
        mock_repository.get_pending_by_user.return_value = [sample_queue_entry]

        result = await service.get_pending_signals(sample_queue_entry.user_id)

        assert result[0].confidence_grade == "C"
