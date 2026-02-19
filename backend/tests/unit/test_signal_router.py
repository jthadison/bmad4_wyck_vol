"""
Unit tests for Signal Router (Story 12.8 Task 6)

Tests signal routing to paper trading vs live trading based on account status.

Author: Story 12.8
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

# All tests in this file require a PostgreSQL database (JSONB columns).
pytestmark = pytest.mark.database

from src.models.paper_trading import PaperAccount, PaperPosition
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
from src.trading.exceptions import RiskLimitExceededError
from src.trading.signal_router import SignalRouter


@pytest.fixture
def mock_db_session():
    """Create mock database session factory."""

    class MockSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def commit(self):
            pass

        async def rollback(self):
            pass

    # Create a callable that returns the context manager
    class MockSessionMaker:
        def __call__(self):
            return MockSession()

    return MockSessionMaker()


@pytest.fixture
def mock_signal():
    """Create mock trading signal."""
    # Create confidence components
    confidence = ConfidenceComponents(
        pattern_confidence=88,
        phase_confidence=82,
        volume_confidence=80,
        overall_confidence=85,
    )

    # Create target levels
    targets = TargetLevels(
        primary_target=Decimal("156.00"),
        secondary_targets=[Decimal("152.00"), Decimal("154.00")],
    )

    # Create validation chain
    validation = ValidationChain(
        pattern_id=uuid4(),
        overall_status=ValidationStatus.PASS,
        validation_results=[
            StageValidationResult(
                stage="Volume", status=ValidationStatus.PASS, validator_id="VOLUME_VALIDATOR"
            )
        ],
    )

    # Create TradeSignal
    return TradeSignal(
        symbol="AAPL",
        pattern_type="SPRING",
        phase="C",
        timeframe="1h",
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("148.00"),
        target_levels=targets,
        position_size=Decimal("100"),
        notional_value=Decimal("15000.00"),
        risk_amount=Decimal("200.00"),
        r_multiple=Decimal("3.0"),
        confidence_score=85,
        confidence_components=confidence,
        validation_chain=validation,
        timestamp=datetime.now(UTC),
    )


@pytest.fixture
def mock_paper_account():
    """Create mock paper account."""
    return PaperAccount(
        starting_capital=Decimal("100000.00"),
        current_capital=Decimal("100000.00"),
        equity=Decimal("100000.00"),
    )


class TestSignalRouter:
    """Test signal routing logic."""

    @pytest.mark.asyncio
    async def test_route_to_paper_when_enabled(
        self, mock_db_session, mock_signal, mock_paper_account
    ):
        """Test signal is routed to paper trading when account exists."""
        router = SignalRouter(mock_db_session)

        # Mock paper account repository to return an account (paper trading enabled)
        with patch("src.trading.signal_router.PaperAccountRepository") as mock_account_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_account = AsyncMock(return_value=mock_paper_account)
            mock_account_repo_class.return_value = mock_repo

            # Mock paper trading service execution
            with patch("src.trading.signal_router.PaperTradingService") as mock_service_class:
                mock_position = PaperPosition(
                    signal_id=mock_signal.id,
                    symbol="AAPL",
                    entry_time=datetime.now(UTC),
                    entry_price=Decimal("150.03"),
                    quantity=Decimal("100"),
                    stop_loss=Decimal("148.00"),
                    target_1=Decimal("152.00"),
                    target_2=Decimal("154.00"),
                    current_price=Decimal("150.00"),
                    unrealized_pnl=Decimal("0"),
                    status="OPEN",
                    commission_paid=Decimal("0.50"),
                    slippage_cost=Decimal("3.00"),
                )

                mock_service = AsyncMock()
                mock_service.execute_signal = AsyncMock(return_value=mock_position)
                mock_service_class.return_value = mock_service

                # Route signal
                result = await router.route_signal(mock_signal, Decimal("150.00"))

                # Verify routed to paper trading
                assert result == "paper"
                mock_service.execute_signal.assert_called_once_with(mock_signal, Decimal("150.00"))

    @pytest.mark.asyncio
    async def test_route_to_live_when_paper_disabled(self, mock_db_session, mock_signal):
        """Test signal routing when paper trading is disabled (no account)."""
        router = SignalRouter(mock_db_session)

        # Mock paper account repository to return None (paper trading disabled)
        with patch("src.trading.signal_router.PaperAccountRepository") as mock_account_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_account = AsyncMock(return_value=None)
            mock_account_repo_class.return_value = mock_repo

            # Route signal
            result = await router.route_signal(mock_signal, Decimal("150.00"))

            # Verify skipped (no broker router configured for live trading)
            assert result == "skipped"

    @pytest.mark.asyncio
    async def test_risk_validation_failure_raises_error(
        self, mock_db_session, mock_signal, mock_paper_account
    ):
        """Test that risk validation failures raise ValueError."""
        router = SignalRouter(mock_db_session)

        # Mock paper account repository
        with patch("src.trading.signal_router.PaperAccountRepository") as mock_account_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_account = AsyncMock(return_value=mock_paper_account)
            mock_account_repo_class.return_value = mock_repo

            # Mock paper trading service to raise RiskLimitExceededError (risk validation failed)
            with patch("src.trading.signal_router.PaperTradingService") as mock_service_class:
                mock_service = AsyncMock()
                mock_service.execute_signal = AsyncMock(
                    side_effect=RiskLimitExceededError(
                        limit_type="per_trade_risk",
                        limit_value=Decimal("2.0"),
                        actual_value=Decimal("5.0"),
                        symbol="AAPL",
                    )
                )
                mock_service_class.return_value = mock_service

                # Verify RiskLimitExceededError is raised
                with pytest.raises(RiskLimitExceededError):
                    await router.route_signal(mock_signal, Decimal("150.00"))

    @pytest.mark.asyncio
    async def test_unexpected_error_is_raised(
        self, mock_db_session, mock_signal, mock_paper_account
    ):
        """Test that unexpected errors are propagated."""
        router = SignalRouter(mock_db_session)

        # Mock paper account repository
        with patch("src.trading.signal_router.PaperAccountRepository") as mock_account_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_account = AsyncMock(return_value=mock_paper_account)
            mock_account_repo_class.return_value = mock_repo

            # Mock paper trading service to raise unexpected error
            with patch("src.trading.signal_router.PaperTradingService") as mock_service_class:
                mock_service = AsyncMock()
                mock_service.execute_signal = AsyncMock(
                    side_effect=RuntimeError("Database connection failed")
                )
                mock_service_class.return_value = mock_service

                # Verify error is raised
                with pytest.raises(RuntimeError, match="Database connection failed"):
                    await router.route_signal(mock_signal, Decimal("150.00"))
