"""
Risk Validator - Multi-Stage Validation Chain (Story 8.6)

Purpose:
--------
Validates position sizing and portfolio risk limits (heat, correlation, campaign risk).
Fourth stage in the validation chain (Volume → Phase → Levels → Risk → Strategy).

Validation Checks (FR18, FR19):
--------------------------------
1. Per-trade risk: Maximum 2.0% of account equity (FR18)
2. Portfolio heat: Maximum 10.0% total heat (FR18)
3. Campaign risk: Maximum 5.0% per campaign + 5 position limit (FR18)
4. Correlated risk: Maximum 6.0% per sector (FR18)
5. R-multiple: Pattern-specific minimums (Spring 3.0R, SOS 2.0R, LPS 2.5R, UTAD 3.0R) (FR19)
6. Position size: Minimum 1 share, maximum 20% account equity

Integration:
------------
- Story 8.2: Fourth stage in validation chain
- Story 8.5: Requires entry/stop/target from LevelValidator
- Epic 7: Uses RiskManager for position sizing calculations
- Story 7.6: R-multiple validation
- Story 7.3: Portfolio heat calculation

Author: Story 8.6
"""

from decimal import Decimal
from typing import Any

import structlog

from src.models.portfolio import PortfolioContext, Position
from src.models.risk import SectorMapping
from src.models.risk_allocation import PatternType
from src.models.validation import StageValidationResult, ValidationContext, ValidationStatus
from src.risk_management.position_calculator import calculate_position_size
from src.risk_management.risk_allocator import RiskAllocator
from src.signal_generator.validators.base import BaseValidator

logger = structlog.get_logger(__name__)


# FR19: R-multiple minimums by pattern type
R_MULTIPLE_MINIMUMS = {
    "SPRING": Decimal("3.0"),
    "SOS": Decimal("2.0"),
    "LPS": Decimal("2.5"),
    "UTAD": Decimal("3.0"),
    "ST": Decimal("2.5"),  # Secondary Test
}

# FR18: Risk limits
MAX_PER_TRADE_RISK = Decimal("2.0")  # 2% per trade
MAX_PORTFOLIO_HEAT = Decimal("10.0")  # 10% total heat
MAX_CAMPAIGN_RISK = Decimal("5.0")  # 5% per campaign
MAX_CORRELATED_RISK = Decimal("6.0")  # 6% per sector
MAX_POSITION_VALUE_PCT = Decimal("20.0")  # 20% of account equity
MAX_CAMPAIGN_POSITIONS = 5  # Maximum positions per campaign

# Warning thresholds (80% capacity)
PORTFOLIO_HEAT_WARNING = Decimal("8.0")  # 80% of 10%
CAMPAIGN_RISK_WARNING = Decimal("4.0")  # 80% of 5%
CORRELATED_RISK_WARNING = Decimal("4.8")  # 80% of 6%


