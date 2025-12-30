"""
Integration tests for Paper Trading end-to-end flow (Story 12.8 Task 18)

Tests the complete paper trading lifecycle including:
- Enabling paper trading
- Executing signals
- Position management
- Trade completion
- Account metrics updates

Author: Story 12.8
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.brokers.paper_broker_adapter import PaperBrokerAdapter
from src.database import Base
from src.models.paper_trading import PaperAccount, PaperTradingConfig
from src.models.signal import ConfidenceComponents, TargetLevels, TradeSignal
from src.models.validation import StageValidationResult, ValidationChain, ValidationStatus
from src.repositories.paper_account_repository import PaperAccountRepository
from src.repositories.paper_position_repository import PaperPositionRepository
from src.repositories.paper_trade_repository import PaperTradeRepository
from src.trading.paper_trading_service import PaperTradingService


@pytest.fixture
async def test_db_session():
    """Create a test database session with in-memory SQLite."""
    # Create in-memory SQLite database
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Provide session
    async with async_session_maker() as session:
        yield session

    # Cleanup
    await engine.dispose()


@pytest.fixture
def paper_config():
    """Create default paper trading configuration."""
    return PaperTradingConfig(
        enabled=True,
        starting_capital=Decimal("100000.00"),
        commission_per_share=Decimal("0.005"),
        slippage_percentage=Decimal("0.02"),
        use_realistic_fills=True,
    )


@pytest.fixture
def mock_signal():
    """Create a mock trading signal for testing."""
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
        asset_class="STOCK",
        symbol="AAPL",
        pattern_type="SPRING",
        phase="C",
        timeframe="1h",
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("148.00"),
        target_levels=targets,
        position_size=Decimal("100"),
        position_size_unit="SHARES",
        leverage=Decimal("1.0"),
        margin_requirement=Decimal("0"),
        notional_value=Decimal("15000.00"),
        risk_amount=Decimal("200.00"),
        r_multiple=Decimal("3.0"),
        confidence_score=85,
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


@pytest.mark.asyncio
async def test_complete_paper_trading_flow(test_db_session, paper_config, mock_signal):
    """
    Test complete paper trading flow from enable to trade completion.

    Steps:
    1. Enable paper trading
    2. Execute signal and create position
    3. Verify position created correctly
    4. Simulate price movement to stop loss
    5. Update positions and verify trade closed
    6. Verify account metrics updated
    """
    session = test_db_session

    # Initialize repositories
    account_repo = PaperAccountRepository(session)
    position_repo = PaperPositionRepository(session)
    trade_repo = PaperTradeRepository(session)

    # Initialize broker and service
    broker = PaperBrokerAdapter(paper_config)
    service = PaperTradingService(account_repo, position_repo, trade_repo, broker)

    # Step 1: Enable paper trading
    account = PaperAccount(
        starting_capital=paper_config.starting_capital,
        current_capital=paper_config.starting_capital,
        equity=paper_config.starting_capital,
    )
    saved_account = await account_repo.create_account(account)
    # Note: create_account commits automatically

    assert saved_account is not None
    assert saved_account.starting_capital == Decimal("100000.00")
    assert saved_account.current_capital == Decimal("100000.00")

    # Step 2: Execute signal
    market_price = Decimal("150.00")
    position = await service.execute_signal(mock_signal, market_price)
    # Note: execute_signal commits automatically via repository calls

    # Step 3: Verify position created
    assert position is not None
    assert position.symbol == "AAPL"
    assert position.quantity == Decimal("100")
    assert position.status == "OPEN"
    assert position.entry_price == Decimal("150.03")  # 150.00 + 0.02% slippage
    assert position.stop_loss == Decimal("148.00")

    # Verify account updated
    account = await account_repo.get_account()
    assert account.current_capital < Decimal("100000.00")  # Capital reduced by position cost
    assert account.current_heat > Decimal("0")  # Portfolio heat increased

    # Step 4: Get open positions
    open_positions = await position_repo.list_open_positions()
    assert len(open_positions) == 1
    assert open_positions[0].id == position.id

    # Step 5: Simulate price drop to stop loss
    # Manually trigger stop hit by setting current price below stop
    position.current_price = Decimal("147.50")  # Below stop loss of 148.00
    await position_repo.update_position(position)
    await session.commit()

    # Update positions (should close position at stop)
    # Note: We need to manually simulate this since we don't have real market data
    # In production, update_positions() would fetch current prices from MarketDataService

    # Manually close the position to simulate stop hit
    trade = broker.close_position(position, Decimal("148.00"), "STOP_LOSS")
    await trade_repo.save_trade(trade)

    position.status = "STOPPED"  # Valid status per PaperPosition model
    await position_repo.update_position(position)

    # Update account
    account = await account_repo.get_account()
    account.current_capital += trade.exit_price * trade.quantity - trade.commission_total
    account.total_realized_pnl += trade.realized_pnl
    account.total_commission_paid += trade.commission_total
    account.total_slippage_cost += trade.slippage_total
    account.total_trades += 1
    account.losing_trades += 1

    await account_repo.update_account(account)
    await session.commit()

    # Step 6: Verify trade completed
    trades, total = await trade_repo.list_trades(limit=10, offset=0)
    assert total == 1
    assert trades[0].symbol == "AAPL"
    assert trades[0].exit_reason == "STOP_LOSS"
    assert trades[0].realized_pnl < Decimal("0")  # Loss on stop
    assert trades[0].r_multiple_achieved < Decimal("0")  # Negative R

    # Step 7: Verify account metrics
    account = await account_repo.get_account()
    assert account.total_trades == 1
    assert account.losing_trades == 1
    assert account.winning_trades == 0
    assert account.total_realized_pnl < Decimal("0")
    assert account.total_commission_paid > Decimal("0")
    assert account.total_slippage_cost > Decimal("0")

    # Step 8: Verify no open positions remain
    open_positions = await position_repo.list_open_positions()
    assert len(open_positions) == 0


@pytest.mark.asyncio
async def test_winning_trade_flow(test_db_session, paper_config, mock_signal):
    """Test paper trading flow with a winning trade hitting target."""
    session = test_db_session

    # Initialize repositories
    account_repo = PaperAccountRepository(session)
    position_repo = PaperPositionRepository(session)
    trade_repo = PaperTradeRepository(session)

    # Initialize broker and service
    broker = PaperBrokerAdapter(paper_config)
    service = PaperTradingService(account_repo, position_repo, trade_repo, broker)

    # Enable paper trading
    account = PaperAccount(
        starting_capital=paper_config.starting_capital,
        current_capital=paper_config.starting_capital,
        equity=paper_config.starting_capital,
    )
    await account_repo.create_account(account)
    await session.commit()

    # Execute signal
    market_price = Decimal("150.00")
    position = await service.execute_signal(mock_signal, market_price)
    await session.commit()

    assert position is not None

    # Simulate price hitting target
    position.current_price = Decimal("152.50")
    await position_repo.update_position(position)
    await session.commit()

    # Close position at target
    trade = broker.close_position(position, Decimal("152.00"), "TARGET_1")
    await trade_repo.save_trade(trade)

    position.status = "TARGET_1_HIT"  # Valid status per PaperPosition model
    await position_repo.update_position(position)

    # Update account
    account = await account_repo.get_account()
    account.current_capital += trade.exit_price * trade.quantity - trade.commission_total
    account.total_realized_pnl += trade.realized_pnl
    account.total_commission_paid += trade.commission_total
    account.total_slippage_cost += trade.slippage_total
    account.total_trades += 1
    account.winning_trades += 1

    await account_repo.update_account(account)
    await session.commit()

    # Verify winning trade
    trades, total = await trade_repo.list_trades(limit=10, offset=0)
    assert total == 1
    assert trades[0].exit_reason == "TARGET_1"
    assert trades[0].realized_pnl > Decimal("0")  # Profit
    assert trades[0].r_multiple_achieved > Decimal("0")  # Positive R

    # Verify account metrics
    account = await account_repo.get_account()
    assert account.total_trades == 1
    assert account.winning_trades == 1
    assert account.losing_trades == 0
    assert account.total_realized_pnl > Decimal("0")


@pytest.mark.asyncio
async def test_risk_limit_validation(test_db_session, paper_config):
    """Test that risk limits are enforced correctly."""
    session = test_db_session

    # Initialize repositories
    account_repo = PaperAccountRepository(session)
    position_repo = PaperPositionRepository(session)
    trade_repo = PaperTradeRepository(session)

    # Initialize broker and service
    broker = PaperBrokerAdapter(paper_config)
    service = PaperTradingService(account_repo, position_repo, trade_repo, broker)

    # Enable paper trading
    account = PaperAccount(
        starting_capital=Decimal("10000.00"),  # Smaller capital to trigger risk limits
        current_capital=Decimal("10000.00"),
        equity=Decimal("10000.00"),
    )
    await account_repo.create_account(account)
    await session.commit()

    # Create signal with large position size that exceeds 2% risk limit
    confidence = ConfidenceComponents(
        pattern_confidence=88,
        phase_confidence=82,
        volume_confidence=80,
        overall_confidence=85,
    )

    targets = TargetLevels(
        primary_target=Decimal("200.00"),
        secondary_targets=[Decimal("180.00"), Decimal("190.00")],
    )

    validation = ValidationChain(
        pattern_id=uuid4(),
        overall_status=ValidationStatus.PASS,
        validation_results=[
            StageValidationResult(
                stage="Volume", status=ValidationStatus.PASS, validator_id="VOLUME_VALIDATOR"
            )
        ],
    )

    # Signal with $10 stop ($150 - $140) and 200 shares = $2000 risk on $10000 account = 20% risk
    risky_signal = TradeSignal(
        asset_class="STOCK",
        symbol="TSLA",
        pattern_type="SPRING",
        phase="C",
        timeframe="1h",
        entry_price=Decimal("150.00"),
        stop_loss=Decimal("140.00"),  # $10 stop
        target_levels=targets,  # Primary target is 200.00
        position_size=Decimal("200"),  # 200 shares = $2000 risk
        position_size_unit="SHARES",
        leverage=Decimal("1.0"),
        margin_requirement=Decimal("0"),
        notional_value=Decimal("30000.00"),
        risk_amount=Decimal("2000.00"),
        r_multiple=Decimal("5.0"),  # (200 - 150) / (150 - 140) = 50 / 10 = 5R
        confidence_score=85,
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

    # Should raise RiskLimitExceededError
    from src.trading.exceptions import RiskLimitExceededError

    with pytest.raises(RiskLimitExceededError) as exc_info:
        await service.execute_signal(risky_signal, Decimal("150.00"))

    assert exc_info.value.limit_type == "per_trade_risk"
    assert exc_info.value.limit_value == Decimal("2.0")
    assert exc_info.value.actual_value > Decimal("2.0")


@pytest.mark.asyncio
async def test_performance_metrics_calculation(test_db_session, paper_config, mock_signal):
    """Test that performance metrics are calculated correctly."""
    session = test_db_session

    # Initialize repositories
    account_repo = PaperAccountRepository(session)
    position_repo = PaperPositionRepository(session)
    trade_repo = PaperTradeRepository(session)

    # Initialize broker and service
    broker = PaperBrokerAdapter(paper_config)
    service = PaperTradingService(account_repo, position_repo, trade_repo, broker)

    # Enable paper trading
    account = PaperAccount(
        starting_capital=paper_config.starting_capital,
        current_capital=paper_config.starting_capital,
        equity=paper_config.starting_capital,
    )
    await account_repo.create_account(account)
    await session.commit()

    # Execute and close 2 winning trades and 1 losing trade
    for i in range(3):
        # Execute signal
        position = await service.execute_signal(mock_signal, Decimal("150.00"))
        await session.commit()

        # Close position (first 2 wins, last loses)
        if i < 2:
            exit_price = Decimal("152.00")
            exit_reason = "TARGET_1"
            position_status = "TARGET_1_HIT"  # Valid status
        else:
            exit_price = Decimal("148.00")
            exit_reason = "STOP_LOSS"
            position_status = "STOPPED"  # Valid status

        trade = broker.close_position(position, exit_price, exit_reason)
        await trade_repo.save_trade(trade)

        position.status = position_status
        await position_repo.update_position(position)

        account = await account_repo.get_account()
        account.current_capital += trade.exit_price * trade.quantity - trade.commission_total
        account.total_realized_pnl += trade.realized_pnl
        account.total_commission_paid += trade.commission_total
        account.total_slippage_cost += trade.slippage_total
        account.total_trades += 1

        if trade.realized_pnl > Decimal("0"):
            account.winning_trades += 1
        else:
            account.losing_trades += 1

        await account_repo.update_account(account)
        await session.commit()

    # Calculate performance metrics
    metrics = await service.calculate_performance_metrics()

    # Verify metrics
    assert metrics["total_trades"] == 3
    assert metrics["winning_trades"] == 2
    assert metrics["losing_trades"] == 1
    assert metrics["win_rate"] == pytest.approx(66.67, rel=0.1)  # 2/3 = 66.67%
    assert metrics["total_realized_pnl"] != 0
    assert "average_r_multiple" in metrics
    assert "max_drawdown" in metrics
