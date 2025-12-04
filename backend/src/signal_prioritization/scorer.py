"""
Signal Scorer - FR28 Priority Scoring Algorithm (Story 9.3).

Purpose:
--------
Implements FR28 weighted scoring algorithm to rank concurrent signals by:
- Confidence (40%): Pattern detection quality
- R-multiple (30%): Risk/reward potential
- Pattern priority (30%): Pattern type rarity and strategic value

Algorithm:
----------
1. Normalize confidence (70-95) to [0.0, 1.0]
2. Normalize R-multiple (2.0-5.0) to [0.0, 1.0]
3. Normalize pattern priority (1-4) to [0.0, 1.0] (inverted: lower = higher)
4. Calculate weighted score: (conf * 0.40) + (r * 0.30) + (pattern * 0.30)
5. Scale to 0-100 range

Pattern Priority Order (AC: 2, 3):
-----------------------------------
- Spring (1): Highest priority - rarest pattern, best R-multiple (3-5R)
- LPS (2): Second priority - better entry than SOS direct
- SOS (3): Third priority - breakout confirmation, higher entry
- UTAD (4): Lowest priority - distribution pattern (sell signal)

Author: Story 9.3 (Signal Prioritization Logic)
"""

from datetime import UTC, datetime
from decimal import Decimal

import structlog

from src.models.priority import PatternPriorityOrder, PriorityComponents, PriorityScore
from src.models.signal import TradeSignal

logger = structlog.get_logger()


