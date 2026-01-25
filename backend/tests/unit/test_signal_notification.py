"""
Unit Tests for Signal Notification (Story 19.7)

Tests:
- SignalNotification model validation and serialization
- SignalNotificationService retry logic
- WebSocket delivery timing requirements
- Delivery status logging
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.models.notification import SignalNotification
from src.models.signal import (
    ConfidenceComponents,
    TargetLevels,
    TradeSignal,
)
from src.models.validation import (
    StageValidationResult,
    ValidationChain,
    ValidationStatus,
)
from src.services.signal_notification_service import (
    MAX_RETRIES,
    RETRY_DELAYS_MS,
    DeliveryResult,
    DeliveryStatus,
    SignalNotificationService,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_signal() -> TradeSignal:
    """Create a sample approved TradeSignal for testing."""
    validation_chain = ValidationChain(
        pattern_id=uuid4(),
        validation_results=[
            StageValidationResult(
                stage="Volume",
                status=ValidationStatus.PASS,
                validator_id="VOLUME_VALIDATOR",
                metadata={"volume_ratio": 0.6},
            ),
            StageValidationResult(
                stage="Phase",
                status=ValidationStatus.PASS,
                validator_id="PHASE_VALIDATOR",
                metadata={},
            ),
            StageValidationResult(
                stage="Levels",
                status=ValidationStatus.PASS,
                validator_id="LEVEL_VALIDATOR",
                metadata={},
            ),
            StageValidationResult(
                stage="Risk",
                status=ValidationStatus.PASS,
                validator_id="RISK_VALIDATOR",
                metadata={"risk_percentage": 1.5},
            ),
            StageValidationResult(
                stage="Strategy",
                status=ValidationStatus.PASS,
                validator_id="STRATEGY_VALIDATOR",
                metadata={},
            ),
        ],
        overall_status=ValidationStatus.PASS,
    )

    return TradeSignal(
        symbol="AAPL",
        asset_class="STOCK",
        pattern_type="SPRING",
        phase="C",
        timeframe="1h",
        entry_price=Decimal("150.25"),
        stop_loss=Decimal("149.50"),
        target_levels=TargetLevels(
            primary_target=Decimal("152.75"),
            secondary_targets=[Decimal("151.50"), Decimal("152.00")],
        ),
        position_size=Decimal("100"),
        position_size_unit="SHARES",
        notional_value=Decimal("15025.00"),
        risk_amount=Decimal("75.00"),
        r_multiple=Decimal("3.33"),
        confidence_score=92,
        confidence_components=ConfidenceComponents(
            pattern_confidence=94,
            phase_confidence=90,
            volume_confidence=90,
            overall_confidence=92,
        ),
        validation_chain=validation_chain,
        status="APPROVED",
        timestamp=datetime.now(UTC),
    )


@pytest.fixture
def mock_connection_manager() -> MagicMock:
    """Create a mock ConnectionManager for testing."""
    manager = MagicMock()
    manager.broadcast = AsyncMock()
    manager.emit_signal_approved = AsyncMock()
    return manager


@pytest.fixture
def notification_service(mock_connection_manager: MagicMock) -> SignalNotificationService:
    """Create SignalNotificationService with mock connection manager."""
    return SignalNotificationService(mock_connection_manager)


# ============================================================================
# SignalNotification Model Tests
# ============================================================================


class TestSignalNotificationModel:
    """Test SignalNotification model validation and serialization."""

    def test_create_valid_notification(self):
        """Test creating a valid SignalNotification."""
        signal_id = uuid4()
        now = datetime.now(UTC)
        expires = now + timedelta(minutes=5)

        notification = SignalNotification(
            signal_id=signal_id,
            timestamp=now,
            symbol="AAPL",
            pattern_type="SPRING",
            confidence_score=92.5,
            confidence_grade="A+",
            entry_price="150.25",
            stop_loss="149.50",
            target_price="152.75",
            risk_amount="75.00",
            risk_percentage=1.5,
            r_multiple=3.33,
            expires_at=expires,
        )

        assert notification.type == "signal_approved"
        assert notification.signal_id == signal_id
        assert notification.symbol == "AAPL"
        assert notification.pattern_type == "SPRING"
        assert notification.confidence_score == 92.5
        assert notification.confidence_grade == "A+"
        assert notification.entry_price == "150.25"
        assert notification.r_multiple == 3.33

    def test_notification_type_literal(self):
        """Test that type field is always 'signal_approved'."""
        notification = SignalNotification(
            signal_id=uuid4(),
            timestamp=datetime.now(UTC),
            symbol="AAPL",
            pattern_type="SOS",
            confidence_score=85.0,
            confidence_grade="A",
            entry_price="150.00",
            stop_loss="148.00",
            target_price="156.00",
            risk_amount="200.00",
            risk_percentage=2.0,
            r_multiple=3.0,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

        assert notification.type == "signal_approved"

    def test_notification_json_serialization(self):
        """Test JSON serialization produces expected format."""
        signal_id = uuid4()
        now = datetime.now(UTC)
        expires = now + timedelta(minutes=5)

        notification = SignalNotification(
            signal_id=signal_id,
            timestamp=now,
            symbol="AAPL",
            pattern_type="SPRING",
            confidence_score=92.5,
            confidence_grade="A+",
            entry_price="150.25",
            stop_loss="149.50",
            target_price="152.75",
            risk_amount="75.00",
            risk_percentage=1.5,
            r_multiple=3.33,
            expires_at=expires,
        )

        json_data = notification.model_dump(mode="json")

        assert json_data["type"] == "signal_approved"
        assert isinstance(json_data["signal_id"], str)
        assert isinstance(json_data["timestamp"], str)
        assert json_data["symbol"] == "AAPL"
        assert json_data["pattern_type"] == "SPRING"
        assert json_data["confidence_score"] == 92.5
        assert json_data["confidence_grade"] == "A+"

    def test_confidence_score_validation(self):
        """Test confidence score range validation (0-100)."""
        # Valid scores
        for score in [0.0, 50.0, 70.0, 85.0, 95.0, 100.0]:
            notification = SignalNotification(
                signal_id=uuid4(),
                timestamp=datetime.now(UTC),
                symbol="AAPL",
                pattern_type="SPRING",
                confidence_score=score,
                confidence_grade="A",
                entry_price="150.00",
                stop_loss="148.00",
                target_price="156.00",
                risk_amount="200.00",
                risk_percentage=1.5,
                r_multiple=3.0,
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            )
            assert notification.confidence_score == score

    def test_risk_percentage_validation(self):
        """Test risk percentage range validation (0-100)."""
        # Valid percentages
        for pct in [0.0, 1.5, 2.0, 5.0]:
            notification = SignalNotification(
                signal_id=uuid4(),
                timestamp=datetime.now(UTC),
                symbol="AAPL",
                pattern_type="SPRING",
                confidence_score=85.0,
                confidence_grade="A",
                entry_price="150.00",
                stop_loss="148.00",
                target_price="156.00",
                risk_amount="200.00",
                risk_percentage=pct,
                r_multiple=3.0,
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            )
            assert notification.risk_percentage == pct


class TestConfidenceGrading:
    """Test confidence score to grade conversion."""

    def test_grade_a_plus(self):
        """Test A+ grade for scores >= 90."""
        assert SignalNotification.confidence_to_grade(90.0) == "A+"
        assert SignalNotification.confidence_to_grade(95.0) == "A+"
        assert SignalNotification.confidence_to_grade(100.0) == "A+"

    def test_grade_a(self):
        """Test A grade for scores 85-89."""
        assert SignalNotification.confidence_to_grade(85.0) == "A"
        assert SignalNotification.confidence_to_grade(87.5) == "A"
        assert SignalNotification.confidence_to_grade(89.9) == "A"

    def test_grade_b(self):
        """Test B grade for scores 80-84."""
        assert SignalNotification.confidence_to_grade(80.0) == "B"
        assert SignalNotification.confidence_to_grade(82.5) == "B"
        assert SignalNotification.confidence_to_grade(84.9) == "B"

    def test_grade_c(self):
        """Test C grade for scores 70-79."""
        assert SignalNotification.confidence_to_grade(70.0) == "C"
        assert SignalNotification.confidence_to_grade(75.0) == "C"
        assert SignalNotification.confidence_to_grade(79.9) == "C"


# ============================================================================
# SignalNotificationService Tests
# ============================================================================


class TestSignalNotificationService:
    """Test SignalNotificationService core functionality."""

    @pytest.mark.asyncio
    async def test_notify_signal_approved_success(
        self, notification_service: SignalNotificationService, sample_signal: TradeSignal
    ):
        """Test successful signal notification delivery."""
        result = await notification_service.notify_signal_approved(sample_signal)

        assert result.status == DeliveryStatus.SUCCESS
        assert result.signal_id == sample_signal.id
        assert result.attempts == 1
        assert result.error is None
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_notify_creates_correct_payload(
        self,
        notification_service: SignalNotificationService,
        sample_signal: TradeSignal,
        mock_connection_manager: MagicMock,
    ):
        """Test that notification payload matches expected format."""
        await notification_service.notify_signal_approved(sample_signal)

        # Verify broadcast was called
        mock_connection_manager.broadcast.assert_called_once()

        # Get the payload
        payload = mock_connection_manager.broadcast.call_args[0][0]

        assert payload["type"] == "signal_approved"
        assert payload["symbol"] == "AAPL"
        assert payload["pattern_type"] == "SPRING"
        assert payload["entry_price"] == str(sample_signal.entry_price)
        assert payload["stop_loss"] == str(sample_signal.stop_loss)
        assert payload["target_price"] == str(sample_signal.target_levels.primary_target)
        assert payload["risk_amount"] == str(sample_signal.risk_amount)
        assert payload["r_multiple"] == float(sample_signal.r_multiple)
        assert "confidence_grade" in payload
        assert "expires_at" in payload

    @pytest.mark.asyncio
    async def test_confidence_grade_in_payload(
        self,
        notification_service: SignalNotificationService,
        sample_signal: TradeSignal,
        mock_connection_manager: MagicMock,
    ):
        """Test confidence grade is correctly included in payload."""
        # Sample signal has confidence_score=92, should be A+
        await notification_service.notify_signal_approved(sample_signal)

        payload = mock_connection_manager.broadcast.call_args[0][0]
        assert payload["confidence_grade"] == "A+"

    @pytest.mark.asyncio
    async def test_metrics_tracking(
        self, notification_service: SignalNotificationService, sample_signal: TradeSignal
    ):
        """Test that delivery metrics are tracked."""
        # Initial metrics
        metrics_before = notification_service.get_metrics()
        assert metrics_before["signal_notifications_sent_total"] == 0

        # Send notification
        await notification_service.notify_signal_approved(sample_signal)

        # Check metrics updated
        metrics_after = notification_service.get_metrics()
        assert metrics_after["signal_notifications_sent_total"] == 1
        assert metrics_after["signal_notification_failures_total"] == 0


class TestRetryLogic:
    """Test retry logic with mock failures."""

    @pytest.mark.asyncio
    async def test_retry_on_first_failure(
        self, sample_signal: TradeSignal, mock_connection_manager: MagicMock
    ):
        """Test that service retries after first failure."""
        # Configure mock to fail first time, succeed second time
        mock_connection_manager.broadcast.side_effect = [
            Exception("Connection error"),
            None,  # Success on second attempt
        ]

        service = SignalNotificationService(mock_connection_manager)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await service.notify_signal_approved(sample_signal)

        assert result.status == DeliveryStatus.SUCCESS
        assert result.attempts == 2
        assert mock_connection_manager.broadcast.call_count == 2
        mock_sleep.assert_called_once()  # 100ms delay

    @pytest.mark.asyncio
    async def test_retry_delays_exponential_backoff(
        self, sample_signal: TradeSignal, mock_connection_manager: MagicMock
    ):
        """Test that retry delays follow exponential backoff pattern."""
        # Configure mock to fail twice, succeed third time
        mock_connection_manager.broadcast.side_effect = [
            Exception("Error 1"),
            Exception("Error 2"),
            None,  # Success
        ]

        service = SignalNotificationService(mock_connection_manager)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await service.notify_signal_approved(sample_signal)

        assert result.status == DeliveryStatus.SUCCESS
        assert result.attempts == 3

        # Verify delay sequence: 100ms, 500ms
        assert mock_sleep.call_count == 2
        calls = mock_sleep.call_args_list
        assert calls[0][0][0] == RETRY_DELAYS_MS[0] / 1000  # 0.1 seconds
        assert calls[1][0][0] == RETRY_DELAYS_MS[1] / 1000  # 0.5 seconds

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(
        self, sample_signal: TradeSignal, mock_connection_manager: MagicMock
    ):
        """Test that delivery fails after all retries exhausted."""
        # Configure mock to always fail
        mock_connection_manager.broadcast.side_effect = Exception("Persistent error")

        service = SignalNotificationService(mock_connection_manager)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await service.notify_signal_approved(sample_signal)

        assert result.status == DeliveryStatus.FAILED
        assert result.attempts == MAX_RETRIES
        assert result.error == "Persistent error"
        assert mock_connection_manager.broadcast.call_count == MAX_RETRIES

    @pytest.mark.asyncio
    async def test_failure_metrics_on_exhausted_retries(
        self, sample_signal: TradeSignal, mock_connection_manager: MagicMock
    ):
        """Test failure metrics are updated when all retries fail."""
        mock_connection_manager.broadcast.side_effect = Exception("Error")

        service = SignalNotificationService(mock_connection_manager)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await service.notify_signal_approved(sample_signal)

        metrics = service.get_metrics()
        assert metrics["signal_notification_failures_total"] == 1
        assert metrics["signal_notification_retries_total"] == MAX_RETRIES


class TestDeliveryTiming:
    """Test delivery timing requirements."""

    @pytest.mark.asyncio
    async def test_latency_tracking(
        self, notification_service: SignalNotificationService, sample_signal: TradeSignal
    ):
        """Test that latency is measured and returned."""
        result = await notification_service.notify_signal_approved(sample_signal)

        # Latency should be a positive number (in ms)
        assert result.latency_ms >= 0
        assert result.latency_ms < 1000  # Should be fast in tests

    @pytest.mark.asyncio
    async def test_delivery_within_timing_target(
        self,
        notification_service: SignalNotificationService,
        sample_signal: TradeSignal,
        mock_connection_manager: MagicMock,
    ):
        """Test that delivery completes quickly for successful case."""
        # Successful delivery should be well under 500ms in tests
        result = await notification_service.notify_signal_approved(sample_signal)

        assert result.status == DeliveryStatus.SUCCESS
        # In unit tests without network, should be very fast
        assert result.latency_ms < 100


class TestDeliveryResult:
    """Test DeliveryResult dataclass."""

    def test_success_result(self):
        """Test creating success result."""
        signal_id = uuid4()
        result = DeliveryResult(
            status=DeliveryStatus.SUCCESS,
            signal_id=signal_id,
            user_id=None,
            attempts=1,
            latency_ms=45.5,
        )

        assert result.status == DeliveryStatus.SUCCESS
        assert result.signal_id == signal_id
        assert result.attempts == 1
        assert result.latency_ms == 45.5
        assert result.error is None

    def test_failure_result(self):
        """Test creating failure result with error."""
        signal_id = uuid4()
        result = DeliveryResult(
            status=DeliveryStatus.FAILED,
            signal_id=signal_id,
            user_id=None,
            attempts=3,
            latency_ms=2600.0,
            error="Connection refused",
        )

        assert result.status == DeliveryStatus.FAILED
        assert result.attempts == 3
        assert result.error == "Connection refused"


# ============================================================================
# Integration Tests (WebSocket + Service)
# ============================================================================


class TestWebSocketIntegration:
    """Test integration between service and WebSocket manager."""

    @pytest.mark.asyncio
    async def test_notification_sent_via_broadcast(
        self,
        notification_service: SignalNotificationService,
        sample_signal: TradeSignal,
        mock_connection_manager: MagicMock,
    ):
        """Test that notification is sent via broadcast method."""
        await notification_service.notify_signal_approved(sample_signal)

        mock_connection_manager.broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_signals_sent_independently(
        self,
        notification_service: SignalNotificationService,
        sample_signal: TradeSignal,
        mock_connection_manager: MagicMock,
    ):
        """Test multiple signal notifications are independent."""
        # Send first notification
        result1 = await notification_service.notify_signal_approved(sample_signal)

        # Create second signal with different symbol
        sample_signal.symbol = "MSFT"
        sample_signal.id = uuid4()

        result2 = await notification_service.notify_signal_approved(sample_signal)

        assert result1.status == DeliveryStatus.SUCCESS
        assert result2.status == DeliveryStatus.SUCCESS
        assert mock_connection_manager.broadcast.call_count == 2

        # Verify both signals sent
        payloads = [call[0][0] for call in mock_connection_manager.broadcast.call_args_list]
        symbols = [p["symbol"] for p in payloads]
        assert "AAPL" in symbols
        assert "MSFT" in symbols
