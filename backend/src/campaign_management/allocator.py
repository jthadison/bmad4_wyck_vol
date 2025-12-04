"""
Campaign Allocator - BMAD Position Allocation Logic (Story 9.2)

Purpose:
--------
Implements BMAD 40/30/30 allocation methodology for campaign position building:
- Spring: 40% of campaign budget (2.0% of 5% max)
- SOS: 30% of campaign budget (1.5% of 5% max)
- LPS: 30% of campaign budget (1.5% of 5% max)

Includes rebalancing logic when earlier entries are skipped and validation
to enforce 5% campaign maximum risk limit (FR18).

Key Features:
-------------
1. BMAD allocation percentages (FR23)
2. Rebalancing when entries skipped (AC: 5, 9)
3. Campaign budget validation (AC: 7)
4. 75% confidence requirement for 100% LPS allocation (AC: 11, 12)
5. Structured logging for audit trail (AC: 10)

Integration:
------------
- Story 9.1: Uses Campaign and CampaignPosition models
- Story 8.8: Uses TradeSignal model
- Epic 7: Uses RiskManager for actual position sizing (FR16)
- Story 8.10: Called by MasterOrchestrator via CampaignService

Author: Story 9.2
"""

from decimal import Decimal
from typing import Optional

import structlog

from src.config import (
    BMAD_LPS_ALLOCATION,
    BMAD_SOS_ALLOCATION,
    BMAD_SPRING_ALLOCATION,
    CAMPAIGN_MAX_RISK_PCT,
    LPS_SOLE_ENTRY_MIN_CONFIDENCE,
)
from src.models.allocation import AllocationPlan
from src.models.campaign_lifecycle import Campaign
from src.models.signal import TradeSignal

logger = structlog.get_logger(__name__)


class InvalidPatternTypeError(Exception):
    """Raised when pattern_type is not SPRING, SOS, or LPS."""

    pass