class SignalScorer:
    """
    Signal scorer implementing FR28 priority algorithm (AC: 1, 4).

    Calculates priority scores for signals using weighted normalization
    of confidence, R-multiple, and pattern priority.
    """

    def __init__(
        self,
        min_confidence: int = 70,
        max_confidence: int = 95,
        min_r_multiple: Decimal = Decimal("2.0"),
        max_r_multiple: Decimal = Decimal("5.0"),
    ):
        """
        Initialize scorer with normalization ranges.

        Parameters:
        -----------
        min_confidence : int
            Minimum confidence score (default: 70 from FR26)
        max_confidence : int
            Maximum confidence score (default: 95 from FR26)
        min_r_multiple : Decimal
            Minimum R-multiple (default: 2.0 from FR17)
        max_r_multiple : Decimal
            Maximum R-multiple for normalization (default: 5.0)
        """
        self.min_confidence = min_confidence
        self.max_confidence = max_confidence
        self.min_r_multiple = min_r_multiple
        self.max_r_multiple = max_r_multiple

        # FR28 weights (AC: 1)
        self.weights = {
            "confidence": Decimal("0.40"),
            "r_multiple": Decimal("0.30"),
            "pattern": Decimal("0.30"),
        }

        self.logger = logger.bind(component="signal_scorer")

    def normalize_confidence(self, confidence: int) -> Decimal:
        """
        Normalize confidence score (70-95) to range [0.0, 1.0] (AC: 1).

        Formula: (confidence - min) / (max - min)
        Example: confidence=85 → (85-70)/(95-70) = 0.60

        Clamping: Values outside range clipped to [0.0, 1.0]

        Parameters:
        -----------
        confidence : int
            Confidence score (typically 70-95)

        Returns:
        --------
        Decimal
            Normalized confidence in range [0.0, 1.0]
        """
        if confidence < self.min_confidence:
            return Decimal("0.0")
        if confidence > self.max_confidence:
            return Decimal("1.0")

        normalized = Decimal(confidence - self.min_confidence) / Decimal(
            self.max_confidence - self.min_confidence
        )
        return normalized.quantize(Decimal("0.01"))

    def normalize_r_multiple(self, r_multiple: Decimal) -> Decimal:
        """
        Normalize R-multiple (2.0-5.0) to range [0.0, 1.0] (AC: 1).

        Formula: (r - min) / (max - min)
        Example: r=3.5 → (3.5-2.0)/(5.0-2.0) = 0.50

        Clamping: Values outside range clipped to [0.0, 1.0]

        Parameters:
        -----------
        r_multiple : Decimal
            R-multiple (typically 2.0-5.0)

        Returns:
        --------
        Decimal
            Normalized R-multiple in range [0.0, 1.0]
        """
        if r_multiple < self.min_r_multiple:
            return Decimal("0.0")
        if r_multiple > self.max_r_multiple:
            return Decimal("1.0")

        normalized = (r_multiple - self.min_r_multiple) / (
            self.max_r_multiple - self.min_r_multiple
        )
        return normalized.quantize(Decimal("0.01"))

    def normalize_pattern_priority(self, pattern_type: str) -> Decimal:
        """
        Normalize pattern priority (1-4) to range [0.0, 1.0] (AC: 2, 3).

        Pattern priority order (AC: 2):
        - Spring (1): Normalized = 1.0 (highest)
        - LPS (2): Normalized = 0.67
        - SOS (3): Normalized = 0.33
        - UTAD (4): Normalized = 0.0 (lowest)

        Formula: (max - priority) / (max - min)
        Inversion: Lower priority number = higher score

        Parameters:
        -----------
        pattern_type : str
            Pattern type: "SPRING" | "LPS" | "SOS" | "UTAD"

        Returns:
        --------
        Decimal
            Normalized pattern priority in range [0.0, 1.0]

        Raises:
        -------
        ValueError
            If pattern_type not in valid patterns
        """
        if pattern_type not in ["SPRING", "LPS", "SOS", "UTAD"]:
            raise ValueError(
                f"Invalid pattern_type: {pattern_type}. " f"Must be one of: SPRING, LPS, SOS, UTAD"
            )

        priority = PatternPriorityOrder[pattern_type].value
        max_priority = 4  # UTAD
        min_priority = 1  # SPRING

        # Invert: lower priority number = higher normalized score
        normalized = Decimal(max_priority - priority) / Decimal(max_priority - min_priority)
        return normalized.quantize(Decimal("0.01"))

    def calculate_priority_score(self, signal: TradeSignal) -> PriorityScore:
        """
        Calculate FR28 priority score for signal (AC: 4).

        Algorithm:
        ----------
        1. Normalize confidence (70-95) → [0.0, 1.0]
        2. Normalize R-multiple (2.0-5.0) → [0.0, 1.0]
        3. Normalize pattern priority (1-4) → [0.0, 1.0]
        4. Apply FR28 weights: (conf * 0.40) + (r * 0.30) + (pattern * 0.30)
        5. Scale to 0-100 range

        Example Calculation (Spring):
        -----------------------------
        - confidence=85: (85-70)/(95-70) = 0.60
        - r_multiple=3.5: (3.5-2.0)/(5.0-2.0) = 0.50
        - pattern=SPRING: (4-1)/(4-1) = 1.0
        - score = (0.60 * 0.40) + (0.50 * 0.30) + (1.0 * 0.30)
        - score = 0.24 + 0.15 + 0.30 = 0.69
        - scaled = 0.69 * 100 = 69.0

        Parameters:
        -----------
        signal : TradeSignal
            Trade signal with confidence_score, r_multiple, pattern_type

        Returns:
        --------
        PriorityScore
            Priority score with components and weighted calculation

        Raises:
        -------
        ValueError
            If signal.confidence_score not in [70, 95]
            If signal.r_multiple < 2.0
            If signal.pattern_type not in valid patterns
        """
        # Validate signal fields
        if signal.confidence_score < 70 or signal.confidence_score > 95:
            raise ValueError(
                f"Signal confidence_score must be in [70, 95]. Got: {signal.confidence_score}"
            )

        if signal.r_multiple < Decimal("2.0"):
            raise ValueError(f"Signal r_multiple must be >= 2.0. Got: {signal.r_multiple}")

        if signal.pattern_type not in ["SPRING", "LPS", "SOS", "UTAD"]:
            raise ValueError(
                f"Signal pattern_type must be one of: SPRING, LPS, SOS, UTAD. "
                f"Got: {signal.pattern_type}"
            )

        # Normalize components to [0.0, 1.0]
        confidence_normalized = self.normalize_confidence(signal.confidence_score)
        r_normalized = self.normalize_r_multiple(signal.r_multiple)
        pattern_normalized = self.normalize_pattern_priority(signal.pattern_type)

        # Apply FR28 weights (AC: 1)
        weighted_score = (
            (confidence_normalized * self.weights["confidence"])
            + (r_normalized * self.weights["r_multiple"])
            + (pattern_normalized * self.weights["pattern"])
        )

        # Scale to 0-100 range (AC: 4)
        final_score = weighted_score * 100
        final_score = final_score.quantize(Decimal("0.01"))

        # Build PriorityComponents
        pattern_priority = PatternPriorityOrder[signal.pattern_type].value

        components = PriorityComponents(
            confidence_score=signal.confidence_score,
            confidence_normalized=confidence_normalized,
            r_multiple=signal.r_multiple,
            r_normalized=r_normalized,
            pattern_type=signal.pattern_type,  # type: ignore
            pattern_priority=pattern_priority,
            pattern_normalized=pattern_normalized,
        )

        # Build PriorityScore
        priority_score = PriorityScore(
            signal_id=signal.id,
            priority_score=final_score,
            components=components,
            weights=self.weights,
            calculated_at=datetime.now(UTC),
            rank=None,  # Set by priority queue
        )

        # Log score calculation
        self.logger.info(
            "priority_score_calculated",
            signal_id=str(signal.id),
            pattern_type=signal.pattern_type,
            confidence=signal.confidence_score,
            r_multiple=str(signal.r_multiple),
            priority_score=str(final_score),
            confidence_norm=str(confidence_normalized),
            r_norm=str(r_normalized),
            pattern_norm=str(pattern_normalized),
        )

        return priority_score
