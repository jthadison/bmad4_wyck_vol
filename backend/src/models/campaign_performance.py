"""
Campaign Performance Metrics - Story 22.10

Purpose:
--------
Performance tracking for campaigns extracted from the monolithic Campaign
dataclass for improved Single Responsibility Principle compliance.

Contains P&L tracking, R-multiples, excursion tracking, and win/loss status
for campaign performance analysis.

Classes:
--------
- CampaignPerformanceMetrics: Performance tracking dataclass

Author: Story 22.10 - Decompose Campaign Dataclass
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


class ExitReason(str, Enum):
    """
    Campaign exit reasons.

    Attributes:
        TARGET_HIT: Reached profit target (Jump level)
        STOP_OUT: Stop loss triggered
        TIME_EXIT: Manual time-based exit
        PHASE_E: Phase E completion exit
        MANUAL_EXIT: User-initiated manual exit
        UNKNOWN: Exit reason unknown/not specified
    """

    TARGET_HIT = "TARGET_HIT"
    STOP_OUT = "STOP_OUT"
    TIME_EXIT = "TIME_EXIT"
    PHASE_E = "PHASE_E"
    MANUAL_EXIT = "MANUAL_EXIT"
    UNKNOWN = "UNKNOWN"


class WinLossStatus(str, Enum):
    """
    Campaign win/loss classification.

    Attributes:
        OPEN: Campaign still active
        WIN: Campaign closed with positive P&L
        LOSS: Campaign closed with negative P&L
        BREAKEVEN: Campaign closed with zero or near-zero P&L
    """

    OPEN = "open"
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


@dataclass
class CampaignPerformanceMetrics:
    """
    Performance tracking for a campaign.

    Contains realized and unrealized P&L, R-multiples, and excursion tracking
    for comprehensive performance analysis.

    Attributes:
        # P&L tracking
        profit_loss: Total P&L (realized + unrealized)
        unrealized_pnl: Current unrealized P&L
        realized_pnl: Final realized P&L after exit

        # R-multiple tracking
        r_multiple: Achieved R-multiple (points_gained / risk_per_share)
        target_r_multiple: Expected R-multiple based on targets

        # Price movement
        points_gained: Exit price - entry price
        percent_gain: Percentage gain/loss

        # Excursion tracking (for trade quality analysis)
        max_favorable_excursion: Highest unrealized profit during trade
        max_adverse_excursion: Deepest unrealized loss during trade

        # Status
        win_loss_status: WIN, LOSS, BREAKEVEN, or OPEN
        exit_reason: Reason for campaign exit
        exit_price: Final exit price
        exit_timestamp: Campaign exit timestamp

        # Duration
        duration_bars: Campaign duration in bars

    Example:
        >>> from decimal import Decimal
        >>> perf = CampaignPerformanceMetrics(
        ...     profit_loss=Decimal("500.00"),
        ...     r_multiple=Decimal("2.5"),
        ...     win_loss_status=WinLossStatus.WIN
        ... )
        >>> perf.calculate_efficiency()
        0.8  # If MFE was $625
    """

    # P&L tracking
    profit_loss: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")

    # R-multiple tracking
    r_multiple: Optional[Decimal] = None
    target_r_multiple: Decimal = Decimal("2.0")

    # Price movement
    points_gained: Optional[Decimal] = None
    percent_gain: float = 0.0

    # Excursion tracking
    max_favorable_excursion: Decimal = Decimal("0")
    max_adverse_excursion: Decimal = Decimal("0")

    # Status
    win_loss_status: WinLossStatus = WinLossStatus.OPEN
    exit_reason: ExitReason = ExitReason.UNKNOWN
    exit_price: Optional[Decimal] = None
    exit_timestamp: Optional[datetime] = None

    # Duration
    duration_bars: int = 0

    # Phase E tracking (Story 13.6.1)
    phase_e_progress_percent: Decimal = Decimal("0")

    def update_excursions(self, current_pnl: Decimal) -> None:
        """
        Update MFE/MAE based on current P&L.

        Maximum Favorable Excursion (MFE) tracks the highest unrealized profit
        reached during the trade. Maximum Adverse Excursion (MAE) tracks the
        deepest unrealized loss. These metrics are used to analyze trade
        management quality.

        Args:
            current_pnl: Current unrealized P&L

        Example:
            >>> perf = CampaignPerformanceMetrics()
            >>> perf.update_excursions(Decimal("100"))  # Profit
            >>> perf.max_favorable_excursion
            Decimal('100')
            >>> perf.update_excursions(Decimal("-50"))  # Drawdown
            >>> perf.max_adverse_excursion
            Decimal('-50')
            >>> perf.update_excursions(Decimal("200"))  # New high
            >>> perf.max_favorable_excursion
            Decimal('200')
        """
        if current_pnl > self.max_favorable_excursion:
            self.max_favorable_excursion = current_pnl
        if current_pnl < self.max_adverse_excursion:
            self.max_adverse_excursion = current_pnl

    def calculate_efficiency(self) -> Optional[float]:
        """
        Calculate trade efficiency (actual gain / MFE).

        Trade efficiency measures how much of the maximum favorable move
        was captured. A value of 1.0 means all potential profit was captured.
        Values below 1.0 indicate profit was left on the table.

        Returns:
            Trade efficiency ratio (0.0-1.0+) or None if MFE is zero

        Example:
            >>> perf = CampaignPerformanceMetrics(
            ...     profit_loss=Decimal("400"),
            ...     max_favorable_excursion=Decimal("500")
            ... )
            >>> perf.calculate_efficiency()
            0.8  # Captured 80% of max profit
        """
        if self.max_favorable_excursion == Decimal("0"):
            return None
        return float(self.profit_loss / self.max_favorable_excursion)

    def calculate_mae_ratio(self) -> Optional[float]:
        """
        Calculate MAE ratio (actual loss / risk taken).

        The MAE ratio shows how deep the drawdown was relative to the
        final outcome. Useful for assessing whether stops are too tight.

        Returns:
            MAE ratio or None if no adverse excursion

        Example:
            >>> perf = CampaignPerformanceMetrics(
            ...     profit_loss=Decimal("200"),
            ...     max_adverse_excursion=Decimal("-100")
            ... )
            >>> perf.calculate_mae_ratio()
            -0.5  # Drawdown was half the final profit
        """
        if self.profit_loss == Decimal("0"):
            return None
        return float(self.max_adverse_excursion / self.profit_loss)

    def finalize(
        self,
        exit_price: Decimal,
        entry_price: Decimal,
        risk_per_share: Optional[Decimal],
        exit_reason: ExitReason,
        exit_timestamp: datetime,
    ) -> None:
        """
        Finalize performance metrics at campaign exit.

        Calculates final P&L, R-multiple, win/loss status, and records
        exit details.

        Args:
            exit_price: Campaign exit price
            entry_price: Campaign entry price
            risk_per_share: Risk per share for R-multiple calculation
            exit_reason: Reason for exit
            exit_timestamp: Exit timestamp

        Example:
            >>> perf = CampaignPerformanceMetrics()
            >>> perf.finalize(
            ...     exit_price=Decimal("155.00"),
            ...     entry_price=Decimal("150.00"),
            ...     risk_per_share=Decimal("2.00"),
            ...     exit_reason=ExitReason.TARGET_HIT,
            ...     exit_timestamp=datetime.now()
            ... )
            >>> perf.points_gained
            Decimal('5.00')
            >>> perf.r_multiple
            Decimal('2.5')
            >>> perf.win_loss_status
            WinLossStatus.WIN
        """
        # Calculate points gained
        self.points_gained = exit_price - entry_price

        # Calculate profit/loss (simplified - actual depends on position size)
        self.realized_pnl = self.points_gained
        self.profit_loss = self.realized_pnl
        self.unrealized_pnl = Decimal("0")

        # Calculate R-multiple
        if risk_per_share and risk_per_share > Decimal("0"):
            self.r_multiple = self.points_gained / risk_per_share
        else:
            self.r_multiple = None

        # Calculate percent gain
        if entry_price > Decimal("0"):
            self.percent_gain = float((self.points_gained / entry_price) * Decimal("100"))

        # Determine win/loss status
        if self.points_gained > Decimal("0"):
            self.win_loss_status = WinLossStatus.WIN
        elif self.points_gained < Decimal("0"):
            self.win_loss_status = WinLossStatus.LOSS
        else:
            self.win_loss_status = WinLossStatus.BREAKEVEN

        # Record exit details
        self.exit_price = exit_price
        self.exit_reason = exit_reason
        self.exit_timestamp = exit_timestamp

    def is_winner(self) -> bool:
        """
        Check if campaign was a winner.

        Returns:
            True if win_loss_status is WIN

        Example:
            >>> perf = CampaignPerformanceMetrics(win_loss_status=WinLossStatus.WIN)
            >>> perf.is_winner()
            True
        """
        return self.win_loss_status == WinLossStatus.WIN

    def is_closed(self) -> bool:
        """
        Check if campaign is closed (not OPEN status).

        Returns:
            True if campaign has exited

        Example:
            >>> perf = CampaignPerformanceMetrics(win_loss_status=WinLossStatus.OPEN)
            >>> perf.is_closed()
            False
        """
        return self.win_loss_status != WinLossStatus.OPEN

    def target_reached(self) -> bool:
        """
        Check if R-multiple target was reached.

        Returns:
            True if r_multiple >= target_r_multiple

        Example:
            >>> perf = CampaignPerformanceMetrics(
            ...     r_multiple=Decimal("3.0"),
            ...     target_r_multiple=Decimal("2.0")
            ... )
            >>> perf.target_reached()
            True
        """
        if self.r_multiple is None:
            return False
        return self.r_multiple >= self.target_r_multiple
