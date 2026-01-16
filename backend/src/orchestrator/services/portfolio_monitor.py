"""
Portfolio Monitor Service.

Provides portfolio context building and monitoring for risk validation.

Story 18.10.5: Services Extraction and Orchestrator Facade (AC2)
"""

from decimal import Decimal
from typing import Any, Protocol

import structlog

from src.models.portfolio import PortfolioContext
from src.models.risk import CorrelationConfig

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
        """
        self._position_repo = position_repo
        self._campaign_repo = campaign_repo
        self._account_service = account_service
        self._default_equity = default_equity
        self._max_sector_correlation = max_sector_correlation
        self._max_asset_class_correlation = max_asset_class_correlation
        self._enforcement_mode = enforcement_mode

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

    async def _get_active_campaigns(self) -> list[Any]:
        """Get active campaigns from repository or empty list."""
        if self._campaign_repo:
            try:
                return await self._campaign_repo.get_active_campaigns()
            except Exception as e:
                logger.warning("campaigns_fetch_failed", error=str(e))
        return []

    async def get_portfolio_heat(self) -> Decimal:
        """
        Calculate current portfolio heat (total risk exposure).

        Returns sum of risk amounts for all open positions as
        percentage of account equity.
        """
        context = await self.build_context()
        if context.account_equity <= 0:
            return Decimal("0")

        total_risk = sum(getattr(p, "risk_amount", Decimal("0")) for p in context.open_positions)
        heat = (total_risk / context.account_equity) * 100

        logger.debug(
            "portfolio_heat_calculated",
            total_risk=str(total_risk),
            equity=str(context.account_equity),
            heat_pct=str(heat),
        )

        return heat
