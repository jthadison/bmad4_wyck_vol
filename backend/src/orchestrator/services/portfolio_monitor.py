"""
Portfolio Monitor Service.

Provides portfolio context building and monitoring for risk validation.

Story 18.10.5: Services Extraction and Orchestrator Facade (AC2)
Story 23.13: Daily P&L tracking integration
P2a: Wire portfolio monitor to real PostgreSQL position queries.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any, Protocol

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from src.models.correlation_campaign import CampaignForCorrelation
from src.models.portfolio import PortfolioContext, Position
from src.models.risk import CorrelationConfig
from src.repositories.models import CampaignModel, PositionModel

if TYPE_CHECKING:
    from src.monitoring.daily_pnl_tracker import DailyPnLTracker

logger = structlog.get_logger(__name__)


class PositionRepository(Protocol):
    """Protocol for position data access."""

    async def get_open_positions(self) -> list[Any]:
        """Get all open positions."""
        ...


class CampaignRepository(Protocol):
    """Protocol for campaign data access."""

    async def get_active_campaigns(self) -> list[Any]:
        """Get all active campaigns."""
        ...


class AccountService(Protocol):
    """Protocol for account data access."""

    async def get_equity(self) -> Decimal:
        """Get current account equity."""
        ...


class SqlPositionRepository:
    """Concrete PositionRepository backed by PostgreSQL via async_session_maker."""

    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        default_equity: Decimal = Decimal("100000.00"),
    ) -> None:
        self._session_maker = session_maker
        self._default_equity = default_equity

    async def get_open_positions(self) -> list[Any]:
        """Query open positions and convert to domain Position dataclasses."""
        async with self._session_maker() as session:
            result = await session.execute(
                select(PositionModel).where(PositionModel.status == "OPEN")
            )
            rows = result.scalars().all()

        equity = self._default_equity
        positions: list[Position] = []
        for row in rows:
            risk_dollars = abs(row.entry_price - row.stop_loss) * row.shares
            risk_pct = (risk_dollars / equity * 100) if equity > 0 else Decimal("0")
            positions.append(
                Position(
                    symbol=row.symbol,
                    position_risk_pct=risk_pct,
                    status=row.status,
                    campaign_id=row.campaign_id,
                )
            )
        return positions


class SqlCampaignRepository:
    """Concrete CampaignRepository backed by PostgreSQL via async_session_maker."""

    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        default_equity: Decimal = Decimal("100000.00"),
    ) -> None:
        self._session_maker = session_maker
        self._default_equity = default_equity

    async def get_active_campaigns(self) -> list[Any]:
        """Query active campaigns and convert to CampaignForCorrelation."""
        async with self._session_maker() as session:
            result = await session.execute(
                select(CampaignModel)
                .where(CampaignModel.status.in_(["ACTIVE", "MARKUP"]))
                .options(selectinload(CampaignModel.positions))
            )
            rows = result.scalars().all()

        equity = self._default_equity
        campaigns: list[CampaignForCorrelation] = []
        for row in rows:
            # Convert child positions to domain Position dataclasses
            domain_positions: list[Position] = []
            for p in row.positions:
                if p.status != "OPEN":
                    continue
                risk_dollars = abs(p.entry_price - p.stop_loss) * p.shares
                risk_pct = (risk_dollars / equity * 100) if equity > 0 else Decimal("0")
                domain_positions.append(
                    Position(
                        symbol=p.symbol,
                        position_risk_pct=risk_pct,
                        status=p.status,
                        campaign_id=p.campaign_id,
                    )
                )
            total_risk = sum(p.position_risk_pct for p in domain_positions)
            campaigns.append(
                CampaignForCorrelation(
                    campaign_id=row.id,
                    symbol=row.symbol,
                    sector="unknown",
                    asset_class="stock",
                    total_campaign_risk=total_risk,
                    positions=domain_positions,
                    status=row.status,
                )
            )
        return campaigns


class PortfolioMonitor:
    """
    Service for portfolio monitoring and context building.

    Provides portfolio state for risk validation including equity,
    open positions, active campaigns, and correlation configuration.

    Example:
        >>> monitor = PortfolioMonitor()
        >>> context = await monitor.build_context()
        >>> risk_manager.validate(signal, context)
    """

    # Default configuration values
    DEFAULT_EQUITY = Decimal("100000.00")
    DEFAULT_MAX_SECTOR_CORRELATION = Decimal("6.0")
    DEFAULT_MAX_ASSET_CLASS_CORRELATION = Decimal("15.0")
    DEFAULT_ENFORCEMENT_MODE = "strict"

    def __init__(
        self,
        position_repo: PositionRepository | None = None,
        campaign_repo: CampaignRepository | None = None,
        account_service: AccountService | None = None,
        default_equity: Decimal = DEFAULT_EQUITY,
        max_sector_correlation: Decimal = DEFAULT_MAX_SECTOR_CORRELATION,
        max_asset_class_correlation: Decimal = DEFAULT_MAX_ASSET_CLASS_CORRELATION,
        enforcement_mode: str = DEFAULT_ENFORCEMENT_MODE,
        pnl_tracker: DailyPnLTracker | None = None,
    ) -> None:
        """
        Initialize portfolio monitor with optional dependencies.

        Args:
            position_repo: Repository for position data
            campaign_repo: Repository for campaign data
            account_service: Service for account data
            default_equity: Default equity when account service unavailable
            max_sector_correlation: Max allowed sector correlation (default 6.0%)
            max_asset_class_correlation: Max allowed asset class correlation (default 15.0%)
            enforcement_mode: Correlation enforcement mode (default "strict")
            pnl_tracker: Optional daily P&L tracker (Story 23.13)
        """
        self._position_repo = position_repo
        self._campaign_repo = campaign_repo
        self._account_service = account_service
        self._default_equity = default_equity
        self._max_sector_correlation = max_sector_correlation
        self._max_asset_class_correlation = max_asset_class_correlation
        self._enforcement_mode = enforcement_mode
        self._pnl_tracker = pnl_tracker

    async def build_context(self) -> PortfolioContext:
        """
        Build portfolio context for risk validation.

        Fetches current account state including equity, positions,
        and campaigns. Uses defaults when repositories unavailable.

        Returns:
            PortfolioContext with current portfolio state
        """
        # Get account equity
        equity = await self._get_equity()

        # Get open positions
        positions = await self._get_open_positions()

        # Get active campaigns
        campaigns = await self._get_active_campaigns()

        context = PortfolioContext(
            account_equity=equity,
            open_positions=positions,
            active_campaigns=campaigns,
            sector_mappings={},
            correlation_config=CorrelationConfig(
                max_sector_correlation=self._max_sector_correlation,
                max_asset_class_correlation=self._max_asset_class_correlation,
                enforcement_mode=self._enforcement_mode,
                sector_mappings={},
            ),
            r_multiple_config={},
        )

        logger.debug(
            "portfolio_context_built",
            equity=str(equity),
            open_positions=len(positions),
            active_campaigns=len(campaigns),
        )

        return context

    async def _get_equity(self) -> Decimal:
        """Get account equity from service or default."""
        if self._account_service:
            try:
                return await self._account_service.get_equity()
            except Exception as e:
                logger.warning("account_equity_fetch_failed", error=str(e))
        return self._default_equity

    async def _get_open_positions(self) -> list[Any]:
        """Get open positions from repository or empty list."""
        if self._position_repo:
            try:
                return await self._position_repo.get_open_positions()
            except Exception as e:
                logger.warning("positions_fetch_failed", error=str(e))
                return []
        logger.warning(
            "no_position_repo_configured",
            detail="Portfolio heat will read 0% — risk monitoring is inactive",
        )
        return []

    async def _get_active_campaigns(self) -> list[Any]:
        """Get active campaigns from repository or empty list."""
        if self._campaign_repo:
            try:
                return await self._campaign_repo.get_active_campaigns()
            except Exception as e:
                logger.warning("campaigns_fetch_failed", error=str(e))
                return []
        logger.warning(
            "no_campaign_repo_configured",
            detail="Active campaigns will read empty — campaign monitoring is inactive",
        )
        return []

    async def get_portfolio_heat(self) -> Decimal:
        """
        Calculate current portfolio heat (total risk exposure).

        Returns sum of position_risk_pct for all open positions.
        The SQL repos already convert ORM rows to domain Position
        dataclasses with position_risk_pct expressed as a percentage
        of account equity, so we sum directly.
        """
        context = await self.build_context()
        if context.account_equity <= 0:
            return Decimal("0")

        heat = sum(
            (getattr(p, "position_risk_pct", Decimal("0")) for p in context.open_positions),
            Decimal("0"),
        )

        logger.debug(
            "portfolio_heat_calculated",
            equity=str(context.account_equity),
            heat_pct=str(heat),
        )

        return heat

    async def record_pnl_update(self, symbol: str, pnl_change: Decimal) -> bool:
        """
        Record a position P&L change and check daily threshold.

        Delegates to the DailyPnLTracker if configured. Returns whether
        the daily P&L threshold has been breached.

        Args:
            symbol: Trading symbol.
            pnl_change: Dollar P&L change (negative for loss).

        Returns:
            True if daily P&L threshold was breached, False otherwise.
            Always returns False if no P&L tracker is configured.
        """
        if not self._pnl_tracker:
            return False

        await self._pnl_tracker.update_pnl(symbol, pnl_change)
        equity = await self._get_equity()
        return await self._pnl_tracker.check_and_notify(equity)
