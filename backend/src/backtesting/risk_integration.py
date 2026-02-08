"""
Risk Manager Integration for Backtesting (Story 13.9)

Purpose:
--------
Integrates risk management into backtesting by providing:
1. BacktestRiskManager - Synchronous wrapper for position sizing and validation
2. Dynamic position sizing based on stop distance (FR9.2)
3. Campaign risk tracking and enforcement (FR9.3)
4. Portfolio heat tracking and enforcement (FR9.4)
5. Correlated risk validation for forex pairs (FR9.5)
6. Risk validation pipeline (FR9.6)
7. Risk limit violation tracking and reporting (FR9.7)

Risk Limits (FR18 - Non-Negotiable):
------------------------------------
- Max risk per trade: 2.0%
- Max campaign risk: 5.0%
- Max portfolio heat: 10.0%
- Max correlated risk: 6.0%

Wyckoff Risk Principle:
-----------------------
"Preserve capital first, make profits second." - Richard D. Wyckoff

Author: Story 13.9
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from typing import Literal, Optional
from uuid import uuid4

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Data Classes for Risk Tracking (FR9.7)
# =============================================================================


@dataclass
class RiskLimitViolations:
    """
    Track risk limit violations during backtest (FR9.7).

    Provides statistics on:
    - Total entry attempts
    - Entries allowed vs rejected
    - Rejection reasons breakdown
    - Rejection rate calculation
    """

    total_entry_attempts: int = 0
    entries_allowed: int = 0
    campaign_risk_rejections: int = 0
    portfolio_heat_rejections: int = 0
    correlated_risk_rejections: int = 0
    position_size_failures: int = 0

    @property
    def total_rejections(self) -> int:
        """Total number of rejected entries."""
        return (
            self.campaign_risk_rejections
            + self.portfolio_heat_rejections
            + self.correlated_risk_rejections
            + self.position_size_failures
        )

    @property
    def rejection_rate(self) -> float:
        """Percentage of entries rejected."""
        if self.total_entry_attempts == 0:
            return 0.0
        return self.total_rejections / self.total_entry_attempts * 100


@dataclass
class CampaignRiskProfile:
    """
    Campaign risk tracking (FR9.3).

    Tracks aggregate risk across all positions in a campaign
    and enforces 5% maximum campaign risk limit.
    """

    campaign_id: str
    symbol: str
    open_positions: list[str] = field(default_factory=list)  # Position IDs
    position_risks: dict[str, Decimal] = field(default_factory=dict)  # pos_id -> risk_pct
    max_allowed_risk_pct: Decimal = Decimal("5.0")

    @property
    def total_risk_pct(self) -> Decimal:
        """Total risk across all positions in campaign."""
        return sum(self.position_risks.values(), Decimal("0"))

    def can_add_position(self, new_position_risk_pct: Decimal) -> tuple[bool, Optional[str]]:
        """
        Check if new position would exceed campaign risk limit.

        Args:
            new_position_risk_pct: Risk percentage of proposed position

        Returns:
            tuple: (can_add: bool, rejection_reason: Optional[str])
        """
        new_total = self.total_risk_pct + new_position_risk_pct

        if new_total > self.max_allowed_risk_pct:
            return (
                False,
                f"Campaign risk would exceed {self.max_allowed_risk_pct}% "
                f"(current: {self.total_risk_pct}% + new: {new_position_risk_pct}% "
                f"= {new_total}%)",
            )

        return (True, None)

    def add_position(self, position_id: str, risk_pct: Decimal) -> None:
        """Add a position to the campaign."""
        self.open_positions.append(position_id)
        self.position_risks[position_id] = risk_pct

    def remove_position(self, position_id: str) -> None:
        """Remove a position from the campaign."""
        if position_id in self.open_positions:
            self.open_positions.remove(position_id)
        if position_id in self.position_risks:
            del self.position_risks[position_id]


@dataclass
class PositionMetadata:
    """
    Track position for risk management (FR9.6).

    Contains all metadata needed for risk calculations
    and portfolio tracking.
    """

    position_id: str
    campaign_id: str
    symbol: str
    entry_price: Decimal
    stop_loss: Decimal
    position_size: Decimal
    risk_amount: Decimal
    risk_pct: Decimal
    entry_timestamp: datetime
    side: Literal["LONG", "SHORT"] = "LONG"
    r_multiple: Decimal = Decimal("0")

    def calculate_current_pnl(self, current_price: Decimal) -> Decimal:
        """Calculate current unrealized P&L (direction-aware)."""
        if self.side == "SHORT":
            return (self.entry_price - current_price) * self.position_size
        return (current_price - self.entry_price) * self.position_size


# =============================================================================
# Correlated Risk Detection (FR9.5)
# =============================================================================


def get_shared_currency(symbol1: str, symbol2: str) -> Optional[str]:
    """
    Detect shared currency between two forex pairs (FR9.5).

    Args:
        symbol1: First symbol (e.g., "C:EURUSD")
        symbol2: Second symbol (e.g., "C:EURGBP")

    Returns:
        Shared currency code or None if no correlation

    Example:
        >>> get_shared_currency("C:EURUSD", "C:EURGBP")
        "EUR"
        >>> get_shared_currency("C:EURUSD", "C:AUDJPY")
        None
    """
    # Extract currency pairs (remove "C:" prefix if present)
    pair1 = symbol1.replace("C:", "").replace("X:", "")
    pair2 = symbol2.replace("C:", "").replace("X:", "")

    # Handle non-forex symbols
    if len(pair1) < 6 or len(pair2) < 6:
        return None

    # Extract base and quote currencies
    base1, quote1 = pair1[:3], pair1[3:6]
    base2, quote2 = pair2[:3], pair2[3:6]

    # Check for shared currency
    if base1 == base2:
        return base1
    if base1 == quote2:
        return base1
    if quote1 == base2:
        return quote1
    if quote1 == quote2:
        return quote1

    return None


# =============================================================================
# Backtest Risk Manager (FR9.1 - FR9.7)
# =============================================================================


class BacktestRiskManager:
    """
    Risk manager for backtesting (Story 13.9).

    Provides synchronous risk validation and position sizing for use
    in backtest strategy functions. Implements all FR9 requirements:

    - FR9.1: RiskManager initialization with limits
    - FR9.2: Dynamic position sizing based on stop distance
    - FR9.3: Campaign risk tracking (5% max)
    - FR9.4: Portfolio heat tracking (10% max)
    - FR9.5: Correlated risk validation (6% max)
    - FR9.6: Risk validation pipeline
    - FR9.7: Violation tracking and reporting

    Risk Limits:
    - max_risk_per_trade_pct: 2.0%
    - max_campaign_risk_pct: 5.0%
    - max_portfolio_heat_pct: 10.0%
    - max_correlated_risk_pct: 6.0%

    Example:
        >>> risk_mgr = BacktestRiskManager(initial_capital=Decimal("100000"))
        >>> can_trade, size, reason = risk_mgr.validate_and_size_position(
        ...     symbol="C:EURUSD",
        ...     entry_price=Decimal("1.0580"),
        ...     stop_loss=Decimal("1.0520"),
        ...     campaign_id="camp_123"
        ... )
    """

    def __init__(
        self,
        initial_capital: Decimal,
        max_risk_per_trade_pct: Decimal = Decimal("2.0"),
        max_campaign_risk_pct: Decimal = Decimal("5.0"),
        max_portfolio_heat_pct: Decimal = Decimal("10.0"),
        max_correlated_risk_pct: Decimal = Decimal("6.0"),
        min_position_size: Decimal = Decimal("1"),
        pattern_risk_map: Optional[dict[str, Decimal]] = None,
    ):
        """
        Initialize BacktestRiskManager (FR9.1).

        Args:
            initial_capital: Starting account balance
            max_risk_per_trade_pct: Maximum risk per trade (default 2.0%)
            max_campaign_risk_pct: Maximum campaign risk (default 5.0%)
            max_portfolio_heat_pct: Maximum portfolio heat (default 10.0%)
            max_correlated_risk_pct: Maximum correlated risk (default 6.0%)
            min_position_size: Minimum position size in tradeable units.
                Default 1 for stocks/indices (1 share).
                Use Decimal('1000') for forex (0.01 lot / mini-lot minimum).
                Use Decimal('0.01') for crypto (fractional units).
            pattern_risk_map: Optional mapping of pattern_type to risk percentage.
                E.g. {"SPRING": Decimal("0.5"), "SOS": Decimal("0.8")}.
                When a pattern is not in the map, falls back to max_risk_per_trade_pct.
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital

        # Risk limits (FR18)
        self.max_risk_per_trade_pct = max_risk_per_trade_pct
        self.max_campaign_risk_pct = max_campaign_risk_pct
        self.max_portfolio_heat_pct = max_portfolio_heat_pct
        self.max_correlated_risk_pct = max_correlated_risk_pct
        self.min_position_size = min_position_size
        self.pattern_risk_map = pattern_risk_map or {}

        # Tracking state
        self.open_positions: dict[str, PositionMetadata] = {}
        self.campaign_profiles: dict[str, CampaignRiskProfile] = {}
        self.violations = RiskLimitViolations()
        self.portfolio_heat_history: list[Decimal] = []

        logger.info(
            "[RISK] BacktestRiskManager initialized",
            initial_capital=float(initial_capital),
            max_risk_per_trade=float(max_risk_per_trade_pct),
            max_campaign_risk=float(max_campaign_risk_pct),
            max_portfolio_heat=float(max_portfolio_heat_pct),
            max_correlated_risk=float(max_correlated_risk_pct),
        )

    def update_capital(self, new_capital: Decimal) -> None:
        """Update current capital (after trade P&L)."""
        self.current_capital = new_capital

    def get_risk_pct_for_pattern(self, pattern_type: Optional[str] = None) -> Decimal:
        """Get risk percentage for a specific pattern type.

        Falls back to max_risk_per_trade_pct if pattern not in map.
        """
        if pattern_type and pattern_type in self.pattern_risk_map:
            return self.pattern_risk_map[pattern_type]
        return self.max_risk_per_trade_pct

    def get_portfolio_heat(self) -> Decimal:
        """
        Calculate current portfolio heat (FR9.4).

        Portfolio heat = sum of all open position risk percentages.

        Returns:
            Current portfolio heat as percentage
        """
        if not self.open_positions:
            return Decimal("0")

        return sum((pos.risk_pct for pos in self.open_positions.values()), Decimal("0"))

    def get_campaign_risk(self, campaign_id: str) -> Decimal:
        """
        Get current risk for a campaign (FR9.3).

        Args:
            campaign_id: Campaign identifier

        Returns:
            Current campaign risk as percentage
        """
        if campaign_id not in self.campaign_profiles:
            return Decimal("0")

        return self.campaign_profiles[campaign_id].total_risk_pct

    def get_correlated_risk(self, symbol: str) -> tuple[Decimal, list[str]]:
        """
        Calculate correlated risk for a symbol (FR9.5).

        For forex, detects positions with shared currencies.

        Args:
            symbol: Symbol to check correlation for

        Returns:
            tuple: (correlated_risk_pct, list of correlated symbols)
        """
        correlated_risk = Decimal("0")
        correlated_symbols = []

        for pos in self.open_positions.values():
            shared_currency = get_shared_currency(symbol, pos.symbol)
            if shared_currency:
                correlated_risk += pos.risk_pct
                correlated_symbols.append(pos.symbol)

        return correlated_risk, correlated_symbols

    def calculate_position_size(
        self,
        entry_price: Decimal,
        stop_loss: Decimal,
        account_balance: Optional[Decimal] = None,
        pattern_type: Optional[str] = None,
    ) -> tuple[Decimal, Decimal, Decimal]:
        """
        Calculate dynamic position size based on stop distance (FR9.2).

        Formula:
            risk_amount = account_balance * (max_risk_per_trade_pct / 100)
            stop_distance = abs(entry_price - stop_loss)
            position_size = risk_amount / stop_distance

        Args:
            entry_price: Proposed entry price
            stop_loss: Stop loss price
            account_balance: Optional account balance (uses current_capital if None)

        Returns:
            tuple: (position_size, risk_amount, risk_pct)

        Example:
            Entry: $1.0580, Stop: $1.0520, Account: $100,000
            Risk: $2,000 (2% of $100k)
            Stop Distance: $0.0060 (60 pips)
            Position Size: $2,000 / $0.0060 = 333,333 units
        """
        if account_balance is None:
            account_balance = self.current_capital

        # Calculate stop distance
        stop_distance = abs(entry_price - stop_loss)

        if stop_distance == Decimal("0"):
            logger.error(
                "[RISK] Stop distance is zero",
                entry=float(entry_price),
                stop=float(stop_loss),
            )
            return Decimal("0"), Decimal("0"), Decimal("0")

        # Calculate max risk amount using pattern-specific or default risk pct
        risk_pct = self.get_risk_pct_for_pattern(pattern_type)
        risk_amount = (account_balance * risk_pct / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )

        # Calculate position size
        # For forex: position_size in base currency units
        position_size = (risk_amount / stop_distance).quantize(Decimal("1"), rounding=ROUND_DOWN)

        # Calculate actual risk percentage
        actual_risk_pct = (risk_amount / account_balance * Decimal("100")).quantize(
            Decimal("0.0001"), rounding=ROUND_DOWN
        )

        logger.debug(
            "[RISK] Position size calculated",
            entry=float(entry_price),
            stop=float(stop_loss),
            stop_distance_pct=float(stop_distance / entry_price * 100),
            risk_amount=float(risk_amount),
            position_size=float(position_size),
            risk_pct=float(actual_risk_pct),
        )

        return position_size, risk_amount, actual_risk_pct

    def validate_campaign_risk(
        self,
        campaign_id: str,
        symbol: str,
        new_risk_pct: Decimal,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate campaign risk limit (FR9.3).

        Args:
            campaign_id: Campaign identifier
            symbol: Symbol for the campaign
            new_risk_pct: Risk percentage of proposed position

        Returns:
            tuple: (is_valid, rejection_reason)
        """
        # Get or create campaign profile
        if campaign_id not in self.campaign_profiles:
            self.campaign_profiles[campaign_id] = CampaignRiskProfile(
                campaign_id=campaign_id,
                symbol=symbol,
            )

        profile = self.campaign_profiles[campaign_id]
        can_add, reason = profile.can_add_position(new_risk_pct)

        if not can_add:
            logger.warning(
                "[RISK LIMIT] Campaign risk limit exceeded",
                campaign_id=campaign_id,
                current_risk=float(profile.total_risk_pct),
                new_risk=float(new_risk_pct),
                limit=float(self.max_campaign_risk_pct),
            )

        return can_add, reason

    def validate_portfolio_heat(
        self,
        new_risk_pct: Decimal,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate portfolio heat limit (FR9.4).

        Args:
            new_risk_pct: Risk percentage of proposed position

        Returns:
            tuple: (is_valid, rejection_reason)
        """
        current_heat = self.get_portfolio_heat()
        new_heat = current_heat + new_risk_pct

        if new_heat > self.max_portfolio_heat_pct:
            reason = (
                f"Portfolio heat would exceed {self.max_portfolio_heat_pct}% "
                f"(current: {current_heat}% + new: {new_risk_pct}% = {new_heat}%)"
            )
            logger.warning(
                "[RISK LIMIT] Portfolio heat limit exceeded",
                current_heat=float(current_heat),
                new_risk=float(new_risk_pct),
                projected_heat=float(new_heat),
                limit=float(self.max_portfolio_heat_pct),
            )
            return False, reason

        logger.debug(
            "[RISK] Portfolio heat check passed",
            current_heat=float(current_heat),
            new_risk=float(new_risk_pct),
            projected_heat=float(new_heat),
            utilization_pct=float(new_heat / self.max_portfolio_heat_pct * 100),
        )

        return True, None

    def validate_correlated_risk(
        self,
        symbol: str,
        new_risk_pct: Decimal,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate correlated risk limit (FR9.5).

        For forex pairs, checks that positions with shared currencies
        don't exceed 6% total risk.

        Args:
            symbol: Symbol to check
            new_risk_pct: Risk percentage of proposed position

        Returns:
            tuple: (is_valid, rejection_reason)
        """
        correlated_risk, correlated_symbols = self.get_correlated_risk(symbol)
        new_correlated_risk = correlated_risk + new_risk_pct

        if new_correlated_risk > self.max_correlated_risk_pct:
            reason = (
                f"Correlated risk would exceed {self.max_correlated_risk_pct}% "
                f"(current: {correlated_risk}% + new: {new_risk_pct}% = {new_correlated_risk}%) "
                f"- Correlated positions: {', '.join(correlated_symbols)}"
            )
            logger.warning(
                "[RISK LIMIT] Correlated risk limit exceeded",
                symbol=symbol,
                correlated_symbols=correlated_symbols,
                current_correlated=float(correlated_risk),
                new_risk=float(new_risk_pct),
                projected=float(new_correlated_risk),
                limit=float(self.max_correlated_risk_pct),
            )
            return False, reason

        return True, None

    def validate_and_size_position(
        self,
        symbol: str,
        entry_price: Decimal,
        stop_loss: Decimal,
        campaign_id: str,
        target_price: Optional[Decimal] = None,
        side: Literal["LONG", "SHORT"] = "LONG",
        pattern_type: Optional[str] = None,
    ) -> tuple[bool, Optional[Decimal], Optional[str]]:
        """
        Comprehensive risk validation pipeline for new position (FR9.6).

        Validates all risk limits in order:
        0. Directional validation (stop/entry relationship)
        1. Position size calculation (stop distance > 0)
        2. Campaign risk limit (< 5%)
        3. Portfolio heat limit (< 10%)
        4. Correlated risk limit (< 6%)
        5. Minimum position size check

        Args:
            symbol: Trading symbol
            entry_price: Proposed entry price
            stop_loss: Stop loss price (e.g., Creek/Spring low)
            campaign_id: Campaign identifier
            target_price: Optional target price for R-multiple
            side: Position side ("LONG" or "SHORT")

        Returns:
            tuple: (can_trade, position_size, rejection_reason)
        """
        self.violations.total_entry_attempts += 1

        # Step 0: Directional validation - stop must be on correct side of entry
        if side == "SHORT" and stop_loss <= entry_price:
            self.violations.position_size_failures += 1
            return (
                False,
                None,
                f"Invalid SHORT: stop_loss ({stop_loss}) must be above "
                f"entry_price ({entry_price})",
            )
        if side == "LONG" and stop_loss >= entry_price:
            self.violations.position_size_failures += 1
            return (
                False,
                None,
                f"Invalid LONG: stop_loss ({stop_loss}) must be below "
                f"entry_price ({entry_price})",
            )

        # Step 1: Calculate position size
        position_size, risk_amount, risk_pct = self.calculate_position_size(
            entry_price=entry_price,
            stop_loss=stop_loss,
            pattern_type=pattern_type,
        )

        if position_size <= Decimal("0"):
            self.violations.position_size_failures += 1
            return False, None, "Position size calculation failed (stop distance zero or invalid)"

        # Step 2: Campaign risk check
        campaign_ok, campaign_reason = self.validate_campaign_risk(
            campaign_id=campaign_id,
            symbol=symbol,
            new_risk_pct=risk_pct,
        )

        if not campaign_ok:
            self.violations.campaign_risk_rejections += 1
            return False, None, f"CAMPAIGN_RISK: {campaign_reason}"

        # Step 3: Portfolio heat check
        portfolio_ok, portfolio_reason = self.validate_portfolio_heat(
            new_risk_pct=risk_pct,
        )

        if not portfolio_ok:
            self.violations.portfolio_heat_rejections += 1
            return False, None, f"PORTFOLIO_HEAT: {portfolio_reason}"

        # Step 4: Correlated risk check
        correlated_ok, correlated_reason = self.validate_correlated_risk(
            symbol=symbol,
            new_risk_pct=risk_pct,
        )

        if not correlated_ok:
            self.violations.correlated_risk_rejections += 1
            return False, None, f"CORRELATED_RISK: {correlated_reason}"

        # Step 5: Minimum position size check (broker minimum)
        if position_size < self.min_position_size:
            self.violations.position_size_failures += 1
            return (
                False,
                None,
                f"Position size {position_size} below minimum {self.min_position_size} "
                f"for this asset class (adjust min_position_size if needed: "
                f"stocks=1, forex=1000, crypto=0.01)",
            )

        # All checks passed
        self.violations.entries_allowed += 1

        # Calculate R-multiple if target provided
        r_multiple = Decimal("0")
        if target_price and stop_loss != entry_price:
            stop_distance = abs(entry_price - stop_loss)
            target_distance = abs(target_price - entry_price)
            if stop_distance > 0:
                r_multiple = (target_distance / stop_distance).quantize(
                    Decimal("0.01"), rounding=ROUND_DOWN
                )

        logger.info(
            "[RISK] All risk validation checks passed",
            symbol=symbol,
            campaign_id=campaign_id,
            position_size=float(position_size),
            risk_pct=float(risk_pct),
            entry=float(entry_price),
            stop=float(stop_loss),
            r_multiple=float(r_multiple),
        )

        return True, position_size, None

    def register_position(
        self,
        symbol: str,
        campaign_id: str,
        entry_price: Decimal,
        stop_loss: Decimal,
        position_size: Decimal,
        timestamp: datetime,
        side: Literal["LONG", "SHORT"] = "LONG",
    ) -> str:
        """
        Register a new position after successful entry.

        Args:
            symbol: Trading symbol
            campaign_id: Campaign identifier
            entry_price: Entry price
            stop_loss: Stop loss price
            position_size: Position size
            timestamp: Entry timestamp
            side: Position side ("LONG" or "SHORT")

        Returns:
            Position ID
        """
        position_id = str(uuid4())[:8]

        # Calculate risk
        stop_distance = abs(entry_price - stop_loss)
        risk_amount = position_size * stop_distance
        risk_pct = (risk_amount / self.current_capital * Decimal("100")).quantize(
            Decimal("0.0001"), rounding=ROUND_DOWN
        )

        # Create position metadata
        position = PositionMetadata(
            position_id=position_id,
            campaign_id=campaign_id,
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss,
            position_size=position_size,
            risk_amount=risk_amount,
            risk_pct=risk_pct,
            entry_timestamp=timestamp,
            side=side,
        )

        # Register position
        self.open_positions[position_id] = position

        # Update campaign profile
        if campaign_id not in self.campaign_profiles:
            self.campaign_profiles[campaign_id] = CampaignRiskProfile(
                campaign_id=campaign_id,
                symbol=symbol,
            )
        self.campaign_profiles[campaign_id].add_position(position_id, risk_pct)

        # Track portfolio heat
        self.portfolio_heat_history.append(self.get_portfolio_heat())

        logger.info(
            "[RISK] Position registered",
            position_id=position_id,
            symbol=symbol,
            campaign_id=campaign_id,
            risk_pct=float(risk_pct),
            portfolio_heat=float(self.get_portfolio_heat()),
        )

        return position_id

    def close_position(self, position_id: str, exit_price: Decimal) -> Optional[Decimal]:
        """
        Close a position and calculate P&L.

        Args:
            position_id: Position identifier
            exit_price: Exit price

        Returns:
            Realized P&L or None if position not found
        """
        if position_id not in self.open_positions:
            # Fallback: try matching by campaign_id or symbol
            matches = [
                (pos_id, pos)
                for pos_id, pos in self.open_positions.items()
                if pos.campaign_id == position_id or pos.symbol == position_id
            ]
            if len(matches) == 0:
                return None
            if len(matches) > 1:
                logger.warning(
                    "[RISK] close_position fallback: multiple positions match, "
                    "closing first found. Consider using exact position_id.",
                    original_position_id=position_id,
                    match_count=len(matches),
                )
            matched_pos_id, _ = matches[0]
            logger.warning(
                "[RISK] close_position fallback: exact position_id not found, "
                "matched by campaign_id or symbol instead.",
                original_position_id=position_id,
                matched_position_id=matched_pos_id,
            )
            position_id = matched_pos_id

        position = self.open_positions.pop(position_id)

        # Calculate P&L (direction-aware)
        if position.side == "SHORT":
            pnl = (position.entry_price - exit_price) * position.position_size
        else:
            pnl = (exit_price - position.entry_price) * position.position_size

        # Update campaign profile
        if position.campaign_id in self.campaign_profiles:
            self.campaign_profiles[position.campaign_id].remove_position(position_id)

        # Update capital
        self.current_capital += pnl

        # Track portfolio heat
        self.portfolio_heat_history.append(self.get_portfolio_heat())

        logger.info(
            "[RISK] Position closed",
            position_id=position_id,
            pnl=float(pnl),
            portfolio_heat=float(self.get_portfolio_heat()),
        )

        return pnl

    def close_all_positions_for_symbol(self, symbol: str, exit_price: Decimal) -> Decimal:
        """
        Close all positions for a given symbol.

        Args:
            symbol: Symbol to close positions for
            exit_price: Exit price

        Returns:
            Total realized P&L
        """
        total_pnl = Decimal("0")

        positions_to_close = [
            pos_id for pos_id, pos in self.open_positions.items() if pos.symbol == symbol
        ]

        for pos_id in positions_to_close:
            pnl = self.close_position(pos_id, exit_price)
            if pnl is not None:
                total_pnl += pnl

        return total_pnl

    def get_risk_report(self) -> dict:
        """
        Generate risk management report (FR9.7).

        Returns comprehensive statistics on risk management performance.
        """
        violations = self.violations

        # Calculate portfolio utilization metrics
        avg_heat = Decimal("0")
        peak_heat = Decimal("0")
        if self.portfolio_heat_history:
            avg_heat = sum(self.portfolio_heat_history, Decimal("0")) / Decimal(
                len(self.portfolio_heat_history)
            )
            peak_heat = max(self.portfolio_heat_history)

        return {
            "entry_validation": {
                "total_attempts": violations.total_entry_attempts,
                "entries_allowed": violations.entries_allowed,
                "entries_rejected": violations.total_rejections,
                "rejection_rate_pct": violations.rejection_rate,
            },
            "rejection_reasons": {
                "campaign_risk_limit": violations.campaign_risk_rejections,
                "portfolio_heat_limit": violations.portfolio_heat_rejections,
                "correlated_risk_limit": violations.correlated_risk_rejections,
                "position_size_failures": violations.position_size_failures,
            },
            "portfolio_utilization": {
                "average_heat_pct": float(avg_heat),
                "peak_heat_pct": float(peak_heat),
                "heat_limit_pct": float(self.max_portfolio_heat_pct),
                "utilization_pct": float(peak_heat / self.max_portfolio_heat_pct * 100)
                if peak_heat > 0
                else 0,
            },
            "capital": {
                "initial": float(self.initial_capital),
                "current": float(self.current_capital),
                "return_pct": float(
                    (self.current_capital - self.initial_capital) / self.initial_capital * 100
                ),
            },
        }

    def print_risk_management_report(self) -> None:
        """Print formatted risk management report (FR9.7)."""
        report = self.get_risk_report()
        violations = self.violations

        print("\n" + "=" * 70)
        print("[RISK MANAGEMENT REPORT]")
        print("=" * 70)

        print("\n1. ENTRY RISK VALIDATION")
        print("-" * 70)
        ev = report["entry_validation"]
        print(f"  Total Entry Attempts:        {ev['total_attempts']}")
        if ev["total_attempts"] > 0:
            allowed_pct = ev["entries_allowed"] / ev["total_attempts"] * 100
            print(f"  Entries Allowed:             {ev['entries_allowed']} ({allowed_pct:.1f}%)")
            print(
                f"  Entries Rejected:            {ev['entries_rejected']} ({ev['rejection_rate_pct']:.1f}%)"
            )
        else:
            print("  Entries Allowed:             0")
            print("  Entries Rejected:            0")

        print("\n2. REJECTION REASONS")
        print("-" * 70)
        rr = report["rejection_reasons"]
        print(f"  Campaign Risk Limit (5%):    {rr['campaign_risk_limit']} rejections")
        print(f"  Portfolio Heat Limit (10%):  {rr['portfolio_heat_limit']} rejections")
        print(f"  Correlated Risk Limit (6%):  {rr['correlated_risk_limit']} rejections")
        print(f"  Position Size Failures:      {rr['position_size_failures']} rejections")

        print("\n3. PORTFOLIO UTILIZATION")
        print("-" * 70)
        pu = report["portfolio_utilization"]
        print(f"  Average Portfolio Heat:      {pu['average_heat_pct']:.1f}%")
        print(f"  Peak Portfolio Heat:         {pu['peak_heat_pct']:.1f}%")
        print(f"  Heat Limit:                  {pu['heat_limit_pct']:.1f}%")
        print(f"  Utilization:                 {pu['utilization_pct']:.1f}%")

        print("\n4. CAPITAL PERFORMANCE")
        print("-" * 70)
        cap = report["capital"]
        print(f"  Initial Capital:             ${cap['initial']:,.2f}")
        print(f"  Current Capital:             ${cap['current']:,.2f}")
        print(f"  Return:                      {cap['return_pct']:+.2f}%")

        print("\n5. WYCKOFF INSIGHT")
        print("-" * 70)
        if violations.total_entry_attempts > 0:
            print(f"  Risk management rejected {violations.rejection_rate:.1f}% of entries.")
            print("  This protects capital during high-risk conditions.")
            print(
                f"  Portfolio heat averaging {pu['average_heat_pct']:.1f}% shows position sizing in action."
            )
        else:
            print("  No entry attempts during backtest period.")

        print('\n  Wyckoff principle: "Preserve capital first, profits second" - validated')
        print("=" * 70 + "\n")
