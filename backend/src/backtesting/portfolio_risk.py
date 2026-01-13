"""
Portfolio Risk Management - Story 13.6.4

Purpose:
--------
Portfolio-level risk management for multi-campaign trading:
- Portfolio heat tracking and exit logic (FR6.6.3)
- Correlation cascade detection (FR6.6.4)
- Phase-weighted exit priority
- Weighted average entry price calculation

Key Features:
-------------
1. Portfolio heat exits when approaching 10% max heat limit
2. Exit priority: Phase E first (near target), Phase D last (best opportunity)
3. Correlation cascade detection (3+ correlated positions failing)
4. Weighted entry price for multi-pattern campaigns (Spring + LPS)

Author: Story 13.6.4 Implementation
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

import structlog

from src.backtesting.intraday_campaign_detector import Campaign
from src.models.lps import LPS
from src.models.sos_breakout import SOSBreakout
from src.models.spring import Spring
from src.models.wyckoff_phase import WyckoffPhase

logger = structlog.get_logger(__name__)


# ============================================================================
# Task 1: Portfolio Risk State Model (AC1)
# ============================================================================


@dataclass
class PortfolioRiskState:
    """
    Portfolio-level risk tracking for multi-campaign management.

    Tracks total portfolio heat, active campaigns, and enforces heat limits.
    Heat = percentage of portfolio at risk across all active campaigns.

    Attributes:
        active_campaigns: List of active Campaign objects
        total_heat_pct: Current total heat percentage (0-100)
        max_heat_pct: Maximum allowed heat (default: 10.0% from CLAUDE.md)

    Example:
        >>> portfolio = PortfolioRiskState()
        >>> portfolio.add_campaign(campaign1, Decimal("3.0"))
        True
        >>> portfolio.total_heat_pct
        Decimal('3.0')
    """

    active_campaigns: list[Campaign] = field(default_factory=list)
    total_heat_pct: Decimal = Decimal("0")
    max_heat_pct: Decimal = Decimal("10.0")  # System limit from CLAUDE.md

    def add_campaign(self, campaign: Campaign, risk_pct: Decimal) -> bool:
        """
        Add campaign if within heat limits.

        Args:
            campaign: Campaign to add
            risk_pct: Risk percentage for this campaign

        Returns:
            True if campaign added, False if rejected due to heat limits

        Example:
            >>> portfolio = PortfolioRiskState()
            >>> success = portfolio.add_campaign(campaign, Decimal("3.0"))
            >>> success
            True
        """
        # Check if adding this campaign would exceed max heat
        projected_heat = self.total_heat_pct + risk_pct

        if projected_heat > self.max_heat_pct:
            logger.warning(
                "campaign_rejected_heat_limit",
                campaign_id=campaign.campaign_id,
                current_heat=str(self.total_heat_pct),
                risk_pct=str(risk_pct),
                projected_heat=str(projected_heat),
                max_heat=str(self.max_heat_pct),
            )
            return False

        # Add campaign
        self.active_campaigns.append(campaign)
        self.total_heat_pct += risk_pct

        logger.info(
            "campaign_added_to_portfolio",
            campaign_id=campaign.campaign_id,
            risk_pct=str(risk_pct),
            total_heat=str(self.total_heat_pct),
            active_count=len(self.active_campaigns),
        )

        return True

    def remove_campaign(self, campaign_id: str) -> None:
        """
        Remove campaign and recalculate heat.

        Args:
            campaign_id: ID of campaign to remove

        Example:
            >>> portfolio.remove_campaign("abc123")
            >>> # Campaign removed, heat recalculated
        """
        # Find and remove campaign
        original_count = len(self.active_campaigns)
        self.active_campaigns = [c for c in self.active_campaigns if c.campaign_id != campaign_id]

        if len(self.active_campaigns) < original_count:
            # Recalculate heat
            self.total_heat_pct = self.recalculate_heat()

            logger.info(
                "campaign_removed_from_portfolio",
                campaign_id=campaign_id,
                total_heat=str(self.total_heat_pct),
                active_count=len(self.active_campaigns),
            )
        else:
            logger.warning(
                "campaign_not_found_in_portfolio",
                campaign_id=campaign_id,
            )

    def get_underwater_campaigns(
        self,
        current_prices: dict[str, Decimal],
        threshold_pct: Decimal = Decimal("-1.0"),
    ) -> list[Campaign]:
        """
        Get campaigns below profit threshold.

        Args:
            current_prices: Dict mapping symbol -> current price
            threshold_pct: Profit threshold (default: -1.0%)

        Returns:
            List of campaigns below threshold

        Example:
            >>> prices = {"EUR/USD": Decimal("1.0500")}
            >>> underwater = portfolio.get_underwater_campaigns(prices)
            >>> len(underwater)
            2
        """
        underwater = []

        for campaign in self.active_campaigns:
            if not campaign.patterns:
                continue

            # Get symbol from first pattern
            symbol = campaign.patterns[0].bar.symbol if hasattr(campaign.patterns[0], "bar") else ""

            if symbol not in current_prices:
                continue

            current_price = current_prices[symbol]

            # Calculate profit percentage
            profit_pct = calculate_campaign_profit_pct(campaign, current_price)

            if profit_pct < threshold_pct:
                underwater.append(campaign)

        logger.debug(
            "underwater_campaigns_calculated",
            total_campaigns=len(self.active_campaigns),
            underwater_count=len(underwater),
            threshold_pct=str(threshold_pct),
        )

        return underwater

    def recalculate_heat(self) -> Decimal:
        """
        Recalculate total heat from active campaigns.

        Returns:
            Total heat percentage

        Example:
            >>> heat = portfolio.recalculate_heat()
            >>> heat
            Decimal('7.5')
        """
        # For MVP, use risk_per_share as proxy for heat
        # In production, this would sum actual position sizes * risk_per_share / portfolio value
        total_heat = Decimal("0")

        for campaign in self.active_campaigns:
            if campaign.risk_per_share and campaign.support_level:
                # Simple approximation: risk_pct = (risk_per_share / support_level) * 100
                risk_pct = (campaign.risk_per_share / campaign.support_level) * Decimal("100")
                total_heat += risk_pct

        logger.debug(
            "portfolio_heat_recalculated",
            active_campaigns=len(self.active_campaigns),
            total_heat=str(total_heat),
        )

        return total_heat


# ============================================================================
# Task 2: Portfolio Heat Exit Logic (AC2, AC3, AC7)
# ============================================================================


def get_exit_priority(campaign: Campaign) -> int:
    """
    Calculate exit priority based on Wyckoff phase.

    Lower number = exit first.
    Phase E (near target) exits before Phase D (best opportunity).

    Priority Mapping:
        1 = Phase E (near Jump target, lock in gains)
        2 = Phase C (unconfirmed, higher risk)
        3 = Phase D (best opportunity, protect)
        4 = Phase B (early accumulation)
        5 = Phase A / None (very early)

    Args:
        campaign: Campaign to evaluate

    Returns:
        Priority score (1 = highest priority to exit)

    Example:
        >>> campaign.current_phase = WyckoffPhase.E
        >>> priority = get_exit_priority(campaign)
        >>> priority
        1
    """
    PHASE_PRIORITY = {
        WyckoffPhase.E: 1,  # Near target - exit first
        WyckoffPhase.C: 2,  # Unconfirmed - exit second
        WyckoffPhase.D: 3,  # Best opportunity - exit last
        WyckoffPhase.B: 4,  # Early accumulation
        WyckoffPhase.A: 5,  # Very early
    }

    priority = PHASE_PRIORITY.get(campaign.current_phase, 5)

    logger.debug(
        "exit_priority_calculated",
        campaign_id=campaign.campaign_id,
        phase=campaign.current_phase.value if campaign.current_phase else None,
        priority=priority,
    )

    return priority


def get_campaigns_by_exit_priority(
    campaigns: list[Campaign],
    current_prices: dict[str, Decimal],
) -> list[Campaign]:
    """
    Sort campaigns by exit priority for heat reduction.

    Primary sort: Wyckoff phase (E=1, C=2, D=3)
    Secondary sort: Profit percentage (smallest first)

    Rationale:
        - Exit Phase E first (already near target, lock in)
        - Exit Phase C next (unconfirmed, uncertain)
        - Protect Phase D (best Wyckoff opportunity)
        - Within same phase: exit smallest winners first (preserve big winners)

    Args:
        campaigns: List of campaigns to sort
        current_prices: Dict mapping symbol -> current price

    Returns:
        Campaigns sorted by exit priority (first = exit first)

    Example:
        >>> sorted_campaigns = get_campaigns_by_exit_priority(campaigns, prices)
        >>> sorted_campaigns[0].current_phase
        WyckoffPhase.E  # Phase E campaigns exit first
    """

    def sort_key(campaign: Campaign) -> tuple[int, Decimal]:
        phase_priority = get_exit_priority(campaign)

        # Get symbol from first pattern
        symbol = ""
        if campaign.patterns:
            if hasattr(campaign.patterns[0], "bar"):
                symbol = campaign.patterns[0].bar.symbol
            elif hasattr(campaign.patterns[0], "symbol"):
                symbol = campaign.patterns[0].symbol

        current_price = current_prices.get(symbol, Decimal("0"))
        profit_pct = calculate_campaign_profit_pct(campaign, current_price)

        return (phase_priority, profit_pct)

    sorted_campaigns = sorted(campaigns, key=sort_key)

    logger.info(
        "campaigns_sorted_by_exit_priority",
        total_campaigns=len(campaigns),
        first_campaign_phase=sorted_campaigns[0].current_phase.value
        if sorted_campaigns and sorted_campaigns[0].current_phase
        else None,
    )

    return sorted_campaigns


def check_portfolio_heat(
    portfolio: PortfolioRiskState,
    campaign: Campaign,
    current_price: Decimal,
    heat_threshold_pct: Decimal = Decimal("80.0"),
) -> tuple[bool, Optional[str]]:
    """
    Check if portfolio heat approaching limit warrants exit.

    Logic:
    - Only exit if campaign is profitable (>0.5%)
    - Only exit if heat > threshold (default 80% of max)
    - Exit priority: Phase E first, Phase D last
    - Within same phase: smallest profit exits first

    Args:
        portfolio: Portfolio risk state
        campaign: Campaign to check for exit
        current_price: Current price for campaign symbol
        heat_threshold_pct: Heat threshold percentage (default: 80.0%)

    Returns:
        tuple: (should_exit, exit_reason)

    Example:
        >>> should_exit, reason = check_portfolio_heat(portfolio, campaign, price)
        >>> if should_exit:
        ...     print(reason)
        'PORTFOLIO_HEAT - 9.2% of 10.0% max'
    """
    # Calculate current heat percentage of max
    current_heat_pct = (portfolio.total_heat_pct / portfolio.max_heat_pct) * Decimal("100")

    # Check if heat exceeds threshold
    if current_heat_pct <= heat_threshold_pct:
        logger.debug(
            "portfolio_heat_below_threshold",
            current_heat_pct=str(current_heat_pct),
            threshold=str(heat_threshold_pct),
            campaign_id=campaign.campaign_id,
        )
        return (False, None)

    # Calculate campaign profit
    profit_pct = calculate_campaign_profit_pct(campaign, current_price)

    # AC3: Only exit profitable positions (>0.5%)
    if profit_pct <= Decimal("0.5"):
        logger.debug(
            "campaign_unprofitable_no_heat_exit",
            campaign_id=campaign.campaign_id,
            profit_pct=str(profit_pct),
            current_heat_pct=str(current_heat_pct),
        )
        return (False, None)

    # Get all profitable campaigns for priority sorting
    profitable_campaigns = []
    for c in portfolio.active_campaigns:
        if not c.patterns:
            continue

        symbol = ""
        if hasattr(c.patterns[0], "bar"):
            symbol = c.patterns[0].bar.symbol
        elif hasattr(c.patterns[0], "symbol"):
            symbol = c.patterns[0].symbol

        # Use current_price for the campaign being checked, estimate for others
        c_price = current_price if c.campaign_id == campaign.campaign_id else current_price
        c_profit = calculate_campaign_profit_pct(c, c_price)

        if c_profit > Decimal("0.5"):
            profitable_campaigns.append(c)

    # Sort by exit priority
    sorted_campaigns = get_campaigns_by_exit_priority(
        profitable_campaigns, {campaign.patterns[0].bar.symbol: current_price}
    )

    # Check if this campaign should exit (is it first in priority?)
    if sorted_campaigns and sorted_campaigns[0].campaign_id == campaign.campaign_id:
        exit_reason = (
            f"PORTFOLIO_HEAT - {portfolio.total_heat_pct}% of {portfolio.max_heat_pct}% max"
        )

        logger.warning(
            "portfolio_heat_exit_triggered",
            campaign_id=campaign.campaign_id,
            current_heat=str(portfolio.total_heat_pct),
            max_heat=str(portfolio.max_heat_pct),
            heat_pct=str(current_heat_pct),
            profit_pct=str(profit_pct),
            phase=campaign.current_phase.value if campaign.current_phase else None,
        )

        return (True, exit_reason)

    return (False, None)


def calculate_campaign_profit_pct(campaign: Campaign, current_price: Decimal) -> Decimal:
    """
    Calculate campaign P&L percentage using weighted average entry.

    Team Review Update (AC8):
    - Uses weighted average entry for multi-pattern campaigns
    - Not just first pattern (which underestimates true cost basis)

    Args:
        campaign: Campaign to calculate profit for
        current_price: Current market price

    Returns:
        Profit percentage (positive = profit, negative = loss)

    Example:
        >>> profit = calculate_campaign_profit_pct(campaign, Decimal("1.0650"))
        >>> profit
        Decimal('2.5')  # 2.5% profit
    """
    if not campaign.patterns:
        return Decimal("0")

    # Use weighted average entry price (AC8)
    entry_price = calculate_weighted_entry_price(campaign)

    if entry_price <= 0:
        return Decimal("0")

    profit_pct = ((current_price - entry_price) / entry_price) * Decimal("100")

    logger.debug(
        "campaign_profit_calculated",
        campaign_id=campaign.campaign_id,
        entry_price=str(entry_price),
        current_price=str(current_price),
        profit_pct=str(profit_pct),
    )

    return profit_pct


# ============================================================================
# Task 5: Weighted Average Entry Price (AC8)
# ============================================================================


def calculate_weighted_entry_price(campaign: Campaign) -> Decimal:
    """
    Calculate weighted average entry price for multi-pattern campaigns.

    For campaigns with multiple entry patterns (Spring → LPS add):
    - Extract entry price from each pattern
    - Weight equally if position sizes not available
    - Weight by position size if available

    Pattern Entry Price Extraction:
    - Spring: recovery_price
    - SOSBreakout: breakout_price
    - LPS: bar.close

    Args:
        campaign: Campaign with patterns

    Returns:
        Weighted average entry price

    Example:
        >>> # Spring at $100, LPS at $105
        >>> entry = calculate_weighted_entry_price(campaign)
        >>> entry
        Decimal('102.50')
    """
    entry_prices = []

    for pattern in campaign.patterns:
        entry_price = None

        if isinstance(pattern, Spring) and hasattr(pattern, "recovery_price"):
            entry_price = pattern.recovery_price
        elif isinstance(pattern, SOSBreakout) and hasattr(pattern, "breakout_price"):
            entry_price = pattern.breakout_price
        elif isinstance(pattern, LPS) and hasattr(pattern, "bar"):
            entry_price = pattern.bar.close

        if entry_price is not None and entry_price > 0:
            entry_prices.append(entry_price)

    if not entry_prices:
        logger.warning(
            "no_valid_entry_prices_found",
            campaign_id=campaign.campaign_id,
            pattern_count=len(campaign.patterns),
        )
        return Decimal("0")

    # Equal weight average (position sizing is future enhancement)
    weighted_avg = sum(entry_prices) / Decimal(str(len(entry_prices)))

    logger.debug(
        "weighted_entry_price_calculated",
        campaign_id=campaign.campaign_id,
        pattern_count=len(entry_prices),
        entry_prices=[str(p) for p in entry_prices],
        weighted_avg=str(weighted_avg),
    )

    return weighted_avg


# ============================================================================
# Task 3: Currency Correlation Calculation (AC4)
# ============================================================================


def parse_currency_pair(symbol: str) -> tuple[str, str]:
    """
    Parse currency pair into base and quote currencies.

    Supports two formats:
    - XXX/YYY (e.g., "EUR/USD")
    - XXXYYY (e.g., "EURUSD")

    Args:
        symbol: Currency pair symbol

    Returns:
        tuple: (base_currency, quote_currency)

    Raises:
        ValueError: If symbol cannot be parsed

    Example:
        >>> base, quote = parse_currency_pair("EUR/USD")
        >>> (base, quote)
        ('EUR', 'USD')
        >>> base, quote = parse_currency_pair("EURUSD")
        >>> (base, quote)
        ('EUR', 'USD')
    """
    # Handle XXX/YYY format
    if "/" in symbol:
        parts = symbol.split("/")
        if len(parts) == 2:
            return parts[0].upper(), parts[1].upper()

    # Handle XXXYYY format (6 chars)
    if len(symbol) == 6:
        return symbol[:3].upper(), symbol[3:].upper()

    raise ValueError(f"Cannot parse currency pair: {symbol}")


def get_currency_correlation(symbol1: str, symbol2: str) -> Decimal:
    """
    Calculate correlation between currency pairs.

    Correlation Rules (simplified for MVP):
    - Same quote currency: EUR/USD vs GBP/USD = 0.85
    - Same base currency: EUR/GBP vs EUR/JPY = 0.80
    - Shared currency opposite position: EUR/USD vs USD/JPY = 0.60
    - No shared currencies: EUR/GBP vs AUD/NZD = 0.20

    Args:
        symbol1: First currency pair
        symbol2: Second currency pair

    Returns:
        Correlation coefficient 0.0 to 1.0 (always positive for simplicity)

    Example:
        >>> corr = get_currency_correlation("EUR/USD", "GBP/USD")
        >>> corr
        Decimal('0.85')
        >>> corr = get_currency_correlation("EUR/USD", "AUD/NZD")
        >>> corr
        Decimal('0.20')
    """
    try:
        base1, quote1 = parse_currency_pair(symbol1)
        base2, quote2 = parse_currency_pair(symbol2)
    except ValueError as e:
        logger.warning(
            "currency_correlation_parse_error",
            symbol1=symbol1,
            symbol2=symbol2,
            error=str(e),
        )
        return Decimal("0.20")  # Default to low correlation

    # Same pair
    if base1 == base2 and quote1 == quote2:
        return Decimal("1.0")

    # Same quote currency (highest correlation)
    if quote1 == quote2:
        correlation = Decimal("0.85")
        logger.debug(
            "high_correlation_same_quote",
            symbol1=symbol1,
            symbol2=symbol2,
            correlation=str(correlation),
        )
        return correlation

    # Same base currency
    if base1 == base2:
        correlation = Decimal("0.80")
        logger.debug(
            "high_correlation_same_base",
            symbol1=symbol1,
            symbol2=symbol2,
            correlation=str(correlation),
        )
        return correlation

    # Shared currency in opposite positions
    if base1 == quote2 or quote1 == base2:
        correlation = Decimal("0.60")
        logger.debug(
            "medium_correlation_opposite",
            symbol1=symbol1,
            symbol2=symbol2,
            correlation=str(correlation),
        )
        return correlation

    # No shared currencies
    correlation = Decimal("0.20")
    logger.debug(
        "low_correlation_no_shared",
        symbol1=symbol1,
        symbol2=symbol2,
        correlation=str(correlation),
    )
    return correlation


# ============================================================================
# Task 4: Correlation Cascade Detection (AC5, AC6)
# ============================================================================


def check_correlation_cascade(
    portfolio: PortfolioRiskState,
    campaign: Campaign,
    current_prices: dict[str, Decimal],
    cascade_threshold: int = 3,
    underwater_threshold_pct: Decimal = Decimal("-1.0"),
    correlation_threshold: Decimal = Decimal("0.7"),
) -> tuple[bool, Optional[str]]:
    """
    Detect correlation cascade requiring exit.

    Logic:
    - Count positions underwater by > threshold
    - Check if current campaign correlates with underwater positions
    - If 3+ correlated positions failing, exit to limit systemic exposure

    Args:
        portfolio: Portfolio risk state
        campaign: Campaign to check
        current_prices: Dict mapping symbol -> current price
        cascade_threshold: Number of correlated failures (default: 3)
        underwater_threshold_pct: Profit threshold for "underwater" (default: -1.0%)
        correlation_threshold: Minimum correlation to count (default: 0.7)

    Returns:
        tuple: (should_exit, exit_reason)

    Example:
        >>> # EUR/USD -0.9%, GBP/USD -1.2%, AUD/USD -0.8% (3 correlated)
        >>> should_exit, reason = check_correlation_cascade(portfolio, campaign, prices)
        >>> should_exit
        True
        >>> reason
        'CORRELATION_CASCADE - 3 correlated positions failing'
    """
    if not campaign.patterns:
        return (False, None)

    # Get campaign symbol
    campaign_symbol = ""
    if hasattr(campaign.patterns[0], "bar"):
        campaign_symbol = campaign.patterns[0].bar.symbol
    elif hasattr(campaign.patterns[0], "symbol"):
        campaign_symbol = campaign.patterns[0].symbol

    if not campaign_symbol:
        return (False, None)

    # Get underwater campaigns
    underwater_campaigns = portfolio.get_underwater_campaigns(
        current_prices, underwater_threshold_pct
    )

    # Count correlated underwater campaigns
    correlated_count = 0
    correlated_symbols = []

    for underwater_camp in underwater_campaigns:
        if not underwater_camp.patterns:
            continue

        # Get underwater campaign symbol
        underwater_symbol = ""
        if hasattr(underwater_camp.patterns[0], "bar"):
            underwater_symbol = underwater_camp.patterns[0].bar.symbol
        elif hasattr(underwater_camp.patterns[0], "symbol"):
            underwater_symbol = underwater_camp.patterns[0].symbol

        if not underwater_symbol:
            continue

        # Calculate correlation
        correlation = get_currency_correlation(campaign_symbol, underwater_symbol)

        if correlation >= correlation_threshold:
            correlated_count += 1
            correlated_symbols.append(underwater_symbol)

    logger.debug(
        "correlation_cascade_check",
        campaign_id=campaign.campaign_id,
        campaign_symbol=campaign_symbol,
        underwater_campaigns=len(underwater_campaigns),
        correlated_count=correlated_count,
        cascade_threshold=cascade_threshold,
    )

    # Check if cascade threshold met
    if correlated_count >= cascade_threshold:
        exit_reason = f"CORRELATION_CASCADE - {correlated_count} correlated positions failing"

        logger.warning(
            "correlation_cascade_detected",
            campaign_id=campaign.campaign_id,
            campaign_symbol=campaign_symbol,
            correlated_count=correlated_count,
            correlated_symbols=correlated_symbols,
            cascade_threshold=cascade_threshold,
        )

        return (True, exit_reason)

    return (False, None)
