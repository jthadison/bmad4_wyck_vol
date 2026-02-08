"""
Wyckoff Campaign Detector (Story 12.8 Tasks 1-5).

Purpose:
--------
Detects and tracks complete Wyckoff Accumulation/Distribution campaigns from
backtest trade data, validates pattern sequences, tracks phase progression,
and calculates campaign-level metrics.

Business Context:
-----------------
Wyckoff methodology teaches that individual patterns are meaningless without
campaign context. A Spring pattern in isolation tells you nothing - but a Spring
following PS→SC→AR sequence in Phase C of an Accumulation campaign is a high-
probability long setup.

Campaign tracking provides critical insights:
- Campaign completion rates (% reaching Markup/Markdown)
- Sequential validation (pattern prerequisites met)
- Campaign P&L vs individual trade P&L
- Phase progression analysis

Author: Story 12.8
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

import structlog

from src.models.backtest import BacktestTrade, CampaignPerformance

logger = structlog.get_logger(__name__)


class WyckoffCampaignDetector:
    """
    Detect and track Wyckoff Accumulation/Distribution campaigns.

    Provides campaign lifecycle tracking from initial patterns (PS/BC) through
    phase progression (A→B→C→D→E) to completion (JUMP/DECLINE) or failure.

    Example:
        detector = WyckoffCampaignDetector()
        campaigns = detector.detect_campaigns(trades)
        for campaign in campaigns:
            print(f"{campaign.campaign_type}: {campaign.status}")
    """

    # Wyckoff pattern sequences for valid campaigns
    ACCUMULATION_PATTERNS = [
        "PS",  # Preliminary Support (Phase A start)
        "SC",  # Selling Climax (Phase A)
        "AR",  # Automatic Rally (Phase A end / Phase B start)
        "SECONDARY_TEST",  # Secondary Test (Phase B)
        "ST",  # Secondary Test (Phase B) - alternative name
        "SPRING",  # Spring (Phase C - critical shakeout)
        "TEST",  # Test of Spring (Phase C)
        "SOS",  # Sign of Strength (Phase D start)
        "LPS",  # Last Point of Support (Phase D)
        "BACKUP",  # Backup to support (Phase D)
        "BU",  # Backup (Phase D) - alternative name
        "JUMP",  # Jump into Markup (Phase E)
    ]

    DISTRIBUTION_PATTERNS = [
        "PSY",  # Preliminary Supply (Phase A start)
        "BC",  # Buying Climax (Phase A)
        "AR",  # Automatic Reaction (Phase A end / Phase B start)
        "SECONDARY_TEST",  # Secondary Test (Phase B)
        "ST",  # Secondary Test (Phase B) - alternative name
        "UTAD",  # Upthrust After Distribution (Phase C)
        "TEST",  # Test of UTAD (Phase C)
        "SOW",  # Sign of Weakness (Phase D start)
        "LPSY",  # Last Point of Supply (Phase D)
        "BACKUP",  # Backup to resistance (Phase D)
        "BU",  # Backup (Phase D) - alternative name
        "DECLINE",  # Decline into Markdown (Phase D end)
    ]

    # Pattern to phase mapping
    PATTERN_TO_PHASE = {
        # Accumulation phases
        "PS": "PHASE_A",
        "SC": "PHASE_A",
        "AR": "PHASE_B",
        "SECONDARY_TEST": "PHASE_B",
        "ST": "PHASE_B",
        "SPRING": "PHASE_C",
        "TEST": "PHASE_C",
        "SOS": "PHASE_D",
        "LPS": "PHASE_D",
        "BACKUP": "PHASE_D",
        "BU": "PHASE_D",
        "JUMP": "PHASE_E",
        # Distribution phases
        "PSY": "PHASE_A",
        "BC": "PHASE_A",
        "UTAD": "PHASE_D",
        "SOW": "PHASE_D",
        "LPSY": "PHASE_D",
        "DECLINE": "PHASE_D",
    }

    # Pattern prerequisites (what must come before this pattern)
    PATTERN_PREREQUISITES = {
        "SPRING": ["SC", "AR"],  # Spring requires Selling Climax and Automatic Rally
        "SOS": ["SPRING", "TEST"],  # SOS requires Spring or Test (at least one)
        "LPS": ["SOS"],  # LPS requires Sign of Strength
        "JUMP": ["SOS", "LPS"],  # JUMP requires Phase D patterns
        "UTAD": ["BC", "AR"],  # UTAD requires Buying Climax and Automatic Reaction
        "SOW": ["UTAD", "TEST"],  # SOW requires UTAD or Test
        "LPSY": ["SOW"],  # LPSY requires Sign of Weakness
        "DECLINE": ["SOW", "LPSY"],  # DECLINE requires Phase D patterns
    }

    def __init__(self, campaign_window_days: int = 90):
        """
        Initialize campaign detector.

        Args:
            campaign_window_days: Maximum days between patterns in same campaign (default 90)
        """
        self.campaign_window_days = campaign_window_days
        self.logger = logger.bind(component="campaign_detector")

    def detect_campaigns(self, trades: list[BacktestTrade]) -> list[CampaignPerformance]:
        """
        Detect all campaigns from backtest trades (Story 12.8 Task 1).

        Groups trades into campaigns by symbol and temporal proximity, validates
        pattern sequences, tracks phase progression, and calculates campaign metrics.

        Args:
            trades: List of backtest trades with pattern_type field

        Returns:
            List of CampaignPerformance objects

        Example:
            detector = WyckoffCampaignDetector()
            campaigns = detector.detect_campaigns(trades)
            # Returns: [CampaignPerformance(campaign_type="ACCUMULATION", ...)]
        """
        if not trades:
            return []

        # Filter trades with Wyckoff patterns only
        pattern_trades = [t for t in trades if t.pattern_type is not None]
        if not pattern_trades:
            return []

        self.logger.info("Detecting campaigns", total_trades=len(pattern_trades))

        # Sort by entry timestamp for sequential processing
        sorted_trades = sorted(pattern_trades, key=lambda t: t.entry_timestamp)

        # Group trades into campaigns by symbol
        campaigns_by_symbol = self._group_trades_by_campaign(sorted_trades)

        # Build campaign performance objects
        all_campaigns = []
        for symbol, campaign_groups in campaigns_by_symbol.items():
            for campaign_trades in campaign_groups:
                campaign = self._build_campaign_performance(campaign_trades)
                all_campaigns.append(campaign)

        self.logger.info(
            "Campaign detection complete",
            campaigns_detected=len(all_campaigns),
            accumulation=len([c for c in all_campaigns if c.campaign_type == "ACCUMULATION"]),
            distribution=len([c for c in all_campaigns if c.campaign_type == "DISTRIBUTION"]),
        )

        return all_campaigns

    def _group_trades_by_campaign(
        self, sorted_trades: list[BacktestTrade]
    ) -> dict[str, list[list[BacktestTrade]]]:
        """
        Group trades into campaigns by symbol and temporal proximity.

        Trades are grouped into the same campaign if:
        - Same symbol
        - Within campaign_window_days of previous trade
        - Pattern sequence is valid

        Args:
            sorted_trades: Trades sorted by entry_timestamp

        Returns:
            Dict mapping symbol → list of campaign trade groups
        """
        campaigns_by_symbol: dict[str, list[list[BacktestTrade]]] = {}

        for trade in sorted_trades:
            symbol = trade.symbol
            pattern = trade.pattern_type.upper() if trade.pattern_type else ""

            # Initialize symbol tracking
            if symbol not in campaigns_by_symbol:
                campaigns_by_symbol[symbol] = [[trade]]
                continue

            # Get current campaign for this symbol
            current_campaign = campaigns_by_symbol[symbol][-1]
            last_trade = current_campaign[-1]

            # Check if trade should be part of current campaign or start new one
            time_delta = trade.entry_timestamp - last_trade.entry_timestamp
            days_apart = time_delta.days

            # Start new campaign if time gap too large
            if days_apart > self.campaign_window_days:
                campaigns_by_symbol[symbol].append([trade])
                continue

            # Validate pattern fits in campaign sequence
            current_patterns = [t.pattern_type.upper() for t in current_campaign if t.pattern_type]

            # Determine if pattern is valid next step
            if self._is_valid_next_pattern(current_patterns, pattern):
                current_campaign.append(trade)
            else:
                # Pattern breaks sequence - start new campaign
                campaigns_by_symbol[symbol].append([trade])

        return campaigns_by_symbol

    def _is_valid_next_pattern(self, current_patterns: list[str], new_pattern: str) -> bool:
        """
        Validate if new_pattern is a valid next step in campaign (Story 12.8 Task 2).

        Checks:
        - Pattern belongs to same campaign type (Accumulation or Distribution)
        - Pattern prerequisites are met
        - Pattern sequence is valid

        Args:
            current_patterns: Patterns already in campaign
            new_pattern: Candidate pattern to add

        Returns:
            True if pattern is valid next step, False otherwise
        """
        if not current_patterns:
            # First pattern - must be campaign starter (PS or PSY/BC)
            return new_pattern in ["PS", "PSY", "BC"]

        # Determine campaign type from first pattern
        first_pattern = current_patterns[0]
        if first_pattern in self.ACCUMULATION_PATTERNS:
            campaign_type = "ACCUMULATION"
            valid_patterns = self.ACCUMULATION_PATTERNS
        elif first_pattern in self.DISTRIBUTION_PATTERNS:
            campaign_type = "DISTRIBUTION"
            valid_patterns = self.DISTRIBUTION_PATTERNS
        else:
            # Unknown pattern type
            return False

        # Check if new pattern belongs to this campaign type
        if new_pattern not in valid_patterns:
            return False

        # Check prerequisites if pattern requires them
        if new_pattern in self.PATTERN_PREREQUISITES:
            required = self.PATTERN_PREREQUISITES[new_pattern]

            # Determine if ALL prerequisites required or just ONE
            # SPRING requires BOTH SC and AR (all prerequisites)
            # SOS/SOW/JUMP/DECLINE require at least one prerequisite
            if new_pattern in ["SPRING", "UTAD"]:
                # ALL prerequisites must be present
                if not all(req in current_patterns for req in required):
                    self.logger.warning(
                        "Pattern prerequisite failed - ALL required",
                        pattern=new_pattern,
                        required=required,
                        current=current_patterns,
                    )
                    return False
            else:
                # At least ONE prerequisite must be present
                if not any(req in current_patterns for req in required):
                    self.logger.warning(
                        "Pattern prerequisite failed - at least ONE required",
                        pattern=new_pattern,
                        required=required,
                        current=current_patterns,
                    )
                    return False

        return True

    def _build_campaign_performance(
        self, campaign_trades: list[BacktestTrade]
    ) -> CampaignPerformance:
        """
        Build CampaignPerformance object from campaign trades (Story 12.8 Tasks 3-5).

        Calculates:
        - Campaign type (ACCUMULATION or DISTRIBUTION)
        - Phase progression
        - Campaign status (COMPLETED, FAILED, IN_PROGRESS)
        - Campaign P&L and R:R metrics

        Args:
            campaign_trades: All trades in this campaign

        Returns:
            CampaignPerformance with complete metrics
        """
        # Basic metadata
        first_trade = campaign_trades[0]
        last_trade = campaign_trades[-1]

        symbol = first_trade.symbol
        campaign_id = uuid4()
        start_date = first_trade.entry_timestamp
        end_date = last_trade.exit_timestamp if last_trade.exit_timestamp else None

        # Determine campaign type and pattern sequence
        pattern_sequence = [t.pattern_type.upper() for t in campaign_trades if t.pattern_type]
        first_pattern = pattern_sequence[0] if pattern_sequence else "UNKNOWN"

        if first_pattern in self.ACCUMULATION_PATTERNS:
            campaign_type = "ACCUMULATION"
        elif first_pattern in self.DISTRIBUTION_PATTERNS:
            campaign_type = "DISTRIBUTION"
        else:
            campaign_type = "ACCUMULATION"  # Default to ACCUMULATION

        # Track phases completed throughout campaign
        phases_completed = []
        for pattern in pattern_sequence:
            phase = self.PATTERN_TO_PHASE.get(pattern, "UNKNOWN")
            if phase not in phases_completed and phase != "UNKNOWN":
                phases_completed.append(phase)

        # Determine completion stage (highest phase reached)
        if phases_completed:
            # Extract phase letter and find highest
            phase_order = ["PHASE_A", "PHASE_B", "PHASE_C", "PHASE_D", "PHASE_E"]
            highest_phase_idx = max(
                phase_order.index(p) for p in phases_completed if p in phase_order
            )
            completion_stage = phase_order[highest_phase_idx]
        else:
            completion_stage = "UNKNOWN"

        # Determine campaign status and completion reason
        status, completion_reason = self._determine_campaign_status(
            pattern_sequence, campaign_type, end_date
        )

        # Calculate campaign P&L
        total_pnl = sum(t.realized_pnl for t in campaign_trades)

        # Calculate campaign return percentage (based on first trade capital)
        first_trade_value = first_trade.entry_price * Decimal(str(first_trade.quantity))
        if first_trade_value > 0:
            campaign_return_pct = (total_pnl / first_trade_value) * Decimal("100")
        else:
            campaign_return_pct = Decimal("0")

        # Calculate average R-multiple for campaign (risk_reward_realized)
        r_multiples = [t.r_multiple for t in campaign_trades if t.r_multiple is not None]
        if r_multiples:
            risk_reward_realized = sum(r_multiples) / Decimal(len(r_multiples))
        else:
            risk_reward_realized = Decimal("0")

        # Calculate markup/markdown returns if campaign completed
        avg_markup_return = None
        avg_markdown_return = None
        if status == "COMPLETED":
            if campaign_type == "ACCUMULATION" and "JUMP" in pattern_sequence:
                # Markup return is campaign_return_pct for completed accumulation
                avg_markup_return = campaign_return_pct.quantize(Decimal("0.0001"))
            elif campaign_type == "DISTRIBUTION" and "DECLINE" in pattern_sequence:
                # Markdown return is campaign_return_pct for completed distribution
                avg_markdown_return = campaign_return_pct.quantize(Decimal("0.0001"))

        # Count patterns
        total_patterns_detected = len(pattern_sequence)
        patterns_traded = len(campaign_trades)  # All detected patterns were traded in backtest

        return CampaignPerformance(
            campaign_id=str(campaign_id),
            campaign_type=campaign_type,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            status=status,
            total_patterns_detected=total_patterns_detected,
            patterns_traded=patterns_traded,
            completion_stage=completion_stage,
            pattern_sequence=pattern_sequence,
            failure_reason=completion_reason if status == "FAILED" else None,
            total_campaign_pnl=total_pnl,
            risk_reward_realized=risk_reward_realized,
            avg_markup_return=avg_markup_return,
            avg_markdown_return=avg_markdown_return,
            phases_completed=phases_completed,
        )

    def _determine_campaign_status(
        self,
        pattern_sequence: list[str],
        campaign_type: str,
        end_date: Optional[datetime],
    ) -> tuple[str, Optional[str]]:
        """
        Determine campaign status and completion reason (Story 12.8 Task 4).

        Campaign States:
        - COMPLETED: Campaign reached final phase (JUMP for Accumulation, DECLINE for Distribution)
        - FAILED: Campaign broke sequence, failed prerequisites, or abandoned
        - IN_PROGRESS: Campaign active with valid sequence

        Args:
            pattern_sequence: List of patterns in campaign
            campaign_type: ACCUMULATION or DISTRIBUTION
            end_date: Campaign end date (None if IN_PROGRESS)

        Returns:
            Tuple of (status, completion_reason)
        """
        if not pattern_sequence:
            return ("FAILED", "NO_PATTERNS")

        last_pattern = pattern_sequence[-1]

        # Check for completed campaigns
        if campaign_type == "ACCUMULATION" and last_pattern == "JUMP":
            return ("COMPLETED", "MARKUP_REACHED")
        elif campaign_type == "DISTRIBUTION" and last_pattern == "DECLINE":
            return ("COMPLETED", "MARKDOWN_REACHED")

        # Check for failed campaigns
        # Note: Sequence validation happens in _is_valid_next_pattern, so if we're here
        # the sequence is valid. Failure reasons are pattern-specific.

        # If campaign ended but didn't reach completion phase, it failed
        if end_date is not None:
            if campaign_type == "ACCUMULATION":
                # Failed to reach JUMP
                if "SOS" in pattern_sequence:
                    return ("FAILED", "MARKUP_FAILED")
                else:
                    return ("FAILED", "PHASE_D_NOT_REACHED")
            elif campaign_type == "DISTRIBUTION":
                # Failed to reach DECLINE
                if "SOW" in pattern_sequence:
                    return ("FAILED", "MARKDOWN_FAILED")
                else:
                    return ("FAILED", "PHASE_D_NOT_REACHED")

        # Campaign still in progress
        return ("IN_PROGRESS", None)