class RiskValidator(BaseValidator):
    """
    Risk validation stage.

    Validates position sizing, portfolio heat, campaign risk, correlated risk,
    and R-multiple requirements against FR18 and FR19 constraints.

    Properties:
    -----------
    - validator_id: "RISK_VALIDATOR"
    - stage_name: "Risk"

    Example Usage:
    --------------
    >>> validator = RiskValidator()
    >>> result = await validator.validate(context)
    >>> print(result.status)  # PASS if all risk checks pass, FAIL if any violates limits
    """

    def __init__(self) -> None:
        """Initialize RiskValidator with RiskAllocator."""
        self.risk_allocator = RiskAllocator()

    @property
    def validator_id(self) -> str:
        """Unique identifier for this validator."""
        return "RISK_VALIDATOR"

    @property
    def stage_name(self) -> str:
        """Human-readable stage name."""
        return "Risk"

    def _validate_per_trade_risk(
        self, risk_pct: Decimal, risk_amount: Decimal, account_equity: Decimal
    ) -> tuple[bool, str | None, Decimal]:
        """
        Validate per-trade risk does not exceed 2.0% maximum (FR18).

        Parameters:
        -----------
        risk_pct : Decimal
            Risk percentage of account equity
        risk_amount : Decimal
            Dollar amount at risk
        account_equity : Decimal
            Total account equity

        Returns:
        --------
        tuple[bool, str | None, Decimal]
            (passes, rejection_reason, risk_pct)
        """
        if risk_pct > MAX_PER_TRADE_RISK:
            reason = (
                f"Per-trade risk {risk_pct:.2f}% exceeds {MAX_PER_TRADE_RISK:.1f}% maximum "
                f"(risk_amount: ${risk_amount:.2f}, account_equity: ${account_equity:.2f}) [FR18]"
            )
            logger.warning(
                "per_trade_risk_exceeded",
                risk_pct=float(risk_pct),
                risk_amount=float(risk_amount),
                limit=float(MAX_PER_TRADE_RISK),
            )
            return (False, reason, risk_pct)

        logger.debug(
            "per_trade_risk_check_passed",
            risk_pct=float(risk_pct),
            limit=float(MAX_PER_TRADE_RISK),
        )
        return (True, None, risk_pct)

    def _validate_portfolio_heat(
        self, current_heat: Decimal, new_position_risk: Decimal
    ) -> tuple[bool, str | None, Decimal]:
        """
        Validate portfolio heat does not exceed 10.0% maximum (FR18).

        Parameters:
        -----------
        current_heat : Decimal
            Current portfolio heat percentage
        new_position_risk : Decimal
            New position risk percentage

        Returns:
        --------
        tuple[bool, str | None, Decimal]
            (passes, rejection_reason_or_warning, total_heat)
        """
        total_heat = current_heat + new_position_risk

        if total_heat > MAX_PORTFOLIO_HEAT:
            reason = (
                f"Portfolio heat would reach {total_heat:.2f}% "
                f"(current: {current_heat:.2f}%, new: {new_position_risk:.2f}%), "
                f"exceeds {MAX_PORTFOLIO_HEAT:.1f}% maximum [FR18]"
            )
            logger.warning(
                "portfolio_heat_exceeded",
                current_heat=float(current_heat),
                new_position_risk=float(new_position_risk),
                total_heat=float(total_heat),
                limit=float(MAX_PORTFOLIO_HEAT),
            )
            return (False, reason, total_heat)

        # Warning at 80% capacity
        if total_heat >= PORTFOLIO_HEAT_WARNING:
            warning = f"WARNING: Portfolio heat {total_heat:.2f}% approaching {MAX_PORTFOLIO_HEAT:.1f}% limit"
            logger.warning(
                "risk_limit_approaching",
                limit_type="portfolio_heat",
                current=float(total_heat),
                limit=float(MAX_PORTFOLIO_HEAT),
                capacity_used_pct=float(total_heat / MAX_PORTFOLIO_HEAT * Decimal("100")),
            )
            return (True, warning, total_heat)

        logger.debug(
            "portfolio_heat_check_passed",
            current_heat=float(current_heat),
            new_position_risk=float(new_position_risk),
            total_heat=float(total_heat),
            limit=float(MAX_PORTFOLIO_HEAT),
        )
        return (True, None, total_heat)

    def _validate_campaign_risk(
        self,
        campaign_id: str | None,
        current_campaign_risk: Decimal,
        new_position_risk: Decimal,
        open_positions: list[Position],
    ) -> tuple[bool, str | None, Decimal]:
        """
        Validate campaign risk does not exceed 5.0% maximum and 5 position limit (FR18).

        Parameters:
        -----------
        campaign_id : str | None
            Campaign identifier
        current_campaign_risk : Decimal
            Current campaign risk percentage
        new_position_risk : Decimal
            New position risk percentage
        open_positions : list[Position]
            All open positions

        Returns:
        --------
        tuple[bool, str | None, Decimal]
            (passes, rejection_reason_or_warning, total_campaign_risk)
        """
        if campaign_id is None:
            logger.debug("campaign_risk_validation_skipped", reason="No campaign_id provided")
            return (True, None, Decimal("0.0"))

        # Count positions in this campaign
        campaign_positions = [p for p in open_positions if str(p.campaign_id) == str(campaign_id)]
        campaign_position_count = len(campaign_positions)

        # Check position limit (5 positions max per campaign)
        if campaign_position_count >= MAX_CAMPAIGN_POSITIONS:
            reason = f"Campaign position limit reached ({MAX_CAMPAIGN_POSITIONS} positions max for campaign {campaign_id})"
            logger.warning(
                "campaign_position_limit_reached",
                campaign_id=campaign_id,
                position_count=campaign_position_count,
                limit=MAX_CAMPAIGN_POSITIONS,
            )
            return (False, reason, current_campaign_risk)

        # Check campaign risk percentage
        total_campaign_risk = current_campaign_risk + new_position_risk

        if total_campaign_risk > MAX_CAMPAIGN_RISK:
            reason = (
                f"Campaign risk would reach {total_campaign_risk:.2f}% "
                f"(current: {current_campaign_risk:.2f}%, new: {new_position_risk:.2f}%), "
                f"exceeds {MAX_CAMPAIGN_RISK:.1f}% maximum for campaign {campaign_id} [FR18]"
            )
            logger.warning(
                "campaign_risk_exceeded",
                campaign_id=campaign_id,
                current_risk=float(current_campaign_risk),
                new_position_risk=float(new_position_risk),
                total_risk=float(total_campaign_risk),
                limit=float(MAX_CAMPAIGN_RISK),
            )
            return (False, reason, total_campaign_risk)

        # Warning at 80% capacity
        if total_campaign_risk >= CAMPAIGN_RISK_WARNING:
            warning = f"WARNING: Campaign risk {total_campaign_risk:.2f}% approaching {MAX_CAMPAIGN_RISK:.1f}% limit"
            logger.warning(
                "risk_limit_approaching",
                limit_type="campaign_risk",
                campaign_id=campaign_id,
                current=float(total_campaign_risk),
                limit=float(MAX_CAMPAIGN_RISK),
                capacity_used_pct=float(total_campaign_risk / MAX_CAMPAIGN_RISK * Decimal("100")),
            )
            return (True, warning, total_campaign_risk)

        logger.debug(
            "campaign_risk_check_passed",
            campaign_id=campaign_id,
            current_risk=float(current_campaign_risk),
            new_position_risk=float(new_position_risk),
            total_risk=float(total_campaign_risk),
            position_count=campaign_position_count,
            limit=float(MAX_CAMPAIGN_RISK),
        )
        return (True, None, total_campaign_risk)

    def _validate_correlated_risk(
        self,
        symbol: str,
        sector: str,
        current_correlated_risk: Decimal,
        new_position_risk: Decimal,
    ) -> tuple[bool, str | None, Decimal]:
        """
        Validate correlated risk does not exceed 6.0% maximum (FR18).

        Parameters:
        -----------
        symbol : str
            Trading symbol
        sector : str
            Sector classification
        current_correlated_risk : Decimal
            Current sector risk percentage
        new_position_risk : Decimal
            New position risk percentage

        Returns:
        --------
        tuple[bool, str | None, Decimal]
            (passes, rejection_reason_or_warning, total_correlated_risk)
        """
        total_correlated_risk = current_correlated_risk + new_position_risk

        if total_correlated_risk > MAX_CORRELATED_RISK:
            reason = (
                f"Correlated risk in {sector} sector would reach {total_correlated_risk:.2f}%, "
                f"exceeds {MAX_CORRELATED_RISK:.1f}% maximum [FR18]"
            )
            logger.warning(
                "correlated_risk_exceeded",
                symbol=symbol,
                sector=sector,
                current_risk=float(current_correlated_risk),
                new_position_risk=float(new_position_risk),
                total_risk=float(total_correlated_risk),
                limit=float(MAX_CORRELATED_RISK),
            )
            return (False, reason, total_correlated_risk)

        # Warning at 80% capacity
        if total_correlated_risk >= CORRELATED_RISK_WARNING:
            warning = (
                f"WARNING: Correlated risk in {sector} sector {total_correlated_risk:.2f}% "
                f"approaching {MAX_CORRELATED_RISK:.1f}% limit"
            )
            logger.warning(
                "risk_limit_approaching",
                limit_type="correlated_risk",
                sector=sector,
                current=float(total_correlated_risk),
                limit=float(MAX_CORRELATED_RISK),
                capacity_used_pct=float(
                    total_correlated_risk / MAX_CORRELATED_RISK * Decimal("100")
                ),
            )
            return (True, warning, total_correlated_risk)

        logger.debug(
            "correlated_risk_check_passed",
            sector=sector,
            current_risk=float(current_correlated_risk),
            new_position_risk=float(new_position_risk),
            total_risk=float(total_correlated_risk),
            limit=float(MAX_CORRELATED_RISK),
        )
        return (True, None, total_correlated_risk)

    def _validate_r_multiple(
        self, pattern_type: str, entry: Decimal, stop: Decimal, target: Decimal
    ) -> tuple[bool, str | None, Decimal]:
        """
        Validate R-multiple meets pattern-specific minimum requirements (FR19).

        Parameters:
        -----------
        pattern_type : str
            Pattern type (SPRING, SOS, LPS, UTAD)
        entry : Decimal
            Entry price
        stop : Decimal
            Stop loss price
        target : Decimal
            Target price

        Returns:
        --------
        tuple[bool, str | None, Decimal]
            (passes, rejection_reason, r_multiple)
        """
        # Calculate R-multiple: (target - entry) / (entry - stop)
        stop_distance = abs(entry - stop)
        if stop_distance == Decimal("0"):
            reason = "Invalid stop loss (stop distance is zero)"
            logger.error("r_multiple_validation_failed", reason=reason)
            return (False, reason, Decimal("0.0"))

        r_multiple = (target - entry) / stop_distance

        # Get minimum R for pattern type
        minimum_r = R_MULTIPLE_MINIMUMS.get(pattern_type.upper(), Decimal("2.0"))

        if r_multiple < minimum_r:
            reason = (
                f"{pattern_type} R-multiple {r_multiple:.2f} below {minimum_r:.2f} "
                f"minimum requirement [FR19]"
            )
            logger.warning(
                "r_multiple_below_minimum",
                pattern_type=pattern_type,
                r_multiple=float(r_multiple),
                minimum_required=float(minimum_r),
            )
            return (False, reason, r_multiple)

        logger.debug(
            "r_multiple_check_passed",
            pattern_type=pattern_type,
            r_multiple=float(r_multiple),
            minimum_required=float(minimum_r),
        )
        return (True, None, r_multiple)

    def _validate_position_size(
        self, position_size: int, position_value: Decimal, account_equity: Decimal
    ) -> tuple[bool, str | None]:
        """
        Validate position size meets minimum 1 share and maximum 20% equity constraints.

        Parameters:
        -----------
        position_size : int
            Number of shares
        position_value : Decimal
            Total position value (shares × entry price)
        account_equity : Decimal
            Total account equity

        Returns:
        --------
        tuple[bool, str | None]
            (passes, rejection_reason)
        """
        if position_size < 1:
            reason = "Position size calculation resulted in <1 share (insufficient equity or risk too low)"
            logger.warning("position_size_below_minimum", position_size=position_size)
            return (False, reason)

        max_position_value = account_equity * (MAX_POSITION_VALUE_PCT / Decimal("100"))
        if position_value > max_position_value:
            reason = (
                f"Position value ${position_value:.2f} exceeds {MAX_POSITION_VALUE_PCT:.0f}% "
                f"of account equity (max: ${max_position_value:.2f})"
            )
            logger.warning(
                "position_value_exceeds_maximum",
                position_value=float(position_value),
                max_position_value=float(max_position_value),
                account_equity=float(account_equity),
            )
            return (False, reason)

        logger.debug(
            "position_size_check_passed",
            position_size=position_size,
            position_value=float(position_value),
            max_position_value=float(max_position_value),
        )
        return (True, None)

    def _calculate_current_heat(self, open_positions: list[Position]) -> Decimal:
        """
        Calculate current portfolio heat from open positions.

        Parameters:
        -----------
        open_positions : list[Position]
            All open positions

        Returns:
        --------
        Decimal
            Current portfolio heat percentage
        """
        total_heat = sum(p.position_risk_pct for p in open_positions)
        return total_heat

    def _calculate_campaign_risk(
        self, campaign_id: str | None, open_positions: list[Position]
    ) -> Decimal:
        """
        Calculate current campaign risk from open positions.

        Parameters:
        -----------
        campaign_id : str | None
            Campaign identifier
        open_positions : list[Position]
            All open positions

        Returns:
        --------
        Decimal
            Current campaign risk percentage
        """
        if campaign_id is None:
            return Decimal("0.0")

        campaign_positions = [p for p in open_positions if str(p.campaign_id) == str(campaign_id)]
        total_risk = sum(p.position_risk_pct for p in campaign_positions)
        return total_risk

    def _calculate_correlated_risk(self, sector: str, open_positions: list[Position]) -> Decimal:
        """
        Calculate current correlated risk from open positions in same sector.

        Parameters:
        -----------
        sector : str
            Sector classification
        open_positions : list[Position]
            All open positions

        Returns:
        --------
        Decimal
            Current sector risk percentage
        """
        sector_positions = [p for p in open_positions if p.sector == sector]
        total_risk = sum(p.position_risk_pct for p in sector_positions)
        return total_risk

    async def validate(self, context: ValidationContext) -> StageValidationResult:
        """
        Execute risk validation logic.

        Validates:
        1. Portfolio context presence
        2. Entry/stop/target presence (from LevelValidator)
        3. Position size calculation
        4. Position size constraints (≥1 share, ≤20% equity)
        5. R-multiple minimum (FR19)
        6. Per-trade risk (≤2.0%, FR18)
        7. Portfolio heat (≤10.0%, FR18)
        8. Campaign risk (≤5.0%, ≤5 positions, FR18)
        9. Correlated risk (≤6.0%, FR18)

        Parameters:
        -----------
        context : ValidationContext
            Context with pattern and portfolio_context

        Returns:
        --------
        StageValidationResult
            FAIL if any limit violated, PASS if all valid, with comprehensive metadata
        """
        logger.info(
            "risk_validation_started",
            pattern_id=str(context.pattern.id) if hasattr(context.pattern, "id") else "unknown",
            pattern_type=context.pattern.pattern_type
            if hasattr(context.pattern, "pattern_type")
            else "unknown",
            symbol=context.symbol,
        )

        # Step 1: Validate portfolio_context presence
        if context.portfolio_context is None:
            return self.create_result(
                ValidationStatus.FAIL,
                reason="Portfolio context not available for risk validation",
            )

        portfolio_context: PortfolioContext = context.portfolio_context

        # Step 2: Extract entry, stop, target from context (set by LevelValidator)
        entry_price = getattr(context, "entry_price", None)
        stop_loss = getattr(context, "stop_loss", None)
        target_price = getattr(context, "target_price", None)

        if entry_price is None or stop_loss is None or target_price is None:
            return self.create_result(
                ValidationStatus.FAIL,
                reason="Entry/stop/target levels not available (LevelValidator must run first)",
            )

        # Edge case validations
        if entry_price <= stop_loss:
            return self.create_result(
                ValidationStatus.FAIL,
                reason=f"Invalid stop loss (stop ${stop_loss} >= entry ${entry_price})",
            )

        if target_price <= entry_price:
            return self.create_result(
                ValidationStatus.FAIL,
                reason=f"Invalid target (target ${target_price} <= entry ${entry_price})",
            )

        if portfolio_context.account_equity <= Decimal("0"):
            return self.create_result(
                ValidationStatus.FAIL,
                reason=f"Invalid account equity (${portfolio_context.account_equity})",
            )

        # Step 3: Calculate position size using RiskManager position_calculator
        pattern_type_str = (
            context.pattern.pattern_type if hasattr(context.pattern, "pattern_type") else "SPRING"
        )
        try:
            pattern_type_enum = PatternType[pattern_type_str.upper()]
        except KeyError:
            pattern_type_enum = PatternType.SPRING  # Default fallback

        position_sizing = calculate_position_size(
            account_equity=portfolio_context.account_equity,
            pattern_type=pattern_type_enum,
            entry=entry_price,
            stop=stop_loss,
            target=target_price,
            risk_allocator=self.risk_allocator,
        )

        if position_sizing is None:
            return self.create_result(
                ValidationStatus.FAIL,
                reason="Position sizing calculation failed",
            )

        # Step 4: Validate position size
        position_value = Decimal(position_sizing.shares) * entry_price
        passes, reason = self._validate_position_size(
            position_sizing.shares, position_value, portfolio_context.account_equity
        )
        if not passes:
            return self.create_result(ValidationStatus.FAIL, reason=reason)

        # Step 5: Validate R-multiple (FR19)
        passes, reason, r_multiple = self._validate_r_multiple(
            pattern_type_str, entry_price, stop_loss, target_price
        )
        if not passes:
            return self.create_result(ValidationStatus.FAIL, reason=reason)

        # Step 6: Validate per-trade risk (FR18)
        risk_pct = position_sizing.risk_pct
        passes, reason, _ = self._validate_per_trade_risk(
            risk_pct, position_sizing.risk_amount, portfolio_context.account_equity
        )
        if not passes:
            return self.create_result(ValidationStatus.FAIL, reason=reason)

        # Step 7: Validate portfolio heat (FR18)
        current_heat = self._calculate_current_heat(portfolio_context.open_positions)
        passes, reason_or_warning, total_heat = self._validate_portfolio_heat(
            current_heat, risk_pct
        )
        if not passes:
            return self.create_result(ValidationStatus.FAIL, reason=reason_or_warning)

        # Collect warnings
        warnings = []
        if reason_or_warning and passes:
            warnings.append(reason_or_warning)

        # Step 8: Validate campaign risk (FR18)
        campaign_id = getattr(context, "campaign_id", None)
        current_campaign_risk = self._calculate_campaign_risk(
            campaign_id, portfolio_context.open_positions
        )
        passes, reason_or_warning, total_campaign_risk = self._validate_campaign_risk(
            campaign_id, current_campaign_risk, risk_pct, portfolio_context.open_positions
        )
        if not passes:
            return self.create_result(ValidationStatus.FAIL, reason=reason_or_warning)

        if reason_or_warning and passes:
            warnings.append(reason_or_warning)

        # Step 9: Validate correlated risk (FR18)
        # Get sector from symbol mapping
        sector_mapping: SectorMapping | None = portfolio_context.sector_mappings.get(context.symbol)
        if sector_mapping:
            sector = sector_mapping.sector
            current_correlated_risk = self._calculate_correlated_risk(
                sector, portfolio_context.open_positions
            )
            passes, reason_or_warning, total_correlated_risk = self._validate_correlated_risk(
                context.symbol, sector, current_correlated_risk, risk_pct
            )
            if not passes:
                return self.create_result(ValidationStatus.FAIL, reason=reason_or_warning)

            if reason_or_warning and passes:
                warnings.append(reason_or_warning)
        else:
            # Sector mapping not available - skip correlated risk validation
            total_correlated_risk = Decimal("0.0")
            logger.warning(
                "correlated_risk_validation_skipped",
                symbol=context.symbol,
                reason="Symbol not found in sector_mappings",
            )

        # All validations passed - construct metadata
        metadata: dict[str, Any] = {
            "position_size": position_sizing.shares,
            "risk_amount": float(position_sizing.risk_amount),
            "risk_pct": float(risk_pct),
            "r_multiple": float(r_multiple),
            "portfolio_heat_before": float(current_heat),
            "portfolio_heat_after": float(total_heat),
            "portfolio_heat_limit": float(MAX_PORTFOLIO_HEAT),
            "campaign_risk_before": float(current_campaign_risk),
            "campaign_risk_after": float(total_campaign_risk),
            "campaign_risk_limit": float(MAX_CAMPAIGN_RISK),
            "correlated_risk_before": float(current_correlated_risk) if sector_mapping else 0.0,
            "correlated_risk_after": float(total_correlated_risk) if sector_mapping else 0.0,
            "correlated_risk_limit": float(MAX_CORRELATED_RISK),
            "per_trade_risk_limit": float(MAX_PER_TRADE_RISK),
            "r_multiple_minimum": float(
                R_MULTIPLE_MINIMUMS.get(pattern_type_str.upper(), Decimal("2.0"))
            ),
            "account_equity": float(portfolio_context.account_equity),
            "position_value": float(position_value),
            "entry_price": float(entry_price),
            "stop_loss": float(stop_loss),
            "target_price": float(target_price),
        }

        logger.info(
            "risk_validation_passed",
            pattern_type=pattern_type_str,
            position_size=position_sizing.shares,
            risk_pct=float(risk_pct),
            r_multiple=float(r_multiple),
            portfolio_heat=float(total_heat),
            warnings_count=len(warnings),
        )

        # Return WARN if warnings exist, otherwise PASS
        if warnings:
            return self.create_result(
                ValidationStatus.WARN,
                reason="; ".join(warnings),
                metadata=metadata,
            )

        return self.create_result(ValidationStatus.PASS, metadata=metadata)