class CampaignAllocator:
    """
    BMAD allocation engine for campaign position building (AC: 6).

    Calculates allocation plans for signals according to BMAD 40/30/30
    methodology, with rebalancing when earlier entries are skipped.

    Attributes
    ----------
    portfolio_value : Decimal
        Current portfolio equity for calculating actual risk percentages
    """

    def __init__(self, portfolio_value: Decimal):
        """
        Initialize allocator with portfolio value.

        Parameters
        ----------
        portfolio_value : Decimal
            Current portfolio equity (used to calculate actual_risk_pct)
        """
        self.portfolio_value = portfolio_value
        self.logger = logger.bind(component="CampaignAllocator")

    def allocate_campaign_risk(self, campaign: Campaign, new_signal: TradeSignal) -> AllocationPlan:
        """
        Allocate campaign risk for new signal using BMAD methodology (AC: 6).

        Implements 40/30/30 allocation with rebalancing when earlier entries
        are skipped. Validates against 5% campaign maximum and applies 75%
        confidence threshold for 100% LPS allocation.

        Parameters
        ----------
        campaign : Campaign
            Current campaign state (contains existing positions)
        new_signal : TradeSignal
            New signal to allocate budget for

        Returns
        -------
        AllocationPlan
            Allocation plan with approval/rejection decision

        Raises
        ------
        InvalidPatternTypeError
            If pattern_type not in [SPRING, SOS, LPS]

        Examples
        --------
        >>> allocator = CampaignAllocator(portfolio_value=Decimal("100000"))
        >>> campaign = Campaign(...)  # Empty campaign
        >>> spring_signal = TradeSignal(pattern_type="SPRING", ...)
        >>> plan = allocator.allocate_campaign_risk(campaign, spring_signal)
        >>> assert plan.bmad_allocation_pct == Decimal("0.40")  # 40%
        >>> assert plan.target_risk_pct == Decimal("2.0")  # 40% of 5%
        """
        pattern_type = new_signal.pattern_type
        signal_id = new_signal.id
        campaign_id = campaign.id

        # Step 1: Get BMAD allocation for pattern type
        if pattern_type == "SPRING":
            bmad_pct = BMAD_SPRING_ALLOCATION  # 40%
        elif pattern_type == "SOS":
            bmad_pct = BMAD_SOS_ALLOCATION  # 30%
        elif pattern_type == "LPS":
            bmad_pct = BMAD_LPS_ALLOCATION  # 30%
        else:
            raise InvalidPatternTypeError(
                f"Invalid pattern_type '{pattern_type}' - must be SPRING, SOS, or LPS"
            )

        # Step 2: Check for rebalancing opportunity (AC: 5)
        is_rebalanced, rebalance_reason, bmad_pct = self._check_rebalancing_needed(
            campaign, pattern_type, bmad_pct, new_signal.confidence_score
        )

        # If rebalancing returned rejection (100% LPS with low confidence)
        if rebalance_reason and rebalance_reason.startswith("REJECTED:"):
            return AllocationPlan(
                campaign_id=campaign_id,
                signal_id=signal_id,
                pattern_type=pattern_type,
                bmad_allocation_pct=bmad_pct,
                target_risk_pct=CAMPAIGN_MAX_RISK_PCT * bmad_pct,
                actual_risk_pct=Decimal("0"),
                position_size_shares=Decimal("0"),
                allocation_used=Decimal("0"),
                remaining_budget=Decimal("0"),
                is_rebalanced=True,
                rebalance_reason=rebalance_reason[9:],  # Strip "REJECTED:" prefix
                approved=False,
                rejection_reason=rebalance_reason[9:],
            )

        # Step 3: Calculate target risk percentage (AC: 2, 4)
        target_risk_pct = CAMPAIGN_MAX_RISK_PCT * bmad_pct
        # Example: Spring 40% of 5% = 0.40 × 5.0% = 2.0%

        # Step 4: Get actual risk from signal (FR16)
        # RiskManager has already calculated risk_amount based on pattern-specific
        # risk percentages (Spring 0.5%, SOS 1.0%, LPS 0.6%)
        actual_risk_pct = (new_signal.risk_amount / self.portfolio_value) * Decimal("100")
        # Round to 2 decimal places
        actual_risk_pct = actual_risk_pct.quantize(Decimal("0.01"))

        # Step 5: Calculate allocation used
        # Note: Actual risk (FR16) may differ from BMAD target allocation
        # BMAD allocates campaign budget, FR16 determines actual position size
        allocation_used = actual_risk_pct

        # Step 6: Check campaign budget remaining (AC: 1, 7)
        current_allocation = campaign.total_allocation
        remaining_budget = CAMPAIGN_MAX_RISK_PCT - current_allocation

        if allocation_used > remaining_budget:
            # Allocation would exceed 5% campaign maximum - REJECT
            rejection_reason = (
                f"Allocation {allocation_used}% exceeds remaining budget "
                f"{remaining_budget}% (campaign max: {CAMPAIGN_MAX_RISK_PCT}%)"
            )
            self.logger.warning(
                "campaign_allocation_rejected",
                campaign_id=str(campaign_id),
                pattern_type=pattern_type,
                rejection_reason=rejection_reason,
                current_allocation=float(current_allocation),
                requested_allocation=float(allocation_used),
            )

            return AllocationPlan(
                campaign_id=campaign_id,
                signal_id=signal_id,
                pattern_type=pattern_type,
                bmad_allocation_pct=bmad_pct,
                target_risk_pct=target_risk_pct,
                actual_risk_pct=actual_risk_pct,
                position_size_shares=new_signal.position_size,
                allocation_used=allocation_used,
                remaining_budget=remaining_budget,
                is_rebalanced=is_rebalanced,
                rebalance_reason=rebalance_reason,
                approved=False,
                rejection_reason=rejection_reason,
            )

        # Step 7: Approve allocation
        remaining_budget_after = CAMPAIGN_MAX_RISK_PCT - (current_allocation + allocation_used)

        # Step 8: Create AllocationPlan object
        allocation_plan = AllocationPlan(
            campaign_id=campaign_id,
            signal_id=signal_id,
            pattern_type=pattern_type,
            bmad_allocation_pct=bmad_pct,
            target_risk_pct=target_risk_pct,
            actual_risk_pct=actual_risk_pct,
            position_size_shares=new_signal.position_size,
            allocation_used=allocation_used,
            remaining_budget=remaining_budget_after,
            is_rebalanced=is_rebalanced,
            rebalance_reason=rebalance_reason,
            approved=True,
            rejection_reason=None,
        )

        # Log allocation decision (AC: 10)
        self.logger.info(
            "campaign_allocation_approved",
            campaign_id=str(campaign_id),
            pattern_type=pattern_type,
            bmad_allocation=float(bmad_pct),
            target_risk_pct=float(target_risk_pct),
            actual_risk_pct=float(actual_risk_pct),
            remaining_budget=float(remaining_budget_after),
            is_rebalanced=is_rebalanced,
            rebalance_reason=rebalance_reason,
        )

        # Log budget warning if low
        if remaining_budget_after < Decimal("1.0"):
            self.logger.warning(
                "campaign_budget_low",
                campaign_id=str(campaign_id),
                remaining_budget=float(remaining_budget_after),
            )

        return allocation_plan

    def _check_rebalancing_needed(
        self,
        campaign: Campaign,
        new_pattern_type: str,
        original_bmad_pct: Decimal,
        signal_confidence: int,
    ) -> tuple[bool, Optional[str], Decimal]:
        """
        Check if allocation should be rebalanced due to skipped entries (AC: 5).

        Rebalancing Scenarios:
        ----------------------
        1. Spring skipped, SOS entry: SOS gets 70% (40% + 30%)
        2. Spring skipped, LPS entry (SOS taken): LPS gets 60% (40% + 30% - 30%)
        3. Spring + SOS skipped, LPS entry: LPS gets 100% (requires 75% confidence)
        4. SOS skipped, LPS entry (Spring taken): LPS gets 60% (30% + 30%)

        Parameters
        ----------
        campaign : Campaign
            Current campaign state
        new_pattern_type : str
            Pattern type being allocated (SPRING, SOS, LPS)
        original_bmad_pct : Decimal
            Original BMAD allocation percentage
        signal_confidence : int
            Confidence score of the new signal

        Returns
        -------
        tuple[bool, Optional[str], Decimal]
            (is_rebalanced, rebalance_reason, adjusted_bmad_pct)
            If rejected, reason starts with "REJECTED:"
        """
        has_spring = any(p.pattern_type == "SPRING" for p in campaign.positions)
        has_sos = any(p.pattern_type == "SOS" for p in campaign.positions)

        # Scenario 1: Spring skipped, SOS entry
        if not has_spring and new_pattern_type == "SOS":
            self.logger.info(
                "campaign_rebalanced",
                campaign_id=str(campaign.id),
                pattern_type=new_pattern_type,
                original_allocation=float(original_bmad_pct),
                adjusted_allocation=0.70,
                rebalance_reason="Spring entry not taken, reallocating 40% to SOS",
            )
            return (
                True,
                "Spring entry not taken, reallocating 40% to SOS",
                Decimal("0.70"),
            )

        # Scenario 2-4: LPS entry with various skipped patterns
        if new_pattern_type == "LPS":
            # Scenario 3: Spring + SOS skipped, LPS sole entry (100% allocation)
            if not has_spring and not has_sos:
                # CRITICAL: 100% LPS allocation requires 75% minimum confidence (AC: 11, 12)
                if signal_confidence < LPS_SOLE_ENTRY_MIN_CONFIDENCE:
                    rejection_reason = (
                        f"100% LPS allocation requires {LPS_SOLE_ENTRY_MIN_CONFIDENCE}% minimum "
                        f"confidence (signal has {signal_confidence}%)"
                    )
                    self.logger.warning(
                        "lps_sole_entry_rejected_low_confidence",
                        campaign_id=str(campaign.id),
                        signal_confidence=signal_confidence,
                        required_confidence=float(LPS_SOLE_ENTRY_MIN_CONFIDENCE),
                        rejection_reason=rejection_reason,
                    )
                    return (True, f"REJECTED:{rejection_reason}", Decimal("1.00"))

                self.logger.info(
                    "campaign_rebalanced",
                    campaign_id=str(campaign.id),
                    pattern_type=new_pattern_type,
                    original_allocation=float(original_bmad_pct),
                    adjusted_allocation=1.00,
                    rebalance_reason=(
                        "Spring and SOS entries not taken, LPS sole entry with "
                        "elevated confidence threshold (75%)"
                    ),
                )
                return (
                    True,
                    "Spring and SOS entries not taken, LPS sole entry with elevated confidence threshold (75%)",
                    Decimal("1.00"),
                )

            # Scenario 2: Spring skipped, LPS entry (SOS taken)
            # Actually: Spring skipped → LPS gets Spring's 40% + its 30% = 70%
            # But SOS already took 30%, so actual rebalancing logic:
            # If Spring skipped and SOS taken, LPS should get remaining budget
            # But more precisely: Spring allocation (40%) goes to LPS, so 40% + 30% = 70%
            # However, SOS took 30% already, so LPS gets 40% (Spring's share) + 30% (its own)
            # But that's still 70% of REMAINING budget after SOS
            # The story says: "LPS gets 60% (40% + 30% - 30% SOS already took)"
            # This is confusing - let me re-read the story spec...
            #
            # From story line 291-293:
            # "LPS gets Spring's 40% + its own 30% = 70% BUT SOS already used 30%,
            # so LPS gets 40% + 30% - 30% = 40%"
            # Actually that math doesn't work. Let me check line 520:
            # "Rebalanced: LPS gets Spring's 40% + LPS's 30% = 70% BUT SOS already
            # consumed 30%"
            #
            # I think the intent is:
            # - Total budget: 100% (5% campaign max)
            # - Spring (40%) not taken
            # - SOS (30%) already taken
            # - Remaining: 100% - 30% = 70%
            # - LPS gets its share (30%) + Spring's unclaimed (40%) = 70% of ORIGINAL
            # But that would exceed budget if SOS took 30%
            #
            # Let me check scenario 4 line 528-531:
            # "SOS skipped, LPS entry (Spring taken): LPS gets SOS's 30% + LPS 30% = 60%"
            # So Spring took 40%, leaving 60%, and LPS gets all 60% (SOS's 30% + LPS's 30%)
            #
            # So the pattern is: LPS gets unclaimed allocations + its own
            # Scenario 2: Spring unclaimed (40%), SOS claimed (30%), LPS claims 40% + 30% = 70%
            # But wait, that's 30% + 70% = 100%, which is fine!
            #
            # I think I misread. Let me recheck line 287-293...
            # "LPS gets Spring's allocation: bmad_pct = 0.40 + 0.30 = 0.70"
            # Wait no, that says 0.70, not 0.40
            #
            # Ah I see the confusion - there are TWO scenarios:
            # Line 108-111: "If Spring skipped AND SOS taken: LPS gets 60% (rebalanced)"
            # Line 287-293: "If Spring skipped, LPS entry (but has SOS): LPS gets 70%"
            #
            # These contradict! Let me check the test at line 287:
            # test_rebalance_lps_gets_60_percent_when_spring_skipped()
            # "Create Campaign with SOS position but NO Spring"
            # "Assert: bmad_allocation_pct == 0.60 (60% = 40% Spring + 30% LPS - SOS already took 30%)"
            #
            # That comment is wrong math. I think it should be:
            # Spring skipped (40% available), LPS normal (30%), but we don't double-count
            # If SOS took 30% from the budget, and Spring's 40% is available,
            # then LPS gets Spring's 40% + nothing extra? Or LPS's 30%?
            #
            # I think the cleanest interpretation:
            # - Spring's 40% was not claimed → available for reallocation
            # - LPS's 30% is its normal share
            # - Spring's unclaimed 40% gets added to LPS → 40% + 30% = 70%
            # - But the test says 60%...
            #
            # Actually, re-reading line 291:
            # "bmad_allocation_pct == 0.60 (60% = 40% Spring + 30% LPS - SOS already took 30%)"
            # I think this is saying: of the REMAINING budget after SOS took 30%,
            # LPS gets a bigger share. But that doesn't make sense with percentages.
            #
            # Let me look at the actual allocation in practice:
            # - Campaign budget: 5%
            # - Spring 40% of 5% = 2.0% (not taken)
            # - SOS 30% of 5% = 1.5% (TAKEN)
            # - LPS normal would be 30% of 5% = 1.5%
            # - Remaining budget: 5% - 1.5% = 3.5%
            # - If LPS gets "rebalanced", it should get the 2.0% that Spring didn't take
            # - So LPS gets 2.0% + 1.5% = 3.5% (the full remaining budget)
            # - 3.5% / 5% = 0.70 = 70%
            #
            # But test says 60%. Let me check if maybe it's:
            # LPS gets Spring's allocation (40%) + LPS keeps its original (20% not 30%)?
            # No, that doesn't match the BMAD model.
            #
            # I'm going to implement based on the clearest statement in the rebalancing
            # logic section lines 145-167, which shows the actual code:
            # Line 154-157: "If not has_spring and new_pattern_type == LPS:"
            #   "If has_sos: Return (True, 'Spring not taken...', Decimal('0.60'))"
            #
            # So the code explicitly says 0.60 when Spring not taken, SOS taken, LPS entry.
            # And line 158: "Else: Return (True, ..., Decimal('1.0'))" for both skipped.
            #
            # I'll implement exactly as specified in lines 145-167.

            # Spring skipped, SOS taken
            if not has_spring and has_sos:
                self.logger.info(
                    "campaign_rebalanced",
                    campaign_id=str(campaign.id),
                    pattern_type=new_pattern_type,
                    original_allocation=float(original_bmad_pct),
                    adjusted_allocation=0.60,
                    rebalance_reason="Spring not taken, reallocating to LPS",
                )
                return (
                    True,
                    "Spring not taken, reallocating to LPS",
                    Decimal("0.60"),
                )

            # Scenario 4: SOS skipped, LPS entry (Spring taken)
            if has_spring and not has_sos:
                self.logger.info(
                    "campaign_rebalanced",
                    campaign_id=str(campaign.id),
                    pattern_type=new_pattern_type,
                    original_allocation=float(original_bmad_pct),
                    adjusted_allocation=0.60,
                    rebalance_reason="SOS not taken, reallocating 30% to LPS",
                )
                return (
                    True,
                    "SOS not taken, reallocating 30% to LPS",
                    Decimal("0.60"),
                )

        # No rebalancing needed
        return (False, None, original_bmad_pct)
