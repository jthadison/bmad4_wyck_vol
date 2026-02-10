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


# ---------------------------------------------------------------------------
# Helper: create PaperTrade for metrics tests (Story 23.8a)
# ---------------------------------------------------------------------------

from src.models.paper_trading import PaperTrade


def _create_test_trade(
    realized_pnl=Decimal("100.00"),
    r_multiple=Decimal("1.5"),
    exit_reason="TARGET_1",
) -> PaperTrade:
    """Create a PaperTrade for testing metrics calculations."""
    now = datetime.now(UTC)
    return PaperTrade(
        position_id=uuid4(),
        signal_id=uuid4(),
        symbol="AAPL",
        entry_time=now,
        entry_price=Decimal("150.00"),
        exit_time=now,
        exit_price=Decimal("152.00"),
        quantity=Decimal("100"),
        realized_pnl=realized_pnl,
        r_multiple_achieved=r_multiple,
        commission_total=Decimal("1.00"),
        slippage_total=Decimal("3.00"),
        exit_reason=exit_reason,
    )


# ---------------------------------------------------------------------------
# Helper: create BacktestResult for comparison tests (Story 23.8a)
# ---------------------------------------------------------------------------

from datetime import date

from src.models.backtest import BacktestConfig, BacktestMetrics, BacktestResult


def _create_test_backtest_result(
    win_rate=Decimal("0.65"),
    avg_r=Decimal("1.8"),
    max_drawdown=Decimal("0.08"),
    profit_factor=Decimal("2.1"),
) -> BacktestResult:
    """Create a BacktestResult for testing comparison logic."""
    config = BacktestConfig(
        symbol="AAPL",
        timeframe="1d",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        initial_capital=Decimal("100000"),
    )
    metrics = BacktestMetrics(
        win_rate=win_rate,
        average_r_multiple=avg_r,
        max_drawdown=max_drawdown,
        profit_factor=profit_factor,
        total_trades=50,
    )
    return BacktestResult(
        backtest_run_id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        config=config,
        summary=metrics,
    )


# ---------------------------------------------------------------------------
# Story 23.8a: Performance metrics & backtest comparison tests
# ---------------------------------------------------------------------------


class TestPaperTradingServiceProfitFactor:
    """Tests for profit_factor in calculate_performance_metrics (Story 23.8a)."""

    @pytest.mark.asyncio
    async def test_calculate_performance_metrics_includes_profit_factor(self):
        """profit_factor should appear in metrics and be computed correctly."""
        config = PaperTradingConfig()
        broker = PaperBrokerAdapter(config)
        account_repo = MockPaperAccountRepository()
        position_repo = MockPaperPositionRepository()
        trade_repo = MockPaperTradeRepository()

        # Add mix of winning and losing trades
        trade_repo.trades = [
            _create_test_trade(realized_pnl=Decimal("200.00"), r_multiple=Decimal("2.0")),
            _create_test_trade(realized_pnl=Decimal("300.00"), r_multiple=Decimal("3.0")),
            _create_test_trade(
                realized_pnl=Decimal("-100.00"),
                r_multiple=Decimal("-1.0"),
                exit_reason="STOP_LOSS",
            ),
        ]

        service = PaperTradingService(account_repo, position_repo, trade_repo, broker)
        metrics = await service.calculate_performance_metrics()

        assert "profit_factor" in metrics
        # total wins = 200+300 = 500, total losses = 100 => PF = 5.0
        assert metrics["profit_factor"] == pytest.approx(5.0)

    @pytest.mark.asyncio
    async def test_profit_factor_all_winners(self):
        """profit_factor should be inf when there are no losing trades."""
        config = PaperTradingConfig()
        broker = PaperBrokerAdapter(config)
        account_repo = MockPaperAccountRepository()
        position_repo = MockPaperPositionRepository()
        trade_repo = MockPaperTradeRepository()

        trade_repo.trades = [
            _create_test_trade(realized_pnl=Decimal("100.00")),
            _create_test_trade(realized_pnl=Decimal("200.00")),
        ]

        service = PaperTradingService(account_repo, position_repo, trade_repo, broker)
        metrics = await service.calculate_performance_metrics()

        assert metrics["profit_factor"] == 999.99

    @pytest.mark.asyncio
    async def test_profit_factor_no_trades(self):
        """profit_factor should be 0 when there are no trades."""
        config = PaperTradingConfig()
        broker = PaperBrokerAdapter(config)
        account_repo = MockPaperAccountRepository()
        position_repo = MockPaperPositionRepository()
        trade_repo = MockPaperTradeRepository()

        service = PaperTradingService(account_repo, position_repo, trade_repo, broker)
        metrics = await service.calculate_performance_metrics()

        assert metrics["profit_factor"] == 0.0


