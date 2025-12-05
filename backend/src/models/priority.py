"""
Priority Score Models - Signal Prioritization (Story 9.3).

Purpose:
--------
Data models for FR28 priority scoring algorithm that ranks concurrent signals
by confidence (40%), R-multiple (30%), and pattern priority (30%).

Models:
-------
- PatternPriorityOrder: Enum defining pattern priority (Spring > LPS > SOS > UTAD)
- PriorityComponents: Breakdown of score components (confidence, R-multiple, pattern)
- PriorityScore: Final priority score with weighted calculation (0-100)

FR28 Scoring Algorithm:
------------------------
Priority score = (confidence_norm * 0.40) + (r_norm * 0.30) + (pattern_norm * 0.30)

Pattern Priority Rationale (AC: 2, 3):
- Spring (1): Rarest pattern, highest R-multiple (3-5R), best entry price
- LPS (2): Better entry than direct SOS, reduced risk
- SOS (3): Breakout confirmation, higher entry price
- UTAD (4): Distribution pattern, lowest priority for long-only system

Author: Story 9.3 (Signal Prioritization Logic)
"""

from datetime import UTC, datetime
from decimal import Decimal
from enum import IntEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PatternPriorityOrder(IntEnum):
    """
    Pattern priority for signal ranking (AC: 2).

    Lower number = higher priority.

    Rationale (AC: 3):
    ------------------
    - SPRING (1): Rarest pattern with highest R-multiple potential (3-5R)
    - LPS (2): Better entry than direct SOS with reduced risk
    - SOS (3): Breakout confirmation but higher entry price
    - UTAD (4): Distribution pattern (sell signal), lowest priority for long-only
    """

    SPRING = 1  # Highest priority
    LPS = 2
    SOS = 3
    UTAD = 4  # Lowest priority


class PriorityComponents(BaseModel):
    """
    Breakdown of priority score components for transparency (AC: 1).

    All normalized values in range [0.0, 1.0] for weighted calculation.
    """

    confidence_score: int = Field(..., ge=70, le=95, description="Pattern confidence 70-95% (FR26)")
    confidence_normalized: Decimal = Field(
        ..., ge=0, le=1, description="Normalized confidence 0.0-1.0"
    )
    r_multiple: Decimal = Field(..., ge=Decimal("2.0"), description="R-multiple 2.0+ (FR17)")
    r_normalized: Decimal = Field(..., ge=0, le=1, description="Normalized R-multiple 0.0-1.0")
    pattern_type: Literal["SPRING", "LPS", "SOS", "UTAD"]
    pattern_priority: int = Field(..., ge=1, le=4, description="Pattern priority 1-4 (AC: 2)")
    pattern_normalized: Decimal = Field(
        ..., ge=0, le=1, description="Normalized pattern priority 0.0-1.0"
    )

    model_config = {"json_encoders": {Decimal: str}}


class PriorityScore(BaseModel):
    """
    Priority score for signal ranking (AC: 1, 4).

    FR28 Weighted Scoring:
    ----------------------
    - Confidence: 40% (pattern detection quality is most important)
    - R-multiple: 30% (risk/reward potential is second priority)
    - Pattern priority: 30% (pattern type rarity and strategic value)

    Final score range: 0.0-100.0 (AC: 4)

    Heap Ordering (AC: 5, 6):
    --------------------------
    Implements __lt__ for Python heapq priority queue.
    Higher priority_score = higher priority (inverted for min-heap).
    Tie-breaking uses pattern_priority (lower number wins).
    """

    signal_id: UUID
    priority_score: Decimal = Field(..., ge=0, le=100, description="Final score 0-100 (AC: 4)")
    components: PriorityComponents
    weights: dict[str, Decimal] = Field(
        default={
            "confidence": Decimal("0.40"),
            "r_multiple": Decimal("0.30"),
            "pattern": Decimal("0.30"),
        },
        description="FR28 weights",
    )
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    rank: int | None = Field(default=None, description="Position in queue (1=highest)")

    model_config = {
        "json_encoders": {
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        }
    }

    def __lt__(self, other: "PriorityScore") -> bool:
        """
        Comparison for heap ordering (AC: 5, 6).

        Higher priority_score = higher priority (inverted for min-heap).
        Tie-breaking: use pattern_priority (lower number wins).

        Parameters:
        -----------
        other : PriorityScore
            Other score to compare against

        Returns:
        --------
        bool
            True if self has higher priority than other
        """
        if self.priority_score != other.priority_score:
            # Invert for max-heap behavior (heapq is min-heap by default)
            return self.priority_score > other.priority_score

        # Tie-breaking: lower pattern_priority number = higher priority
        return self.components.pattern_priority < other.components.pattern_priority
