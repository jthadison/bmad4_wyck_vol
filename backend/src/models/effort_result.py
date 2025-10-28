"""
Effort vs. Result Classification Enum for Wyckoff Volume Analysis.

This module defines the EffortResult enum used to classify bars based on
the relationship between effort (volume) and result (spread).
"""

from enum import Enum


class EffortResult(str, Enum):
    """
    Wyckoff effort vs. result classification.

    This enum classifies bars based on the relationship between volume (effort)
    and spread (result), which is a core principle of Wyckoff Volume Spread Analysis.

    Values:
        CLIMACTIC: High volume + Wide spread = Strong effort with strong result.
            Indicates climactic action, potential reversal point.
            Examples: Selling Climax (SC), Buying Climax (BC), UTAD.
            Typical phases: End of Phase A (SC), End of Phase D (UTAD/BC).

        ABSORPTION: High volume + Narrow spread = Strong effort with weak result.
            Indicates professional absorption of supply/demand.
            Examples: Spring, Test, Secondary Test, Last Point of Support (LPS).
            Typical phases: Phase C (Spring, Test), Phase D (LPS).
            Combined with close_position:
                - close_position >= 0.7 = Bullish absorption (accumulation)
                - close_position <= 0.3 = Bearish absorption (distribution)

        NO_DEMAND: Low volume + Narrow spread = Weak effort with weak result.
            Indicates lack of interest, potential reversal if in uptrend.
            Examples: Test bars in Phase C, weak rallies in distribution.
            Typical phases: Phase C (Tests), Phase D (weak rallies).

        NORMAL: Balanced or mixed effort and result.
            Normal market activity with no special signal.
            Examples: Continuation bars, trading range bars.
    """

    CLIMACTIC = "CLIMACTIC"
    ABSORPTION = "ABSORPTION"
    NO_DEMAND = "NO_DEMAND"
    NORMAL = "NORMAL"