class TestPaperTradingServiceBacktestComparison:
    """Tests for compare_to_backtest scale normalization & flagging (Story 23.8a)."""

    @pytest.mark.asyncio
    async def test_compare_to_backtest_normalizes_scales(self):
        """Backtest win_rate (0-1) and max_drawdown (0-1) should be scaled to 0-100."""
        config = PaperTradingConfig()
        broker = PaperBrokerAdapter(config)
        account_repo = MockPaperAccountRepository()
        position_repo = MockPaperPositionRepository()
        trade_repo = MockPaperTradeRepository()

        # Set up trades so paper metrics are computed
        trade_repo.trades = [
            _create_test_trade(realized_pnl=Decimal("200.00"), r_multiple=Decimal("2.0")),
            _create_test_trade(
                realized_pnl=Decimal("-50.00"),
                r_multiple=Decimal("-0.5"),
                exit_reason="STOP_LOSS",
            ),
        ]

        service = PaperTradingService(account_repo, position_repo, trade_repo, broker)

        backtest = _create_test_backtest_result(
            win_rate=Decimal("0.65"),
            max_drawdown=Decimal("0.08"),
        )

        comparison = await service.compare_to_backtest(backtest)

        # Backtest win_rate 0.65 should become 65.0 in comparison
        assert comparison["backtest_metrics"]["win_rate"] == pytest.approx(65.0)
        # Backtest max_drawdown 0.08 should become 8.0 in comparison
        assert comparison["backtest_metrics"]["max_drawdown"] == pytest.approx(8.0)

    @pytest.mark.asyncio
    async def test_compare_to_backtest_detects_warnings(self):
        """Deviations >10% but <=20% should produce warnings."""
        config = PaperTradingConfig()
        broker = PaperBrokerAdapter(config)
        account_repo = MockPaperAccountRepository()
        position_repo = MockPaperPositionRepository()
        trade_repo = MockPaperTradeRepository()

        # Paper metrics: win_rate will be 50% (1 of 2 trades wins)
        trade_repo.trades = [
            _create_test_trade(realized_pnl=Decimal("100.00"), r_multiple=Decimal("1.0")),
            _create_test_trade(
                realized_pnl=Decimal("-80.00"),
                r_multiple=Decimal("-0.8"),
                exit_reason="STOP_LOSS",
            ),
        ]

        service = PaperTradingService(account_repo, position_repo, trade_repo, broker)

        # Backtest win_rate=0.58 => 58%. Paper=50%. Delta=13.8% (warning)
        backtest = _create_test_backtest_result(
            win_rate=Decimal("0.58"),
            avg_r=Decimal("0.10"),  # avg_r: paper ~0.1, backtest 0.1 => ~0% delta
            max_drawdown=Decimal("0.0"),
            profit_factor=Decimal("1.25"),  # paper PF=100/80=1.25 => 0% delta
        )

        comparison = await service.compare_to_backtest(backtest)

        assert comparison["status"] in ("WARNING", "ERROR")
        has_win_rate_issue = any(
            "win_rate" in w for w in comparison["warnings"] + comparison["errors"]
        )
        assert has_win_rate_issue

    @pytest.mark.asyncio
    async def test_compare_to_backtest_detects_errors(self):
        """Deviations >20% should produce errors."""
        config = PaperTradingConfig()
        broker = PaperBrokerAdapter(config)
        account_repo = MockPaperAccountRepository()
        position_repo = MockPaperPositionRepository()
        trade_repo = MockPaperTradeRepository()

        # Paper win_rate will be 50% (1 of 2)
        trade_repo.trades = [
            _create_test_trade(realized_pnl=Decimal("100.00"), r_multiple=Decimal("1.0")),
            _create_test_trade(
                realized_pnl=Decimal("-80.00"),
                r_multiple=Decimal("-0.8"),
                exit_reason="STOP_LOSS",
            ),
        ]

        service = PaperTradingService(account_repo, position_repo, trade_repo, broker)

        # Backtest win_rate=0.80 => 80%. Paper=50%. Delta=37.5% (error)
        backtest = _create_test_backtest_result(
            win_rate=Decimal("0.80"),
            avg_r=Decimal("0.10"),
            max_drawdown=Decimal("0.0"),
            profit_factor=Decimal("1.25"),
        )

        comparison = await service.compare_to_backtest(backtest)

        assert comparison["status"] == "ERROR"
        assert len(comparison["errors"]) > 0
        has_win_rate_error = any("win_rate" in e for e in comparison["errors"])
        assert has_win_rate_error

    @pytest.mark.asyncio
    async def test_compare_to_backtest_ok_when_close(self):
        """No warnings/errors when paper and backtest metrics are close."""
        config = PaperTradingConfig()
        broker = PaperBrokerAdapter(config)
        account_repo = MockPaperAccountRepository()
        position_repo = MockPaperPositionRepository()
        trade_repo = MockPaperTradeRepository()

        # Paper win_rate = 50%, profit_factor = 100/80 = 1.25
        trade_repo.trades = [
            _create_test_trade(realized_pnl=Decimal("100.00"), r_multiple=Decimal("1.0")),
            _create_test_trade(
                realized_pnl=Decimal("-80.00"),
                r_multiple=Decimal("-0.8"),
                exit_reason="STOP_LOSS",
            ),
        ]

        service = PaperTradingService(account_repo, position_repo, trade_repo, broker)

        # Set backtest metrics very close to paper metrics
        backtest = _create_test_backtest_result(
            win_rate=Decimal("0.50"),  # 50% => same as paper
            avg_r=Decimal("0.10"),  # close to paper avg_r
            max_drawdown=Decimal("0.0"),
            profit_factor=Decimal("1.25"),  # same as paper
        )

        comparison = await service.compare_to_backtest(backtest)

        assert comparison["status"] == "OK"
        assert len(comparison["warnings"]) == 0
        assert len(comparison["errors"]) == 0


