"""
Wyckoff Phase enumeration for accumulation cycle classification.

Defines the five phases of Wyckoff accumulation:
- Phase A: Stopping action (SC + AR)
- Phase B: Building cause (STs, Tests)
- Phase C: Final test (Spring, Shakeout)
- Phase D: Markup beginning (SOS, LPS)
- Phase E: Markup continuation
"""

from enum import Enum


class WyckoffPhase(str, Enum):
    """
    Wyckoff market phases in accumulation cycle.

    Wyckoff Interpretation:
    - Phase A: Stopping action - Panic selling exhausts (SC), demand steps in (AR)
    - Phase B: Building cause - Accumulation consolidation (STs, Tests oscillate in range)
    - Phase C: Final test - Spring shakeout tests final supply (Spring below Creek)
    - Phase D: Markup beginning - Demand dominates, breaks resistance (SOS above Ice)
    - Phase E: Markup continuation - Sustained uptrend after breakout

    Used in:
    - Story 4.4: Phase classification logic
    - Story 4.5: Phase confidence scoring
    - Story 4.6: Phase progression validation
    - Story 4.7: PhaseDetector integration
    """

    A = "A"  # Stopping action (SC + AR)
    B = "B"  # Building cause (STs, Tests)
    C = "C"  # Final test (Spring, Shakeout)
    D = "D"  # Markup beginning (SOS, LPS)
    E = "E"  # Markup continuation
