"""
Unit Tests for Paper Trading Service (Story 12.8 Task 17)

Tests for PaperTradingService including signal execution, position updates,
risk validation, and performance metrics.

Author: Story 12.8
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.brokers.paper_broker_adapter import PaperBrokerAdapter
from src.models.paper_trading import PaperAccount, PaperTradingConfig
from src.models.signal import ConfidenceComponents, TargetLevels, TradeSignal
from src.models.validation import ValidationChain, ValidationStatus
from src.trading.exceptions import (
    PaperAccountNotFoundError,
    RiskLimitExceededError,
)
from src.trading.paper_trading_service import PaperTradingService


class MockPaperAccountRepository:
    """Mock repository for testing"""

    def __init__(self):
        self.account = PaperAccount(
            id=uuid4(),
            starting_capital=Decimal("100000.00"),
            current_capital=Decimal("100000.00"),
            equity=Decimal("100000.00"),
            current_heat=Decimal("0.00"),
        )

    async def get_account(self):
        return self.account

    async def update_account(self, account):
        self.account = account


class MockPaperPositionRepository:
    """Mock repository for testing"""

    def __init__(self):
        self.positions = []

    async def save_position(self, position):
        self.positions.append(position)
        return position

    async def list_open_positions(self):
        return [p for p in self.positions if p.status == "OPEN"]

    async def update_position(self, position):
        for i, p in enumerate(self.positions):
            if p.id == position.id:
                self.positions[i] = position
                break


class MockPaperTradeRepository:
    """Mock repository for testing"""

    def __init__(self):
        self.trades = []

    async def save_trade(self, trade):
        self.trades.append(trade)
        return trade

    async def list_trades(self, limit, offset):
        return self.trades[offset : offset + limit], len(self.trades)


def create_test_signal(
    symbol: str = "AAPL",
    entry_price: Decimal = Decimal("150.00"),
    stop_loss: Decimal = Decimal("148.00"),
    target: Decimal = Decimal("154.00"),
    position_size: Decimal = Decimal("100"),
) -> TradeSignal:
    """Create a test trade signal"""
    signal_id = uuid4()

    targets = TargetLevels(
        primary_target=target,
        secondary_targets=[target],
    )

    confidence = ConfidenceComponents(
        pattern_confidence=85,
        phase_confidence=80,
        volume_confidence=75,
        overall_confidence=80,
    )

    validation = ValidationChain(
        pattern_id=signal_id,
        overall_status=ValidationStatus.PASS,
        validation_results=[],
    )

    # Calculate R-multiple: (target - entry) / (entry - stop)
    risk_per_share = entry_price - stop_loss
    reward_per_share = target - entry_price
    r_multiple = reward_per_share / risk_per_share if risk_per_share != 0 else Decimal("0")

    return TradeSignal(
        id=signal_id,
        asset_class="STOCK",
        symbol=symbol,
        pattern_type="SPRING",
        phase="C",
        timeframe="1D",
        entry_price=entry_price,
        stop_loss=stop_loss,
        target_levels=targets,
        position_size=position_size,
        position_size_unit="SHARES",
        leverage=Decimal("1.0"),
        margin_requirement=Decimal("0"),
        notional_value=entry_price * position_size,
        risk_amount=(entry_price - stop_loss) * position_size,
        r_multiple=r_multiple,
        confidence_score=80,
        confidence_components=confidence,
        validation_chain=validation,
        status="PENDING",
        rejection_reasons=[],
        pattern_data={},
        volume_analysis={},
        campaign_id=None,
        timestamp=datetime.now(UTC),
        created_at=datetime.now(UTC),
        schema_version=1,
    )


class TestPaperTradingServiceExecution:
    """Test signal execution"""

    @pytest.mark.asyncio
    async def test_execute_signal_creates_position(self):
        """Test that executing a signal creates a paper position"""
        # Setup
        config = PaperTradingConfig()
        broker = PaperBrokerAdapter(config)
        account_repo = MockPaperAccountRepository()
        position_repo = MockPaperPositionRepository()
        trade_repo = MockPaperTradeRepository()

        service = PaperTradingService(account_repo, position_repo, trade_repo, broker)

        signal = create_test_signal()
        market_price = Decimal("150.00")

        # Execute
        position = await service.execute_signal(signal, market_price)

        # Assert
        assert position is not None
        assert position.symbol == "AAPL"
        assert position.quantity == Decimal("100")
        assert position.status == "OPEN"
        assert len(position_repo.positions) == 1

    @pytest.mark.asyncio
    async def test_execute_signal_updates_account_capital(self):
        """Test that executing signal reduces available capital"""
        # Setup
        config = PaperTradingConfig()
        broker = PaperBrokerAdapter(config)
        account_repo = MockPaperAccountRepository()
        position_repo = MockPaperPositionRepository()
        trade_repo = MockPaperTradeRepository()

        service = PaperTradingService(account_repo, position_repo, trade_repo, broker)

        initial_capital = account_repo.account.current_capital
        signal = create_test_signal()
        market_price = Decimal("150.00")

        # Execute
        await service.execute_signal(signal, market_price)

        # Assert - capital should be reduced
        assert account_repo.account.current_capital < initial_capital

    @pytest.mark.asyncio
    async def test_execute_signal_rejects_excessive_risk(self):
        """Test that signals exceeding 2% per-trade risk are rejected"""
        # Setup
        config = PaperTradingConfig()
        broker = PaperBrokerAdapter(config)
        account_repo = MockPaperAccountRepository()
        position_repo = MockPaperPositionRepository()
        trade_repo = MockPaperTradeRepository()

        service = PaperTradingService(account_repo, position_repo, trade_repo, broker)

        # Create signal with excessive risk (>2%)
        # $100k equity, 2% = $2k max risk
        # Risk per share: $10, so max 200 shares
        # Let's try 500 shares = $5k risk = 5%
        signal = create_test_signal(
            entry_price=Decimal("100.00"),
            stop_loss=Decimal("90.00"),  # $10 risk per share
            position_size=Decimal("500"),  # $5k total risk = 5%
        )
        market_price = Decimal("100.00")

        # Execute and expect rejection
        with pytest.raises(RiskLimitExceededError) as exc_info:
            await service.execute_signal(signal, market_price)

        assert "per_trade_risk" in str(exc_info.value.limit_type)

    @pytest.mark.asyncio
    async def test_execute_signal_rejects_excessive_heat(self):
        """Test that signals exceeding 10% portfolio heat are rejected"""
        # Setup
        config = PaperTradingConfig()
        broker = PaperBrokerAdapter(config)
        account_repo = MockPaperAccountRepository()
        position_repo = MockPaperPositionRepository()
        trade_repo = MockPaperTradeRepository()

        service = PaperTradingService(account_repo, position_repo, trade_repo, broker)

        # Execute multiple signals to build up heat
        # Each position: $10 entry, $9.90 stop = $0.10 risk/share
        # 20,000 shares × $0.10 = $2000 risk = 2% of $100k equity
        # 20,000 shares × $10.002 fill = $200,040 capital needed - TOO MUCH
        # Better: Use smaller entry price
        # $1 entry, $0.99 stop = $0.01 risk/share
        # 20,000 shares × $0.01 = $200 risk (only 0.2%, need 10x)
        # OR: 200,000 shares × $0.01 = $2000 risk = 2% of $100k
        # Capital needed: 200,000 × $1.0002 = $200,040 - STILL TOO MUCH!
        #
        # Solution: Start with larger account OR use leverage-like sizing
        # Let's use entry=$10, stop=$9.98, 10,000 shares
        # Risk: 10,000 × $0.02 = $200 (0.2% of $100k) - too small
        # 100,000 shares × $0.02 = $2000 (2% of $100k) - capital=$1,000,200
        #
        # BETTER APPROACH: Entry $1, Stop $0.98, 100,000 shares
        # Risk: 100,000 × $0.02 = $2000 = 2%
        # Capital: 100,000 × $1.0002 = $100,020
        # With 5 positions: Need ~$500k capital... Still too much!
        #
        # FINAL APPROACH: Use $1M equity, 10,000 shares per position
        # Each: 10,000 shares × $2 risk/share = $20,000 risk = 2% of $1M
        # Capital needed: 5 positions × 10,000 shares × $100.02 = $5,001,000
        account_repo.account.starting_capital = Decimal("10000000.00")  # $10M for capital
        account_repo.account.current_capital = Decimal("10000000.00")
        account_repo.account.equity = Decimal("1000000.00")  # But equity is $1M for heat calc

        # Execute 4 positions (will add 8.08% heat)
        for i in range(4):
            signal = create_test_signal(
                symbol=f"STOCK{i}",
                entry_price=Decimal("100.00"),
                stop_loss=Decimal("98.00"),  # $2 risk/share
                target=Decimal("106.00"),  # $6 reward = 3R
                position_size=Decimal("10000"),  # 10,000 × $2 = $20,000 risk = 2% of $1M
            )
            await service.execute_signal(signal, Decimal("100.00"))

        # Heat should now be ~8% (4 positions × 2% each)
        # Try one more 2% signal - should be rejected (would push to 10.08%)
        signal = create_test_signal(
            symbol="STOCK4",
            entry_price=Decimal("100.00"),
            stop_loss=Decimal("98.00"),
            target=Decimal("106.00"),
            position_size=Decimal("10000"),  # 2% risk - will exceed 10% limit
        )

        with pytest.raises(RiskLimitExceededError) as exc_info:
            await service.execute_signal(signal, Decimal("100.00"))

        assert "portfolio_heat" in str(exc_info.value.limit_type)


class TestPaperTradingServiceMetrics:
    """Test performance metrics calculation"""

    @pytest.mark.asyncio
    async def test_calculate_performance_metrics_empty(self):
        """Test metrics calculation with no trades"""
        # Setup
        config = PaperTradingConfig()
        broker = PaperBrokerAdapter(config)
        account_repo = MockPaperAccountRepository()
        position_repo = MockPaperPositionRepository()
        trade_repo = MockPaperTradeRepository()

        service = PaperTradingService(account_repo, position_repo, trade_repo, broker)

        # Execute
        metrics = await service.calculate_performance_metrics()

        # Assert
        assert metrics["total_trades"] == 0
        assert metrics["win_rate"] == 0.0
        assert metrics["average_r_multiple"] == 0.0

    @pytest.mark.asyncio
    async def test_validate_live_trading_eligibility_not_ready(self):
        """Test eligibility validation when not ready"""
        # Setup
        config = PaperTradingConfig()
        broker = PaperBrokerAdapter(config)
        account_repo = MockPaperAccountRepository()
        position_repo = MockPaperPositionRepository()
        trade_repo = MockPaperTradeRepository()

        # Set start date to recent (< 90 days)
        account_repo.account.paper_trading_start_date = datetime.now(UTC)
        account_repo.account.total_trades = 5  # < 20 required

        service = PaperTradingService(account_repo, position_repo, trade_repo, broker)

        # Execute
        eligibility = await service.validate_live_trading_eligibility()

        # Assert
        assert eligibility["eligible"] is False
        assert eligibility["checks"]["duration"] is False
        assert eligibility["checks"]["trade_count"] is False


class TestPaperTradingServiceErrorHandling:
    """Test error handling"""

    @pytest.mark.asyncio
    async def test_execute_signal_no_account_raises_error(self):
        """Test that executing without account raises error"""
        # Setup
        config = PaperTradingConfig()
        broker = PaperBrokerAdapter(config)

        # Mock repo that returns None
        class NoAccountRepo:
            async def get_account(self):
                return None

        account_repo = NoAccountRepo()
        position_repo = MockPaperPositionRepository()
        trade_repo = MockPaperTradeRepository()

        service = PaperTradingService(account_repo, position_repo, trade_repo, broker)

        signal = create_test_signal()

        # Execute and expect error
        with pytest.raises(PaperAccountNotFoundError):
            await service.execute_signal(signal, Decimal("150.00"))