# ---------------------------------------------------------------------------
# Story B-3: close_all_positions_atomic tests
# ---------------------------------------------------------------------------

from unittest.mock import AsyncMock, MagicMock

from src.models.paper_trading import PaperPosition


def _create_test_position(
    symbol: str = "AAPL",
    entry_price: Decimal = Decimal("150.00"),
    current_price: Decimal = Decimal("152.00"),
    quantity: Decimal = Decimal("100"),
    stop_loss: Decimal = Decimal("148.00"),
) -> PaperPosition:
    """Create a PaperPosition for testing close_all_positions_atomic."""
    now = datetime.now(UTC)
    return PaperPosition(
        id=uuid4(),
        signal_id=uuid4(),
        symbol=symbol,
        entry_time=now,
        entry_price=entry_price,
        quantity=quantity,
        stop_loss=stop_loss,
        target_1=Decimal("154.00"),
        target_2=Decimal("156.00"),
        current_price=current_price,
        unrealized_pnl=(current_price - entry_price) * quantity,
        status="OPEN",
        commission_paid=Decimal("0.50"),
        slippage_cost=Decimal("3.00"),
    )


class TestCloseAllPositionsAtomic:
    """Tests for close_all_positions_atomic (B-3 fix)."""

    @pytest.mark.asyncio
    async def test_close_all_positions_atomic_empty_list(self):
        """No positions means return 0 with no commit called."""
        config = PaperTradingConfig()
        broker = PaperBrokerAdapter(config)

        mock_session = AsyncMock()
        account_repo = MockPaperAccountRepository()
        account_repo.session = mock_session
        position_repo = MockPaperPositionRepository()
        trade_repo = MockPaperTradeRepository()

        service = PaperTradingService(account_repo, position_repo, trade_repo, broker)

        account = account_repo.account
        result = await service.close_all_positions_atomic([], account)

        assert result == 0
        mock_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_close_all_positions_atomic_closes_multiple(self):
        """3 positions should all close with a single commit and correct account metrics."""
        config = PaperTradingConfig()
        broker = PaperBrokerAdapter(config)

        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        account_repo = MockPaperAccountRepository()
        account_repo.session = mock_session
        position_repo = MockPaperPositionRepository()
        trade_repo = MockPaperTradeRepository()

        service = PaperTradingService(account_repo, position_repo, trade_repo, broker)

        positions = [
            _create_test_position(symbol="AAPL"),
            _create_test_position(symbol="MSFT"),
            _create_test_position(symbol="GOOG"),
        ]

        account = account_repo.account
        initial_trades = account.total_trades

        result = await service.close_all_positions_atomic(positions, account)

        assert result == 3
        # commit called exactly once
        mock_session.commit.assert_awaited_once()
        # session.add called 3 times (one trade DB object per position)
        assert mock_session.add.call_count == 3
        # session.execute called 3 (position updates) + 1 (account update) = 4 times
        assert mock_session.execute.await_count == 4
        # Account trade count incremented by 3
        assert account.total_trades == initial_trades + 3

    @pytest.mark.asyncio
    async def test_close_all_positions_atomic_rolls_back_on_error(self):
        """If broker.close_position raises for position 2 of 3, error propagates (no partial commit)."""
        config = PaperTradingConfig()
        broker = PaperBrokerAdapter(config)

        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        account_repo = MockPaperAccountRepository()
        account_repo.session = mock_session
        position_repo = MockPaperPositionRepository()
        trade_repo = MockPaperTradeRepository()

        service = PaperTradingService(account_repo, position_repo, trade_repo, broker)

        positions = [
            _create_test_position(symbol="AAPL"),
            _create_test_position(symbol="MSFT"),
            _create_test_position(symbol="GOOG"),
        ]

        # Make broker.close_position fail on the second call
        original_close = broker.close_position
        call_count = 0

        def failing_close(position, price, reason):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Simulated broker failure")
            return original_close(position, price, reason)

        broker.close_position = failing_close

        account = account_repo.account

        with pytest.raises(RuntimeError, match="Simulated broker failure"):
            await service.close_all_positions_atomic(positions, account)

        # commit should NOT have been called (error before reaching it)
        mock_session.commit.assert_not_awaited()
