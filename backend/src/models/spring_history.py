"""
SpringHistory dataclass for tracking multiple springs in a trading range.

This module defines the SpringHistory dataclass which provides complete spring
detection history including all detected springs, generated signals, best selections,
volume trend analysis, and risk assessment.

Purpose:
--------
Track all springs in chronological order and identify the highest quality spring/signal
using Wyckoff quality criteria (volume → penetration → recovery hierarchy).

Wyckoff Multi-Spring Principles:
---------------------------------
Multiple springs in the same trading range indicate:
- Increasing supply absorption (each successive spring tests lower)
- Declining volume = professional accumulation pattern (LOW risk)
- Rising volume = potential distribution warning (HIGH risk)
- Last valid spring is typically the strongest signal (closest to markup)

Quality Hierarchy (for best spring selection):
-----------------------------------------------
1. **Volume quality** (primary): Lower volume ratio = better (professional)
2. **Penetration depth** (secondary): Deeper penetration = more supply absorbed
3. **Recovery speed** (tiebreaker): Faster recovery = stronger demand

Example:
--------
>>> from backend.src.models.spring_history import SpringHistory
>>> from backend.src.models.spring import Spring
>>> from backend.src.models.spring_signal import SpringSignal
>>> from datetime import datetime, timezone
>>> from uuid import uuid4
>>>
>>> # Create history
>>> history = SpringHistory(
...     symbol="AAPL",
...     trading_range_id=uuid4()
... )
>>>
>>> # Add first spring (0.5x volume, 2% penetration, 3-bar recovery)
>>> spring1 = Spring(...)  # volume_ratio=0.5
>>> signal1 = SpringSignal(...)  # confidence=75
>>> history.add_spring(spring1, signal1)
>>>
>>> # Add second spring (0.3x volume, 2.5% penetration, 2-bar recovery)
>>> spring2 = Spring(...)  # volume_ratio=0.3 (LOWER volume = better)
>>> signal2 = SpringSignal(...)  # confidence=85
>>> history.add_spring(spring2, signal2)
>>>
>>> # Best spring has LOWEST volume (0.3x < 0.5x)
>>> assert history.best_spring == spring2
>>> assert history.best_signal == signal2  # Highest confidence
>>> assert history.spring_count == 2
>>> assert history.volume_trend == "DECLINING"  # 0.5 → 0.3 = declining
>>> assert history.risk_level == "LOW"  # Declining volume = professional

Author: Story 5.6 - SpringDetector Module Integration
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Optional
from uuid import UUID

import structlog

from src.models.spring import Spring
from src.models.spring_signal import SpringSignal

logger = structlog.get_logger(__name__)


@dataclass
class SpringHistory:
    """
    Complete history of spring detection for a trading range.

    Tracks all detected springs in chronological order, identifies the best spring
    using Wyckoff quality criteria, and analyzes volume trends for risk assessment.

    Attributes:
        symbol: Ticker symbol (e.g., "AAPL")
        trading_range_id: Associated trading range UUID
        springs: All detected springs (chronological order by timestamp)
        signals: All generated signals
        best_spring: Highest quality spring (Wyckoff criteria: volume → penetration → recovery)
        best_signal: Highest confidence signal
        volume_trend: Volume trend through springs ("DECLINING" | "STABLE" | "RISING")
        spring_count: Total number of springs detected
        risk_level: Risk assessment ("LOW" | "MODERATE" | "HIGH")
        detection_timestamp: When history was created (UTC)
        spring_timing: Temporal spacing classification ("COMPRESSED" | "NORMAL" | "HEALTHY" | "SINGLE_SPRING")
        spring_intervals: Bar counts between successive springs (chronological order)
        avg_spring_interval: Average spacing between springs for campaign quality assessment
        test_quality_trend: Test progression classification ("IMPROVING" | "STABLE" | "DEGRADING" | "INSUFFICIENT_DATA")
        test_quality_metrics: Detailed test quality progression data for analysis

    Wyckoff Quality Criteria (best spring selection):
        1. Volume quality (primary): Lower volume ratio = better
        2. Penetration depth (secondary): Deeper penetration = more supply absorbed
        3. Recovery speed (tiebreaker): Faster recovery = stronger demand

    Volume Trend Analysis:
        - DECLINING: Each spring has lower volume (professional accumulation ✅)
        - STABLE: Volume remains consistent through springs
        - RISING: Volume increases through springs (warning sign ⚠️)

    Risk Assessment:
        - LOW: Single spring <0.3x volume OR declining multi-spring trend
        - MODERATE: Single spring 0.3-0.7x volume OR stable trend
        - HIGH: Single spring >=0.7x volume OR rising trend
    """

    symbol: str
    trading_range_id: UUID
    springs: list[Spring] = field(default_factory=list)
    signals: list[SpringSignal] = field(default_factory=list)
    best_spring: Optional[Spring] = None
    best_signal: Optional[SpringSignal] = None
    volume_trend: str = "STABLE"  # DECLINING | STABLE | RISING
    spring_count: int = 0
    risk_level: str = "MODERATE"  # LOW | MODERATE | HIGH
    detection_timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Story 5.6.2: Spring Timing Analysis (AC 1)
    spring_timing: str = "SINGLE_SPRING"  # COMPRESSED | NORMAL | HEALTHY | SINGLE_SPRING
    spring_intervals: list[int] = field(default_factory=list)  # Bar counts between springs
    avg_spring_interval: float = 0.0  # Average spacing for campaign assessment

    # Story 5.6.2: Test Quality Progression (AC 2)
    test_quality_trend: str = (
        "INSUFFICIENT_DATA"  # IMPROVING | STABLE | DEGRADING | INSUFFICIENT_DATA
    )
    test_quality_metrics: dict = field(default_factory=dict)  # Detailed progression data

    def add_spring(self, spring: Spring, signal: Optional[SpringSignal] = None) -> None:
        """
        Add spring to history (maintains chronological order).

        Updates spring count, maintains chronological order, selects best spring
        using Wyckoff quality hierarchy, and updates best signal if provided.

        Args:
            spring: Detected spring pattern
            signal: Generated signal (optional, depends on test confirmation)

        Wyckoff Logic:
            - Best spring = lowest volume (primary criterion)
            - If volume equal, deeper penetration wins
            - If still equal, faster recovery wins

        Example:
            >>> history = SpringHistory(symbol="AAPL", trading_range_id=uuid4())
            >>> spring1 = Spring(..., volume_ratio=Decimal("0.5"))
            >>> spring2 = Spring(..., volume_ratio=Decimal("0.3"))  # Lower volume
            >>> history.add_spring(spring1)
            >>> history.add_spring(spring2)
            >>> assert history.best_spring == spring2  # 0.3 < 0.5
        """
        # Add to springs list (maintain chronological order)
        self.springs.append(spring)
        self.springs.sort(key=lambda s: s.bar.timestamp)

        # Add signal if provided
        if signal:
            self.signals.append(signal)
            self.signals.sort(key=lambda s: s.spring_bar_timestamp)

        # Update spring count
        self.spring_count = len(self.springs)

        # Update best spring using Wyckoff quality criteria
        if self.best_spring is None:
            self.best_spring = spring
        elif self._is_better_spring(spring, self.best_spring):
            self.best_spring = spring

        # Update best signal (highest confidence)
        if signal:
            if self.best_signal is None:
                self.best_signal = signal
            elif signal.confidence > self.best_signal.confidence:
                self.best_signal = signal

        # Log addition
        logger.info(
            "spring_added_to_history",
            symbol=self.symbol,
            spring_id=str(spring.id),
            spring_timestamp=spring.bar.timestamp.isoformat(),
            volume_ratio=float(spring.volume_ratio),
            penetration_pct=float(spring.penetration_pct),
            recovery_bars=spring.recovery_bars,
            spring_count=self.spring_count,
            has_signal=signal is not None,
        )

    def _is_better_spring(self, new: Spring, current: Spring) -> bool:
        """
        Determine if new spring is higher quality than current best spring.

        Uses Wyckoff quality hierarchy:
        1. Volume quality (primary): Lower volume = better (professional)
        2. Penetration depth (secondary): Deeper penetration = more supply absorbed
        3. Recovery speed (tiebreaker): Faster recovery = stronger demand

        Args:
            new: New spring to evaluate
            current: Current best spring

        Returns:
            True if new spring is better quality than current

        Wyckoff Rationale:
            - Lower volume proves professional accumulation (not public distribution)
            - Deeper penetration shows more supply absorption at lower prices
            - Faster recovery confirms strong underlying demand

        Example:
            >>> spring1 = Spring(..., volume_ratio=Decimal("0.5"), penetration_pct=Decimal("0.02"))
            >>> spring2 = Spring(..., volume_ratio=Decimal("0.3"), penetration_pct=Decimal("0.02"))
            >>> history._is_better_spring(spring2, spring1)
            True  # 0.3 < 0.5 (lower volume wins)
        """
        # 1. Volume quality (PRIMARY criterion)
        # Lower volume = professional accumulation (better)
        if new.volume_ratio < current.volume_ratio:
            logger.debug(
                "new_spring_better_volume",
                new_volume=float(new.volume_ratio),
                current_volume=float(current.volume_ratio),
                reason="Lower volume = professional accumulation",
            )
            return True
        elif new.volume_ratio > current.volume_ratio:
            return False

        # 2. Penetration depth (SECONDARY criterion)
        # Deeper penetration = more supply absorbed (better)
        if new.penetration_pct > current.penetration_pct:
            logger.debug(
                "new_spring_better_penetration",
                new_penetration=float(new.penetration_pct),
                current_penetration=float(current.penetration_pct),
                reason="Deeper penetration = more supply absorbed",
            )
            return True
        elif new.penetration_pct < current.penetration_pct:
            return False

        # 3. Recovery speed (TIEBREAKER)
        # Faster recovery = stronger demand (better)
        if new.recovery_bars < current.recovery_bars:
            logger.debug(
                "new_spring_better_recovery",
                new_recovery_bars=new.recovery_bars,
                current_recovery_bars=current.recovery_bars,
                reason="Faster recovery = stronger demand",
            )
            return True

        # Springs are equal quality (keep current as best)
        return False
